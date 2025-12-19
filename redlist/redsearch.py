import re
import logging
import html

from beets.autotag import distance as beets_tagger

from .redapi import get_api
from . import matching
from . import config

log = logging.getLogger(__name__)
log.setLevel("INFO")


def make_search_dict(track_info):
    "Construct the fields necessary for searching redacted for a given track"
    d = {}
    d["filelist"] = track_info.title
    if track_info.artist and track_info.artist.lower not in matching.VA_ARTISTS:
        d["artistname"] = track_info.artist
    if track_info.album:
        d["groupname"] = track_info.album
    if not d.get("artistname") and not d.get("groupname"):
        raise ValueError("Not Enough fields")

    return d


async def find_album(track_info, restrict_album=True):
    api = await get_api()
    search_dict = make_search_dict(track_info)
    res = await api.request("browse", **search_dict)
    if not res["status"] == "success":
        log.error("Error retreving data from redacted: %s", res)
        raise RuntimeError
    try:
        res = res["response"]
    except KeyError:
        log.critical('no "response" field in server response')
        log.critical("%s", res)
        raise
    if len(res["results"]) == 1:
        log.info("Hit on first try for %s.", track_info)
        group = res["results"][0]
        prefs = [
            re.compile(p, re.I) for p in config["redacted"]["format_preferences"].get()
        ]
        prefered = choose_prefered_torrent(group, prefs)
        if prefered is None:
            log.info(
                "Could not find a torrent for %s that fits your current preferences.",
                track_info,
            )
        del group["torrents"]
        group["torrent"] = prefered
        group["groupName"] = html.unescape(group["groupName"])
        return group
    elif len(res["results"]) > 1:
        log.info(
            'Found %d canidates for "%s", searching them...',
            len(res["results"]),
            track_info,
        )
        hit = await search_torrent_groups(track_info, res["results"], api)
        if hit:
            return hit

    # relax the track requirement
    log.info("widening search for %s...", track_info)
    del search_dict["filelist"]
    res = await api.request("browse", **search_dict)
    try:
        res = res["response"]
    except KeyError:
        log.critical('no "response" field in server response')
        log.critical("%s", res)
        raise
    hit = await search_torrent_groups(track_info, res["results"], api)
    if hit or restrict_album:
        return hit
    log.info(
        "Could not find %s, Checking other albums by %s.",
        track_info.album,
        track_info.artist,
    )
    search_dict = make_search_dict(track_info)
    try:
        del search_dict["groupname"]
    except KeyError:
        pass
    res = await api.request("browse", **search_dict)
    try:
        res = res["response"]
    except KeyError:
        log.critical('no "response" field in server response')
        log.critical("%s", res)
        raise
    hit = await search_torrent_groups(
        track_info, res["results"], api, restrict_album=False
    )
    if not hit:
        if "," in track_info.artist:
            track_info._clean_feat()
            log.info("Suspect multi-artist track, re-searching with %s", track_info)
            return await find_album(track_info, restrict_album)
        log.info("Could not automatically find torrent for %s. Giving up.", track_info)
    return hit


async def search_torrent_groups(track_info, torrent_groups, api, restrict_album=True):
    "search list of torrent groups for a given track and return a torrent for it"
    group_canidates = {}
    # score them by how likely they are to match the given track
    for index, group in enumerate(torrent_groups):
        group["groupName"] = html.unescape(group["groupName"])  # clean album html
        group_artist = matching.match_artist(track_info.artist, get_artists(group))
        group["artist_match"] = group_artist
        if not group_artist:
            continue
        dist = beets_tagger.Distance()
        dist.add_string("artist", track_info.artist, group_artist)
        if track_info.album:
            dist.add_string("album", track_info.album, group["groupName"])
        if dist > 0.5:
            log.info(
                "distance of %f is too high for %s, skipping to next",
                float(dist),
                group["groupName"],
            )
            continue
        group_canidates[index] = dist
    # Search files of each torrentGroup in descending likelyhood and return
    # first to be a good match
    prefs = [
        re.compile(p, re.I) for p in config["redacted"]["format_preferences"].get()
    ]
    for group in sorted(group_canidates, key=lambda g: group_canidates[g]):
        group = torrent_groups[group]
        prefered = choose_prefered_torrent(group, prefs)
        if prefered is None:
            log.info(
                "Could not find a torrent for %s that fits your current prefrences",
                group["groupName"],
            )
            return None
        log.info(
            'Considering %s: id=%s for "%s"',
            group["groupName"],
            prefered["torrentId"],
            track_info.title,
        )
        full_torrent_data = await api.request("torrent", id=prefered["torrentId"])
        full_torrent_data = full_torrent_data["response"]
        torrent_data = full_torrent_data["torrent"]
        for track_canidate in torrent_data["fileList"].split("|||"):
            original_canidate = track_canidate
            match = re.match(
                r"(.+)\.(mp3|flac|ogg|mp4|m4a|ac3|dts){.*$", track_canidate
            )
            if not match:
                continue
            track_canidate = match.group(1).lower()
            # Clean artist from filename
            track_canidate = re.sub(
                r"^.*{}[\W\s]+".format(track_info.artist),
                "",
                track_canidate,
                flags=re.I,
            )
            # Clean useless parenteses from filename
            if not track_info.title.endswith(")"):
                track_canidate = re.sub(r"\(.*\)$", "", track_canidate)
            # Clean track numbers from filename
            track_canidate = re.sub(r"^\d+[\W\s]+", "", track_canidate)
            try:
                canidate_info = matching.TrackInfo(
                    title=track_canidate,
                    artist=group["artist_match"],
                    album=group["groupName"],
                )
            except ValueError:
                log.error(
                    "could not make TrackInfo for %s from torrent %s",
                    original_canidate,
                    prefered["torrentId"],
                )
                continue

            dist = matching.track_distance(
                track_info, canidate_info, restrict_album=restrict_album
            )
            if dist <= 0.3:
                log.info(
                    'Found torrent for "%s" with %.1f%% confidence.',
                    track_info,
                    (1 - dist) * 100,
                )
                group["torrent"] = prefered
                del group["torrents"]
                return group
    log.info("Unable to find torrent for %s", track_info)
    return None


def get_artists(torrent_group):
    "get a set of artists from a torrent_group"
    artists = {torrent_group["artist"].lower()}
    for t in torrent_group["torrents"]:
        for a in t["artists"]:
            artists.add(a["name"].lower())
    try:
        for key, art in torrent_group["musicInfo"].items():
            for a in art:
                artists.add(a["name"].lower())
    except KeyError:
        pass
    return artists - set(matching.VA_ARTISTS)


def choose_prefered_torrent(torrent_group, prefs):
    ordering = []
    for t in torrent_group["torrents"]:
        tmp = []
        try:
            fmt = " ".join(t[k] for k in ["format", "encoding", "media"])
        except KeyError:
            continue
        tmp.append(get_priority_tuple(fmt, prefs))
        tmp.append(-t["snatches"])
        tmp.append(-t["seeders"])
        ordering.append((tuple(tmp), t))
    try:
        return min(ordering, key=lambda x: x[0])[1]
    except ValueError:
        return None


def get_priority_tuple(value, prefs):
    tmp = []
    for p in prefs:
        if p.match(value):
            tmp.append(0)
        else:
            tmp.append(1)
    return tuple(tmp)
