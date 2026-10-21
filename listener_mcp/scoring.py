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
    "account_risk": _rx(r"(account|event) (was )?(suspended|banned|deactivated|removed|taken down|closed)",
                        r"flagged", r"locked out"),
    "refunds": _rx(r"refunds?", r"chargebacks?", r"cancell?ation"),
    "checkout_ux": _rx(r"checkout", r"clunky", r"confusing", r"buggy", r"glitch", r"crash(ed|es)?", r"slow",
                       r"(seat|seating) (map|chart)", r"scann?(er|ing)", r"qr code"),
}

ORGANISER = _rx(
    r"\b(my|our) (event|events|festival|gig|gigs|show|shows|conference|meetup|club night|tournament|race|marathon|workshop|venue|tour|league|fundraiser|gala)\b",
    r"\bi('m| am)? (organi[sz](e|ing)|run(ning)?|host(ing)?|promot(e|ing)|put(ting)? on)\b", r"\bwe('re| are)? (organi[sz]ing|hosting|running|putting on)\b",
    r"\b(event|gig|club|festival) promoter\b", r"\bevent organi[sz]er\b", r"\b(sell|selling|sold) tickets\b",
    r"\bour attendees\b", r"\bmy attendees\b", r"\bticket sales\b", r"\bon[- ]sale\b", r"\bticketing (platform|provider|partner|software|system)\b",
)

FAN = _rx(
    r"\bi (bought|purchased|got) (a |my |two |2 )?tickets?\b", r"\bscalp(er|ers|ing)\b", r"\bresale\b", r"\bqueue\b",
    r"\bverified fan\b", r"\bpresale code\b", r"\btaylor swift\b", r"\boasis\b", r"\bdynamic pricing\b.*\bconcert\b",
    r"\bas a (fan|customer|buyer)\b",
)

SWITCHING = _rx(
    r"\balternatives?\b", r"\bswitch(ing|ed)? (from|away|to)\b", r"\bmov(e|ing|ed) (away )?from\b", r"\bleav(e|ing)\b",
    r"\bany (recommendations|suggestions)\b", r"\b(what|which) (do you|does everyone|platform|ticketing)\b.*\b(use|recommend)\b",
    r"\blooking for (a |an )?(new |better |cheaper )?(ticketing|platform|way to sell)\b", r"\brecommend\b", r"\bvs\.?\b",
    r"\bbetter than\b", r"\bfed up\b", r"\bnever (again|using)\b", r"\bdone with\b",
)

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

ORGANISER_COMMUNITIES = {"r/eventprofs", "r/eventmanagement", "r/promoters", "r/bandmembers", "#eventprofs"}


def detect_competitors(text: str, competitors: dict[str, list[str]]) -> list[str]:
    padded = f" {text.lower()} "
    return [name for name, aliases in competitors.items() if any(a in padded for a in aliases)]


def score(post: dict, competitors: dict[str, list[str]], now: datetime | None = None) -> dict:
    """Return the post's features and a 0-100 score. Pure function: easy to test."""
    text = f"{post.get('title', '')}\n{post.get('text', '')}"
    community = (post.get("community") or "").lower()
    now = now or datetime.now(timezone.utc)

    comps = detect_competitors(text, competitors)
    if not comps and not TICKETING.search(text):
        return {"score": 0, "competitors": [], "pain_categories": [], "is_organiser_signal": False,
                "is_fan_signal": False, "switching_intent": False, "negative_emotion": False, "regions": [],
                "why": "No ticketing context."}
    pains = [k for k, rx in PAIN.items() if rx.search(text)]
    organiser = bool(ORGANISER.search(text)) or community in ORGANISER_COMMUNITIES
    fan = bool(FAN.search(text))
    switching = bool(SWITCHING.search(text))
    anger = bool(ANGER.search(text))
    noise = bool(NOISE.search(text))
    regions = [r for r, rx in REGIONS.items() if rx.search(f"{text} {community}")]

    s = 0
    if comps:
        s += 20
        # Ticketmaster complaints are overwhelmingly fans; only count them with an organiser signal.
        if comps == ["Ticketmaster"] and not organiser:
            s -= 20
    if pains:
        s += 15 + min(10, 5 * (len(pains) - 1))
    if organiser:
        s += 25
    if fan and not organiser:
        s -= 30
    if switching:
        s += 20
    if anger:
        s += 10
    if noise:
        s -= 15
    if community in ORGANISER_COMMUNITIES:
        s += 5
    try:
        age_h = (now - datetime.fromisoformat(post["created_utc"].replace("Z", "+00:00"))).total_seconds() / 3600
        if age_h <= 48:
            s += 5
    except (KeyError, ValueError):
        pass
    if len(text.strip()) < 40:
        s -= 10

    s = max(0, min(100, s))
    return {
        "score": s,
        "competitors": comps,
        "pain_categories": pains,
        "is_organiser_signal": organiser,
        "is_fan_signal": fan,
        "switching_intent": switching,
        "negative_emotion": anger,
        "regions": regions,
        "why": explain(comps, pains, organiser, switching, anger, regions),
    }


def priority(s: int) -> str:
    if s >= 70:
        return "Hot"
    if s >= 50:
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
