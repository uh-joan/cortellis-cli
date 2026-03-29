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
/landscape diabetes --phase C3
```

## Workflow

Execute these steps in order. Use `cortellis --json` for all commands.

### Step 1: Resolve indication ID
```bash
cortellis --json ontology search --term "<INDICATION>" --category indication
```
Extract the ID (e.g., 238 for Obesity). If multiple matches, pick the most specific.

### Step 2: Launched drugs
```bash
cortellis --json drugs search --phase L --indication <ID> --hits 50
```

### Step 3: Pipeline drugs (Phase 1-3)
```bash
cortellis --json drugs search --phase C3 --indication <ID> --hits 50
cortellis --json drugs search --phase C2 --indication <ID> --hits 50
cortellis --json drugs search --phase C1 --indication <ID> --hits 50
```

### Step 4: Key companies
Extract unique companies from Steps 2-3. For the top 5 by drug count, get profiles:
```bash
cortellis --json companies get <COMPANY_ID>
```

### Step 5: Recent deals
```bash
cortellis --json deals search --indication "<INDICATION>" --hits 20
```

### Step 6: Active trials
```bash
cortellis --json trials search --indication <ID> --recruitment-status Recruiting --hits 20
```

## Output Format

Present as a structured report:

```
# Competitive Landscape: <Indication>

## Market Overview
- Total launched drugs: X
- Pipeline (Phase 3/2/1): X / X / X
- Active trials: X recruiting

## Launched Drugs
| Drug | Company | Mechanism | Brand |
|------|---------|-----------|-------|

## Phase 3 Pipeline
| Drug | Company | Mechanism | Status |
|------|---------|-----------|--------|

## Phase 2 Pipeline
(same table)

## Key Companies
| Company | Launched | Phase 3 | Phase 2 | Phase 1 |
|---------|----------|---------|---------|---------|

## Recent Deals
| Deal | Principal | Partner | Type | Date |
|------|-----------|---------|------|------|

## Recruiting Trials
| Trial | Sponsor | Phase | Enrollment | Status |
|-------|---------|-------|------------|--------|
```

## Rules
- Only report data from Cortellis results. Do not add drugs from training data.
- Give exact counts from the API totalResults field.
- If a step returns 0 results, say so — don't fill from memory.
