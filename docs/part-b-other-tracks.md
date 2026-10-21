# Part B: The tracks I didn't build

> The brief says "pick one of the five tracks" and lists four. I built Track 1, so these are Tracks 2, 3 and 4.
> Cost assumptions: Ticmint's scale is ~4 markets, ~10 competitors, a growth team of 1–3, a few hundred leads and a few thousand ad-platform rows a month. LLM costs are at small/fast-model prices (Gemini Flash / Haiku class), checked against their published per-token rates in Oct 2026, and rounded up.

## Track 2: Review-site sentiment agent

**Signal and source**
- New 1–3★ reviews of Eventbrite, Ticket Tailor, Platinumlist, TicketSource, Skiddle and Humanitix on **Trustpilot** (public pages, organisers write there about payouts and account holds), **Capterra/GetApp** and **G2** (reviewer role, company size and industry are shown). Polled daily. G2 and Capterra are behind Cloudflare, so in practice this needs a paid scraper actor (Apify) or manual CSV exports. Trustpilot's public business pages are fetchable.

**What it decides, and on what logic**
- Is the reviewer an **organiser** (not a ticket buyer)? On Trustpilot most Eventbrite 1★ reviews are buyers. Role words, "my event", payout language, and G2's role/company fields decide it.
- Which **specific complaint** (fees, payout hold, account suspension, support, refunds), extracted with a quote that must appear verbatim in the review, the same grounding check as Part A.
- **Enrichment confidence**: G2 gives "Event Manager, 11–50 employees, Events Services" plus first name and last initial. Matching that to a company or LinkedIn profile is a guess, so the agent scores the match and drops anything below "two independent fields agree".

**Action and approval**
- Drafts a message that answers *that* complaint (e.g. payout hold → "on Ticmint buyers pay into your own Stripe, so there's nothing to hold"), logs to Freshsales and the Sheet. **A human approves every send.** A cold message that quotes someone's review back to them is borderline creepy and close to review sites' terms, so the human checks tone and whether to reference the review at all.

**Failure mode that worries me most**
- **Wrong-person enrichment.** "Sarah K., Event Manager" matched to the wrong Sarah, who gets a message about a complaint she never made. That's reputational damage for little upside. The guard is confidence thresholds, and not mentioning the review unless identity is certain.

**Monthly cost:** Apify actors for G2/Capterra ≈ $30–50; LLM classification of ~2,000 reviews + 200 drafts ≈ $3; Hunter/Apollo free tiers for emails; GitHub Actions free. **≈ $35–60/month.**

## Track 3: Multi-tool orchestration ("what did we spend last week and what did it produce?")

**Signal and source**
- A plain-language question from the team (Slack or Claude), plus a scheduled Monday question. Sources: **Google Ads API, Meta Marketing API, LinkedIn Marketing API** (spend, clicks, conversions), **GA4 Data API** (sessions, sign-ups by source), **Freshsales API** (leads, SQLs, deals by source), **GSC** (organic). One custom MCP server per source, plus a **metrics MCP server** that holds the definitions.

**What it decides, and on what logic**
- **Query planning:** which sources, which date range, which timezone and currency (UAE/India/UK accounts report in different ones).
- **Definitions, not improvisation:** "produce" means Freshsales SQLs and first paid tickets, not platform-reported conversions. Those definitions live in a versioned semantic layer (YAML) that the LLM reads but can't change.
- **Join logic:** UTM → GA4 source → Freshsales lead source, with a reported match rate, so you see how much spend is unattributable.

**Action and approval**
- **Read-only.** It answers, shows the tool calls and the SQL behind every number, and flags gaps ("27% of SQLs have no source"). There's no approval step because it changes nothing. Pausing ads or moving budget is a different agent with different guardrails.

**Failure mode that worries me most**
- **A confidently wrong number that sounds right.** The LLM adds Meta's "conversions" to Freshsales SQLs, or mixes AED and INR. The rule: **the LLM never does arithmetic.** Tools return computed totals, and the answer must cite the tool output for every figure. A nightly reconciliation test compares the agent's answers to fixed queries.

**Monthly cost:** all APIs free (Google Ads needs an approved developer token); BigQuery free tier for joins (GA4 export is free); LLM ≈ 300 questions × ~20k tokens ≈ $5–15; hosting on a $5 VM or Cloud Run free tier. **≈ $10–25/month.**

## Track 4: Funnel measurement agent

**Signal and source**
- **Synthetic journeys** every hour: Playwright runs ticmint.com → pricing → "Start Creating Free" and "Book an Enterprise Demo" with a test UTM, and records which tags fire (GA4, Meta Pixel, LinkedIn Insight, GTM container IDs). The audit found two GTM containers, so the agent would have caught that on day one.
- **Volume monitors:** GA4 Data API event counts by hour (sign_up, generate_lead, purchase), compared against the same hour-of-week baseline.
- **Downstream reconciliation:** GA4 generate_lead vs Freshsales leads created vs Meta/Google reported conversions, daily.
- **Config diffs:** GTM API container versions, so any publish is diffed and attributed.

**What it decides, and on what logic**
- **Broken vs quiet:** a drop is "broken" if synthetic journeys fail or the ratio between stages (form submits ÷ leads created) breaks, and only "quiet" if all stages drop together (a low-traffic day). That ratio logic is what keeps alert fatigue down.
- **Severity** = revenue weight of the step × hours broken. A dead demo form is P1, a missing scroll event is P4.

**Action and approval**
- Slack alert with evidence (screenshot, network log, which tag, which GTM version changed and who published it), a GA4 annotation, and a ticket. **No automatic fixes to GTM.** A human publishes tag changes. The agent can also block a reporting run ("don't send the weekly report, lead counts are 40% under Freshsales") and that needs no approval, since it prevents bad data rather than creating it.

**Failure mode that worries me most**
- **Synthetic tests polluting the data they're protecting.** Test sign-ups landing in GA4, Meta audiences and Freshsales. Guard: a dedicated test email domain and UTM, filtered at GA4 (internal traffic rule), the CRM (auto-delete) and Meta (exclusion). The second worry is alerting so often that people mute the channel.

**Monthly cost:** GitHub Actions or a $5 VM for Playwright hourly; APIs free; LLM only to write the alert summary ≈ $2. **≈ $5–15/month.**
