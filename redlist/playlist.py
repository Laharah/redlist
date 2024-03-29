from collections import OrderedDict
import logging
import re
from pathlib import Path
import shlex

from mutagen.easyid3 import EasyID3

from .matching import TrackInfo, track_distance, beets_match
from . import spotify
from . import config

log = logging.getLogger(__name__)


def spotlist_to_m3u(spotlist, music_dir):
    music_dir = Path(music_dir)
    files = [p.absolute() for p in music_dir.iterdir()]
    listing = get_sp_data(Path(spotlist))
    id3s = {TrackInfo.from_id3(EasyID3(f)) for f in files}
    m3u = []
    for track in listing:
        for id3 in id3s:
            if track_distance(id3, track) <= 0.3:
                m3u.append(Path(id3.path))
                break
        else:
            log.error("Could not find track %s in %s", str(track), music_dir)
            m3u.append(f"# {track}")

    return "\n".join(
        str(p.relative_to(music_dir.parent.absolute())) if isinstance(p, Path) else p
        for p in m3u
    )


def get_sp_data(spotlist):
    listing = [re.split(r"\s,", l) for l in Path(spotlist).read_text().splitlines()]
    tracks = []
    for t in listing:
        tracks.append(TrackInfo(*t))
    return tracks


def create_m3u_from_info(track_infos, output: Path, url=None):
    "From a mapping of TrackInfo -> beetsLibraryItems, create a m3u playlist"
    log.info("Writing m3u file to %s.", output)
    with open(output, "wb") as fout:
        if url:
            fout.write("# {}\n".format(url).encode("utf8"))
        for track, item in track_infos.items():
            try:
                fout.write(item.path)
            except AttributeError:
                if isinstance(track, str):
                    fout.write(track.encode("utf8"))
                elif isinstance(track, TrackInfo):
                    fout.write(
                        b"# TrackInfo(json='''%s''')" % track.json().encode("utf8")
                    )
            fout.write(b"\n")


def create_info_from_m3u(m3u: Path, lib):
    "Given an m3u, track_info:beets_match dictionary"
    m3u = Path(m3u)
    matches = OrderedDict()
    for line in m3u.read_text().splitlines():
        if line.startswith("# TrackInfo"):
            info = parse_track_info_string(line)
            matches[info] = None
        elif line.startswith("#"):
            matches[line] = None
            continue
        else:
            item = lib.items(shlex.quote("path:" + line)).get()
            if item is None:
                log.error("Could not find item at path %s", line)
                continue
            matches[item] = item
    return matches


async def parse_playlist(argument, library):
    "Given a path or spotify uri return playlist_name, track_info"
    spotify_id = parse_spotfiy_id(argument)
    if spotify_id:
        log.info("Fetching playlist %s from spotify.", spotify_id)
        return await spotify.fetch_play_list_data(spotify_id)
    f = Path(argument)
    if not f.exists():
        log.error("Could not find the file %s", f)
        raise FileNotFoundError(f)
    if f.suffix in [".m3u", ".m3u8"]:
        log.info("Reading in m3u file %s.", f.stem)
        return f.stem, create_info_from_m3u(f, lib=library)
    log.info("Reading in csv file %s.", f.stem)
    return f.stem, get_sp_data(f)


async def make_missing_spotify_playlist(title, trackinfos):
    try:
        assert all(hasattr(t, "spotify_id") for t in trackinfos)
    except AssertionError:
        log.error("Not all tracks have a spotify id, cannot create a spotify playlist.")
        return
    ids = (t.spotify_id for t in trackinfos)
    description = (
        f"A playlist of songs from the {title} playlist "
        "that you do not have in your beets library."
    )
    try:
        location = await spotify.create_new_playlist(
            title + " (missing tracks)", ids, description
        )
    except Exception as e:
        log.error("Could not create spotify playlist!")
        log.debug("Stack Trace:", exc_info=True)
        if isinstance(e, spotify.SpotifyError):
            try:
                if e.json["error"]["status"] == 403:
                    token_file = Path(config.config_dir()) / "spotify_token.json"
                    log.error(
                        (
                            "[RED]list does not have sufficient permissions."
                            " Try deleting %s to reauthorize"
                        ),
                        token_file,
                    )
            except KeyError:
                pass
        return
    print(
        f"created playlist of missing tracks at : https://open.spotify.com/playlist/{location}"
    )


def parse_spotfiy_id(address):
    "Return the playlist id if it's a spotify playlist. Otherwise return False"
    match = re.match(r".*spotify.*[:/]playlist[:/]([\w\d]+)", address)
    return match.group(1) if match else None


def parse_track_info_string(line):
    # Try extracting json first
    m = re.search(r"json=[\'|\"]{1,3}(.+?)[\'\"]{1,3}\)$", line)
    if m:
        return TrackInfo(json=m.group(1))
    # Old (incorrect) style. Must keep for compatibility
    kwargs = {}
    line = re.search(r"TrackInfo\((.*)\)", line).group(1)
    args = re.findall(r"[\w|_].+?\=[\',\"]?.*?[\d|\'|\"]\,", line)
    args = [a.strip("'\",") for a in args]
    for a in args:
        k, v = a.split("=")
        if v == "None":
            kwargs[k] = None
        elif re.match(r"\d+", v):
            kwargs[k] = float(v)
        else:
            kwargs[k] = v.strip("'\"")
    return TrackInfo(**kwargs)
