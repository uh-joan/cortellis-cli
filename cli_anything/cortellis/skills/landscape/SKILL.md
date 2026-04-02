---
name: landscape
description: /landscape: Competitive Landscape Report
---

# /landscape — Competitive Landscape Report

Generate a full competitive landscape for a therapeutic indication.

## Usage

```
/landscape obesity
/landscape "non-small cell lung cancer"
/landscape MASH
/landscape diabetes
```

## Workflow

### Setup
```bash
RECIPES="cli_anything/cortellis/skills/landscape/recipes"
PIPELINE_RECIPES="cli_anything/cortellis/skills/pipeline/recipes"
DIR="/tmp/landscape"
mkdir -p "$DIR"
HEADER="name,id,phase,indication,mechanism,company,source"
```

### Step 1: Resolve indication ID
```bash
RESULT=$(python3 $RECIPES/resolve_indication.py "<INDICATION>")
# Output: indication_id,indication_name
# Uses NER first (exact match), then ontology search fallback
# Tested: obesity, NSCLC, MASH, diabetes, Alzheimer — all correct
```

### Step 2: Drugs by phase (with pagination for large indications)
```bash
# For small indications (<50 drugs per phase):
echo "$HEADER" > $DIR/launched.csv
cortellis --json drugs search --indication <ID> --phase L --hits 50 | python3 $PIPELINE_RECIPES/ci_drugs_to_csv.py >> $DIR/launched.csv
# Repeat for C3, C2, C1, DR

# For large indications (obesity, NSCLC — hit 50 cap):
bash $RECIPES/fetch_indication_phase.sh <ID> L $DIR/launched.csv $PIPELINE_RECIPES
bash $RECIPES/fetch_indication_phase.sh <ID> C3 $DIR/phase3.csv $PIPELINE_RECIPES
bash $RECIPES/fetch_indication_phase.sh <ID> C2 $DIR/phase2.csv $PIPELINE_RECIPES
bash $RECIPES/fetch_indication_phase.sh <ID> C1 $DIR/phase1.csv $PIPELINE_RECIPES
bash $RECIPES/fetch_indication_phase.sh <ID> DR $DIR/discovery.csv $PIPELINE_RECIPES
```

### Step 3: Key companies (deduplicated)
```bash
python3 $RECIPES/company_landscape.py $DIR > $DIR/companies.csv
```
Outputs deduplicated company counts with phase breakdown.

### Step 4: Recent deals
```bash
cortellis --json deals search --indication "<INDICATION>" --hits 20 --sort-by "-dealDateStart" | python3 $PIPELINE_RECIPES/deals_to_csv.py > $DIR/deals.csv
```

### Step 5: Recruiting trials
```bash
cortellis --json trials search --indication <ID> --recruitment-status Recruiting --hits 50 --sort-by "-trialDateStart" | python3 $PIPELINE_RECIPES/trials_to_csv.py > $DIR/trials.csv
```

### Step 6: Generate report
```bash
python3 $RECIPES/landscape_report_generator.py $DIR "<INDICATION_NAME>" "<INDICATION_ID>"
```

## Output Rules

- ALWAYS list ALL drugs in tables. NEVER truncate with "+ N others".
- Give exact counts from API @totalResults.
- Show warning when a phase hits the 50-drug cap.
- Do not add drugs from training data.

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
```

## Recipes

### Step 1 → Resolve indication
```bash
python3 $RECIPES/resolve_indication.py "<INDICATION>"
# NER-first, ontology fallback. Tested on 5 diverse indications.
```

### Step 2 → Paginated drug fetch (for large indications)
```bash
bash $RECIPES/fetch_indication_phase.sh <IND_ID> <PHASE> <OUTPUT_CSV> $PIPELINE_RECIPES
# Auto-paginates up to 200 drugs per phase. Rate limit protection.
```

### Step 3 → Deduplicated company analysis
```bash
python3 $RECIPES/company_landscape.py $DIR > $DIR/companies.csv
# Counts unique drugs per company, not drug-phase entries.
```

### Step 6 → Report with ASCII charts
```bash
python3 $RECIPES/landscape_report_generator.py $DIR "<NAME>" "<ID>"
# Pipeline chart, mechanism density chart, top companies chart
# Drug tables per phase, company ranking, deals, trials summary
```

NOTE: This skill reuses pipeline recipes for CSV conversion:
- `$PIPELINE_RECIPES/ci_drugs_to_csv.py`
- `$PIPELINE_RECIPES/deals_to_csv.py`
- `$PIPELINE_RECIPES/trials_to_csv.py`
- `$PIPELINE_RECIPES/count_by_field.py`
