#!/usr/bin/env python3
"""Assemble a checkout-independent desktop runtime into an app bundle.

Bundle layout (under the app's ``Contents/Resources``)::

    runtime/
      VERSION          app version + source commit, one line
      SOURCE-COMMIT    full source commit the runtime was built from
      PYTHON-VERSION   pinned interpreter version, e.g. ``3.12.4``
      MANIFEST.json    file counts, python version, commit, build time (UTC)
      python/          pinned interpreter tree (python-build-standalone
                       layout: ``bin/python3`` plus its ``lib/``); copied
                       verbatim from --python-home
      src/             copy of the repo's ``src/`` (the ``exo`` package)
      plugins/         copy of the repo's ``plugins/`` (web assets live
                       beside the plugin code, so bundling the plugins
                       bundles the assets; the replay fix ships in-tree)
      site-packages/   third-party dependencies, copied from a synced
                       staging environment (see --site-packages)

Why this layout: ``exo web`` already resolves plugins from
``Path(exo/cli.py).parents[2] / 'plugins'``. With ``src/`` and ``plugins/``
as siblings under ``runtime/``, that fallback lands inside the bundle,
not in a checkout. The generated launcher (see make-launcher.py
--packaged) resolves every path from its own location inside the bundle
and never consults the checkout. A missing or damaged bundled runtime
fails with exit 72 and a clear message; it never silently falls back to
a moved checkout.

The checkout is a *build-time* input only: this script copies sources
out of it. Deleting, moving or renaming the checkout after packaging
must not affect the packaged app.

Usage (macOS build machine)::

    python3 package-runtime.py --repo /path/to/checkout \
        --output MyApp.app/Contents/Resources \
        --python-home /path/to/python-build-standalone \
        --site-packages /path/to/staging-venv/lib/python3.12/site-packages \
        --version 0.1.0-alpha

``--python-home`` is required for a real package. ``--dry-run`` validates
the sources and prints the layout and manifest that would be written,
without writing anything; it is the checkout-free verification step
that runs on machines without a macOS toolchain.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

IGNORE = shutil.ignore_patterns('__pycache__', '*.pyc', '.git', '.DS_Store')

# Entries in a synced site-packages dir that must never be bundled: an
# editable install points back at the checkout, and .pth files can do
# the same. Third-party wheels carry neither.
EDITABLE_PREFIX = '__editable__'


def _is_checkout_reference(path: Path, repo: Path) -> bool:
    try:
        text = path.read_text(errors='ignore')
    except OSError:
        return False
    return str(repo) in text


def copy_site_packages(source: Path, target: Path, repo: Path) -> int:
    """Copy third-party packages, dropping anything that points at the repo."""
    count = 0
    target.mkdir(parents=True, exist_ok=True)
    for entry in sorted(source.iterdir()):
        name = entry.name
        if name.startswith(EDITABLE_PREFIX):
            continue
        if name.endswith('.pth') and _is_checkout_reference(entry, repo):
            continue
        if name in ('exo', 'exo_tui') or name.startswith(('exo-', 'exo_tui-')):
            # The exo package itself ships as bundled src/, never from here.
            continue
        dest = target / name
        if entry.is_dir():
            shutil.copytree(entry, dest, ignore=IGNORE)
        else:
            shutil.copy2(entry, dest)
        count += 1
    return count


def python_version(python_home: Path) -> str:
    exe = python_home / 'bin' / 'python3'
    if not exe.is_file():
        raise SystemExit(f'python-home has no bin/python3: {python_home}')
    out = subprocess.run([str(exe), '--version'], capture_output=True, text=True)
    text = (out.stdout or out.stderr).strip()
    return text.split()[-1] if text else 'unknown'


def git_commit(repo: Path) -> str:
    out = subprocess.run(['git', '-C', str(repo), 'rev-parse', 'HEAD'],
                         capture_output=True, text=True)
    return out.stdout.strip() if out.returncode == 0 else 'unknown'


def count_files(root: Path) -> int:
    return sum(1 for p in root.rglob('*') if p.is_file())


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[3],
                   help='checkout root (build-time input only)')
    p.add_argument('--output', type=Path, default=None,
                   help='app Contents/Resources dir the runtime/ goes under '
                        '(not needed with --overlay-only)')
    p.add_argument('--python-home', type=Path,
                   help='pinned interpreter tree to bundle as runtime/python')
    p.add_argument('--site-packages', type=Path,
                   help='synced staging site-packages dir to copy third-party deps from')
    p.add_argument('--version', default='0.1.0-alpha')
    p.add_argument('--commit', default=None, help='override the git commit recorded')
    p.add_argument('--dry-run', action='store_true',
                   help='validate and print the plan; write nothing')
    p.add_argument('--overlay-output', type=Path,
                   help='also write a versioned Application Support overlay here: '
                        'plugins/ plus a VERSION file naming the app version and commit')
    p.add_argument('--overlay-only', action='store_true',
                   help='write only the overlay (no runtime assembly, no --python-home needed); '
                        'for attached installs, where the selected exo executable stays external')
    a = p.parse_args()

    repo = a.repo.resolve()
    src = repo / 'src' / 'exo' / 'cli.py'
    plugins = repo / 'plugins' / 'exo-command' / 'exo_command' / '__init__.py'
    if not src.is_file():
        p.error(f'repo has no src/exo/cli.py: {repo}')
    if not plugins.is_file():
        p.error(f'repo has no plugins/exo-command: {repo}')
    if a.python_home is not None and not (a.python_home / 'bin' / 'python3').is_file():
        p.error(f'python-home has no bin/python3: {a.python_home}')
    if a.site_packages is not None and not a.site_packages.is_dir():
        p.error(f'site-packages is not a directory: {a.site_packages}')

    commit = a.commit or git_commit(repo)
    pyver = python_version(a.python_home) if a.python_home else 'unbundled'
    if a.output is None and not a.overlay_only and not a.dry_run:
        p.error('--output is required unless --overlay-only or --dry-run is given')
    runtime = a.output / 'runtime' if a.output is not None else Path('<no runtime output>')
    manifest = {
        'version': a.version,
        'source_commit': commit,
        'python_version': pyver,
        'layout': ['python/', 'src/', 'plugins/', 'site-packages/'],
        'python_bundled': a.python_home is not None,
        'site_packages_copied': a.site_packages is not None,
    }
    plan = [
        f'repo: {repo}',
        f'runtime dir: {runtime}',
        f'version: {a.version}',
        f'source commit: {commit}',
        f'python: {pyver} (bundled: {a.python_home is not None})',
        f'site-packages: {a.site_packages}',
        'copies: src/ -> runtime/src, plugins/ -> runtime/plugins',
    ]
    if a.overlay_output is not None:
        plan.append(f'overlay: plugins/ + VERSION -> {a.overlay_output}')
    if a.dry_run:
        print('\n'.join(plan))
        print('manifest: ' + json.dumps(manifest, sort_keys=True))
        print('dry run: nothing written')
        return 0

    if a.overlay_only:
        if a.overlay_output is None:
            p.error('--overlay-only needs --overlay-output')
        overlay = a.overlay_output
        if overlay.exists():
            shutil.rmtree(overlay)
        overlay.mkdir(parents=True)
        shutil.copytree(repo / 'plugins', overlay / 'plugins', ignore=IGNORE)
        (overlay / 'VERSION').write_text(f'{a.version}+{commit}\n')
        print(f'overlay written: {overlay} ({count_files(overlay / "plugins")} plugin files)')
        return 0

    if a.python_home is None:
        p.error('--python-home is required for a real package '
                '(a pinned python-build-standalone tree); use --dry-run to plan only')
    if runtime.exists():
        shutil.rmtree(runtime)
    runtime.mkdir(parents=True)
    shutil.copytree(repo / 'src', runtime / 'src', ignore=IGNORE)
    shutil.copytree(repo / 'plugins', runtime / 'plugins', ignore=IGNORE)
    shutil.copytree(a.python_home, runtime / 'python', ignore=IGNORE)
    site_count = 0
    if a.site_packages is not None:
        site_count = copy_site_packages(a.site_packages, runtime / 'site-packages', repo)
    manifest['src_files'] = count_files(runtime / 'src')
    manifest['plugin_files'] = count_files(runtime / 'plugins')
    manifest['site_packages_entries'] = site_count
    (runtime / 'VERSION').write_text(f'{a.version}+{commit}\n')
    (runtime / 'SOURCE-COMMIT').write_text(commit + '\n')
    (runtime / 'PYTHON-VERSION').write_text(pyver + '\n')
    (runtime / 'MANIFEST.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    if a.overlay_output is not None:
        overlay = a.overlay_output
        if overlay.exists():
            shutil.rmtree(overlay)
        overlay.mkdir(parents=True)
        shutil.copytree(runtime / 'plugins', overlay / 'plugins', ignore=IGNORE)
        (overlay / 'VERSION').write_text(f'{a.version}+{commit}\n')
        print(f'overlay written: {overlay}')
    print('\n'.join(plan))
    print(f'packaged runtime: {runtime} '
          f'({manifest["src_files"]} src files, {manifest["plugin_files"]} plugin files, '
          f'{site_count} site-packages entries)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
