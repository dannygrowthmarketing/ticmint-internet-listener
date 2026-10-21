"""Second pass: an LLM reads the posts the rules shortlisted and decides
whether a real organiser is unhappy with a real platform.

Provider-agnostic: any OpenAI-compatible /chat/completions endpoint works.
Free options that work out of the box:
  - Groq        LLM_BASE_URL=https://api.groq.com/openai/v1          LLM_MODEL=llama-3.3-70b-versatile
  - Gemini      LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai  LLM_MODEL=gemini-2.5-flash
  - Ollama      LLM_BASE_URL=http://localhost:11434/v1               LLM_MODEL=llama3.1
With no LLM_API_KEY set, classify() returns None and the rules decide alone.

Hallucination guard: the model must quote the post. If the quote isn't in the
text, or it names a platform the post never mentions, we throw its answer away.
"""

import json
import os
import re

from .http import client

SYSTEM = """You qualify sales leads for Ticmint, a white-label event ticketing platform (organisers sell tickets on their own domain, keep attendee data, ~2% fee, built-in email/WhatsApp marketing). Markets: India, UK, UAE, US.

You will get one public post. Decide if the AUTHOR is an event organiser/promoter/venue (the person who sells tickets), not a ticket buyer, who is frustrated with, or shopping around for, a ticketing platform.

Reply with JSON only:
{
 "is_organiser": true|false,
 "frustrated_with_platform": true|false,
 "platform": "name exactly as written in the post, or null",
 "pain": "fees|payouts|support|data_ownership|account_risk|refunds|checkout_ux|other|none",
 "intent": "switching_now|evaluating|venting|none",
 "evidence_quote": "an exact substring of the post, max 200 chars, that proves the above",
 "event_type": "e.g. club nights, conference, festival, sports, community, unknown",
 "score": 0-100,
 "why_contact": "one sentence a salesperson can act on",
 "opener": "a 2-3 sentence reply that answers their exact complaint, mentions Ticmint once, no hype, no links"
}
Score guide: 85+ organiser actively switching; 60-84 organiser frustrated or evaluating; 30-59 unclear role or mild; <30 fan, developer, journalist, or unrelated. If unsure, score lower."""

_norm = re.compile(r"\s+")


def enabled() -> bool:
    return bool(os.getenv("LLM_API_KEY"))


def _n(s: str) -> str:
    return _norm.sub(" ", (s or "").lower()).strip()


def classify(post: dict) -> dict | None:
    if not enabled():
        return None
    base = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")
    model = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
    body = (post.get("title", "") + "\n\n" + post.get("text", ""))[:4000]
    r = client().post(
        f"{base}/chat/completions",
        headers={"Authorization": f"Bearer {os.environ['LLM_API_KEY']}"},
        json={
            "model": model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": f"Source: {post.get('source')} / {post.get('community')}\n\n{body}"},
            ],
        },
        timeout=60,
    )
    if r.status_code != 200:
        return {"error": f"HTTP {r.status_code}: {r.text[:200]}"}
    try:
        content = r.json()["choices"][0]["message"]["content"]
        out = json.loads(content[content.find("{"): content.rfind("}") + 1])
    except (KeyError, ValueError, IndexError) as e:
        return {"error": f"unparseable LLM reply: {e}"}
    return verify(out, body)


def verify(out: dict, body: str) -> dict:
    """Reject answers that aren't grounded in the post."""
    text = _n(body)
    quote = _n(out.get("evidence_quote", ""))
    problems = []
    if not quote or quote not in text:
        problems.append("evidence_quote not found in post")
    platform = out.get("platform")
    if platform and _n(platform) not in text:
        problems.append(f"platform '{platform}' not in post")
    try:
        out["score"] = max(0, min(100, int(out.get("score", 0))))
    except (TypeError, ValueError):
        problems.append("non-numeric score")
        out["score"] = 0
    out["grounded"] = not problems
    out["grounding_problems"] = problems
    return out
