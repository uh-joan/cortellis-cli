---
name: mechanism-explorer
description: /mechanism-explorer: Mechanism of Action Explorer
---

# /mechanism-explorer — Mechanism of Action Explorer

All drugs and evidence for a mechanism of action: pipeline by phase, pharmacology data, target biology.

## Usage

```
/mechanism-explorer "PD-1 inhibitor"
/mechanism-explorer "GLP-1 receptor agonist"
/mechanism-explorer "CDK4/6 inhibitor"
```

## Workflow

### Setup
```bash
RECIPES="cli_anything/cortellis/skills/mechanism-explorer/recipes"
LANDSCAPE_RECIPES="cli_anything/cortellis/skills/landscape/recipes"
DIR="/tmp/mechanism_explorer"
mkdir -p "$DIR"
```

### Step 1: Resolve action/mechanism name
```bash
RESULT=$(python3 $LANDSCAPE_RECIPES/resolve_target.py "<MECHANISM>")
# Output: action_name
```

### Step 2: Drugs by phase for this mechanism
```bash
cortellis --json drugs search --action "<ACTION_NAME>" --phase L --hits 30 > $DIR/drugs_launched.json
cortellis --json drugs search --action "<ACTION_NAME>" --phase C3 --hits 30 > $DIR/drugs_p3.json
cortellis --json drugs search --action "<ACTION_NAME>" --phase C2 --hits 30 > $DIR/drugs_p2.json
cortellis --json drugs search --action "<ACTION_NAME>" --phase C1 --hits 30 > $DIR/drugs_p1.json
```

### Step 3: Pharmacology data for this mechanism
```bash
cortellis --json drug-design pharmacology --query "<MECHANISM>" --hits 20 > $DIR/pharmacology.json
```

### Step 4: Recent deals involving this mechanism
```bash
cortellis --json deals search --action "<ACTION_NAME>" --hits 15 --sort-by "-dealDateStart" > $DIR/deals.json
```

### Generate report
```bash
python3 $RECIPES/mechanism_report.py $DIR "<MECHANISM>"
```

## Output Rules

- Skip empty sections automatically.
- Only report data from Cortellis results. No training data.
- Give exact numbers. No approximations.

## Output Format

```
# Mechanism Explorer: <Mechanism>

## Drug Pipeline
(ASCII bar chart by phase)
### Launched | Phase 3 | Phase 2 | Phase 1

## Top Companies
| Company | Drug Count |

## Pharmacology Data
| Compound | System | Target | Effect | Parameter | Value |

## Recent Deals
| Deal | Principal | Partner | Type | Date |
```

## Recipes

### Steps 1-4 -> Collect data, then generate report
```bash
python3 $RECIPES/mechanism_report.py $DIR "<MECHANISM>"
```
