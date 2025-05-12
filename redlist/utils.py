import itertools
import logging
from pathlib import Path

import humanize
from beets import config as beetconfig

API = None
log = logging.getLogger(__name__)
USER_BUFFER = None


class NotEnoughDownloadBuffer(Exception):
    pass


def resolve_configured_paths(cfg):
    paths = {}
    if cfg["beets_library"].get():
        paths["beets_library"] = Path(cfg["beets_library"].as_filename()).absolute()
    else:
        paths["beets_library"] = Path(beetconfig["library"].as_filename()).absolute()
    for key in ["torrent_directory", "m3u_directory"]:
        if cfg[key].get():
            paths[key] = Path(cfg[key].as_filename()).absolute()
        else:
            paths[key] = Path(".")
    for key in paths:
        if not paths[key].exists():
            raise FileNotFoundError(f'Could not find {paths[key]} for option "{key}"')
        paths[key] = str(paths[key])
    cfg.set_args(paths)


async def check_dl_buffer(new_torrent_groups, api, cache=True):
    global USER_BUFFER
    buff = USER_BUFFER
    if not USER_BUFFER or not cache:
        user_data = await api.request("user", id=api.user_id)
        user_data = user_data["response"]
        buff = user_data["stats"]["buffer"]
        USER_BUFFER = buff
    new_dl = sum(g["torrent"]["size"] for g in new_torrent_groups)
    new_buff = buff - new_dl
    if new_buff <= 0:
        raise NotEnoughDownloadBuffer(
            f"Downloading these {len(new_torrent_groups)} torrents will exceted your"
            f"download buffer by {humanize.naturalsize(-new_buff, gnu=True)}!"
        )
    return new_buff


def chunk(iterable, n):
    it = iter(iterable)
    while True:
        chunk = tuple(itertools.islice(it, n))
        if not chunk:
            return
        yield chunk
