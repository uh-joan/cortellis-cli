---
name: target-profile
description: /target-profile: Deep Biological Target Profile
---

# /target-profile — Deep Biological Target Profile

Everything about a biological target as a drug target: biology, disease associations, genetic evidence, drug pipeline, protein interactions, and pharmacology data.

## Usage

```
/target-profile GLP-1
/target-profile EGFR
/target-profile PD-L1
/target-profile "BTK"
/target-profile "KRAS"
```

## Workflow

### Setup
```bash
RECIPES="cli_anything/cortellis/skills/target-profile/recipes"
DIR="/tmp/target_profile"
mkdir -p "$DIR"
```

### Step 1: Resolve target ID and action name
```bash
RESULT=$(python3 $RECIPES/resolve_target_id.py "<TARGET>")
TARGET_ID=$(echo "$RESULT" | cut -d',' -f1)
TARGET_NAME=$(echo "$RESULT" | cut -d',' -f2)
GENE_SYMBOL=$(echo "$RESULT" | cut -d',' -f3)
ACTION_NAME=$(echo "$RESULT" | cut -d',' -f4)
RESOLUTION_METHOD=$(echo "$RESULT" | cut -d',' -f5)
# Output: target_id,target_name,gene_symbol,action_name,resolution_method
```

### Steps 2-8: Fetch all data (parallel)
These API calls are independent — run them concurrently to reduce wall time from ~20s to ~3-5s.
```bash
# Step 2: Full target record
cortellis --json targets records $TARGET_ID > $DIR/record.json &

# Step 3: Disease-drug associations
cortellis --json targets condition-drugs $TARGET_ID > $DIR/condition_drugs.json &

# Step 4: Disease-gene associations
cortellis --json targets condition-genes $TARGET_ID > $DIR/condition_genes.json &

# Step 5: Protein-protein interactions
cortellis --json targets interactions $TARGET_ID > $DIR/interactions.json &

# Step 6: Drug pipeline by mechanism (CI domain)
# Paginate drug pipeline (50 per page, up to 10 pages = 500 drugs)
# If ACTION_NAME is empty, skip this step.
(python3 -c "
import json, subprocess, time, sys
all_drugs = []
offset, total = 0, None
while (total is None or offset < total) and offset < 500:
    r = subprocess.run(['cortellis', '--json', 'drugs', 'search', '--action', '$ACTION_NAME', '--hits', '50', '--offset', str(offset)], capture_output=True, text=True)
    try:
        d = json.loads(r.stdout)
        total = int(d.get('drugResultsOutput', {}).get('@totalResults', '0'))
        drugs = d.get('drugResultsOutput', {}).get('SearchResults', {}).get('Drug', [])
        if isinstance(drugs, dict): drugs = [drugs]
        all_drugs.extend(drugs)
    except: break
    offset += 50
    if offset < total: time.sleep(3)
result = {'drugResultsOutput': {'@totalResults': str(total or 0), 'SearchResults': {'Drug': all_drugs}}}
json.dump(result, open('$DIR/drugs_pipeline.json', 'w'))
") &

# Step 7: Pharmacology data (Drug Design / SI)
# Note: Use plain gene symbol as query, NOT targetSynonyms: prefix (not supported by pharmacology endpoint).
cortellis --json drug-design pharmacology --query "$GENE_SYMBOL" --hits 20 > $DIR/pharmacology.json &

# Step 8: Disease briefings (optional, may return 400 for some targets)
(cortellis --json drug-design disease-briefings-search --query "$TARGET_NAME" --hits 3 > $DIR/briefings.json 2>/dev/null || echo '{}' > $DIR/briefings.json) &

wait  # All parallel fetches complete before report generation
```

### Step 9: Generate report
```bash
python3 $RECIPES/target_report_generator.py $DIR "$RESOLUTION_METHOD"
```

## Output Rules

- Skip empty sections automatically.
- Only report data from Cortellis results. No training data.
- Give exact numbers. No approximations.
- Show "Showing X of Y" when results are truncated.
- Drug pipeline is paginated (up to 500 results).

## Output Format

```
# Target Profile: <Target Name> (<Gene Symbol>)

**ID:** X | **Organism:** Human | **Family:** X
**Synonyms:** X, Y, Z

## Biology
| Field | Value |
|-------|-------|
| Function | ... |
| Subcellular Location | ... |
| Protein Family | ... |

## Disease Associations (X diseases)
| Disease | Drugs | Top Drug (Phase) |
|---------|-------|-------------------|

## Genetic Evidence (X associations)
| Disease | Gene | Evidence |
|---------|------|----------|

## Drug Pipeline (X total)
(ASCII bar chart by phase)

| Drug | Company | Phase | Indications |
|------|---------|-------|-------------|

## Protein Interactions (X)
| Partner | Interaction Type |
|---------|-----------------|

## Pharmacology (X records)
| Compound | Assay | Value | Unit |
|----------|-------|-------|------|

## Disease Briefings (if available)
```

## Recipes

### resolve_target_id.py — Target name to ID + action name
```bash
python3 $RECIPES/resolve_target_id.py "<TARGET>"
# Output: target_id,target_name,gene_symbol,action_name,resolution_method
# 3-strategy resolution: NER → direct search → normalized retry
# Handles: GLP-1, GLP1R, EGFR, PD-L1, HER2, BRAF, BTK, JAK, KRAS, etc.
```

### target_report_generator.py — Formatted report from JSON files
```bash
python3 $RECIPES/target_report_generator.py $DIR
# Reads: record.json, condition_drugs.json, condition_genes.json,
#         interactions.json, drugs_pipeline.json, pharmacology.json, briefings.json
# Outputs: formatted markdown with ASCII pipeline chart, tables
# Skips empty sections automatically
```
