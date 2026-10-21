"""Failure handling: blocked sources, crashing tools, LLM errors and lies, missing credentials,
duplicate runs, and human statuses surviving a refresh."""

import asyncio
import json
from pathlib import Path

import pytest

from agent.pipeline import run_cycle
from listener_mcp import llm, scoring, server, sheets, store
from listener_mcp.config import watchlist

FX = {p["id"]: p for p in json.loads((Path(__file__).parent / "fixtures" / "posts.json").read_text())}


@pytest.fixture(autouse=True)
def tmp_data(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DATA", tmp_path)
    for k in ("LLM_API_KEY", "GOOGLE_SERVICE_ACCOUNT_JSON", "SHEET_ID", "BSKY_HANDLE", "BSKY_APP_PASSWORD"):
        monkeypatch.delenv(k, raising=False)
    return tmp_path


class Tools:
    """The pipeline only talks to tools, so tests can swap any tool for a failing one."""

    def __init__(self, sources: dict, fail_qualify: set = frozenset()):
        self.sources, self.fail_qualify = sources, fail_qualify

    async def call(self, name, **kw):
        if name == "search_source":
            v = self.sources.get(kw["source"], {"posts": [], "error": "bluesky skipped: no credentials"})
            return v
        if name == "qualify_post" and kw["post"]["id"] in self.fail_qualify:
            raise RuntimeError("tool qualify_post failed: boom")
        return getattr(server, name)(**kw)


def run(tools):
    return asyncio.run(run_cycle(tools, trigger="test", log=lambda *_: None))


def posts(*ids):
    return {"posts": [FX[i] for i in ids], "error": None}


def test_one_blocked_source_does_not_lose_the_others():
    r = run(Tools({"hackernews": posts("hackernews:fx2"), "reddit": {"posts": [], "error": "HTTP 403"},
                   "mastodon": {"posts": [], "error": None}}))
    assert r["status"] == "partial" and r["sources_failed"] == "reddit" and "hackernews" in r["sources_ok"]
    assert r["sources_skipped"] == "bluesky"  # unconfigured is not a failure
    assert [l["lead_id"] for l in store.read_leads()] == ["hackernews:fx2"]


class Flaky(Tools):
    """Reddit answers the first query, then rate-limits (what run 8 on 21 Oct actually did)."""

    async def call(self, name, **kw):
        if name == "search_source" and kw["source"] == "reddit":
            self.n = getattr(self, "n", 0) + 1
            return {"posts": [], "error": None} if self.n == 1 else {"posts": [], "error": "HTTP 429"}
        return await super().call(name, **kw)


def test_source_failing_midway_marks_run_partial():
    r = run(Flaky({"hackernews": {"posts": [], "error": None}, "mastodon": {"posts": [], "error": None}}))
    assert r["status"] == "partial" and "reddit: HTTP 429" in r["source_errors"]


def test_all_sources_down_is_a_failed_run():
    r = run(Tools({s: {"posts": [], "error": "HTTP 503"} for s in ("hackernews", "reddit", "mastodon")}))
    assert r["status"] == "failed" and r["qualified"] == 0
    assert store.read_runs()[-1]["status"] == "failed"


def test_crashing_tool_on_one_post_keeps_the_rest_and_retries_later():
    r = run(Tools({"reddit": posts("reddit:fx1", "reddit:fx6"), "hackernews": {"posts": [], "error": None},
                   "mastodon": {"posts": [], "error": None}}, fail_qualify={"reddit:fx6"}))
    assert r["processing_errors"] == 1 and r["status"] == "partial"
    assert {l["lead_id"] for l in store.read_leads()} == {"reddit:fx1"}
    assert "reddit:fx6" not in store.load_seen()  # will be retried next run


def test_second_run_creates_no_duplicates():
    t = Tools({"reddit": posts("reddit:fx1", "reddit:fx5"), "hackernews": {"posts": [], "error": None},
               "mastodon": {"posts": [], "error": None}})
    run(t)
    r2 = run(t)
    assert r2["new"] == 0 and r2["qualified"] == 0 and len(store.read_leads()) == 2


def test_human_review_status_survives_refresh():
    lead = server.qualify_post(FX["reddit:fx1"], use_llm=False)["lead"]
    store.write_leads([{**lead, "review_status": "Accepted"}])
    store.write_leads([{**lead, "score": 95}])  # the agent rewrites the row
    assert store.read_leads()[0]["review_status"] == "Accepted"


def test_missing_credentials_are_skips_not_crashes():
    assert server.search_source("bluesky", "eventbrite fees")["error"].startswith("bluesky skipped")
    assert sheets.sync([], []).startswith("skipped")
    assert llm.classify(FX["reddit:fx1"]) is None


def test_llm_exception_falls_back_to_rules(monkeypatch):
    monkeypatch.setattr(llm, "classify", lambda p: (_ for _ in ()).throw(TimeoutError("read timeout")))
    res = server.qualify_post(FX["reddit:fx1"])
    assert res["keep"] and res["lead"]["scored_by"].startswith("rules (LLM error: TimeoutError")


def test_ungrounded_llm_answer_is_ignored(monkeypatch):
    monkeypatch.setattr(llm, "classify", lambda p: llm.verify(
        {"is_organiser": True, "evidence_quote": "Ticket Tailor froze our payout", "platform": "Ticket Tailor", "score": 99},
        p["title"] + "\n\n" + p["text"]))
    lead = server.qualify_post(FX["reddit:fx1"])["lead"]
    assert lead["scored_by"].startswith("rules (LLM rejected") and lead["competitor"] == "Eventbrite"


def test_llm_not_an_organiser_drops_the_post(monkeypatch):
    monkeypatch.setattr(llm, "classify", lambda p: {"is_organiser": False, "grounded": True, "score": 10})
    assert not server.qualify_post(FX["reddit:fx1"])["keep"]


def test_llm_cannot_make_a_non_organiser_hot(monkeypatch):
    post = {**FX["reddit:fx1"], "id": "reddit:x", "title": "Eventbrite fees are a total ripoff, any alternative?",
            "text": "Seriously, the fees are insane and support is useless. Is there an alternative?",
            "community": "r/random"}
    assert scoring.score(post, watchlist()["competitors"])["parts"]["organiser"] == 0
    monkeypatch.setattr(llm, "classify", lambda p: {"is_organiser": True, "grounded": True, "score": 100,
                                                    "evidence_quote": "the fees are insane"})
    res = server.qualify_post(post)
    assert res["keep"] and res["lead"]["priority"] != "Hot"


def test_competitor_and_anger_without_organiser_is_never_hot():
    post = {**FX["reddit:fx1"], "title": "Eventbrite is the worst", "community": "r/random",
            "text": "Eventbrite fees are a scam and support is useless, looking for an alternative ticketing platform."}
    s = scoring.score(post, watchlist()["competitors"])
    assert s["score"] < scoring.WARM


def test_incidental_ticket_mention_is_rejected():
    post = {**FX["hackernews:fx4"], "title": "The art of defusing a second world war bomb", "community": "HN",
            "text": "Better to build an open top cylinder. Though that would hide the explosion so you can't sell tickets."}
    assert scoring.score(post, watchlist()["competitors"])["score"] < watchlist()["min_score_to_keep"]


def test_every_lead_carries_its_evidence():
    lead = server.qualify_post(FX["reddit:fx6"], use_llm=False)["lead"]
    assert lead["evidence_quote"] and lead["evidence_quote"].lower() in FX["reddit:fx6"]["text"].lower()
    assert lead["url"] == FX["reddit:fx6"]["url"] and "organiser" in lead["evidence"]
    assert lead["score_explanation"].endswith(f"= {lead['score']}") and lead["confidence"] in ("High", "Medium", "Low")


def test_crm_export_is_labelled_unconnected_and_sends_nothing(monkeypatch):
    monkeypatch.delenv("FRESHSALES_API_KEY", raising=False)
    store.write_leads([server.qualify_post(FX["reddit:fx1"], use_llm=False)["lead"]])
    out = server.export_to_crm(["reddit:fx1", "reddit:nope"])
    assert out["mode"].startswith("NOT CONNECTED") and out["count"] == 1 and out["missing"] == ["reddit:nope"]
    assert (store.DATA / "crm_outbox.jsonl").exists()
