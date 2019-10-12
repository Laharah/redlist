import pytest
import asyncio

import redlist.redapi

from SECRETS import USERNAME, PASSWORD


@pytest.fixture(scope='session')
@pytest.mark.asyncio
def event_loop():
    loop = asyncio.get_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope='session')
async def api():
    try:
        handle = redlist.redapi.RedAPI(user=USERNAME, cookies='cookies.dat')
    except FileNotFoundError:
        handle = redlist.redapi.RedAPI(user=USERNAME)
    try:
        await handle._auth()
    except redlist.redapi.LoginException:
        await handle.login(PASSWORD)
    try:
        yield handle
    finally:
        handle.session.cookie_jar.save('cookies.dat')
        await handle.session.close()
