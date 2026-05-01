---
name: changelog
description: Use when a user asks what changed in a competitive landscape, wants pipeline evolution history, asks "what's new since last run", "what changed in [indication]", "how did the pipeline evolve", or wants a temporal diff of drug counts, company rankings, or phase transitions.
---

# /changelog — Competitive Landscape History

Show how a compiled landscape evolved over time using raw data history.

## IMPORTANT — Execution rules

1. **Always run the harness.** Never answer changelog questions from memory, wiki context, or the landscape output. Always execute `cortellis run-skill changelog "<indication>"` and display the output verbatim.
2. **Do not report internal harness details.** Never mention variable names, node IDs, file paths, or implementation bugs to the user.
3. **Display the script output as-is.** The harness prints the changelog narrative directly — pass it through without reformatting or adding commentary.
4. **Do not say "no data yet" without running the skill.** The historical timeline may have been populated in the same session. Always run first, then report what the script returns.

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
