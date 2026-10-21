"""Hacker News via the free Algolia API. No key, generous limits (~10k req/hour)."""

from datetime import datetime, timezone

from ..http import get_json
from . import clean_html

BASE = "https://hn.algolia.com/api/v1"


def search(query: str, since_ts: int, limit: int = 25) -> list[dict]:
    data = get_json(
        f"{BASE}/search_by_date",
        params={
            "query": query,
            "tags": "(story,comment)",
            "numericFilters": f"created_at_i>{since_ts}",
            "hitsPerPage": limit,
        },
    )
    posts = []
    for h in data.get("hits", []):
        oid = h.get("objectID")
        is_comment = "comment" in (h.get("_tags") or [])
        title = h.get("title") or h.get("story_title") or ""
        text = clean_html(h.get("comment_text") or h.get("story_text") or "")
        if not text and not is_comment:
            text = title
        posts.append(
            {
                "id": f"hackernews:{oid}",
                "source": "hackernews",
                "url": f"https://news.ycombinator.com/item?id={oid}",
                "author": h.get("author") or "",
                "author_url": f"https://news.ycombinator.com/user?id={h.get('author')}",
                "title": title,
                "text": text,
                "created_utc": datetime.fromtimestamp(h.get("created_at_i", 0), timezone.utc).isoformat(),
                "community": h.get("story_title") or "Hacker News",
                "raw_score": h.get("points") or 0,
            }
        )
    return posts


def profile(username: str) -> dict:
    u = get_json(f"{BASE}/users/{username}")
    about = clean_html(u.get("about"))
    return {
        "author": username,
        "karma": u.get("karma"),
        "account_created": u.get("created_at"),
        "bio": about[:400],
        "links": _links(about),
    }


def _links(text: str) -> list[str]:
    return [w.strip(".,)") for w in text.split() if w.startswith(("http://", "https://"))][:5]
