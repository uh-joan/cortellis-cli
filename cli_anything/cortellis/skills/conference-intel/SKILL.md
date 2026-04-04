---
name: conference-intel
description: /conference-intel: Conference Intelligence
---

# /conference-intel — Conference Intelligence

Conference-based competitive intelligence: search conferences by keyword, review abstracts and presentations.

## Usage

```
/conference-intel ASCO
/conference-intel "obesity congress"
/conference-intel "ADA 2025"
```

## Workflow

### Setup
```bash
RECIPES="cli_anything/cortellis/skills/conference-intel/recipes"
DIR="/tmp/conference_intel"
mkdir -p "$DIR"
```

### Step 1: Search conferences (paginated, up to 200 results)
```bash
# Page 1 (hits 1-20)
cortellis --json conferences search --query "<KEYWORD>" --hits 20 --offset 0 > $DIR/conferences_p1.json
# Page 2 (hits 21-40)
cortellis --json conferences search --query "<KEYWORD>" --hits 20 --offset 20 > $DIR/conferences_p2.json
# Continue up to page 10 (--offset 180) for up to 200 total results
# Merge all pages into a single file before running the report
```

### Step 2: Get full records for top conferences
```bash
cortellis --json conferences get <CONF_ID> > $DIR/conference_1.json
```

### Generate report
```bash
python3 $RECIPES/conference_report.py $DIR "<KEYWORD>"
```

## Output Rules

- Skip empty sections automatically.
- Only report data from Cortellis results. No training data.
- Show "Showing X of Y" when results are truncated.
- Conference search is paginated (up to 200 results).

## Output Format

```
# Conference Intelligence: <Keyword>

**Total Results:** X

## Conferences
| # | Title | Date | Location |

## Conference Details
### <Conference Title>
Abstract/summary content
```

## Recipes

### Steps 1-2 -> Collect data, then generate report
```bash
python3 $RECIPES/conference_report.py $DIR "<KEYWORD>"
```
