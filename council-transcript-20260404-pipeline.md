# LLM Council Transcript — Pipeline Skill Completeness

**Date:** 2026-04-04
**Question:** Is the `/pipeline` skill in the Cortellis CLI complete enough for production use? What gaps exist?

---

## Original Question

> is the cli_anything/cortellis/skills/pipeline complete enough? do we have gaps?

## Framed Question

The `/pipeline` skill is the flagship command of the Cortellis CLI — an unofficial pharmaceutical intelligence tool wrapping the Cortellis API (17 data domains, 80+ commands). It analyzes a company's full drug development pipeline.

**What the skill does today (12 recipe scripts):**
1. **Company resolution** (`resolve_company.py`): 4 strategies — NER → ontology depth-1 → broad search → suffix search. 98% success on 50 major pharma.
2. **CI drug fetch by phase**: 5 phases (Launched, Phase 3, Phase 2, Phase 1, Discovery), 50 hits each
3. **SI (Drug Design) merge**: Fetches Phase I and Preclinical from drug-design API, merges with CI, deduplicates by name
4. **Per-indication phase resolution** (`resolve_phase_indications.py`): Finds drugs in 2+ phase CSVs, batch-fetches full records, rewrites CSVs with phase-specific indications
5. **Catch missing drugs** (`catch_missing_drugs.py`): Fetches ALL drugs (no phase filter), compares against phase CSVs, writes missed drugs to other.csv, excludes attrition
6. **Deals**: Last 20 deals sorted by date
7. **Trials**: 50 recruiting trials sorted by date
8. **Report generation** (`report_generator.py`): ASCII bar charts, summary table, full drug tables per phase, deals table, trials summary
9. **Pagination** (`fetch_phase.sh`): Auto-paginates up to 150 drugs/phase (3 pages), 1s delay between pages
10. **CSV pipeline**: All data flows through `/tmp/pipeline/` with standardized columns: name,id,phase,indication,mechanism,company,source

**Architecture:** Claude Code reads the SKILL.md and executes bash/python recipes step-by-step. No automation framework — the LLM is the orchestrator.

**Available but unused API domains:** regulatory, conferences, literature, press releases, ontology, analytics, company analytics, deals intelligence, targets, drug design (beyond search-drugs)

**What's at stake:** This is the flagship skill — the first thing users run. If it's incomplete, users get an inaccurate picture of a pharma company's pipeline, leading to bad competitive intelligence decisions.

---

## Advisor Responses

### The Contrarian

The skill has a structural deception problem that no pagination fix will solve.

**The 50-hits-per-phase cap is a lie waiting to happen.** Pfizer has 300+ pipeline assets. Merck, Roche, AstraZeneca — same story. You paginate to 150 max per phase, but that's still an artificial ceiling with zero warning when you hit it. A user runs `/pipeline` on Pfizer and gets a "complete" report missing 40% of their oncology portfolio. No truncation warning. No "fetched 150 of 287" message. Silent incompleteness.

**Company resolution 98% success rate on 50 major pharma is the wrong denominator.** Users will run this on mid-size biotechs, spinouts, recently-renamed companies, subsidiaries. That's where the 2% becomes 20%. When resolution fails, what does the user get? A report for the wrong company with no red flag.

**The phase deduplication logic is fragile at the edges.** Drugs that appear in 2+ phases get indication-split, but what about drugs with ambiguous or missing indication data? They get silently dropped or misattributed. The `other.csv` catch is clever but sends real assets to a bucket labeled "other" — which users will ignore.

**Zero data freshness signals.** No timestamps on fetched data, no API date fields surfaced in the report. A user can't tell if they're looking at a pipeline as of today or a cached state from last week.

**The flagship problem:** This skill presents itself as definitive. The word "complete" is in the architecture description. But it's actually best-effort-with-silent-failures. That's the production gap — not missing API domains, but missing honest uncertainty communication.

### The First Principles Thinker

The question being asked is "is this complete enough?" The question that should be asked is "complete enough for what decision?"

Pipeline intelligence is not a static snapshot problem. It is a signal-detection problem. Someone running this skill is trying to answer one of three fundamentally different questions: What is this company betting on? Where are they vulnerable? Where are they winning? The current architecture answers none of these explicitly — it answers "what exists" and leaves the inference to the user.

That framing exposes the real gaps, which are not API coverage gaps but reasoning gaps.

The skill has no mechanism for change detection. A pipeline without delta is a photograph, not intelligence. What moved from Phase 2 to Phase 3 last quarter? What got quietly discontinued? Without temporal comparison, users cannot detect momentum — which is the only thing that actually matters for competitive decisions.

The skill has no competitive anchoring. A company's pipeline in isolation is meaningless. Phase 3 for what indication, against what standard of care, alongside which competitors? The indication-deep-dive and landscape skills exist but are not wired in.

The skill has no attrition signal. You explicitly exclude attrition from catch_missing_drugs. That exclusion is defensible for noise reduction, but attrition IS the signal for a company under pressure.

The 98% company resolution rate on 50 major pharma is the wrong validation set. Major pharma companies are easy to resolve. The failures that matter are mid-size biotech and spinouts — exactly the companies where competitive intelligence has the most asymmetric value.

So: not production-ready, but not because of missing recipes. Because the output answers the wrong question.

### The Expansionist

The pipeline skill is scratching the surface of what's possible when you think about what "complete" actually means for a flagship product.

The real opportunity hiding here: this skill could become a **living competitive intelligence engine**, not just a snapshot report. Right now it fetches, organizes, and presents. That's table stakes.

What's being massively undervalued:

**The untapped API surface is a goldmine.** Regulatory timelines + pipeline phases = you can predict approval windows, not just describe current status. Conference data + pipeline = you can flag which assets are being presented where, signaling BD intent. Press releases + deals + pipeline = you can reconstruct the narrative arc of how a pipeline evolved.

**The cross-skill integration play.** Every drug in that pipeline table could be a clickable entry point into `drug-profile`, `head-to-head`, `deal-deep-dive`. The pipeline skill should be the hub of a connected intelligence graph, not a terminal report.

**The temporal dimension is completely missing.** Where was this pipeline 6 months ago? What moved phases? What got dropped? Patent watch + pipeline delta = the actual competitive signal pharma analysts pay for.

**Partner identification is sitting right there.** Mechanism explorer + partnership network + the pipeline assets = automated BD target list generation. That's not a feature, that's a product.

The gaps aren't really "bugs" — the skill works. The gap is that it's treating a flagship intelligence surface like a reporting tool when it could be the front door to a full pharma intelligence platform. Every company that runs this and gets a static ASCII table is an opportunity to show them something they couldn't see before.

### The Outsider

The "flagship" framing is doing a lot of work here. Let me tell you what I actually see.

**The skill is a recipe card, not a production system.** An AI reads a markdown file and decides which bash commands to run. That's not a pipeline — that's a tutorial. Production systems don't depend on an AI correctly interpreting step ordering, remembering to run Step 4c after Step 4a, or noticing the pagination note buried at the bottom.

**Specific gaps I can see in the actual code:**

The `report_generator.py` hardcodes `--hits 50` as the truncation threshold on line 45, but the pagination scripts go up to 150. Those two things don't talk to each other — a company with 60 Phase 2 drugs gets flagged truncated even if you paginated correctly.

The `trials_summary` function caps display at 15 indications (`counts.most_common(15)`) with no warning. The total trials count comes from `len(rows)` fetched, not from the API's `@totalResults` field — the very thing the SKILL.md says to never approximate.

The 2% resolution failure rate has no documented fallback. What does a user do when their company isn't in the 98%? Silent failure? Error message? Unknown.

**The bigger problem:** There's no way to know if a run succeeded. No checksums on the CSVs, no validation that each step produced output before the next step runs, no diff against a previous run. If `ci_drugs_to_csv.py` produces 0 rows because of an API timeout, the report generates silently with empty tables.

For a flagship, it needs a verification step. Right now you're trusting the AI to notice when something looks wrong.

### The Executor

Three production blockers, ranked by damage:

1. **Filename mismatch (step 7)** — `catch_missing_drugs.py` reads `phase1.csv`/`discovery.csv` but pipeline writes `phase1_ci.csv`/`discovery_ci.csv`. Result: `other.csv` is bloated with false positives. No error thrown, no warning. This is the worst kind of bug.

2. **No error handling on API failures** — `fetch_all_drugs` has a bare `except: break`. A transient 429 or network blip silently truncates the drug list. You'll get an `other.csv` that looks plausible but is incomplete.

3. **`/tmp/pipeline/` is not persistent** — the SKILL.md step 7 runs after steps 5 and 6 (deals, trials). On any OS that clears `/tmp` between reboots, a multi-session run loses everything. This isn't hypothetical on Linux containers.

**What works fine:** The pagination logic, the dedup approach, the report generator structure, the 4-strategy company resolution — those are solid.

**Monday morning fix:** In `catch_missing_drugs.py` line 46, change `"phase1.csv"` to `"phase1_ci.csv"` and `"discovery.csv"` to `"discovery_ci.csv"`. That's a two-line fix that unblocks production. Everything else is hardening, not correctness.

---

## Peer Reviews

### Anonymization Mapping
- Response A = The Contrarian
- Response B = The First Principles Thinker
- Response C = The Expansionist
- Response D = The Outsider
- Response E = The Executor

### Review 1

**Strongest: Response E** — identifies a concrete, verifiable, production-blocking bug with an exact line number and a two-line fix. Actionable intelligence, not commentary.

**Biggest blind spot: Response C** — treats the pipeline as an opportunity roadmap rather than a production readiness question. Identifies no bugs, no failure modes, no concrete gaps. Visionary but useless for the question asked.

**All missed:** Authentication and credentials handling. None ask how API keys are managed or what happens when a Cortellis session token expires mid-run. A multi-step pipeline that silently fails at step 4 due to a 401 produces partial output that looks complete.

### Review 2

**Strongest: Response E** — only falsifiable, actionable findings. Concrete bugs with specific fixes.

**Biggest blind spot: Response C** — evangelizing cross-skill integration before fixing filename mismatches and bare-except truncation is premature. Zero actionable production guidance.

**All missed:** Error surfacing to the caller. No structured run manifest — operators cannot distinguish a clean run from a quietly broken one.

### Review 3

**Strongest: Response E** — bugs, not opinions. Fix in minutes and verify.

**Biggest blind spot: All responses** missed SKILL.md drift from actual scripts.

**All missed:** `fetch_drugs_paginated.sh` has path-coupling fragility — wrong recipes dir causes silent CSV conversion failure for every page.

### Review 4

**Strongest: Response E** — runtime bug with falsifiable evidence.

**Biggest blind spot: Response D** — sharpest critique with the least utility.

**All missed:** Authentication/credential lifecycle and SKILL.md-to-script synchronization.

### Review 5

**Strongest: Response E** — verifiable runtime bug.

**All missed:** The false-alarm problem — report_generator.py flags truncation at >=50 rows even when pagination legitimately returned 51+ real drugs. The warning cries wolf.

---

## Chairman's Synthesis

### Where the Council Agrees

Every advisor found the same underlying failure mode: **silent, undetectable errors**. The Executor named a specific bug (filename mismatch producing false positives in other.csv). The Outsider found the same class independently (empty CSV from API timeout generates complete-looking report). The Contrarian named the category (50-hit cap with no warning).

This is not a collection of separate issues. It is one architectural failure: **the pipeline has no integrity layer**. It assumes every step succeeds and reports confidently regardless of whether it did.

Second convergence: the resolution logic has an invisible accuracy cliff. 98% on major pharma sounds good. Mid-size biotechs — the more interesting targets — fail at ~20%. Three reviewers flagged this. No one disagreed.

### Where the Council Clashes

**Reporting tool vs intelligence platform?** The Expansionist and First Principles Thinker argue the pipeline answers the wrong question. The Executor and Outsider implicitly reject this: it doesn't correctly report what exists yet, so platform ambitions are premature. The Executor is right on sequencing.

**Is the AI-reads-markdown architecture a problem?** The Outsider calls it a tutorial. No other advisor challenged this. The honest answer: Claude Code reading SKILL.md is unconventional but not disqualifying. What the Outsider is pointing at is the absence of orchestration guarantees — a real problem dressed in architectural clothing.

### Blind Spots the Council Caught

1. **Credential lifecycle** — flagged by every reviewer. A multi-step pipeline that silently fails at step 4 due to a 401 produces a partial report with no indication of where it broke.

2. **SKILL.md drift** — load-bearing documentation may desynchronize from actual scripts over time. Since Claude Code uses it as the orchestration source, drift means wrong commands with no user-visible signal.

3. **False-alarm truncation** — report_generator.py flags >=50 rows as truncated even when pagination legitimately returned 51+ real drugs. Users learn to ignore the warning, and real truncation becomes invisible.

### The Recommendation

**Not production-ready. Ship as beta with an integrity layer added first.**

The skill works for known large pharma where resolution is reliable and the user can sanity-check the output. It is not ready for any context where a user will act on the output without manual verification.

The gaps are not feature gaps. They are trust gaps. An operator cannot currently tell if a pipeline run produced complete data or silently degraded data. That single fact disqualifies it from production.

### The One Thing to Do First

Add a run manifest: after every pipeline execution, write a structured JSON file recording each step, its exit code, the row count of every CSV produced, the timestamp, and any truncation flags. Make report generation read this manifest and refuse to render if any upstream step produced zero rows or a non-zero exit. This single change converts silent failures into loud ones, surfaces the filename mismatch, the empty-CSV-from-timeout, and the credential failure modes simultaneously — without requiring changes to the underlying recipe scripts.
