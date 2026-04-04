# LLM Council Transcript — Final Pipeline Verification

**Date:** 2026-04-04
**Council:** #3 (Final)
**Question:** Have ALL 12 issues been adequately addressed? Is the pipeline skill ready to ship?
**Previous Councils:** council-transcript-20260404-pipeline.md, council-transcript-20260404-verification.md

---

## Framed Question

This is the third council run on the pipeline skill. The first council identified 12 issues and declared "not production-ready." Three rounds of fixes addressed all 12. The skill now has 16 recipe scripts (was 12), a manifest integrity layer, credential checking, attrition tracking, temporal detection, and competitive context. All files pass syntax checks. The council must determine if the fixes are adequate for shipping.

---

## Advisor Responses

### The Contrarian

Checked the code directly. Issues 1-7, 9-12 confirmed as claimed. One gap: the total_trials optional 5th argument (Issue 5's fix) is not documented in SKILL.md — an operator following SKILL.md will always get None as the display total rather than the actual count.

One structural concern: EXPECTED_STEPS has 15 entries. competitive_context, snapshot_pipeline, and diff_pipeline are NOT in EXPECTED_STEPS. They run after validation, so a failed competitive_context call is invisible to the integrity layer. That is arguably by design, but it means the manifest gives a green light on the parts users may care about most.

Not a hard block, but not a clean sign-off. Fix the total_trials gap and note the manifest scope caveat.

### The First Principles Thinker

The structural scaffolding is now in place, but "silently degraded data" is still possible through three gaps.

What genuinely improved: The credential check, manifest validation, and exit-on-failure for company resolution are real wins. The operator can now distinguish "run crashed" from "run completed."

Where silent degradation persists: Pagination doesn't verify page consistency — if page 2 returns zero due to transient error, the script accepts it. First run has no baseline — a corrupted initial run becomes the reference. hits=0 competitive queries answer "are there drugs?" but not "did I retrieve all the drugs?"

A run can still complete cleanly, pass manifest validation, produce a snapshot, show a diff, and deliver a report that reflects 40% of available drugs because three API calls returned truncated results with HTTP 200.

The 12 issues were structurally catalogued. The silent degradation problem was made more visible at the edges while remaining invisible in the middle.

### The Expansionist

The 12-issue checklist is a floor, not a ceiling. Yes, the pipeline clears it. The bigger question is whether we're thinking small by celebrating coverage of a list written before we knew what this system could become.

Three expansion vectors: (1) Longitudinal tracking at scale — manifest infrastructure enables industry-wide attrition benchmarks across 50 companies. (2) Cross-skill synthesis — auto-trigger disease-briefing + head-to-head + deal-deep-dive when pipeline detects a Phase 3 cluster. (3) Predictive signals — trial data + deal timing + competitive context could estimate pipeline mortality risk per asset.

The constraint now isn't coverage — it's imagination about what to do with what we've assembled.

### The Outsider

The fixes look thorough on paper but the architecture itself is the unasked question. An AI reading markdown and running 16 scripts in sequence assumes a careful cook. Four of the twelve fixes are "now the AI must do more things correctly in the right order." The failure mode hasn't changed — it has grown.

Documentation was updated in all 3 rounds — suggesting code and docs are still racing each other. A stable system doesn't need documentation chasing fixes across multiple rounds.

No mention of a test run on a fresh environment against a real API. "Fixed" and "works" are different claims. If a domain expert runs it carefully once a week, probably fine. If it needs to run reliably across operators or at higher frequency, the architecture itself is the thirteenth problem.

### The Executor

The 12 issues are addressed. Two gaps before shipping:

1. Integration path untested — syntax checks confirm parseable Python but not that 16 scripts wire together. catch_missing_drugs.py reads 7 CSVs — do all 7 exist at the point it runs? attrition.csv needs to exist before report_generator.py reads it. Has anyone run this end-to-end?

2. competitive_context.py hits=0 logic needs a null check. If ontology resolution fails and hits=0, are we outputting a table of zeros?

Monday morning call: run one full pipeline against a real company ID, capture actual output, verify manifest validates clean. 2-3 hours. If it passes, ship. If hits=0 produces garbage, that's a one-line fix.

---

## Peer Reviews

### Anonymization Mapping
- Response A = The Contrarian
- Response B = The First Principles Thinker
- Response C = The Expansionist
- Response D = The Outsider
- Response E = The Executor

### Review 1
**Strongest: D** — correctly identifies that "fixed" and "works" are different claims. Increasing AI-mediated steps multiplies failure surface.
**Blind spot: D** — offers no path forward. Critique without constructive direction.
**All missed:** Rollback/recovery — if pipeline corrupts data and manifest validates it, how do you recover?

### Review 2
**Strongest: A** — only reviewer who checked the code. Identifies specific total_trials gap — actionable and falsifiable.
**Blind spot: A** — treats manifest scope caveat as minor.
**All missed:** Whether the original 12 issues were the right 12.

### Review 3
**Strongest: E** — most operationally useful. Proposes concrete acceptance test with time estimate.
**Blind spot: E** — flags null check but doesn't acknowledge hits=0 is semantically ambiguous.
**All missed:** Idempotency — what happens when pipeline is re-run on the same company.

### Review 4
**Strongest: B** — silent degradation framing is the most structurally important insight.
**Blind spot: B** — diagnoses disease but prescribes nothing.
**All missed:** Concurrency and ordering — 16 scripts assume no shared state.

### Review 5
**Strongest: B+A combined** form the most complete picture.
**Blind spot: C** — is a product roadmap, not a peer review.
**All missed:** Observability — how does an operator know the pipeline is misbehaving in production?

---

## Chairman's Synthesis

### Where the Council Agrees

The 12 original issues have structural fixes in place. The code compiles. The scaffolding is there. Every advisor acknowledged progress rather than regression.

No one disputes that end-to-end integration testing has not happened. This is unanimous.

### Where the Council Clashes

The real clash is epistemological: does "addressed" mean "fixed" or "fixed and confirmed"? The Expansionist conflates the two. The Outsider refuses to accept either without evidence.

The Executor bridges this: one E2E test converts "fixed" into "confirmed." Without it, the council is debating semantics.

### Blind Spots the Council Caught

1. **total_trials documentation gap** — code fix exists but unreachable via SKILL.md workflow
2. **Rollback and recovery** — no mechanism for partial pipeline failure recovery
3. **Observability in production** — no logging beyond stderr
4. **Post-validation steps invisible** — competitive/snapshot/diff failures not in manifest
5. **Whether the original 12 were the right 12** — the audit was never audited

### The Recommendation

Do not ship yet. Not because the work is bad — it is not — but because no one has run it. Run one full end-to-end pipeline execution against a real company with known outputs. If it passes, the 12 issues are addressed and the skill ships. If it fails, you find out where the docs and code are still racing.

The total_trials SKILL.md gap should be fixed before the test run. The silent degradation concern is legitimate but is a monitoring requirement, not a ship blocker.

### The One Thing to Do First

Run one full end-to-end pipeline execution against a real company with known outputs. Not a syntax check. Not a dry run. The actual pipeline, live data, verified output. Two to three hours. Do it before anything else.
