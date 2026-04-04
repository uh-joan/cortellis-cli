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
DIR="/tmp/drug_profile"
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

### Step 3: SWOT data collection
Fetch inputs for the AI-generated strategic SWOT (editorial SWOT used as reference only):
```bash
cortellis --json drugs swots <DRUG_ID> > $DIR/swot.json
cortellis --json company-analytics query-drugs drugPatentProductExpiry --id-list <DRUG_ID> > $DIR/patent_expiry.json
cortellis --json drugs search --drug-name "<DRUG_NAME> biosimilar" --hits 10 > $DIR/biosimilars.json
cortellis --json drugs search --action "<PRIMARY_ACTION>" --phase C3 --hits 15 > $DIR/competitors_p3.json
```
The SWOT section is synthesized from ALL collected data (record, financials, trials, deals, patents, competitors) — not just the editorial SWOT.

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
cortellis --json deals search --drug "<DRUG_NAME>" --hits 50 --sort-by "-dealDateStart" > $DIR/deals.json
```

### Step 7: Active trials
```bash
cortellis --json trials search --query "trialInterventionsPrimaryAloneNameDisplay:<DRUG_NAME>" --hits 50 --sort-by "-trialDateStart" > $DIR/trials.json
```

### Step 8: Regulatory status
```bash
cortellis --json regulations search --query "<DRUG_NAME>" --hits 30 --sort-by "-regulatoryDateSort" > $DIR/regulatory.json
```

### Step 9: Competitive landscape (drugs with same primary mechanism)
Extract the primary action from the drug record, then search for other drugs with the same mechanism:
```bash
cortellis --json drugs search --action "<PRIMARY_ACTION>" --phase L --hits 15 > $DIR/competitors.json
```

### Step 10: Drug Design (SI) enrichment
For any drug, optionally enrich with pharmacology data:
```bash
cortellis --json drug-design search-drugs --query "<DRUG_NAME>" --hits 1 > $DIR/si_drug.json
cortellis --json drug-design pharmacology --query "<DRUG_NAME>" --hits 10 > $DIR/pharmacology.json
```
Adds: research codes, pharmacology records (targets, assays, PK data), biologic flag, SI phase.

### Generate report
```bash
python3 $RECIPES/drug_report_generator.py $DIR
```

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

## Strategic SWOT Analysis
(AI-generated from live data: financials, trials, deals, patents, competitors)

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
#         deals.json, trials.json, regulatory.json, competitors.json,
#         patent_expiry.json, biosimilars.json, competitors_p3.json
# SWOT section: calls drug-swot/recipes/swot_data_collector.py to
# synthesize a strategic SWOT from ALL collected data
# Skips empty sections automatically
```
