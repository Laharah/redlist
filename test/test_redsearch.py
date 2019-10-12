import pytest
import asyncio
import re
from pathlib import Path

import beets.library

import redlist.redsearch as s
from redlist.matching import TrackInfo
import redlist.redapi
from redlist.playlist import get_sp_data
from redlist.matching import beets_match

from SECRETS import USERNAME, PASSWORD
SPOTLIST = Path('test/txtpl.txt')
BEETSLIB = 'test/beets_library.db'


@pytest.mark.asyncio
async def test_find_album(api):
    track_info = TrackInfo(artist='Up, Bustle & Out',
                           album='One Colour Just Reflects Another',
                           title='1, 2, 3 Alto Y Fuera')
    t_group = await s.find_album(track_info, api, restrict_album=False)
    assert t_group['torrent']['torrentId'] == 969405
    print(t_group)


"""
sample_value = {
    'groupId': 59518,
    'groupName': 'One Colour Just Reflects Another',
    'artist': 'Up, Bustle & Out',
    'cover': 'https://ptpimg.me/j4s612.jpg',
    'tags': ['electronic', 'future.jazz', 'trip.hop'],
    'bookmarked': False,
    'vanityHouse': False,
    'groupYear': 1996,
    'releaseType': 'Album',
    'groupTime': '1489682482',
    'maxSize': 489114570,
    'totalSnatched': 35,
    'totalSeeders': 19,
    'totalLeechers': 0,
    'artist_match': 'up, bustle & out',
    'torrent': {
        'torrentId': 969405,
        'editionId': 2,
        'artists': [{
            'id': 5631,
            'name': 'Up, Bustle & Out',
            'aliasid': 5631
        }],
        'remastered': True,
        'remasterYear': 1996,
        'remasterCatalogueNumber': 'SDW001-2',
        'remasterTitle': '',
        'media': 'CD',
        'encoding': 'V0 (VBR)',
        'format': 'MP3',
        'hasLog': False,
        'logScore': 0,
        'hasCue': False,
        'scene': False,
        'vanityHouse': False,
        'fileCount': 16,
        'time': '2017-03-16 16:41:22',
        'size': 162497572,
        'snatches': 2,
        'seeders': 1,
        'leechers': 0,
        'isFreeleech': False,
        'isNeutralLeech': False,
        'isPersonalFreeleech': False,
        'canUseToken': False,
        'hasSnatched': False
    }
}
"""


@pytest.mark.asyncio
async def test_full_playlist_search(api):
    track_info = get_sp_data(SPOTLIST)
    lib = beets.library.Library(BEETSLIB)

    matched = beets_match(track_info, lib)
    unmatched = [v for v in matched.values() if v is None]
    print('Done matching local tracks, beginning redacted search of %d items' %
          len(unmatched))
    missing = [t for t, m in matched.items() if m is None]
    tasks = {
        track: asyncio.create_task(s.find_album(track, api, restrict_album=False))
        for track in missing
    }
    await asyncio.gather(*tasks.values())
    results = {t: v.result() for t, v in tasks.items()}
    for track, torrent in results.items():
        try:
            print(track, ': ', torrent['artist'], ' - ', torrent['groupName'])
        except (TypeError, AttributeError, KeyError):
            print(track, ': ', torrent)
    print("\nThe following Could not be located:")
    total = 0
    for track, torrent in results.items():
        if torrent is None:
            total += 1
            print(track)
    print(f'Total: {total}')


def test_choose_prefered_torrent():
    from groups import group
    prefs = [r'.*(v0 \(VBR\)|lossless) vinyl', r'mp3 v0', r'flac .*'] 
    prefs = [re.compile(p, re.I) for p in prefs]
    s.choose_prefered_torrent(group, prefs)
