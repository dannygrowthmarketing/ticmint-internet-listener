"""Rule-based first pass. Cheap, deterministic, explainable.

Every post gets scored here. Only posts that clear the bar go on to the LLM
(see llm.py), which keeps cost flat no matter how noisy the sources are.
The rules also run alone when no LLM key is configured, so the pipeline
never stops producing rows because a free tier ran out.
"""

import re
from datetime import datetime, timezone


def _rx(*words: str) -> re.Pattern:
    return re.compile(r"(" + "|".join(words) + r")", re.I)


PAIN = {
    "fees": _rx(r"\bfees?\b", r"commission", r"per[- ]ticket", r"service charge", r"booking fee", r"too expensive",
                r"\b\d+(\.\d+)?\s?%", r"rip[- ]?off", r"price hike", r"cheaper"),
    "payouts": _rx(r"payout", r"paid out", r"hold(ing)? (my|our|the) (money|funds)", r"funds? (held|frozen|on hold)",
                   r"after the event", r"cash ?flow", r"withheld"),
    "support": _rx(r"customer (service|support)", r"\bsupport\b", r"no one (replies|responds|answers)", r"can'?t reach",
                   r"no response", r"chatbot", r"ticket(ed)? (with|to) support"),
    "data_ownership": _rx(r"(own|owning|my|our) (attendee|customer|audience) (data|list|emails?)", r"attendee data",
                          r"email list", r"they own", r"marketplace", r"my brand", r"white[- ]?label", r"custom domain"),
    "account_risk": _rx(r"(account|event)\W+(\w+\W+){0,2}(suspended|banned|deactivated|removed|taken down|closed|disabled|frozen)",
                        r"\bsuspended\b", r"flagged", r"locked out"),
    "refunds": _rx(r"refunds?", r"chargebacks?", r"cancell?ation"),
    "checkout_ux": _rx(r"checkout", r"clunky", r"confusing", r"buggy", r"glitch", r"crash(ed|es)?", r"slow",
                       r"(seat|seating) (map|chart)", r"scann?(er|ing)", r"qr code"),
}

# First-person evidence that the author sells tickets. Generic phrases like "sell
# tickets" or "ticket sales" are NOT enough: run 7 kept an HN comment about bomb
# disposal because it said "you can't sell tickets".
ORGANISER = _rx(
    r"\b(my|our) (event|events|festival|gig|gigs|show|shows|conference|meetup|club night|club nights|tournament|race|marathon|workshop|venue|tour|league|fundraiser|gala|attendees|ticket sales|on-?sale)\b",
    r"\bi('m| am)? (organi[sz](e|ing)|run(ning)?|host(ing)?|promot(e|ing)|put(ting)? on)\b",
    r"\bwe('re| are)? (organi[sz]ing|hosting|running|putting on|promoting)\b", r"\bwe (run|host|organi[sz]e|promote|put on)\b",
    r"\b(i|we)('re| are)? (sell|selling|sold) tickets\b", r"\bmy eventbrite\b", r"\bmy (organi[sz]er|promoter) account\b",
    r"\bas an? (event )?(organi[sz]er|promoter)\b", r"\bi'?m an? (event )?(organi[sz]er|promoter)\b",
)

# What kind of event, for ICP fit (Part D: festivals/promoters first, then sport).
EVENT_TYPES = {
    "festival/concert": _rx(r"festival", r"concert", r"\bgigs?\b", r"club nights?", r"\bdj\b", r"\btour\b", r"\bpromoter"),
    "sports": _rx(r"tournament", r"\bleague\b", r"federation", r"\bmatch(es)?\b", r"championship", r"\bclub\b.*\b(match|season)\b"),
    "conference": _rx(r"conference", r"summit", r"\bexpo\b", r"\btedx\b", r"meetup"),
    "endurance": _rx(r"marathon", r"\b(5|10)k\b", r"\brace\b", r"triathlon", r"cyclo"),
    "venue/theatre": _rx(r"\bvenue\b", r"theatre", r"theater", r"box office", r"comedy club"),
    "community/recurring": _rx(r"workshop", r"\bclasses\b", r"community event", r"recurring event", r"meet-?ups?"),
}

# A dated, near-term event raises urgency (only counted alongside a problem).
NEAR_TERM = _rx(r"\b\d+ days? (before|until|away|left)\b", r"\bnext (week|weekend|month)\b", r"\btomorrow\b", r"\btonight\b",
                r"\bthis (friday|saturday|sunday|week)\b", r"\bon (monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
                r"\bin (two|three|\d+) weeks\b", r"\bon-?sale (date|starts)\b")

FAN = _rx(
    r"\bi (bought|purchased|got) (a |my |two |2 )?tickets?\b", r"\bscalp(er|ers|ing)\b", r"\bresale\b", r"\bqueue\b",
    r"\bverified fan\b", r"\bpresale code\b", r"\btaylor swift\b", r"\boasis\b", r"\bdynamic pricing\b.*\bconcert\b",
    r"\bas a (fan|customer|buyer)\b",
)

SWITCHING = _rx(
    r"\balternatives?\b", r"\bswitch(ing|ed)? (from|away|to)\b", r"\bmov(e|ing|ed) (away )?from\b", r"\bleav(e|ing)\b",
    r"\bany (recommendations|suggestions)\b", r"\b(what|which) (do you|does everyone|platform|ticketing)\b.*\b(use|recommend)\b",
    r"\blooking for (a |an )?(new |better |cheaper )?(ticketing|platform|way to sell)\b", r"\brecommend\b", r"\bvs\.?\b",
    r"\bbetter than\b", r"\bis there (a|an|any)\b[^.?!]{0,40}\b(option|alternative|platform|way|tool)\b", r"\bfed up\b", r"\bnever (again|using)\b", r"\bdone with\b",
)

# Something is actually wrong (as opposed to a topic merely being mentioned).
PROBLEM = _rx(r"\bhelp\b", r"still waiting", r"\bwon'?t\b", r"\bcan'?t\b", r"\bhasn'?t\b", r"\bhaven'?t (been|received|got)",
              r"\bno (reply|response|answer|one)\b", r"\bsuspended\b", r"\bproblem\b", r"\bissue\b", r"\bcomplain",
              r"\bwhy (does|is|did)\b", r"\btoo (high|much|expensive)\b", r"\bcharg(ed|ing) (me|us)\b", r"\bunacceptable\b")

# Event promotion: the organiser is *using* a platform happily and advertising an event.
# Useful later as a "who uses Eventbrite" list, but not a frustration lead.
PROMO = _rx(r"get your tickets", r"tickets? (are )?(available|on sale) (now|at|here)", r"\blink in (bio|comments)\b", r"\brsvp\b",
            r"come (solo|join|out|along)", r"this weekend", r"one night only", r"doors open", r"\bline-?up\b",
            r"what'?s (going on|happening)", r"events? for (fri|sat|sun|mon|tue|wed|thu)", r"don'?t miss", r"\bfeaturing\b",
            r"agencies", r"\bcurated list\b", r"\btop \d+\b")

ANGER = _rx(r"\bhate\b", r"terrible", r"awful", r"nightmare", r"ridiculous", r"\bscam\b", r"frustrat", r"annoy", r"insane",
            r"robbery", r"daylight robbery", r"disgust", r"useless", r"worst", r"absurd", r"greedy", r"predatory")

NOISE = _rx(r"\bapi\b", r"\bgithub\b", r"\bwe('re| are) hiring\b", r"\bjob (posting|opening)\b", r"\bscraper\b", r"\bshow hn\b",
            r"\bstock\b", r"\bipo\b", r"\bearnings\b", r"\bacquisition\b", r"\bshareholders?\b")

REGIONS = {
    "UK": _rx(r"\buk\b", r"united kingdom", r"london", r"manchester", r"glasgow", r"edinburgh", r"birmingham", r"bristol",
              r"leeds", r"£", r"\bgbp\b", r"r/london"),
    "UAE": _rx(r"\buae\b", r"dubai", r"abu dhabi", r"sharjah", r"\baed\b", r"dirham", r"\bdtcm\b", r"r/dubai"),
    "India": _rx(r"india", r"mumbai", r"bangalore", r"bengaluru", r"delhi", r"hyderabad", r"chennai", r"pune", r"kolkata",
                 r"₹", r"\binr\b", r"\brs\.? ?\d", r"r/(india|bangalore|mumbai)"),
    "US": _rx(r"\busa\b", r"\bu\.s\.\b", r"united states", r"new york", r"\bnyc\b", r"los angeles", r"chicago", r"austin",
              r"texas", r"california", r"\$\d"),
}

# Relevance gate. The first live run (21 Oct 2026) kept 31 rows and almost all were
# noise: HN essays and #eventprofs blog posts that matched "support" or "slow".
# Nothing scores unless the post is actually about tickets or names a platform.
TICKETING = _rx(r"\btickets?\b", r"\bticketing\b", r"\bbox office\b", r"\bregistration (platform|page|fees?|system)\b",
                r"\bsell(ing)? out\b", r"\bticket sales\b")

ORGANISER_COMMUNITIES = {"r/eventprofs", "r/eventmanagement", "r/promoters", "r/bandmembers", "#eventprofs",
                         "r/eventbritesupport", "r/eventbrite"}


# Most specific / most urgent first: the first pain found drives the opener.
PAIN = {k: PAIN[k] for k in ("account_risk", "payouts", "fees", "data_ownership", "support", "refunds", "checkout_ux")}


def detect_competitors(text: str, competitors: dict[str, list[str]]) -> list[str]:
    padded = f" {text.lower()} "
    return [name for name, aliases in competitors.items() if any(a in padded for a in aliases)]


# Thresholds. Hot also needs organiser + problem evidence (see score()).
HOT, WARM = 70, 50


def _first(rx: re.Pattern, text: str) -> str:
    m = rx.search(text)
    return m.group(0).strip() if m else ""


def score(post: dict, competitors: dict[str, list[str]], now: datetime | None = None) -> dict:
    """Score a post 0-100 on six explicit criteria, each backed by the phrase that earned it.

    organiser  0-30  first-person evidence the author sells tickets (15 if only the community suggests it)
    platform   0-15  a named ticketing platform (5 for generic "ticketing platform" talk)
    problem    0-25  a pain topic AND evidence something is actually wrong (5 for the topic alone)
    intent     0-20  switching/evaluating (15) and a near-term event (+5)
    identity   0-5   public profile context that makes the person findable
    icp        0-5   a target market (India/UAE/UK/US) and an ICP event type
    penalties        ticket-buyer voice -40, happy event promotion -25, developer/finance noise -15, too short -10

    Caps: no organiser evidence -> at most Watch (49). Hot needs organiser AND problem evidence,
    so a competitor name alone can never make a lead Hot. Pure function: easy to test."""
    text = f"{post.get('title', '')}\n{post.get('text', '')}"
    community = (post.get("community") or "").lower()
    now = now or datetime.now(timezone.utc)

    comps = detect_competitors(text, competitors)
    if not comps and not TICKETING.search(text):
        return _result(0, {}, {"gate": "no ticketing context"}, comps, [], [], "", "", False, False, False,
                       "No ticketing context.")

    # Long posts (event digests, listicles, essays) mention a platform once and say
    # "recommend" or "problem" somewhere else entirely. Judge them only on the text
    # around the platform/ticketing mentions.
    whole = text
    if len(text) > 700:
        spans = [m.span() for a in (al for name in comps for al in competitors[name]) for m in re.finditer(re.escape(a.strip()), text, re.I)]
        spans += [m.span() for m in TICKETING.finditer(text)]
        text = " … ".join(whole[max(0, a - 250): b + 250] for a, b in sorted(spans)[:6]) or whole[:700]

    ev: dict[str, str] = {}
    parts: dict[str, int] = {}

    org_phrase = _first(ORGANISER, text)
    if org_phrase:
        parts["organiser"], ev["organiser"] = 30, org_phrase
    elif community in ORGANISER_COMMUNITIES:
        parts["organiser"], ev["organiser"] = 15, f"posted in {post.get('community')}"
    else:
        parts["organiser"] = 0

    if comps:
        parts["platform"], ev["platform"] = 15, ", ".join(comps)
        if comps == ["Ticketmaster"] and not org_phrase:
            parts["platform"] = 0  # Ticketmaster talk is overwhelmingly fans
    elif re.search(r"ticketing (platform|provider|software|system)", text, re.I):
        parts["platform"], ev["platform"] = 5, "generic ticketing platform"
    else:
        parts["platform"] = 0

    pains = [k for k, rx in PAIN.items() if rx.search(text)]
    problem_phrase = _first(PROBLEM, text) or _first(ANGER, text)
    switch_phrase = _first(SWITCHING, text)
    if pains and (problem_phrase or switch_phrase):
        parts["problem"] = 25
        ev["problem"] = f"{PAIN_LABEL[pains[0]]}: \"{_first(PAIN[pains[0]], text)}\" + \"{problem_phrase or switch_phrase}\""
    elif pains:
        parts["problem"], ev["problem"] = 5, f"mentions {PAIN_LABEL[pains[0]]} (no sign anything is wrong)"
    else:
        parts["problem"] = 0

    near = _first(NEAR_TERM, text)
    parts["intent"] = (15 if switch_phrase else 0) + (5 if near and parts["problem"] == 25 else 0)
    if switch_phrase:
        ev["intent"] = f"\"{switch_phrase}\""
    if near and parts["problem"] == 25:
        ev["intent"] = (ev.get("intent", "") + f" near-term: \"{near}\"").strip()

    prof = post.get("_profile") or {}
    parts["identity"] = min(5, (2 if prof.get("bio") else 0) + (2 if prof.get("links") else 0)
                            + (1 if (prof.get("karma") or 0) > 100 or (prof.get("followers") or 0) > 100 else 0))

    regions = [r for r, rx in REGIONS.items() if rx.search(f"{whole} {community}")]
    event_type = next((k for k, rx in EVENT_TYPES.items() if rx.search(whole)), "")
    parts["icp"] = (3 if regions else 0) + (2 if event_type else 0)

    pen = {}
    fan_phrase = _first(FAN, text)
    if fan_phrase and not org_phrase:
        pen["ticket buyer"] = -40
        ev["ticket buyer"] = fan_phrase
    promo = bool(PROMO.search(whole)) or (len(whole) > 1500 and whole.count("http") >= 3)
    if promo and not (switch_phrase or _first(ANGER, text) or "account_risk" in pains):
        pen["event promotion"] = -25
    if NOISE.search(text):
        pen["dev/finance noise"] = -15
    if len(whole.strip()) < 40:
        pen["too short"] = -10
    try:
        age_h = (now - datetime.fromisoformat(post["created_utc"].replace("Z", "+00:00"))).total_seconds() / 3600
    except (KeyError, ValueError):
        age_h = None

    raw = sum(parts.values()) + sum(pen.values())
    s = max(0, min(100, raw))
    if parts["organiser"] == 0:
        s = min(s, WARM - 1)
    if s >= HOT and not (parts["organiser"] >= 15 and parts["problem"] == 25):
        s = HOT - 1

    explanation = " + ".join(f"{k} {v}" for k, v in parts.items() if v) or "nothing"
    if pen:
        explanation += " " + " ".join(f"{k} {v}" for k, v in pen.items())
    explanation += f" = {s}"
    return _result(s, parts, {**ev, **({"penalties": ", ".join(pen)} if pen else {})}, comps, pains, regions,
                   event_type, near, bool(org_phrase) or community in ORGANISER_COMMUNITIES, bool(fan_phrase),
                   bool(switch_phrase), explain(comps, pains, bool(org_phrase) or community in ORGANISER_COMMUNITIES,
                                                bool(switch_phrase), bool(_first(ANGER, text)), regions),
                   explanation, age_h)


def _result(s, parts, evidence, comps, pains, regions, event_type, near, organiser, fan, switching, why,
            explanation="", age_h=None) -> dict:
    return {
        "score": s,
        "parts": parts,
        "evidence": evidence,
        "score_explanation": explanation or why,
        "competitors": comps,
        "pain_categories": pains,
        "regions": regions,
        "event_type": event_type,
        "near_term": near,
        "is_organiser_signal": organiser,
        "is_fan_signal": fan,
        "switching_intent": switching,
        "age_hours": round(age_h, 1) if age_h is not None else None,
        "why": why,
    }


def priority(s: int) -> str:
    if s >= HOT:
        return "Hot"
    if s >= WARM:
        return "Warm"
    return "Watch"


PAIN_LABEL = {
    "fees": "fees",
    "payouts": "slow or held payouts",
    "support": "unresponsive support",
    "data_ownership": "not owning their attendee data/brand",
    "account_risk": "account or event suspension",
    "refunds": "refund/chargeback handling",
    "checkout_ux": "checkout or event-day tooling",
}


def explain(comps, pains, organiser, switching, anger, regions) -> str:
    bits = []
    bits.append("Organiser voice" if organiser else "Not clearly an organiser")
    if comps:
        bits.append("on " + ", ".join(comps))
    if pains:
        bits.append("unhappy about " + ", ".join(PAIN_LABEL[p] for p in pains[:3]))
    if switching:
        bits.append("actively looking at alternatives")
    elif anger:
        bits.append("strong frustration")
    if regions:
        bits.append("region: " + "/".join(regions))
    return "; ".join(bits) + "."


# Openers are written to answer the complaint, not to pitch. One per pain, with
# the platform named so it reads as a reply to *their* post.
OPENERS = {
    "fees": "Saw your post about {comp}'s fees. We ran the maths for a few organisers your size: on Ticmint it's 2% on the Growth plan and you can pass the booking fee to the buyer. Happy to send the calculation for your ticket price if useful, no call needed.",
    "payouts": "Saw you're waiting on {comp} to release your money. On Ticmint the buyer pays straight into your own Stripe/Razorpay, so there's nothing for us to hold. If it helps I can show you how that's set up.",
    "support": "Sorry you're stuck with {comp} support. If you're weighing a move, we give organisers a WhatsApp line to a real person and help migrate the next event. Want me to share what the switch involves?",
    "data_ownership": "Your point about {comp} owning the relationship with your attendees is exactly why we built Ticmint white-label: your domain, your checkout, your list. Want a look at how one of our festivals set it up?",
    "account_risk": "That sounds stressful, having {comp} pull the event. If you need a backup ticket page live today on your own domain, I can help you get one up for free.",
    "refunds": "Saw the refund mess with {comp}. Ticmint lets you set your own refund rules and offers attendees optional refund protection, so you're not eating the cost. Happy to explain how it works.",
    "checkout_ux": "Saw your note about {comp}'s checkout/event-day tools. Ticmint's branded checkout and offline scanning app might fit. Want a 2-minute screen recording instead of a demo call?",
    "_default": "Saw your post about ticketing for your events. If you're comparing options, I'm happy to share a no-pitch breakdown of fees and data ownership across {comp} and alternatives.",
}


def opener(features: dict) -> str:
    comp = features["competitors"][0] if features["competitors"] else "your current platform"
    pain = features["pain_categories"][0] if features["pain_categories"] else "_default"
    return OPENERS.get(pain, OPENERS["_default"]).format(comp=comp)
