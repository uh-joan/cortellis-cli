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

### Step 1: Find the drug
If name given:
```bash
cortellis --json drugs search --drug-name "<NAME>" --hits 5
```
Pick the best match, extract the drug ID.

### Step 2: Full drug record
```bash
cortellis --json drugs get <DRUG_ID> --category report --include-sources
```

### Step 3: SWOT analysis
```bash
cortellis --json drugs swots <DRUG_ID>
```

### Step 4: Financial data
```bash
cortellis --json drugs financials <DRUG_ID>
```

### Step 5: Development history
```bash
cortellis --json drugs history <DRUG_ID>
```

### Step 6: Related deals
```bash
cortellis --json deals search --drug "<DRUG_NAME>" --hits 10
```

### Step 7: Active trials
```bash
cortellis --json trials search --query "trialInterventionsPrimaryAloneNameDisplay:<DRUG_NAME>" --hits 10
```

### Step 8: Regulatory status
```bash
cortellis --json regulations search --query "<DRUG_NAME>" --hits 10
```

## Output Format

```
# Drug Profile: <Drug Name>

## Overview
- ID: X | Phase: X | Originator: X
- Primary Indications: X, Y, Z
- Mechanism: X
- Technology: X

## Development Timeline
(from history data — key milestones with dates)

## SWOT Analysis
### Strengths
### Weaknesses
### Opportunities
### Threats

## Financial Data
(sales actuals + forecasts if available)

## Deals
| Deal | Partner | Type | Date |
|------|---------|------|------|

## Clinical Trials
| Trial | Phase | Indication | Status | Enrollment |
|-------|-------|-----------|--------|------------|

## Regulatory
| Document | Region | Type | Date |
|----------|--------|------|------|
```

## Rules
- Only report data from Cortellis. If a step returns empty, say "No data available" for that section.
- Some steps may fail (financials, SWOT) — that's OK, skip that section.
- Give exact data, no approximations.
