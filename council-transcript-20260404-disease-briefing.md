# LLM Council Transcript — Disease Briefing Skill

**Date:** 2026-04-04
**Question:** Is the `/disease-briefing` skill complete enough for production use? What gaps exist?

---

## Framed Question

The `/disease-briefing` skill generates disease overview reports from Cortellis Drug Design disease briefings. It requires a premium Drug Design subscription. It has 2 files: SKILL.md (73 lines, 3-step workflow) and briefing_report_generator.py (148 lines). The skill searches briefings, fetches records with sections, and generates a markdown report with section text truncated to 500 characters.

---

## Advisor Responses

### The Contrarian

Most "gaps" are nice-to-haves being dressed up as blockers. The 500-char truncation is a deliberate design choice for scannability. No disease name resolution is correct — the API does fuzzy matching. The len(str(d))<50 check is reasonable. Cross-skill hints are sugar. Multimedia is irrelevant for CLI markdown. The real question: how many users have premium subscriptions? If niche, over-engineering is waste. Ship the MVP.

### The First Principles Thinker

Step 1 has no relevance validation — "NSCLC" search might return wrong briefings. Step 2 doesn't document which fields contain section IDs for Step 3. Step 3 truncates to 500 chars, delivering ~5% of actual briefing content (4,500 chars vs tens of thousands). The skill delivers a teaser, not a briefing. Fix: deliver full text or let user choose sections to expand.

### The Expansionist

Missed opportunity on premium API. Uses 1 of 4 Drug Design endpoints. Needs: full text with --full flag, CSV export, manifest, subscription pre-check, multimedia metadata, cross-reference with indication-deep-dive, --compare mode, temporal tracking for briefing updates. Premium users pay for full API surface.

### The Outsider

Premium feature doesn't check subscription upfront — user waits 30+ seconds before finding out. File naming convention (section_1_1.txt) is undocumented implementation leak. 500-char truncation serves developer convenience, not user workflow. Works mechanically but not experientially. For a premium feature, that gap matters more.

### The Executor

3 P0 fixes (~2 hours): (1) Remove/parameterize 500-char truncation — change line 140 from `cleaned[:500]` to `cleaned[:max_chars]` with default 5000 (3-line change). (2) Document section ID extraction between Steps 2-3 in SKILL.md (10 lines). (3) Add subscription check — stop at Step 1 if error. P1: fix load_json heuristic, add manifest, cross-skill hints. P2: CSV, multimedia, compare mode.

---

## Peer Reviews

### Anonymization Mapping
- Response A = The Contrarian
- Response B = The First Principles Thinker
- Response C = The Expansionist
- Response D = The Outsider
- Response E = The Executor

### Review 1
**Strongest: A** — challenges feature creep, frames decision around user base size.
**Blind spot: A** — dismisses truncation without engaging with the 5% content delivery problem.
**All missed:** Actual user task definition — 500 chars may be fine for triage, broken for depth.

### Review 2
**Strongest: B** — sharpest diagnosis (5% content delivery).
**Blind spot: B** — skips subscription-check failure mode entirely.
**All missed:** Cascade failure if Step 2 fails silently.

### Review 3
**Strongest: C** — premium users reasonably expect full API utilization.
**Blind spot: C** — 8 features with no priority ordering or effort estimate.
**All missed:** Output destination matters (terminal vs file vs LLM pipeline).

### Review 4
**Strongest: D** — subscription pre-check is most user-facing bug.
**Blind spot: D** — raises file naming problem without proposing solution.
**All missed:** Observability — no progress indicators for 30-second process.

### Review 5
**Strongest: E** — P0/P1/P2 distinction + time estimate. "P0 = 2 hours" is the most useful sentence.
**Blind spot: E** — doesn't specify what error surface the API actually returns.
**All missed:** Testability without live premium account.

---

## Chairman's Synthesis

### Where the Council Agrees

Every advisor accepts the skill runs and produces output (functional MVP). No one argues it's broken. The dispute is about "runs" vs "ready."

Silent consensus: the 30+ second wait before subscription error is unacceptable. That's the one unanimous pain point.

### Where the Council Clashes

Central fault line: **truncation intent**. Contrarian reads 500 chars as deliberate scannability. First Principles reads it as delivering 5% of content. The skill doesn't declare which it is (triage vs analysis), so both readings are valid.

Secondary clash: completeness vs shippability. Expansionist wants full API utilization. Executor wants 3 small fixes and a ship date. Executor is right on tactics; Expansionist is right that premium users have calibrated expectations.

### Blind Spots the Council Caught

1. Cascade failure on silent Step 2 miss
2. Output destination unspecified (terminal vs file vs LLM input)
3. No progress indicators for 30-second process
4. No testability without live premium account
5. No observability — can't distinguish API failure from wrong disease name

### The Recommendation

Not production-ready. Ship in two weeks. Fix the 3 P0s (~2 hours), declare the scope (triage vs analysis), and ship. Revisit the Expansionist's roadmap with real usage data.

### The One Thing to Do First

Add a subscription pre-check at Step 1 with explicit early exit and clear error message.
