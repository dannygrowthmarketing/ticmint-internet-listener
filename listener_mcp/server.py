"""Ticmint Listener MCP server.

Every piece of I/O and judgment in the pipeline is a tool on this server:
fetching from the four sources, de-duplication, rule scoring, LLM
qualification, author enrichment, persistence, and the Google Sheets sync.
The scheduled agent (agent/run.py) is a thin MCP client that calls these
tools in order. The same server plugs into Claude Desktop / Claude Code,
so a person can ask "who complained about Eventbrite payouts in the UK this
week?" against the same data the schedule writes.

Run:  python -m listener_mcp.server        (stdio transport)
"""

import os
import re
from datetime import datetime, timedelta, timezone

from mcp.server.fastmcp import FastMCP

from . import llm, scoring, sheets, store
from .config import watchlist
from .http import SourceError
from .sources import bluesky, hackernews, mastodon, reddit

mcp = FastMCP(
    "ticmint-listener",
    instructions=(
        "Finds event organisers on Hacker News, Reddit, Bluesky and Mastodon who are frustrated with their "
        "ticketing platform, qualifies them, and keeps the results in data/leads.csv and a Google Sheet. "
        "Use query_leads / lead_stats to answer questions; use search_source + qualify_post to investigate "
        "something new; run_listener for a full cycle."
    ),
)

SOURCES = ("hackernews", "reddit", "bluesky", "mastodon")


def _since(hours: float) -> datetime:
    return datetime.now(timezone.utc) - timedelta(hours=hours)


# --------------------------------------------------------------------- collect

@mcp.tool()
def search_source(source: str, query: str, since_hours: float = 168, limit: int = 25) -> dict:
    """Search one source for recent public posts matching `query`.

    source: hackernews | reddit | bluesky | mastodon (for mastodon, `query` is a hashtag without '#').
    Returns {"posts": [...], "error": str|None}. Errors are returned, not raised, so one
    blocked source never stops a run."""
    cfg = watchlist()
    since = _since(since_hours)
    if os.getenv("LISTENER_FIXTURES"):  # offline test mode, see tests/
        import json, pathlib
        fx = json.loads(pathlib.Path(os.environ["LISTENER_FIXTURES"]).read_text())
        return {"posts": [p for p in fx if p["source"] == source and query in p.get("_queries", [query])], "error": None}
    try:
        if source == "hackernews":
            posts = hackernews.search(query, int(since.timestamp()), limit)
        elif source == "reddit":
            posts = reddit.search(query, int(since.timestamp()), limit, cfg.get("reddit", {}).get("subreddits"))
        elif source == "bluesky":
            if not bluesky.enabled():
                return {"posts": [], "error": "bluesky skipped: no credentials"}
            posts = bluesky.search(query, since.isoformat().replace("+00:00", "Z"), limit)
        elif source == "mastodon":
            posts = mastodon.search(cfg["mastodon"]["instance"], query.lstrip("#"), since.isoformat(), None, limit)
        else:
            return {"posts": [], "error": f"unknown source {source}"}
    except SourceError as e:
        return {"posts": [], "error": str(e)}
    return {"posts": posts, "error": None}


@mcp.tool()
def filter_unseen(post_ids: list[str]) -> list[str]:
    """Return only the ids this listener has never processed before."""
    seen = store.load_seen()
    return [i for i in dict.fromkeys(post_ids) if i not in seen]


@mcp.tool()
def mark_seen(post_ids: list[str]) -> int:
    """Record ids as processed so later runs skip them. Returns the total seen count."""
    seen = store.load_seen() | set(post_ids)
    store.save_seen(seen)
    return len(seen)


# --------------------------------------------------------------------- judge

@mcp.tool()
def score_post(post: dict) -> dict:
    """Rule-based score (0-100) with the features that produced it. Deterministic and free."""
    return scoring.score(post, watchlist()["competitors"])


@mcp.tool()
def enrich_author(source: str, author: str) -> dict:
    """Public profile context for a post's author: karma/followers, account age, bio, links.
    Used to judge whether the person is a real, active organiser worth contacting."""
    try:
        if source == "hackernews":
            return hackernews.profile(author)
        if source == "reddit":
            return reddit.profile(author)
        if source == "bluesky":
            return bluesky.profile(author)
    except SourceError as e:
        return {"author": author, "error": str(e)}
    return {"author": author, "error": f"no profile lookup for {source}"}


@mcp.tool()
def qualify_post(post: dict, use_llm: bool = True) -> dict:
    """Full qualification of one post: rules -> author enrichment -> (if shortlisted) LLM with
    grounding check -> a sheet-ready lead row carrying the evidence behind every judgment.

    Returns {"keep": bool, "lead": {...} | None, "rule_score": int, "llm": {...} | None, "reason": str}."""
    cfg = watchlist()
    min_keep = cfg.get("min_score_to_keep", 30)
    feats = scoring.score(post, cfg["competitors"])
    if feats["score"] < min_keep:
        return {"keep": False, "lead": None, "rule_score": feats["score"], "llm": None,
                "reason": f"rules {feats['score_explanation']}"}

    # Enrich before the final score so identity confidence counts.
    if not post.get("_profile") and post.get("author"):
        prof = enrich_author(post["source"], post["author"])
        if not prof.get("error"):
            post = {**post, "_profile": prof}
            feats = scoring.score(post, cfg["competitors"])
    profile = post.get("_profile") or {}

    verdict = None
    if use_llm:
        try:
            verdict = llm.classify(post)
        except Exception as e:  # network error, timeout, provider outage: never lose the post
            verdict = {"error": f"{type(e).__name__}: {str(e)[:120]}"}
    final, scored_by = feats["score"], "rules"
    why, opener = feats["why"], scoring.opener(feats)
    pain = feats["pain_categories"][0] if feats["pain_categories"] else ""
    intent = "switching_or_evaluating" if feats["switching_intent"] else ""
    competitor = ", ".join(feats["competitors"])
    explanation = feats["score_explanation"]
    llm_agrees = False

    if verdict and not verdict.get("error"):
        if not verdict["grounded"]:
            # Ungrounded answer: ignore the model, keep the rule score, flag it for review.
            scored_by = "rules (LLM rejected: " + "; ".join(verdict["grounding_problems"]) + ")"
        elif not verdict.get("is_organiser"):
            return {"keep": False, "lead": None, "rule_score": feats["score"], "llm": verdict,
                    "reason": "LLM: author is not an organiser"}
        else:
            final = round(0.4 * feats["score"] + 0.6 * verdict["score"])
            # The LLM can't lift a post past the rules' evidence caps.
            if feats["parts"].get("organiser", 0) == 0:
                final = min(final, scoring.WARM - 1)
            if final >= scoring.HOT and feats["parts"].get("problem", 0) < 25 and not verdict.get("frustrated_with_platform"):
                final = scoring.HOT - 1
            scored_by = f"rules+llm ({os.getenv('LLM_MODEL') or 'llama-3.3-70b-versatile'})"
            explanation += f"; LLM {verdict['score']} -> 0.4*rules + 0.6*LLM = {final}"
            why = verdict.get("why_contact") or why
            opener = verdict.get("opener") or opener
            pain = verdict.get("pain") or pain
            intent = verdict.get("intent") or intent
            competitor = verdict.get("platform") or competitor
            llm_agrees = True
    elif verdict and verdict.get("error"):
        scored_by = f"rules (LLM error: {verdict['error'][:80]})"

    # Without a working LLM verdict the rules are the only judge, so they must clear a higher bar.
    floor = min_keep if llm_agrees else cfg.get("min_score_rules_only", 45)
    if final < floor:
        return {"keep": False, "lead": None, "rule_score": feats["score"], "llm": verdict,
                "reason": f"below floor {floor}: {explanation}"}

    text = " ".join((post.get("text") or post.get("title") or "").split())
    quote = verdict.get("evidence_quote") if (verdict and verdict.get("grounded")) else _evidence_sentence(text, feats)
    tier = scoring.priority(final)
    lead = {
        "first_seen_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
        "priority": tier,
        "score": final,
        "confidence": _confidence(feats, llm_agrees),
        "icp_fit": _icp_fit(feats),
        "organisation_hint": _org_hint(profile),
        "event_context": " · ".join(x for x in (feats["event_type"], feats["near_term"] and f"near-term: {feats['near_term']}") if x),
        "competitor": competitor,
        "problem": scoring.PAIN_LABEL.get(pain, pain),
        "intent": intent,
        "evidence_quote": (quote or "")[:300],
        "score_explanation": explanation,
        "evidence": " | ".join(f"{k}: {v}" for k, v in feats["evidence"].items())[:500],
        "why_contact": why,
        "next_action": NEXT_ACTION[tier],
        "suggested_opener": opener,
        "source": post["source"],
        "community": post.get("community", ""),
        "url": post["url"],
        "posted_utc": (post.get("created_utc") or "")[:16].replace("T", " "),
        "author": post.get("author", ""),
        "author_profile": post.get("author_url", ""),
        "author_context": _profile_line(profile),
        "region": "/".join(feats["regions"]),
        "post_title": (post.get("title") or "")[:200],
        "scored_by": scored_by,
        "review_status": "",
        "lead_id": post["id"],
    }
    return {"keep": True, "lead": lead, "rule_score": feats["score"], "llm": verdict, "reason": explanation}


NEXT_ACTION = {
    "Hot": "Review today. If accepted, reply in the public thread with the opener; no DM unless invited. Log in CRM.",
    "Warm": "Review this week. Check the profile/links for the organisation, then decide: reply, nurture or reject.",
    "Watch": "No outreach. Kept for pattern analysis and rule tuning.",
}


def _evidence_sentence(text: str, feats: dict) -> str:
    """The sentence that carries the strongest evidence (problem > organiser > platform), verbatim."""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    for key in ("problem", "organiser", "platform"):
        ev = feats["evidence"].get(key, "")
        for needle in re.findall(r'"([^"]+)"', ev) or [ev.split(",")[0]]:
            for s_ in sentences:
                if needle and needle.lower() in s_.lower():
                    return s_
    return text[:300]


def _confidence(feats: dict, llm_agrees: bool) -> str:
    p = feats["parts"]
    if p.get("organiser", 0) == 30 and p.get("problem", 0) == 25 and (p.get("platform", 0) == 15 or llm_agrees):
        return "High"
    if p.get("organiser", 0) >= 15 and p.get("problem", 0) >= 5:
        return "Medium"
    return "Low"


def _icp_fit(feats: dict) -> str:
    regions, et = set(feats["regions"]), feats["event_type"]
    if regions & {"UAE", "India"} and et in ("festival/concert", "conference", "community/recurring", "venue/theatre"):
        tier = "Primary ICP (UAE/India promoter or festival)"
    elif "India" in regions and et in ("sports", "endurance"):
        tier = "Secondary ICP (India sport)"
    elif regions & {"UK", "US"}:
        tier = "Self-serve market (UK/US)"
    else:
        tier = "Market unknown"
    return f"{tier} · {et or 'event type unknown'}"


def _org_hint(profile: dict) -> str:
    """Never verified automatically: a website from the public profile is a hint for the reviewer."""
    links = profile.get("links") or []
    return f"unverified: {links[0]}" if links else ""


def _profile_line(p: dict) -> str:
    if not p or p.get("error"):
        return ""
    bits = []
    if p.get("display_name"):
        bits.append(p["display_name"])
    if p.get("karma") is not None:
        bits.append(f"karma {p['karma']}")
    if p.get("followers") is not None:
        bits.append(f"{p['followers']} followers")
    if p.get("account_created"):
        bits.append(f"since {str(p['account_created'])[:10]}")
    if p.get("bio"):
        bits.append("bio: " + p["bio"][:160].replace("\n", " "))
    if p.get("links"):
        bits.append(" ".join(p["links"][:2]))
    return " | ".join(bits)


# --------------------------------------------------------------------- persist

@mcp.tool()
def save_leads(leads: list[dict]) -> dict:
    """Upsert lead rows into data/leads.csv (keeps any human-set status). Returns totals."""
    rows = store.write_leads(leads)
    return {"total_leads": len(rows), "upserted": len(leads)}


@mcp.tool()
def log_run(run: dict) -> str:
    """Append one row to the run log (data/runs.csv and the 'Run log' tab)."""
    store.append_run(run)
    return "logged"


@mcp.tool()
def sync_sheet() -> str:
    """Push data/leads.csv and the run log to the Google Sheet. Statuses typed in the sheet win."""
    leads = store.read_leads()
    try:
        status = sheets.sync(leads, store.read_runs())
    except Exception as e:  # auth expiry, quota, sheet not shared: report, don't crash the run
        return f"error: {type(e).__name__}: {str(e)[:200]}"
    store.write_leads(leads)  # persist statuses pulled from the sheet
    return status


@mcp.tool()
def write_summary() -> dict:
    """Recompute data/summary.json: the numbers the dashboard shows, all derived from stored data."""
    leads, runs = store.read_leads(), store.read_runs()
    def n(r, k):
        try:
            return int(r.get(k) or 0)
        except ValueError:
            return 0
    ok_runs = [r for r in runs if r.get("status") in ("ok", "partial")]
    by_trigger: dict[str, int] = {}
    for r in runs:
        by_trigger[r.get("trigger", "?")] = by_trigger.get(r.get("trigger", "?"), 0) + 1
    last = runs[-1] if runs else {}
    summary = {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "posts_processed_total": len(store.load_seen()),
        "leads_total": len(leads),
        "leads_by_priority": {t: sum(1 for l in leads if l["priority"] == t) for t in ("Hot", "Warm", "Watch")},
        "unique_prospects": len({(l["source"], l["author"]) for l in leads if l.get("author")}),
        "leads_reviewed": sum(1 for l in leads if l.get("review_status")),
        "runs_logged": len(runs),
        "runs_by_trigger": by_trigger,
        "runs_by_status": {s_: sum(1 for r in runs if r.get("status") == s_) for s_ in ("ok", "partial", "failed")},
        "last_successful_run_utc": ok_runs[-1]["finished_utc"] if ok_runs else None,
        "last_run": {k: last.get(k) for k in ("finished_utc", "trigger", "status", "sources_ok", "sources_failed",
                                               "sources_skipped", "discovered", "new", "qualified", "source_errors")},
        "llm_enabled": llm.enabled(),
        "llm_calls_total": sum(n(r, "llm_calls") for r in runs),
        "sheet_push_enabled": sheets.enabled(),
        "note": "posts_processed_total counts distinct posts ever scored (de-dup state). It was reset on 21 Oct "
                "while scoring rules changed, so it undercounts the earliest runs.",
    }
    store.write_summary(summary)
    return summary


@mcp.tool()
def export_to_crm(lead_ids: list[str], dry_run: bool = True) -> dict:
    """Hand human-ACCEPTED leads to the CRM. Only call with ids a person has accepted in the sheet.
    Not connected here (no Freshsales credentials): payloads go to data/crm_outbox.jsonl for checking.
    Never sends messages to the prospect."""
    from . import crm

    wanted = set(lead_ids)
    leads = [l for l in store.read_leads() if l["lead_id"] in wanted]
    return crm.export(leads, dry_run=dry_run) | {"missing": sorted(wanted - {l["lead_id"] for l in leads})}


# --------------------------------------------------------------------- ask

@mcp.tool()
def query_leads(min_score: int = 0, priority: str | None = None, competitor: str | None = None,
                pain: str | None = None, region: str | None = None, days: int = 30, limit: int = 20) -> list[dict]:
    """Filter stored leads. All filters optional and case-insensitive; newest first."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d %H:%M")
    out = []
    for r in store.read_leads():
        if r["first_seen_utc"] < cutoff or int(r["score"] or 0) < min_score:
            continue
        if priority and r["priority"].lower() != priority.lower():
            continue
        if competitor and competitor.lower() not in r["competitor"].lower():
            continue
        if pain and pain.lower() not in r["pain"].lower():
            continue
        if region and region.lower() not in r["region"].lower():
            continue
        out.append(r)
        if len(out) >= limit:
            break
    return out


@mcp.tool()
def lead_stats(days: int = 30) -> dict:
    """Counts of stored leads by priority, competitor, pain, region and source, plus recent runs."""
    rows = query_leads(days=days, limit=10_000)
    def count(key, split=False):
        c: dict[str, int] = {}
        for r in rows:
            vals = [v.strip() for v in r[key].replace("/", ",").split(",")] if split else [r[key]]
            for v in vals:
                if v:
                    c[v] = c.get(v, 0) + 1
        return dict(sorted(c.items(), key=lambda kv: -kv[1]))
    return {
        "leads": len(rows),
        "by_priority": count("priority"),
        "by_competitor": count("competitor", split=True),
        "by_pain": count("pain"),
        "by_region": count("region", split=True),
        "by_source": count("source"),
        "last_runs": store.read_runs()[-5:],
    }


# --------------------------------------------------------------------- one-shot cycle

@mcp.tool()
async def run_listener(trigger: str = "manual", max_llm_calls: int = 40) -> dict:
    """Run a whole listening cycle inside the server (same steps as agent/run.py).
    Handy from a chat client: "run the listener now"."""
    from agent.pipeline import run_cycle

    return await run_cycle(_LocalTools(), trigger=trigger, max_llm_calls=max_llm_calls, log=lambda *_: None)


class _LocalTools:
    """Lets run_listener reuse the pipeline without a second MCP hop."""

    async def call(self, name: str, **kwargs):
        return globals()[name](**kwargs)


@mcp.resource("listener://watchlist")
def watchlist_resource() -> dict:
    """The queries, communities and competitor list the listener uses."""
    return watchlist()


@mcp.prompt()
def weekly_digest() -> str:
    """Prompt template: summarise the week's leads for a growth stand-up."""
    return ("Call lead_stats(days=7) and query_leads(min_score=60, days=7). Write a 10-line digest: how many "
            "organisers complained, about which platforms, the top 3 people to contact today with why, and one "
            "pattern in the complaints that should change our messaging.")


def main():
    mcp.run()


if __name__ == "__main__":
    main()
