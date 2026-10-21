"""Google Sheets sink (push model).

Needs two env vars:
  GOOGLE_SERVICE_ACCOUNT_JSON  the service account key, as JSON text
  SHEET_ID                     the spreadsheet id from its URL; share the sheet
                               with the service account's client_email as Editor

Tabs written: "Leads" (full rewrite, sorted, keeps the review_status a human
typed into the sheet) and "Run log" (one row per run). A full rewrite costs
two API calls per tab, well inside the free 300 requests/minute quota.
"""

import json
import os

from .store import LEAD_COLUMNS, RUN_COLUMNS

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def enabled() -> bool:
    return bool(os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON") and os.getenv("SHEET_ID"))


def _book():
    import gspread
    from google.oauth2.service_account import Credentials

    info = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
    gc = gspread.authorize(Credentials.from_service_account_info(info, scopes=SCOPES))
    return gc.open_by_key(os.environ["SHEET_ID"])


def _tab(book, title: str, cols: int):
    import gspread

    try:
        return book.worksheet(title)
    except gspread.WorksheetNotFound:
        return book.add_worksheet(title=title, rows=1000, cols=cols)


def sync(leads: list[dict], runs: list[dict]) -> str:
    if not enabled():
        return "skipped (no GOOGLE_SERVICE_ACCOUNT_JSON/SHEET_ID)"
    book = _book()

    ws = _tab(book, "Leads", len(LEAD_COLUMNS))
    # Preserve statuses typed by a human in the sheet ("contacted", "not a fit" ...)
    current = ws.get_all_values()
    if current and "lead_id" in current[0] and "review_status" in current[0]:
        i_id, i_st = current[0].index("lead_id"), current[0].index("review_status")
        typed = {r[i_id]: r[i_st] for r in current[1:] if len(r) > max(i_id, i_st) and r[i_st]}
        for lead in leads:
            if lead["lead_id"] in typed:
                lead["review_status"] = typed[lead["lead_id"]]
    values = [LEAD_COLUMNS] + [[str(l.get(c, "")) for c in LEAD_COLUMNS] for l in leads]
    ws.clear()
    ws.update(values=values, range_name="A1", value_input_option="RAW")
    ws.freeze(rows=1)

    rl = _tab(book, "Run log", len(RUN_COLUMNS))
    rl.clear()
    rl.update(values=[RUN_COLUMNS] + [[r.get(c, "") for c in RUN_COLUMNS] for r in reversed(runs)],
              range_name="A1", value_input_option="RAW")
    rl.freeze(rows=1)
    return f"ok ({len(leads)} leads, {len(runs)} runs)"
