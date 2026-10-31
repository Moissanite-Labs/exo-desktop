"""Pane overlay is opt-in and accepts only the verified runtime assets."""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[4]
BASELINE = os.environ.get('EXO_TEST_OVERLAY_BASELINE')
pytestmark = pytest.mark.skipif(not BASELINE, reason='set EXO_TEST_OVERLAY_BASELINE to verified runtime plugins')


@pytest.mark.parametrize('picker', [False, True])
@pytest.mark.parametrize('panes', [False, True])
def test_picker_pane_combinations_preserve_runtime_commands(tmp_path, picker, panes):
    output = tmp_path / 'output'
    args = [sys.executable, str(ROOT / 'clients/desktop/macos/prepare-web-overlay.py'), '--plugins', BASELINE, '--output', str(output)]
    if picker:
        args.append('--with-model-picker')
    if panes:
        args.append('--with-pane-layout')
    original = Path(BASELINE) / 'exo-command/exo_command/static/chat.js'
    before = hashlib.sha256(original.read_bytes()).hexdigest()
    subprocess.run(args, check=True, capture_output=True)
    assets = output / 'exo-command/exo_command/static'
    chat = (assets / 'chat.js').read_text()
    assert '/rounds' in chat
    assert ('attachPaneLayout' in chat) is panes
    assert ('pane_layout.css' in (assets / 'index.html').read_text()) is panes
    if panes:
        assert (assets / 'pane_layout.js').read_bytes() == (ROOT / 'plugins/exo-command/exo_command/static/pane_layout.js').read_bytes()
    assert hashlib.sha256(original.read_bytes()).hexdigest() == before


@pytest.mark.parametrize('name', ['chat.js', 'index.html'])
def test_unknown_pane_baseline_refused_before_output(tmp_path, name):
    source = tmp_path / 'source'
    shutil.copytree(BASELINE, source, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    with (source / 'exo-command/exo_command/static' / name).open('a') as handle:
        handle.write('\nunknown baseline\n')
    output = tmp_path / 'output'
    result = subprocess.run([sys.executable, str(ROOT / 'clients/desktop/macos/prepare-web-overlay.py'), '--plugins', str(source), '--output', str(output), '--with-pane-layout'], capture_output=True)
    assert result.returncode != 0 and not output.exists()
