# Part D: Growth Strategy

> **Assumptions I'm making throughout** (none of these are public, so I state them):
> Ticmint's revenue is mostly the platform fee on paid tickets, so an account's value ≈ annual ticket GMV × take rate (5% Starter, 2% Growth, custom 1.5–7% Enterprise). Today's GMV is concentrated in a handful of enterprise accounts (BAI, BFI, CaribTix). There is one small growth team. Paid acquisition has been paused since August 2026, and GA4 data is unreliable because of the duplicate GTM container. If any of these is wrong, D1 and D5 are what change first.

## D1. ICP

### Segments

| Segment | Example | Tickets / yr | Est. annual value to Ticmint* | Sales cycle | Who they use now | Ticmint's right to win |
|---|---|---|---|---|---|---|
| A. Sports federations & leagues (India) | BAI, BFI, state associations, franchise leagues | 20k–200k | $15k–100k | 3–9 months, committee | BookMyShow, District, Paytm Insider, in-house | **Proven** (India Open, BFI), ISO/SOC 2 |
| B. Mid-market promoters & festivals (UAE + India) | Recurring concert/club promoters, cultural & wellness festivals, community mega-events (Onam, Pooram) | 5k–150k | $5k–60k | 3–8 weeks, founder decides | Platinumlist, Virgin Megastore Tickets, District, BookMyShow | DTCM authorisation, data ownership, WhatsApp marketing, Peak Longevity / TEDx proof |
| C. Conferences & B2B events (UAE, UK, India) | TEDx chapters, industry conferences | 500–10k | $1k–8k | 2–6 weeks | Eventbrite, Platinumlist, KonfHub | DTCM, branded checkout |
| D. White-label resellers | CaribTix, Ticketing Nation | 100k+ | $50k+ | 6–12 months | Their own stack / vivenu / Eventcube | API, infra, already done once |
| E. UK/US self-serve small organisers | Club nights, comedy, community | < 5k | < $1k | Self-serve | Eventbrite, Ticket Tailor, DICE | Weak on price vs Ticket Tailor's flat fee |
| F. Venues, colleges, marathons | Theatres, college fests, race series | varies | $1k–20k | varies | mixed | SkyAim, ITFoK proof |

\* GMV estimates assume ₹600–1,500 / AED 100–300 average ticket price and a 2–4% blended take. They're for ranking segments against each other, not for forecasting.

### Primary ICP: B. Mid-market recurring promoters and festivals in the UAE and India, currently on a marketplace

- **Why this one now:** *Urgency*: they live on an on-sale calendar, so every upcoming event is a deadline. *Budget*: they already pay marketplace commissions of roughly 8–15% (Ticmint's own ads quote "10–15%"), so the saving funds the switch. *Sales cycle*: weeks, and one founder decides. *Expansion*: every new event, city and add-on (WhatsApp, refund guarantee, affiliates) grows the account. *Proof*: Peak Longevity (3.1× revenue), TEDx Emirates Hills (moved off Platinumlist), Afroloud. *Moat*: DTCM permits in Dubai, which global players don't help with.
- **Company profile:** 2–30 staff, 4–40 events a year, 5k–150k tickets, at least one flagship event over 2,000 capacity, active Instagram audience, selling through Platinumlist/District/BookMyShow or a clunky self-built page.
- **Buyer roles:** Founder/managing partner (decides), head of marketing (cares about data and the pixel), ops/production lead (cares about gate scanning and day-of risk), finance (cares about payout timing and fees).
- **Core pain:** "The marketplace owns my audience and takes 10%+ of every ticket. I can't retarget my own buyers, I get paid after the event, and my brand disappears inside theirs."
- **What triggers a buying decision:** a newly announced event that isn't on sale yet (a 30–90 day window); a bad on-sale (crash, queue, fraud); a payout delay; a renewal or exclusivity contract ending; a new DTCM permit cycle; a first event in a new city.

### Secondary ICP: A. Sports federations, state associations and leagues in India

- **Why second, not first:** the best proof and the biggest accounts, but cycles are slow (committees, tenders, sponsor approvals), there are few buyers, and the calendar is seasonal. It's a pipeline that pays in 6–9 months, so it runs in parallel and gets founder time rather than volume tactics.
- **Company profile:** national federations, the ~30 state associations under each one (badminton, basketball, kabaddi, volleyball, athletics), and franchise leagues.
- **Buyer roles:** secretary general / CEO (signs), commercial or marketing head (champions), sponsor and broadcast partners (influence), tech/finance committee (approves).
- **Core pain:** moving from free entry to paid ticketing without empty stands, fraud at the gate, and no fan data to show sponsors.
- **Trigger:** a tournament awarded or scheduled; a federation-level partner announcement (BAI → state associations is a ready referral path); sponsor demands for fan data; a bad ticketing experience at the last edition.

**Explicitly not primary:** UK/US self-serve (E). Against Ticket Tailor's flat 22–60p/ticket, a 2% fee loses on any ticket above roughly £11–30, so price isn't a wedge there. These organisers are served by self-serve and SEO, with no outbound and no paid prospecting.

---

## D2. Channel prioritisation

**Available:** SEO, AEO/GEO, Google Search (brand + conquest), Meta (prospecting, retargeting), LinkedIn Ads, outbound (email, LinkedIn, WhatsApp), partnerships (DTCM permit consultants, event agencies, venues, federations), review sites, referral and the "Powered by Ticmint" loop on every event page, PR, founder-led LinkedIn, events/trade shows, affiliates, communities.

**The pick for the next two quarters:**

| Channel | Job | Why it fits the primary ICP | 90-day success |
|---|---|---|---|
| **1. Signal-led outbound** (email + LinkedIn + WhatsApp where it's the business norm) | Pipeline | Promoters announce events publicly, *on competitor marketplaces*. Every Platinumlist/District listing is a named organiser, a ticket price, a capacity and an on-sale date: the trigger in D1. Add the Part A listener for frustration signals. Few, high-value accounts suit outbound better than ads. | 300 accounts worked, ≥ 4% positive reply, 25 qualified meetings, 8 SQLs, 3 organisers live with a paid on-sale |
| **2. Bottom-funnel search: comparison pages + Google conquest** | Capture | The best ad Ticmint ever ran was "Platinumlist keeps your attendee data. Ticmint gives it back." Restart it, extend it to District/BookMyShow/Virgin, and point it at honest comparison pages with a fee calculator. These pages also become the sources answer engines cite (Part C). | 5 comparison pages live, conquest CPA per demo known per market, ≥ 20 demo requests, cost per SQL measured on clean (single-GTM) tracking |
| **3. Proof engine: reviews + case studies + founder LinkedIn** | Trust | Outbound and conquest ads both fail without proof at the click. 0 Capterra reviews next to Ticket Tailor's 596 kills deals and AI visibility. Founder posts on BAI/BFI/Peak Longevity reach the exact federation and promoter network. | 50 reviews across G2 + Capterra, 4 case studies in text with schema, 2 founder posts/week, Ticmint named in ≥ 3 third-party "best ticketing" lists |

**What I'm explicitly not doing, and why:**

- **Meta prospecting at organisers.** Organisers are a small professional audience inside a consumer platform. The pixel is useful for retargeting site visitors (cheap, keep it), not for finding new promoters.
- **LinkedIn Ads at volume.** CPCs are high and the UAE/India promoter audience on LinkedIn is thin. I'd use it only for small ABM bursts to named federation lists (secondary ICP) in Q2.
- **UK/US expansion pushes.** The fee wedge breaks against Ticket Tailor, and Eventbrite owns discovery. Self-serve + SEO only.
- **More blog volume.** 110 posts already. The next 10 pages should be comparisons and case studies, not post 111.
- **Trade-show booths.** Expensive and slow to attribute. Attend to walk the floor and book meetings from the outbound list instead.
- **The NFT/blockchain story.** Retire it everywhere it still appears.

---

## D3. Cold outreach motion (primary ICP)

### Who's worth contacting

**Contact** if all of: an upcoming event 30–120 days out (announced, not yet on sale, or on sale on a marketplace); recurring (≥ 3 events a year, or an annual flagship); estimated ≥ 3,000 tickets a year; a named decision-maker we can find; based in the UAE or India.

**Boost** (move up a tier): a public frustration signal (Part A listener), a recent bad on-sale, a first event in Dubai (DTCM pain), a competitor the audit has a sharp story against (Platinumlist).

**Ignore:** one-off or free events, under ~1,000 tickets a year (send to self-serve), venue-tied exclusive ticketing (they can't switch), organisers who switched platforms in the last 6 months, fans, students without an event, agencies reselling someone else's event.

### Sequence (14–21 days, three tiers by expected value)

| Day | Step | Content |
|---|---|---|
| 0 | Email 1 + LinkedIn profile view | The trigger, the maths, one question. *"Saw [Event] is on Platinumlist for [date]. At [AED price] × ~[capacity], commission is roughly AED [X]. On Ticmint it'd be ~AED [Y], on your own domain, with the buyer list yours. Worth a 15-minute look before on-sale?"* |
| 2 | LinkedIn connect | No pitch, just the context line |
| 4 | Email 2 | Proof from the same segment: Peak Longevity 3.1× revenue / TEDx Emirates Hills moved off Platinumlist with DTCM handled |
| 7 | LinkedIn message or 40-second voice note | One question: "Who handles ticketing for [Event]?" |
| 10 | Email 3 | An asset made *for them*: a mock branded ticket page on their domain style (Ticmint can generate this in minutes) or their fee calculation as a PDF |
| 14 | WhatsApp (only to a published business number, UAE/India norm) | Short, with an opt-out |
| 21 | Break-up email | "Closing the loop. If timing's wrong, want me to check back before [next event]?" |

**Tier 1 (top 50 accounts by value):** fully hand-written by me, founder cc'd where there's a mutual connection. **Tier 2 (next 250):** variables computed, one human-written line each. **Tier 3:** listener and trigger-sourced long tail, mostly templated, human-approved in batches.

### Personalisation at volume without mail-merge theatre

The personalisation is **the maths and the trigger, not flattery.** "Loved your recent post!" is theatre. "Your 4,000-ticket night on the 14th will cost you ~AED 60k in commission" is information they can't easily get anywhere else. Every variable is computed from public data: listing price tiers, venue capacity, event date and the marketplace's fee range. The line between that and theatre is simple: if the variable could be swapped into another prospect's email unchanged, it isn't personalisation.

### How it connects to the agent I built

The Part A listener is the **frustration signal** for Tier 2/3, and its Sheet is already the working queue: Hot/Warm leads with the exact quote, the competitor, the pain, and a reply that answers that complaint. The next build (in the README) is an **event-listing monitor**: the same MCP server pattern, reading new Platinumlist/District/Eventbrite listings for UAE/India, which turns "upcoming event on a competitor" into rows with organiser, date, price and estimated commission. That feed is the Tier 1/2 trigger. The listener alone won't fill the pipeline. Most promoters complain to peers, not on Reddit, so it's a booster, not the engine.

### Measure, and when to kill it

- Track: accounts contacted, **positive reply rate** (not open rate; Apple MPP makes opens meaningless), meetings per 100 accounts, meeting → SQL rate, SQL → live organiser, days to first paid on-sale, deliverability (bounce, spam complaints).
- **Kill or rebuild** if, after 400 accounts and at least two messaging angles, positive reply is under 1.5%, or meeting → SQL is under 25% (we're booking the wrong people). **Pause immediately** if spam complaints exceed 0.3% or bounces exceed 3%. Domain reputation is slower to fix than a bad quarter.

### Tools

Freshsales (the CRM Ticmint already uses) as the system of record; the Part A listener + event-listing monitor (this repo, free); Apollo free tier or Hunter for emails; Google Workspace on 2 secondary sending domains with SPF/DKIM/DMARC and gradual warm-up; Instantly or Smartlead (≈ $40/month) for sending; LinkedIn Sales Navigator for Tier 1 only; WhatsApp Business app for UAE/India follow-ups.

---

## D4. Funnel and qualification

| Stage | Primary channels | The action that matters | Metric | Biggest drop-off risk |
|---|---|---|---|---|
| **TOFU** (aware the option exists) | Founder LinkedIn, PR, "Powered by Ticmint" badge on every client event page, answer engines, listener-sourced conversations | Visits a comparison page, the fee calculator or a case study | Non-brand sessions to BOFU pages; calculator completions; AI share-of-answer (Part C) | Mixed story: they find the NFT-era YouTube and press and bounce |
| **MOFU** (considering) | Comparison pages, case studies, retargeting, outbound sequence, reviews | **Self-serve:** creates an event. **Sales-led:** books a demo | Sign-up → event created (7 days); demo request rate; reply → meeting | "Watch Demo" goes to `#`; the 5% vs 2% fee contradiction reads as bait-and-switch |
| **BOFU** (committing) | Demo, migration offer, founder call for Tier 1 | **First paid ticket sold**; for enterprise, the signed order form | Activation (first paid ticket ≤ 14 days from sign-up); demo → SQL → closed-won; days to first on-sale | Payment gateway setup (own Stripe/Razorpay KYC takes days) and fear of switching close to an on-sale |

**Sales-ready (SQL):** an upcoming event ≤ 120 days out with an on-sale date, ≥ 3,000 tickets a year *or* a single event ≥ 2,000 capacity, the decision-maker on the call, and a current platform or setup named. For self-serve, any account that creates an event with ≥ 500 capacity or sells its first 100 paid tickets gets a human touch the same day.

**Nurture:** the right profile but the next event is > 4 months away, or they're locked into a contract (record the end date in Freshsales and trigger a sequence 90 days before it).

**Disqualify early:** free-only events; under ~1,000 tickets a year (self-serve, no sales time); categories Ticmint's gateways won't support; students or individuals without an event; agencies that don't control ticketing.

---

## D5. Metrics

**North star: organisers who sold paid tickets through Ticmint this month (active paying organisers), split self-serve vs sales-led.**

Why this, and why now rather than in two years: revenue is fee × GMV, but GMV today is dominated by a few federations and is lumpy by tournament calendar, so a good or bad month says little about whether growth is working. The question for the next two quarters is *can Ticmint repeatedly win and activate new organisers in its ICP?* Active paying organisers answers that directly, and it can't be gamed by sign-ups that never sell. In two years, with a broad base, I'd switch to **net GMV retention** (are organisers running more and bigger events on Ticmint), which is what compounds.

**Leading indicators**

| Indicator | How it changes a decision |
|---|---|
| SQLs per week by channel and market | Where outbound effort and conquest budget go next week |
| Activation: % of new sign-ups selling a first paid ticket within 14 days | Below ~20% means the problem is onboarding (gateway setup, templates), not acquisition, so pause spend and fix the product path |
| Outbound positive reply rate by message angle | Kills or scales angles (fee maths vs data ownership vs DTCM) within 2 weeks |
| Share of answer on 40 money prompts + review count | Whether off-site work (reviews, list inclusion) or on-site pages get the next sprint |
| Comparison-page → demo conversion | Whether the fee calculator and comparison pages are the right landing for conquest ads |

**Lagging indicators**

| Indicator | How it changes a decision |
|---|---|
| New-organiser GMV and net revenue (cohorted by month of acquisition) | Which segment actually pays back, which decides where the next quarter's ICP weight goes |
| CAC payback by segment and channel | Whether a channel scales, holds or is cut |
| Organiser retention (ran a second event on Ticmint within 6 months) | Low retention in a segment means stop acquiring it until the product is fixed |

---

## D6. Risks and trade-offs

**Biggest assumptions**

1. Promoters on marketplaces will give up marketplace *discovery* for data ownership and lower fees. This is the big one. Platinumlist and BookMyShow also *sell* tickets to their own audiences. (Mitigation: position it as "your own checkout first, the marketplace as one channel". The Thrissur Pooram Dubai listing on both Platinumlist and ticmint.com shows dual-listing already happens.)
2. Public listings give enough data (price, capacity, organiser) to make the fee maths credible.
3. The team can turn around onboarding and gateway setup inside a 30–90 day on-sale window.

**Three things most likely to go wrong in the first six months**

1. **Measurement stays broken.** The duplicate GTM and missing Meta CAPI mean every channel decision rests on bad data. Fix in month one, before any spend.
2. **The secondary ICP eats the primary's time.** One federation deal can absorb the founder and the team for a quarter. Ring-fence: federation work is founder-led, everything else runs on the system.
3. **Outbound burns domains or the market.** The UAE promoter scene is small and connected. Badly targeted sequences get talked about. Tight lists, Tier 1 by hand, hard deliverability limits.

**If early signals come back flat (say, week 6):** check the inputs before the message. Did we reach the right people, and are the triggers real? Interview 10 organisers who said no and 5 who churned. Narrow to one market (UAE, where DTCM is a moat) and one competitor story. Test a partner channel: DTCM permit consultants and event agencies, who bring many organisers at once.

**What I'm knowingly trading away:** UK/US self-serve growth, broad brand awareness, social follower counts, content volume, and the NFT/anti-scalping story. Also some short-term speed: month one is plumbing (tracking, site leaks, reviews), not campaigns.
