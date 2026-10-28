"""Real disposable Git histories and fake gh; no network, host credentials or runtime changes."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / 'scripts/sync_upstream.py'
spec = importlib.util.spec_from_file_location('sync_upstream', SCRIPT)
sync = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = sync
spec.loader.exec_module(sync)


def git(path, *args):
    return subprocess.run(['git', '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                           '-c', 'commit.gpgsign=false', *args], cwd=path, check=True,
                          text=True, capture_output=True,
                          env={'PATH': os.defpath, 'HOME': str(path), 'GIT_CONFIG_GLOBAL': os.devnull,
                               'GIT_CONFIG_NOSYSTEM': '1'}).stdout.strip()


@pytest.fixture
def repos(tmp_path):
    upstream, fork, writer = (tmp_path / name for name in ('upstream.git', 'fork.git', 'writer'))
    git(tmp_path, 'init', '--bare', '--initial-branch=main', str(upstream))
    git(tmp_path, 'clone', str(upstream), str(writer))
    (writer / 'shared').write_text('base\n')
    git(writer, 'add', '.'); git(writer, 'commit', '-m', 'base'); git(writer, 'push', 'origin', 'main')
    git(tmp_path, 'clone', '--bare', str(upstream), str(fork))
    state = tmp_path / 'gh-state.json'
    state.write_text(json.dumps({'prs': [], 'issues': [], 'calls': [], 'creates': 0}))
    gh = tmp_path / 'fake gh'
    gh.write_text('#!' + sys.executable + '\n' + r'''
import json,os,sys,subprocess
from pathlib import Path
p=Path(os.environ['FAKE_GH_STATE']);s=json.loads(p.read_text());a=sys.argv[1:];s['calls'].append(a)
def finish(value=None,code=0):
 p.write_text(json.dumps(s))
 if value is not None:print(json.dumps(value))
 sys.exit(code)
if a[0]=='api':
 if 'issues?' in a[-1]:
  if s.get('report_fail'):finish(code=1)
  finish([s['issues']])
 finish(code=1 if s.get('auth_fail') else 0)
if a[:2]==['pr','list']:
 for pr in s['prs']:
  pr['headRefOid']=s.get('pr_oid_override') or subprocess.check_output(['git','--git-dir',os.environ['FAKE_FORK'],'rev-parse','refs/heads/automation/exo-upstream-sync'],text=True).strip()
 finish(s['prs'])
if a[:2]==['pr','create']:
 if s.get('pr_fail'):finish(code=1)
 body=Path(a[a.index('--body-file')+1]).read_text()
 s['creates']+=1;s['prs']=[{'number':1,'isDraft':True,'isCrossRepository':False,'body':body,'baseRefName':'main','headRefName':'automation/exo-upstream-sync','url':'https://example.invalid/pr/1'}]
 finish(code=1 if s.get('create_race') else 0)
if a[:2]==['pr','edit']:
 if s.get('edit_fail'):finish(code=1)
 s['prs'][0]['body']=Path(a[a.index('--body-file')+1]).read_text();finish()
if a[:2]==['issue','create']:
 s['issues'].append({'number':len(s['issues'])+1,'body':Path(a[a.index('--body-file')+1]).read_text()});finish()
finish(code=2)
''')
    gh.chmod(0o700)
    env = {'PATH': os.defpath, 'HOME': str(tmp_path / 'fake-home'), 'FAKE_GH_STATE': str(state),
           'EXO_SYNC_TOKEN': 'synthetic-sync-' + 'credential', 'FAKE_FORK': str(fork)}
    def make(name='sync work', **kw):
        return sync.Sync(sync.Config(tmp_path / name, str(fork), str(upstream), **kw), env=env, gh=str(gh))
    return tmp_path, upstream, fork, writer, state, env, make


def advance(repos, remote, name='upstream-change', shared=False):
    root, upstream, fork, writer, *_ = repos
    if remote == upstream:
        work = writer
    else:
        work = root / ('fork-writer-' + name)
        git(root, 'clone', str(remote), str(work))
    (work / ('shared' if shared else name)).write_text(name + '\n')
    git(work, 'add', '.'); git(work, 'commit', '-m', name); git(work, 'push', 'origin', 'main')
    return git(work, 'rev-parse', 'HEAD')


def update_state(path, **kw):
    data = json.loads(path.read_text()); data.update(kw); path.write_text(json.dumps(data))


def failure(instance, stage):
    with pytest.raises(sync.SyncError) as caught:
        instance.run()
    assert caught.value.stage == stage
    return caught.value


def test_merge_preserves_history_main_and_reuses_one_owned_draft(repos):
    _, upstream, fork, _, state, env, make = repos
    base = advance(repos, fork, 'fork-native-change')
    head = advance(repos, upstream)
    assert 'draft sync PR #1' in make().run()
    merged = git(fork, 'rev-parse', 'refs/heads/' + sync.BRANCH)
    assert git(fork, 'show', '-s', '--format=%P', merged).split() == [base, head]
    assert git(fork, 'rev-parse', 'main') == base
    assert 'draft sync PR #1' in make('second work').run()
    assert git(fork, 'rev-parse', 'refs/heads/' + sync.BRANCH) == merged
    data = json.loads(state.read_text()); assert data['creates'] == 1 and data['prs'][0]['isDraft']
    assert env['EXO_SYNC_TOKEN'] not in state.read_text()
    for args in data['calls']:
        if args[0] in ('pr', 'issue'):
            assert args[args.index('--repo') + 1] == sync.FORK


def test_no_change_creates_no_remote_branch_or_pr(repos):
    _, _, fork, _, state, _, make = repos
    assert make().run().startswith('unchanged:')
    assert not json.loads(state.read_text())['prs']
    assert git(fork, 'for-each-ref', '--format=%(refname)', 'refs/heads/') == 'refs/heads/main'


def test_conflict_is_distinct_and_does_not_push(repos):
    _, upstream, fork, _, state, _, make = repos
    advance(repos, upstream, 'canonical', shared=True)
    base = advance(repos, fork, 'native', shared=True)
    error = failure(make(), 'conflict')
    assert git(fork, 'rev-parse', 'main') == base
    reporter = make('unused-report-directory'); reporter.report(error); reporter.report(error)
    data = json.loads(state.read_text()); assert len(data['issues']) == 1
    assert 'failure:conflict:v1' in data['issues'][0]['body']
    assert all(sync.FORK in a[-1] for a in data['calls'] if a[0]=='api' and 'issues?' in a[-1])


@pytest.mark.parametrize('when', [1, 2])
def test_base_drift_refuses_before_pr_and_never_overwrites_main(repos, when):
    _, upstream, fork, _, state, _, make = repos
    advance(repos, upstream)
    instance = make(); original = instance.check_main; calls = 0; advanced = None
    def drifting(base):
        nonlocal calls, advanced
        calls += 1
        if calls == when:
            advanced = advance(repos, fork, 'concurrent-main')
        original(base)
    instance.check_main = drifting
    failure(instance, 'base-drift')
    assert git(fork, 'rev-parse', 'main') == advanced
    assert not json.loads(state.read_text())['prs']


@pytest.mark.parametrize('stage', ['auth', 'fetch', 'push', 'pr'])
def test_failures_remain_separate_and_do_not_create_conflict_issues(repos, stage):
    _, upstream, fork, _, state, _, make = repos
    advance(repos, upstream)
    instance = make()
    if stage == 'auth':update_state(state, auth_fail=True)
    elif stage == 'fetch':instance.config.upstream_url = str(upstream.parent / 'missing.git')
    elif stage == 'push':
        hook = fork / 'hooks/pre-receive'; hook.write_text('#!/bin/sh\nexit 1\n'); hook.chmod(0o700)
    else:update_state(state, pr_fail=True)
    base = git(fork, 'rev-parse', 'main')
    error = failure(instance, stage)
    assert git(fork, 'rev-parse', 'main') == base
    instance.report(error)
    assert 'failure:' + stage + ':v1' in json.loads(state.read_text())['issues'][0]['body']


def test_missing_workflow_token_and_existing_workspace_fail_closed(repos):
    *_, env, make = repos
    env.pop('EXO_SYNC_TOKEN')
    failure(make(), 'auth')
    assert not make().cwd.exists()
    manual = make(manual=True)
    assert manual.run().startswith('unchanged:')  # fake authorized host gh, no token lookup
    failure(make(manual=True), 'workspace')


@pytest.mark.parametrize('human_pr', ['ready', 'unmarked'])
def test_refuses_unexpected_reserved_commits_and_human_prs(repos, human_pr):
    root, upstream, fork, writer, state, _, make = repos
    advance(repos, upstream)
    make().run()
    data = json.loads(state.read_text())
    if human_pr == 'ready':data['prs'][0]['isDraft'] = False
    else:data['prs'][0]['body'] = 'Human-owned PR'
    state.write_text(json.dumps(data))
    before = git(fork, 'rev-parse', 'refs/heads/' + sync.BRANCH)
    failure(make('new work'), 'ownership')
    assert git(fork, 'rev-parse', 'refs/heads/' + sync.BRANCH) == before
    update_state(state, prs=[])
    git(writer, 'fetch', str(fork), sync.BRANCH); git(writer, 'switch', '--detach', 'FETCH_HEAD')
    (writer / 'human').write_text('manual work'); git(writer, 'add', '.'); git(writer, 'commit', '-m', 'human change')
    git(writer, 'push', str(fork), 'HEAD:refs/heads/' + sync.BRANCH)
    failure(make('third work'), 'ownership')


def test_pr_create_race_validates_reused_draft_and_report_errors_are_not_nomatch(repos):
    _, upstream, _, _, state, _, make = repos
    advance(repos, upstream); update_state(state, create_race=True)
    assert 'draft sync PR #1' in make().run()
    update_state(state, report_fail=True)
    with pytest.raises(sync.SyncError) as caught:
        make('unused').report(sync.SyncError('fetch', 'Fetch failed'))
    assert caught.value.stage == 'report'
    assert not json.loads(state.read_text())['issues']


def test_workflow_has_fixed_main_token_draft_concurrency_and_pinned_checkout():
    workflow = (SCRIPT.parents[1] / '.github/workflows/sync-upstream.yml').read_text()
    assert 'ref: main' in workflow and 'persist-credentials: false' in workflow
    assert 'actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5' in workflow
    assert 'cancel-in-progress: false' in workflow and 'EXO_SYNC_TOKEN' in workflow
    assert "vars.EXO_SYNC_ENABLED == 'true'" in workflow
    assert 'secrets.GITHUB_TOKEN' not in workflow and 'git push origin main' not in workflow



def test_existing_bot_branch_merges_new_main_and_upstream_without_rewriting(repos):
    _, upstream, fork, _, state, _, make = repos
    advance(repos, upstream)
    make().run()
    previous = git(fork, 'rev-parse', 'refs/heads/' + sync.BRANCH)
    base = advance(repos, fork, 'later-main')
    incoming = advance(repos, upstream, 'later-upstream')
    make('later sync').run()
    current = git(fork, 'rev-parse', 'refs/heads/' + sync.BRANCH)
    for parent in (previous, base, incoming):
        git(fork, 'merge-base', '--is-ancestor', parent, current)
    assert git(fork, 'rev-parse', 'main') == base
    assert json.loads(state.read_text())['creates'] == 1


def test_inherited_git_context_and_debug_cannot_redirect_owned_work(repos):
    root, upstream, fork, _, _, env, make = repos
    advance(repos, upstream)
    env.update(GIT_DIR=str(fork), GIT_WORK_TREE=str(root), GIT_TRACE=str(root / 'trace'),
               GH_DEBUG='api', GH_HOST='untrusted.invalid')
    instance = make()
    assert instance.run().startswith('draft sync PR')
    assert not (root / 'trace').exists()
    assert instance.env['GH_HOST'] == 'github.com' and 'GH_DEBUG' not in instance.env
    assert 'GIT_DIR' not in instance.env and 'GIT_WORK_TREE' not in instance.env



def test_unmarked_reserved_branch_at_canonical_head_is_not_adopted(repos):
    _, upstream, fork, writer, _, _, make = repos
    advance(repos, upstream)
    git(writer, 'push', str(fork), 'HEAD:refs/heads/' + sync.BRANCH)
    failure(make(), 'ownership')



def test_new_upstream_history_without_tree_changes_creates_no_pr(repos):
    _, _, fork, writer, state, _, make = repos
    git(writer, 'commit', '--allow-empty', '-m', 'metadata-only upstream commit')
    git(writer, 'push', 'origin', 'main')
    assert make().run().startswith('unchanged: merged tree')
    assert not json.loads(state.read_text())['prs']
    assert git(fork, 'for-each-ref', '--format=%(refname)', 'refs/heads/') == 'refs/heads/main'



def test_tracked_symlink_cannot_redirect_private_posting_bodies(repos):
    root, _, _, writer, state, _, make = repos
    outside = root / 'outside-file'; outside.write_text('untouched')
    (writer / 'sync-pr-body.md').symlink_to(outside)
    git(writer, 'add', '.'); git(writer, 'commit', '-m', 'tracked body-name symlink')
    git(writer, 'push', 'origin', 'main')
    instance = make()
    assert instance.run().startswith('draft sync PR')
    assert outside.read_text() == 'untouched'
    data = json.loads(state.read_text())
    assert sync.FOOTER in data['prs'][0]['body']
    body_args = next(a for a in data['calls'] if a[:2] == ['pr', 'create'])
    body = Path(body_args[body_args.index('--body-file') + 1])
    assert not body.is_relative_to(instance.cwd) and body.stat().st_mode & 0o777 == 0o600
    error = sync.SyncError('fetch', 'Fetch failed'); instance.report(error)
    assert sync.FOOTER in json.loads(state.read_text())['issues'][0]['body']


def test_pr_ready_transition_during_merge_refuses_before_branch_push(repos):
    _, upstream, fork, _, state, _, make = repos
    advance(repos, upstream); make().run()
    before = git(fork, 'rev-parse', 'refs/heads/' + sync.BRANCH)
    advance(repos, upstream, 'next-canonical-change')
    instance = make('second work'); original = instance.merge
    def become_ready(ref):
        original(ref)
        if ref == 'upstream/main':
            data = json.loads(state.read_text()); data['prs'][0]['isDraft'] = False
            state.write_text(json.dumps(data))
    instance.merge = become_ready
    failure(instance, 'ownership')
    assert git(fork, 'rev-parse', 'refs/heads/' + sync.BRANCH) == before



def test_after_push_human_branch_update_is_not_claimed_as_reviewed_sync(repos):
    root, upstream, fork, _, state, _, make = repos
    advance(repos, upstream); make().run()
    data = json.loads(state.read_text()); previous_body = data['prs'][0]['body']
    previous_edits = sum(a[:2] == ['pr', 'edit'] for a in data['calls'])
    base = git(fork, 'rev-parse', 'main')
    advance(repos, upstream, 'later-upstream')
    instance = make('second sync'); original = instance.body_file; human_head = None
    def human_advances(text, **kw):
        nonlocal human_head
        work = root / 'human writer'; git(root, 'clone', str(fork), str(work))
        git(work, 'switch', sync.BRANCH)
        (work / 'human-work').write_text('retain human work')
        git(work, 'add', '.'); git(work, 'commit', '-m', 'human branch update')
        git(work, 'push', 'origin', sync.BRANCH)
        human_head = git(work, 'rev-parse', 'HEAD')
        return original(text, **kw)
    instance.body_file = human_advances
    failure(instance, 'branch-drift')
    assert git(fork, 'rev-parse', 'refs/heads/' + sync.BRANCH) == human_head
    assert git(fork, 'rev-parse', 'main') == base
    data = json.loads(state.read_text())
    assert data['prs'][0]['body'] == previous_body
    assert sum(a[:2] == ['pr', 'edit'] for a in data['calls']) == previous_edits


def test_pr_api_head_must_match_prepared_commit_before_edit(repos):
    _, upstream, fork, _, state, _, make = repos
    advance(repos, upstream); make().run()
    data = json.loads(state.read_text()); previous_body = data['prs'][0]['body']
    previous_edits = sum(a[:2] == ['pr', 'edit'] for a in data['calls'])
    head = git(fork, 'rev-parse', 'refs/heads/' + sync.BRANCH)
    update_state(state, pr_oid_override='0' * 40)
    failure(make('second sync'), 'branch-drift')
    assert git(fork, 'rev-parse', 'refs/heads/' + sync.BRANCH) == head
    data = json.loads(state.read_text())
    assert data['prs'][0]['body'] == previous_body
    assert sum(a[:2] == ['pr', 'edit'] for a in data['calls']) == previous_edits


def test_branch_change_during_metadata_edit_is_not_reported_as_success(repos):
    root, upstream, fork, _, _, _, make = repos
    advance(repos, upstream)
    instance = make(); original = instance.gh; human_head = None
    def edit_then_human(*args, **kw):
        nonlocal human_head
        result = original(*args, **kw)
        if args[:2] == ('pr', 'edit'):
            work = root / 'human writer'; git(root, 'clone', str(fork), str(work))
            git(work, 'switch', sync.BRANCH)
            (work / 'human-work').write_text('retain human work')
            git(work, 'add', '.'); git(work, 'commit', '-m', 'human branch update')
            git(work, 'push', 'origin', sync.BRANCH)
            human_head = git(work, 'rev-parse', 'HEAD')
        return result
    instance.gh = edit_then_human
    failure(instance, 'branch-drift')
    assert git(fork, 'rev-parse', 'refs/heads/' + sync.BRANCH) == human_head
