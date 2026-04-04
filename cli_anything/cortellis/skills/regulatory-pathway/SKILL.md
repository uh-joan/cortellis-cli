---
name: regulatory-pathway
description: /regulatory-pathway: Regulatory Intelligence Report
---

# /regulatory-pathway — Regulatory Intelligence Report

Deep regulatory analysis for a drug: approval timelines, regulatory documents, citation graph, and cross-region status.

## Usage

```
/regulatory-pathway semaglutide
/regulatory-pathway tirzepatide
/regulatory-pathway "pembrolizumab"
```

## Workflow

### Setup
```bash
RECIPES="cli_anything/cortellis/skills/regulatory-pathway/recipes"
DRUG_RECIPES="cli_anything/cortellis/skills/drug-profile/recipes"
DIR="/tmp/regulatory_pathway"
mkdir -p "$DIR"
```

### Step 1: Resolve drug name (if needed)
```bash
RESULT=$(python3 $DRUG_RECIPES/resolve_drug.py "<DRUG_NAME>")
# Output: drug_id,drug_name,phase,indication_count
```

### Step 2: Search regulatory documents for the drug
```bash
cortellis --json regulations search --query "<DRUG_NAME>" --hits 20 > $DIR/reg_search.json
```

### Step 3: Get full record for top regulatory documents
For the top 3-5 most important documents (Original Approvals, key supplementals):
```bash
cortellis --json regulations get <REG_NUMBER> --category metadata > $DIR/reg_record_1.json
```

### Step 4: Citation graph for key approval documents
For each key approval document:
```bash
cortellis --json regulations cited-documents <REG_NUMBER> > $DIR/cited_1.json
cortellis --json regulations cited-by <REG_NUMBER> > $DIR/cited_by_1.json
```

### Step 5: Drug record for regulatory context
```bash
cortellis --json drugs get <DRUG_ID> --category report > $DIR/drug_record.json
```

### Generate report
```bash
python3 $RECIPES/regulatory_report_generator.py $DIR "<DRUG_NAME>"
```

## Output Rules

- Skip empty sections automatically.
- Only report data from Cortellis results. No training data.
- Give exact numbers. No approximations.
- ALWAYS list ALL items in tables. No truncation.
- Clean HTML tags from abstracts before displaying.

## Output Format

```
# Regulatory Pathway: <Drug Name>

**Total Documents:** X | **Regions:** X

## Approval Timeline
| Date | Document | Region | Type | Status |
|------|----------|--------|------|--------|

## Key Approvals
### <Document Title>
**Region:** X | **Date:** X | **Type:** X
Abstract summary...

## Regulatory Documents by Region
| Region | Count | Latest |
|--------|-------|--------|

## Citation Graph (for key approval)
### Documents Cited By This Approval
| Document | Date | Region |
### Documents That Cite This Approval
| Document | Date | Region |

## All Regulatory Documents
| # | Title | Region | Type | Date | Status |
```

## Recipes

### Step 1 -> Resolve drug name (reuses drug-profile resolver)
```bash
python3 $DRUG_RECIPES/resolve_drug.py "<DRUG_NAME>"
```

### Steps 2-5 -> Collect data, then generate report
```bash
python3 $RECIPES/regulatory_report_generator.py $DIR "<DRUG_NAME>"
# Reads: reg_search.json, reg_record_*.json, cited_*.json, cited_by_*.json, drug_record.json
# Outputs: formatted markdown with approval timeline, citation graph
# Skips empty sections automatically
```
