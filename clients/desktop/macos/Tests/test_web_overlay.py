"""Overlay asset tests against the verified runtime baseline; never starts or contacts an Exo core."""
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile

root = Path(__file__).resolve().parents[1]
repo = root.parents[2]
baseline = 'f9d1e423'  # runtime whose server.py, service.py and static assets the overlay verifies
pinned = 'cc38bd3af1cd6769b6f0894d7db1dd92a1060e0d2ac2a9c14f8368254431b823'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


if subprocess.run(['git', '-C', str(repo), 'cat-file', '-e', baseline + '^{commit}'], capture_output=True).returncode:
    print('SKIP: baseline runtime ' + baseline + ' is not in this checkout\'s history')
    sys.exit(0)
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
print('PASS: overlay stylesheet is the pinned runtime stylesheet for each flag; without a flag the runtime stylesheet is kept')
