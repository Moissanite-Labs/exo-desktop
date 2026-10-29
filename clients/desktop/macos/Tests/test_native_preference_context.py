"""Exercise the actual configured-preference factory with disposable embedded app metadata."""
import os
from pathlib import Path
import plistlib
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='exo-preference-context-') as directory:
    base = Path(directory)
    home = base / 'installed home'
    home.mkdir()
    other = base / 'different home'
    other.mkdir()
    helper = base / 'exo-alpha'
    helper.write_text('#!/bin/sh\nexit 99\n')
    helper.chmod(0o755)
    info = base / 'Info.plist'
    info.write_bytes(plistlib.dumps({'CFBundleIdentifier': 'test.exo.preference-context', 'ExoPreferenceScope': 'a' * 64, 'ExoPreferenceUserHome': str(home)}))
    source = (root / 'Sources/ExoDesktop/main.swift').read_text().split('\nlet delegate = AppDelegate()')[0]
    source += '''
extension AppDelegate {
 static func acceptance() {
  precondition((configuredPreferences() != nil) == (CommandLine.arguments[1] == "enabled"))
 }
}
AppDelegate.acceptance()
'''
    main = base / 'main.swift'
    main.write_text(source)
    sources = [str(path) for path in sorted((root / 'Sources/ExoDesktop').glob('*.swift')) if path.name != 'main.swift']
    executable = base / 'probe'
    subprocess.run(['swiftc', str(main), *sources, '-framework', 'AppKit', '-framework', 'WebKit', '-Xlinker', '-sectcreate', '-Xlinker', '__TEXT', '-Xlinker', '__info_plist', '-Xlinker', str(info), '-o', str(executable)], check=True)
    environment = dict(os.environ, HOME=str(home), CFFIXED_USER_HOME=str(home))
    environment.pop('EXO_DESKTOP_EXO', None)
    environment.pop('EXO_SEAT', None)
    subprocess.run([str(executable), 'enabled'], env=environment, check=True)
    subprocess.run([str(executable), 'disabled'], env=dict(environment, HOME=str(other)), check=True)
    subprocess.run([str(executable), 'disabled'], env=dict(environment, EXO_DESKTOP_EXO=str(helper)), check=True)
    helper.unlink()
    subprocess.run([str(executable), 'disabled'], env=environment, check=True)
print('PASS: installed context enables, changed HOME/explicit override/missing bundled launcher refuse')
