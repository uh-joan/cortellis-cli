---
name: patent-watch
description: /patent-watch: Patent Expiry & Competitive Watch
---

# /patent-watch — Patent Expiry & Competitive Watch

Patent expiry timeline and competitive positioning for a drug or company's portfolio.

## Usage

```
/patent-watch semaglutide
/patent-watch "Novo Nordisk"
```

## Workflow

### Setup
```bash
RECIPES="cli_anything/cortellis/skills/patent-watch/recipes"
DRUG_RECIPES="cli_anything/cortellis/skills/drug-profile/recipes"
PIPELINE_RECIPES="cli_anything/cortellis/skills/pipeline/recipes"
DIR="/tmp/patent_watch"
mkdir -p "$DIR"
```

### Step 1: Resolve drug or company
**If drug:**
```bash
RESULT=$(python3 $DRUG_RECIPES/resolve_drug.py "<DRUG_NAME>")
```
**If company:**
```bash
RESULT=$(python3 $PIPELINE_RECIPES/resolve_company.py "<COMPANY>")
```

### Step 2: Get patent expiry data
```bash
cortellis --json company-analytics query-drugs drugPatentProductExpiry --id-list <DRUG_ID> > $DIR/patent_expiry.json
```
Or for multiple drugs (company mode), collect drug IDs from pipeline first.

### Step 3: Get patent expiry detail
```bash
cortellis --json company-analytics query-drugs drugPatentExpiryDetail --id-list <DRUG_ID> > $DIR/patent_detail.json
```

### Step 4: Drug record for context
```bash
cortellis --json drugs get <DRUG_ID> --category report > $DIR/drug_record.json
```

### Step 5: Search for generic/biosimilar competitors
```bash
cortellis --json drugs search --drug-name "<DRUG_NAME> biosimilar" --hits 10 > $DIR/biosimilars.json
```

### Generate report
```bash
python3 $RECIPES/patent_report_generator.py $DIR "<DRUG_NAME>"
```

## Output Rules

- Skip empty sections automatically.
- Only report data from Cortellis results. No training data.
- Give exact numbers with dates. No approximations.

## Output Format

```
# Patent Watch: <Drug Name>

**ID:** X | **Phase:** Launched | **Originator:** X

## Patent Expiry Summary
| Patent | Territory | Expiry Date | Type |

## Patent Expiry Detail
| Patent | Territory | Expiry Date | Extension | SPC |

## Generic/Biosimilar Threats
| Drug | Company | Phase | Indications |
```

## Recipes

### Steps 1-5 -> Collect data, then generate report
```bash
python3 $RECIPES/patent_report_generator.py $DIR "<DRUG_NAME>"
```
