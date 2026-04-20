---
name: landscape
description: /landscape: Competitive Landscape Report
---

# /landscape — Competitive Landscape Report

Generate a full competitive landscape for a therapeutic indication.

> **Version: v0.9-internal POC** (2026-04-05). CPI scores and strategic briefings are directional, not definitive — validate against domain judgment before acting on external commitments. Governance artifacts (council transcripts, blind-test protocols, validation runs, reproducibility kits) live under `docs/governance/` for interested reviewers.

## LICENSING

> **Code:** MIT (see repository `LICENSE`).
> **Derived analytical outputs** (strategic briefings, scenario libraries, CPI rankings, mechanism crowding indices): shareable per the TOS answer recorded in `docs/governance/tos_check.md` (ANSWERED 2026-04-05). Attribute Cortellis/Clarivate as the underlying data source when sharing externally.
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

> **New to `/landscape`?** Read `docs/worked_example_mash.md` for a narrated end-to-end example before your first run.

## Technology Mode Workflow

<!-- Model routing
  haiku  — Tech Step 1 (resolve technology/indication ID)
  sonnet — Tech Steps 2–5 (fetch drugs, enrich, deals)
  opus   — Tech Step 6 (report, scoring, narrative, wiki compile)
-->

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

### Technology Step 3b: Enrich mechanisms (recommended)
```bash
python3 $RECIPES/enrich_mechanisms.py $DIR
# Fills empty mechanism fields from Drug Design (SI) by name search.
```

### Technology Step 3c: Group biosimilars (optional, for indications with many biosimilars)
```bash
python3 $RECIPES/group_biosimilars.py $DIR
```

### Technology Step 4: Key companies
```bash
python3 $RECIPES/company_landscape.py $DIR > $DIR/companies.csv
```

### Technology Step 4b: Enrich company sizes (recommended)
```bash
python3 $RECIPES/enrich_company_sizes.py $DIR
```

### Technology Step 4c: Normalize company names (recommended)
```bash
python3 $RECIPES/company_normalize.py $DIR
```

### Technology Step 5: Recent deals (paginated)
```bash
# Note: dealTechnologies is not a valid Cortellis deals API field (returns HTTP 500).
# Use free-text keyword query instead — over-fetches slightly but avoids 500 errors.
bash $RECIPES/fetch_deals_paginated.sh '--query "\"$TECH_NAME\""' $DIR/deals.csv $PIPELINE_RECIPES
python3 $RECIPES/deals_analytics.py $DIR/deals.csv $DIR/deals.meta.json | tee $DIR/deals_analytics.md
```

### Technology Step 6: Generate report + strategic analysis
```bash
python3 $RECIPES/landscape_report_generator.py $DIR "$TECH_NAME" "" "<TECH>" | tee $DIR/report.md
python3 $RECIPES/strategic_scoring.py $DIR | tee $DIR/strategic_scores.md
python3 $RECIPES/opportunity_matrix.py $DIR | tee $DIR/opportunity_analysis.md
python3 $RECIPES/strategic_narrative.py $DIR "$TECH_NAME" | tee $DIR/strategic_briefing.md
python3 $RECIPES/loe_analysis.py $DIR | tee $DIR/loe_analysis.md
python3 $RECIPES/scenario_library.py $DIR "$TECH_NAME" | tee $DIR/scenario_analysis.md
python3 $RECIPES/compose_swot.py $DIR | tee $DIR/swot_composition.md
python3 $RECIPES/narrate.py $DIR "$TECH_NAME"
# Pass empty string for ID (not applicable in technology mode)
# For combined mode: python3 $RECIPES/landscape_report_generator.py $DIR "$TECH_NAME ($IND_NAME)" "" "<TECH> + <IND>" | tee $DIR/report.md
# USER_INPUT is the original user-supplied technology (and indication) name
# Report saved to $DIR/report.md
```

## Target Mode Workflow

<!-- Model routing
  haiku  — Target Step 1 (resolve action name)
  sonnet — Target Steps 2–4 (fetch drugs, enrich, deals)
  opus   — Target Step 5 (report, scoring, narrative, wiki compile)
-->

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

### Target Step 2b: Enrich mechanisms (recommended)
```bash
python3 $RECIPES/enrich_mechanisms.py $DIR
# Fills empty mechanism fields from Drug Design (SI) by name search.
```

### Target Step 2c: Group biosimilars (optional, for targets with many biosimilars)
```bash
python3 $RECIPES/group_biosimilars.py $DIR
```

### Target Step 3: Key companies
```bash
python3 $RECIPES/company_landscape.py $DIR > $DIR/companies.csv
```

### Target Step 3b: Enrich company sizes (recommended)
```bash
python3 $RECIPES/enrich_company_sizes.py $DIR
```

### Target Step 3c: Normalize company names (recommended)
```bash
python3 $RECIPES/company_normalize.py $DIR
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
python3 $RECIPES/loe_analysis.py $DIR | tee $DIR/loe_analysis.md
python3 $RECIPES/scenario_library.py $DIR "$ACTION_NAME" | tee $DIR/scenario_analysis.md
python3 $RECIPES/compose_swot.py $DIR | tee $DIR/swot_composition.md
python3 $RECIPES/narrate.py $DIR "$ACTION_NAME"
# Pass empty string for ID (not applicable in target mode)
# USER_INPUT is the original user-supplied target name
# Report saved to $DIR/report.md
```

## Indication Workflow

<!-- Model routing
  haiku  — Steps 0, 1 (resolve/classify — lightweight decisions, no synthesis)
  sonnet — Steps 2–8 (fetch + enrich — script execution + moderate interpretation)
  opus   — Steps 9–15 (report, scoring, narrative, wiki compile — deep synthesis)
-->

### Step 0: Wiki freshness check <!-- model: haiku -->
Before running the pipeline, check if a fresh compiled wiki article exists:
```bash
python3 -c "
import sys; sys.path.insert(0, '.')
from cli_anything.cortellis.utils.wiki import check_freshness, slugify
slug = slugify('<INDICATION>')
result = check_freshness(slug)
print(f'{slug}:{result}')
"
```
- If result is `fresh`: Read `wiki/indications/<slug>.md` and answer from compiled knowledge. **Skip Steps 1–15.**
- If result is `stale` or `missing`: Proceed with Setup and Steps 1–14, then compile in Step 15.

### Setup
```bash
RECIPES="cli_anything/cortellis/skills/landscape/recipes"
PIPELINE_RECIPES="cli_anything/cortellis/skills/pipeline/recipes"
DIR="raw/<INDICATION_SLUG>"
mkdir -p "$DIR"
HEADER="name,id,phase,indication,mechanism,company,source"
```
Use a slug derived from the indication name (e.g., `raw/obesity`, `raw/nsclc`, `raw/mash`, `raw/huntingtons-disease`). Lowercase, hyphens for spaces, no apostrophes.

### Step 1: Resolve indication ID <!-- model: haiku -->
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
Resolves top 30 companies via NER → batch-fetches `@companySize` (Large/Medium/Small) from Cortellis company-analytics. Writes `company_sizes.json`. Used by report generator for dynamic company classification (no hardcoded pharma lists).

### Step 5c: Normalize company names (recommended)
```bash
python3 $RECIPES/company_normalize.py $DIR
```
Collapses company name variants to canonical form using `config/company_aliases.csv` (e.g., "Lilly", "Eli Lilly & Co", "Eli Lilly and Company" → one row). Critical for trustworthy downstream CPI, crowding, and specialty-buyer-fit scores. Writes `normalization_log.json`. Alias CSV flagged `REQUIRES_DOMAIN_REVIEW` — extend as needed.

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

### Step 6c: Enrich deal financials (recommended)
```bash
python3 $RECIPES/enrich_deal_financials.py $DIR
# Fetches expanded deal records in batches of 30 via deals-intelligence API.
# Extracts: upfront payments, milestones, royalties, total deal value.
# Writes deal_financials.csv and deal_comps.md.
# Rate limit: 3s between batches.
```

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

### Step 8b: Enrich launched drugs with regulatory approval regions (recommended)
```bash
python3 $RECIPES/enrich_approval_regions.py $DIR <INDICATION_ID> "<INDICATION_NAME>"
# Walks IDdbDevelopmentStatus.DevelopmentStatusCurrent[] for each launched drug
# and keeps only (country, status, date) rows whose indication matches the target.
# Aggregates per-drug: approval countries, earliest launch date, has_us/has_eu/has_jp.
# Writes approval_regions.json and approval_regions.md.
# Cost: 1 batch API call per 20 launched drugs (e.g. 3 calls for psoriasis=49).
#
# Surfaces "pre-first-in-class in the West" markets: when 0 launched drugs are
# approved in US/EU/JP for this indication, the downstream report emits a
# "no Western-approved drug" FINDING banner. Validated on Sjögren's (0% Western)
# vs psoriasis (61% Western).
```

### Step 8c: Enrich regulatory milestones (recommended)
```bash
python3 $RECIPES/enrich_regulatory_milestones.py $DIR "<INDICATION_NAME>"
# Searches regulatory events for top 20 drugs (launched + phase 3) across US, EU, JP.
# Extracts: submissions, approvals, PDUFA dates, label changes.
# Writes regulatory_milestones.csv and regulatory_timeline.md.
# Rate limit: 2s between API calls. Handles 0-result drugs gracefully.
```

### Step 8d: Enrich with recent publications (optional)
```bash
python3 $RECIPES/enrich_literature.py $DIR "<INDICATION_NAME>"
# Searches literature for top 10 drugs (launched + phase 3).
# Writes literature_summary.csv and recent_publications.md.
# Rate limit: 2s between API calls.
```

### Step 8e: Enrich with recent press releases (recommended)
```bash
python3 $RECIPES/enrich_press_releases.py $DIR "<INDICATION_NAME>"
# Searches press releases for top 10 companies.
# Writes press_releases_summary.csv and recent_press_releases.md.
# Rate limit: 2s between API calls.
```

### Step 8f: Enrich with historical pipeline timeline (optional)
```bash
python3 $RECIPES/enrich_historical_timeline.py $DIR --max-drugs 100 --months 24
# Fetches change_history per drug via Cortellis API (launched + Phase 3 + Phase 2).
# Reconstructs monthly pipeline snapshots going back 24 months.
# Writes phase_timeline.csv, historical_snapshots.csv, historical_timeline.md.
# Rate limit: 1s between API calls. ~1 min for 66 drugs.
# Use when: "how has the pipeline evolved?", "show me trends", "historical view"
```

### Step 9: Generate report <!-- model: opus -->
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

### Step 12: Strategic narrative (executive briefing) <!-- model: opus -->
```bash
python3 $RECIPES/strategic_narrative.py $DIR "<INDICATION_NAME>" | tee $DIR/strategic_briefing.md
# Produces 2-page executive briefing from scored data:
# - Executive Summary (5 key bullets)
# - Company 2x2 Matrix (Leaders/Fading Giants/Rising Challengers/Under Pressure)
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

### Step 15: Compile landscape to wiki <!-- model: opus -->
```bash
python3 $RECIPES/compile_dossier.py $DIR "<INDICATION_NAME>"
# Compiles all landscape outputs into wiki/indications/<slug>.md
# Creates/updates company articles in wiki/companies/
# Refreshes wiki/INDEX.md with current entries
# Saves previous snapshot in frontmatter for temporal diffs
# Enables future sessions to answer from compiled knowledge (Step 0 fast-path)
```

### Post-Run Review (optional, run after report is delivered)
```bash
python3 $RECIPES/../post_run_reviewer.py landscape $DIR "<INDICATION_NAME>"
```
Read the manifest output above. If you see a clear pattern worth encoding (e.g. an
optional enrichment step that returned empty for this indication class), update the
`## Learned Optimizations` section below with a targeted patch. Only add an
optimization if it would generalize to future runs of similar inputs — not for
one-off anomalies. If unsure, skip.

## Learned Optimizations
<!-- Auto-updated by post-run review. Add generalizable skip rules and fast-path hints here. -->

### Cross-drill: Deep dive into top drugs (optional)
After completing the landscape, if the user wants to drill into specific drugs:
1. Read the compiled wiki article or the Key Drugs section to identify top drugs
2. For each drug of interest, run the /drug-profile workflow:
   ```bash
   # Example for each top drug:
   DIR_DRUG="raw/drugs/<DRUG_SLUG>"
   mkdir -p "$DIR_DRUG"
   # Follow /drug-profile SKILL.md steps 1-10, using $DIR_DRUG as output
   python3 cli_anything/cortellis/skills/drug-profile/recipes/compile_drug.py "$DIR_DRUG" "<DRUG_NAME>"
   ```
3. Drug articles compile to wiki/drugs/<slug>.md with [[wikilinks]] back to the indication
4. Use when: "drill into the top drugs", "deep dive on semaglutide", "profile the leaders"

### Diff: What changed since last run?
```bash
python3 $RECIPES/diff_landscape.py <INDICATION_SLUG>
```
- Compares current wiki article with its previous snapshot (no API calls)
- Use when: "what changed in obesity?", "what's new since last time?", "any pipeline changes?"
- Requires at least 2 compile runs (current + previous_snapshot in frontmatter)
- Shows: drug count deltas by phase, deal activity changes, company ranking shifts

### Portfolio: Cross-indication overview
```bash
python3 $RECIPES/portfolio_report.py
```
- Reads all compiled wiki articles (no API calls)
- Use when: "compare my indications", "portfolio overview", "which area has the most opportunity?"
- Shows: indication comparison table, company presence across areas, portfolio signals

### Signals: Strategic intelligence report
```bash
python3 $RECIPES/signals_report.py
```
- Scans all compiled wiki articles for strategic signals (no API calls)
- Detects: new Phase 3 entrants, top company changes, deal acceleration, pipeline surges
- Ranks by severity (high/medium/low) with deterministic action templates
- Use when: "what's happening?", "any strategic signals?", "intelligence report", "what changed across the portfolio?"

### Insights: Accumulated analysis intelligence
```bash
python3 $RECIPES/insights_report.py [--days 30] [--indication SLUG]
```
- Shows key findings, scenarios, and implications from previous landscape analyses
- Accumulates automatically on each session flush
- Use when: "what have we learned?", "previous insights", "accumulated intelligence"

### Lint: Wiki health check
```bash
python3 $RECIPES/lint_wiki.py
```
- Runs 7 structural checks: broken links, orphans, stale articles, missing refs, empty sections, index consistency, freshness gaps
- Use when: "check wiki health", "lint", "any broken links?"

### Graph: Knowledge graph from wiki
```bash
python3 $RECIPES/graphify_wiki.py
```
- Builds NetworkX graph from all wiki article frontmatter (no API calls, no LLM)
- Detects: god nodes (highest connectivity), clusters (communities), bridge nodes
- Writes wiki/graph.json + wiki/GRAPH_REPORT.md
- Use when: "show me the knowledge graph", "what entities are most connected?", "find clusters"
- Requires: `pip install networkx` (or `pip install cortellis-cli[graph]`)

### Wiki management
```bash
python3 $RECIPES/wiki_manage.py status                    # Show KB health summary
python3 $RECIPES/wiki_manage.py reset                     # Delete wiki/ + daily/ (fresh start, raw/ preserved)
python3 $RECIPES/wiki_manage.py reset --keep-daily         # Reset wiki/ only, keep daily logs
python3 $RECIPES/wiki_manage.py remove <INDICATION_SLUG>   # Remove one indication + company refs + raw data
python3 $RECIPES/wiki_manage.py prune                     # Remove wiki articles with no raw/ source
```
- Use when: "reset the KB", "remove huntingtons from wiki", "wiki status", "clean up the knowledge base"
- `remove` also cleans company articles (removes indication references, deletes companies with no remaining indications)
- `reset` preserves raw/ API data so you can recompile without re-fetching

### Export: PowerPoint deck (optional)
```bash
python3 $RECIPES/export_pptx.py $DIR "<INDICATION_NAME>"
# Generates <indication>-landscape.pptx in $DIR
# Slides: Title, Executive Summary, Pipeline Chart, Competitive Table,
#   Mechanism Analysis, Deal Landscape, Regulatory (if available), Opportunity Assessment
# Professional pharma styling: 16:9, Calibri, navy/blue palette
# Use when: user asks for slides, deck, PowerPoint, presentation
```

### Export: Excel workbook (optional)
```bash
python3 $RECIPES/export_xlsx.py $DIR "<INDICATION_NAME>"
# Generates <indication>-landscape.xlsx in $DIR
# Sheets: Pipeline by Phase, Company Rankings, Mechanism Analysis, Deals, Opportunity Matrix
# Auto-filters, frozen headers, conditional formatting on CPI
# Use when: user asks for Excel, spreadsheet, workbook, data export
```

### Audience-specific formatting (optional)
```bash
python3 $RECIPES/format_audience.py $DIR "<INDICATION_NAME>" --audience bd
# Generates <indication>-bd-brief.md — focused on deal comps, white space, licensing targets
# Use when: BD asks for competitive context, deal evaluation support

python3 $RECIPES/format_audience.py $DIR "<INDICATION_NAME>" --audience exec
# Generates <indication>-exec-brief.md — 5-bullet summary, plain language, one page
# Use when: VP/exec asks for board prep, strategic overview, portfolio summary
```

## Execution Rules

- Once the final report has been delivered to the user, **do not respond to background task completion notifications**. Discard them silently — they are late arrivals for steps already processed. One-line acknowledgement at most if unavoidable; never repeat the full summary.

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
- **Validation harness**: `docs/governance/validation_harness.md` — reproducibility test protocol, known ground-truth fixtures (asthma, IPF, ALS), and regression-check commands.
- **Stress test findings**: `docs/governance/fragmented_indication_stress_test.md` — documents Tier D collapse on IPF/ALS, thin-pipeline specialty-fit degeneracy, and dealActionsPrimary API bug; describes the adaptive-tier and engagement-tiebreak fixes applied in v0.9.
- **Glossary**: `docs/glossary.md` — definitions for confidence labels (HIGH/MEDIUM/LOW/ABSTAIN), CPI scoring factors, tier thresholds, and key terms used across all strategic output files.
- **TOS check**: `docs/governance/tos_check.md` — Cortellis redistribution question, **ANSWERED 2026-04-05**: derived analytical outputs may be shared externally with attribution; raw Cortellis data stays internal. Code is MIT-licensed (repository `LICENSE`).
- **Pre-registered predictions**: `docs/governance/pre_registered_predictions.md` — forward-looking scenario predictions registered before outcomes are known, for future back-testing of scenario_library.py accuracy.
- **Audit trail spec**: `docs/governance/audit_trail_spec.md` — audit_trail/v1 schema, bottom-of-file HTML-comment placement, and how to cite `/landscape` output in an IC memo.
- **Freshness contract**: `docs/freshness_contract.md` — staleness thresholds, user-visible warning placement, and the "no silent history rewrite" rule for reruns.

## Recipes (16 total)

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
# Company 2x2 matrix: Leaders / Fading Giants / Rising Challengers / Under Pressure
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

### enrich_approval_regions.py — Regulatory approval scope per launched drug
```bash
python3 $RECIPES/enrich_approval_regions.py $DIR <IND_ID> "<IND_NAME>"
# Walks IDdbDevelopmentStatus.DevelopmentStatusCurrent[] per drug, keeps
# (country, L|R status, date) rows where Indication.@id == target OR
# indication name contains target (catches child indications without ontology calls).
# Outputs approval_regions.json + approval_regions.md.
# Enables the report generator to distinguish "launched for this indication
# in US/EU/JP" vs "launched but only in non-Western regions via a broad label".
```

### company_normalize.py — Company name normalization
```bash
python3 $RECIPES/company_normalize.py $DIR
# Reads config/company_aliases.csv for variant→canonical mappings
# Case-insensitive exact match on trimmed name — no fuzzy matching
# Rewrites company column in all phase CSVs; also principal/partner in deals.csv
# Writes normalization_log.json with per-variant rewrite counts and alias CSV sha256
# Idempotent for CSV rewrites: running twice produces byte-identical CSV output (normalization_log.json carries a fresh run_timestamp_utc on each run)
# Missing alias CSV → warn + exit 0 (degrades gracefully, no hard failure)
```

NOTE: This skill reuses pipeline recipes for CSV conversion:
- `$PIPELINE_RECIPES/ci_drugs_to_csv.py`
- `$PIPELINE_RECIPES/deals_to_csv.py`
- `$PIPELINE_RECIPES/trials_to_csv.py`
