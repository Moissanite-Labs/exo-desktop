"""Optional local integration against the helper's supported original plugin fixture.

Set DESKTOP_OVERLAY_FIXTURE to a read-only baseline plugin directory. Outputs are temporary.
"""
import asyncio
import hashlib
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / 'prepare-web-overlay.py'
ROOT = SCRIPT.parents[3]


@pytest.fixture
def baseline():
    value = os.environ.get('DESKTOP_OVERLAY_FIXTURE')
    if not value:
        pytest.skip('set DESKTOP_OVERLAY_FIXTURE to the verified original runtime plugin fixture')
    return Path(value)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize('picker', [False, True])
def test_helper_dependency_closure_and_older_core_refusal(baseline, tmp_path, picker):
    source = baseline / 'exo-command/exo_command'
    watched = [source / p for p in ('server.py', 'service.py', 'static/providers.js', 'static/chat.js', 'static/style.css')]
    before = [digest(p) for p in watched]
    output = tmp_path / 'plugins'
    subprocess.run([sys.executable, str(SCRIPT), '--plugins', str(baseline), '--output', str(output),
                    *(['--with-model-picker'] if picker else [])], check=True, capture_output=True, text=True)
    copied = output / 'exo-command/exo_command'
    assert digest(copied / 'reasoning.py') == digest(ROOT / 'plugins/exo-command/exo_command/reasoning.py')
    assert not (output / 'src').exists()  # the overlay does not package a replacement core
    if picker:
        assert digest(copied / 'static/reasoning.js') == digest(ROOT / 'plugins/exo-command/exo_command/static/reasoning.js')
        assert '"./reasoning.js"' in (copied / 'static/providers.js').read_text()
    else:
        assert digest(copied / 'static/providers.js') == digest(source / 'static/providers.js')
    assert [digest(p) for p in watched] == before
    spec = importlib.util.spec_from_file_location('overlay_reasoning_edge', copied / 'reasoning.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    class OldSource:
        async def call(self, body):
            assert body.args == '{"action":"list"}'
            error = RuntimeError('older core has no reasoning command')
            error.code = 'not_found'
            raise error
    status, data = asyncio.run(module.handle(SimpleNamespace(source=OldSource()), 'POST', {'level': 'high'}))
    assert status == 503 and data['upgrade_required']


def test_helper_still_rejects_unknown_baseline_before_copy(baseline, tmp_path):
    source = tmp_path / 'source'
    shutil.copytree(baseline, source, ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '.git'))
    path = source / 'exo-command/exo_command/server.py'
    path.write_text(path.read_text() + '\n# unknown fixture version\n')
    output = tmp_path / 'output'
    result = subprocess.run([sys.executable, str(SCRIPT), '--plugins', str(source), '--output', str(output)], capture_output=True)
    assert result.returncode != 0 and not output.exists()
