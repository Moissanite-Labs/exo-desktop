#!/usr/bin/env python3
"""Prepare a draft sync PR in an owned Git directory. Never update main or run fetched code."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile

FORK = 'aska-digital/exo-desktop'
UPSTREAM = 'aska-digital/exo'
BRANCH = 'automation/exo-upstream-sync'
MARKER = '<!-- exo-upstream-sync:v1 -->'
TRAILER = 'Exo-Upstream-Sync: v1'
BOT = 'exo-upstream-sync[bot]'
EMAIL = 'exo-upstream-sync[bot]@users.noreply.github.com'
FOOTER = '> Automated posting by agentic team with human oversight.'


class SyncError(Exception):
    def __init__(self, stage, message):
        self.stage = stage
        super().__init__(message)


@dataclass
class Config:
    work_dir: Path
    fork_url: str = f'https://github.com/{FORK}.git'
    upstream_url: str = f'https://github.com/{UPSTREAM}.git'
    manual: bool = False


class Sync:
    def __init__(self, config, *, env=None, gh='gh'):
        self.config = config
        supplied = os.environ if env is None else env
        self.env = {key: value for key, value in supplied.items()
                    if not key.startswith('GIT_') and key not in ('GH_DEBUG', 'GH_HOST', 'GH_REPO')}
        self.env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull,
                        GIT_TERMINAL_PROMPT='0', GH_HOST='github.com')
        self.git_exe = str(Path(shutil.which('git', path=self.env.get('PATH')) or 'git').absolute())
        self.gh_exe = str(Path(shutil.which(gh, path=self.env.get('PATH')) or gh).absolute())
        self.cwd = config.work_dir
        self.artifacts = None

    def body_file(self, text, *, stage='pr'):
        # Never write a body into fetched content: it could contain tracked symlinks.
        try:
            if self.artifacts is None:
                self.artifacts = Path(tempfile.mkdtemp(prefix='exo-sync-artifacts-', dir=self.cwd.parent))
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', prefix='body-', suffix='.md',
                                             dir=self.artifacts, delete=False) as handle:
                handle.write(text + '\n\n' + FOOTER + '\n')
                return Path(handle.name).resolve()  # mkstemp uses O_EXCL and mode 0600
        except OSError:
            raise SyncError(stage, 'Could not create a private posting body') from None

    def run_command(self, args, stage, *, check=True, cwd=None):
        try:
            result = subprocess.run(args, cwd=cwd, env=self.env, capture_output=True, text=True, timeout=120)
        except (OSError, subprocess.TimeoutExpired):
            raise SyncError(stage, f'{stage} operation could not finish') from None
        if check and result.returncode:
            raise SyncError(stage, f'{stage} operation failed. No main update was attempted')
        return result

    def gh(self, *args, stage='pr'):
        return self.run_command([self.gh_exe, *args], stage,
                                cwd=self.cwd if (self.cwd / '.git').is_dir() else None).stdout

    def git(self, *args, stage='merge', check=True, cwd=None):
        return self.run_command([self.git_exe, '-c', 'credential.helper=', '-c',
                                 'credential.helper=!' + shlex.quote(self.gh_exe) + ' auth git-credential',
                                 '-c', 'core.hooksPath=' + os.devnull, '-c', 'commit.gpgsign=false',
                                 '-c', 'user.name=' + BOT, '-c', 'user.email=' + EMAIL, *args],
                                stage, check=check, cwd=cwd or self.cwd)

    def json_gh(self, *args, stage='pr'):
        try:
            return json.loads(self.gh(*args, stage=stage))
        except (ValueError, TypeError):
            raise SyncError(stage, f'{stage} response was invalid') from None

    def ancestor(self, first, second):
        result = self.git('merge-base', '--is-ancestor', first, second, check=False)
        if result.returncode not in (0, 1):
            raise SyncError('merge', 'Could not compare fetched history')
        return result.returncode == 0

    def remote_ref(self, name):
        result = self.git('ls-remote', '--exit-code', '--heads', 'origin', name, stage='fetch', check=False)
        if result.returncode == 2:
            return None
        if result.returncode:
            raise SyncError('fetch', 'Could not read the fork reference')
        rows = result.stdout.splitlines()
        if len(rows) != 1 or rows[0].split()[1] != 'refs/heads/' + name:
            raise SyncError('fetch', 'Fork reference response was unexpected')
        return rows[0].split()[0]

    def check_main(self, base):
        if self.remote_ref('main') != base:
            raise SyncError('base-drift', 'Fork main advanced during sync. Rerun from fresh refs')

    def check_branch(self, prepared, pr=None):
        if self.remote_ref(BRANCH) != prepared or (pr is not None and pr.get('headRefOid') != prepared):
            raise SyncError('branch-drift', 'Reserved sync branch or PR head changed. Maintainer review is required')

    def validate_owned_branch(self):
        extra = self.git('rev-list', 'origin/' + BRANCH, '^origin/main', '^upstream/main').stdout.splitlines()
        if not extra and not self.ancestor('origin/' + BRANCH, 'origin/main'):
            raise SyncError('ownership', 'Reserved branch has no owned merge history. Maintainer review is required')
        for commit in extra:
            raw = self.git('show', '-s', '--format=%an%n%ae%n%P%n%B', commit).stdout
            name, email, parents, body = raw.split('\n', 3)
            if name != BOT or email != EMAIL or len(parents.split()) != 2 or TRAILER not in body.splitlines():
                raise SyncError('ownership', 'Reserved sync branch has unexpected commits. Maintainer review is required')

    def merge(self, ref):
        if self.ancestor(ref, 'HEAD'):
            return
        result = self.git('merge', '--no-ff', '--no-edit', '-m', f'Merge {ref} for desktop sync\n\n{TRAILER}', ref, check=False)
        if result.returncode:
            conflicts = self.git('diff', '--name-only', '--diff-filter=U').stdout
            stage = 'conflict' if conflicts else 'merge'
            raise SyncError(stage, 'Upstream sync needs owner resolution. No automatic conflict fix was made')

    def open_pr(self):
        rows = self.json_gh('pr', 'list', '--repo', FORK, '--head', BRANCH, '--base', 'main', '--state', 'open',
                            '--json', 'number,isDraft,isCrossRepository,body,baseRefName,headRefName,headRefOid,url')
        if not isinstance(rows, list) or len(rows) > 1:
            raise SyncError('pr', 'Sync pull-request lookup was unexpected')
        if rows:
            row = rows[0]
            if (not isinstance(row, dict) or row.get('isDraft') is not True or
                    row.get('isCrossRepository') is not False or
                    type(row.get('number')) is not int or row['number'] < 1 or
                    not isinstance(row.get('body'), str) or MARKER not in row['body'] or
                    row.get('baseRefName') != 'main' or row.get('headRefName') != BRANCH):
                raise SyncError('ownership', 'Existing sync PR is not an owned draft. Maintainer review is required')
            return row
        return None

    def run(self):
        if not self.config.manual:
            token = self.env.get('EXO_SYNC_TOKEN')
            if not token:
                raise SyncError('auth', 'EXO_SYNC_TOKEN is missing. Configure an owner-approved credential or use --manual')
            self.env['GH_TOKEN'] = token
        for repo in (UPSTREAM, FORK):
            self.gh('api', f'repos/{repo}', '--silent', stage='auth')
        try:
            self.cwd.mkdir(mode=0o700)
        except OSError:
            raise SyncError('workspace', 'Work directory must be new and have a writable parent') from None
        self.git('init', '--quiet')
        self.git('remote', 'add', 'origin', self.config.fork_url)
        self.git('remote', 'add', 'upstream', self.config.upstream_url)
        self.git('fetch', '--no-tags', 'origin', 'refs/heads/main:refs/remotes/origin/main', stage='fetch')
        self.git('fetch', '--no-tags', 'upstream', 'refs/heads/main:refs/remotes/upstream/main', stage='fetch')
        base = self.git('rev-parse', 'origin/main').stdout.strip()
        upstream = self.git('rev-parse', 'upstream/main').stdout.strip()
        if self.ancestor('upstream/main', 'origin/main'):
            return 'unchanged: canonical main is already included; no PR created'
        self.open_pr()  # refuse human/ready PRs before any branch push
        remote = self.remote_ref(BRANCH)
        if remote:
            self.git('fetch', '--no-tags', 'origin', f'refs/heads/{BRANCH}:refs/remotes/origin/{BRANCH}', stage='fetch')
            self.validate_owned_branch()
        self.git('switch', '-c', BRANCH, 'origin/' + BRANCH if remote else 'origin/main')
        self.merge('origin/main')
        self.merge('upstream/main')
        tree_diff = self.git('diff', '--quiet', 'origin/main', 'HEAD', check=False)
        if tree_diff.returncode == 0:
            return 'unchanged: merged tree matches fork main; no PR created'
        if tree_diff.returncode != 1:
            raise SyncError('merge', 'Could not compare the merged tree')
        prepared = self.git('rev-parse', 'HEAD').stdout.strip()
        self.check_main(base)
        self.open_pr()  # recheck ownership/draft after merging, immediately before branch mutation
        self.git('push', 'origin', f'HEAD:refs/heads/{BRANCH}', stage='push')  # fast-forward only, never main
        self.check_main(base)
        body = self.body_file(f'{MARKER}\nMerge canonical Exo main `{upstream}` into desktop main `{base}`.\n\n'
                        'History is preserved. This draft requires independent review and tests before merge. '
                        'It does not install, activate or restart a runtime. Main may advance after this check.\n')
        self.check_branch(prepared)
        pr = self.open_pr()  # a ready/human PR must not be edited after the branch push either
        if not pr:
            self.run_command([self.gh_exe, 'pr', 'create', '--repo', FORK, '--draft', '--base', 'main',
                                       '--head', BRANCH, '--title', 'Sync canonical Exo main', '--body-file', str(body)],
                                      'pr', check=False, cwd=self.cwd)
            pr = self.open_pr()  # also validates a concurrent creator; never accept an arbitrary same-head PR
            if not pr:
                raise SyncError('pr', 'Draft sync PR could not be created or verified')
        self.check_branch(prepared, pr)
        self.gh('pr', 'edit', str(pr['number']), '--repo', FORK, '--body-file', str(body))
        confirmed = self.open_pr()
        if not confirmed or confirmed['number'] != pr['number']:
            raise SyncError('pr', 'Sync draft changed during the metadata update. Review its current state')
        self.check_branch(prepared, confirmed)
        return f'draft sync PR #{pr["number"]} is ready for review'

    def report(self, error):
        marker = f'<!-- exo-upstream-sync:failure:{error.stage}:v1 -->'
        pages = self.json_gh('api', '--paginate', '--slurp', f'repos/{FORK}/issues?state=open&per_page=100', stage='report')
        if (not isinstance(pages, list) or any(not isinstance(page, list) for page in pages) or
                any(not isinstance(row, dict) or not isinstance(row.get('body'), (str, type(None)))
                    for page in pages for row in page)):
            raise SyncError('report', 'Failure issue lookup was unexpected')
        if any(isinstance(row, dict) and isinstance(row.get('body'), str) and marker in row['body']
               for page in pages for row in page if isinstance(row, dict) and 'pull_request' not in row):
            return  # no duplicate issue or daily comment spam
        body = self.body_file(marker + '\n' + str(error) + '\nResolve this stage and rerun the draft sync. Never force push main.', stage='report')
        self.gh('issue', 'create', '--repo', FORK, '--title', 'Upstream sync: ' + error.stage,
                '--body-file', str(body), stage='report')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-dir', type=Path, required=True, help='new private directory, never an existing checkout')
    parser.add_argument('--manual', action='store_true', help='use the operator\'s already authorized gh identity')
    parser.add_argument('--report-failures', action='store_true', help='deduplicate stage-specific issues in the desktop fork')
    args = parser.parse_args()
    sync = Sync(Config(args.work_dir, manual=args.manual))
    try:
        print(sync.run())
        return 0
    except SyncError as error:
        print(f'Upstream sync failed [{error.stage}]: {error}', file=sys.stderr)
        if args.report_failures:
            try:
                sync.report(error)
            except SyncError:
                print('Failure reporting also failed [report]; no issue result was assumed', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
