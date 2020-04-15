# [RED]list
### Convert Spotify playlists to local m3u's and fill the gaps!

[RED]list is a tool to glue together Spotify, [Beets](https://beets.io), and [REDACTED].

## Installation
[RED]list requires python 3.6+. 

[RED]list also expects you to have a populated [Beets](https://beets.io)
library. It will use it to find and match your music files.

To install simply run:

`pip install git+https://github.com/Laharah/redlist.git`

## Usage
```
usage: redlist [options] <playlist>...

Save spotify playlists as m3u and fill in missing songs from [REDACTED]

positional arguments:
  playlist

optional arguments:
  -h, --help            show this help message and exit
  --config CONFIGFILE   Path to configuration file.
  --beets-library BEETS_LIBRARY
                        The beets library to use
  --downloads TORRENT_DIRECTORY
                        Directory new torrents will be saved to (exclusive
                        with --deluge)
  -y                    Assume yes to all queries and do not prompt.
  --deluge              Load torrents directly into deluge
  --deluge-server DELUGE.HOST
                        address of deluge server, (Default: localhost)
  --deluge-port DELUGE.PORT
                        Port of deluge server, (Default: 58846)
  --restrict-album      Only match tracks if they come from the same album.
  --use-fl-tokens       Use freeleach tokens (note: slows torrent download
                        SIGNIFICANTLY).
  --show-config         Dump the current configuration values and exit.
  --overwrite-m3u       if argument is an m3u, overwrite it instead of
                        outputting to playlist dir.
  --log-level {CRITICAL,ERROR,WARNING,INFO,DEBUG}
                        Set the log level. (Default: INFO)
```

Where playlist is a Spotify playlist (uri or url), an m3u, or a csv file (artist, title, album). 

[RED]list will use your local beets library (located automatically) and do it's best to
match tracks from the playlist to tracks in your library and write the results to m3u. Any
missing tracks can then be automatically searched for on [REDACTED] and torrents will be
downloaded or, if you use deluge, added to a running deluge instance. 

[RED]list can then be re-run any time on the created m3u playlist to re-match any
previously missing files.


## Security

[RED]list does not store your password (unless you enter them into your config). It does
however store a cookie from [REDACTED] to keep you logged in. This can be disabled in your
configuration file.

The first time you give [RED]list a Spotify url, you will have to grant [RED]list access
to read your playlists, even if the playlist is public. This involves visiting a Spotify
link [RED]list gives you and pasting back the (broken) URL Spotify sends you to. This URL
contains an access code for [RED]list to poll the Spotify API. It does not grant [RED]list
permissions to read anything but your playlists. [RED]list stores this api token in the
config directory and refreshes and re-uses it for future use.

## Configuration

[RED]list has several configuration options. The defaults are shown here:
``` yaml
beets_library: null  		# Usually found automatically
pinentry: yes  				# Use Pinentry to securely get passwords
enable_deluge: no 			# Load downloaded torrents into deluge
torrent_directory: null 	# Directory save downloaded torrents
m3u_directory: null 		# Directory to save processed m3u playlists
restrict_album: no 			# Only allow tracks to match if they are from the same album
overwrite_m3u: no 			# If argument is m3u, overwrite it instead of saving to m3u_dir

redacted:
  username: null
  password: null
  save_cookies: yes
  use_fl_tokens: no  	# Use freeleach tokens 
  format_preferences:  	# "Format Encoding Media"
    - 'MP3 V0'
    - 'MP3 320'
    - 'FLAC .*'
    - 'MP3 .*'
    - '.*'

deluge:
  host: 'localhost'
  port: 58846
  username: null
  password: null
  add_paused: no
```

Any of the above settings can be overridden by settings from your own configuration file.
To configure [RED]list, you create a file called `config.yaml`. The location of the file
depends on your platform:

* On Unix-like OSes: `~/.config/redlist/config.yaml`.
* On Windows: `%APPDATA%\redlist\config.yaml`.
* On OS X: `~/Library/Application Support/redlist/config.yaml`.

You can use the `--show-config` option at any time to see what your current
configuration looks like. You may also override your config file from the
command line with the `--config` option.

### Example
The config uses YAML syntax. An example config might look like so:
``` yaml
enable_deluge: yes
deluge:
    host: example.com
redacted:
    format_preferences:
        - 'FLAC .* (CD|Vinyl)'
        - 'FLAC (lossless|24bit Lossless)'
        - 'MP3 (V0|320)'
        - '.*'
```

This will set [RED]list to automatically add torrents to a deluge server running at
example.com. It also specifies the preferred torrent formats. The preferences are listed
as regex strings in the preferred order. The regex strings are matched against a string of
the format `"format encoding media"` eg:(`MP3 V0 (VBR) Web`). The above regex strings can
be interpreted as such:

- `'FLAC .* (CD|Vinyl)'`: Any FLAC from CD or vinyl media.
- `'FLAC (lossless|24bit Lossless)'`: otherwise, a lossless or 24bit lossless FLAC from any media
- `'MP3 (V0|320)'`: otherwise, An MP3 encoded at either V0 or 320, from any media
- `'.*'`: If none of the above can be found, accept whatever is available

*note: the regex strings are not case sensitive*

[RED]list will only choose torrents that match at least one of your given preferences.
This is why you usually want to end your preferences with a permissive rule.

