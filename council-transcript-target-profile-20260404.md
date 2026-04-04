# LLM Council Transcript — Target Profile Skill Completeness
**Date:** April 4, 2026

---

## Original Question
> Is the cli_anything/cortellis/skills/target-profile complete enough? Do we have gaps?

## Framed Question
**Question:** Is the `cli_anything/cortellis/skills/target-profile/` skill complete enough for production use, or does it have meaningful gaps?

**Context:** This is a biological target profiling skill for a pharmaceutical intelligence CLI (Cortellis). It produces deep profiles for drug targets (e.g., EGFR, PD-L1, GLP-1) across 7 data dimensions: biology, disease associations, genetic evidence, drug pipeline, protein interactions, pharmacology, and disease briefings. It has 2 recipe scripts: `resolve_target_id.py` (4-strategy resolution: NER→direct search→normalized retry→fail) and `target_report_generator.py` (markdown report from collected JSON). The workflow is 9 steps with 7-8 API calls per run. Drug pipeline fetches are capped at 50 hits. Display limits: 25 diseases, 15 genetic evidence, 20 interactions, 20 pharmacology. No pagination, no metadata tracking, no coverage signals, no truncation warnings. Cross-skill dependency on landscape's resolve_target.py. SKILL.md says "ALWAYS list ALL items — no truncation" but code contradicts this.

**Prior council context:** The landscape skill was just counciled and found "not production-ready" due to silent truncation, missing coverage signals, and a hardcoded pharma list. Those issues were fixed. Same lens applies here.

**What's at stake:** Target profiling is a core use case for drug discovery teams — used for target validation, competitive intelligence on specific mechanisms, and understanding the druggability of biological targets. Gaps mean incomplete target assessment, missed competitors, or wrong conclusions about a target's therapeutic potential.

---

## Advisor Responses

### 1. The Contrarian

The skill has the same fatal flaw the landscape skill had, and it's worse here because the stakes are higher.

**Silent truncation is the core problem.** 50 hits on drug pipeline for EGFR? EGFR has 300+ drugs in various stages. A researcher seeing this report has no idea they're looking at roughly 15% of the competitive landscape. That's not a data gap — that's a liability. The report will look authoritative while being structurally incomplete. Same problem with 25 disease associations and 20 pharmacology records for any major target.

**No pagination means no completeness.** The landscape skill got dinged for this. Target profiling is worse because targets like EGFR, PD-L1, or VEGFR are among the most-studied in oncology. Capping at 50 drugs and calling it a pipeline analysis is analytically dishonest.

**The cross-skill dependency is a production anti-pattern.** Depending on `landscape/resolve_target.py` for action name resolution means this skill silently breaks when that path changes or that skill is updated. No interface contract, no versioning, no fallback.

**7-8 sequential API calls with no parallelization** makes this unusable for batch workflows. Want to profile 10 targets before a BD meeting? That's potentially 70+ sequential calls. In production, that's a timeout or a 20-minute wait.

**The 400 errors on disease briefings are unhandled gracefully but silently.** "Optional, may fail" is not acceptable for a section in a clinical report.

**Bottom line:** This is a demo-quality prototype that produces reports which look production-ready but hide their own incompleteness. For drug discovery work where missing a competitor or underestimating target validation evidence has real consequences, this is not production-ready.

### 2. The First Principles Thinker

The question being asked is wrong. "Is it complete enough for production use?" presupposes the right evaluation frame is feature completeness. It isn't.

The real question: **Does this tool produce outputs a scientist can trust without knowing its limitations?** The answer is no, and that's a production disqualifier regardless of feature count.

Here's what's actually broken at the foundation:

**The silent truncation problem is an epistemological failure.** When a tool returns 50 drugs for a well-studied target like EGFR (which has 200+ pipeline compounds), it doesn't just give incomplete data — it gives data that *looks* complete. A researcher comparing EGFR vs KRAS pipeline depth using this tool will get confidently wrong conclusions. The tool is actively misleading, not merely incomplete.

**No pagination isn't a gap — it's a design assumption that was never validated.** The 50-hit cap exists because someone made a default choice and never questioned it. First principles: what's the actual distribution of pipeline counts for high-value targets? If the answer is "often exceeds 50," then the cap isn't a limitation to document, it's a correctness bug.

**7-8 sequential API calls with no parallelism means the tool is structurally slow for no reason.** This isn't a performance nicety — slow tools get abandoned or, worse, get run less thoroughly.

The cross-skill dependency on `resolve_target.py` from a separate skill is an undocumented coupling. If that resolver changes, this skill breaks silently.

**Production readiness requires that outputs are trustworthy by default, not by user vigilance.** This tool requires users to already know its limitations to use it safely — which inverts the entire value proposition of intelligence tooling.

Fix the epistemic layer first. Everything else is polish.

### 3. The Expansionist

The skill is functionally incomplete for production drug discovery use. Here's what's being missed:

**The 50-hit pipeline cap is the most damaging gap.** For major targets like EGFR or PD-L1, there are hundreds of active programs. Silently capping at 50 means competitive intelligence is systematically wrong — a BD team using this for deal assessment is working with a fraction of the landscape. Apply the same pagination fix just done for the landscape skill: paginate until exhausted, add a coverage footer showing "showing X of Y programs."

**The display limits compound this.** 25 diseases, 15 genetic evidence entries, 20 interactions — these aren't display preferences, they're hard data truncations with no signal to the user. A target like GLP-1 has extensive genetic evidence; silently dropping most of it creates false confidence in incomplete profiles.

**The adjacent opportunity being missed: cross-target comparison.** Once you have deep profiles, the obvious next move is a diff view — "EGFR vs ERBB2" or "GLP-1R vs GIPR." The data is already being fetched in the right shape. A `/target-compare` skill is a natural extension that would be extremely high-value for druggability triage.

**Resolution robustness matters more here than anywhere.** Target resolution feeds into every downstream data dimension. A resolution failure at step 1 silently corrupts all 7 dimensions. The 4-strategy scoring needs a confidence score surfaced in the output header, not buried or absent.

**The optional disease briefings are a silent capability degradation.** If they're returning 400s with any frequency, that needs monitoring and a fallback message — not silent omission.

Fix pagination and add coverage signals first. That's the same lesson the landscape skill just learned, and it applies here harder.

### 4. The Outsider

I've read all three files. Here is my assessment.

**The skill is not production-ready. Here are the specific gaps that matter:**

**1. Silent truncation is the biggest problem.** The SKILL.md says "ALWAYS list ALL items in tables. No truncation." The code contradicts this directly. `disease_data[:25]`, `gene_assocs[:15]`, `meaningful[:20]`, `pharm_list[:20]` — all hard caps, no warning emitted. A drug discovery team looking at EGFR disease associations would see 25 rows and have no idea whether there are 26 or 260. That's a research integrity problem, not a cosmetic one.

**2. Drug pipeline undercounting is undetected.** The API call fetches `--hits 50`. The report header prints `total` from `@totalResults`, which reflects the real count. So you'll see "Drug Pipeline (847 total)" followed by a table with 50 rows and no explanation. The number signals completeness; the data doesn't deliver it.

**3. Protein interactions silently filter without disclosure.** The code filters out interactions where the partner name exceeds 60 characters (to remove chemical names), then falls back if nothing survives. There's no indication in the output that any interactions were excluded by this filter. The reported count is the pre-filter total, so the table row count won't match the header.

**4. Resolution failure is a hard stop with no guidance.** If `resolve_target_id.py` returns None, the workflow halts with an error. There's no fallback suggestion, no fuzzy candidate list, nothing. For an end user who typed "GLP1" instead of "GLP-1", the experience is a silent failure.

**5. Cross-skill dependency is fragile.** `resolve_action_name()` calls a script from the landscape skill via a relative path. If the landscape skill is absent or its path changes, action-name resolution silently returns an empty string, and Step 6 (drug pipeline) is skipped entirely with no notice.

**The fix from the landscape review — adding a coverage footer — applies here directly and would address points 1 and 2 in one pass.**

### 5. The Executor

The skill has 4 meaningful gaps that block production use for drug discovery teams:

**1. Drug pipeline is blind beyond 50 results.** For EGFR, there are 200+ compounds in development. Capping at 50 without pagination means the pipeline section is incomplete by default for any clinically validated target. Fix: paginate with `--start` offset, capture `totalResults`, loop until exhausted or hit a reasonable cap (500).

**2. No truncation warnings anywhere.** The 25/15/20/20 display limits are silent. A user sees "20 protein interactions" and has no idea if that's all of them or 20 of 300. Every truncated section needs a footer line: `Showing X of Y (truncated)`. Same pattern the landscape skill just got.

**3. No coverage/confidence signals.** Resolution confidence (which of the 4 strategies fired, score), fill rate per section, totalResults captured vs displayed — none of this surfaces. Drug discovery teams need to know if they're looking at a thin profile or a complete one.

**4. Sequential API calls when parallelism is free.** 7-8 calls run one at a time. Biology, disease associations, genetic evidence, drug pipeline, interactions — these are independent. Parallelize with background subshells or `wait`. Cuts wall time by 60-70%.

**What's serviceable:** The 4-strategy resolution is solid. The 7-dimension structure is correct. Disease briefings failing gracefully on 400 is fine.

**Bottom line:** Ship it for internal prototyping only. Before production, fix pagination (gap 1) and add truncation warnings (gap 2) — those two alone materially change the intelligence quality. Coverage signals (gap 3) and parallelism (gap 4) are polish but worth doing in the same pass since the landscape skill already has the pattern.

---

## Peer Reviews

### Anonymization Mapping
- Response A = The Contrarian
- Response B = The First Principles Thinker
- Response C = The Expansionist
- Response D = The Outsider
- Response E = The Executor

### Peer Review 1

**Strongest: Response D (Outsider)** — the only one grounded in actual code evidence. Cites specific truncation lines (`disease_data[:25]`, `gene_assocs[:15]`), identifies the header/table mismatch (847 total, 50 rows), and flags the protein interaction filter without disclosure. Not analysis — audit.

**Biggest blind spot: Response E (Executor)** — calls disease briefings "failing gracefully" when D and A both flag that 400 errors are silently skipped. "Graceful failure" obscures that a researcher gets a report with a missing dimension and no indication why.

**All missed:** Output reproducibility and caching. No result caching, no run metadata, no timestamp. Two runs on the same target one day apart silently produce different results — different drug counts, different pipeline states — with no record of when data was fetched. For scientific use, this is a traceability failure.

### Peer Review 2

**Strongest: Response D (Outsider)** — cites the artifact, not arguments. Biggest blind spot: Response E (Executor) — calls resolution "solid" with no basis; D directly contradicts this.

**All missed:** Error propagation across 7 dimensions. If resolution fails or returns wrong IDs, every subsequent API call runs against bad inputs and returns plausible-looking but incorrect data — no dimension flags this. No validation layer between resolution and retrieval. A scientist gets a complete-looking 7-dimension report built on a wrong target ID. Worse than a hard stop.

### Peer Review 3

**Strongest: Response D (Outsider)** — verifiable, specific failures.

**Biggest blind spot: Response E (Executor)** — "ship internally" is not a meaningful risk boundary. Internal users build workflows on silent truncation the same way external users would.

**All missed:** Data freshness and provenance. No timestamps, no API endpoint attribution per dimension. Stale pipeline count or outdated mechanism annotation is patient-safety-adjacent. The council focused on retrieval completeness but said nothing about whether data is current, attributed, or auditable.

---

## Chairman Synthesis

### Where the Council Agrees

The drug pipeline cap at 50 is the most damaging single defect. EGFR has 300+ pipeline entries; the skill shows 50 and displays a header with the true total, making the incompleteness visible but doing nothing about it. That internal contradiction — showing `totalResults: 847` while returning 50 rows — is not a limitation, it is a lie of omission that a scientist will miss.

Silent truncation is universal across all dimensions. `disease_data[:25]`, `gene_assocs[:15]`, `meaningful[:20]`, `pharm_list[:20]` execute without warning. SKILL.md says "ALWAYS list ALL items — no truncation." The code contradicts this on four separate lines. Every advisor flagged this in some form.

Cross-skill dependency on the landscape resolver is undocumented coupling with no contract, no versioning, and no fallback. If landscape is absent, Step 6 silently skips — not an error, not a warning, just missing data that looks like an absence of associations rather than a code failure.

Sequential API calls are structurally slow for no reason when 60-70% of the latency is recoverable through parallelism.

### Where the Council Clashes

The Executor calls disease briefing 400s "graceful failure." The Contrarian and both peer reviewers call it a silent data hole. The Executor is wrong. A failure that is silent to the user is not graceful — it is invisible. Graceful failure requires surfacing the failure, not absorbing it.

The Executor calls resolution "solid." The Outsider and Peer Review 2 show it is a hard stop with no fuzzy candidates on failure. Resolution failure at Step 1 propagates corrupt or empty data across all 7 dimensions — Peer Review 2's point that this produces plausible-looking but incorrect data is more dangerous than a hard stop.

The Expansionist frames cross-target comparison as an "adjacent opportunity." This is premature. The current skill cannot be trusted for a single target; expanding to comparison before fixing data integrity inverts the priority order.

### Blind Spots the Council Caught

All three peer reviews identified the same gap the advisors missed entirely: **output provenance**. No timestamps, no run metadata, no API endpoint attribution per dimension. Two runs on the same target at different times can produce different results with no record of when the data was fetched. For drug discovery — a regulatory and scientific record-keeping domain — this is a traceability failure, not a minor omission.

The secondary blind spot: error propagation across dimensions. A wrong resolution at Step 1 does not produce an error. It produces confident-looking outputs across all 7 dimensions that are wrong for the wrong target. There is no validation layer between resolution and retrieval. This is worse than a failure to resolve at all.

### The Recommendation

**Do not ship in production, including internally without explicit caveats.** "Internal use" is not a meaningful risk boundary when outputs look authoritative and contain no signals of incompleteness or provenance.

The skill has the right architecture — 7 dimensions, correct structure, real API calls. But it systematically misrepresents its own completeness. A scientist using this output to make a go/no-go decision on a target program has no way to know they are seeing 6% of the pipeline data, or that their protein interaction list was silently filtered, or that the data was fetched six months ago. The SKILL.md documentation actively contradicts the code behavior, which means users have been told a false contract.

Before any production use, four things must be true: (1) every truncated list shows "Showing X of Y" with Y from the API's totalResults, (2) pagination is implemented for drug pipeline, (3) every output includes a run timestamp and API source per dimension, (4) resolution failure either returns fuzzy candidates or fails loudly — never silently corrupts downstream dimensions.

### The One Thing to Do First

Fix the drug pipeline pagination and add "Showing X of Y" to every truncated list — in the same commit, add the run timestamp to the output header. This single change closes the internal contradiction (showing 847 in the header, 50 in the table), makes truncation visible across all dimensions, and begins the provenance record. Everything else is secondary to making incompleteness legible.

---

*LLM Council — 5 advisors, 3 peer reviews, 1 chairman synthesis — April 4, 2026*
