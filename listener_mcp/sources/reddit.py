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
        try:
            return _pullpush(query, since_ts, limit)
        except SourceError as e:
            raise SourceError(f"{errors[0]}; pullpush fallback: {e}")
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
