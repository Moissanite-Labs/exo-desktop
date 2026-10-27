"""Packaged-runtime tests; never starts a real Exo core or touches a checkout.

Covers issue #31: the packaged launcher resolves its runtime from its own
bundle location, keeps working when the checkout path is gone, and fails
loudly (exit 72) instead of silently falling back to a moved checkout.
"""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile

root = Path(__file__).resolve().parents[1]
macos = root
repo = macos.parents[2]
make_launcher = macos / 'make-launcher.py'
package_runtime = macos / 'package-runtime.py'


def run(cmd, env=None, check=True):
    return subprocess.run(cmd, env=env, capture_output=True, text=True, check=check)


def fake_cli(src_dir):
    pkg = src_dir / 'exo'
    pkg.mkdir(parents=True)
    (pkg / '__init__.py').write_text('')
    (pkg / 'cli.py').write_text(
        'import json, os, sys\n'
        'def main():\n'
        '    print(json.dumps({"args": sys.argv[1:], "pythonpath": os.environ.get("PYTHONPATH"),\n'
        '                      "plugins": os.environ.get("EXO_PLUGIN_DIRS"), "cwd": os.getcwd()}))\n'
        '    return 0\n')


def fake_bundle(base):
    """A fake app bundle whose 'checkout' path is a separate temp dir."""
    resources = base / 'ExoDesktop.app' / 'Contents' / 'Resources'
    runtime = resources / 'runtime'
    (runtime / 'python' / 'bin').mkdir(parents=True)
    os.symlink(sys.executable, runtime / 'python' / 'bin' / 'python3')
    fake_cli(runtime / 'src')
    (runtime / 'plugins' / 'exo-command' / 'exo_command').mkdir(parents=True)
    (runtime / 'plugins' / 'exo-command' / 'exo_command' / '__init__.py').write_text('')
    return resources, runtime


with tempfile.TemporaryDirectory(prefix='desktop packaged ') as tmp:
    base = Path(tmp)
    home = base / 'fake home'
    home.mkdir()
    env = dict(os.environ, HOME=str(home))
    resources, runtime = fake_bundle(base)
    launcher = resources / 'exo-alpha'
    run([sys.executable, str(make_launcher), '--output', str(launcher), '--packaged'])

    script = launcher.read_text()
    # The word "checkout" appears only in a failure message; what must be
    # absent is any checkout *path* the launcher could resolve at launch.
    assert str(repo) not in script, 'packaged launcher must not name the checkout path'
    assert str(base) not in script, 'packaged launcher must not embed its build path'

    proc = run([str(launcher), 'web', '--port', '0', '--no-open'], env=env)
    record = json.loads(proc.stdout)
    assert record['args'] == ['web', '--port', '0', '--no-open'], record
    assert record['pythonpath'].startswith(str(runtime / 'src')), record
    assert record['plugins'] == str(runtime / 'plugins'), record
    assert record['cwd'] == str(home / 'Library/Application Support/Exo Desktop Alpha/workspace'), record

    # The checkout the bundle was built from is gone; the app must not care.
    # (Nothing in the bundle references it, so there is nothing to delete
    # here by construction; the assertion above is the check.)

    # Missing bundled python fails loudly, never falls back.
    python_bin = runtime / 'python' / 'bin' / 'python3'
    python_bin.unlink()
    proc = run([str(launcher), 'web'], env=env, check=False)
    assert proc.returncode == 72 and 'reinstall' in proc.stderr and 'checkout' in proc.stderr, proc
    os.symlink(sys.executable, python_bin)

    # Missing bundled sources fail loudly too.
    cli = runtime / 'src' / 'exo' / 'cli.py'
    cli.rename(cli.with_suffix('.py.bak'))
    proc = run([str(launcher), 'web'], env=env, check=False)
    assert proc.returncode == 72, proc
    cli.with_suffix('.py.bak').rename(cli)

    # Attached + packaged: versioned overlay in Application Support.
    overlay = base / 'overlay' / '0.1.0-alpha+deadbeef'
    overlay.mkdir(parents=True)
    (overlay / 'plugins').mkdir()
    (overlay / 'VERSION').write_text('0.1.0-alpha+deadbeef\n')
    sockpath = base / 'core socket'
    with socket.socket(socket.AF_UNIX) as sock:
        sock.bind(str(sockpath))
        attached = resources / 'exo-attached'
        run([sys.executable, str(make_launcher), '--output', str(attached), '--packaged',
             '--attach-socket', str(sockpath), '--exo-home', str(base / 'shared home'),
             '--seat', 'canary', '--overlay-dir', str(overlay),
             '--overlay-version', '0.1.0-alpha+deadbeef'])
        proc = run([str(attached), 'web', '--port', '0', '--no-open'], env=env)
        record = json.loads(proc.stdout)
        assert record['plugins'] == str(overlay / 'plugins'), record
        assert record['args'] == ['web', '--port', '0', '--no-open', '--socket', str(sockpath)], record
        assert run([str(attached), 'stop'], env=env, check=False).returncode == 64
    sockpath.unlink()
    (overlay / 'VERSION').write_text('0.1.0-alpha+stale\n')
    with socket.socket(socket.AF_UNIX) as sock:
        sock.bind(str(sockpath))
        proc = run([str(attached), 'web'], env=env, check=False)
    assert proc.returncode == 72 and 'overlay version' in proc.stderr, proc

    # package-runtime.py: dry run, overlay-only, and the site-packages filter.
    proc = run([sys.executable, str(package_runtime), '--repo', str(repo), '--dry-run',
                '--output', str(base / 'dry Resources')])
    assert 'runtime dir' in proc.stdout and 'copies: src/ -> runtime/src' in proc.stdout, proc.stdout
    assert not (base / 'dry Resources').exists(), 'dry run must write nothing'
    out_overlay = base / 'app support overlay'
    run([sys.executable, str(package_runtime), '--repo', str(repo), '--overlay-only',
         '--overlay-output', str(out_overlay), '--version', '0.1.0-alpha', '--commit', 'deadbeef'])
    assert (out_overlay / 'plugins' / 'exo-command' / 'exo_command' / '__init__.py').is_file()
    assert (out_overlay / 'VERSION').read_text().strip() == '0.1.0-alpha+deadbeef'

    spec = importlib.util.spec_from_file_location('package_runtime', str(package_runtime))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    stage = base / 'stage site-packages'
    stage.mkdir()
    (stage / '__editable__.exo_finder').mkdir()
    (stage / 'realpkg').mkdir()
    (stage / 'realpkg' / '__init__.py').write_text('')
    (stage / 'leak.pth').write_text(str(repo) + '\n')
    target = base / 'bundled site-packages'
    count = mod.copy_site_packages(stage, target, repo)
    assert (target / 'realpkg' / '__init__.py').is_file(), 'third-party package must be copied'
    assert not (target / '__editable__.exo_finder').exists(), 'editable hooks must be dropped'
    assert not (target / 'leak.pth').exists(), 'checkout .pth files must be dropped'
    assert count == 1, count

    # Full runtime assembly with a fake python-home (real checkout sources).
    fake_python_home = base / 'fake python-home'
    (fake_python_home / 'bin').mkdir(parents=True)
    os.symlink(sys.executable, fake_python_home / 'bin' / 'python3')
    out_resources = base / 'assembled Resources'
    run([sys.executable, str(package_runtime), '--repo', str(repo), '--output', str(out_resources),
         '--python-home', str(fake_python_home), '--version', '0.1.0-alpha', '--commit', 'deadbeef'])
    assembled = out_resources / 'runtime'
    assert (assembled / 'src' / 'exo' / 'cli.py').is_file()
    assert (assembled / 'plugins' / 'exo-command' / 'exo_command' / '__init__.py').is_file()
    assert (assembled / 'VERSION').read_text().strip() == '0.1.0-alpha+deadbeef'
    assert json.loads((assembled / 'MANIFEST.json').read_text())['python_bundled'] is True
    assert not (assembled / 'src' / 'exo' / '__pycache__').exists(), 'pycache must not be bundled'

print('PASS: packaged launcher resolution, checkout independence, exit-72 failures, '
      'overlay versioning, site-packages filter, runtime assembly')
