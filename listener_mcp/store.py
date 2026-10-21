"""Local state, committed back to the repo by the scheduled workflow.

data/state.json  ids already processed (so a post is scored once, ever)
data/leads.csv   every lead kept, newest first: the canonical copy of the Sheet
data/runs.csv    one row per run: the audit trail that proves it runs on its own
"""

import csv
import json
import os
from pathlib import Path

DATA = Path(os.getenv("LISTENER_DATA_DIR", Path(__file__).resolve().parent.parent / "data"))

LEAD_COLUMNS = [
    "first_seen_utc", "priority", "score", "confidence", "icp_fit", "organisation_hint", "event_context",
    "competitor", "problem", "intent", "evidence_quote", "score_explanation", "evidence", "why_contact",
    "next_action", "suggested_opener", "source", "community", "url", "posted_utc", "author", "author_profile",
    "author_context", "region", "post_title", "scored_by", "review_status", "lead_id",
]

RUN_COLUMNS = [
    "run_id", "started_utc", "finished_utc", "trigger", "status", "sources_ok", "sources_failed", "sources_skipped",
    "discovered", "new", "shortlisted", "llm_calls", "llm_errors", "processing_errors", "qualified", "hot", "warm",
    "watch", "source_errors", "sheet_status",
]


def _seen_path() -> Path:
    return DATA / "state.json"


def load_seen() -> set[str]:
    p = _seen_path()
    if not p.exists():
        return set()
    return set(json.loads(p.read_text()).get("seen", []))


def save_seen(seen: set[str], cap: int = 20000) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    # Keep the file bounded; old ids fall out of every source's lookback window anyway.
    ids = sorted(seen)[-cap:]
    _seen_path().write_text(json.dumps({"seen": ids}, indent=0))


def read_leads() -> list[dict]:
    p = DATA / "leads.csv"
    if not p.exists():
        return []
    with p.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_leads(new_rows: list[dict]) -> list[dict]:
    """Upsert by lead_id; keep a human-entered review_status if the row already exists."""
    existing = {r["lead_id"]: r for r in read_leads()}
    for row in new_rows:
        old = existing.get(row["lead_id"])
        if old and old.get("review_status"):
            row["review_status"] = old["review_status"]
        existing[row["lead_id"]] = row
    rows = sorted(existing.values(), key=lambda r: (r["first_seen_utc"], int(r["score"] or 0)), reverse=True)
    DATA.mkdir(parents=True, exist_ok=True)
    with (DATA / "leads.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=LEAD_COLUMNS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    return rows


def append_run(run: dict) -> None:
    """Append a run, or update it in place if this run_id is already logged."""
    DATA.mkdir(parents=True, exist_ok=True)
    runs = [r for r in read_runs() if r.get("run_id") != run.get("run_id")] + [run]
    with (DATA / "runs.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=RUN_COLUMNS, extrasaction="ignore")
        w.writeheader()
        w.writerows(runs)


def read_runs() -> list[dict]:
    p = DATA / "runs.csv"
    if not p.exists():
        return []
    with p.open(newline="", encoding="utf-8") as f:
        return [_migrate(r) for r in csv.DictReader(f)]


def _migrate(r: dict) -> dict:
    """Runs logged before 21 Oct 09:30 UTC used 'fetched'/'kept' and had no status."""
    if "discovered" not in r or r.get("discovered") in (None, ""):
        if "fetched" in r:
            r["discovered"] = r.pop("fetched")
            r["qualified"] = r.pop("kept", "")
            failed = [e.split(":")[0].strip() for e in (r.get("source_errors") or "").split("; ")
                      if e and "skipped" not in e and e.split(":")[0].strip() in ("hackernews", "reddit", "bluesky", "mastodon")]
            r["sources_failed"] = " ".join(sorted(set(failed)))
            r["sources_skipped"] = "bluesky" if "bluesky skipped" in (r.get("source_errors") or "") else ""
            r["sources_ok"] = " ".join(s for s in ("hackernews", "mastodon") if s not in failed)
            r["status"] = "partial" if failed else "ok"
    return r


def write_summary(summary: dict) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "summary.json").write_text(json.dumps(summary, indent=2))
