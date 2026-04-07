---
name: drug-comparison
description: /drug-comparison: Side-by-Side Drug Comparison
---

# /drug-comparison — Side-by-Side Drug Comparison

Compare 2–5 drugs across development phase, mechanism, indications, trials, and deals.

## Usage

```
/drug-comparison tirzepatide vs semaglutide
/drug-comparison ozempic versus wegovy versus mounjaro
/drug-comparison tirzepatide, semaglutide, amycretin
compare drugs tirzepatide vs semaglutide
head to head tirzepatide semaglutide
```

## Workflow

### Setup
```bash
RECIPES="cli_anything/cortellis/skills/drug-comparison/recipes"
PROFILE_RECIPES="cli_anything/cortellis/skills/drug-profile/recipes"
DIR="/tmp/drug_comparison"
mkdir -p "$DIR"
```

### Step 1: Parse drug names from user query
Split input on "vs", "versus", commas, and "head to head" delimiters.
Accept 2–5 drug names. Trim whitespace. Example: "tirzepatide vs semaglutide" → ["tirzepatide", "semaglutide"].

### Step 2: Resolve drug IDs
For each drug name (use index N starting at 1):
```bash
RESULT=$(python3 $PROFILE_RECIPES/resolve_drug.py "<DRUG_NAME_N>")
# Output: drug_id,drug_name,phase,indication_count
DRUG_ID_N=$(echo "$RESULT" | cut -d',' -f1)
DRUG_CANONICAL_N=$(echo "$RESULT" | cut -d',' -f2)
```
If user provides a numeric ID, skip resolve for that drug.

### Step 3: Fetch drug records
For each resolved drug (N = 1, 2, …):
```bash
cortellis --json drugs get $DRUG_ID_N --category report --include-sources > $DIR/drug_N.json
```

### Step 4: Fetch trial data
For each drug canonical name:
```bash
cortellis --json trials search --query "trialInterventionsPrimaryAloneNameDisplay:<DRUG_CANONICAL_N>" --hits 10 --sort-by "-trialDateStart" > $DIR/trials_N.json
```

### Step 5: Fetch deal data
For each drug canonical name:
```bash
cortellis --json deals search --drug "<DRUG_CANONICAL_N>" --hits 10 --sort-by "-dealDateStart" > $DIR/deals_N.json
```

### Step 6: Generate comparison
```bash
python3 $RECIPES/drug_comparison_generator.py $DIR
```

## Output Rules

- Only report data from Cortellis results. No training data.
- Give exact numbers. No approximations.
- Skip a column's section gracefully if data is unavailable for that drug.
- Tables must include ALL drugs side by side — no truncation.

## Output Format

```
# Drug Comparison: Drug1 vs Drug2 [vs Drug3 …]

## Overview
| Attribute | Drug1 | Drug2 |
|---|---|---|
| Phase | Launched | Phase 3 |
| Mechanism | GLP-1 agonist | GIP/GLP-1 dual agonist |
| Indications | 4 | 2 |
| Company | Novo Nordisk | Eli Lilly |

## Clinical Trials
| Metric | Drug1 | Drug2 |
|---|---|---|
| Total Trials | 45 | 28 |
| Recruiting | 12 | 8 |
| Phase 3 | 6 | 4 |

## Deal Activity
| Metric | Drug1 | Drug2 |
|---|---|---|
| Total Deals | 14 | 8 |
| Latest Deal | 2024-03 | 2023-11 |
| Deal Types | Licensing; Co-dev | Licensing |

## Key Differentiators
- Drug1 is Launched while Drug2 is in Phase 3
- Drug1 targets 4 indications vs Drug2's 2
- Different mechanisms: GLP-1 agonist vs GIP/GLP-1 dual agonist
```

## Recipes

### Steps 2 → Resolve each drug name to ID
```bash
python3 $PROFILE_RECIPES/resolve_drug.py "<DRUG_NAME>"
# Output: drug_id,drug_name,phase,indication_count
# Reuses drug-profile resolver — same semantics and preferences
```

### Step 6 → Generate comparison markdown
```bash
python3 $RECIPES/drug_comparison_generator.py $DIR
# Reads: drug_N.json, trials_N.json, deals_N.json (N = 1..5)
# Discovers how many drugs are present automatically
# Outputs: formatted comparison markdown with tables and differentiators
```
