"""Mastodon public hashtag timelines. No key needed. Full-text status search
requires a login on most instances, so we read hashtags and filter locally
for the query terms."""

from datetime import datetime

from ..http import get_json
from . import clean_html


def search(instance: str, hashtag: str, since_iso: str, query: str | None = None, limit: int = 40) -> list[dict]:
    data = get_json(f"{instance.rstrip('/')}/api/v1/timelines/tag/{hashtag}", params={"limit": min(limit, 40)})
    since = datetime.fromisoformat(since_iso.replace("Z", "+00:00"))
    terms = [t for t in (query or "").lower().split() if len(t) > 2]
    posts = []
    for s in data:
        created = datetime.fromisoformat(s["created_at"].replace("Z", "+00:00"))
        if created < since:
            continue
        text = clean_html(s.get("content"))
        if terms and not all(t in text.lower() for t in terms):
            continue
        acct = s.get("account", {})
        posts.append(
            {
                "id": f"mastodon:{s.get('uri')}",
                "source": "mastodon",
                "url": s.get("url") or s.get("uri"),
                "author": acct.get("acct", ""),
                "author_url": acct.get("url", ""),
                "title": "",
                "text": text,
                "created_utc": created.isoformat(),
                "community": f"#{hashtag}",
                "raw_score": s.get("favourites_count", 0),
                # Mastodon ships the profile inline, so enrichment is free.
                "_profile": {
                    "author": acct.get("acct", ""),
                    "display_name": acct.get("display_name"),
                    "followers": acct.get("followers_count"),
                    "bio": clean_html(acct.get("note"))[:400],
                    "links": [clean_html(f.get("value")) for f in acct.get("fields", []) if "http" in (f.get("value") or "")][:3],
                },
            }
        )
    return posts
