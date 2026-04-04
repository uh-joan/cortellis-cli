---
name: deal-deep-dive
description: /deal-deep-dive: Expanded Deal Analysis
---

# /deal-deep-dive — Expanded Deal Analysis

Deep analysis of pharma deals: expanded financials, territories, milestones, comparable deals, and linked drug/trial context.

## Usage

```
/deal-deep-dive 479661
/deal-deep-dive "semaglutide"
/deal-deep-dive "Novo Nordisk" --recent
```

## Workflow

### Setup
```bash
RECIPES="cli_anything/cortellis/skills/deal-deep-dive/recipes"
DIR="/tmp/deal_deep_dive"
mkdir -p "$DIR"
```

### Step 1: Resolve deal(s)

**If deal ID given:** Skip to Step 2.

**If drug name given:**
```bash
cortellis --json deals search --drug "<DRUG_NAME>" --hits 10 --sort-by "-dealDateStart" > $DIR/search_results.json
```

**If company name given:**
```bash
cortellis --json deals search --principal "<COMPANY_NAME>" --hits 10 --sort-by "-dealDateStart" > $DIR/search_results.json
```

Present the top deals to the user and let them pick, or analyze the top 5 if `--recent` flag is used.

### Step 2: Fetch expanded deal record
```bash
cortellis --json deals-intelligence get <DEAL_ID> > $DIR/deal_expanded.json
```

### Step 3: Fetch standard deal record (for additional fields)
```bash
cortellis --json deals get <DEAL_ID> --category expanded > $DIR/deal_standard.json
```

### Step 4: Fetch deal sources
```bash
cortellis --json deals sources <DEAL_ID> > $DIR/deal_sources.json
```

### Step 5: Find comparable deals (same indication + deal type)
Extract the primary indication and deal type from the expanded record, then search:
```bash
cortellis --json deals-intelligence search --query "<INDICATION> <DEAL_TYPE>" --hits 50 --sort-by "-dealDateStart" > $DIR/comparables.json
```

### Step 6: Drug context (if deal involves a specific drug)
```bash
cortellis --json drugs search --drug-name "<DRUG_NAME>" --hits 1 > $DIR/drug_context.json
```

### Generate report
```bash
python3 $RECIPES/deal_report_generator.py $DIR
```

## Output Rules

- Skip empty sections automatically.
- Only report data from Cortellis results. No training data.
- Give exact numbers. No approximations.
- ALWAYS list ALL items in tables. No truncation.
- Show financial values as reported (do not convert currencies).

## Output Format

```
# Deal Deep Dive: <Deal Title>

**ID:** X | **Status:** Active | **Date:** YYYY-MM-DD

## Parties
| Role | Company | Type |
|------|---------|------|
| Principal | X | Pharma |
| Partner | Y | Biotech |

## Deal Structure
| Field | Value |
|-------|-------|
| Agreement Type | X |
| Transaction Type | X |
| Asset Type | X |
| Phase at Signing | X |
| Current Phase | X |

## Territories
**Included:** X, Y, Z
**Excluded:** A, B

## Financial Terms
| Component | Value | Status |
|-----------|-------|--------|
| Total Projected (Signing) | $X | Disclosed |
| Total Projected (Current) | $X | Disclosed |
| Upfront Payment | $X | Disclosed |
| Milestones | $X | Disclosed |
| Royalties | X% | Disclosed |

## Indications & Mechanisms
| Indication | Primary |
|------------|---------|
| X | Yes |
| Y | No |

## Drugs Involved
| Drug | Phase |
|------|-------|

## Comparable Deals
| Deal | Type | Principal | Partner | Value | Date |
|------|------|-----------|---------|-------|------|

## Sources
| Source | Date |
|--------|------|
```

## Recipes

### Step 2-6 -> Collect data, then generate report
```bash
python3 $RECIPES/deal_report_generator.py $DIR
# Reads: deal_expanded.json, deal_standard.json, deal_sources.json,
#         comparables.json, drug_context.json
# Outputs: formatted markdown with financial tables, territory mapping
# Skips empty sections automatically
```
