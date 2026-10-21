"""One listening cycle, expressed only in terms of MCP tool calls.

`tools.call(name, **args)` is either a real MCP client session (agent/run.py)
or an in-process shim (the server's run_listener tool). The pipeline never
touches an API, a file or the sheet directly: that is all the server's job.
"""

import uuid
from datetime import datetime, timezone

from listener_mcp.config import watchlist


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


async def run_cycle(tools, trigger: str = "manual", max_llm_calls: int = 40, log=print) -> dict:
    cfg = watchlist()
    run = {"run_id": uuid.uuid4().hex[:8], "started_utc": _now(), "trigger": trigger}
    lookback = cfg.get("lookback_hours", 168)
    limit = cfg.get("max_per_query", 25)

    # 1. Collect -----------------------------------------------------------
    # HN search is literal and low-volume, so it gets short brand/category terms;
    # Reddit and Bluesky get the full organiser-phrased query list.
    jobs = [("hackernews", q) for q in cfg.get("hackernews_queries", cfg["queries"])]
    jobs += [("reddit", q) for q in cfg["queries"]]
    jobs += [("bluesky", q) for q in cfg["queries"]]
    jobs += [("mastodon", h) for h in cfg.get("mastodon", {}).get("hashtags", [])]

    posts: dict[str, dict] = {}
    errors: dict[str, str] = {}
    dead_sources: set[str] = set()
    for source, q in jobs:
        if source in dead_sources:
            continue
        res = await tools.call("search_source", source=source, query=q, since_hours=lookback, limit=limit)
        if res.get("error"):
            errors.setdefault(source, res["error"])
            # A source that is blocked/unconfigured on its first query will be for the rest.
            if not res["posts"] and (source not in {p["source"] for p in posts.values()}):
                dead_sources.add(source)
            continue
        for p in res["posts"]:
            posts.setdefault(p["id"], p)
    run["fetched"] = len(posts)
    log(f"[collect] {len(posts)} unique posts; source errors: {errors or 'none'}")

    # 2. De-duplicate against every previous run ----------------------------
    fresh_ids = await tools.call("filter_unseen", post_ids=list(posts))
    fresh = [posts[i] for i in fresh_ids]
    run["new"] = len(fresh)
    log(f"[dedupe] {len(fresh)} not seen before")

    # 3. Rules first, best candidates to the LLM, within a per-run budget ---
    scored = []
    for p in fresh:
        s = await tools.call("score_post", post=p)
        scored.append((s["score"], p))
    scored.sort(key=lambda t: -t[0])
    min_keep = cfg.get("min_score_to_keep", 30)
    shortlist = [p for s, p in scored if s >= min_keep]
    run["shortlisted"] = len(shortlist)
    log(f"[rules] {len(shortlist)} shortlisted of {len(fresh)}")

    leads, llm_calls = [], 0
    for p in shortlist:
        use_llm = llm_calls < max_llm_calls
        res = await tools.call("qualify_post", post=p, use_llm=use_llm)
        if res.get("llm") is not None:
            llm_calls += 1
        if res["keep"]:
            leads.append(res["lead"])
    run["llm_calls"] = llm_calls

    # 4. Persist, mark seen, sync ------------------------------------------
    if leads:
        await tools.call("save_leads", leads=leads)
    await tools.call("mark_seen", post_ids=fresh_ids)
    run["kept"] = len(leads)
    for tier in ("Hot", "Warm", "Watch"):
        run[tier.lower()] = sum(1 for l in leads if l["priority"] == tier)
    run["source_errors"] = "; ".join(f"{k}: {v[:400]}" for k, v in errors.items())
    run["finished_utc"] = _now()

    # Log the run before syncing so the sheet's Run log includes this run, then again with the result.
    run["sheet_status"] = "syncing"
    await tools.call("log_run", run=run)
    sheet_status = await tools.call("sync_sheet")
    run["sheet_status"] = sheet_status
    await tools.call("log_run", run=run)
    log(f"[sheet] {sheet_status}")
    log(f"[done] kept {run['kept']} (hot {run['hot']}, warm {run['warm']}, watch {run['watch']}), llm calls {llm_calls}")
    return run
