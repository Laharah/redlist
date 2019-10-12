import pytest
from pathlib import Path
from pprint import pprint

import beets.library

import redlist.playlist as playlist
import redlist.matching as m

SPOTLIST = Path('test/txtpl.txt')
BEETSLIB = 'test/beets_library.db'


def test_beets_match():
    track_info = playlist.get_sp_data(SPOTLIST)
    lib = beets.library.Library(BEETSLIB)

    matched = m.beets_match(track_info, lib)
    for k, v in matched.items():
        print(k.__repr__(), v.path if v else v, sep=': ')
    assert len([v for v in matched.values() if v is None]) == 12


def test_track_info_from_spotify():
    t = {
        'added_at': '2016-03-03T23:08:55Z',
        'added_by': {
            'external_urls': {
                'spotify': 'https://open.spotify.com/user/kukalicious'
            },
            'href': 'https://api.spotify.com/v1/users/kukalicious',
            'id': 'kukalicious',
            'type': 'user',
            'uri': 'spotify:user:kukalicious'
        },
        'is_local': False,
        'primary_color': None,
        'track': {
            'album': {
                'album_type':
                'album',
                'artists': [{
                    'external_urls': {
                        'spotify':
                        'https://open.spotify.com/artist/1ILwJ5zliBLMsRARQJjOMp'
                    },
                    'href': 'https://api.spotify.com/v1/artists/1ILwJ5zliBLMsRARQJjOMp',
                    'id': '1ILwJ5zliBLMsRARQJjOMp',
                    'name': 'Aim',
                    'type': 'artist',
                    'uri': 'spotify:artist:1ILwJ5zliBLMsRARQJjOMp'
                }],
                'available_markets': [
                    'AD', 'AE', 'AR', 'AT', 'AU', 'BE', 'BG', 'BH', 'BO', 'BR', 'CA',
                    'CH', 'CL', 'CO', 'CR', 'CY', 'CZ', 'DE', 'DK', 'DO', 'DZ', 'EC',
                    'EE', 'EG', 'ES', 'FI', 'FR', 'GB', 'GR', 'GT', 'HK', 'HN', 'HU',
                    'ID', 'IE', 'IL', 'IN', 'IS', 'IT', 'JO', 'JP', 'KW', 'LB', 'LI',
                    'LT', 'LU', 'LV', 'MA', 'MC', 'MT', 'MX', 'MY', 'NI', 'NL', 'NO',
                    'NZ', 'OM', 'PA', 'PE', 'PH', 'PL', 'PS', 'PT', 'PY', 'QA', 'RO',
                    'SA', 'SE', 'SG', 'SK', 'SV', 'TH', 'TN', 'TR', 'TW', 'US', 'UY',
                    'VN', 'ZA'
                ],
                'external_urls': {
                    'spotify': 'https://open.spotify.com/album/6N5ST7D8lhiW1I5YfPDE5R'
                },
                'href':
                'https://api.spotify.com/v1/albums/6N5ST7D8lhiW1I5YfPDE5R',
                'id':
                '6N5ST7D8lhiW1I5YfPDE5R',
                'images': [{
                    'height': 640,
                    'url':
                    'https://i.scdn.co/image/2cb6bc0117f208dd4cd3434e64e9935436892a9c',
                    'width': 640
                }, {
                    'height': 300,
                    'url':
                    'https://i.scdn.co/image/e510f4bf73bc673c628430b959b731e91b4bb24b',
                    'width': 300
                }, {
                    'height': 64,
                    'url':
                    'https://i.scdn.co/image/b10797e61b815b630a1462d4a1d8eb526b86dd2f',
                    'width': 64
                }],
                'name':
                'Cold Water Music',
                'release_date':
                '1999',
                'release_date_precision':
                'year',
                'total_tracks':
                14,
                'type':
                'album',
                'uri':
                'spotify:album:6N5ST7D8lhiW1I5YfPDE5R'
            },
            'artists': [{
                'external_urls': {
                    'spotify': 'https://open.spotify.com/artist/1ILwJ5zliBLMsRARQJjOMp'
                },
                'href': 'https://api.spotify.com/v1/artists/1ILwJ5zliBLMsRARQJjOMp',
                'id': '1ILwJ5zliBLMsRARQJjOMp',
                'name': 'Aim',
                'type': 'artist',
                'uri': 'spotify:artist:1ILwJ5zliBLMsRARQJjOMp'
            }, {
                'external_urls': {
                    'spotify': 'https://open.spotify.com/artist/4hie13XwaObu4XO47ANkWw'
                },
                'href': 'https://api.spotify.com/v1/artists/4hie13XwaObu4XO47ANkWw',
                'id': '4hie13XwaObu4XO47ANkWw',
                'name': 'Qnc',
                'type': 'artist',
                'uri': 'spotify:artist:4hie13XwaObu4XO47ANkWw'
            }],
            'available_markets': [
                'AD', 'AE', 'AR', 'AT', 'AU', 'BE', 'BG', 'BH', 'BO', 'BR', 'CA', 'CH',
                'CL', 'CO', 'CR', 'CY', 'CZ', 'DE', 'DK', 'DO', 'DZ', 'EC', 'EE', 'EG',
                'ES', 'FI', 'FR', 'GB', 'GR', 'GT', 'HK', 'HN', 'HU', 'ID', 'IE', 'IL',
                'IN', 'IS', 'IT', 'JO', 'JP', 'KW', 'LB', 'LI', 'LT', 'LU', 'LV', 'MA',
                'MC', 'MT', 'MX', 'MY', 'NI', 'NL', 'NO', 'NZ', 'OM', 'PA', 'PE', 'PH',
                'PL', 'PS', 'PT', 'PY', 'QA', 'RO', 'SA', 'SE', 'SG', 'SK', 'SV', 'TH',
                'TN', 'TR', 'TW', 'US', 'UY', 'VN', 'ZA'
            ],
            'disc_number':
            1,
            'duration_ms':
            245946,
            'episode':
            False,
            'explicit':
            False,
            'external_ids': {
                'isrc': 'GBKNX0700050'
            },
            'external_urls': {
                'spotify': 'https://open.spotify.com/track/39qTXRJZd7omJi2KZCd0nJ'
            },
            'href':
            'https://api.spotify.com/v1/tracks/39qTXRJZd7omJi2KZCd0nJ',
            'id':
            '39qTXRJZd7omJi2KZCd0nJ',
            'is_local':
            False,
            'name':
            'The Force',
            'popularity':
            52,
            'preview_url':
            'https://p.scdn.co/mp3-preview/e5be8975cfeb4e00d715610e6cc1a90c4da7aae3?cid=031bda217dec48b28a39a997e5a7d317',
            'track':
            True,
            'track_number':
            3,
            'type':
            'track',
            'uri':
            'spotify:track:39qTXRJZd7omJi2KZCd0nJ'
        },
        'video_thumbnail': {
            'url': None
        }
    }
    assert str(m.TrackInfo.from_spotify(t)) == str(
        m.TrackInfo(artist='Aim',
                    title='The Force',
                    album='Cold Water Music',
                    length=245.946,
                    feat='Qnc'))
