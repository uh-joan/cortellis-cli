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

### Setup
```bash
RECIPES="cli_anything/cortellis/skills/drug-profile/recipes"
```

### Step 1: Resolve drug ID and INN slug
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
python3 $RECIPES/enrich_fda_approval.py $DIR "$DRUG_NAME_RESOLVED"
```
Fetches FDA drugsfda approvals from api.fda.gov (no auth required). Writes `fda_approvals.json` (raw) and `fda_summary.md` (table). Handles 404/no-results gracefully.

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

### Step 11: Compile to wiki
```bash
python3 $RECIPES/compile_drug.py $DIR "$DRUG_NAME_RESOLVED" [--wiki-dir /path/to/wiki-root]
```
Reads all JSON files from `$DIR` and writes `wiki/drugs/<slug>.md` plus updates `wiki/INDEX.md`.

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
