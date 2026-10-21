"""CRM hand-off. NOT CONNECTED in this deployment: no Freshsales credentials exist.

Design: the agent never pushes on its own. A person marks a lead "Accepted" in the
sheet's review_status, then calls export_to_crm with those lead ids (from Claude, or a
future workflow that reads the sheet). Without credentials, or with dry_run=True, the
payloads are written to data/crm_outbox.jsonl (git-ignored) so the mapping can be
checked before anything is connected.

To connect Freshsales: set FRESHSALES_DOMAIN (e.g. "ticmint" for ticmint.myfreshworks.com)
and FRESHSALES_API_KEY (Profile settings -> API settings) as GitHub secrets.
"""

import json
import os
from datetime import datetime, timezone

from .http import client
from . import store


def connected() -> bool:
    return bool(os.getenv("FRESHSALES_DOMAIN") and os.getenv("FRESHSALES_API_KEY"))


def to_freshsales(lead: dict) -> dict:
    """Map a sheet row to a Freshsales lead. Only public, already-visible fields."""
    return {
        "lead": {
            "last_name": lead.get("author") or "unknown",
            "company": {"name": (lead.get("organisation_hint") or "").removeprefix("unverified: ") or None},
            "lead_source_id": None,  # set to your 'Internet Listener' source id once created
            "description": (
                f"[{lead.get('priority')} {lead.get('score')}] {lead.get('problem')} on {lead.get('competitor')}\n"
                f"Evidence: \"{lead.get('evidence_quote')}\"\nWhy: {lead.get('why_contact')}\n"
                f"Source: {lead.get('url')}\nScore: {lead.get('score_explanation')}"
            ),
            "custom_field": {"cf_listener_lead_id": lead.get("lead_id"), "cf_icp_fit": lead.get("icp_fit")},
        }
    }


def export(leads: list[dict], dry_run: bool = True) -> dict:
    payloads = [to_freshsales(l) for l in leads]
    if dry_run or not connected():
        store.DATA.mkdir(parents=True, exist_ok=True)
        with (store.DATA / "crm_outbox.jsonl").open("a", encoding="utf-8") as f:
            for l, p in zip(leads, payloads):
                f.write(json.dumps({"at": datetime.now(timezone.utc).isoformat(), "lead_id": l["lead_id"], "payload": p}) + "\n")
        return {"mode": "dry_run" if connected() else "NOT CONNECTED (no Freshsales credentials): written to data/crm_outbox.jsonl",
                "count": len(payloads)}
    url = f"https://{os.environ['FRESHSALES_DOMAIN']}.myfreshworks.com/crm/sales/api/leads"
    headers = {"Authorization": f"Token token={os.environ['FRESHSALES_API_KEY']}", "Content-Type": "application/json"}
    results = []
    for l, p in zip(leads, payloads):
        r = client().post(url, headers=headers, json=p)
        results.append({"lead_id": l["lead_id"], "status": r.status_code})
    return {"mode": "live", "results": results}
