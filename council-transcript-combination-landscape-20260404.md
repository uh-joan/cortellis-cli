# LLM Council Transcript — Combination Landscape Skill Completeness
**Date:** April 4, 2026

---

## Original Question
> Is the cli_anything/cortellis/skills/combination-landscape complete enough? Do we have gaps?

## Framed Question
**Question:** Is the `cli_anything/cortellis/skills/combination-landscape/` skill complete enough for production use, or does it have meaningful gaps?

**Context:** Combination therapy landscape skill for a pharma CLI. Analyzes drug combinations by indication. 2 files: SKILL.md (4-step workflow) and combination_report.py (127 lines). Workflow: (1) resolve indication via landscape's resolve_indication.py, (2) search combo drugs ("+" in name or "Co-formulation" technology, --hits 50), (3) search combo trials ("combination" keyword, --hits 50), (4) generate report. Report: 30 drugs max, 20 trials max, 10 companies. No pagination, no metadata, no coverage signals. Cross-dependency on landscape skill.

**Prior context:** Landscape skill fixed (pagination 300→1000, coverage footer, enrichment metadata). Target-profile fixed (pagination, "Showing X of Y", inlined dependencies, parallel API, fuzzy candidates). Same quality bar applies.

**What's at stake:** Combination therapy is fastest-growing in oncology/immunology. Missing combination programs means missing competitive threats. Feeds BD and clinical strategy decisions.

---

## Advisor Responses

### 1. The Contrarian

Data truncation with no warning. 50-hit cap plus 30/20 row limits silently discards results. No totalResults capture, no "Showing X of Y," no footer. A user sees a clean table with no idea they missed 200 combinations.

Primary detection method broken by design. Searching for "+" in drug name catches branded co-formulations, not investigational combinations. The vast majority of combination regimens — pembrolizumab + olaparib, nivolumab + ipilimumab — will never appear in a drug name search. This is the wrong API endpoint for the question being asked.

"combination" as trial keyword is noise. Returns trials where "combination" appears anywhere in the protocol — monotherapy trials with combination endpoints, trials mentioning the word in background. No filtering by co-primary agent, no deduplication, no relevance signal.

Cross-skill dependency is fragile. Hardcoding into landscape's resolve_indication.py means silent breakage on refactoring. No pagination means artificially low ceiling. This skill will produce confidently wrong outputs with no signal that anything is missing.

### 2. The First Principles Thinker

Search logic wrong by design. "+" catches only co-formulated branded products, not actual combination regimens (FOLFOX, carboplatin+pembrolizumab). Co-formulation fallback is equally narrow. The skill's core premise mismatches how combination therapy actually works in Cortellis.

No pagination, hard cap at 50 hits. In NSCLC alone hundreds of active combination regimens. The 50-hit ceiling silently truncates. No @totalResults surfaced relative to fetched.

No coverage signals. Report prints total but only shows 30 rows with no warning that 282 were dropped.

Drug table drops the Components column. SKILL.md specifies Components in the output format. The recipe never extracts or prints it. The most diagnostic field for combination landscape — what is being combined — is absent.

Cross-dependency not inlined. Step 1 calls landscape's resolve_indication.py. If path wrong or landscape absent, workflow fails silently.

Trials search weaker than it looks. --query "combination" is full-text keyword, not structured filter. Misses trials where combination is implicit in design. No terminology grounding.

Verdict: do not ship to oncology/immunology users.

### 3. The Expansionist

Three structural deficiencies: no pagination (50/30 caps), no coverage footer (@totalResults read but never surfaced), fallback logic is brittle prose not automated.

The upside: combination therapy is the single highest-signal query type in Cortellis — Phase 2→3 transitions are densest here, BD deal flow concentrates around combos. A skill that works correctly becomes the go-to for competitive intelligence on any hot indication. Fix is same playbook as landscape: paginate, merge, print coverage footer. Two hours of work for disproportionate value.

### 4. The Outsider

Silent truncation is the critical flaw. 50 drugs, 50 trials, displaying 30 and 20 — nowhere told "we found 50+ results, you're seeing 20."

Search logic fragile. "+" in drug names misses anything named differently — co-administrations, brand names, "plus" or "with" in free text. "Co-formulation" is narrow. "combination" keyword returns noise.

50-result hard cap with no pagination. Cross-dependency on landscape for indication resolution is undocumented risk.

Same bug class across codebase — silent truncation needs to be treated as a bug class, not a per-skill issue.

### 5. The Executor

Three concrete blockers: no "Showing X of Y", no coverage footer, no pagination.

Secondary: ActionsPrimary renders as `{'$': 'inhibitor'}` in table cells. Fallback logic in SKILL.md prose not enforced. No enrichment metadata on trials.

Fix: raise hits to 1000, add showing X of Y, add footer — 20 lines of Python.

---

## Peer Reviews

### Anonymization Mapping
- Response A = The Contrarian
- Response B = The First Principles Thinker
- Response C = The Expansionist
- Response D = The Outsider
- Response E = The Executor

### Peer Review 1

**Strongest: B (First Principles)** — most precise, names FOLFOX/carboplatin examples, finds Components column spec violation.

**Biggest blind spot: E (Executor)** — underweights its own best finding (dict rendering bug as secondary).

**All missed:** Nobody examined what the cross-dependency actually does — subprocess, import, or shared config. Failure mode of dependency is more dangerous than truncation.

### Peer Review 2

**Strongest: D (Outsider)** — identifies bug class, not just instance.

**Biggest blind spot: A (Contrarian)** — diagnoses without prescribing fixes.

**All missed:** Nobody ran the skill against real data. All critiques are code-reading, not empirical. A 10-minute smoke test would separate confirmed bugs from hypothetical ones.

### Peer Review 3

**Strongest: B (First Principles)** — root cause + spec violation.

**Biggest blind spot: E (Executor)** — "20 lines to fix" without addressing upstream data problem.

**All missed:** Does the Cortellis API even have a dedicated combination endpoint? If not, the skill is reverse-engineering structured data from unstructured text, and precision will always be low.

---

## Chairman Synthesis

### Where the Council Agrees

Every advisor independently identified the same three defects: no pagination, no coverage signal ("Showing X of Y total"), and silent truncation at 50/30/20 limits. The council also unanimously agrees the skill produces outputs with no warning when results are capped — users receive confidently incomplete data. That is a production defect, not a gap.

### Where the Council Clashes

The split is on severity of the search logic. The Contrarian and First Principles Thinker call the "+" detection approach broken by design — it catches branded co-formulations but misses investigational combos. The Executor calls it secondary and claims 20 lines of Python fixes the skill.

The Executor is wrong about severity. "+" in drug name is not a minor gap — it is the wrong detection unit. FOLFOX has no "+". Carboplatin+pembrolizumab trials are not branded. The 50-hit cap on a broken query returns a biased sample of the wrong population. Fixing pagination on a broken query is waste.

### Blind Spots the Council Caught

**API capability question:** Nobody asked whether Cortellis has a dedicated combination therapy endpoint or structured combination flag. If it does not, the skill is reverse-engineering structured data from unstructured text, and precision will always be low. Every other fix is downstream of this answer.

**No empirical testing:** All critiques are static code analysis. A 10-minute smoke test against live data would confirm or refute whether the search logic actually misses combos in practice.

**Cross-dependency failure mode:** Nobody examined whether it's a subprocess, import, or config coupling. The blast radius of a dependency failure is unknown.

### The Recommendation

Do not ship to production. The skill is a working prototype with correct scaffolding but incorrect core logic. The infrastructure (report generator, table formatting, CLI wiring) is sound. The data retrieval strategy is not.

Fix order: data source question first, then search logic, then pagination and coverage signals. Fixing pagination on a broken query is waste.

### The One Thing to Do First

Determine whether the Cortellis API exposes a combination therapy endpoint or a structured combination flag on drug records. If yes, rewrite the search logic. If no, document the precision ceiling explicitly in the skill output. Every other fix is downstream of this answer.

---

*LLM Council — 5 advisors, 3 peer reviews, 1 chairman synthesis — April 4, 2026*
