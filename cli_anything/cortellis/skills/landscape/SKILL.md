---
name: landscape
description: /landscape: Competitive Landscape Report
---

# /landscape — Competitive Landscape Report

Generate a full competitive landscape for a therapeutic indication.

> **Version: v0.9-internal** (locked 2026-04-05)
>
> **Status:** Cleared for internal BD use. Not promoted to public v0.9 — pending completion of the retrospective blind test (`docs/decider_trials/retrospective_blind_test_protocol.md`, protocol ID `retrospective-blind-v1-20260405`).
>
> **Roles (names tracked in referenced docs, not here):** harness owner, independent observer, rubric author, external decider, third-party rubric reviewer (TBD).
>
> **Validation status:** 5-indication internal harness 4/4 PASS. Independent harness re-run scheduled. TOS dual-attestation complete (MIT relicense). Retrospective blind test pending.
>
> **Caveat:** Strategic briefings and scores should be reviewed against domain judgment before acting on external commitments until v0.9 promotion lands.

## LICENSING

> **Code:** MIT (see repository `LICENSE`).
> **Derived analytical outputs** (strategic briefings, scenario libraries, CPI rankings, mechanism crowding indices): shareable per the TOS answer recorded in `docs/tos_check.md` (ANSWERED 2026-04-05). Attribute Cortellis/Clarivate as the underlying data source when sharing externally.
> **Raw Cortellis data** (anything under `raw/` pulled directly from the API) remains governed by your Cortellis/Clarivate subscription agreement and must not be redistributed.

## Usage

**Indication mode (default):**
```
/landscape obesity
/landscape "non-small cell lung cancer"
/landscape MASH
/landscape "Huntington's disease"
/landscape "sickle cell disease"
```

**Target mode:**
```
/landscape --target "GLP-1 receptor"
/landscape --target "PD-L1"
/landscape --target "EGFR"
/landscape --target "CDK4/6"
```

**Technology mode:**
```
/landscape --technology "ADC"
/landscape --technology "mRNA"
/landscape --technology "gene therapy"
/landscape --technology "CAR-T"
```

**Combined mode (technology + indication):**
```
/landscape --technology "ADC" --indication "cancer"
/landscape --technology "mRNA" --indication "cancer"
/landscape --technology "gene therapy" --indication "sickle cell disease"
```

## Technology Mode Workflow

When invoked as `/landscape --technology "<TECH>"` (optionally with `--indication "<IND>"`), use the following workflow.

### Technology Setup
```bash
RECIPES="cli_anything/cortellis/skills/landscape/recipes"
PIPELINE_RECIPES="cli_anything/cortellis/skills/pipeline/recipes"
DIR="raw/<TECH_SLUG>"
mkdir -p "$DIR"
```
Use a slug derived from the technology name (e.g., `raw/adc`, `raw/mrna`, `raw/gene-therapy`).

### Technology Step 1: Resolve technology ID and name
```bash
RESULT=$(python3 $RECIPES/resolve_technology.py "<TECH>")
TECH_ID=$(echo "$RESULT" | cut -d',' -f1)
TECH_NAME=$(echo "$RESULT" | cut -d',' -f2-)
# Output: id,name (e.g. "1164,Antibody drug conjugate")
# Strategies: synonym table → ontology search (--category technology) → normalized retry
# Use TECH_ID with --technology for precise taxonomy matching
```

### Technology Step 2 (combined mode only): Resolve indication ID
```bash
# Only needed when --indication is also provided:
RESULT=$(python3 $RECIPES/resolve_indication.py "<INDICATION>")
IND_ID=$(echo "$RESULT" | cut -d',' -f1)
IND_NAME=$(echo "$RESULT" | cut -d',' -f2-)
```

### Technology Step 3: Drugs by phase (paginated)
```bash
# Technology-only mode (use --phase-highest for "drugs whose highest phase IS X"):
bash $RECIPES/fetch_drugs_paginated.sh L $DIR/launched.csv $PIPELINE_RECIPES --phase-highest --technology $TECH_ID
bash $RECIPES/fetch_drugs_paginated.sh C3 $DIR/phase3.csv $PIPELINE_RECIPES --phase-highest --technology $TECH_ID
bash $RECIPES/fetch_drugs_paginated.sh C2 $DIR/phase2.csv $PIPELINE_RECIPES --phase-highest --technology $TECH_ID
bash $RECIPES/fetch_drugs_paginated.sh C1 $DIR/phase1.csv $PIPELINE_RECIPES --phase-highest --technology $TECH_ID
bash $RECIPES/fetch_drugs_paginated.sh DR $DIR/discovery.csv $PIPELINE_RECIPES --phase-highest --technology $TECH_ID

# Combined mode (technology + indication):
bash $RECIPES/fetch_drugs_paginated.sh L $DIR/launched.csv $PIPELINE_RECIPES --phase-highest --technology $TECH_ID --indication $IND_ID
bash $RECIPES/fetch_drugs_paginated.sh C3 $DIR/phase3.csv $PIPELINE_RECIPES --phase-highest --technology $TECH_ID --indication $IND_ID
bash $RECIPES/fetch_drugs_paginated.sh C2 $DIR/phase2.csv $PIPELINE_RECIPES --phase-highest --technology $TECH_ID --indication $IND_ID
bash $RECIPES/fetch_drugs_paginated.sh C1 $DIR/phase1.csv $PIPELINE_RECIPES --phase-highest --technology $TECH_ID --indication $IND_ID
bash $RECIPES/fetch_drugs_paginated.sh DR $DIR/discovery.csv $PIPELINE_RECIPES --phase-highest --technology $TECH_ID --indication $IND_ID
```

### Technology Step 4: Key companies
```bash
python3 $RECIPES/company_landscape.py $DIR > $DIR/companies.csv
```

### Technology Step 5: Recent deals (paginated)
```bash
bash $RECIPES/fetch_deals_paginated.sh '--query "dealTechnologies:\"$TECH_NAME\""' $DIR/deals.csv $PIPELINE_RECIPES
python3 $RECIPES/deals_analytics.py $DIR/deals.csv $DIR/deals.meta.json | tee $DIR/deals_analytics.md
```

### Technology Step 6: Generate report + strategic analysis
```bash
python3 $RECIPES/landscape_report_generator.py $DIR "$TECH_NAME" "" "<TECH>" | tee $DIR/report.md
python3 $RECIPES/strategic_scoring.py $DIR | tee $DIR/strategic_scores.md
python3 $RECIPES/opportunity_matrix.py $DIR | tee $DIR/opportunity_analysis.md
python3 $RECIPES/strategic_narrative.py $DIR "$TECH_NAME" | tee $DIR/strategic_briefing.md
python3 $RECIPES/compose_swot.py $DIR | tee $DIR/swot_composition.md
python3 $RECIPES/narrate.py $DIR "$TECH_NAME"
# Pass empty string for ID (not applicable in technology mode)
# For combined mode: python3 $RECIPES/landscape_report_generator.py $DIR "$TECH_NAME ($IND_NAME)" "" "<TECH> + <IND>" | tee $DIR/report.md
# USER_INPUT is the original user-supplied technology (and indication) name
# Report saved to $DIR/report.md
```

## Target Mode Workflow

When invoked as `/landscape --target "<TARGET>"`, use the following workflow instead of the indication workflow below.

### Target Setup
```bash
RECIPES="cli_anything/cortellis/skills/landscape/recipes"
PIPELINE_RECIPES="cli_anything/cortellis/skills/pipeline/recipes"
DIR="raw/<TARGET_SLUG>"
mkdir -p "$DIR"
```
Use a slug derived from the target name (e.g., `raw/glp-1-receptor`, `raw/pd-l1`, `raw/egfr`).

### Target Step 1: Resolve action name
```bash
ACTION_NAME=$(python3 $RECIPES/resolve_target.py "<TARGET>")
# Output: canonical action name (e.g. "Glucagon-like peptide 1 receptor agonist")
# Strategies: synonym table → NER → ontology → normalized retry
# Use this name with --action in all drug searches
```

### Target Step 2: Drugs by phase (paginated, --phase-highest for "drugs whose highest phase IS X")
```bash
bash $RECIPES/fetch_drugs_paginated.sh L $DIR/launched.csv $PIPELINE_RECIPES --phase-highest --action "$ACTION_NAME"
bash $RECIPES/fetch_drugs_paginated.sh C3 $DIR/phase3.csv $PIPELINE_RECIPES --phase-highest --action "$ACTION_NAME"
bash $RECIPES/fetch_drugs_paginated.sh C2 $DIR/phase2.csv $PIPELINE_RECIPES --phase-highest --action "$ACTION_NAME"
bash $RECIPES/fetch_drugs_paginated.sh C1 $DIR/phase1.csv $PIPELINE_RECIPES --phase-highest --action "$ACTION_NAME"
bash $RECIPES/fetch_drugs_paginated.sh DR $DIR/discovery.csv $PIPELINE_RECIPES --phase-highest --action "$ACTION_NAME"
```

### Target Step 3: Key companies
```bash
python3 $RECIPES/company_landscape.py $DIR > $DIR/companies.csv
```

### Target Step 4: Recent deals (paginated)
```bash
# Note: dealActionsPrimary is not a valid Cortellis deals API field (returns HTTP 500).
# Use free-text keyword query instead — over-fetches slightly but avoids 500 errors.
bash $RECIPES/fetch_deals_paginated.sh '--query "\"$ACTION_NAME\""' $DIR/deals.csv $PIPELINE_RECIPES
python3 $RECIPES/deals_analytics.py $DIR/deals.csv $DIR/deals.meta.json | tee $DIR/deals_analytics.md
```

### Target Step 5: Generate report + strategic analysis
```bash
python3 $RECIPES/landscape_report_generator.py $DIR "$ACTION_NAME" "" "<TARGET>" | tee $DIR/report.md
python3 $RECIPES/strategic_scoring.py $DIR | tee $DIR/strategic_scores.md
python3 $RECIPES/opportunity_matrix.py $DIR | tee $DIR/opportunity_analysis.md
python3 $RECIPES/strategic_narrative.py $DIR "$ACTION_NAME" | tee $DIR/strategic_briefing.md
# Pass empty string for ID (not applicable in target mode)
# USER_INPUT is the original user-supplied target name
# Report saved to $DIR/report.md
```

## Indication Workflow

### Setup
```bash
RECIPES="cli_anything/cortellis/skills/landscape/recipes"
PIPELINE_RECIPES="cli_anything/cortellis/skills/pipeline/recipes"
DIR="raw/<INDICATION_SLUG>"
mkdir -p "$DIR"
HEADER="name,id,phase,indication,mechanism,company,source"
```
Use a slug derived from the indication name (e.g., `raw/obesity`, `raw/nsclc`, `raw/mash`, `raw/huntingtons-disease`). Lowercase, hyphens for spaces, no apostrophes.

### Step 1: Resolve indication ID
```bash
RESULT=$(python3 $RECIPES/resolve_indication.py "<INDICATION>")
# Output: indication_id,indication_name
# Strategies: synonym lookup → NER → ontology → normalized retry → suffix stripping
# Handles: apostrophes (Huntington's), synonyms (sickle cell disease → anemia),
#   abbreviations (ALS, NSCLC, COPD), multi-word names
# Tested: 12 indications including obesity, NSCLC, MASH, Huntington's, sickle cell,
#   narcolepsy, acromegaly, cystic fibrosis, myasthenia gravis — all correct
```

### Step 2: Drugs by phase (with pagination for large indications)
```bash
# Always use the pagination script — handles both small and large indications:
bash $RECIPES/fetch_indication_phase.sh <ID> L $DIR/launched.csv $PIPELINE_RECIPES
bash $RECIPES/fetch_indication_phase.sh <ID> C3 $DIR/phase3.csv $PIPELINE_RECIPES
bash $RECIPES/fetch_indication_phase.sh <ID> C2 $DIR/phase2.csv $PIPELINE_RECIPES
bash $RECIPES/fetch_indication_phase.sh <ID> C1 $DIR/phase1.csv $PIPELINE_RECIPES
bash $RECIPES/fetch_indication_phase.sh <ID> DR $DIR/discovery.csv $PIPELINE_RECIPES
# Auto-paginates until ALL drugs fetched. Writes .meta.json with totalResults.
# Rate limit protection: 3s between pages, 10s retry on rate limit.
```

### Step 3: Enrich mechanisms (optional, adds ~2 API calls per empty drug)
```bash
python3 $RECIPES/enrich_mechanisms.py $DIR
# Fills empty mechanism fields from Drug Design (SI) by name search.
# Typical fill rate: 50-60% of empty mechanisms recovered.
# Max 20 lookups per phase file to control API calls.
```

### Step 4: Group biosimilars (optional, for indications with many biosimilars)
```bash
python3 $RECIPES/group_biosimilars.py $DIR
# Collapses biosimilar/follow-on entries under originator drug.
# RA: 140 launched → 72 after grouping. Critical for RA, breast cancer, oncology.
```

### Step 5: Key companies (deduplicated)
```bash
python3 $RECIPES/company_landscape.py $DIR > $DIR/companies.csv
```
Outputs deduplicated company counts with phase breakdown.

### Step 5b: Enrich company sizes (recommended)
```bash
python3 $RECIPES/enrich_company_sizes.py $DIR
```
Resolves top 20 companies via NER → batch-fetches `@companySize` (Large/Medium/Small) from Cortellis company-analytics. Writes `company_sizes.json`. Used by report generator for dynamic company classification (no hardcoded pharma lists).

### Step 6: Recent deals (paginated, up to 200)
```bash
bash $RECIPES/fetch_deals_paginated.sh '--indication "<INDICATION>"' $DIR/deals.csv $PIPELINE_RECIPES
```
Fetches up to 200 deals (4 pages of 50), sorted newest first. Writes `deals.meta.json` with totalResults.
Typically covers ~18 months of deal activity.

### Step 6b: Deal analytics
```bash
python3 $RECIPES/deals_analytics.py $DIR/deals.csv $DIR/deals.meta.json | tee $DIR/deals_analytics.md
```
Produces: deal type breakdown chart, top deal-makers table, deal velocity by quarter, summary stats.

### Step 7: Trial activity summary
```bash
python3 $RECIPES/trials_phase_summary.py <ID> $DIR/trials_summary.csv $DIR/companies.csv
# Shows total recruiting trials per phase + per-sponsor breakdown for top companies.
# Outputs: trials_summary.csv (phase counts) + trials_by_sponsor.csv (company x phase matrix)
```

### Step 8: Catch missing drugs (recommended)
```bash
python3 $RECIPES/catch_missing_drugs.py <ID> $DIR
# Fetches ALL drugs (no phase filter), compares against phase CSVs.
# Writes drugs missed by per-phase search to other.csv.
# Excludes attrition (discontinued, suspended, no development reported).
# Catches drugs in phases like "Preclinical" that --phase DR may miss.
```

### Step 9: Generate report
```bash
python3 $RECIPES/landscape_report_generator.py $DIR "<INDICATION_NAME>" "<INDICATION_ID>" "<USER_INPUT>" | tee $DIR/report.md
# Reads .meta.json files for accurate truncation warnings.
# Pipeline chart, mechanism density chart, top companies chart.
# Drug tables per phase, company ranking, deals, trials summary.
# USER_INPUT is the original user query; shown in header when it differs from resolved name.
# Report saved to $DIR/report.md for future reference.
```

### Step 10: Strategic scoring
```bash
python3 $RECIPES/strategic_scoring.py $DIR [PRESET] | tee $DIR/strategic_scores.md
# Computes: Competitive Position Index (CPI with A/B/C/D tiers), mechanism crowding, momentum indicators
# Outputs: strategic_scores.csv, mechanism_scores.csv + markdown to stdout
# Pure computation — no LLM calls. Deterministic and reproducible.
#
# Optional PRESET arg selects therapeutic area weights from config/presets/:
#   default      (20/30/20/15/15 — balanced)
#   oncology     (15/35/25/15/10 — phase + mechanism diversity)
#   rare_disease (30/25/10/20/15 — breadth + deal commitment)
#   neuro        (15/40/20/15/10 — P3 is exceptional due to attrition)
#   metabolic    (15/25/15/25/20 — deals + trial velocity dominate)
#   respiratory  (25/35/15/15/10 — launched franchise + trial execution weighted)
#   rare_cns     (35/30/10/15/10 — breadth + phase score for ultra-rare CNS)
#   io_combo     (10/40/30/10/10 — mechanism diversity + late-stage focus for I-O combos)
# Note: CPI tiers are percentile-based within each run (Tier A = top 10%, floor cpi>=40).
#   Tier A always exists when any company clears the floor — avoids Tier D collapse on sparse indications.
# Example: python3 $RECIPES/strategic_scoring.py $DIR respiratory
```

### Step 11: Opportunity analysis
```bash
python3 $RECIPES/opportunity_matrix.py $DIR | tee $DIR/opportunity_analysis.md
# Computes: mechanism x phase heatmap, white space identification, attrition-adjusted opportunity
# Outputs: opportunity_matrix.csv + markdown to stdout
# Classifies mechanisms: Mature, Crowded Pipeline, Emerging, White Space, Active
```

### Step 12: Strategic narrative (executive briefing)
```bash
python3 $RECIPES/strategic_narrative.py $DIR "<INDICATION_NAME>" | tee $DIR/strategic_briefing.md
# Produces 2-page executive briefing from scored data:
# - Executive Summary (5 key bullets)
# - Company 2x2 Matrix (Leaders/Fading Giants/Rising Challengers/Struggling)
# - Scenario Analysis (what if top company exits?)
# - Strategic Implications for 4 executive decisions
# Pure computation — no LLM calls. Every claim backed by a number.
```

### Step 12b: Scenario library (counterfactual analysis)
```bash
python3 $RECIPES/scenario_library.py $DIR "<INDICATION_NAME>" [--scenarios all|<name,...>] | tee $DIR/scenario_analysis.md
# Runs 5 counterfactual scenarios:
#   top_exit              — top company exits; ranks beneficiaries by specialty-buyer-fit
#   crowded_consolidation — crowded mechanism consolidates to top-3 winners
#   loe_wave              — LOE wave simulation (requires loe_metrics.csv from loe_analysis.py)
#   new_entrant_disruption — well-funded entrant targets white-space mechanisms
#   pivotal_failure       — top-3 company's flagship phase-3 drug fails
# Pure computation, stdlib only. Run after strategic_scoring.py and opportunity_matrix.py.
# Example: python3 $RECIPES/scenario_library.py $DIR "Asthma" --scenarios top_exit,loe_wave
```

### Step 12c: LOE analysis
```bash
python3 $RECIPES/loe_analysis.py $DIR | tee $DIR/loe_analysis.md
# Computes Loss-of-Exclusivity exposure per company:
#   - launched drug count vs phase-3 backfill gap
#   - LOE exposure % (launched / total pipeline)
#   - HIGH risk flag: refill_gap >= 3 or exposure > 50%
# Outputs: loe_metrics.csv + markdown to stdout
# Required input for scenario_library.py loe_wave scenario
```

### Step 13: Cross-skill composition (optional)
```bash
python3 $RECIPES/compose_swot.py $DIR | tee $DIR/swot_composition.md
# Identifies top Leader-tier companies and their flagship drugs
# Outputs markdown with /drug-swot commands for the orchestrator to execute
# Enables /landscape → /drug-swot cross-skill chains
```

### Step 14: LLM narration context (optional)
```bash
python3 $RECIPES/narrate.py $DIR "<INDICATION_NAME>"
# Prepares structured context for LLM-based narrative briefing
# Writes narrate_context.json with top companies, mechanisms, opportunities, risks
# Outputs a prompt template for the orchestrator to feed to an LLM
# Honors council recommendation: structured LLM prompts over scored data (no freeform)
```

## Output Rules

- ALWAYS list ALL drugs in tables. NEVER truncate with "+ N others".
- Give exact counts from API @totalResults.
- Show warning only when data is actually truncated (metadata-based).
- Do not add drugs from training data.
- Present the report generator output directly. Do not reformat its tables.
- Company classification uses Cortellis `@companySize` + phase-weighted scoring (no hardcoded pharma lists):
  - Phase-weighted scoring: Launched=5, Phase 3=4, Phase 2=3, Phase 1=2, Discovery/Preclinical=1
  - **Leader**: score >= 10, OR (Large company AND score >= 4)
  - **Active**: score >= 4, OR Large company (from Cortellis company-analytics)
  - **Emerging**: everything else

### Confidence & abstention

`strategic_narrative.py` and `scenario_library.py` now emit confidence labels — **HIGH**, **MEDIUM**, **LOW**, or **ABSTAIN** — on key claims and scenario outputs.

- **HIGH**: claim is supported by dense pipeline data (many drugs, multiple large-cap companies, substantial deal activity).
- **MEDIUM**: claim is directionally supported but rests on moderate data (thin launched franchise, limited deals, or few large players).
- **LOW**: claim is speculative; data is sparse and a single data point could reverse the conclusion.
- **ABSTAIN**: data is too thin to rank or recommend. Treat ABSTAIN as "no recommendation", **not** "weakest recommendation". Downstream consumers must not infer a preference from an ABSTAIN label.

Confidence labels appear on: Primary Beneficiaries (strategic_narrative), all 5 scenario headers and `top_exit` beneficiary rows (scenario_library).

### Reader orientation

- For definitions of all confidence labels, scoring factors, and tier thresholds, see **`docs/glossary.md`**.

## Output Format

```
# Competitive Landscape: <Indication>

## Market Overview
**Total drugs:** X | **Deals:** X | **Recruiting trials:** X

(ASCII charts: Pipeline by Phase, Competitive Density by Mechanism, Top Companies)

## Pipeline Summary
| Phase | Count |
|-------|-------|

### Launched (X)
| Drug | Company | Mechanism |
(list ALL)

### Phase 3 (X)
(list ALL)

(repeat for Phase 2, Phase 1, Discovery)

## Key Companies
| Company | Unique Drugs | Market Position |
|---------|-------------|-----------------|
(deduplicated — Leader/Active/Emerging based on drug count)

## Recent Deals
| Deal | Partner | Type | Date |
(sorted newest first)

## Recruiting Trials
| Phase | Trials |
|-------|--------|

## Strategic Intelligence (from strategic_scoring.py + opportunity_matrix.py)
- Competitive Position Index (ranked companies with CPI scores)
- Mechanism Crowding Analysis (crowding index per mechanism)
- Momentum Signals (deal velocity trends)
- Opportunity Heatmap (mechanism x phase matrix)
- White Space Identification (underserved mechanism-phase combinations)
- Risk Zones (high attrition mechanisms to avoid)
```

## Documentation

- **Schema contract**: `schemas/landscape_output.schema.json` — JSON Schema draft-07 for all CSV/JSON outputs. Downstream skills should validate against this.
- **CPI factor audit**: `docs/cpi_factor_audit.md` — construct validity analysis of the 5 scoring factors, including known limitations (double counting, selection bias, temporal mismatch).
- **Weight derivation methodology**: `docs/weight_derivation.md` — how CPI weights SHOULD be derived empirically when historical data is available (currently using committee-compromise weights).
- **Presets**: `config/presets/*.json` — therapeutic area-specific CPI weights (default, oncology, rare_disease, neuro, metabolic, respiratory, rare_cns, io_combo).
- **Validation harness**: `docs/validation_harness.md` — reproducibility test protocol, known ground-truth fixtures (asthma, IPF, ALS), and regression-check commands.
- **Stress test findings**: `docs/fragmented_indication_stress_test.md` — documents Tier D collapse on IPF/ALS, thin-pipeline specialty-fit degeneracy, and dealActionsPrimary API bug; describes the adaptive-tier and engagement-tiebreak fixes applied in v0.9.
- **Glossary**: `docs/glossary.md` — definitions for confidence labels (HIGH/MEDIUM/LOW/ABSTAIN), CPI scoring factors, tier thresholds, and key terms used across all strategic output files.
- **TOS check**: `docs/tos_check.md` — Cortellis redistribution question, **ANSWERED 2026-04-05**: derived analytical outputs may be shared externally with attribution; raw Cortellis data stays internal. Code is MIT-licensed (repository `LICENSE`).
- **Pre-registered predictions**: `docs/pre_registered_predictions.md` — forward-looking scenario predictions registered before outcomes are known, for future back-testing of scenario_library.py accuracy.

## Recipes (15 total)

### resolve_indication.py — Indication ID resolution
```bash
python3 $RECIPES/resolve_indication.py "<INDICATION>"
# 5-strategy resolution: synonym table → NER → ontology → normalized retry → suffix strip
# Handles apostrophes, abbreviations (ALS, NSCLC), common synonyms
# Tested on 12 diverse indications — all correct
```

### fetch_indication_phase.sh — Paginated drug fetch
```bash
bash $RECIPES/fetch_indication_phase.sh <IND_ID> <PHASE> <OUTPUT_CSV> $PIPELINE_RECIPES
# Auto-paginates up to 300 drugs per phase. Auto-detects venv PATH.
# Writes .meta.json with totalResults for truncation detection.
# Rate limit: 3s between pages, guards empty results, no false 429 detection.
```

### enrich_mechanisms.py — SI mechanism enrichment
```bash
python3 $RECIPES/enrich_mechanisms.py $DIR
# Searches Drug Design (SI) by drug name for empty mechanism fields.
# Typical fill rate: 50-60%. Max 20 lookups per file.
# Example: pirarubicin → "DNA Topoisomerase II Inhibitors; DNA-Intercalating Drugs"
```

### group_biosimilars.py — Biosimilar grouping
```bash
python3 $RECIPES/group_biosimilars.py $DIR
# Detects "biosimilar"/"follow-on" in drug names, groups under originator.
# RA launched: 140 → 72 rows (68 biosimilars grouped).
# Shows: "adalimumab (+ 20 biosimilars)" instead of 20 separate rows.
```

### company_landscape.py — Deduplicated company analysis
```bash
python3 $RECIPES/company_landscape.py $DIR > $DIR/companies.csv
# Counts unique drugs per company (not drug-phase entries).
# Phase breakdown: launched, phase3, phase2, phase1, discovery.
```

### trials_phase_summary.py — Trial counts by phase
```bash
python3 $RECIPES/trials_phase_summary.py <IND_ID> $DIR/trials_summary.csv
# Makes per-phase API calls to get accurate totalResults.
# Shows total recruiting count, not just the top 50.
```

### resolve_target.py — Target/action name resolution
```bash
python3 $RECIPES/resolve_target.py "<TARGET>"
# 3-strategy resolution: synonym table → NER (Action entities) → ontology → normalized retry
# Returns canonical action name for use with --action flag in drugs search
# Handles abbreviations (GLP-1, PD-L1, EGFR, CDK4/6) and full names
# Example: "GLP-1 receptor" → "Glucagon-like peptide 1 receptor agonist"
```

### resolve_technology.py — Technology/modality name resolution
```bash
python3 $RECIPES/resolve_technology.py "<TECH>"
# 2-strategy resolution: synonym table → ontology (--category technology) → normalized retry
# Returns canonical technology name for use with --technology flag in drugs search
# Handles abbreviations (ADC, mRNA, CAR-T) and alternate spellings
# Example: "ADC" → "Antibody drug conjugate", "mRNA" → "mRNA therapy"
# Example: "gene therapy" → "Gene transfer system viral"
```

### landscape_report_generator.py — Report with ASCII charts
```bash
python3 $RECIPES/landscape_report_generator.py $DIR "<NAME>" "<ID>" "<USER_INPUT>"
# Reads .meta.json for accurate truncation warnings (no false positives).
# Pipeline chart, mechanism density chart, top companies chart.
# Wider table columns: drug (60), company (40), mechanism (50).
# USER_INPUT shown in header when it differs from resolved indication name.
```

### strategic_scoring.py — Competitive Position Index + Mechanism Crowding
```bash
python3 $RECIPES/strategic_scoring.py $DIR
# Computes CPI per company (weighted: pipeline breadth 20%, phase score 30%,
#   mechanism diversity 20%, deal activity 15%, trial intensity 15%)
# Computes mechanism crowding index (active_count * company_count)
# Computes deal momentum (recent 6m vs prior 6m velocity)
# Outputs: strategic_scores.csv, mechanism_scores.csv + markdown to stdout
# Pure computation — no LLM calls
```

### strategic_narrative.py — Executive Briefing + Scenario Analysis
```bash
python3 $RECIPES/strategic_narrative.py $DIR "<INDICATION_NAME>"
# 2-page executive briefing from scored data
# Company 2x2 matrix: Leaders / Fading Giants / Rising Challengers / Struggling
# Scenario analysis: what if top company exits? Who benefits?
# Strategic implications for 4 decisions: enter, partner, cut, differentiate
# Every claim backed by a computed number — no LLM inference
```

### compose_swot.py — Cross-skill composition (/landscape → /drug-swot)
```bash
python3 $RECIPES/compose_swot.py $DIR
# Identifies top 5 Leader-tier companies from strategic_scores.csv
# Extracts flagship drugs from launched.csv / phase3.csv
# Outputs markdown with /drug-swot commands for orchestrator execution
# Pure Python stdlib
```

### narrate.py — LLM narration scaffold
```bash
python3 $RECIPES/narrate.py $DIR "<INDICATION_NAME>"
# Reads all scored CSVs + opportunity_matrix + deals metadata
# Builds structured context dict (top companies, mechanisms, opportunities, risks)
# Writes $DIR/narrate_context.json
# Prints prompt template for orchestrator to feed to LLM
# Honors council spec: structured prompts over scored data, no freeform
```

### opportunity_matrix.py — Mechanism x Phase Heatmap + White Space
```bash
python3 $RECIPES/opportunity_matrix.py $DIR
# Builds mechanism x phase matrix from all drug CSVs
# Classifies mechanisms: Mature, Crowded Pipeline, Emerging, White Space, Active
# Computes attrition-adjusted opportunity score per mechanism
# Identifies top 5 strategic opportunities + risk zones (graveyard mechanisms)
# Outputs: opportunity_matrix.csv + markdown to stdout
```

NOTE: This skill reuses pipeline recipes for CSV conversion:
- `$PIPELINE_RECIPES/ci_drugs_to_csv.py`
- `$PIPELINE_RECIPES/deals_to_csv.py`
- `$PIPELINE_RECIPES/trials_to_csv.py`
