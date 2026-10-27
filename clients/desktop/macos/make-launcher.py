#!/usr/bin/env python3
"""Generate a quoted local launcher. No credentials are copied into the bundle."""
import argparse
import os
from pathlib import Path
import shlex

p = argparse.ArgumentParser()
p.add_argument('--output', required=True)
p.add_argument('--exo', required=False, default=None,
               help='checkout/external exo executable (source installs); omit with --packaged')
p.add_argument('--attach-socket')
p.add_argument('--plugins')
p.add_argument('--exo-home')
p.add_argument('--seat')
p.add_argument('--packaged', action='store_true',
               help='resolve the runtime from the bundle itself (see package-runtime.py): '
                    'the launcher lives in Contents/Resources, the runtime in '
                    'Contents/Resources/runtime, and no checkout path is consulted')
p.add_argument('--overlay-dir',
               help='attached only: versioned Application Support overlay dir '
                    'holding plugins/ and a VERSION file (made by package-runtime.py); '
                    'replaces --plugins so the overlay is not an external path')
p.add_argument('--overlay-version',
               help='attached only: expected "<version>+<commit>" overlay VERSION')
a = p.parse_args()
q = shlex.quote
attached = a.attach_socket is not None
if a.packaged and a.exo is not None:
    p.error('--packaged takes no --exo: the runtime comes from the bundle')
if not a.packaged and a.exo is None:
    p.error('--exo is required unless --packaged is given')
if a.overlay_dir is not None and not attached:
    p.error('--overlay-dir needs --attach-socket')
if a.overlay_dir is not None and a.overlay_version is None:
    p.error('--overlay-dir needs --overlay-version')
if attached and not all((a.exo_home, a.seat)):
    p.error('attached mode requires --exo-home and --seat')
if attached and not a.packaged and not a.plugins and a.overlay_dir is None:
    p.error('attached source mode requires --plugins or --overlay-dir')
if attached and a.packaged and a.overlay_dir is None:
    p.error('attached packaged mode requires --overlay-dir and --overlay-version')
script = '''#!/bin/sh
set -eu
export PYTHONUNBUFFERED=1
export EXO_DESKTOP_PORT=0
unset ANTHROPIC_API_KEY EXO_SEAT EXO_PLUGIN_DIRS EXO_PRINCIPAL EXO_STORE EXO_COMMAND_SOCKET EXO_COMMAND_URL EXO_COMMAND_TOKEN EXO_COMMAND_TOKEN_FILE EXO_TOKEN EXO_KEYS_FILE EXO_PRINCIPAL_STORE EXO_COMMAND_PRINCIPAL_STORE EXO_COMMAND_HOST
export EXO_COMMAND_HOST=127.0.0.1
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:${PATH:-}"
'''
if a.packaged:
    # Everything resolves from the launcher's own location inside the
    # bundle. Nothing here names a checkout, a venv, or a user-supplied
    # runtime path, so moving or deleting the checkout cannot change
    # what this script runs. A missing/damaged bundle fails loudly
    # (exit 72); it never falls back to a checkout or system python.
    script += '''resources=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
runtime="$resources/runtime"
python="$runtime/python/bin/python3"
[ -x "$python" ] || { echo "Bundled desktop runtime is missing or damaged; reinstall the app. It does not use the source checkout." >&2; exit 72; }
[ -f "$runtime/src/exo/cli.py" ] || { echo "Bundled desktop runtime is missing its exo sources; reinstall the app." >&2; exit 72; }
PYTHONPATH="$runtime/src"
[ -d "$runtime/site-packages" ] && PYTHONPATH="$PYTHONPATH:$runtime/site-packages"
export PYTHONPATH
'''
    if attached:
        script += 'socket=' + q(a.attach_socket) + '\n'
        script += 'overlay=' + q(a.overlay_dir) + '\n'
        script += 'overlay_version=' + q(a.overlay_version) + '\n'
        script += '''[ "${1:-}" = web ] || { echo "Attached desktop only runs its web client; core control is disabled." >&2; exit 64; }
[ -S "$socket" ] || { echo "The selected core socket is unavailable. Start that core separately, then retry." >&2; exit 69; }
[ -f "$overlay/VERSION" ] && [ "$(cat "$overlay/VERSION")" = "$overlay_version" ] || { echo "Desktop overlay version does not match this app; reinstall the app." >&2; exit 72; }
shift
'''
        script += 'export EXO_HOME=' + q(a.exo_home) + '\n'
        script += 'export EXO_SEAT=' + q(a.seat) + '\n'
        script += 'export EXO_PLUGIN_DIRS="$overlay/plugins"\n'
        script += 'cd "$HOME"\nexec "$python" -c \'import sys; from exo.cli import main; sys.exit(main())\' web "$@" --socket "$socket"\n'
    else:
        script += '''export EXO_HOME="$HOME/Library/Application Support/Exo Desktop Alpha/runtime"
export EXO_PLUGIN_DIRS="$runtime/plugins"
mkdir -p "$EXO_HOME" "$HOME/Library/Application Support/Exo Desktop Alpha/workspace"
cd "$HOME/Library/Application Support/Exo Desktop Alpha/workspace"
exec "$python" -c 'import sys; from exo.cli import main; sys.exit(main())' "$@"
'''
else:
    script += 'exo=' + q(a.exo) + '\n'
    script += '[ -x "$exo" ] || { echo "Desktop runtime executable is unavailable; reinstall the app." >&2; exit 72; }\n'
    if attached:
        script += 'socket=' + q(a.attach_socket) + '\n'
        script += '''[ "${1:-}" = web ] || { echo "Attached desktop only runs its web client; core control is disabled." >&2; exit 64; }
[ -S "$socket" ] || { echo "The selected core socket is unavailable. Start that core separately, then retry." >&2; exit 69; }
'''
        if a.overlay_dir is not None:
            script += 'overlay=' + q(a.overlay_dir) + '\n'
            script += 'overlay_version=' + q(a.overlay_version) + '\n'
            script += '[ -f "$overlay/VERSION" ] && [ "$(cat "$overlay/VERSION")" = "$overlay_version" ] || { echo "Desktop overlay version does not match this app; reinstall the app." >&2; exit 72; }\n'
        script += 'shift\n'
        script += 'export EXO_HOME=' + q(a.exo_home) + '\n'
        script += 'export EXO_SEAT=' + q(a.seat) + '\n'
        if a.overlay_dir is not None:
            script += 'export EXO_PLUGIN_DIRS="$overlay/plugins"\n'
        else:
            script += 'export EXO_PLUGIN_DIRS=' + q(a.plugins) + '\n'
        script += 'cd "$HOME"\nexec "$exo" web "$@" --socket "$socket"\n'
    else:
        script += '''export EXO_HOME="$HOME/Library/Application Support/Exo Desktop Alpha/runtime"
mkdir -p "$EXO_HOME" "$HOME/Library/Application Support/Exo Desktop Alpha/workspace"
cd "$HOME/Library/Application Support/Exo Desktop Alpha/workspace"
exec "$exo" "$@"
'''
Path(a.output).write_text(script)
os.chmod(a.output, 0o755)
