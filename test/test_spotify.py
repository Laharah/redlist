import pytest
from cryptography import fernet

import redlist.spotify as sp


def test_decrypt():
    frn = fernet.Fernet(sp.KEY)
    assert len(frn.decrypt(sp.CODE)) == 65


@pytest.mark.skip
@pytest.mark.asyncio
async def test_get_access_token():
    token = sp.SpotifyAccessToken()
    token.token_info = None
    assert not token.is_valid
    await token.ensure_valid()


@pytest.mark.asyncio
async def test_token_refresh():
    token = sp.SpotifyAccessToken()
    assert token.is_valid
    code = token.token_info['access_token']
    await token.refresh()
    assert token.is_valid
    assert token.token_info['access_token'] != code

@pytest.mark.asyncio
async def test_fetch_playlist_data():
    name, data = await sp.fetch_play_list_data('1yQQKwc2ZrjfEBQdsheZnH')
    assert name == 'hop dat'
    assert len(data) == 229
