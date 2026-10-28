"""Set up or remove a seat's GitHub authentication (the human-run `exo github-auth` steps).

This lives outside the core because saving a token goes through `exo.providers_setup`'s stores, and the core may not
import product modules beyond its recorded cap (D-083). The core keeps what a running seat needs: reading the binding
and building the child environment (`exo.core.github_auth`).
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from exo.core.github_auth import AuthError, _identity, account, binding, paths, status
from exo.core.models import keys
from exo.core.private import atomic_write, private_dir


def configure(home: str | Path, seat: str, mode: str, host: str = 'github.com',
              token: str | None = None, store: str | None = None) -> dict:
    from exo import providers_setup as ps
    home, seat, host = _identity(home, seat, host)
    if mode not in ('token', 'gh-login', 'host'):
        raise AuthError('Choose token, gh-login or host authentication')
    old = binding(home, seat)
    meta = {'mode': mode, 'host': host}
    if mode == 'token':
        value = ps.check_key(token or '')
        keys.remember_secret(value)
        store = store or ps.default_store()
        name = account(home, seat, host)
        if store == 'keychain':
            ps._keychain_set(name, value)
        elif store == 'secret-service':
            ps._secret_tool_set(name, value)
        elif store == 'file':
            ps.write_keys_file(name, value)
        else:
            raise AuthError('Choose keychain, secret-service or file storage')
        meta['store'] = store
    if old.get('mode') == 'token' and (mode != 'token' or old.get('host') != host):
        _remove_saved_token(home, seat, old)
    path, ghdir = paths(home, seat)
    private_dir(path.parent)
    if mode == 'gh-login':
        private_dir(ghdir)
    atomic_write(path, json.dumps(meta) + '\n')
    return status(home, seat)


def _remove_saved_token(home: str | Path, seat: str, meta: dict) -> None:
    from exo import providers_setup as ps
    name = account(home, seat, meta['host'])
    ps._keychain_delete(name)
    ps._secret_tool_delete(name)
    ps.remove_from_keys_file(name)


def remove(home: str | Path, seat: str) -> dict:
    meta = binding(home, seat)
    if meta and meta['mode'] == 'token':
        _remove_saved_token(home, seat, meta)
    path, ghdir = paths(home, seat)
    shutil.rmtree(ghdir, ignore_errors=True)
    private_dir(path.parent)
    atomic_write(path, json.dumps({'mode': 'disabled', 'host': meta.get('host', 'github.com')}) + '\n')
    return {'seat': seat, 'configured': True, 'mode': 'disabled', 'available': False}
