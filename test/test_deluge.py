import pytest

from redlist import deluge
import deluge_client


@pytest.fixture(autouse=True)
def default_config():
    deluge.config.clear()
    deluge.config.read(user=False)


def test_resolve_password_from_local(tmpdir):
    with open(tmpdir / 'auth', 'w') as auth:
        auth.write('localclient:localpass:10')
    deluge.resolve_password(tmpdir)
    assert deluge.config['deluge']['username'].get() == 'localclient'
    assert deluge.config['deluge']['password'].get() == 'localpass'


def test_resolve_password_from_config():
    deluge.config['deluge']['password'] = '123'
    deluge.config['deluge']['username'] = 'user123'
    deluge.resolve_password()
    assert deluge.config['deluge']['username'].get() == 'user123'
    assert deluge.config['deluge']['password'].get() == '123'


@pytest.mark.skip(reason='user interaction')
def test_resolve_password_non_pinentry():
    deluge.config['deluge']['host'] = 'example.com'
    deluge.config['pinentry'] = False
    deluge.resolve_password()
    assert deluge.config['deluge']['username'].get() is not None
    assert deluge.config['deluge']['password'].get() is not None


@pytest.mark.skip(reason='user interaction')
def test_resolve_password_pinentry():
    deluge.config['deluge']['host'] = 'example.com'
    deluge.resolve_password()
    assert deluge.config['deluge']['username'].get() is not None
    assert deluge.config['deluge']['password'].get() is not None


@pytest.mark.skip(reason='user interaction')
def test_resolve_password_only():
    deluge.config['deluge']['host'] = 'example.com'
    deluge.config['deluge']['username'] = 'jonsmith'
    deluge.resolve_password()
    assert deluge.config['deluge']['username'].get() is not None
    assert deluge.config['deluge']['password'].get() is not None


@pytest.mark.skip(reason='deluge only')
def test_get_client():
    client = deluge.Client()
    assert client._client.host == 'localhost'
    assert client._client.port == 58846


@pytest.mark.skip(reason='deluge only')
@pytest.mark.asyncio
async def test_client_connect():
    client = deluge.Client()
    await client.connect()
    client._client.disconnect()


@pytest.mark.skip(reason='deluge only')
@pytest.mark.asyncio
async def test_client_add_torrent():
    client = deluge.Client()
    with open(
            'test/Kid Koala - Carpal Tunnel Syndrome - 2013 (WEB - MP3 - V0 (VBR))-1364328.torrent',
            'rb') as fin:
        data = fin.read()
    await client.connect()
    await client.add_torrent_file(
        'Kid Koala - Carpal Tunnel Syndrome - 2013 (WEB - MP3 - V0 (VBR))-1364328.torrent',
        data,
        paused=True)
