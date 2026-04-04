---
name: sales-forecast
description: /sales-forecast: Drug Sales & Forecast Analysis
---

# /sales-forecast — Drug Sales & Forecast Analysis

Drug sales actuals and forecast with competitive context.

## Usage

```
/sales-forecast semaglutide
/sales-forecast tirzepatide
/sales-forecast "pembrolizumab"
```

## Workflow

### Setup
```bash
RECIPES="cli_anything/cortellis/skills/sales-forecast/recipes"
DRUG_RECIPES="cli_anything/cortellis/skills/drug-profile/recipes"
DIR="/tmp/sales_forecast"
mkdir -p "$DIR"
```

### Step 1: Resolve drug ID
```bash
RESULT=$(python3 $DRUG_RECIPES/resolve_drug.py "<DRUG_NAME>")
# Output: drug_id,drug_name,phase,indication_count
```

### Step 2: Fetch financial data
```bash
cortellis --json drugs financials <DRUG_ID> > $DIR/financials.json
```

### Step 3: Fetch financial CSV data
```bash
cortellis --json drugs financials <DRUG_ID> --csv > $DIR/financials.csv
```

### Step 4: Fetch drug record for context
```bash
cortellis --json drugs get <DRUG_ID> --category report > $DIR/drug_record.json
```

### Step 5: Fetch competitors (same mechanism, launched)
```bash
cortellis --json drugs search --action "<PRIMARY_ACTION>" --phase L --hits 15 > $DIR/competitors.json
```

### Step 6: Fetch competitor financials (top 3 competitors)
```bash
cortellis --json drugs financials <COMPETITOR_ID_1> > $DIR/comp_fin_1.json
cortellis --json drugs financials <COMPETITOR_ID_2> > $DIR/comp_fin_2.json
cortellis --json drugs financials <COMPETITOR_ID_3> > $DIR/comp_fin_3.json
```

### Generate report
```bash
python3 $RECIPES/sales_report_generator.py $DIR "<DRUG_NAME>"
```

## Output Rules

- Skip empty sections automatically.
- Only report data from Cortellis results. No training data.
- Give exact numbers. No approximations.
- Show financial values as reported (do not convert currencies).

## Output Format

```
# Sales & Forecast: <Drug Name>

**ID:** X | **Phase:** Launched | **Originator:** X

## Sales Commentary
<cleaned commentary text>

## Competitive Sales Comparison
| Drug | Company | Sales Commentary |

## Competitive Landscape (same mechanism)
| Drug | Company | Phase | Indications |
```

## Recipes

### Step 1 -> Resolve drug name (reuses drug-profile resolver)
```bash
python3 $DRUG_RECIPES/resolve_drug.py "<DRUG_NAME>"
```

### Steps 2-6 -> Collect data, then generate report
```bash
python3 $RECIPES/sales_report_generator.py $DIR "<DRUG_NAME>"
```
