import pytest
import asyncio

import aiohttp
import time
pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")

from redlist import redapi
from SECRETS import USERNAME, PASSWORD

COOKIES = "tmp.dat"


def test_rate_limit_connector():
    sites = [
        'https://destiny.gg', 'https://xkcd.com', 'https://smbc-comics.com',
        'https://youtube.com'
    ]
    tokens = 2
    time_frame = 2

    async def fetch(session, url):
        async with await session.get(url) as response:
            try:
                res = await response.text()
                print(f"response from {url}")
                return res
            except aiohttp.client_exceptions.ClientPayloadError:
                print(f"Failed response for {url}")
                return "RESPONSE FAILED"

    results = []
    finished = 0

    async def main():
        start = time.time()
        async with redapi.RateLimitedSession(tokens, time_frame) as session:
            tasks = [asyncio.create_task(fetch(session, u)) for u in sites]
            res = await asyncio.gather(*tasks)
        nonlocal finished
        nonlocal results
        results.extend((t.result() for t in tasks))
        finished = time.time() - start

    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
    print([f'{r[:30]}...{r[-10:]}' for r in results])
    print(finished)
    assert -tokens + len(sites) / (tokens / time_frame) < finished


"""From here on out we re-use the token bucket to maintain the rate limit"""


@pytest.mark.asyncio
async def test_straight_auth(api):
    bucket = api.session.token_bucket
    new = redapi.RedAPI(user=USERNAME)
    new.session.token_bucket = bucket
    with pytest.raises(redapi.LoginException) as execinfo:
        await new._auth()
    await new.session.close()


@pytest.mark.asyncio
async def test_login(api):
    bucket = api.session.token_bucket
    red = redapi.RedAPI(user=USERNAME)
    red.session.token_bucket = bucket

    await red.login(PASSWORD)

    assert red.passkey
    assert red.authkey
    print("Logged in")
    print("Storing Cookies for future tests")
    red.session.cookie_jar.save(COOKIES)
    await red.session.close()


@pytest.mark.asyncio
async def test_cookie_auth(api):
    bucket = api.session.token_bucket
    red = redapi.RedAPI(user=USERNAME)
    red.session.token_bucket = bucket
    red.session.cookie_jar.load(COOKIES)
    assert not red.authkey
    await red._auth()
    assert red.authkey and red.passkey
    await red.session.close()
    import os
    os.remove(COOKIES)


@pytest.mark.asyncio
async def test_get_torrent(api):
    filename, data = await api.get_torrent(1327467)
    assert filename == 'Amon Tobin - Creatures - 1996 (Vinyl - MP3 - 320)-1327467.torrent'
    assert len(data) == 5286
