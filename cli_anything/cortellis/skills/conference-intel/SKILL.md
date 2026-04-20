---
name: conference-intel  
description: /conference-intel: Conference Intelligence Briefing
---

# /conference-intel — Conference Intelligence Briefing

Search conferences and generate "What's New / So What / What's Next" briefings.

## Usage
/conference-intel ASCO 2026
/conference-intel "obesity conferences"

## Workflow

### Step 1: Search conferences
```bash
cortellis --json conferences search --query "<CONFERENCE_OR_TOPIC>" --hits 20
```

### Step 2: Fetch conference details
For each relevant conference:
```bash
cortellis --json conferences get <CONFERENCE_ID>
```

### Step 3: Cross-reference with compiled knowledge
```bash
python3 $RECIPES/conference_briefing.py <output_dir> "<query>"
# Reads conference data + wiki/ articles
# Cross-references presenters against wiki company articles
# Cross-references drug mentions against wiki indication articles
```

### Step 4: Present briefing
Present the conference_briefing.md output.

### Step 5: Compile to wiki
```bash
python3 $RECIPES/compile_conference.py $DIR "<CONFERENCE_NAME>"
```
Writes `wiki/conferences/<slug>.md` and updates `INDEX.md`.

### Post-Run Review (run after report is delivered)
```bash
python3 $RECIPES/../post_run_reviewer.py conference-intel $DIR "<CONFERENCE_NAME>"
```
Read the manifest output above. If you see a clear pattern worth encoding
(e.g. cross-referencing fails without compiled wiki), update the
`## Learned Optimizations` section below with a targeted patch.

## Learned Optimizations
<!-- Auto-updated by post-run review. Add generalizable skip rules and fast-path hints here. -->

- **Cross-referencing (Step 3) only adds value when wiki articles exist** — if no landscape or drug-profile runs have been compiled yet, `conference_briefing.py` will find no matches. In fresh environments, skip cross-reference or note "no compiled knowledge available."

## Execution Rules

- Once the final report has been delivered to the user, **do not respond to background task completion notifications**. Discard them silently — they are late arrivals for steps already processed.

## Output Rules
- Focus on "What's New / So What / What's Next" framing
- Cross-reference against compiled wiki when available
- Highlight drugs/companies that appear in compiled landscapes
