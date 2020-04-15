import pytest
from pathlib import Path
from pprint import pprint

from mutagen.easyid3 import EasyID3
from fuzzywuzzy import fuzz
import beets.library

import redlist.playlist as pl
from redlist.matching import TrackInfo

MUSIC = Path('lounge')
SPOTLIST = Path('test/txtpl.txt')
BEETSLIB = 'test/beets_library.db'
M3U = 'test/txtpl.m3u'


def test_spotlist_to_m3u():
    "given a spotlistr text dump and a direcory of files, create an m3u"
    m3u = pl.spotlist_to_m3u(SPOTLIST, MUSIC)
    for line, data in zip(m3u.splitlines(),
                          (l.split(' , ') for l in SPOTLIST.read_text().splitlines())):
        p = Path(line)
        assert Path(line).exists()
        id3 = EasyID3(p)
        a = ' '.join([id3['artist'][0], id3['title'][0]])
        b = ' '.join([data[0], data[1]])
        assert fuzz.token_set_ratio(a, b) > 90


def test_create_info_from_m3u(tmp_path):
    lib = beets.library.Library(BEETSLIB)
    matches = pl.create_info_from_m3u(M3U, lib)
    out = tmp_path / 'tmp'
    pl.create_m3u_from_info(matches, out)
    assert Path(M3U).read_text() == out.read_text()


def test_parse_track_info_string():
    t = TrackInfo(artist='Daft Punk',
                  title='Solar Sailer',
                  album="TRON's, Legacy",
                  length=162.12,
                  spotify_id='0Jc2SfIHv63JNsUZpunh54')
    old = pl.parse_track_info_string(
        """# TrackInfo(artist='Daft Punk', title='Solar Sailer', album="TRON's, Legacy", length=162.12, spotify_id='0Jc2SfIHv63JNsUZpunh54')"""
    )
    new = pl.parse_track_info_string(
        """# TrackInfo(json='{"artist": "Daft Punk", "title": "Solar Sailer", "album": "TRON\'s, Legacy", "length": 162.12, "spotify_id": "0Jc2SfIHv63JNsUZpunh54"}')"""
    )
    assert t.json() == new.json()
