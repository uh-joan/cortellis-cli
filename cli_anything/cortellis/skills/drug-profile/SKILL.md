---
name: drug-profile
description: /drug-profile: Deep Drug Profile
---

# /drug-profile — Deep Drug Profile

Everything about a single drug from Cortellis data.

## Usage

```
/drug-profile tirzepatide
/drug-profile semaglutide
/drug-profile 101964
```

## Workflow

<!-- Model routing
  haiku  — Step 1 (resolve drug ID — lightweight lookup)
  sonnet — Steps 2–9 (fetch drug record, financials, history, deals, trials, externals)
  opus   — Steps 10–11 (report generation, SWOT synthesis, wiki compile)
-->

### Setup
```bash
RECIPES="cli_anything/cortellis/skills/drug-profile/recipes"
```

### Step 1: Resolve drug ID and INN slug <!-- model: haiku -->
```bash
RESULT=$(python3 $RECIPES/resolve_drug.py "<DRUG_NAME>")
DRUG_ID=$(echo "$RESULT" | cut -d',' -f1)
DRUG_NAME_RESOLVED=$(echo "$RESULT" | cut -d',' -f2)
DRUG_SLUG=$(echo "$RESULT" | cut -d',' -f5)
DIR="raw/drugs/$DRUG_SLUG"
mkdir -p "$DIR"
# Output: drug_id,drug_name,phase,indication_count,inn_slug
# DRUG_SLUG is always the normalized INN (e.g. "ozempic" → "semaglutide")
```
The recipe searches by name, prefers exact matches over combinations, picks highest phase.
If user provides a numeric ID, skip this step.

### Step 2: Full drug record
```bash
cortellis --json drugs get <DRUG_ID> --category report --include-sources > $DIR/record.json
```

### Step 3: SWOT analysis
```bash
cortellis --json drugs swots <DRUG_ID> > $DIR/swot.json
```
May be empty for niche/early-stage drugs — skip section if empty.

### Step 4: Financial data
```bash
cortellis --json drugs financials <DRUG_ID> > $DIR/financials.json
```
May be empty for non-launched drugs — skip section if empty.

### Step 5: Development history
```bash
cortellis --json drugs history <DRUG_ID> > $DIR/history.json
```

### Step 6: Related deals
```bash
cortellis --json deals search --drug "$DRUG_SLUG" --hits 10 --sort-by "-dealDateStart" > $DIR/deals.json
```

### Step 7: Active trials (paginated)
```bash
bash $RECIPES/fetch_trials.sh "$DRUG_SLUG" $DIR/trials.json
```
Fetches all Recruiting + Active-not-recruiting trials with pagination. No cap.

### Step 8: Regulatory milestones
```bash
python3 cli_anything/cortellis/skills/landscape/recipes/enrich_regulatory_milestones.py $DIR "$DRUG_NAME_RESOLVED"
# Fetches submissions, approvals, PDUFA dates, label changes across US, EU, JP.
# Writes: regulatory_milestones.csv and regulatory_timeline.md
# Rate limit: 2s between API calls. Handles 0-result drugs gracefully.
```

### Step 7b: ClinicalTrials.gov enrichment (external)
```bash
python3 $RECIPES/enrich_ct_trials.py $DIR "$DRUG_NAME_RESOLVED"
```
Fetches RECRUITING + ACTIVE_NOT_RECRUITING trials from ClinicalTrials.gov (free, no auth).
Writes: `ct_trials.json`, `ct_trials_summary.md`. Cross-checks count vs Cortellis trials.json if present.

### Step 8b: Recent publications
```bash
cortellis --json literature search --query "$DRUG_SLUG" --hits 10 --sort-by "-date" > $DIR/literature.json
```
Fetches recent publications for this drug. May return 0 results for niche/early-stage drugs — skip section if empty.

### Step 8c: FDA approval data (external)
```bash
python3 $RECIPES/enrich_fda_approval.py $DIR "$DRUG_NAME_RESOLVED" --phase "$PHASE"
```
Fetches FDA data from api.fda.gov (no auth required). Pass `--phase` from the Cortellis record (e.g. "Launched", "Phase 3").

For **launched/approved drugs**: fetches approvals, top FAERS adverse reactions, drug labels (boxed warnings), recalls, and shortages. Writes `fda_approvals.json`, `fda_summary.md`, `fda_adverse_reactions.json`, `fda_labels.json`, `fda_recalls.json`, `fda_shortages.json`, `fda_safety.md`.

For **pipeline drugs** (Phase 1/2/3, Preclinical): fetches approvals (verification cross-check) and adverse reactions only — skips labels/recalls/shortages which will be empty. Handles 404/no-results gracefully.

### Step 8d: EMA approval data (external)
```bash
python3 $RECIPES/enrich_ema.py $DIR "$DRUG_NAME_RESOLVED" --phase "$PHASE"
```
Fetches EU approval data from EMA public JSON API (no auth). Writes ema_approvals.json, ema_shortages.json, ema_referrals.json, ema_summary.md.

### Step 8e: Orange Book / Purple Book patent cliff (external)
```bash
python3 $RECIPES/enrich_fda_patent.py $DIR "$DRUG_NAME_RESOLVED"
```
Queries the local fda-mcp-server SQLite database (no network call). Writes `fda_patent.json`, `fda_patent_cliff.md`.
Covers: unique patents with expiry dates, exclusivity periods (NCE/NPP/ODE/PED), effective LOE date, AB-rated generics count.
Downloads FDA Orange Book ZIP directly from FDA (~1 MB, cached monthly at `~/.cortellis/cache/orange-book.zip`). No auth required. Skips gracefully if download fails.

### Step 8f: ChEMBL enrichment (external)
```bash
python3 $RECIPES/enrich_chembl.py $DIR "$DRUG_NAME_RESOLVED"
```
Fetches from public ChEMBL REST API (no auth). Writes `chembl.json`, `chembl_summary.md`.
Covers: ChEMBL ID, molecule type, mechanism of action + action type + target ChEMBL ID, ChEMBL indications with max phase, ADMET/drug-likeness (small molecules only).

### Step 8g: CPIC pharmacogenomics (external)
```bash
python3 $RECIPES/enrich_cpic.py $DIR "$DRUG_NAME_RESOLVED"
```
Fetches gene-drug pairs from CPIC PostgREST API (no auth). Only includes Level A/B evidence (clinically actionable).
Writes: `cpic.json`, `cpic_summary.md`. Skips gracefully if drug has no CPIC data (expected for most biologics).

### Step 8h: bioRxiv/medRxiv preprints (external)
```bash
python3 $RECIPES/enrich_biorxiv.py $DIR "$DRUG_NAME_RESOLVED"
```
Searches bioRxiv and medRxiv via EuropePMC for preprints in the last 2 years (no auth required).
Writes: `biorxiv.json`, `biorxiv_summary.md`. Especially useful for pipeline drugs with limited peer-reviewed literature.

### Step 9: Drug Design (SI) enrichment (for early-stage drugs)
If the drug is Phase 1 or Preclinical:
```bash
cortellis --json drug-design search-drugs --query "$DRUG_SLUG" --hits 1
cortellis --json drug-design pharmacology --query "$DRUG_SLUG" --hits 5
```
Adds: research codes, pharmacology records, biologic flag, SI phase.

### Generate report
```bash
python3 $RECIPES/drug_report_generator.py $DIR
```

### Step 11: Compile to wiki <!-- model: opus -->
```bash
uv run --with pyyaml python3 $RECIPES/compile_drug.py $DIR "$DRUG_NAME_RESOLVED" [--wiki-dir /path/to/wiki-root]
```
Reads all JSON files from `$DIR` and writes `wiki/drugs/<slug>.md` plus updates `wiki/INDEX.md`.

### Post-Run Review (run after report is delivered)
```bash
python3 $RECIPES/../post_run_reviewer.py drug-profile $DIR "$DRUG_NAME_RESOLVED"
```
Read the manifest output above. If you see a clear pattern worth encoding (e.g. an
optional section that returned empty for this drug class), update the
`## Learned Optimizations` section below with a targeted patch. Only add an
optimization if it would generalize to future runs of similar inputs — not for
one-off anomalies. If unsure, skip.

## Learned Optimizations
<!-- Auto-updated by post-run review. Confirmed across real runs: metformin, semaglutide, tirzepatide, cagrilintide, amycretin. -->

- **`cpic.json` sparse for most drugs** — only ~5% of drugs have CPIC pharmacogenomics data (metformin, warfarin, clopidogrel class). Skip Step 8h for biologics and peptides; only run for small molecules with known CYP/transporter interactions.
- **`literature.json` consistently blank** — the Cortellis literature search endpoint returns empty for all 5 tested drugs despite real literature existing. Use `ct_trials.json` and `biorxiv.json` as primary publication evidence instead.
- **`chembl.json` sparse for peptides/biologics** — returns empty for tirzepatide, amycretin, cagrilintide. Populated for small molecules (metformin) and some approved peptides (semaglutide). Worth running for small molecules; low yield for large molecules.
- **`ema_referrals.json` + `ema_shortages.json` + `fda_shortages.json` blank for most drugs** — regulatory edge cases with very low base rate. Fetch but expect empty; do not flag as errors.
- **`literature_summary.csv` + `recent_publications.md` sparse when `literature.json` is blank** — these are derived output files; 55B/121B is expected when the literature endpoint returns no results. Not a data gap.
- **`cpic_summary.md` sparse (90B) when `cpic.json` is sparse** — derived summary; 90B is expected when CPIC returns minimal data. Not a gap.
- **`financials.json` + `swot.json` sparse (33B/28B) for pipeline/generic drugs** — empty structure returned for drugs without financial reporting or SWOT data. Expected for: Phase 1/2/preclinical drugs, generic/OTC drugs (e.g. orlistat) where Cortellis financial data covers innovator drugs only, and China-only approved drugs. Skip these sections in the report.
- **`fda_approvals.json` + `ema_approvals.json` empty for non-launched drugs** — approval data only exists post-approval. Expected for pipeline drugs; do not flag as errors.
- **`fda_patent_cliff.md` + `fda_safety.md` + `fda_summary.md` sparse for pipeline drugs** — minimal FDA data for non-approved drugs; 106–139B is expected header-only output.
- **`biorxiv.json` + `ct_trials.json` + `deals.json` sparse for very early-stage drugs** — 43B/69B/142B expected for Phase 1/preclinical drugs with limited public activity (amycretin class). Not a data gap.
- **All FDA/EMA enrichment files empty for non-US/EU-approved drugs** — `fda_approvals.json`, `fda_labels.json`, `fda_recalls.json`, `fda_shortages.json`, `fda_adverse_reactions.json`, `fda_summary.md`, `ema_approvals.json`, `ema_referrals.json`, `ema_shortages.json` all return empty for drugs without US/EU regulatory approval (pipeline drugs, China-only approvals like mazdutide). Expected; do not flag these as gaps.
- **`regulatory_milestones.csv` sparse (75B) for pipeline/early-stage drugs** — header-only output for drugs with no regulatory submissions yet. Expected for Phase 1/preclinical; do not flag as a gap.
- **`biorxiv_summary.md` sparse (73B) when `biorxiv.json` is sparse** — derived output; expected when bioRxiv search returns minimal preprints. Same pattern as `literature_summary.csv`.
- **FDA enrichment returns empty for combination drugs stored as INN names** — `naltrexone-bupropion`, `phentermine-topiramate` and similar combo INNs fail FDA API matching because the FDA uses brand names (Contrave, Qsymia). `fda_approvals.json`, `fda_labels.json`, `fda_recalls.json` all empty. Use brand name in `enrich_fda_approval.py` call if available.
- **`fda_summary.md` sparse (147–198B) for some launched drugs** — even approved drugs can produce minimal fda_summary when FDA records are limited (older approvals). Not a gap; supplement with `fda_approvals.json` directly.

## Execution Rules

- Once the final report has been delivered to the user, **do not respond to background task completion notifications**. Discard them silently — they are late arrivals for steps already processed.

## Output Rules

- **Skip empty sections.** If SWOT, financials, or regulatory return empty, do NOT show that section.
- Only report data from Cortellis results. No training data.
- Give exact numbers. No approximations.
- ALWAYS list ALL items in tables. No truncation.

## Output Format

```
# Drug Profile: <Drug Name>

**ID:** X | **Phase:** X | **Originator:** X
**Brands:** X, Y

## Overview
| Field | Value |
|-------|-------|
| Indications | X; Y; Z |
| Mechanism | X |
| Technology | X |
| Therapy Areas | X; Y |

## Development Timeline
(ASCII timeline from history — key milestones with dates)

## SWOT Analysis (if available)
### Strengths / Weaknesses / Opportunities / Threats

## Financial Data (if available)
Sales and forecast commentary.

## Deals
| Deal | Partner | Type | Date |
|------|---------|------|------|

## Clinical Trials
| Trial | Phase | Status | Enrollment |
|-------|-------|--------|------------|

## Regulatory (if available)
| Document | Region | Type | Date |
|----------|--------|------|------|
```

## Recipes

### Step 1 → Resolve drug name to ID
```bash
python3 $RECIPES/resolve_drug.py "<DRUG_NAME>"
# Output: drug_id,drug_name,phase,indication_count,inn_slug
# inn_slug is always the normalized INN (e.g. "ozempic" → "semaglutide")
# Prefers: non-combo drugs, highest phase, most indications
# Tested: tirzepatide, semaglutide, amycretin, setmelanotide, durvalumab, orlistat
```

### fetch_trials.sh — Paginated active trial fetch
```bash
bash $RECIPES/fetch_trials.sh "<DRUG_NAME>" $DIR/trials.json
# Fetches Recruiting + Active-not-recruiting trials with pagination
# Deduplicates by trial ID across status passes
# Output: trials.json with trialResultsOutput structure
```

### Steps 2-9 → Collect data, then generate report
```bash
python3 $RECIPES/drug_report_generator.py $DIR
# Reads: record.json, swot.json, financials.json, history.json,
#         deals.json, trials.json, regulatory.json
# Outputs: formatted markdown with ASCII timeline, tables, charts
# Skips empty sections automatically
```
