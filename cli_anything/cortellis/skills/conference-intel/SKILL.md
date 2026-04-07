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

## Output Rules
- Focus on "What's New / So What / What's Next" framing
- Cross-reference against compiled wiki when available
- Highlight drugs/companies that appear in compiled landscapes
