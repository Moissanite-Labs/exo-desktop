"""Generated overlays must start and optional assets must fail closed on unknown versions."""
from __future__ import annotations

import io
import itertools
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

import pytest

ROOT = Path(__file__).resolve().parents[4]
HELPER = ROOT / 'clients/desktop/macos/prepare-web-overlay.py'
BASE = 'b7c544b695bd7eb8975d5b6a170752e9f4823d5f'


@pytest.fixture(scope='module')
def baseline(tmp_path_factory):
    root = tmp_path_factory.mktemp('overlay-source')
    selected = os.environ.get('EXO_DESKTOP_TEST_PLUGIN_SOURCE')
    if selected:
        shutil.copytree(selected, root / 'plugins', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    else:
        archive = subprocess.check_output(['git', 'archive', BASE, 'plugins/exo-command'], cwd=ROOT)
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            tar.extractall(root, filter='data')
    return root / 'plugins'


def build(source, output, flags=()):
    return subprocess.run([sys.executable, str(HELPER), '--plugins', str(source), '--output', str(output), *flags],
                          cwd=ROOT, capture_output=True, text=True)


def launch(output, tmp_path):
    script = '''
import asyncio
from exo_command.server import WebServer
from exo_command.service import CommandCentre
from exo_command.config import load_settings
class OldCore:
    async def call(self, body):
        assert body.name == 'credentials' and body.args == '{\"action\": \"list\"}'
        return {}
async def run():
    server=WebServer(CommandCentre(load_settings({}),OldCore()),token='fake-overlay-test')
    port=await server.start('127.0.0.1',0)
    try:
        r,w=await asyncio.open_connection('127.0.0.1',port)
        w.write(('GET / HTTP/1.1\\r\\nHost: 127.0.0.1:'+str(port)+'\\r\\n\\r\\n').encode())
        await w.drain()
        data=await asyncio.wait_for(r.read(),2)
        assert b'200 OK' in data and b'<html' in data
        w.close()
        r,w=await asyncio.open_connection('127.0.0.1',port)
        w.write(('GET /api/credentials HTTP/1.1\\r\\nHost: 127.0.0.1:'+str(port)+'\\r\\nX-Exo-Token: fake-overlay-test\\r\\n\\r\\n').encode())
        await w.drain()
        refused=await asyncio.wait_for(r.read(),2)
        assert b'503' in refused and b'upgrade_required' in refused
        w.close()
    finally:
        await server.close()
asyncio.run(run())
print('overlay launched')
'''
    env = {'PATH': os.environ.get('PATH', '/usr/bin:/bin'), 'HOME': str(tmp_path),
           'PYTHONPATH': os.pathsep.join([str(output / 'exo-command'), str(ROOT / 'src')]),
           'EXO_NO_KEYCHAIN': '1', 'EXO_NO_SECRET_SERVICE': '1', 'EXO_KEYS_FILE': str(tmp_path / 'absent.env')}
    result = subprocess.run([sys.executable, '-c', script], env=env, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == 'overlay launched'


@pytest.mark.parametrize(('picker', 'credentials'), list(itertools.product((False, True), repeat=2)))
def test_all_feature_overlay_combinations_import_and_launch(baseline, tmp_path, picker, credentials):
    flags = (['--with-model-picker'] if picker else []) + (['--with-credentials'] if credentials else [])
    output = tmp_path / 'output'
    result = build(baseline, output, flags)
    assert result.returncode == 0, result.stderr
    package = output / 'exo-command/exo_command'
    original = baseline / 'exo-command/exo_command'
    assert (package / 'credentials.py').is_file()  # server import dependency, even with no UI flags
    assert (package / 'api.py').read_bytes() == (original / 'api.py').read_bytes()
    app = (package / 'static/app.js').read_text()
    chat = (package / 'static/chat.js').read_text()
    assert ('["credentials", "Credentials", credentials]' in app) is credentials
    assert ('createModelPicker' in chat) is picker
    if 'max_rounds: maxRounds' in (original / 'static/chat.js').read_text():
        assert 'max_rounds: maxRounds' in chat and 'command.name === "rounds"' in chat
    if not credentials:
        assert (package / 'static/app.js').read_bytes() == (original / 'static/app.js').read_bytes()
    assert not list(output.rglob('*.orig')) and not list(output.rglob('*.rej'))
    launch(output, tmp_path)


@pytest.mark.parametrize('name', ['app.js', 'style.css'])
def test_unknown_credential_asset_rejected_before_output(baseline, tmp_path, name):
    source = tmp_path / 'unknown'
    shutil.copytree(baseline, source)
    file = source / 'exo-command/exo_command/static' / name
    file.write_text(file.read_text() + '\n/* unverified asset */\n')
    output = tmp_path / 'must-not-exist'
    result = build(source, output, ['--with-credentials'])
    assert result.returncode != 0 and 'verified credential baseline' in result.stderr
    assert not output.exists()
