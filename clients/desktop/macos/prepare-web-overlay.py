#!/usr/bin/env python3
"""Copy selected runtime plugins and overlay the desktop replay fixes, without editing the core."""
import argparse
import hashlib
from pathlib import Path
import shutil
import subprocess

p = argparse.ArgumentParser()
p.add_argument('--plugins', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
p.add_argument('--with-model-picker', action='store_true', help='also overlay the searchable picker while preserving runtime-specific chat commands')
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
if a.with_model_picker:
    accepted = {'chat.js': ['a8bc3ec5746548d835397fcfb4e1733e5ca6ac81679f907ed9a1f13bd5c69e91', '16c8ce283226807fae222f952da5fea8f62d0e8f525b4c50ecb12fdeff2ddd60', 'bfc90c7e9031315a77f92d0990a1d23661180563a470e7c0578b92d3a26052b9'], 'providers.js': ['31bf3bbcb5066d5b1fab1dd23f970a66cbf8ed0d113b0be0fbae728fbf77a2d2'], 'style.css': ['df87e01ebc8f869bde86de7e1c485b10828832d353b397d8b4c2772ec07c6ac3']}
    for name, digests in accepted.items():
        if hashlib.sha256((source / 'exo-command/exo_command/static' / name).read_bytes()).hexdigest() not in digests:
            p.error('selected web asset differs from the verified picker baseline: ' + name)
shutil.copytree(source, target, ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '.git'))
patched = Path(__file__).resolve().parents[3] / 'plugins/exo-command/exo_command'
for name in ('server.py', 'service.py'):
    shutil.copy2(patched / name, target / 'exo-command/exo_command' / name)
if a.with_model_picker:
    assets = target / 'exo-command/exo_command/static'
    patch = Path(__file__).resolve().parent / 'patches/model-picker-chat.patch'
    result = assets / 'chat.js.patched'
    subprocess.run(['patch', '--batch', '--fuzz=0', '-o', str(result), str(assets / 'chat.js')], input=patch.read_bytes(), check=True, stdout=subprocess.DEVNULL)
    result.replace(assets / 'chat.js')
    for name in ('model_picker.js', 'providers.js', 'style.css'):
        shutil.copy2(patched / 'static' / name, assets / name)
print('Prepared web replay overlay. Install attached mode with --plugins pointing to the output.')
