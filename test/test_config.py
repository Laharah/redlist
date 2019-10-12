import re

import pytest

from redlist import config


def test_default_config():
    print(config['redacted']['username'])
    assert config['redacted']['username'].get() is None


def test_redaction():
    dump = config.dump(redact=True)
    count = 0
    for line in dump.splitlines():
        if re.search(r'(username|password)', line):
            assert line.endswith('REDACTED')
            count += 1
    assert count == 4
