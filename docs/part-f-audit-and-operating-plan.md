# Part F: Audit, operating plan and status

This section came out of a review of my own build on 21 Oct 2026. It has four jobs: say what was wrong, say what I changed and how I tested it, set out how the listener becomes a sales process, and separate what is proven from what is only planned. Every number below links to a file in the repo or is labelled as not measured yet.

## F1. Audit: what I found

I checked the repo, the workflow history, the committed data and the Google Sheet before changing anything.

| # | Area | Finding (verified) | Severity |
|---|---|---|---|
| 1 | Google Sheet | The sheet the README linked to was **empty**. The Apps Script that should fill it had never been run. | High: the deliverable "Sheet that refreshes on a schedule" did not exist |
| 2 | Scheduling | All 8 runs were `push`-triggered. The cron (`17 */6 * * *`) had never fired yet, because the repo was created at 08:2x UTC and the first slot is 12:17 UTC. "Runs on a schedule" was **configured, not proven**. | High |
| 3 | Metrics | The site showed "951 posts fetched". That was a sum over runs of re-fetched posts, so the same post counted up to 7 times. | High: misleading |
| 4 | Lead quality | One kept row was an HN comment about a **bomb threat at a venue**: it matched "sell tickets" with no organiser speaking. Scoring gave points for any competitor mention. | High |
| 5 | Scoring | Scores were a single opaque number. No per-criterion evidence, no confidence, no ICP fit, no next action. | Medium |
| 6 | LLM | 0 LLM calls ever. No `LLM_API_KEY` is set, so every verdict came from the rules. | Medium (disclosed) |
| 7 | Sources | Reddit returns 403/429 from GitHub Actions on every run. Bluesky has no credentials. Only HN and Mastodon work. | Medium (external) |
| 8 | Failure handling | A crash on one post would have aborted the run. Runs had no ok/partial/failed status. | Medium |
| 9 | Duplicates | De-duplication worked (seen-state + upsert), but there was no test for it. | Low |
| 10 | Human review | The sheet had a `status` column a refresh could overwrite in one of the two sync paths. | Medium |
| 11 | Dashboard | Did not separate discovered, processed, qualified; had no scheduled-run evidence. | Medium |
| 12 | Tests | 10 tests, none for failures, LLM errors, missing credentials or duplicates. | Medium |
| 13 | Run status | Found after the first fix: run 8 said `ok` although Reddit was rate-limited on most queries, because it answered one. | Medium |

## F2. What I changed, in priority order

1. **Sheet that fills itself.** A new sheet whose `Leads` and `Run log` tabs are `IMPORTDATA` formulas over the CSVs the agent commits. No keys, no script. A `Review` tab holds human decisions and is joined back by `lead_id`, so no refresh can overwrite them. `Hot queue` lists Hot and Warm rows. The old empty sheet is renamed "unused".
2. **Evidence-based scoring** ([`scoring.py`](../listener_mcp/scoring.py)). Six criteria, each with the matched text as evidence: organiser 0–30, platform 0–15, problem 0–25, switching or near-term intent 0–20, identity 0–5, ICP 0–5. A post with no first-person organiser language is capped at 49 (below Warm). Hot (≥ 70) needs organiser **and** problem evidence. A competitor name alone is worth 15 at most. Ticket-buyer, promotion and noise penalties. Every row carries `score_explanation`, e.g. `organiser 30 + platform 15 + problem 25 + intent 20 + icp 2 = 92`.
3. **Per-lead fields.** `confidence`, `icp_fit`, `organisation_hint` (marked unverified), `event_context`, `evidence_quote` (verbatim), `score_explanation`, `next_action`, `review_status`, plus the URL.
4. **Honest run accounting** ([`pipeline.py`](../agent/pipeline.py)). Each run logs `discovered`, `new`, `shortlisted`, `qualified`, Hot/Warm/Watch, LLM calls and errors, processing errors, per-source ok/failed/skipped and `status` (ok / partial / failed). A source with any error makes the run partial. A post whose processing crashes is not marked seen, so it is retried. Old rows are migrated on read.
5. **LLM safety.** The LLM can only lower or confirm: if it says "not an organiser" the post is dropped; its quote must be verbatim in the post and its platform must be named, otherwise the verdict is ignored. Timeouts fall back to rules.
6. **CRM interface, clearly unconnected.** `export_to_crm` maps leads to Freshsales fields and writes them to a local outbox, returning `NOT CONNECTED`. Nothing is sent anywhere.
7. **Dashboard.** Pipeline and run panels now show discovered vs processed vs qualified, unique prospects, reviewed, scheduled vs push runs (from the GitHub Actions API, shown as "unavailable" if that call fails), failed runs, last successful run and per-source status.

## F3. Tests

`python -m pytest -q` → **25 passed** (run in this environment on 21 Oct 2026, and on every push by the `test` workflow).

| File | What it proves |
|---|---|
| `test_scoring.py` (9) | Real fixtures: the suspended-account organiser scores Hot; the bomb-threat comment, promotions, digests and fan complaints are rejected |
| `test_mcp_end_to_end.py` (1) | The agent starts the MCP server over stdio and runs a full cycle twice through its tools; the second run adds nothing |
| `test_failures.py` (15) | Blocked source → partial and other sources kept; all sources down → failed; a crash on one post keeps the rest and retries it; source failing midway → partial; no duplicates; review status survives; missing credentials are skips; LLM timeout falls back; an invented quote is ignored; LLM cannot make a non-organiser Hot; competitor + anger without an organiser stays below Warm; every lead carries evidence; CRM export says unconnected |

What tests cannot prove: that real organisers will post often enough, or that a person agrees with the scores. Those need the review loop in F7.

## F4. Recommended initial segment

Scored 1–5 against the five criteria in the brief. These are my judgments from the research in Part D, not measured data.

| Segment | Public signal strength | Ticket volume | Product fit | Commercial value | Decision-maker easy to find | Total |
|---|---|---|---|---|---|---|
| **UAE/India mid-market recurring promoters and festivals** (on Platinumlist, District, BookMyShow) | 2 on social, **4 on event listings** | 4 | 5 | 5 | 4 | **20–22** |
| India sports federations and leagues | 2 | 4 | 4 | 4 | 3 | 17 |
| UK/US small organisers complaining about Eventbrite | **4** | 2 | 3 | 2 | 3 | 14 |
| Universities and student unions | 2 | 3 | 3 | 2 | 4 | 14 |
| Conferences and B2B events | 2 | 2 | 2 | 3 | 4 | 13 |

**Recommendation: start with UAE/India mid-market recurring promoters.** They sell enough tickets for a commission saving to matter, the founder or head of ticketing is usually named on the listing or Instagram, and Ticmint's strengths (white-label, own payouts, local support) are what marketplaces don't give them.

The honest tension: the listener as built finds its best public complaints in the *UK/US Eventbrite* segment, which is the weakest commercial fit. So the next source to build is an event-listing monitor for UAE/India (who is selling, how often, at what price), and the complaint listener stays on as a cheap secondary feed.

## F5. Workflow: from discovery to revenue

```
 discovery        public posts and listings (HN, Mastodon, Reddit*, Bluesky*, listings**)
     │
 filtering        relevance gate: ticketing or a named platform must appear
     │
 organiser ID     first-person organiser language required; buyers and promos penalised
     │
 qualification    problem + platform + intent evidence; optional LLM check, grounded
     │
 scoring          6 criteria, Hot ≥ 70 / Warm ≥ 50 / Watch, with explanation
     │
 Sheet / CRM      Sheet: live.  CRM: mapped, NOT CONNECTED (dry-run outbox)
     │
 human review     Review tab: Accepted / Rejected (reason) — nothing moves without it
     │
 approved outreach  a person replies in the public thread or uses a public business contact
     │
 demo → opportunity → customer → revenue      tracked in Review tab now, CRM later
```

\* blocked or not configured today. \*\* proposed, not built.

Rules that hold at every step:
- **No automatic messages.** The agent drafts an opener; a person decides whether to send it.
- **Public data only.** No logins, no private groups, no scraping behind access controls, no bypassing rate limits or blocks (Reddit's 403 is respected and logged, not evaded).
- **Minimum personal data.** Handle, public profile link and the post. No emails are collected or guessed.
- **Opt-out respected.** Anyone who says no is marked `Rejected: other` with a note and never contacted again.

## F6. Measurement framework

None of these have values yet beyond what the run log shows. Where a number exists it comes from `data/runs.csv` or `data/summary.json`.

**Operational (is the machine working?)**

| Metric | Definition | Source | Today |
|---|---|---|---|
| Collection success rate | source calls that returned data ÷ calls attempted, per source | runs.csv `sources_ok/failed` | HN, Mastodon OK; Reddit blocked; Bluesky skipped |
| Scheduled run success | scheduled runs with status ok or partial ÷ scheduled runs | Actions API + runs.csv | **Not measured yet** (first cron slot 12:17 UTC 21 Oct) |
| Relevant-post rate | shortlisted ÷ new | runs.csv | Per run in the log |
| Qualification rate | qualified ÷ new | runs.csv | Per run in the log |
| Duplicate rate | rows rejected as already seen ÷ discovered | `discovered − new` | Per run in the log |
| False-positive rate | Rejected ÷ reviewed | Review tab | **Unavailable** until leads are reviewed |
| Source availability | share of runs where each source answered | runs.csv | In the log |
| Cost per qualified lead | (LLM spend + paid APIs) ÷ qualified | provider bill | £0 today (free tiers, 0 LLM calls) |

**Sales (does it make money?)**

| Metric | Definition |
|---|---|
| Leads reviewed | rows with any review_status |
| Accepted | reviewed and judged a real organiser in ICP |
| Contacted (approved) | a person sent a message |
| Replies | the organiser answered |
| Demos booked | meeting held |
| Opportunities | pricing or migration discussed |
| Customers | signed |
| CAC | (tooling + time cost) ÷ customers from this channel |
| Revenue | first-year contract value from listener-sourced customers |

All sales metrics are **0 or not yet measured**. I will not report any of them until a real lead reaches that stage.

## F7. Feedback loop into scoring

1. Every week a person reviews all Hot and Warm rows in the `Review` tab.
2. Each rejection carries a reason (`not an organiser`, `not ICP`, `other`). The reason points at the criterion that was wrong.
3. Monthly, compare criterion scores between Accepted and Rejected rows. A criterion that scores high on rejected rows gets narrower patterns or less weight; phrases from accepted rows that the rules missed become new patterns, each with a fixture test.
4. Once there are ~200 reviewed rows, report precision per source and per tier, and move the Hot/Warm thresholds to where precision is acceptable.
5. Downstream statuses (replied, demo, customer) show which signals actually predict revenue; those criteria get more weight.

## F8. 30-60-90 day plan

**Days 1–30: make the signal trustworthy.**
Prove scheduled runs for two weeks. Add an LLM key and Reddit OAuth. Build the UAE/India event-listing monitor. Review every Hot/Warm row weekly. Goal: a measured false-positive rate and 20+ accepted organisers, or a clear finding that public signal is too thin.

**Days 31–60: turn signal into conversations.**
Connect Freshsales (Accepted rows only). Run approved, personalised outreach to accepted organisers, starting with the UAE/India segment. Track replies and demos in the CRM. Retune scoring from the first month of reviews.

**Days 61–90: decide on scale.**
Compare cost per demo and demo-to-opportunity rate against other channels in Part D. If it earns its place: add sources and segments, a daily digest for sales, and a monthly scoring review. If it doesn't: keep the listing monitor (it doubles as market intelligence) and drop the complaint listener.

## F9. Status: what is true today

| Status | Item | Evidence |
|---|---|---|
| **Implemented and verified** | Custom MCP server with 14 tools, driven over stdio by the agent | `test_mcp_end_to_end.py`; every Actions run log prints the tool list |
| | GitHub Actions job runs, scores, commits data | 8+ runs in [`data/runs.csv`](../data/runs.csv), all `push`-triggered |
| | Evidence-based scoring, failure handling, de-duplication, review preservation | 25 passing tests |
| | Live site | https://dannygrowthmarketing.github.io/ticmint-internet-listener/ (fetched after deploy) |
| | Google Sheet exists with IMPORTDATA formulas, shared with Daniel | Drive file 1IJpp71O… |
| **Implemented, not yet verified** | **Scheduled (cron) runs** | Workflow is active with cron `17 */6 * * *` on `main`, but the first slot (12:17 UTC, 21 Oct) produced **no run** (Actions API checked 12:41 UTC). GitHub runs cron on a best-effort basis and often skips or delays the first slots on a new repo. Marked verified only when a `schedule` run appears in the Actions history |
| | Sheet data actually loading | Shows `#REF!` until an editor clicks **Allow access** |
| | LLM qualification | Code and tests exist; 0 real calls (no key) |
| | Bluesky source | Code exists; no credentials |
| **Proposed** | Event-listing monitor, Freshsales sync, company enrichment, weekly digest, feedback re-weighting | Sections F7, F8 and README "What I'd build next" |
| **Blocked** | Reddit | 403/429 from GitHub Actions IPs; needs Reddit OAuth app |
| | CRM | No Freshsales credentials; export runs in dry-run mode and says NOT CONNECTED |

**Real results so far:** one genuine Hot lead (an organiser whose Eventbrite account was suspended days before an event). No one has been contacted. No demos, opportunities, customers or revenue.

## F10. Readiness checklist

- [x] Repo public, MCP server, agent, tests, README
- [x] Tests pass locally and in CI
- [x] Site deployed and reachable
- [x] Sheet created and shared
- [ ] An editor clicks **Allow access** in the sheet so the formulas load
- [ ] Sheet link sharing set to "Anyone with the link: Viewer" (so reviewers can open it)
- [ ] First scheduled run confirmed in the Actions history
- [ ] `LLM_API_KEY` (and `LLM_BASE_URL`, `LLM_MODEL`) set as repo secrets/variables
- [ ] Optional: `BSKY_HANDLE`/`BSKY_APP_PASSWORD`, `REDDIT_CLIENT_ID`/`REDDIT_CLIENT_SECRET`
- [ ] Part E personal figures filled in by Daniel
- [ ] Walkthrough video link added

## F11. How I'd explain it in the interview (two minutes)

"I built a listener that reads public posts where event organisers complain about their ticketing platform. A custom MCP server exposes the search, scoring, storage and Sheet steps as tools, and a scheduled GitHub Actions job drives them. Every run is logged with what it found, what failed and why.

The first version was too generous. It kept a comment about a bomb threat because it said 'sell tickets', and it counted the same posts several times in the headline number. So I rebuilt the scoring around evidence: a post only gets far if an organiser is speaking in the first person, about a real problem, with a platform named. Each score shows its sum. The LLM is optional and can only confirm or reject, and if it invents a quote it's ignored.

It works on two sources today. Reddit blocks cloud servers, and I chose to log that rather than work around it. So far it has found one real lead. Nobody has been contacted, because outreach needs a person to approve it. The bigger lesson is that the best buyers for Ticmint, mid-market promoters in the UAE and India, don't complain on Reddit. The next thing I'd build is a monitor of their event listings, which tells you who is selling, how often, and roughly how much commission they're paying."
