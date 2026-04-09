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
DRUG_SLUG=$(echo "<DRUG_NAME>" | tr '[:upper:]' '[:lower:]' | tr ' ' '-' | sed "s/'//g")
DIR="raw/drugs/$DRUG_SLUG"
mkdir -p "$DIR"
```

### Step 1: Resolve drug ID
```bash
RESULT=$(python3 $RECIPES/resolve_drug.py "<DRUG_NAME>")
# Output: drug_id,drug_name,phase,indication_count
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
cortellis --json deals search --drug "<DRUG_NAME>" --hits 10 --sort-by "-dealDateStart" > $DIR/deals.json
```

### Step 7: Active trials
```bash
cortellis --json trials search --query "trialInterventionsPrimaryAloneNameDisplay:<DRUG_NAME>" --hits 10 --sort-by "-trialDateStart" > $DIR/trials.json
```

### Step 8: Regulatory status
```bash
cortellis --json regulations search --query "<DRUG_NAME>" --hits 10 --sort-by "-regulatoryDateSort" > $DIR/regulatory.json
```

### Step 9: Competitive landscape (drugs with same primary mechanism)
Extract the primary action from the drug record, then search for other drugs with the same mechanism:
```bash
cortellis --json drugs search --action "<PRIMARY_ACTION>" --phase L --hits 15 > $DIR/competitors.json
```

### Step 10: Drug Design (SI) enrichment (for early-stage drugs)
If the drug is Phase 1 or Preclinical:
```bash
cortellis --json drug-design search-drugs --query "<DRUG_NAME>" --hits 1
cortellis --json drug-design pharmacology --query "<DRUG_NAME>" --hits 5
```
Adds: research codes, pharmacology records, biologic flag, SI phase.

### Generate report
```bash
python3 $RECIPES/drug_report_generator.py $DIR
```

### Step 11: Compile to wiki
```bash
python3 $RECIPES/compile_drug.py $DIR "<DRUG_NAME>" [--wiki-dir /path/to/wiki-root]
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

## Competitive Landscape (same mechanism)
| Drug | Company | Phase | Indications |
|------|---------|-------|-------------|

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
# Output: drug_id,drug_name,phase,indication_count
# Prefers: non-combo drugs, highest phase, most indications
# Tested: tirzepatide, semaglutide, amycretin, setmelanotide, durvalumab, orlistat
```

### Steps 2-10 → Collect data, then generate report
```bash
python3 $RECIPES/drug_report_generator.py $DIR
# Reads: record.json, swot.json, financials.json, history.json,
#         deals.json, trials.json, regulatory.json, competitors.json
# Outputs: formatted markdown with ASCII timeline, tables, charts
# Skips empty sections automatically
```
