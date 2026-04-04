---
name: indication-deep-dive
description: /indication-deep-dive: Complete Indication Analysis
---

# /indication-deep-dive — Complete Indication Analysis

Everything about one disease: drugs by phase, clinical trials, deals, regulatory documents, targets, and literature.

## Usage

```
/indication-deep-dive obesity
/indication-deep-dive "non-small cell lung cancer"
/indication-deep-dive MASH
```

## Workflow

### Setup
```bash
RECIPES="cli_anything/cortellis/skills/indication-deep-dive/recipes"
LANDSCAPE_RECIPES="cli_anything/cortellis/skills/landscape/recipes"
DIR="/tmp/indication_deep_dive"
mkdir -p "$DIR"
```

### Step 1: Resolve indication
```bash
RESULT=$(python3 $LANDSCAPE_RECIPES/resolve_indication.py "<INDICATION>")
# Output: indication_id,indication_name
```

### Step 2: Drugs by phase (launched + late-stage)
```bash
cortellis --json drugs search --indication <IND_ID> --phase L --hits 30 > $DIR/drugs_launched.json
cortellis --json drugs search --indication <IND_ID> --phase C3 --hits 30 > $DIR/drugs_p3.json
cortellis --json drugs search --indication <IND_ID> --phase C2 --hits 30 > $DIR/drugs_p2.json
```

### Step 3: Clinical trials
```bash
cortellis --json trials search --indication "<IND_NAME>" --hits 30 --sort-by "-trialDateStart" > $DIR/trials.json
```

### Step 4: Recent deals
```bash
cortellis --json deals search --indication "<IND_NAME>" --hits 20 --sort-by "-dealDateStart" > $DIR/deals.json
```

### Step 5: Regulatory documents
```bash
cortellis --json regulations search --query "<IND_NAME>" --hits 15 > $DIR/regulatory.json
```

### Step 6: Literature
```bash
cortellis --json literature search --query "<IND_NAME>" --hits 20 > $DIR/literature.json
```

### Generate report
```bash
python3 $RECIPES/indication_report_generator.py $DIR "<IND_NAME>"
```

## Output Rules

- Skip empty sections automatically.
- Only report data from Cortellis results. No training data.
- Give exact numbers. No approximations.
- ALWAYS list ALL items in tables. No truncation.

## Output Format

```
# Indication Deep Dive: <Indication>

## Drug Pipeline
(ASCII bar chart by phase)
### Launched (X)
| Drug | Company | Mechanism |
### Phase 3 (X)
### Phase 2 (X)

## Clinical Trials (X total)
| Trial | Phase | Sponsor | Status | Enrollment |

## Recent Deals (X total)
| Deal | Principal | Partner | Type | Date |

## Regulatory Documents (X total)
| Document | Region | Type | Date |

## Literature (X total)
| Title | Authors | Journal | Year |
```

## Recipes

### Step 1 -> Resolve indication (reuses landscape resolver)
```bash
python3 $LANDSCAPE_RECIPES/resolve_indication.py "<INDICATION>"
```

### Steps 2-6 -> Collect data, then generate report
```bash
python3 $RECIPES/indication_report_generator.py $DIR "<IND_NAME>"
```
