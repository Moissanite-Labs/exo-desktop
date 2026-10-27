"""Run against a disposable copy of the verified attached-runtime plugin baseline."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[4]
HELPER = ROOT / 'clients/desktop/macos/prepare-web-overlay.py'
BASELINE = os.environ.get('EXO_TEST_OVERLAY_BASELINE')
pytestmark = pytest.mark.skipif(not BASELINE, reason='set EXO_TEST_OVERLAY_BASELINE to verified runtime plugins')


@pytest.mark.parametrize('picker', [False, True])
def test_overlay_carries_server_connection_assets_and_preserves_rounds(tmp_path, picker):
    output = tmp_path / 'output'
    args = [sys.executable, str(HELPER), '--plugins', BASELINE, '--output', str(output)]
    if picker:
        args.append('--with-model-picker')
    subprocess.run(args, check=True, capture_output=True)
    web = output / 'exo-command/exo_command'
    for name in ('server.py', 'service.py', 'static/app.js', 'static/bus.js'):
        assert (web / name).read_bytes() == (ROOT / 'plugins/exo-command/exo_command' / name).read_bytes()
    subprocess.run([sys.executable, '-c', 'import exo_command.server'],
                   env={**os.environ, 'PYTHONPATH': str(web.parent) + os.pathsep + str(ROOT / 'src')},
                   check=True, capture_output=True)
    original = (Path(BASELINE) / 'exo-command/exo_command/static/chat.js').read_text()
    if '/rounds' in original:
        assert '/rounds' in (web / 'static/chat.js').read_text()
    if picker:
        assert 'core unavailable' in (web / 'static/chat.js').read_text()
        assert 'Try stop' in (web / 'static/chat.js').read_text()
        assert 'waiting for approval' in (web / 'static/chat.js').read_text()


@pytest.mark.parametrize('name', ['app.js', 'bus.js'])
def test_unknown_connection_asset_rejected_before_output(tmp_path, name):
    source = tmp_path / 'source'
    shutil.copytree(BASELINE, source, ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '.git'))
    (source / 'exo-command/exo_command/static' / name).write_text('unknown baseline')
    output = tmp_path / 'output'
    result = subprocess.run([sys.executable, str(HELPER), '--plugins', str(source), '--output', str(output)], capture_output=True)
    assert result.returncode != 0 and not output.exists()
