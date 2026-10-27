#!/usr/bin/env python3
"""Copy selected runtime plugins and overlay the desktop replay fixes, without editing the core."""
import argparse
import hashlib
from pathlib import Path
import shutil

p = argparse.ArgumentParser()
p.add_argument('--plugins', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
source = a.plugins.resolve()
target = a.output.resolve()
if target.exists() or not (source / 'exo-command/exo_command/service.py').is_file():
    p.error('output must not exist and plugins must contain exo-command')
expected = {'server.py': '468e418162677248da50e1724f4587497af53026c672a9825aa63503f344eaf7', 'service.py': 'c103e41c3f08212664b4fb459876a1e5d2bede35d9cec2fed1460d5de29f33e7'}
for name, digest in expected.items():
    if hashlib.sha256((source / 'exo-command/exo_command' / name).read_bytes()).hexdigest() != digest:
        p.error('selected web implementation differs from the verified replay-fix baseline: ' + name)
if source in target.parents or target in source.parents:
    p.error('output must be separate from the selected plugins')
shutil.copytree(source, target, ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '.git'))
patched = Path(__file__).resolve().parents[3] / 'plugins/exo-command/exo_command'
for name in ('server.py', 'service.py'):
    shutil.copy2(patched / name, target / 'exo-command/exo_command' / name)
print('Prepared web replay overlay. Install attached mode with --plugins pointing to the output.')
