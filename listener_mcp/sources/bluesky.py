"""Bluesky post search via the AT Protocol XRPC API.

searchPosts needs an authenticated session (free: any account + an app
password, BSKY_HANDLE / BSKY_APP_PASSWORD). Without credentials the source is
skipped rather than failing the run.
"""

import os
from urllib.parse import quote

from ..http import SourceError, get_json

PDS = "https://bsky.social/xrpc"
_session: dict | None = None


def enabled() -> bool:
    return bool(os.getenv("BSKY_HANDLE") and os.getenv("BSKY_APP_PASSWORD"))


def _headers() -> dict:
    global _session
    if _session is None:
        if not enabled():
            raise SourceError("bluesky: BSKY_HANDLE/BSKY_APP_PASSWORD not set")
        _session = _create_session()
    return {"Authorization": f"Bearer {_session['accessJwt']}"}


def _create_session() -> dict:
    from ..http import client

    r = client().post(
        f"{PDS}/com.atproto.server.createSession",
        json={"identifier": os.environ["BSKY_HANDLE"], "password": os.environ["BSKY_APP_PASSWORD"]},
    )
    if r.status_code != 200:
        raise SourceError(f"bluesky login -> HTTP {r.status_code}")
    return r.json()


def search(query: str, since_iso: str, limit: int = 25) -> list[dict]:
    data = get_json(
        f"{PDS}/app.bsky.feed.searchPosts",
        params={"q": query, "sort": "latest", "since": since_iso, "limit": min(limit, 100)},
        headers=_headers(),
    )
    posts = []
    for p in data.get("posts", []):
        author = p.get("author", {})
        handle = author.get("handle", "")
        rkey = p.get("uri", "").rsplit("/", 1)[-1]
        rec = p.get("record", {})
        posts.append(
            {
                "id": f"bluesky:{p.get('cid')}",
                "source": "bluesky",
                "url": f"https://bsky.app/profile/{handle}/post/{rkey}",
                "author": handle,
                "author_url": f"https://bsky.app/profile/{handle}",
                "title": "",
                "text": rec.get("text", ""),
                "created_utc": rec.get("createdAt", ""),
                "community": "Bluesky",
                "raw_score": p.get("likeCount", 0),
            }
        )
    return posts


def profile(handle: str) -> dict:
    d = get_json(f"{PDS}/app.bsky.actor.getProfile", params={"actor": quote(handle)}, headers=_headers())
    return {
        "author": handle,
        "display_name": d.get("displayName"),
        "followers": d.get("followersCount"),
        "bio": (d.get("description") or "")[:400],
        "links": [],
    }
