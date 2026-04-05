# Worked Example: `/landscape` on MASH (Metabolic Dysfunction-Associated Steatohepatitis)

> **ILLUSTRATIVE EXAMPLE.** Every number below is fabricated for teaching. Do NOT cite any company ranking, drug count, deal value, or CPI score from this document as evidence. For a real run, execute the commands against a live Cortellis pull — see `SKILL.md` for the full workflow.

## Why MASH

MASH is a maturing indication with active deal flow and recent regulatory approvals (Rezdiffra reference-class) that makes it an ideal teaching case. Unlike obesity-level crowded spaces or ALS-level sparse pipelines, MASH has a mix of big pharma and specialty biotech competing across multiple mechanisms. This is precisely the kind of indication an analyst would run `/landscape` against during BD due diligence — neither trivial nor pathological. The council's Executor advisor used a similar indication during the Monday-morning walkthrough.

## What You Run

A numbered list of the shell commands from `SKILL.md` indication mode, executed in order against the directory `raw/mash/`:

```bash
DIR=raw/mash
RECIPES=cli_anything/cortellis/skills/landscape/recipes
PIPELINE_RECIPES=cli_anything/cortellis/skills/pipeline/recipes
mkdir -p $DIR

# Step 1: Resolve indication ID
python3 $RECIPES/resolve_indication.py "MASH"
# → 3891,Metabolic dysfunction-associated steatohepatitis

# Step 2: Fetch drugs by phase (~8 min for a populated indication)
bash $RECIPES/fetch_indication_phase.sh 3891 L $DIR/launched.csv $PIPELINE_RECIPES
bash $RECIPES/fetch_indication_phase.sh 3891 C3 $DIR/phase3.csv $PIPELINE_RECIPES
bash $RECIPES/fetch_indication_phase.sh 3891 C2 $DIR/phase2.csv $PIPELINE_RECIPES
bash $RECIPES/fetch_indication_phase.sh 3891 C1 $DIR/phase1.csv $PIPELINE_RECIPES
bash $RECIPES/fetch_indication_phase.sh 3891 DR $DIR/discovery.csv $PIPELINE_RECIPES

# Step 3: Enrich mechanisms
python3 $RECIPES/enrich_mechanisms.py $DIR

# Step 4: Deduplicated company counts
python3 $RECIPES/company_landscape.py $DIR > $DIR/companies.csv

# Step 5b/c: Enrich company sizes + normalize company names
python3 $RECIPES/enrich_company_sizes.py $DIR
python3 $RECIPES/company_normalize.py $DIR

# Step 6/6b: Deals + analytics
bash $RECIPES/fetch_deals_paginated.sh '--indication "MASH"' $DIR/deals.csv $PIPELINE_RECIPES
python3 $RECIPES/deals_analytics.py $DIR/deals.csv $DIR/deals.meta.json | tee $DIR/deals_analytics.md

# Step 7: Trial activity summary
python3 $RECIPES/trials_phase_summary.py 3891 $DIR/trials_summary.csv $DIR/companies.csv

# Step 10: Strategic scoring (metabolic preset)
python3 $RECIPES/strategic_scoring.py $DIR metabolic | tee $DIR/strategic_scores.md

# Step 11: Opportunity analysis
python3 $RECIPES/opportunity_matrix.py $DIR | tee $DIR/opportunity_analysis.md

# Step 12: Strategic narrative
python3 $RECIPES/strategic_narrative.py $DIR "MASH" metabolic | tee $DIR/strategic_briefing.md

# Step 12b: Scenario library
python3 $RECIPES/scenario_library.py $DIR "MASH" | tee $DIR/scenario_analysis.md
```

The **metabolic** preset is used because MASH is a metabolic disease where deal activity and trial velocity dominate competitive positioning — companies with active licensing partnerships and recruiting trials show stronger commitment signals than breadth alone. The metabolic preset weights deal_activity (25%) and trial_intensity (20%) higher than default.

## What You Get — Annotated

### 1. `strategic_scores.md` — Competitive Position Index (CPI) Table

The CPI table is your first competitive snapshot. Read it left-to-right, starting with Rank 1 (the leader).

```markdown
## Competitive Position Index (Top 6)

| Rank | Company | Tier | CPI | Breadth | Phase Score | Mech Diversity | Deals | Trials | Position |
|------|---------|------|-----|---------|-------------|----------------|-------|--------|----------|
| 1    | NorthStar Therapeutics | **A** | 84 | 7 | 23 | 4 | 5 | 8 | Leader |
| 2    | Helix Metabolics | **A** | 71 | 5 | 18 | 3 | 4 | 6 | Leader |
| 3    | LiverEdge Bio | B | 58 | 4 | 14 | 3 | 2 | 3 | Challenger |
| 4    | Steatohepatix Inc | C | 42 | 3 | 9 | 2 | 1 | 2 | Challenger |
| 5    | Fibroway Pharma | C | 35 | 2 | 6 | 2 | 0 | 1 | Emerging |
| 6    | HepRenew Biosciences | D | 18 | 1 | 2 | 1 | 0 | 0 | Emerging |
```

**What to look at:** Tier is read left-to-right. Tier A (bold) represents the top 10% within MASH — NorthStar and Helix are the Leaders this run. Tier D is the bottom 50% — HepRenew has a single asset in the pipeline. **Critical point:** Tiers are percentile-based *within this indication only*. A Tier A company in MASH is not equivalent in competitive strength to a Tier A company in oncology or obesity. Always contextualize tier by disease.

### 2. `opportunity_analysis.md` — Mechanism × Phase Heatmap with White Space

This table shows where mechanisms are saturated vs where entrants can compete.

```markdown
## Mechanism Status & Opportunity Score

| Mechanism | Launched | Phase 3 | Phase 2 | Phase 1 | Discovery | Status | Opportunity Score |
|-----------|----------|---------|---------|---------|-----------|--------|-------------------|
| THR-β agonists | 1 | 2 | 3 | 4 | 5 | **White Space** | 7.2 |
| FGF21 analogs | 0 | 1 | 2 | 2 | 3 | Active | 4.1 |
| SCD1 inhibitors | 1 | 1 | 1 | 0 | 2 | Mature | 2.8 |
| PPAR-δ agonists | 0 | 0 | 1 | 2 | 1 | Emerging | 3.5 |
| GLP-1 receptor agonists | 2 | 3 | 1 | 0 | 0 | Crowded Pipeline | 1.2 |
```

**What to look at:** "White Space" does **not** mean empty. It means there is a launched drug (validation that the mechanism works) but no Phase 2/3 follow-on from competitors — an opportunity gap. THR-β agonists show this pattern: Rezdiffra is on the market (launched=1) but only 2 companies have Phase 3 programs chasing it. That gap is opportunity for a well-timed next-gen entrant. Conversely, "Crowded Pipeline" (GLP-1 agonists) has many Phase 3 programs with only 2 launches, meaning investors are gambling that one of them will differentiate.

### 3. `strategic_briefing.md` — Executive Briefing with Confidence Labels and Action Closures

Below is a shortened excerpt of the strategic briefing header and one key section:

```markdown
# MASH Competitive Landscape — Strategic Briefing

**Data as of:** 2026-04-04 (Cortellis pull)  
**Preset:** metabolic (deal_activity=25%, trial_intensity=20%, phase_score=25%, mechanism_diversity=15%, pipeline_breadth=15%)  

> As of April 2026, MASH remains a fragmented market with 6 Tier-A competitors holding distinct mechanism positions. Deal momentum is moderate; trial recruiting shows pharma commitment but not yet franchise-level intensity. The indication is transitioning from "emerging" to "competitive" as real-world efficacy data from Rezdiffra accumulates and next-generation programs enter Phase 3.

### Freshness Notice
*Data last updated 2026-04-04. If this report is being read more than 14 days after generation (after 2026-04-18), re-run the fetch pipeline to check for new approvals or fast-moving dealflow.*

## Executive Summary

- **Launched franchise:** 8 drugs across 6 companies; Rezdiffra (thiazolidinedione analog) is reference-class.
- **Pipeline density:** 19 drugs in Phase 3; mechanism diversity is high (5+ distinct pathways).
- **Deal momentum:** 12 deals in trailing 18 months; slightly accelerating (recent 6m vs prior 6m ratio = 1.3x).
- **Market position:** NorthStar Therapeutics and Helix Metabolics are Leaders (Tier A); everyone else is chasing.
- **Strategic implication:** Window to differentiate is open but closing; Phase 3 programs must show clear clinical advantage over standard-of-care to command valuation.

## Company Positioning Matrix

|  | High Deal/Trial Activity | Low Deal/Trial Activity |
|---|---|---|
| **Large Pipeline** | **Leaders**<br>NorthStar Therapeutics (CPI 84)<br>Helix Metabolics (CPI 71) | **Fading Giants**<br>(None this cycle) |
| **Small Pipeline** | **Rising Challengers**<br>LiverEdge Bio (CPI 58) | **Under Pressure**<br>HepRenew Biosciences (CPI 18) |

**What to look at:** The quadrant labels are relative to *this indication's competitive set*, not absolute market power. "Under Pressure" (previously called "Struggling") signals small pipeline + sparse activity — HepRenew has one program and no recent deals. This is not a prediction that HepRenew will exit; it is a statement about their current competitive footprint in MASH.

## Strategic Implications & Action Closures

### Implication 1: Should We Enter MASH as a New Competitor?

The indication is at a critical juncture. Rezdiffra's clinical profile is now known; late movers will need head-to-head evidence or a superior safety profile. **Decision:** Enter MASH only if your candidate has a clear clinical or safety advantage. Otherwise, the ROI is diluted across 6+ competitors.

→ **Action:** Commission a head-to-head analysis of your Phase 2 data vs Rezdiffra's efficacy curve. If superiority is defensible, advance to Phase 3 in MASH. If not, consider a different indication.  
**Confidence: HIGH** — This is backed by 8 launched products with clear efficacy data, 19 Phase 3 programs showing competitive intensity, and 12 deals in the last 18 months. The baseline is well-documented.

### Implication 2: Should We License or Partner with NorthStar Therapeutics?

NorthStar holds the top CPI rank (84) with balanced breadth (7 assets), strong phase score (23), and active deal momentum (5 deals in 18m). They are a plausible acquisition or partnership target for a larger acquirer seeking MASH scale.

→ **Action:** If NorthStar is available, benchmark their Phase 3 data and mechanism diversity against your own pipeline fit. Specialty-buyer-fit scores suggest they overlap best with big pharma seeking metabolic franchises.  
**Confidence: MEDIUM** — NorthStar's strength is clear, but deal activity alone does not predict deal success. Regulatory and clinical factors will dominate. Use this as a hypothesis generator, not a deal directive.

### Implication 3: Where Are the "White Space" Opportunities for Licensing?

THR-β agonists show White Space (launched Rezdiffra, but no Phase 2/3 follow-on from others). This is a therapeutic opportunity if your candidate differs meaningfully. FGF21 analogs show Active status with 4 companies in play — higher crowding but still room for a well-differentiated entrant.

→ **Action:** De-risk White Space mechanisms by running Phase 2 trials vs the reference-class standard. Do not enter a White Space mechanism without efficacy head-to-head; it will not guarantee a premium because Rezdiffra has set a high bar.  
**Confidence: LOW** — White Space identification is sound, but only 3 clinical Phase 2 readouts in MASH next 12 months. The data pipeline is thin. Revisit this analysis in Q4 2026 when more Phase 2 data public.

### Implication 4: What If NorthStar Exits MASH?

Scenario: NorthStar's lead program fails Phase 3 or the company is acquired and divested. Who benefits?

→ **Action:** Do NOT act on this scenario yet. Confidence is ABSTAIN — insufficient deal history to rank successor companies reliably.  
**Confidence: ABSTAIN** — Only 2 companies (Helix, LiverEdge) have sufficient pipeline breadth to absorb NorthStar's market share. The others are too small to move the needle. This analysis is too thin to rank beneficiaries. Treat this as a monitor-and-revisit scenario for 2027.
```

**What to look at:** Each strategic implication has a confidence label (HIGH / MEDIUM / LOW / ABSTAIN) and a directional action closure (`→ Action:`). HIGH confidence means the underlying data pattern is dense and the action is defensible — see Implication 1. MEDIUM means the direction is sound but domain judgment must validate — see Implication 2. LOW means the analysis is illustrative only and rests on sparse data — see Implication 3. ABSTAIN means **do NOT rank or act** — data is too thin. This is not "weakest recommendation"; it is "no recommendation".

### 4. `scenario_analysis.md` — Counterfactual Scenarios with ABSTAIN Example

Below are two example scenarios:

```markdown
## Scenario 1: Top Company Exit (NorthStar Therapeutics exits MASH)

**What if NorthStar Therapeutics is acquired and divested from MASH, or their lead Phase 3 program fails?**

### Beneficiaries Ranked by Specialty-Buyer-Fit

| Rank | Company | Specialty-Buyer-Fit | Mechanism Overlap | Phase 3+ Drugs | Recommendation |
|------|---------|---------------------|------------------|----------------|---|
| 1 | Helix Metabolics | 6.8 | 2 shared mechanisms | 3 | Strong fit for acquirer seeking metabolic franchise consolidation |
| 2 | LiverEdge Bio | 4.1 | 1 shared mechanism | 1 | Moderate fit; acquirer would be acquiring niche, not scale |

**Confidence: HIGH** — NorthStar's position is well-documented (CPI 84, 7 assets, 4 distinct mechanisms). Helix's overlap is substantial (THR-β + FGF21). The analysis is robust.

---

## Scenario 3: LOE Wave (Launched Drugs Lose Exclusivity)

**What if 3 of the 8 launched drugs lose market exclusivity in the next 24 months?**

*If LOE metrics (from loe_analysis.py) are not available, this scenario cannot be scored.*

### Ranking (Not Available)

⚠ **Insufficient signal.** LOE exposure data is required to rank companies by vulnerability. Without loe_metrics.csv in the landscape directory, this scenario is ABSTAIN.

**Confidence: ABSTAIN** — Cannot rank beneficiaries because LOE dates are not in the current dataset. If you have proprietary LOE calendars, cross-check them against this scenario. Otherwise, revisit after Step 12c (loe_analysis.py) completes.
```

**What to look at:** Scenario 1 shows a HIGH-confidence scenario with ranked beneficiaries. Scenario 3 shows an ABSTAIN scenario — the data is too thin, and the analysis **deliberately does not rank companies**. Note the difference: Scenario 1 gives an explicit recommendation (#1: Helix, #2: LiverEdge). Scenario 3 says "cannot rank" and does **not** imply that company #2 in a different scenario is weak. ABSTAIN is not a ranked list; it is "no recommendation on this data". Downstream tooling that infers a ranking from an ABSTAIN label is wrong.

### 5. Audit Trail — The Bottom of Every File

Every output file (`strategic_scores.md`, `strategic_briefing.md`, `scenario_analysis.md`) ends with an HTML-comment audit trail block. This block is invisible in markdown rendering but visible when you view the raw file.

```markdown
<!--
AUDIT TRAIL [audit_trail/v1]
script          : strategic_narrative.py
git_sha         : 9ed6476 (clean)
run_timestamp   : 2026-04-05T21:52:14Z
run_id          : 7f3a9b2c1e04
preset          : metabolic (pipeline_breadth=15, phase_score=25, mechanism_diversity=15, deal_activity=25, trial_intensity=20)
cortellis_pull  : 2026-04-04T08:15:00Z
deals_fetched   : 147 / 189 total (77%, newest first)
trials_updated  : 2026-04-04T09:22:00Z
meta_age_days   : 1
code_url        : https://github.com/org/cortellis-cli/blob/9ed6476/cli_anything/cortellis/skills/landscape/recipes/strategic_narrative.py
-->
```

**What to look at:** This block is the reproducibility anchor. `git_sha` lets a reviewer pull the exact code months later. `run_timestamp` and `cortellis_pull` show temporal scope — "we pulled Cortellis data on April 4, ran the analysis on April 5." `preset` lists every weight so a domain expert can audit the computation. `deals_fetched: 147 / 189` means 42 deals were truncated (pagination capped at 50 per page, 4 pages = 200 max) — a reviewer should know this.

## How to Cite This in an IC Memo

When you bring a `/landscape` claim to an Investment Committee meeting, follow this three-step recipe. For full context on positioning modes (supplementary appendix vs direct source), see `docs/governance/ic_evidence_acceptance.md`.

**One example citation sentence:**

> "Per `/landscape` v0.9 run on 2026-04-05 (metabolic preset, git sha 9ed6476, Cortellis pull 2026-04-04), NorthStar Therapeutics held the top CPI rank (84) within the MASH competitive set, with Tier A tier status reflecting top-10% breadth, phase distribution, and deal momentum. Raw data: `raw/mash/strategic_scores.csv`. Audit trail: `raw/mash/audit_trail.json`. See `docs/governance/ic_evidence_acceptance.md` for positioning guidance (supplementary appendix, direct source, or not-yet, depending on your org's incumbent tool)."

**Three-step structure:**
1. Date, preset name, and git SHA (for reproducibility)
2. The specific claim being made (e.g., "NorthStar held top CPI rank")
3. Link to the raw output file and audit trail, plus pointer to positioning docs

This structure lets any downstream reviewer—in a committee meeting months later—pull the exact code, re-run the analysis, and verify your numbers.

## Common Pitfalls

- **Tier is not portable.** A Tier A in MASH is not equivalent to a Tier A in oncology. Always qualify: "Tier A within MASH."
- **CPI is descriptive, not prescriptive.** It ranks competitive *presence*, not predicted 5-year winners. Use it to form hypotheses and validate them with domain judgment and clinical data.
- **"Under Pressure" is the quadrant label (not "Struggling").** If you see "Struggling" in older output, it is pre-rename. Current runs use "Under Pressure."
- **ABSTAIN ≠ weakest.** An ABSTAIN scenario does not rank companies. Do not infer that company #2 in an ABSTAIN scenario is the weakest option — there is no ranking.
- **Stale data warnings are visible.** If the briefing header shows "DATA STALENESS WARNING" or freshness note exceeds 14 days, rerun the fetch pipeline before citing externally.
- **Company name normalization is opt-in.** If `normalization_log.json` is missing from `raw/mash/`, you may have fragmented company rows (e.g., "Lilly" vs "Eli Lilly and Company"). Re-run Step 5c (company_normalize.py).

## What This Example Does NOT Show

- Real Cortellis API responses (all data is fabricated for teaching).
- Real competitor names or drug IDs (NorthStar, Helix, etc., are composites).
- The retrospective blind test rubric (see `docs/governance/decider_trials/retrospective_blind_test_protocol.md`).
- Cross-skill chaining to `/drug-swot` (see `SKILL.md` Step 13 and `compose_swot.py` output).
- LOE analysis scenarios (requires `loe_analysis.py` to complete first; see Step 12c).

---

*Last updated 2026-04-05 (POC docs consolidation — governance artifacts moved under `docs/governance/`). Numbers are illustrative. This example is not a substitute for running `/landscape` on actual Cortellis data. See `SKILL.md` for the full indication-mode workflow.*
