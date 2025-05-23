__doc__ = """Save spotify playlists as m3u and fill in missing songs from [REDACTED]"""
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
import confuse

from .redapi import get_api, API
from . import redsearch
from . import playlist
from . import matching
from . import utils
from . import config
from . import deluge
from . import ui

log = logging.getLogger(__name__)
log.parent.setLevel("INFO")
try:
    p = log
    while p.parent is not None:
        p = p.parent
    p.handlers[0].setFormatter(ui.UserMessenger())
except IndexError:
    logging.basicConfig(formatter=ui.UserMessenger())


async def search_redlist_and_dl(unmatched, yes=False):
    api = await get_api()
    log.info("\nConnecting to [REDACTED]...")
    log.info("SUCCESS!")
    log.info("Begining search for %s tracks, This may take a while.", len(unmatched))

    async def safe_find_album(track, api):
        restrict_album = config["restrict_album"].get()
        try:
            return await redsearch.find_album(track, restrict_album=restrict_album)
        except (RuntimeError, ValueError, KeyError) as e:
            log.error("Error while searching for track %s.", track)
            log.debug("Stack Trace:", exc_info=True)
            return None

    tasks = {}
    for track in unmatched:
        task = asyncio.ensure_future(safe_find_album(track, api))
        tasks[track] = task
    match_start = time.monotonic()
    await asyncio.gather(*tasks.values())
    match_end = time.monotonic()
    log.info(
        "Searching complete after %s!", humanize.naturaldelta(match_end - match_start)
    )
    results = {t: v.result() for t, v in tasks.items()}
    missing = [t for t, v in results.items() if v is None]
    log.info(
        "Found matches for %d/%d unmatched tracks",
        len(unmatched) - len(missing),
        len(unmatched),
    )

    # prune duplicates
    torrent_ids = set()
    downloads = {}
    for t, g in results.items():
        if g is None:
            continue
        torrent_id = g["torrent"]["torrentId"]
        if torrent_id in torrent_ids:
            continue
        else:
            torrent_ids.add(torrent_id)
            downloads[t] = g

    # Download torrents
    if not downloads:
        print("No new torrents to download.")
        return []
    if not yes:
        print("\nWould you like to download the torrents for these albums?:")
    else:
        print("\nDownloading the following torrents:")
    y = False
    while not y:  # Prompt for editing
        for torrent in downloads.values():
            m = "{} - {} [{}][{} {}]: torrentid={}".format(
                *[torrent[k] for k in ("artist", "groupName")]
                + [torrent["torrent"][k] for k in "media format encoding".split()]
                + [torrent["torrent"]["torrentId"]]
            )
            print("\t", m)
        # get estimated buffer
        try:
            new_buff = await utils.check_dl_buffer(downloads.values(), api)
        except utils.NotEnoughDownloadBuffer as e:
            log.critical("%s", e.args[0])
            if not yes and not re.match("y", input("Continue?: "), re.I):
                return 0
        else:
            print(
                f"After download your new buffer will be "
                f"{humanize.naturalsize(new_buff, gnu=True)}"
            )

        inpt = "" if not yes else "y"
        while not inpt:
            try:
                inpt = input("(Yes/No/Edit)").lower()[0]
            except IndexError:
                continue
            if inpt not in "yne":
                inpt = ""
        if inpt == "n":
            return unmatched
        if inpt == "y":
            y = True
        if inpt == "e":
            downloads = ui.edit_torrent_downloads(downloads)

    await download_torrents(downloads)
    return missing


async def dl_torrents_to_deluge(downloads, use_fl=False):
    api = await get_api()
    with deluge.Client() as client:
        paused = bool(config["deluge"]["add_paused"].get())

        async def add_torrent(torrent):
            filename, data = await api.get_torrent(
                torrent["torrent"]["torrentId"], use_fl
            )
            try:
                client.add_torrent_file(filename, data, paused)
            except ValueError:
                log.error(
                    "Could not add torrent %s to deluge.",
                    torrent["torrent"]["torrentId"],
                )

        dls = [
            asyncio.ensure_future(add_torrent(torrent))
            for torrent in downloads.values()
        ]
        await asyncio.gather(*dls)

    print("Finished.")
    return


async def dl_torrent_to_file(torrent, dl_dir, use_fl=False):
    dl_dir = config["torrent_directory"].as_filename()
    api = await get_api()
    try:
        filename, data = await api.get_torrent(torrent["torrent"]["torrentId"], use_fl)
    except ValueError:
        log.error("Could not download torrent %s.", torrent["torrent"]["torrentId"])
        log.debug("Error details", exc_info=True)
        return
    with open(Path(dl_dir) / filename, "wb") as fout:
        fout.write(data)
    log.info("Downloaded %s.", filename)


async def download_torrents(downloads):
    use_fl = bool(config["redacted"]["use_fl_tokens"].get())
    dl_dir = config["torrent_directory"].as_filename()
    if use_fl:
        log.info(
            "Downloading multiple torrents with FL tokens is SLOW, "
            "expect this to take a while."
        )
    if config["enable_deluge"].get():
        try:
            await dl_torrents_to_deluge(downloads, use_fl)
            return
        except ConnectionRefusedError:
            print("\nThere was an error connecting to the deluge server.")
            print("Saving torrents to files instead.")
            # Fail out to normal download

    # Download to files

    dls = [
        asyncio.ensure_future(dl_torrent_to_file(torrent, dl_dir, use_fl))
        for torrent in downloads.values()
    ]
    await asyncio.gather(*dls)


async def main(spotlist, yes=False):
    # Get Beets library
    dbpath = config["beets_library"].as_filename()
    library = beets.library.Library(dbpath)

    # Parse the playlist
    playlist_title, track_info = await playlist.parse_playlist(spotlist, library)
    log.info('Successfully parsed playlist "%s".', playlist_title)
    # Match exsisting tracks
    log.info("Matching track list to beets library...")
    matched = matching.beets_match(
        track_info, library, bool(config["restrict_album"].get())
    )
    unmatched = [
        track
        for track, i in matched.items()
        if i is None and not isinstance(track, str)
    ]
    log.info(
        "Finished. There are %d/%d tracks that could not be matched.",
        len(unmatched),
        len(track_info),
    )
    if re.match(r".*\.(m3u|m3u8)$", spotlist) and config["overwrite_m3u"].get():
        save_path = Path(spotlist)
        overwrite_flag = True
    else:
        save_dir = config["m3u_directory"].as_filename()
        save_path = Path(save_dir) / "{}.m3u".format(playlist_title)
        overwrite_flag = False
    if save_path.exists() and not overwrite_flag:
        if yes or re.match(r"y", input("\nOverwrite %s?: " % save_path)):
            playlist.create_m3u_from_info(
                matched,
                save_path,
                url=spotlist if playlist.parse_spotfiy_id(spotlist) else None,
            )
    else:
        playlist.create_m3u_from_info(
            matched,
            save_path,
            url=spotlist if playlist.parse_spotfiy_id(spotlist) else None,
        )

    if len(unmatched) == 0:
        return 0
    print("\nThe following tracks could not be matched to your beets library:")
    print("\n".join(map(str, unmatched)))

    # Search [REDACTED] for missing tracks
    redacted_disabled = config["redacted"]["disable"].get()
    if redacted_disabled:
        log.info("\nSearching Redacted is Disabled by config.")
    if not redacted_disabled:
        if yes or re.match(
            r"y", input("\nSearch [REDACTED] for missing tracks?(y/n): "), flags=re.I
        ):
            unmatched = await search_redlist_and_dl(unmatched, yes=yes)

        if unmatched:
            print(
                "\nThe Following tracks could not be found in beets OR on [REDACTED]:"
            )
            for t in unmatched:
                print(t)
    missing_track_playlist = config["missing_track_playlist"].get()
    if (
        (missing_track_playlist == "yes" and missing_track_playlist != "no")
        or missing_track_playlist is not None
        or re.match(
            r"y",
            input(
                "\nWould you like to create a new spotify playlist with the missing tracks?(y/n): "
            ),
            flags=re.I,
        )
    ):
        await playlist.make_missing_spotify_playlist(playlist_title, unmatched)
    print("Finished.")
    return 0


async def cli():
    parser = argparse.ArgumentParser(
        usage="redlist [options] <playlist>...", description=__doc__
    )
    parser.add_argument("playlist", nargs="*")
    parser.add_argument(
        "--config", dest="configfile", help="Path to configuration file."
    )
    parser.add_argument(
        "--beets-library", dest="beets_library", help="The beets library to use"
    )
    parser.add_argument(
        "--downloads",
        dest="torrent_directory",
        help=("Directory new torrents will be saved to " "(exclusive with --deluge)"),
    )
    parser.add_argument(
        "-y",
        dest="yes",
        action="store_true",
        help="Assume yes to all queries and do not prompt.",
    )
    parser.add_argument(
        "--deluge",
        dest="enable_deluge",
        action="store_const",
        const=True,
        help="Load torrents directly into deluge",
    )
    parser.add_argument(
        "--deluge-server",
        dest="deluge.host",
        help="address of deluge server, (Default: localhost)",
    )
    parser.add_argument(
        "--deluge-port",
        dest="deluge.port",
        help="Port of deluge server, (Default: 58846)",
    )
    parser.add_argument(
        "--restrict-album",
        dest="restrict_album",
        action="store_const",
        const=True,
        help="Only match tracks if they come from the same album.",
    )
    parser.add_argument(
        "--use-fl-tokens",
        dest="redacted.use_fl_tokens",
        help="Use freeleach tokens " "(note: slows torrent download SIGNIFICANTLY).",
        action="store_const",
        const=True,
    )
    parser.add_argument(
        "--show-config",
        dest="show_config",
        action="store_true",
        help="Dump the current configuration values and exit.",
    )
    parser.add_argument(
        "--overwrite-m3u",
        dest="overwrite_m3u",
        action="store_const",
        const=True,
        help=(
            "If argument is an m3u, overwrite it "
            "instead of outputting to playlist dir."
        ),
    )
    parser.add_argument(
        "--no-redact",
        dest="redact",
        action="store_false",
        help="Do not redact sensitve information when showing config.",
    )
    parser.add_argument(
        "--log-level",
        dest="loglevel",
        help="Set the log level. (Default: INFO)",
        default="INFO",
        choices=["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"],
    )
    options = parser.parse_args()
    if options.configfile:
        try:
            config.set_file(options.configfile)
        except confuse.ConfigReadError:
            print("Could not open the config file {}.".format(options.configfile))
            return 2
    if options.show_config:
        utils.resolve_configured_paths(config)
        print(
            '# Configuration file at "{}"\n'.format(
                os.path.join(config.config_dir(), "config.yaml")
            )
        )
        print(config.dump(redact=options.redact))
        return 0
    args = options.playlist
    if len(args) < 1:
        parser.error("Must specify at least one playlist")
    log.parent.setLevel(getattr(logging, options.loglevel))
    config.set_args(options, dots=True)
    utils.resolve_configured_paths(config)
    spotlists = args
    results = []
    for splist in spotlists:
        try:
            results.append(await main(splist, options.yes))
        except Exception:
            log.error("Error Processing %s.", splist, exc_info=True)
            results.append(1)

    if API is not None:
        api = await get_api()
        await api.session.close()
    if not all(r == 0 for r in results):
        return 1
    else:
        return 0


def entry_point():
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(cli())


if __name__ == "__main__":
    sys.exit(entry_point())
