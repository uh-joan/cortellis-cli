# /deal-scout — Deal Scouting Report

Find and analyze recent deals in a therapeutic area or for a company.

## Usage

```
/deal-scout oncology
/deal-scout "GLP-1" --type License
/deal-scout --company "Pfizer" --year 2024
```

## Workflow

### Step 1: Search deals
Based on what the user specified:

By indication/topic:
```bash
cortellis --json deals search --indication "<TOPIC>" --hits 30
```

By company:
```bash
cortellis --json deals search --principal "<COMPANY>" --hits 30
```

By deal type:
```bash
cortellis --json deals search --deal-type "<TYPE>" --indication "<TOPIC>" --hits 30
```

### Step 2: Get expanded details for top deals
For the most interesting deals (largest value, most recent):
```bash
cortellis --json deals-intelligence get <DEAL_ID>
```

### Step 3: Identify patterns
From the results, extract:
- Most active companies (principal + partner)
- Common deal types
- Value ranges
- Therapeutic focus

## Output Format

```
# Deal Scout: <Topic/Company>

## Overview
- Total deals found: X
- Date range: earliest — most recent
- Most common type: X

## Top Deals
| Deal | Principal | Partner | Type | Date | Value |
|------|-----------|---------|------|------|-------|

## Most Active Companies
| Company | As Principal | As Partner | Total |
|---------|-------------|-----------|-------|

## Deal Type Breakdown
| Type | Count |
|------|-------|

## Notable Deals (expanded details)
For each top deal, provide: title, summary, territories, financial terms.
```

## Rules
- Only report data from Cortellis results.
- If user asks about a year, use date filters.
- Give exact counts and values from the data.
