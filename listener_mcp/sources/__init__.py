"""Source adapters. Each returns a list of normalised Post dicts.

A Post is a plain dict so it can cross the MCP boundary as JSON unchanged:

    id            "<source>:<native id>"  (stable, used for de-duplication)
    source        hackernews | reddit | bluesky | mastodon
    url           permalink to the post/comment
    author        handle on that platform
    author_url    profile link
    title         thread title (may be empty for comments)
    text          body text, HTML stripped
    created_utc   ISO-8601
    community     subreddit / story title / hashtag, whatever gives context
    raw_score     upvotes / points / likes, if the platform exposes it
"""

import html
import re

_TAG = re.compile(r"<[^>]+>")


def clean_html(s: str | None) -> str:
    if not s:
        return ""
    s = s.replace("<p>", "\n").replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
    return html.unescape(_TAG.sub("", s)).strip()
