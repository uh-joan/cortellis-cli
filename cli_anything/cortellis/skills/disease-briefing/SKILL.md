---
name: disease-briefing
description: /disease-briefing: Disease Briefing Report
---

# /disease-briefing — Disease Briefing Report

Full disease overview from Cortellis Drug Design disease briefings with section text.

## Usage

```
/disease-briefing obesity
/disease-briefing "non-small cell lung cancer"
/disease-briefing MASH
```

## Workflow

### Setup
```bash
RECIPES="cli_anything/cortellis/skills/disease-briefing/recipes"
DIR="/tmp/disease_briefing"
mkdir -p "$DIR"
```

### Step 0: Verify subscription access
```bash
cortellis --json drug-design disease-briefings-search --query "obesity" --hits 1
```
If this returns an error or empty results, the user may not have a Drug Design premium subscription. Inform them and suggest `/indication-deep-dive` as an alternative. Do not proceed if subscription check fails.

### Step 1: Search disease briefings
```bash
cortellis --json drug-design disease-briefings-search --query "<DISEASE>" --hits 5 > $DIR/briefing_search.json
```

### Step 2: Get full briefing records
```bash
cortellis --json drug-design disease-briefings <BRIEFING_ID> > $DIR/briefing_record.json
```

### Step 2b: Extract section IDs from briefing record
The briefing record contains a `Sections.Section` array. Each section has:
- `@id` — the section ID needed for Step 3
- `Title` or `@name` — the section title

Extract all section IDs to iterate in Step 3:
```bash
# Section IDs are in: diseaseBriefingRecordOutput.Sections.Section[]."@id"
# Section titles are in: diseaseBriefingRecordOutput.Sections.Section[].Title
```

### Step 3: Get briefing section text (for each section)
```bash
cortellis --json drug-design disease-briefing-text <BRIEFING_ID> <SECTION_ID> > $DIR/section_1.txt
```

Save each section's text to `$DIR/section_<briefing_index>_<section_index>.txt` (e.g., `section_1_1.txt` for briefing 1, section 1). The report generator expects this naming convention.

### Generate report
```bash
python3 $RECIPES/briefing_report_generator.py $DIR "<DISEASE>" [MAX_CHARS]
```

`MAX_CHARS` defaults to 5000 characters per section. Use a higher value (e.g., 50000) for full briefing text.

## Output Rules

- Skip empty sections automatically.
- Only report data from Cortellis results. No training data.
- Clean HTML tags from section text.

## Scope

This skill provides disease overviews from Cortellis Drug Design premium briefings. It is a **triage and reference tool** — surfaces key sections for quick review. For full briefing text, increase the MAX_CHARS parameter.

For disease analysis using standard (non-premium) Cortellis data, use `/indication-deep-dive` instead.

## Output Format

```
# Disease Briefing: <Disease>

## Overview
| Field | Value |
|-------|-------|

## Sections
### <Section Title>
<Section text content>

## Related Analysis
(navigation hints to /landscape, /indication-deep-dive, /clinical-landscape)
```

## Recipes

### Steps 1-3 -> Collect data, then generate report
```bash
python3 $RECIPES/briefing_report_generator.py $DIR "<DISEASE>"
```
