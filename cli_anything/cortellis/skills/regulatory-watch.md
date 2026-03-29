# /regulatory-watch — Regulatory Activity Monitor

Track recent regulatory activity for a drug, company, or region.

## Usage

```
/regulatory-watch semaglutide
/regulatory-watch --region USA --recent
/regulatory-watch "FDA approval" --year 2024
```

## Workflow

### Step 1: Search regulatory documents
Based on user input:

By drug:
```bash
cortellis --json regulations search --query "<DRUG>" --hits 30 --sort-by "-regulatoryDateSort"
```

By region:
```bash
cortellis --json regulations search --region <REGION> --hits 30 --sort-by "-regulatoryDateSort"
```

By doc type:
```bash
cortellis --json regulations search --doc-type "<TYPE>" --hits 30 --sort-by "-regulatoryDateSort"
```

With date filter:
```bash
cortellis --json regulations search --query "<TOPIC> AND regulatoryDateUpdated:RANGE(>=2024-01-01;<=2024-12-31)" --hits 30
```

### Step 2: Get snapshots for key documents
For the most important results:
```bash
cortellis --json regulations snapshot <ID>
```

### Step 3: Check citations
For approval documents:
```bash
cortellis --json regulations cited-documents <ID>
```

## Output Format

```
# Regulatory Watch: <Topic>

## Summary
- Documents found: X
- Regions: X, Y, Z
- Date range: X — Y

## Recent Activity
| Date | Title | Region | Type | Status |
|------|-------|--------|------|--------|

## Key Documents
For each important document:
- **Title:** X
- **Region:** X | **Type:** X | **Date:** X
- **Summary:** (from snapshot abstract)

## By Region
| Region | Count |
|--------|-------|

## By Document Type
| Type | Count |
|------|-------|
```

## Rules
- Sort by most recent first (use -regulatoryDateSort).
- Only report data from Cortellis results.
- Snapshots may fail for some IDs — skip those.
