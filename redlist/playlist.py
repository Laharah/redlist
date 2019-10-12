from collections import OrderedDict
import logging
import re
from pathlib import Path
import shlex

from mutagen.easyid3 import EasyID3

from .matching import TrackInfo, track_distance, beets_match
from . import spotify

log = logging.getLogger(__name__)


def spotlist_to_m3u(spotlist, music_dir):
    music_dir = Path(music_dir)
    files = [p.absolute() for p in music_dir.iterdir()]
    listing = get_sp_data(Path(spotlist))
    id3s = {TrackInfo.from_id3(EasyID3(f)) for f in files}
    m3u = []
    for track in listing:
        for id3 in id3s:
            if track_distance(id3, track) <= .3:
                m3u.append(Path(id3.path))
                break
        else:
            log.error("Could not find track %s in %s", str(track), music_dir)
            m3u.append(f'# {track}')

    return '\n'.join(
        str(p.relative_to(music_dir.parent.absolute())) if isinstance(p, Path) else p
        for p in m3u)


def get_sp_data(spotlist):
    listing = [re.split(r'\s,', l) for l in Path(spotlist).read_text().splitlines()]
    tracks = []
    for t in listing:
        tracks.append(TrackInfo(*t))
    return tracks


def create_m3u_from_info(track_infos, output: Path):
    "From a mapping of TrackInfo -> beetsLibraryItems, create a m3u playlist"
    log.info('Writing m3u file to %s.', output)
    with open(output, 'wb') as fout:
        for track, item in track_infos.items():
            try:
                fout.write(item.path)
            except AttributeError:
                fout.write(b'# ' + repr(track).encode('utf8'))
            fout.write(b'\n')


def create_info_from_m3u(m3u: Path, lib):
    'Given an m3u, track_info:beets_match dictionary'
    m3u = Path(m3u)
    matches = OrderedDict()
    for line in m3u.read_text().splitlines():
        if line.startswith('# TrackInfo'):
            info = parse_track_info_string(line)
            matches[info] = None
        else:
            item = lib.items(shlex.quote('path:' + line)).get()
            if item is None:
                log.error('Could not find item at path %s', line)
                continue
            matches[item] = item
    return matches


async def parse_playlist(argument, library):
    'Given a path or spotify uri return playlist_name, track_info'
    match = re.match(r'.*spotify.*[:/]playlist[:/]([\w\d]+)', argument)
    if match:
        log.info('Fetching playlist %s from spotify.', match.group(1))
        return await spotify.fetch_play_list_data(match.group(1))
    f = Path(argument)
    if not f.exists():
        log.error('Could not find the file %s', f)
        raise FileNotFoundError(f)
    if f.suffix in ['.m3u', '.m3u8']:
        log.info('Reading in m3u file %s.', f.stem)
        return f.stem, create_info_from_m3u(f, lib=library)
    log.info('Reading in csv file %s.', f.stem)
    return f.stem, get_sp_data(f)


def parse_track_info_string(line):
    kwargs = {}
    args = re.search(r'TrackInfo\((.*)\)', line).group(1).split(', ')
    for a in args:
        k, v = a.split('=')
        if v == 'None':
            kwargs[k] = None
        elif re.match(r'\d+', v):
            kwargs[k] = int(v)
        else:
            kwargs[k] = v.strip('\'"')
    return TrackInfo(**kwargs)
