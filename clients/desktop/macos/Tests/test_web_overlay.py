"""Overlay asset tests against the verified runtime baseline; never starts or contacts an Exo core."""
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile

root = Path(__file__).resolve().parents[1]
repo = root.parents[2]
baseline = '716dad79'  # runtime whose server.py, service.py and static assets the overlay verifies
pinned = 'cc38bd3af1cd6769b6f0894d7db1dd92a1060e0d2ac2a9c14f8368254431b823'
exo_main = '0ef042e5'  # reviewed exo main whose server.py and service.py the overlay also accepts


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


shallow = subprocess.run(['git', '-C', str(repo), 'rev-parse', '--is-shallow-repository'], capture_output=True, text=True).stdout.strip() == 'true'
for commit in (baseline, exo_main):
    if subprocess.run(['git', '-C', str(repo), 'cat-file', '-e', commit + '^{commit}'], capture_output=True).returncode:
        if shallow:
            print('SKIP: runtime ' + commit + ' is not in this shallow checkout\'s history')
            sys.exit(0)
        # A full clone must have both pins: a missing one means the pin is stale (for example after a history rewrite).
        print('FAIL: runtime ' + commit + ' is not in this full checkout\'s history; update the pins in this test, prepare-web-overlay.py and the README')
        sys.exit(1)
with tempfile.TemporaryDirectory(prefix='overlay fixture ') as tmp:
    base = Path(tmp)
    runtime = base / 'runtime'
    runtime.mkdir()
    archive = subprocess.run(['git', '-C', str(repo), 'archive', baseline, 'plugins'], capture_output=True, check=True).stdout
    subprocess.run(['tar', '-x', '-C', str(runtime)], input=archive, check=True)
    plugins = runtime / 'plugins'
    original = digest(plugins / 'exo-command/exo_command/static/style.css')
    flags = (['--with-model-picker'], ['--with-approval-shortcuts'], ['--with-model-picker', '--with-approval-shortcuts'])
    for n, extra in enumerate(flags):
        out = base / ('out %d' % n)
        subprocess.run([sys.executable, str(root / 'prepare-web-overlay.py'), '--plugins', str(plugins), '--output', str(out), *extra], check=True, capture_output=True)
        static = out / 'exo-command/exo_command/static'
        assert digest(static / 'style.css') == pinned, (extra, digest(static / 'style.css'))
        if '--with-model-picker' in extra:
            assert (static / 'model_picker.js').is_file() and 'createModelPicker' in (static / 'chat.js').read_text(), extra
        if '--with-approval-shortcuts' in extra:
            assert digest(static / 'approvals.js') == digest(repo / 'plugins/exo-command/exo_command/static/approvals.js'), extra
    plain = base / 'out plain'
    subprocess.run([sys.executable, str(root / 'prepare-web-overlay.py'), '--plugins', str(plugins), '--output', str(plain)], check=True, capture_output=True)
    assert digest(plain / 'exo-command/exo_command/static/style.css') == original

    # Exo main's server.py and service.py are accepted for the replay fix; the asset flags still refuse its assets.
    main_runtime = base / 'main runtime'
    main_runtime.mkdir()
    archive = subprocess.run(['git', '-C', str(repo), 'archive', exo_main, 'plugins'], capture_output=True, check=True).stdout
    subprocess.run(['tar', '-x', '-C', str(main_runtime)], input=archive, check=True)
    main_plugins = main_runtime / 'plugins'
    main_plain = base / 'main plain'
    subprocess.run([sys.executable, str(root / 'prepare-web-overlay.py'), '--plugins', str(main_plugins), '--output', str(main_plain)], check=True, capture_output=True)
    for name in ('server.py', 'service.py'):
        assert digest(main_plain / 'exo-command/exo_command' / name) == digest(repo / 'plugins/exo-command/exo_command' / name), name
    for name in ('chat.js', 'providers.js', 'style.css', 'approvals.js'):
        assert digest(main_plain / 'exo-command/exo_command/static' / name) == digest(main_plugins / 'exo-command/exo_command/static' / name), name
    for extra, refused in ((['--with-model-picker'], 'chat.js'), (['--with-approval-shortcuts'], 'approvals.js')):
        out = base / ('main ' + extra[0])
        run = subprocess.run([sys.executable, str(root / 'prepare-web-overlay.py'), '--plugins', str(main_plugins), '--output', str(out), *extra], capture_output=True, text=True)
        assert run.returncode and run.stderr.rstrip().endswith('baseline: ' + refused) and not out.exists(), (extra, run.stderr)
print('PASS: overlay stylesheet is the pinned runtime stylesheet for each flag; without a flag the runtime stylesheet is kept;'
      ' exo main ' + exo_main + ' takes the replay fix and its assets are refused by both flags')
