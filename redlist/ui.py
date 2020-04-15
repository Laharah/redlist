from pynentry import PynEntry
from getpass import getpass
import logging
import os
import subprocess
import tempfile
import re

from . import config


class UserMessenger(logging.Formatter):
    'convert info logs into tidy user messages'

    def __init__(self, fmt=logging.BASIC_FORMAT, datefmt=None):
        super().__init__(fmt=fmt, datefmt=datefmt)

    def format(self, record):
        if record.levelname != 'INFO':
            return super().format(record)
        message = record.msg % record.args
        if record.name == 'redlist.redsearch':
            return '[REDACTED]: %s' % message
        if record.name == '__main__':
            return message
        if record.name == 'deluge_client.client':
            return ''
        if record.name == 'redlist.deluge':
            return 'Deluge: %s' % message
        return message


def get_user_and_pass(cfg, name=None, overwrite=False, error=None):
    'get the user to put in user/pass and assign it in given config'
    if not name:
        name = cfg.name.title()
    if cfg['username'].get() is None:
        cfg['username'] = input(f'{name} Username: ')
    if cfg['password'].get() is not None and overwrite != True:
        return
    if not config['pinentry'].get():
        cfg['password'] = getpass(f'{name} Password: ')
        return
    with PynEntry() as p:
        p.title = f'{name} Password'
        desc = f'Please enter your password for {name}.'
        p.description = desc
        if error is not None:
            p.error_text = error
        p.prompt = 'password:'
        cfg['password'] = p.get_pin()


def get_spotify_auth_code(auth_url):
    print(
        '\nOpen this url in a web browser to authorize redlist to download your playlists\n'
    )
    print(auth_url)
    print('\n')
    msg = ('After accepting, you will be redirected to a page that does not work. '
           'Paste the url you are redirected to here (it contains your access code).')
    print(msg)
    return input('url: ')


def user_editor(original_data):
    with tempfile.NamedTemporaryFile(delete=False) as tf:
        tf.write(original_data.encode('utf8'))
        tf.flush()
    editor = os.getenv('EDITOR')
    try:
        if editor:
            subprocess.call([editor, tf.name])
        else:
            log.error("You must set the EDITOR environment variable to use this feature.")
    finally:
        with open(tf.name) as f:
            edited = f.read()
        os.unlink(tf.name)
    return edited

def edit_torrent_downloads(downloads):
    prompt = ["#remove any torrentid's you don't want downloaded." '\n']
    for torrent in downloads.values():
        m = '{} - {} [{}][{} {}]: torrentid={}'.format(
            *[torrent[k] for k in ('artist', 'groupName')] +
            [torrent['torrent'][k] for k in 'media format encoding'.split()] +
            [torrent['torrent']['torrentId']])
        prompt.append(m)
    response = user_editor('\n'.join(prompt))
    ids = set(map(int, re.findall('torrentid=(\d+)', response)))
    downloads = {t: v for t, v in downloads.items() if v['torrent']['torrentId'] in ids}
    return downloads
