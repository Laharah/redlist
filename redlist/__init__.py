import confuse
import pynentry
import logging

logging.basicConfig()
log = logging.getLogger(__name__)


config = confuse.LazyConfig('redlist', __name__)

sensitive = [
    config['deluge']['username'],
    config['deluge']['password'],
    config['redacted']['username'],
    config['redacted']['password'],
]

for key in sensitive:
    key.redact = True

# test for pinentry
try:
    p = pynentry.PynEntry()
except FileNotFoundError:
    log.error('program pinentry could not be found in path.')
    config['pinentry'] = False
except OSError:
    log.debug('Probably not a tty')
    config['pinentry'] = False
else:
    p.close()
