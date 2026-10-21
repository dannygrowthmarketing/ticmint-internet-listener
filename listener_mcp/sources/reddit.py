"""Reddit search.

Preferred: the official OAuth API with a free "script" app (REDDIT_CLIENT_ID /
REDDIT_CLIENT_SECRET), 100 requests/minute. Fallback: the public .json
endpoints, which Reddit increasingly blocks from cloud IPs (GitHub Actions
included). When both fail the agent logs it and the other sources still run.
"""

import os
import time
from datetime import datetime, timezone

from ..http import SourceError, get_json
from . import clean_html

_token: tuple[str, float] | None = None


def _auth_headers() -> tuple[str, dict]:
    """Return (base_url, headers). Uses OAuth when credentials exist."""
    global _token
    cid, secret = os.getenv("REDDIT_CLIENT_ID"), os.getenv("REDDIT_CLIENT_SECRET")
    if not (cid and secret):
        return "https://www.reddit.com", {}
    if _token is None or _token[1] < time.time() + 60:
        data = get_json(
            "https://www.reddit.com/api/v1/access_token",
            method="POST",
            data={"grant_type": "client_credentials"},
            auth=(cid, secret),
        )
        _token = (data["access_token"], time.time() + float(data.get("expires_in", 3600)))
    return "https://oauth.reddit.com", {"Authorization": f"bearer {_token[0]}"}


def search(query: str, since_ts: int, limit: int = 25, subreddits: list[str] | None = None) -> list[dict]:
    base, headers = _auth_headers()
    suffix = "" if base.startswith("https://oauth") else ".json"
    # Site-wide search, plus one multireddit search ("r/a+b+c") over organiser-heavy
    # communities, so each query costs two requests, not one per subreddit.
    targets = ["search"] + (["r/" + "+".join(subreddits) + "/search"] if subreddits else [])
    posts: dict[str, dict] = {}
    errors = []
    for path in targets:
        params = {"q": query, "sort": "new", "t": "week", "limit": limit, "type": "link"}
        if path != "search":
            params["restrict_sr"] = "1"
        try:
            data = get_json(f"{base}/{path}{suffix}", params=params, headers=headers, retries=1)
        except SourceError as e:
            errors.append(str(e))
            continue
        for child in data.get("data", {}).get("children", []):
            p = child.get("data", {})
            if p.get("created_utc", 0) < since_ts:
                continue
            pid = f"reddit:{p.get('id')}"
            posts[pid] = {
                "id": pid,
                "source": "reddit",
                "url": "https://www.reddit.com" + p.get("permalink", ""),
                "author": p.get("author") or "",
                "author_url": f"https://www.reddit.com/user/{p.get('author')}",
                "title": p.get("title") or "",
                "text": clean_html(p.get("selftext") or ""),
                "created_utc": datetime.fromtimestamp(p.get("created_utc", 0), timezone.utc).isoformat(),
                "community": f"r/{p.get('subreddit')}",
                "raw_score": p.get("score") or 0,
            }
        # Subreddit searches are extra; if site-wide search is blocked the rest will be too.
        if errors and path == "search":
            break
    if not posts and errors:
        # Reddit blocks unauthenticated requests from most cloud IPs (GitHub Actions
        # included). Fall back to PullPush, a free public archive of Reddit.
        fallbacks = []
        for fn in (_pullpush, _rss):
            try:
                return fn(query, since_ts, limit)
            except SourceError as e:
                fallbacks.append(f"{fn.__name__.strip('_')}: {e}")
        raise SourceError("; ".join([errors[0]] + fallbacks))
    return list(posts.values())


def _pullpush(query: str, since_ts: int, limit: int) -> list[dict]:
    posts = []
    for kind in ("submission", "comment"):
        data = get_json(f"https://api.pullpush.io/reddit/search/{kind}/",
                        params={"q": query, "after": since_ts, "size": limit, "sort": "desc", "sort_type": "created_utc"},
                        retries=1)
        for p in data.get("data", []):
            pid = f"reddit:{p.get('id')}"
            link = p.get("permalink") or f"/comments/{(p.get('link_id') or '').removeprefix('t3_')}/_/{p.get('id')}"
            posts.append({
                "id": pid,
                "source": "reddit",
                "url": link if link.startswith("http") else "https://www.reddit.com" + link,
                "author": p.get("author") or "",
                "author_url": f"https://www.reddit.com/user/{p.get('author')}",
                "title": p.get("title") or "",
                "text": clean_html(p.get("selftext") or p.get("body") or ""),
                "created_utc": datetime.fromtimestamp(int(p.get("created_utc", 0)), timezone.utc).isoformat(),
                "community": f"r/{p.get('subreddit')}",
                "raw_score": p.get("score") or 0,
            })
    return posts


def profile(username: str) -> dict:
    base, headers = _auth_headers()
    suffix = "" if base.startswith("https://oauth") else ".json"
    d = get_json(f"{base}/user/{username}/about{suffix}", headers=headers).get("data", {})
    sub = d.get("subreddit") or {}
    return {
        "author": username,
        "karma": (d.get("link_karma") or 0) + (d.get("comment_karma") or 0),
        "account_created": datetime.fromtimestamp(d.get("created_utc", 0), timezone.utc).date().isoformat()
        if d.get("created_utc")
        else None,
        "bio": (sub.get("public_description") or "")[:400],
        "links": [],
    }


def _rss(query: str, since_ts: int, limit: int) -> list[dict]:
    """Last resort: Reddit's Atom search feed (no selftext score, but title + body summary)."""
    import xml.etree.ElementTree as ET

    from ..http import client

    r = client().get("https://www.reddit.com/search.rss", params={"q": query, "sort": "new", "limit": limit},
                     headers={"Accept": "application/atom+xml"})
    if r.status_code != 200:
        raise SourceError(f"https://www.reddit.com/search.rss -> HTTP {r.status_code}")
    ns = {"a": "http://www.w3.org/2005/Atom"}
    posts = []
    for e in ET.fromstring(r.text).findall("a:entry", ns):
        updated = datetime.fromisoformat(e.findtext("a:updated", "", ns).replace("Z", "+00:00"))
        if updated.timestamp() < since_ts:
            continue
        author = (e.findtext("a:author/a:name", "", ns) or "").removeprefix("/u/")
        link = e.find("a:link", ns).get("href")
        cat = e.find("a:category", ns)
        posts.append({
            "id": "reddit:" + e.findtext("a:id", "", ns).removeprefix("t3_"),
            "source": "reddit", "url": link, "author": author,
            "author_url": f"https://www.reddit.com/user/{author}",
            "title": e.findtext("a:title", "", ns), "text": clean_html(e.findtext("a:content", "", ns)),
            "created_utc": updated.isoformat(),
            "community": f"r/{cat.get('term')}" if cat is not None else "reddit", "raw_score": 0,
        })
    return posts
