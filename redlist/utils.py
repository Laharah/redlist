import sys
import os
from pathlib import Path

import humanize
from beets import config as beetconfig

from . import config
from . import ui
from . import redapi

API = None


class NotEnoughDownloadBuffer(Exception):
    pass


def resolve_configured_paths(cfg):
    paths = {}
    if cfg['beets_library'].get():
        paths['beets_library'] = Path(cfg['beets_library'].as_filename()).absolute()
    else:
        paths['beets_library'] = Path(beetconfig['library'].as_filename()).absolute()
    for key in ['torrent_directory', 'm3u_directory']:
        if cfg[key].get():
            paths[key] = Path(cfg[key].as_filename()).absolute()
        else:
            paths[key] = Path('.')
    for key in paths:
        if not paths[key].exists():
            raise FileNotFoundError(f'Could not find {path[key]} for option "{key}"')
        paths[key] = str(paths[key])
    cfg.set_args(paths)


async def check_dl_buffer(new_torrent_groups, api):
    user_data = await api.request('user', id=api.user_id)
    user_data = user_data['response']
    buff = user_data['stats']['buffer']
    new_dl = sum(g['torrent']['size'] for g in new_torrent_groups)
    new_buff = buff - new_dl
    if new_buff <= 0:
        raise NotEnoughDownloadBuffer(
            f"Downloading {len(new_torrent_groups)} torrents will exceted your"
            f"download buffer by {humanize.naturalsize(-new_buff, gnu=True)}!")
    return new_buff


async def get_api():
    'get a redacted api handle, through config or user'
    global API
    if API is not None and not API.session.closed:
        return API
    cfg = config['redacted']
    if cfg['save_cookies']:
        cookies = Path(config.config_dir()) / 'cookies.dat'
        if not cookies.exists():
            cookies = None
    else:
        cookies = None
    api = redapi.RedAPI(cookies=cookies)
    if cookies:
        try:
            await api._auth()
        except redapi.LoginException:
            pass
        else:
            API = api
            return api
    error = None
    while not (cfg['username'] and cfg['password'] and api.authkey):
        ui.get_user_and_pass(cfg,
                             name='[REDACTED]',
                             overwrite=True if error else False,
                             error=error)
        try:
            await api.login(cfg['password'], username=cfg['username'])
        except redapi.LoginException:
            error = "Login failed, please re-enter password"
            continue
        if cfg['save_cookies']:
            api.session.cookie_jar.save(Path(config.config_dir()) / 'cookies.dat')
        API = api
        return api
