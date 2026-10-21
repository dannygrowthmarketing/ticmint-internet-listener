import json
from pathlib import Path

from listener_mcp import llm, scoring
from listener_mcp.config import watchlist

FX = {p["id"]: p for p in json.loads((Path(__file__).parent / "fixtures" / "posts.json").read_text())}
COMP = watchlist()["competitors"]


def s(pid):
    return scoring.score(FX[pid], COMP)


def test_frustrated_organiser_is_hot():
    f = s("reddit:fx1")
    assert f["score"] >= 70 and scoring.priority(f["score"]) == "Hot"
    assert f["competitors"] == ["Eventbrite"]
    assert "fees" in f["pain_categories"] and f["switching_intent"] and "UK" in f["regions"]


def test_fan_complaint_is_dropped():
    assert s("reddit:fx3")["score"] < watchlist()["min_score_to_keep"]


def test_developer_noise_is_dropped():
    assert s("hackernews:fx4")["score"] < watchlist()["min_score_to_keep"]


def test_uae_platinumlist_lead():
    f = s("reddit:fx5")
    assert "Platinumlist" in f["competitors"] and "UAE" in f["regions"] and f["score"] >= 50


def test_opener_names_platform_and_pain():
    o = scoring.opener(s("reddit:fx1"))
    assert "Eventbrite" in o and "2%" in o


def test_llm_grounding_rejects_invented_quote():
    body = FX["reddit:fx1"]["title"] + "\n\n" + FX["reddit:fx1"]["text"]
    bad = llm.verify({"evidence_quote": "Ticket Tailor stole our money", "platform": "Ticket Tailor", "score": 90}, body)
    assert not bad["grounded"] and len(bad["grounding_problems"]) == 2
    good = llm.verify({"evidence_quote": "support never replies", "platform": "Eventbrite", "score": 88}, body)
    assert good["grounded"] and good["score"] == 88


def test_suspended_organiser_is_hot_despite_typo():
    f = s("reddit:fx6")
    assert "account_risk" in f["pain_categories"] and scoring.priority(f["score"]) == "Hot"


def test_happy_event_promotion_is_dropped():
    assert s("reddit:fx7")["score"] < watchlist()["min_score_rules_only"]


def test_long_event_digest_is_dropped():
    # Mentions Eventbrite once; "recommend", "problem", "can't" appear far away from it.
    assert s("reddit:fx8")["score"] < watchlist()["min_score_rules_only"]
