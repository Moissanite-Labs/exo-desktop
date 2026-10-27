"""Disposable wrapper tests; never starts or contacts an Exo core."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile

root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix="desktop fixture ") as tmp:
    base = Path(tmp)
    fake = base / "fake exo"
    fake.write_text('#!' + sys.executable + '\nimport json, os, sys\nprint(json.dumps({"args": sys.argv[1:], "home": os.environ["EXO_HOME"], "seat": os.environ["EXO_SEAT"], "plugins": os.environ["EXO_PLUGIN_DIRS"], "url": os.environ.get("EXO_COMMAND_URL"), "cwd": os.getcwd()}))\n')
    fake.chmod(0o755)
    wrapper = base / "bundled launcher"
    sockpath = base / "core socket"
    with socket.socket(socket.AF_UNIX) as sock:
        sock.bind(str(sockpath))
        home = base / "shared home"
        plugins = base / "selected plugins"
        subprocess.run([sys.executable, str(root / "make-launcher.py"), '--output', str(wrapper), '--exo', str(fake), '--attach-socket', str(sockpath), '--exo-home', str(home), '--plugins', str(plugins), '--seat', 'canary'], check=True)
        env = dict(os.environ, EXO_COMMAND_URL='http://invalid.example', EXO_HOME='unused')
        proc = subprocess.run([str(wrapper), 'web', '--port', '0', '--no-open'], env=env, capture_output=True, text=True, check=True)
        record = json.loads(proc.stdout)
        assert record == {'args': ['web', '--port', '0', '--no-open', '--socket', str(sockpath)], 'home': str(home), 'seat': 'canary', 'plugins': str(plugins), 'url': None, 'cwd': str(Path.home())}, record
        # The desktop app pins the loopback port itself; the wrapper must not force an available port,
        # or the page origin — and the browser storage attached to it — would move on every launch.
        assert 'EXO_DESKTOP_PORT=0' not in wrapper.read_text(), 'wrapper still forces an available port'
        assert subprocess.run([str(wrapper), 'stop'], capture_output=True).returncode == 64
    sockpath.unlink()
    missing = subprocess.run([str(wrapper), 'web'], capture_output=True)
    assert missing.returncode == 69 and not missing.stdout
    fake.unlink()
    assert subprocess.run([str(wrapper), 'web'], capture_output=True).returncode == 72
print('PASS: attached argv and environment, quoted paths, missing socket/runtime, core stop refused')
