"""Album-art lookup adapter: search terms in, candidate covers out.

Currently backed by the iTunes Search API (no auth, no extra deps);
swappable for MusicBrainz/Cover Art Archive later. Network calls — always
run these in a thread worker, and check the selection hasn't moved before
applying the result.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass

USER_AGENT = "mediasmith/0.1"

SEARCH_URL = ("https://itunes.apple.com/search"
              "?term={term}&media=music&entity=album&limit={limit}")


@dataclass(frozen=True)
class CoverCandidate:
    url: str
    label: str          # "Artist — Album", for the notification


def search_covers(artist: str, album: str, limit: int = 5) -> list[CoverCandidate]:
    """Cover candidates for an artist/album pair. May raise OSError."""
    term = urllib.parse.quote_plus(f"{artist} {album}".strip())
    url = SEARCH_URL.format(term=term, limit=limit)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=10) as response:
        payload = json.load(response)
    candidates = []
    for result in payload.get("results", []):
        art = result.get("artworkUrl100")
        if not art:
            continue
        candidates.append(CoverCandidate(
            # the CDN serves any size you name in the filename
            url=art.replace("100x100bb", "600x600bb"),
            label=(f"{result.get('artistName', '?')} — "
                   f"{result.get('collectionName', '?')}")))
    return candidates


def fetch_bytes(url: str) -> bytes:
    """Download one candidate's image bytes. May raise OSError."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=15) as response:
        return response.read()
