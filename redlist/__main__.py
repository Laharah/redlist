from collections import OrderedDict
import humanize
import asyncio
import sys
from pathlib import Path
import logging
import re
import argparse
import time
import os

import beets.library
from pynentry import PinEntryCancelled
import confuse

from . import redapi
from . import redsearch
from . import playlist
from . import matching
from . import utils
from . import config
from . import deluge
from . import ui

log = logging.getLogger(__name__)
log.parent.setLevel('INFO')
try:
    p = log
    while p.parent is not None:
        p = p.parent
    p.handlers[0].setFormatter(ui.UserMessenger())
except IndexError:
    logging.basicConfig(formatter=ui.UserMessenger())


async def main(spotlist, yes=False):
    # Get Beets library
    dbpath = config['beets_library'].as_filename()
    library = beets.library.Library(dbpath)

    # Parse the playlist
    title, track_info = await playlist.parse_playlist(spotlist, library)
    # Match exsisting tracks
    log.info('Matching track list to beets library...')
    matched = matching.beets_match(track_info, library, config['restrict_album'].get())
    unmatched = [track for track, i in matched.items() if i is None]
    log.info('Finished. There are %d tracks that could not be matched.', len(unmatched))
    if re.match(r'.*\.(m3u|m3u8)$', spotlist) and config['overwrite_m3u'].get():
        save_path = Path(spotlist)
        overwrite_flag = True
    else:
        save_dir = config['m3u_directory'].as_filename()
        save_path = Path(save_dir) / '{}.m3u'.format(title)
        overwrite_flag = False
    if save_path.exists() and not overwrite_flag:
        if not yes and not re.match(r'y', input('\nOverwrite %s?: ' % save_path)):
            return 0
    playlist.create_m3u_from_info(matched, save_path)

    if len(unmatched) == 0:
        return 0
    print('\nThe following tracks could not be matched to your beets library:')
    print('\n'.join(map(str, unmatched)))

    # Search [REDACTED] for missing tracks
    if not yes:
        if not re.match(r'y',
                        input('\nSearch [REDACTED] for missing tracks?(y/n): '),
                        flags=re.I):
            return 0
    log.info('\nConnecting to [REDACTED]...')
    try:
        api = await utils.get_api()
    except PinEntryCancelled:
        print("Search Canceled, writing and exiting.")
        return 0
    log.info('SUCCESS!')
    log.info('Begining search for %s tracks, This may take a while.', len(unmatched))

    async def safe_find_album(track, api):
        ra = config['restrict_album'].get()
        try:
            return await redsearch.find_album(track, api, restrict_album=ra)
        except (RuntimeError, ValueError, KeyError) as e:
            log.error('Error while searching for track %s.', track)
            log.debug('Stack Trace:', exc_info=True)
            return None

    tasks = {}
    for track in unmatched:
        task = asyncio.ensure_future(safe_find_album(track, api))
        tasks[track] = task
    match_start = time.monotonic()
    await asyncio.gather(*tasks.values())
    match_end = time.monotonic()
    log.info("Searching complete after %s!",
             humanize.naturaldelta(match_end - match_start))
    results = {t: v.result() for t, v in tasks.items()}
    missing = [t for t, v in results.items() if v is None]
    log.info('Found matches for %d/%d unmatched tracks',
             len(unmatched) - len(missing), len(unmatched))
    if missing:
        print('\nThe Following tracks could not be found on [REDACTED]:')
        for t in missing:
            print(t)

    #prune duplicates
    torrent_ids = set()
    downloads = {}
    for t, g in results.items():
        if g is None:
            continue
        torrent_id = g['torrent']['torrentId']
        if torrent_id in torrent_ids:
            continue
        else:
            torrent_ids.add(torrent_id)
            downloads[t] = g

    # Download torrents
    if not downloads:
        print('No new torrents to download.')
        return 0
    if not yes:
        print('\nWould you like to download the torrents for these albums?:')
    else:
        print('\nDownloading the following torrents:')
    for torrent in downloads.values():
        m = '{} - {} [{}][{} {}]: torrentid={}'.format(
            *[torrent[k] for k in ('artist', 'groupName')] +
            [torrent['torrent'][k] for k in 'media format encoding'.split()] +
            [torrent['torrent']['torrentId']])
        print('\t', m)
    if not yes and not re.match('y', input('(Yes/No)'), re.I):
        return 0
    try:
        new_buff = await utils.check_dl_buffer(downloads.values(), api)
    except utils.NotEnoughDownloadBuffer as e:
        log.critical("%s", e.args[0])
        if not yes and not re.match('y', input('Continue?: '), re.I):
            return 0
    else:
        print(f"After download your new buffer will be "
              f"{humanize.naturalsize(new_buff, gnu=True)}")

    use_fl = config['redacted']['use_fl_tokens']
    if config['enable_deluge'].get():
        try:
            with deluge.Client() as client:
                paused = config['deluge']['add_paused'].get()

                async def add_torrent(torrent):
                    filename, data = await api.get_torrent(
                        torrent['torrent']['torrentId'], use_fl)
                    client.add_torrent_file(filename, data, paused)

                dls = [
                    asyncio.ensure_future(add_torrent(torrent))
                    for torrent in downloads.values()
                ]
                await asyncio.gather(*dls)

            print('Finished.')
            return 0
        except ConnectionRefusedError:
            print("\nThere was an error connecting to the deluge server.")
            print("Saving torrents to files instead.")
            # Fail out to normal download

    # Download to files
    async def dl_torrent(torrent):
        dl_dir = config['torrent_directory'].as_filename()
        filename, data = await api.get_torrent(torrent['torrent']['torrentId'], use_fl)
        with open(Path(dl_dir) / filename, 'wb') as fout:
            fout.write(data)
        log.info('Downloaded %s.', filename)

    dls = [asyncio.ensure_future(dl_torrent(torrent)) for torrent in downloads.values()]
    await asyncio.gather(*dls)

    print('Finished.')
    return 0


def entry_point():
    parser = argparse.ArgumentParser(usage='redlist [options] <playlist>...')
    parser.add_argument('playlist', nargs='*')
    parser.add_argument('--config', dest='configfile', help='Path to configuration file.')
    parser.add_argument("--beets-library",
                        dest='beets_library',
                        help="The beets library to use")
    parser.add_argument(
        '--downloads',
        dest='torrent_directory',
        help="Directory new torrents will be saved to (exclusive with --deluge)")
    parser.add_argument('-y',
                        dest='yes',
                        action='store_true',
                        help="Assume yes to all queries and do not prompt.")
    parser.add_argument('--deluge',
                        dest='enable_deluge',
                        action='store_true',
                        help="Load torrents directly into deluge")
    parser.add_argument('--deluge-server',
                        dest="deluge.host",
                        help="address of deluge server, (Default: localhost)")
    parser.add_argument('--deluge-port',
                        dest="deluge.port",
                        help="Port of deluge server, (Default: 58846)")
    parser.add_argument('--restrict-album',
                        dest='restrict_album',
                        action='store_true',
                        help="Only match tracks if they come from the same album.")
    parser.add_argument('--use-fl-tokens',
                        dest='redacted.use_fl_tokens',
                        help="Use freeleach tokens",
                        action='store_true')
    parser.add_argument('--show-config',
                        dest='show_config',
                        action='store_true',
                        help="Dump the current configuration values.")
    parser.add_argument(
        '--overwrite-m3u',
        dest='overwrite_m3u',
        action='store_true',
        help='if argument is an m3u, overwrite it instead of outputting to playlist dir.')
    parser.add_argument('--log-level',
                        dest='loglevel',
                        help='Set the log level',
                        default='INFO',
                        choices=['CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG'])
    options = parser.parse_args()
    if options.configfile:
        try:
            config.set_file(options.configfile)
        except confuse.ConfigReadError:
            print('Could not open the config file {}.'.format(options.configfile))
            sys.exit(1)
    if options.show_config:
        utils.resolve_configured_paths(config)
        print('# Configuration file at "{}"\n'.format(
            os.path.join(config.config_dir(), 'config.yaml')))
        print(config.dump(redact=True))
        sys.exit()
    args = options.playlist
    if len(args) < 1:
        parser.error('Must specify at least one playlist')
    log.setLevel(options.loglevel)
    config.set_args(options, dots=True)
    utils.resolve_configured_paths(config)
    spotlists = args
    loop = asyncio.get_event_loop()
    results = []
    for splist in spotlists:
        try:
            results.append(loop.run_until_complete(main(splist, options.yes)))
        except Exception:
            log.error("Error Processing %s.", splist, exc_info=True)
            results.append(1)

    if utils.API is not None and not utils.API.session.closed:
        loop.run_until_complete(utils.API.session.close())
    if not all(r == 0 for r in results):
        sys.exit(1)
    else:
        sys.exit()


if __name__ == '__main__':
    entry_point()
