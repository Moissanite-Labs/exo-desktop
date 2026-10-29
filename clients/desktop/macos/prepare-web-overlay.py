#!/usr/bin/env python3
"""Copy selected runtime plugins and overlay the desktop replay fixes, without editing the core."""
import argparse
import hashlib
from pathlib import Path
import shutil
import subprocess

# The overlay stylesheet is pinned: the verified runtime style.css plus patches/overlay-style.patch.
OVERLAY_STYLE = 'cc38bd3af1cd6769b6f0894d7db1dd92a1060e0d2ac2a9c14f8368254431b823'
p =argparse.ArgumentParser()
p.add_argument('--plugins', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
p.add_argument('--with-model-picker', action='store_true', help='also overlay the searchable picker while preserving runtime-specific chat commands')
p.add_argument('--with-approval-shortcuts', action='store_true', help='also overlay approval keyboard guidance and focused-card styling')
a = p.parse_args()
source = a.plugins.resolve()
target = a.output.resolve()
if target.exists() or not (source / 'exo-command/exo_command/service.py').is_file():
    p.error('output must not exist and plugins must contain exo-command')
# server.py: the verified runtime (exo f9d1e423), then exo main's file (blob 1275f85d, unchanged from #757 through 938b027a).
expected = {'server.py': ['468e418162677248da50e1724f4587497af53026c672a9825aa63503f344eaf7', '835a0fb6d35c187b9c6f1d9879e594d86d40c9ceb0d2601609b512a8a740a2a1'], 'service.py': ['c103e41c3f08212664b4fb459876a1e5d2bede35d9cec2fed1460d5de29f33e7']}
for name, digests in expected.items():
    if hashlib.sha256((source / 'exo-command/exo_command' / name).read_bytes()).hexdigest() not in digests:
        p.error('selected web implementation differs from the verified replay-fix baseline: ' + name)
if source in target.parents or target in source.parents:
    p.error('output must be separate from the selected plugins')
if a.with_approval_shortcuts:
    approval_assets = {'approvals.js': '4db09306a3ba58cc97c21f193a765bfdd45b4fe776b43b6ab1ffcd1b09b9d621', 'style.css': 'df87e01ebc8f869bde86de7e1c485b10828832d353b397d8b4c2772ec07c6ac3'}
    for name, digest in approval_assets.items():
        if hashlib.sha256((source / 'exo-command/exo_command/static' / name).read_bytes()).hexdigest() != digest:
            p.error('selected web asset differs from the verified approval baseline: ' + name)
if a.with_model_picker:
    accepted = {'chat.js': ['a8bc3ec5746548d835397fcfb4e1733e5ca6ac81679f907ed9a1f13bd5c69e91', '16c8ce283226807fae222f952da5fea8f62d0e8f525b4c50ecb12fdeff2ddd60'], 'providers.js': ['31bf3bbcb5066d5b1fab1dd23f970a66cbf8ed0d113b0be0fbae728fbf77a2d2'], 'style.css': ['df87e01ebc8f869bde86de7e1c485b10828832d353b397d8b4c2772ec07c6ac3']}
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
    for name in ('model_picker.js', 'providers.js'):
        shutil.copy2(patched / 'static' / name, assets / name)
if a.with_approval_shortcuts:
    assets = target / 'exo-command/exo_command/static'
    shutil.copy2(patched / 'static/approvals.js', assets / 'approvals.js')
if a.with_model_picker or a.with_approval_shortcuts:
    # This repo's style.css targets this repo's workspace DOM, not the older runtime's.
    # Patch the verified runtime stylesheet into the pinned overlay stylesheet instead.
    assets = target / 'exo-command/exo_command/static'
    patch = Path(__file__).resolve().parent / 'patches/overlay-style.patch'
    result = assets / 'style.css.patched'
    subprocess.run(['patch', '--batch', '--fuzz=0', '-o', str(result), str(assets / 'style.css')], input=patch.read_bytes(), check=True, stdout=subprocess.DEVNULL)
    if hashlib.sha256(result.read_bytes()).hexdigest() != OVERLAY_STYLE:
        shutil.rmtree(target)
        p.error('patched overlay stylesheet differs from the pinned overlay stylesheet')
    result.replace(assets / 'style.css')
print('Prepared web replay overlay. Install attached mode with --plugins pointing to the output.')
