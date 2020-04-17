import aiohttp
import asyncio
import base64
import time
import json
import logging
import re
from cryptography import fernet
from urllib.parse import urlencode
from pathlib import Path
import os

from beets.util import sanitize_path

from . import config
from . import ui
from . import matching

log = logging.getLogger(__name__)

KEY = b'vWaggFkc0KRH_19qhyjhduPIF8vq6eFrUGngiUUahdc='
CODE = (
    b'gAAAAABdm60DpX-pHvoEtf2JbZmK6SQYjLE2MwK25LJT1JBiJcol7KHaOgnHnwYx8Z8DQR1igOnXD'
    b'B-BhFGuD0dXAHvJRBMpbyR1m6KfedbSoFh4n9AKt5uY8yoAx3BeoPlFqVR3I3Exfbn5vUP9jAH7jamecRMSSPc'
    b'Y-yL5iZyQ_5rrkOUZ2ls=')
frn = fernet.Fernet(KEY)
AUTH_HEADER = frn.decrypt(CODE)
CLIENT_ID, _ = AUTH_HEADER.split(b':')
AUTH_HEADER = {'Authorization': 'Basic ' + base64.b64encode(AUTH_HEADER).decode('ascii')}
AUTH_URL = 'https://accounts.spotify.com/authorize'
TOKEN_URL = 'https://accounts.spotify.com/api/token'


async def fetch_play_list_data(playlist_id, token=None):
    'given a uri or playlist id, return a list of TrackInfo objects'
    if token is None:
        token = SpotifyAccessToken()
        await token.ensure_valid()

    url = f'https://api.spotify.com/v1/playlists/{playlist_id}'
    data = {'next': url}
    name = playlist_id
    tracks = []
    async with aiohttp.ClientSession(headers=token.auth_header) as session:
        while data['next']:
            async with session.get(data['next']) as resp:
                if resp.status == 429:  # Rate limit exceded
                    await asyncio.sleep(resp.headers['Retry-After']+1)
                    continue
                json = await resp.json()
            try:  # First iteration
                data = json['tracks']
                name = json['name']
            except KeyError:  # more than 100 data
                log.debug('Fetching more playlist tracks from Spotify.')
                data = json
            tracks.extend(matching.TrackInfo.from_spotify(t) for t in data['items'])
            log.debug('%s tracks Fetched from playlist.', len(tracks))
    name = re.sub(r'[\\/]', '_', name)
    name = sanitize_path(name)
    return name, tracks


def generate_auth_url():
    data = {
        'client_id': CLIENT_ID,
        'response_type': 'code',
        'redirect_uri': 'http://localhost/',
    }
    return '?'.join((AUTH_URL, urlencode(data)))


def parse_resp_code(url):
    return url.split("?code=")[1].split("&")[0]


class SpotifyAccessToken:
    def __init__(self):
        self.token_info = None
        config_dir = Path(config.config_dir())
        try:
            with open(config_dir / "spotify_token.json") as fin:
                self.token_info = json.load(fin)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            log.debug('Could not load spotify token because of %s', e, exc_info=True)

    @property
    def is_valid(self):
        now = time.time()
        try:
            if self.token_info['expires_at'] - now > 60:
                return True
        except (TypeError, KeyError):
            pass
        return False

    @property
    def auth_header(self):
        assert self.is_valid
        return {'Authorization': 'Bearer %s' % self.token_info['access_token']}

    def save(self):
        config_dir = Path(config.config_dir())
        with open(config_dir / "spotify_token.json", 'w') as fout:
            json.dump(self.token_info, fout)
            log.debug('Saved new spotify auth token to %s', fout.name)

    async def ensure_valid(self):
        if self.is_valid:
            return
        if not self.token_info:
            await self.gen_new()
            return
        await self.refresh()

    async def gen_new(self):
        log.debug('Attempting to generate new auth token.')
        redirect = ui.get_spotify_auth_code(generate_auth_url())
        code = parse_resp_code(redirect)

        data = {
            'redirect_uri': 'http://localhost/',
            'code': code,
            # 'scope': 'playlist-read-private',
            'grant_type': 'authorization_code'
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(TOKEN_URL, headers=AUTH_HEADER, data=data) as resp:
                token_info = await resp.json()
                if resp.status != 200:
                    raise ValueError(resp.reason, token_info)
        token_info['expires_at'] = int(time.time()) + token_info['expires_in']
        self.token_info = token_info
        self.save()
        return token_info

    async def refresh(self):
        data = {
            'refresh_token': self.token_info['refresh_token'],
            'grant_type': 'refresh_token'
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(TOKEN_URL, headers=AUTH_HEADER, data=data) as resp:
                token_info = await resp.json()
        token_info['expires_at'] = int(time.time()) + token_info['expires_in']
        self.token_info.update(token_info)
        log.debug('Spotify token successfully refreshed.')
        self.save()
        return token_info
