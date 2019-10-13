import time
import asyncio
import aiohttp
import warnings
import json
import re
import random


class LoginException(Exception):
    def __init__(self, data=None):
        self.data = data


class TokenBucket():
    def __init__(self, max_tokens, time_frame):
        self.rate = max_tokens / time_frame
        self.max_tokens = max_tokens
        self.time_frame = time_frame
        self.last_update = time.monotonic()
        self.tokens = float(max_tokens)

    def update_tokens(self):
        now = time.monotonic()
        new_tokens = (now - self.last_update) * self.rate
        if self.tokens + new_tokens >= 1:
            self.tokens = min((self.max_tokens, self.tokens + new_tokens))
            self.last_update = now

    async def get(self):
        while self.tokens < 1:
            self.update_tokens()
            await asyncio.sleep(1)
        self.tokens -= 1
        return 1


with warnings.catch_warnings():
    warnings.simplefilter("ignore", category=DeprecationWarning)

    class RateLimitedSession(aiohttp.ClientSession):
        def __init__(self, max_tokens, time_frame, *args, **kwargs):
            self.token_bucket = TokenBucket(max_tokens, time_frame)
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
    def __init__(self, user=None, server="https://redacted.ch", cookies=None):
        self.session = RateLimitedSession(4, 11, headers=headers)
        if cookies:
            self.session.cookie_jar.load(cookies)
        self.authed = False
        self.username = user
        self.authkey = None
        self.passkey = None
        self.server = server

    async def _auth(self):
        "Get authkey from server, must always be done after login or first connection"
        try:
            accountinfo = await self.request("index")
        except aiohttp.client_exceptions.ContentTypeError as e:
            raise LoginException(e.data) from e
        self.authkey = accountinfo["response"]["authkey"]
        self.passkey = accountinfo["response"]["passkey"]
        self.user_id = accountinfo["response"]["id"]
        if not self.username:
            self.username = accountinfo["response"]["username"]

    async def login(self, password, username=None):
        if username: self.username = username
        loginpage = self.server + '/login.php'
        data = {
            'username': self.username,
            'password': password,
            'keeplogged': 1,
            'login': 'Login'
        }
        async with await self.session.post(loginpage, data=data) as resp:
            pass
        await self._auth()
        self.session.token_bucket.tokens -= 2  # trying to prevent hidden rate after login

    async def get_torrent(self, torrent_id):
        "Download the torrent at torrent_id -> (filename, data)"
        torrentpage = self.server + '/torrents.php'
        params = {
            'action': 'download',
            'id': torrent_id,
            'authkey': self.authkey,
            'torrent_pass': self.passkey
        }
        async with await self.session.get(torrentpage,
                                          params=params,
                                          allow_redirects=False) as response:
            expected = 'application/x-bittorrent; charset=utf-8'
            if response.headers['content-type'] != expected:
                raise ValueError("Wrong content-type")
            match = re.search(r'filename="(.+)"', response.headers['content-disposition'])
            filename = match.group(1)
            return filename, await response.content.read()

    async def request(self, action, **kwargs):
        "Make an AJAX request for a given action"
        ajaxpage = self.server + '/ajax.php'
        params = {'action': action}
        if self.authkey:
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
