# Ticmint Internet Listener

An agent that watches the public internet for **event organisers who are frustrated with their ticketing platform**, works out who they are and why they're worth contacting, and writes them to a Google Sheet that refreshes itself every few hours.

Built for the Ticmint Growth Lead assignment (Part A, Track 1). The written parts are in [`docs/`](docs/) and on the [submission site](https://dannygrowthmarketing.github.io/ticmint-internet-listener/).

| | |
|---|---|
| **Live sheet** | [Ticmint Internet Listener - Leads (live)](https://docs.google.com/spreadsheets/d/1IJpp71OWmk4y0dG08GXMCCMugbN1IB-gEDJSOBHl1BI/edit): tabs `Leads`, `Review`, `Hot queue`, `Run log`, `About`. Leads and Run log pull the repo CSVs with `IMPORTDATA` (Google refreshes roughly hourly); the Review tab is human-only and never overwritten |
| **Proof it runs on its own** | [`data/runs.csv`](data/runs.csv) (one row per run) and the [`listen` workflow history](https://github.com/dannygrowthmarketing/ticmint-internet-listener/actions/workflows/listen.yml) |
| **Schedule** | GitHub Actions cron `17 */6 * * *` (every 6 hours), plus on every change to the agent's code |
| **Custom MCP server** | [`listener_mcp/server.py`](listener_mcp/server.py): 14 tools, 1 resource, 1 prompt |

---

## What a row looks like

*Illustrative, based on a real r/EventbriteSupport post the listener found in run 4 (that post is now a test fixture). Live rows are in the sheet.*

| priority | score | source | competitor | pain | quote | why_contact | suggested_opener |
|---|---|---|---|---|---|---|---|
| Hot | 95 | reddit · r/EventbriteSupport | Eventbrite | account_risk | "My eventbrite account wss suspended… support hasn't replied. My event is on Saturday." | Organiser voice; on Eventbrite; unhappy about account suspension; region: … | "That sounds stressful, having Eventbrite pull the event. If you need a backup ticket page live today on your own domain, I can help you get one up for free." |

Each row also carries the author's handle and profile link, public profile context (karma or followers, account age, bio), the post URL and date, which scorer decided (`rules` or `rules+llm`), plus `review_status`, `confidence`, `icp_fit`, `evidence_quote`, `score_explanation` and `next_action`. Human review lives in the sheet's `Review` tab and survives every refresh.

---

## Architecture

```
          GitHub Actions cron (every 6h)  ──or──  Claude Desktop / Claude Code (ask in plain English)
                     │                                          │
                     ▼                                          │
        agent/run.py  (MCP client, ~60 lines)                   │
                     │  stdio, JSON-RPC                         │
                     ▼                                          ▼
   ┌──────────────── listener_mcp/server.py  (custom MCP server) ────────────────┐
   │  collect        search_source(hackernews|reddit|bluesky|mastodon, query)    │
   │  de-duplicate   filter_unseen · mark_seen                                   │
   │  judge          score_post (rules) → qualify_post (rules → LLM → grounding  │
   │                 check → enrich_author)                                      │
   │  persist        save_leads · log_run · sync_sheet                           │
   │  ask            query_leads · lead_stats · run_listener · weekly_digest     │
   └─────┬───────────────┬────────────────────┬───────────────────────┬─────────┘
         ▼               ▼                    ▼                       ▼
   HN Algolia API   Reddit (OAuth → PullPush   LLM (any OpenAI-       data/*.csv (committed
   Mastodon tags    → RSS fallbacks)           compatible endpoint:   back to the repo) ──▶ Google Sheet
   Bluesky search                              Gemini/Groq free)      Sheets API (push) or Apps Script (pull)
```

**What talks to what.** The scheduled job doesn't call any API itself. `agent/run.py` launches the MCP server as a subprocess, lists its tools, and runs the cycle in [`agent/pipeline.py`](agent/pipeline.py) entirely through `call_tool`. The server owns all I/O and all judgment. Because of that, the same server plugged into Claude Desktop answers questions against the same data:

> "Who complained about Eventbrite payouts in the UK this week, and what should I say to the top one?"
> → `query_leads(pain="payouts", region="UK", days=7)` → the rows, with openers.

**Where the LLM sits.** In one place: `qualify_post`, after the rules and only for posts the rules shortlisted (score ≥ 30, max 40 per run). It returns structured JSON (is this an organiser, which platform, which pain, buying intent, an evidence quote, a score, a reason, an opener). Then a **grounding check** runs: the quote must appear verbatim in the post and the named platform must appear in the text, or the LLM's answer is thrown away and the rules decide. Final score = 0.4 × rules + 0.6 × LLM. If the LLM says "not an organiser", the post is dropped.

**What triggers a run.** The cron schedule; a push that changes `listener_mcp/`, `agent/` or `config/`; the "Run workflow" button; or `run_listener` from a chat client.

**Why rules first.** Rules are free, deterministic and unit-tested ([`tests/`](tests/)). They also keep LLM cost flat however noisy the sources get, and they keep producing rows when a free LLM tier runs out. In that case the bar rises from 30 to 45, because there's no second opinion.

### MCP tools

| Tool | What it does |
|---|---|
| `search_source` | Search one source; returns normalised posts. Errors come back as data so one blocked source never stops a run |
| `filter_unseen` / `mark_seen` | De-duplicate against every previous run (`data/state.json`) |
| `score_post` | Rule score 0–100 with the features that produced it |
| `enrich_author` | Public profile: karma/followers, account age, bio, links |
| `qualify_post` | Rules → LLM → grounding check → enrichment → a sheet-ready row |
| `save_leads` | Upsert into `data/leads.csv`, keeping human statuses |
| `log_run` | Upsert the run's row into `data/runs.csv` |
| `sync_sheet` | Push Leads + Run log to Google Sheets (statuses typed in the sheet win) |
| `query_leads` / `lead_stats` | Ask questions of the stored leads |
| `run_listener` | Whole cycle from a chat client |
| resource `listener://watchlist` / prompt `weekly_digest` | The config, and a stand-up digest template |

What it listens for (queries, communities, the 23 competitors and their aliases) lives in [`config/watchlist.yaml`](config/watchlist.yaml), not in code.

---

## Setup

### 1. Run it locally (2 minutes, no keys)

```bash
git clone https://github.com/dannygrowthmarketing/ticmint-internet-listener && cd ticmint-internet-listener
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt pytest
python -m pytest -q             # 25 tests, including a full MCP round-trip on fixtures
python -m agent.run             # one live cycle: HN + Mastodon (+ Reddit if your IP isn't blocked)
```

Output goes to `data/leads.csv` and `data/runs.csv`. Every key below is optional, and each one switches on one more capability.

### 2. Use the MCP server from Claude Desktop or Claude Code

```json
{
  "mcpServers": {
    "ticmint-listener": {
      "command": "/path/to/ticmint-internet-listener/.venv/bin/python",
      "args": ["-m", "listener_mcp.server"],
      "cwd": "/path/to/ticmint-internet-listener",
      "env": { "PYTHONPATH": "/path/to/ticmint-internet-listener" }
    }
  }
}
```

Claude Code: `claude mcp add ticmint-listener -- python -m listener_mcp.server` from the repo root.

### 3. Turn on the schedule (fork → Actions)

Fork the repo and enable Actions. The `listen` workflow already has a cron. Under **Settings → Secrets and variables → Actions** you can add:

| Name | Type | Gives you | Where to get it (free) |
|---|---|---|---|
| `LLM_API_KEY` | secret | LLM qualification + tailored openers | Gemini: aistudio.google.com/apikey, or Groq: console.groq.com |
| `LLM_BASE_URL`, `LLM_MODEL` | variables | Choice of provider | Gemini: `https://generativelanguage.googleapis.com/v1beta/openai`, `gemini-2.5-flash`. Groq (default): `https://api.groq.com/openai/v1`, `llama-3.3-70b-versatile` |
| `BSKY_HANDLE`, `BSKY_APP_PASSWORD` | secrets | Bluesky search | bsky.app → Settings → App passwords |
| `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET` | secrets | Reliable Reddit (see "Where it breaks") | reddit.com/prefs/apps → "script" app |
| `GOOGLE_SERVICE_ACCOUNT_JSON` + `SHEET_ID` (variable) | secret | Push straight to the Sheet | Option B below |

### 4. Connect the Google Sheet (pick one)

**Option A: formula pull (no keys, no code). This is what the live sheet uses.**
`Leads!A1` is `=IMPORTDATA("https://raw.githubusercontent.com/<owner>/<repo>/main/data/leads.csv")` and `Run log!A1` does the same for `runs.csv`. Google re-fetches them about once an hour, so the sheet follows every committed run with nobody touching it. The first time the file is opened, an editor has to click **Allow access** on the "external data" banner; until then the cells show `#REF!`. Reviews go in the `Review` tab (lead_id + a dropdown status) and are joined back onto `Leads` by a `VLOOKUP`, so a refresh can never overwrite them. `Hot queue` is a `QUERY` over `Leads` for Hot and Warm rows.

**Option A2: Apps Script pull.** If formulas aren't allowed in your Workspace: Sheet → Extensions → Apps Script → paste [`apps_script/Code.gs`](apps_script/Code.gs) → run `setup` once → approve. An hourly trigger rewrites the tabs and keeps typed statuses.

**Option B: service-account push (the agent writes the sheet itself).**
Google Cloud console → new project → enable the Google Sheets API → create a service account → Keys → add a JSON key. Share the sheet with the service account's `client_email` as Editor. Add the JSON as the `GOOGLE_SERVICE_ACCOUNT_JSON` secret and the sheet ID (the long string in its URL) as the `SHEET_ID` variable. `sync_sheet` then writes both tabs at the end of every run.

---

## Where it breaks

These are from running it, not from guessing. Every run's errors are in [`data/runs.csv`](data/runs.csv).

- **Reddit blocks cloud IPs.** From GitHub Actions, `reddit.com/search.json` returns **403** on every run, PullPush (the public Reddit archive) returns **403** on most calls, and the RSS feed returns **429**. Reddit is where organisers complain most, so this is the biggest gap. The fix is OAuth credentials (a free "script" app, 100 requests/min). Reddit has tightened API approvals, so plan for a short wait, or run the job from a residential IP (a $5 VM won't do; a home machine or a proxy will).
- **Signal is sparse and the rules are blunt.** Run 1 kept 31 rows that were all noise (HN essays, conference-design blogs matching "support"). Run 4 kept 9 "Warm" rows that were organisers happily *advertising* events on Eventbrite, while a genuine lead (account suspended five days before an event) scored only 55. Run 5 still kept long event digests that mention Eventbrite once and "recommend" somewhere unrelated, so sentiment is now judged only within ±250 characters of the platform mention. Each fix came with a fixture test. By run 7 the rules kept 2 of 162 posts, one of them the genuine Hot lead. They'll keep missing new phrasings, though. The LLM pass is what makes precision acceptable. Without a key, expect more false positives.
- **The schedule isn't proven yet.** Runs 1–9 were all started by code pushes. The first cron slot (12:17 UTC, 21 Oct) produced no run, although the workflow is active and the cron is on `main`. GitHub treats cron as best effort and commonly drops early or peak-time slots. If slots keep being skipped, the fallback is an external scheduler calling `workflow_dispatch`.
- **Run accounting lied once.** Run 8 (21 Oct, 09:18 UTC) logged `status: ok` although Reddit had returned 429 on most queries: Reddit answered its first query, so it counted as a working source. Any source error now makes a run `partial`; old rows are corrected on read and a test reproduces the case.
- **Hallucination risk.** The LLM can invent a quote, a platform or a pain. The grounding check rejects any answer whose quote isn't verbatim in the post or whose platform isn't mentioned, and marks the row `rules (LLM rejected: …)`. What it *can't* catch is a plausible but wrong judgment ("is an organiser" when the author is a ticket buyer writing in the first person). That's why a human reads the row before any outreach.
- **Auth expiry.** Bluesky sessions are created per run, so there's nothing to expire. A Reddit OAuth token is refreshed per run. A rotated Google service-account key or an un-shared sheet makes `sync_sheet` return `error: …` in the run log. The CSVs still update and the Apps Script path keeps working. Free LLM tiers rate-limit (Gemini free: ~10 RPM). Each error is logged and the row falls back to rules.
- **Cost at scale.** Today it's free: Actions minutes on a public repo, free APIs, ≤ 40 LLM calls per run × 4 runs/day ≈ 5k calls/month, inside free tiers. At 10× the queries on a paid model it's roughly 50k classifications × ~1.2k tokens ≈ 60M tokens/month ≈ **$5–20/month** on a Flash/Haiku-class model. Cost isn't the constraint; source access is.
- **Fragile by design.** Mastodon full-text search isn't public, so it reads hashtag timelines only. HN Algolia's fuzzy matching returns off-topic comments, which the relevance gate drops. `data/state.json` lives in git, so two simultaneous runs could race (prevented with a `concurrency` group). Region detection is keyword-based ("London", "₹", "DTCM") and leaves most rows blank.
- **Compliance.** It only reads public posts and suggests replies. It never sends. Before automating sends: GDPR/PECR in the UK (legitimate-interest assessment, opt-out in every message), and each platform's rules on unsolicited DMs.

## Two calls, for the walkthrough

- **The one I'd defend:** *rules before LLM, with a grounding check after.* It's cheaper, testable, keeps running when the free tier dies, and it caught its own mistakes in public (the commit history shows each fix with the run that exposed it). An "LLM reads everything" design would have hidden runs 1 and 4 behind fluent summaries.
- **The one I'm unsure about:** *listening to public social platforms at all for this ICP.* Ticmint's primary buyers (UAE/India mid-market promoters, Part D) mostly complain in WhatsApp groups and to peers, not on Reddit. The richer signal is probably an **event-listing monitor** (organisers announcing events on Platinumlist/District/Eventbrite, with dates and prices), which is the first thing on the list below.

## What I'd build next week

1. **Event-listing monitor**: a second source tool reading new UAE/India listings on Platinumlist, District and Eventbrite. Output: organiser, event date, price tiers, capacity, estimated commission paid. That becomes the Tier 1/2 outbound trigger in Part D3.
2. **Reddit OAuth + Trustpilot organiser reviews**, to close the biggest source gap.
3. **Freshsales sync**: Hot rows become Freshsales leads with the quote and opener in a note, deduped by handle/domain. Statuses flow back to the sheet.
4. **Company enrichment**: follow bio links to a website, then pull domain, country and team size from the site and its public LinkedIn page, so a Reddit handle becomes an account.
5. **Feedback loop**: use the `status` column ("contacted", "replied", "not a fit") to re-weight rules monthly and build a 200-row labelled set for measuring precision and recall per source.
6. **Daily Slack/WhatsApp digest** of Hot rows using the `weekly_digest` prompt.

## Repo map

```
listener_mcp/       the MCP server: server.py (tools), scoring.py (rules), llm.py (LLM + grounding),
                    sources/ (hackernews, reddit, bluesky, mastodon), store.py, sheets.py, http.py
agent/              run.py (MCP client entry point), pipeline.py (the cycle, as tool calls)
config/             watchlist.yaml: queries, communities, competitors
data/               leads.csv, runs.csv, state.json (written by the scheduled job)
apps_script/        Code.gs: the no-key Sheet refresher
docs/               Parts B–E, the AI-use note, and the submission site
tests/              rules, grounding check, full MCP round-trip twice (proves de-dup)
```
