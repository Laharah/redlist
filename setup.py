from setuptools import setup

setup(
    name='redlist',
    version='0.1.3',
    url='',
    license='MIT',
    author='laharah',
    author_email='laharah22+rl@gmail.com',
    description='Fill the gaps in a library with redacted',
    packages=['redlist'],
    include_package_data=True,
    setup_requires=['pytest-runner'],
    install_requires=[
        'aiohttp[speedups]',
        'beets',
        'python-Levenshtein',
        'humanize',
        'confuse',
        'pynentry',
        'deluge_client',
        'cryptography',
    ],
    tests_require=[
        'pytest >= 2.8.7',
        'pytest-asyncio',
        'mock >= 1.3.0',
        'fuzzywuzzy',
        'httpretty >= 0.8.14',
    ],
    entry_points={
        'console_scripts': [
            'redlist = redlist.__main__:entry_point',
            ]
    }

)
