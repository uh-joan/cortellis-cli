---
name: partnership-network
description: /partnership-network: Partnership Network Analysis
---

# /partnership-network — Partnership Network Analysis

Who partners with whom? Analyze deal partnerships for a company or in an indication.

## Usage

```
/partnership-network "Novo Nordisk"
/partnership-network "Eli Lilly"
/partnership-network --indication "obesity"
```

## Workflow

### Setup
```bash
RECIPES="cli_anything/cortellis/skills/partnership-network/recipes"
PIPELINE_RECIPES="cli_anything/cortellis/skills/pipeline/recipes"
DIR="/tmp/partnership_network"
mkdir -p "$DIR"
```

### Step 1: Resolve company or indication
**If company:**
```bash
RESULT=$(python3 $PIPELINE_RECIPES/resolve_company.py "<COMPANY>")
```
**If indication:**
```bash
RESULT=$(python3 cli_anything/cortellis/skills/landscape/recipes/resolve_indication.py "<INDICATION>")
```

### Step 2: Search deals
**If company:**
```bash
cortellis --json deals search --principal "<COMPANY_NAME>" --hits 50 --sort-by "-dealDateStart" > $DIR/deals_principal.json
cortellis --json deals search --partner "<COMPANY_NAME>" --hits 50 --sort-by "-dealDateStart" > $DIR/deals_partner.json
```
**If indication:**
```bash
cortellis --json deals search --indication "<IND_NAME>" --hits 50 --sort-by "-dealDateStart" > $DIR/deals.json
```

### Generate report
```bash
python3 $RECIPES/partnership_report_generator.py $DIR "<ENTITY_NAME>"
```

## Output Rules

- Skip empty sections automatically.
- Only report data from Cortellis results. No training data.
- Give exact numbers. No approximations.

## Output Format

```
# Partnership Network: <Entity>

**Total Deals:** X

## Top Partners
| Partner | Deal Count | Latest Deal |

## Deal Types
| Type | Count |

## Partnership Timeline
(ASCII chart by year)

## All Deals
| Deal | Principal | Partner | Type | Date |
```

## Recipes

### Steps 1-2 -> Collect data, then generate report
```bash
python3 $RECIPES/partnership_report_generator.py $DIR "<ENTITY_NAME>"
```
