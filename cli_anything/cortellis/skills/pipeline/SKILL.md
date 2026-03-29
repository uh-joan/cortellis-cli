---
name: pipeline
description: /pipeline: Company Pipeline Analysis
---

# /pipeline — Company Pipeline Analysis

Analyze a company's full drug development pipeline.

## Usage

```
/pipeline "Novo Nordisk"
/pipeline "Eli Lilly"
/pipeline 18614
```

## Workflow

### Step 1: Resolve company ID (if name given)
```bash
cortellis --json companies search --name "<COMPANY>" --hits 5
```
Pick the best match and extract the ID.

### Step 2: Get company profile
```bash
cortellis --json companies get <COMPANY_ID>
```

### Step 3: Drugs by phase
Run for each phase:
```bash
cortellis --json drugs search --company <COMPANY_ID> --phase L --hits 50
cortellis --json drugs search --company <COMPANY_ID> --phase C3 --hits 50
cortellis --json drugs search --company <COMPANY_ID> --phase C2 --hits 50
cortellis --json drugs search --company <COMPANY_ID> --phase C1 --hits 50
cortellis --json drugs search --company <COMPANY_ID> --phase DR --hits 50
```

### Step 4: Recent deals
```bash
cortellis --json deals search --principal "<COMPANY>" --hits 20
```

### Step 5: Active trials
```bash
cortellis --json trials search --sponsor "<COMPANY>" --recruitment-status Recruiting --hits 20
```

## Output Format

```
# Pipeline Report: <Company>

## Summary
- Total drugs: X (Launched: X, Phase 3: X, Phase 2: X, Phase 1: X, Discovery: X)
- Active trials: X recruiting
- Recent deals: X

## Pipeline by Phase

### Launched (X)
| Drug | Indication | Mechanism |
|------|-----------|-----------|

### Phase 3 (X)
| Drug | Indication | Mechanism |
|------|-----------|-----------|

(repeat for Phase 2, 1, Discovery)

## Therapeutic Focus
Top indications by drug count (extracted from pipeline data).

## Recent Deals (last 20)
| Deal | Partner | Type | Date |
|------|---------|------|------|

## Recruiting Trials
| Trial | Indication | Phase | Enrollment |
|-------|-----------|-------|------------|
```

## Rules
- Only report data from Cortellis results.
- Give exact counts.
- Do not supplement with training data.
