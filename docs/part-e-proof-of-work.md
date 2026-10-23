# Part E: Proof of Work

> Every number below is already published in my [revenue casebook](https://dannygrowthmarketing.github.io/revenue-casebook/), with its source. Where the result isn't only mine, or the data has a known flaw, the row says so.

## 1. Pages I built (live)

| Page | What it is | What was mine | What I'd change now |
|---|---|---|---|
| [Revenue casebook](https://dannygrowthmarketing.github.io/revenue-casebook/) | Seven client cases, each with its numbers and what's still unproven | Everything: research, copy, design, build | Add a source line under every figure, not just per case |
| [MR Jewels Google Ads case study](https://dannygrowthmarketing.github.io/mrjewels-google-ads-case-study/) | 26-month account review from the Google Ads exports | Analysis, design, build | Separate my months from the inherited account history |
| [MR Jewels August 2026 review](https://dannygrowthmarketing.github.io/mrjewels-august-2026-report/) | Monthly business review: 16 sections, 22 charts | Analysis, design, build | Margin and Meta spend were never supplied; profit view is incomplete |
| [TONI&GUY July 2026 report](https://dannygrowthmarketing.github.io/toniguy-july-2026-report/) | Monthly report for a 16-salon network | Analysis, design, build | Tie every chart to till data, not platform data |
| [Audit journey](https://dannygrowthmarketing.github.io/audit-journey/) | My end-to-end audit method on a worked example | Method, copy, build | — |
| [This submission site](https://dannygrowthmarketing.github.io/ticmint-internet-listener/) | Live dashboard over the agent's committed data | Built with Claude Code, reviewed and corrected by me | — |

## 2. Campaigns I ran

**Platforms:** Google Ads (Search, Performance Max, Demand Gen), Meta Ads, LinkedIn Ads, Google Business Profile. Measurement in GA4, GTM, Looker Studio and HubSpot.

**ROAS.** The one account where I can show revenue-based ROAS is MR Jewels (D2C jewellery, Bengaluru):

| | Figure | Source and caveat |
|---|---|---|
| Max | **24.3×**, Performance Max | Google Ads, platform-reported purchase value, 9 Jul 2024 – 17 Aug 2026. Account lifetime, not only my tenure (I ran it from Aug 2026). PMax was 8.1% of spend and 43.8% of conversion value. |
| Average | **4.48×** blended | Same account and source. ₹62.9L spend, ₹2.82 Cr conversion value, 5,028 purchases. |
| My month | **₹303 CPA**, 1,351 conversions | Aug 2026, 1–17 Aug, after the brand Search rebuild and store PMax launch. |
| The catch | Treat ROAS as an upper bound | In my tracking audit (Sep 2026) I found purchases counted twice: Shopify app tag + GA4 import. |

The other accounts are measured on revenue, leads and cost, not ROAS:

| Account | Result | Source and caveat |
|---|---|---|
| [TONI&GUY Bangalore](https://dannygrowthmarketing.github.io/revenue-casebook/toni-and-guy.html), 16 salons | Revenue **+14.7%** vs same months 2025 (₹14.04 → ₹16.10 Cr), average bill **+21.6%**, Mar–Aug 2026 | Salon till data. Google spend also rose 74%, so not all of it is media efficiency. |
| [Elites Dental Care](https://dannygrowthmarketing.github.io/revenue-casebook/elites-dental.html) | Search CPC **₹79.45 → ₹21.20** after the 1 Oct rebuild | Google Ads. Booking tracking is still being set up, so no cost per booking yet. |
| [Gold Coins Club & Resort](https://dannygrowthmarketing.github.io/revenue-casebook/resort.html) | Found **52 of 55** Google "conversions" were map taps: real cost per lead ~₹580, not ₹95 | Google Ads vs the resort's sales dashboard. A measurement fix, not a growth claim. |
| [EveryWatch](https://dannygrowthmarketing.github.io/revenue-casebook/everywatch.html), global marketplace | Monthly new users **9,113 → 182,782**, Jan 2024 – May 2025 | GA4, all channels. No revenue claimed. |

## 3. Anything else I've built

- **This repo.** A lead-intelligence agent with a custom MCP server (14 tools), scheduled GitHub Actions runs and a self-refreshing Google Sheet. → [README](../README.md)
- **[Audit journey](https://dannygrowthmarketing.github.io/audit-journey/).** How I audit an account end to end, on a real prospect.
- **Client reporting in HTML.** Monthly reviews that join ad platforms, Shopify or till data, and CRM, published as pages instead of decks (links above).
