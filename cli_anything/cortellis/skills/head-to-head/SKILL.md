---
name: head-to-head
description: /head-to-head: Company vs Company Comparison
---

# /head-to-head — Company vs Company Comparison

Compare two companies side-by-side: pipeline depth, therapeutic focus, deal activity, KPIs, and competitive overlap.

## Usage

```
/head-to-head "Novo Nordisk" vs "Eli Lilly"
/head-to-head "Pfizer" "AstraZeneca"
```

## Workflow

### Setup
```bash
RECIPES="cli_anything/cortellis/skills/head-to-head/recipes"
PIPELINE_RECIPES="cli_anything/cortellis/skills/pipeline/recipes"
DIR="/tmp/head_to_head"
mkdir -p "$DIR"
```

### Step 1: Resolve both companies
```bash
RESULT1=$(python3 $PIPELINE_RECIPES/resolve_company.py "<COMPANY_1>")
RESULT2=$(python3 $PIPELINE_RECIPES/resolve_company.py "<COMPANY_2>")
```

### Step 2: Get analytics records
```bash
cortellis --json company-analytics get-company <ID_1> > $DIR/company_1.json
cortellis --json company-analytics get-company <ID_2> > $DIR/company_2.json
```

### Step 3: Pipeline success KPIs
```bash
cortellis --json company-analytics query-companies companyPipelineSuccess --id-list <ID_1>,<ID_2> > $DIR/pipeline_success.json
```

### Step 4: Recent deals for each
```bash
cortellis --json deals search --principal "<NAME_1>" --hits 15 --sort-by "-dealDateStart" > $DIR/deals_1.json
cortellis --json deals search --principal "<NAME_2>" --hits 15 --sort-by "-dealDateStart" > $DIR/deals_2.json
```

### Step 5: Active drugs by phase for each
```bash
cortellis --json drugs search --company <ID_1> --phase L --hits 20 > $DIR/drugs_launched_1.json
cortellis --json drugs search --company <ID_2> --phase L --hits 20 > $DIR/drugs_launched_2.json
```

### Generate report
```bash
python3 $RECIPES/head_to_head_report.py $DIR
```

## Output Rules

- Skip empty sections automatically.
- Only report data from Cortellis results. No training data.
- Give exact numbers. No approximations.
- Present side-by-side wherever possible.

## Output Format

```
# Head-to-Head: <Company A> vs <Company B>

## At a Glance
| Metric | <Company A> | <Company B> |

## Therapeutic Focus Overlap
| Indication | <Company A> | <Company B> |

## Pipeline Success
| Company | Total | Successful | Rate |
(ASCII chart)

## Recent Deals
### <Company A>
### <Company B>

## Launched Drug Portfolios
### <Company A>
### <Company B>
```

## Recipes

### Steps 1-5 -> Collect data, then generate report
```bash
python3 $RECIPES/head_to_head_report.py $DIR
```
