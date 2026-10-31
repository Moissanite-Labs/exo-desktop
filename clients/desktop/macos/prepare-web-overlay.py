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
p.add_argument('--with-pane-layout', action='store_true', help='also overlay persistent pane layout controls')
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
if a.with_pane_layout:
    accepted_panes = {
        'chat.js': {'a8bc3ec5746548d835397fcfb4e1733e5ca6ac81679f907ed9a1f13bd5c69e91', '16c8ce283226807fae222f952da5fea8f62d0e8f525b4c50ecb12fdeff2ddd60'},
        'index.html': {'58c171ee6e81d58368230f40cb443f69d159ffcdcb4193a8e10c600a19668bb7'},
    }
    for name, digests in accepted_panes.items():
        if hashlib.sha256((source / 'exo-command/exo_command/static' / name).read_bytes()).hexdigest() not in digests:
            p.error('selected web asset differs from the verified pane baseline: ' + name)
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
if a.with_pane_layout:
    assets = target / 'exo-command/exo_command/static'
    chat = (assets / 'chat.js').read_text()
    old_mount = '\n'.join([
        '  root.replaceChildren(h("div", { class: "xc-chat" },',
        '    h("nav", { class: "xc-chat-left" }, newBtn, h("div", { class: "xc-label" }, "Threads"), listEl, layoutBtn),',
        '    mainEl,', '    sideEl));'])
    new_mount = '\n'.join([
        '  const threadsEl = h("nav", { class: "xc-chat-left" }, newBtn, h("div", { class: "xc-label" }, "Threads"), listEl, layoutBtn);',
        '  const paneControls = h("nav", { "aria-label": "Pane layout" });',
        '  const chatPanes = h("div", { class: "xc-chat" }, threadsEl, mainEl, sideEl);',
        '  root.replaceChildren(h("section", { class: "xc-pane-workspace", "aria-label": "Conversation workspace" }, paneControls, chatPanes));',
        '  const stopPaneLayout = attachPaneLayout(chatPanes, { threads: threadsEl, conversation: mainEl, details: sideEl }, paneControls);'])
    for needle in ('import * as permissions from "./permissions.js";', old_mount, 'const off = () => {'):
        if chat.count(needle) != 1:
            p.error('verified pane integration hunk is unavailable')
    chat = chat.replace('import * as permissions from "./permissions.js";',
                        'import * as permissions from "./permissions.js";\nimport { attachPaneLayout } from "./pane_layout.js";')
    chat = chat.replace(old_mount, new_mount).replace('const off = () => {', 'const off = () => { stopPaneLayout();')
    (assets / 'chat.js').write_text(chat)
    index = (assets / 'index.html').read_text()
    index = index.replace('<link rel="stylesheet" href="/static/style.css">',
                          '<link rel="stylesheet" href="/static/style.css">\n<link rel="stylesheet" href="/static/pane_layout.css">')
    (assets / 'index.html').write_text(index)
    for name in ('pane_layout.js', 'pane_layout.css'):
        shutil.copy2(patched / 'static' / name, assets / name)
print('Prepared web replay overlay. Install attached mode with --plugins pointing to the output.')
