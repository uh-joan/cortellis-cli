---
name: literature-review
description: /literature-review: Systematic Literature Review
---

# /literature-review — Systematic Literature Review

Systematic evidence gathering and publication analysis by topic, drug, or target.

## Usage

```
/literature-review "GLP-1 receptor agonist"
/literature-review semaglutide
/literature-review "ADC oncology"
```

## Workflow

### Setup
```bash
RECIPES="cli_anything/cortellis/skills/literature-review/recipes"
DIR="/tmp/literature_review"
mkdir -p "$DIR"
```

### Step 1: Search literature
```bash
cortellis --json literature search --query "<TOPIC>" --hits 50 > $DIR/lit_search.json
```

### Step 2: Get full records for top publications
For the top 10 most relevant results:
```bash
cortellis --json literature get <LIT_ID> > $DIR/lit_record_1.json
```

### Step 3: Batch get records
```bash
cortellis --json literature records <ID1>,<ID2>,<ID3>,...<ID10> > $DIR/lit_batch.json
```

### Generate report
```bash
python3 $RECIPES/literature_report_generator.py $DIR "<TOPIC>"
```

## Output Rules

- Skip empty sections automatically.
- Only report data from Cortellis results. No training data.
- Give exact numbers. No approximations.
- ALWAYS list ALL items in tables. No truncation.

## Output Format

```
# Literature Review: <Topic>

**Total Results:** X

## Publication Summary
| Year | Count |
(ASCII bar chart of publications by year)

## Top Journals
| Journal | Count |

## Key Publications
| # | Title | Authors | Journal | Year |

## Publication Details
### 1. <Title>
**Authors:** X | **Journal:** X | **Year:** X
Abstract...
```

## Recipes

### Steps 1-3 -> Collect data, then generate report
```bash
python3 $RECIPES/literature_report_generator.py $DIR "<TOPIC>"
# Reads: lit_search.json, lit_batch.json
# Outputs: formatted markdown with publication analysis
# Skips empty sections automatically
```
