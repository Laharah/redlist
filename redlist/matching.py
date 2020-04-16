import re
import shlex
import json
import logging
from collections import OrderedDict
from itertools import zip_longest

from beets.autotag import hooks as beethooks
from beets import config as beetconfig

VA_ARTISTS = '', 'various artists', 'various', 'va', 'unknown'

log = logging.getLogger(__name__)


class TrackInfo:
    """
    Stores information about a potential track.
    Required Arguments:
        artist: the artist name
        title: the title of the track
    Additional Arguments:
        album: Title of the album the track is from
        length: Length of track in mm:ss format
    
    All other keyword arguments will be stored as attributes.
    """
    def __init__(self, *args, **kwargs):
        if 'json' in kwargs:
            kwargs = json.loads(kwargs['json'])
            args = []
        arg_order = ['artist', 'title', 'album', 'length']
        self.fields = []
        for k, v in zip_longest(arg_order, args):
            self.fields.append(k)
            self.__setattr__(k, v.strip() if v else None)
        if kwargs:
            for k, v in kwargs.items():
                if k not in self.fields:
                    self.fields.append(k)
                try:
                    self.__setattr__(k, v.strip())
                except AttributeError:
                    self.__setattr__(k, v)
        if not self.artist or not self.title:
            raise ValueError("All Tracks require an artist and a track")

        try:
            self.convert_length()
        except AttributeError:
            pass

    def _clean_feat(self):
        fields = ['artist']
        sp = self.artist.split(',')
        if len(sp) > 1:
            self.artist = sp[0]
        for f in fields:
            m = re.match(r'(.+?)[\s\-]+(, |feat(\. |uring )?)(.+)',
                         self.__getattribute__(f))
            if m:
                self.feat = m.groups()[-1]
                self.__setattr__(f, m.group(1))
                self.fields.append('feat')
                log.debug('Cleaned featured artist %s from %s field.', self.feat, f)

    def convert_length(self):
        if not self.length:
            return
        multiplicand = 1
        total = 0
        for t in map(int, reversed(self.length.split(':'))):
            total += multiplicand * t
            multiplicand *= 60
        self.length = total

    @classmethod
    def from_id3(cls, id3):
        keys = ['artist', 'title', 'album']
        args = []
        for k in keys:
            try:
                args.append(id3[k][0])
            except KeyError:
                pass
        return cls(*args, path=id3.filename)

    @classmethod
    def from_spotify(cls, track):
        kwargs = {}
        if 'track' in track and isinstance(track['track'], dict):
            track = track['track']
        kwargs['artist'] = track['artists'][0]['name']
        if len(track['artists']) > 1:
            kwargs['feat'] = track['artists'][1]['name']
        kwargs['title'] = track['name']
        kwargs['album'] = track['album']['name']
        kwargs['length'] = track['duration_ms'] / 1000
        kwargs['spotify_id'] = track['id']
        return cls(**kwargs)

    def json(self):
        return json.dumps({f: self.__getattribute__(f) for f in self.fields})

    def __str__(self):
        return f'{self.artist}{" - "+self.album if self.album else ""} - {self.title}'

    def __repr__(self):
        d = ['='.join((f, repr(self.__getattribute__(f)))) for f in self.fields]
        return f'{self.__class__.__name__}({", ".join(d)})'


def track_distance(item, track_info, restrict_album=False):
    dist = beethooks.Distance()

    if item.length and track_info.length:
        grace = beetconfig['match']['track_length_grace'].as_number()
        length_max = beetconfig['match']['track_length_max'].as_number()
        diff = abs(item.length - track_info.length) - grace
        dist.add_ratio('track_length', diff, length_max)

    dist.add_string('track_title', item.title, track_info.title)

    if item.artist.lower() not in VA_ARTISTS:
        dist.add_string('track_artist', item.artist, track_info.artist)

    if restrict_album and (track_info.album and item.album):
        dist.add_string('album', track_info.album, item.album)

    return dist


def match_artist(track_artist, artists):
    d = {}
    for a in artists:
        dist = beethooks.Distance()
        dist.add_string('artist', track_artist, a)
        d[dist] = a
    best = min(d)
    if best > .1:
        return None
    return d[best]


def beets_match(track_info, lib, restrict_album=False):
    original = track_info if isinstance(track_info, dict) else None
    if original:
        track_info = [t for t, v in original.items() if v is None]
    matched = {}
    for t in track_info:
        if not isinstance(t, TrackInfo):
            log.debug('%s is not a TrackInfo object, skipping.', t)
            continue
        res = list(lib.items(shlex.quote('title:' + t.title)))
        if not res and t.album:
            res.extend(lib.items(shlex.quote('album:' + t.album)))
        if not res and t.artist:
            res.extend(lib.items(shlex.quote('artist:' + t.artist)))
        if not res:
            matched[t] = None
            continue
        else:
            canidates = {
                track_distance(r, t, restrict_album=restrict_album): r
                for r in res
            }

        best = min(canidates)
        if best >= .3:
            matched[t] = None
        else:
            matched[t] = canidates[best]
    if original:
        original.update(matched)
        matched = original
    return matched
