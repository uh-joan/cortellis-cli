---
name: changelog
description: Use when a user asks what changed in a competitive landscape, wants pipeline evolution history, asks "what's new since last run", "what changed in [indication]", or wants a temporal diff of drug counts, company rankings, or phase transitions.
---

# /changelog — Competitive Landscape History

Show how a compiled landscape evolved over time using raw data history.

## Usage
/changelog obesity
/changelog "non-small cell lung cancer"
/changelog MASH

## Note on data source

Wiki files are not git-tracked (gitignored). The changelog uses:
- `raw/<slug>/historical_snapshots.csv` — monthly phase-count time series
- `raw/<slug>/phase_timeline.csv` — individual drug phase transitions
- `raw/<slug>/strategic_scores.csv` — current company CPI rankings
- `wiki/indications/<slug>.md` frontmatter — current compiled state

## Workflow

### Step 1: Resolve indication slug
```bash
SLUG=$(python3 -c "
import sys; sys.path.insert(0,'.')
from cli_anything.cortellis.utils.wiki import slugify
print(slugify('<INDICATION>'))
")
WIKI_FILE="wiki/indications/$SLUG.md"
RAW_DIR="raw/$SLUG"
```

### Step 2: Extract changelog
```bash
python3 cli_anything/cortellis/skills/changelog/recipes/extract_changes.py "$WIKI_FILE" "$RAW_DIR" "<INDICATION>"
```

### Step 3: Display narrative
Print the changelog narrative to the user.
