import base64
import deluge_client
import os
import sys
from pathlib import Path
import asyncio
import logging
import functools

from . import config
from . import ui

log = logging.getLogger(__name__)


class Client:
    def __init__(self):
        cfg = config['deluge']
        self.cfg = cfg
        resolve_password()
        self._client = deluge_client.DelugeRPCClient(
            cfg['host'].get(),
            cfg['port'].get(),
            cfg['username'].get(),
            cfg['password'].get(),
            decode_utf8=True,
        )
        self._loop = asyncio.get_event_loop()

        try:
            self._client.connect()
            log.info('Connected to %s:%d', self._client.host, self._client.port)
        except ConnectionRefusedError:
            log.error('Could not connect to deluge server at %s', self._client.host)
            raise

    def add_torrent_file(self, filename, data, paused=False):
        options = {'add_paused': paused} if paused else {}
        data = base64.encodebytes(data)
        res = self._client.call('core.add_torrent_file', filename, data, options)
        if res is None:
            log.error('Problem when adding torrent %s, it may already exsist.', filename)
        else:
            log.info('Added torrent %s with hash %s.', filename, res)
        return res

    def __enter__(self):
        return self

    def __exit__(self, exc_type, value, traceback):
        self._client.disconnect()


def resolve_password(config_path=None):
    cfg = config['deluge']
    if cfg['username'].get() and cfg['password'].get():
        return
    if not cfg['host'].get() in ['localhost', '127.0.0.1']:
        ui.get_user_and_pass(cfg)
        return

    #  Using local deluge, get localpass
    if config_path is None:
        if sys.platform.startswith('win'):
            auth_file = os.path.join(os.getenv('APPDATA'), 'deluge', 'auth')
        else:
            auth_file = os.path.expanduser('~/.config/deluge/auth')
    else:
        auth_file = os.path.join(config_path, 'auth')
    if not os.path.isfile(auth_file):
        return
    with open(auth_file) as auth:
        for line in auth:
            line = line.strip()
            if line.startswith('#') or not line:
                continue
            lsplit = line.split(':')
            if lsplit[0] == 'localclient':
                cfg['username'], cfg['password'] = lsplit[:2]
