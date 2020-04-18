import time
import asyncio
import aiohttp
import warnings
import json
import re
import random
import logging

log = logging.getLogger(__name__)


class LoginException(Exception):
    def __init__(self, data=None):
        self.data = data


class TokenBucket():
    def __init__(self, capacity, fill_rate):
        self.rate = fill_rate
        self.capacity = capacity
        self.last_update = time.monotonic()
        self._tokens = capacity

    @property
    def tokens(self):
        now = time.monotonic()
        if self._tokens < self.capacity:
            new_tokens = (now - self.last_update) * self.rate
            self._tokens = min(self.capacity, self._tokens + new_tokens)
        self.last_update = now
        return self._tokens

    @tokens.setter
    def tokens(self, value):
        self._tokens = value

    async def get(self):
        while self.tokens < 1:
            await asyncio.sleep(1)
        self.tokens -= 1
        return 1


with warnings.catch_warnings():
    warnings.simplefilter("ignore", category=DeprecationWarning)

    class RateLimitedSession(aiohttp.ClientSession):
        def __init__(self, request_burst, request_rate, *args, **kwargs):
            self.token_bucket = TokenBucket(request_burst, request_rate)
            super().__init__(*args, **kwargs)

        async def get(self, *args, **kwargs):
            token = await self.token_bucket.get()
            for backoff in [1, 2, None]:
                try:
                    return super().get(*args, **kwargs)
                except aiohttp.client_exceptions.ServerDisconnectedError:
                    if backoff is None:
                        raise
                    log.error('ServerDisconnectedError, backing off')
                    await asyncio.sleep(backoff + random.random())

        async def post(self, *args, **kwargs):
            token = await self.token_bucket.get()
            for backoff in [1, 2, None]:
                try:
                    return super().post(*args, **kwargs)
                except aiohttp.client_exceptions.ServerDisconnectedError:
                    if backoff is None:
                        raise
                    log.error('ServerDisconnectedError, backing off')
                    await asyncio.sleep(backoff + random.random())


headers = {
    'Content-type': 'application/x-www-form-urlencoded',
    'Accept-Charset': 'utf-8',
    'User-Agent': 'redapi [laharah]'
}


class RedAPI:
    def __init__(self, user=None, host="https://redacted.ch", cookies=None, api_key=None):
        self.headers = {k: v for k, v in headers.items()}
        self.api_key = api_key
        if api_key:
            self.headers['Authorization'] = api_key
        self.session = RateLimitedSession(4, 4 / 11, headers=self.headers)
        if cookies and not api_key:
            self.session.cookie_jar.load(cookies)
        self.authed = False
        self.username = user
        self.authkey = None
        self.passkey = None
        self.host = host
        self.fl_bucket = TokenBucket(1, 1 / 70)

    async def _auth(self):
        "Get authkey from server, must always be done after login or first connection"
        try:
            accountinfo = await self.request("index")
        except aiohttp.client_exceptions.ContentTypeError as e:
            raise LoginException(e.data) from e
        if accountinfo['status'] != 'success':
            raise LoginException(str(accountinfo))
        self.authkey = accountinfo["response"]["authkey"]
        self.passkey = accountinfo["response"]["passkey"]
        self.user_id = accountinfo["response"]["id"]
        if not self.username:
            self.username = accountinfo["response"]["username"]

    async def login(self, password, username=None):
        if username: self.username = username
        loginpage = self.host + '/login.php'
        data = {
            'username': self.username,
            'password': password,
            'keeplogged': 1,
            'login': 'Login'
        }
        async with await self.session.post(loginpage, data=data) as resp:
            pass
        await self._auth()

    async def get_torrent(self, torrent_id, use_fl=False):
        "Download the torrent at torrent_id -> (filename, data)"
        params = {
            'action': 'download',
            'id': torrent_id,
        }
        if self.api_key:
            torrentpage = self.host + '/ajax.php'
        else:
            torrentpage = self.host + '/torrents.php'
            params.update({'authkey': self.authkey, 'torrent_pass': self.passkey})
        if use_fl:
            await self.fl_bucket.get()
            params['usetoken'] = '1'
        async with await self.session.get(torrentpage,
                                          params=params,
                                          allow_redirects=False) as response:
            expected = 'application/x-bittorrent; charset=utf-8'
            if response.headers['content-type'] != expected:
                log.error(response.headers)
                if log.getEffectiveLevel() <= logging.DEBUG:
                    body = await response.content.read()
                    log.debug(body)
                raise ValueError("Wrong content-type: {}".format(
                    response.headers['content-type']))
            match = re.search(r'filename="(.+)"', response.headers['content-disposition'])
            filename = match.group(1)
            return filename, await response.content.read()

    async def request(self, action, **kwargs):
        "Make an AJAX request for a given action"
        ajaxpage = self.host + '/ajax.php'
        params = {'action': action}
        if self.authkey and not self.api_key:
            params['auth'] = self.authkey
        params.update(kwargs)

        async with await self.session.get(ajaxpage, params=params) as response:
            try:
                res = await response.json()
            except aiohttp.client_exceptions.ContentTypeError as e:
                try:
                    res = json.loads(await response.text())
                except json.JSONDecodeError:
                    e.data = await response.text()
                    raise e
        return res
