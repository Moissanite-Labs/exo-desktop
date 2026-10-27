#!/usr/bin/env python3
"""Generate a quoted local launcher. No credentials are copied into the bundle."""
import argparse
import os
from pathlib import Path
import shlex

p = argparse.ArgumentParser()
p.add_argument('--output', required=True)
p.add_argument('--exo', required=True)
p.add_argument('--attach-socket')
p.add_argument('--plugins')
p.add_argument('--exo-home')
p.add_argument('--seat')
a = p.parse_args()
q = shlex.quote
attached = a.attach_socket is not None
if attached and not all((a.plugins, a.exo_home, a.seat)):
    p.error('attached mode requires --plugins, --exo-home and --seat')
script = '''#!/bin/sh
set -eu
export PYTHONUNBUFFERED=1
unset ANTHROPIC_API_KEY EXO_SEAT EXO_PLUGIN_DIRS EXO_PRINCIPAL EXO_STORE EXO_COMMAND_SOCKET EXO_COMMAND_URL EXO_COMMAND_TOKEN EXO_COMMAND_TOKEN_FILE EXO_TOKEN EXO_KEYS_FILE EXO_PRINCIPAL_STORE EXO_COMMAND_PRINCIPAL_STORE EXO_COMMAND_HOST
# No EXO_DESKTOP_PORT here: the desktop app pins the loopback port itself (7342 unless overridden),
# so the page origin — and the browser storage attached to it — stays stable across reloads and relaunches.
export EXO_COMMAND_HOST=127.0.0.1
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:${PATH:-}"
'''
script += 'exo=' + q(a.exo) + '\n'
script += '[ -x "$exo" ] || { echo "Desktop runtime executable is unavailable; reinstall the app." >&2; exit 72; }\n'
if attached:
    script += 'socket=' + q(a.attach_socket) + '\n'
    script += '''[ "${1:-}" = web ] || { echo "Attached desktop only runs its web client; core control is disabled." >&2; exit 64; }
[ -S "$socket" ] || { echo "The selected core socket is unavailable. Start that core separately, then retry." >&2; exit 69; }
shift
'''
    script += 'export EXO_HOME=' + q(a.exo_home) + '\n'
    script += 'export EXO_SEAT=' + q(a.seat) + '\n'
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
