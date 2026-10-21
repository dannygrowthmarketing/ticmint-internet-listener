"""One listening cycle, expressed only in terms of MCP tool calls.

`tools.call(name, **args)` is either a real MCP client session (agent/run.py)
or an in-process shim (the server's run_listener tool). The pipeline never
touches an API, a file or the sheet directly: that is all the server's job.

Run accounting (what each number in data/runs.csv means):
  discovered    unique posts returned by the sources this run
  new           of those, posts never processed before (these are scored)
  shortlisted   new posts whose rule score reached min_score_to_keep
  qualified     leads written to the sheet this run (hot + warm + watch)
  status        ok | partial (any source call or post failed) | failed (no source worked)
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
    calls: dict[str, list[int]] = {}  # source -> [ok calls, failed calls]
    skipped: set[str] = set()
    dead_sources: set[str] = set()
    crossposts: set = set()
    for source, q in jobs:
        if source in dead_sources:
            continue
        res = await tools.call("search_source", source=source, query=q, since_hours=lookback, limit=limit)
        tally = calls.setdefault(source, [0, 0])
        if res.get("error"):
            if "skipped" in res["error"]:
                skipped.add(source)  # not configured: not a failure
                dead_sources.add(source)
                continue
            tally[1] += 1
            errors.setdefault(source, res["error"])
            # A source that fails its first query without ever succeeding is blocked for this run.
            if tally[0] == 0:
                dead_sources.add(source)
            continue
        tally[0] += 1
        for p in res["posts"]:
            # Cross-posts: same author + title in several subreddits count once.
            key = (p["source"], p.get("author"), (p.get("title") or "").strip().lower()) if p.get("title") else p["id"]
            if key in crossposts:
                continue
            crossposts.add(key)
            posts.setdefault(p["id"], p)
    ok_sources = sorted(s for s, (ok, _) in calls.items() if ok)
    failed_sources = sorted(s for s in errors if s not in ok_sources)
    run["sources_ok"] = " ".join(ok_sources)
    run["sources_failed"] = " ".join(failed_sources)
    run["sources_skipped"] = " ".join(sorted(skipped))
    run["discovered"] = len(posts)
    log(f"[collect] {len(posts)} unique posts; ok: {ok_sources}; failed: {failed_sources}; skipped: {sorted(skipped)}")

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

    leads, llm_calls, llm_errors, proc_errors, done_ids = [], 0, 0, 0, set()
    for p in shortlist:
        use_llm = llm_calls < max_llm_calls
        try:
            res = await tools.call("qualify_post", post=p, use_llm=use_llm)
        except Exception as e:  # one bad post must not cost the run its other results
            proc_errors += 1
            log(f"[error] qualify_post {p['id']}: {str(e)[:160]}")
            continue
        done_ids.add(p["id"])
        if res.get("llm") is not None:
            llm_calls += 1
            if res["llm"].get("error"):
                llm_errors += 1
        if res["keep"]:
            leads.append(res["lead"])
    run["llm_calls"] = llm_calls
    run["llm_errors"] = llm_errors
    run["processing_errors"] = proc_errors

    # 4. Persist, mark seen, sync ------------------------------------------
    if leads:
        await tools.call("save_leads", leads=leads)
    # Posts that errored stay unseen so the next run retries them.
    below_bar = {p["id"] for p in fresh} - {p["id"] for p in shortlist}
    await tools.call("mark_seen", post_ids=sorted(below_bar | done_ids))
    run["qualified"] = len(leads)
    for tier in ("Hot", "Warm", "Watch"):
        run[tier.lower()] = sum(1 for l in leads if l["priority"] == tier)
    run["source_errors"] = "; ".join(f"{k}: {v[:300]}" for k, v in errors.items())
    # Any source error makes the run partial, even if that source answered other queries.
    run["status"] = "failed" if not ok_sources else ("partial" if errors or proc_errors else "ok")
    run["finished_utc"] = _now()

    # Log the run before syncing so the sheet's Run log includes this run, then again with the result.
    run["sheet_status"] = "syncing"
    await tools.call("log_run", run=run)
    sheet_status = await tools.call("sync_sheet")
    run["sheet_status"] = sheet_status
    await tools.call("log_run", run=run)
    await tools.call("write_summary")
    log(f"[sheet] {sheet_status}")
    log(f"[done] {run['status']}: qualified {run['qualified']} (hot {run['hot']}, warm {run['warm']}, "
        f"watch {run['watch']}), llm calls {llm_calls} ({llm_errors} errors)")
    return run
