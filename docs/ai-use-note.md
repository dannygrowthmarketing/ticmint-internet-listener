# Where AI did the work, where I overrode it, where it was confidently wrong

This whole submission was built with Claude Code: the code, the first drafts of every written part, and the GitHub/Drive plumbing. That's the job description, so I didn't avoid it. What matters is where it needed correcting. Every item below happened during this build and can be checked in the commit history or `data/runs.csv`.

**Where AI did the work**
- Wrote the MCP server, the sources, the scoring rules, the tests and the workflows, and drafted Parts B–D from my audit notes and the two Ticmint research docs.
- Ran the agent live on GitHub Actions within an hour of starting, which is why the first mistakes surfaced so fast.

**Where it was confidently wrong**
1. **"Reddit's public JSON will work from GitHub Actions."** It didn't: HTTP 403 on the first run. Its fallback, PullPush, was also confidently proposed and also returned 403 from Actions. Reddit now needs OAuth credentials or a residential IP. Both failures are in `data/runs.csv`, run 1 onwards.
2. **"Organiser-phrased queries plus a pain lexicon will be precise enough."** The first live run kept 31 rows and all 31 were noise: Hacker News essays on AI consciousness and #eventprofs blog posts that matched "support" and "slow". The fix was a hard relevance gate (nothing scores unless it names a platform or is about tickets) plus a stricter bar when no LLM verdict exists. Re-scoring run 1's 31 rows offline with the gate kept 0. Then run 4 showed the next blind spot: 9 "Warm" rows that were organisers happily *advertising* events on Eventbrite, while a real lead (account suspended five days before an event) scored only 55. Pain words now count only alongside a problem, anger or switching signal. Both posts became test fixtures.
3. **SDK drift.** It wrote against the MCP Python SDK 1.x API (`FastMCP`) while the installed version was 2.3, where it's renamed. It pinned `mcp<2` rather than learn the new API under deadline. A defensible call, but the code wasn't right first time.
4. **A regex it was sure about.** The organiser pattern missed "I'm organising a conference". The fixture test caught it, which is why the tests exist.
5. **Platform permissions.** It assumed the GitHub integration could create the repository. It couldn't (403), so I created it by hand.
6. **Its own success metrics.** It put "951 posts fetched" on the dashboard, a sum that counted the same posts up to seven times, and called the schedule "running" before cron had fired once. It also kept a Hacker News comment about a bomb threat as a lead because it contained "sell tickets", and logged run 8 as `ok` while Reddit was rate-limited. An audit on 21 Oct caught all four; the fixes and tests are in [Part F](part-f-audit-and-operating-plan.md).
7. **"The Sheet refreshes itself."** The linked sheet was empty: the Apps Script it relied on had never been run. Replaced with formula-based import.

**Where I overrode it** *(Daniel: add your own; these are the ones from the build log)*
- Kept the rules engine as a first-class scorer instead of "LLM classifies everything". Rules are free, deterministic and testable. The LLM only sees the shortlist and must quote the post, or its answer is discarded.
- Refused to let the README or Part E contain numbers I can't source. ROAS and page results are left as placeholders for me to fill from real exports.
- [Your overrides: e.g. ICP choice, channel cuts, wording you rewrote]

**The pattern:** AI was reliably good at producing working structure fast, and reliably overconfident about the outside world (what an API allows from a given IP, what real posts look like). The defence was to run it against the real internet early and write down what broke.
