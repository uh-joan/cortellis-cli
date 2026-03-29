# /patent-cliff — Patent Expiry Analysis

Identify drugs facing patent cliffs and potential generic competition.

## Usage

```
/patent-cliff "Novo Nordisk"
/patent-cliff obesity
/patent-cliff --year 2027
```

## Workflow

### Step 1: Find drugs to analyze

By company:
```bash
cortellis --json drugs search --company <COMPANY_ID> --phase L --hits 50
```

By indication:
```bash
cortellis --json ontology search --term "<INDICATION>" --category indication
cortellis --json drugs search --phase L --indication <ID> --hits 50
```

### Step 2: Get patent data for each launched drug
For each drug ID from Step 1:
```bash
cortellis --json company-analytics query-drugs drugPatentProductExpiry --id-list "<ID1>,<ID2>,<ID3>..."
```

### Step 3: Get financial data
```bash
cortellis --json company-analytics query-drugs drugSalesActualAndForecast --id-list "<ID1>,<ID2>,<ID3>..."
```

### Step 4: Check for generic competition
For drugs with expiring patents:
```bash
cortellis --json drugs search --drug-name "<DRUG> biosimilar" --hits 10
```

## Output Format

```
# Patent Cliff Analysis: <Company/Indication>

## Overview
- Launched drugs analyzed: X
- Drugs with patent data: X
- Expiring within 2 years: X

## Patent Expiry Timeline
| Drug | Earliest Expiry | Latest Expiry | Revenue (est.) |
|------|----------------|---------------|----------------|

## At Risk (expiring within 2 years)
For each at-risk drug:
- **Drug:** X | **Expiry:** X
- **Revenue:** X
- **Biosimilar/generic competition:** X entries found

## Financial Impact
| Year | Drugs Losing Exclusivity | Est. Revenue at Risk |
|------|------------------------|---------------------|

## Biosimilar Pipeline
| Drug | Biosimilar | Company | Phase |
|------|-----------|---------|-------|
```

## Rules
- Patent data may not be available for all drugs (subscription dependent).
- If company-analytics returns 500/401, note the limitation and skip that step.
- Only report data from Cortellis results.
- Financial figures are from Cortellis forecasts, clearly label as estimates.
