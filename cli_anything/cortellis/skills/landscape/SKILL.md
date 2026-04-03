---
name: landscape
description: /landscape: Competitive Landscape Report
---

# /landscape — Competitive Landscape Report

Generate a full competitive landscape for a therapeutic indication.

## Usage

**Indication mode (default):**
```
/landscape obesity
/landscape "non-small cell lung cancer"
/landscape MASH
/landscape "Huntington's disease"
/landscape "sickle cell disease"
```

**Target mode:**
```
/landscape --target "GLP-1 receptor"
/landscape --target "PD-L1"
/landscape --target "EGFR"
/landscape --target "CDK4/6"
```

**Technology mode:**
```
/landscape --technology "ADC"
/landscape --technology "mRNA"
/landscape --technology "gene therapy"
/landscape --technology "CAR-T"
```

**Combined mode (technology + indication):**
```
/landscape --technology "ADC" --indication "cancer"
/landscape --technology "mRNA" --indication "cancer"
/landscape --technology "gene therapy" --indication "sickle cell disease"
```

## Technology Mode Workflow

When invoked as `/landscape --technology "<TECH>"` (optionally with `--indication "<IND>"`), use the following workflow.

### Technology Setup
```bash
RECIPES="cli_anything/cortellis/skills/landscape/recipes"
PIPELINE_RECIPES="cli_anything/cortellis/skills/pipeline/recipes"
DIR="/tmp/landscape_tech"
mkdir -p "$DIR"
```

### Technology Step 1: Resolve technology ID and name
```bash
RESULT=$(python3 $RECIPES/resolve_technology.py "<TECH>")
TECH_ID=$(echo "$RESULT" | cut -d',' -f1)
TECH_NAME=$(echo "$RESULT" | cut -d',' -f2-)
# Output: id,name (e.g. "1164,Antibody drug conjugate")
# Strategies: synonym table → ontology search (--category technology) → normalized retry
# Use TECH_ID with --technology for precise taxonomy matching
```

### Technology Step 2 (combined mode only): Resolve indication ID
```bash
# Only needed when --indication is also provided:
RESULT=$(python3 $RECIPES/resolve_indication.py "<INDICATION>")
IND_ID=$(echo "$RESULT" | cut -d',' -f1)
IND_NAME=$(echo "$RESULT" | cut -d',' -f2-)
```

### Technology Step 3: Drugs by phase (paginated)
```bash
# Technology-only mode (use --phase-highest for "drugs whose highest phase IS X"):
bash $RECIPES/fetch_drugs_paginated.sh L $DIR/launched.csv $PIPELINE_RECIPES --phase-highest --technology $TECH_ID
bash $RECIPES/fetch_drugs_paginated.sh C3 $DIR/phase3.csv $PIPELINE_RECIPES --phase-highest --technology $TECH_ID
bash $RECIPES/fetch_drugs_paginated.sh C2 $DIR/phase2.csv $PIPELINE_RECIPES --phase-highest --technology $TECH_ID
bash $RECIPES/fetch_drugs_paginated.sh C1 $DIR/phase1.csv $PIPELINE_RECIPES --phase-highest --technology $TECH_ID
bash $RECIPES/fetch_drugs_paginated.sh DR $DIR/discovery.csv $PIPELINE_RECIPES --phase-highest --technology $TECH_ID

# Combined mode (technology + indication):
bash $RECIPES/fetch_drugs_paginated.sh L $DIR/launched.csv $PIPELINE_RECIPES --phase-highest --technology $TECH_ID --indication $IND_ID
bash $RECIPES/fetch_drugs_paginated.sh C3 $DIR/phase3.csv $PIPELINE_RECIPES --phase-highest --technology $TECH_ID --indication $IND_ID
bash $RECIPES/fetch_drugs_paginated.sh C2 $DIR/phase2.csv $PIPELINE_RECIPES --phase-highest --technology $TECH_ID --indication $IND_ID
bash $RECIPES/fetch_drugs_paginated.sh C1 $DIR/phase1.csv $PIPELINE_RECIPES --phase-highest --technology $TECH_ID --indication $IND_ID
bash $RECIPES/fetch_drugs_paginated.sh DR $DIR/discovery.csv $PIPELINE_RECIPES --phase-highest --technology $TECH_ID --indication $IND_ID
```

### Technology Step 4: Key companies
```bash
python3 $RECIPES/company_landscape.py $DIR > $DIR/companies.csv
```

### Technology Step 5: Recent deals
```bash
cortellis --json deals search --query "dealTechnologies:\"$TECH_NAME\"" --hits 20 --sort-by "-dealDateStart" | python3 $PIPELINE_RECIPES/deals_to_csv.py > $DIR/deals.csv
```

### Technology Step 6: Generate report
```bash
python3 $RECIPES/landscape_report_generator.py $DIR "$TECH_NAME" "" "<TECH>"
# Pass empty string for ID (not applicable in technology mode)
# For combined mode: python3 $RECIPES/landscape_report_generator.py $DIR "$TECH_NAME ($IND_NAME)" "" "<TECH> + <IND>"
# USER_INPUT is the original user-supplied technology (and indication) name
```

## Target Mode Workflow

When invoked as `/landscape --target "<TARGET>"`, use the following workflow instead of the indication workflow below.

### Target Setup
```bash
RECIPES="cli_anything/cortellis/skills/landscape/recipes"
PIPELINE_RECIPES="cli_anything/cortellis/skills/pipeline/recipes"
DIR="/tmp/landscape_target"
mkdir -p "$DIR"
```

### Target Step 1: Resolve action name
```bash
ACTION_NAME=$(python3 $RECIPES/resolve_target.py "<TARGET>")
# Output: canonical action name (e.g. "Glucagon-like peptide 1 receptor agonist")
# Strategies: synonym table → NER → ontology → normalized retry
# Use this name with --action in all drug searches
```

### Target Step 2: Drugs by phase (paginated, --phase-highest for "drugs whose highest phase IS X")
```bash
bash $RECIPES/fetch_drugs_paginated.sh L $DIR/launched.csv $PIPELINE_RECIPES --phase-highest --action "$ACTION_NAME"
bash $RECIPES/fetch_drugs_paginated.sh C3 $DIR/phase3.csv $PIPELINE_RECIPES --phase-highest --action "$ACTION_NAME"
bash $RECIPES/fetch_drugs_paginated.sh C2 $DIR/phase2.csv $PIPELINE_RECIPES --phase-highest --action "$ACTION_NAME"
bash $RECIPES/fetch_drugs_paginated.sh C1 $DIR/phase1.csv $PIPELINE_RECIPES --phase-highest --action "$ACTION_NAME"
bash $RECIPES/fetch_drugs_paginated.sh DR $DIR/discovery.csv $PIPELINE_RECIPES --phase-highest --action "$ACTION_NAME"
```

### Target Step 3: Key companies
```bash
python3 $RECIPES/company_landscape.py $DIR > $DIR/companies.csv
```

### Target Step 4: Recent deals
```bash
cortellis --json deals search --query "dealActionsPrimary:\"$ACTION_NAME\"" --hits 20 --sort-by "-dealDateStart" | python3 $PIPELINE_RECIPES/deals_to_csv.py > $DIR/deals.csv
```

### Target Step 5: Generate report
```bash
python3 $RECIPES/landscape_report_generator.py $DIR "$ACTION_NAME" "" "<TARGET>"
# Pass empty string for ID (not applicable in target mode)
# USER_INPUT is the original user-supplied target name
```

## Indication Workflow

### Setup
```bash
RECIPES="cli_anything/cortellis/skills/landscape/recipes"
PIPELINE_RECIPES="cli_anything/cortellis/skills/pipeline/recipes"
DIR="/tmp/landscape"
mkdir -p "$DIR"
HEADER="name,id,phase,indication,mechanism,company,source"
```

### Step 1: Resolve indication ID
```bash
RESULT=$(python3 $RECIPES/resolve_indication.py "<INDICATION>")
# Output: indication_id,indication_name
# Strategies: synonym lookup → NER → ontology → normalized retry → suffix stripping
# Handles: apostrophes (Huntington's), synonyms (sickle cell disease → anemia),
#   abbreviations (ALS, NSCLC, COPD), multi-word names
# Tested: 12 indications including obesity, NSCLC, MASH, Huntington's, sickle cell,
#   narcolepsy, acromegaly, cystic fibrosis, myasthenia gravis — all correct
```

### Step 2: Drugs by phase (with pagination for large indications)
```bash
# Always use the pagination script — handles both small and large indications:
bash $RECIPES/fetch_indication_phase.sh <ID> L $DIR/launched.csv $PIPELINE_RECIPES
bash $RECIPES/fetch_indication_phase.sh <ID> C3 $DIR/phase3.csv $PIPELINE_RECIPES
bash $RECIPES/fetch_indication_phase.sh <ID> C2 $DIR/phase2.csv $PIPELINE_RECIPES
bash $RECIPES/fetch_indication_phase.sh <ID> C1 $DIR/phase1.csv $PIPELINE_RECIPES
bash $RECIPES/fetch_indication_phase.sh <ID> DR $DIR/discovery.csv $PIPELINE_RECIPES
# Auto-paginates up to 300 drugs per phase. Writes .meta.json with totalResults.
# Rate limit protection: 3s between pages, 10s retry on rate limit.
```

### Step 3: Enrich mechanisms (optional, adds ~2 API calls per empty drug)
```bash
python3 $RECIPES/enrich_mechanisms.py $DIR
# Fills empty mechanism fields from Drug Design (SI) by name search.
# Typical fill rate: 50-60% of empty mechanisms recovered.
# Max 20 lookups per phase file to control API calls.
```

### Step 4: Group biosimilars (optional, for indications with many biosimilars)
```bash
python3 $RECIPES/group_biosimilars.py $DIR
# Collapses biosimilar/follow-on entries under originator drug.
# RA: 140 launched → 72 after grouping. Critical for RA, breast cancer, oncology.
```

### Step 5: Key companies (deduplicated)
```bash
python3 $RECIPES/company_landscape.py $DIR > $DIR/companies.csv
```
Outputs deduplicated company counts with phase breakdown.

### Step 6: Recent deals
```bash
cortellis --json deals search --indication "<INDICATION>" --hits 20 --sort-by "-dealDateStart" | python3 $PIPELINE_RECIPES/deals_to_csv.py > $DIR/deals.csv
```

### Step 7: Recruiting trials
```bash
cortellis --json trials search --indication <ID> --recruitment-status Recruiting --hits 50 --sort-by "-trialDateStart" | python3 $PIPELINE_RECIPES/trials_to_csv.py > $DIR/trials.csv
```

### Step 7b: Trial phase summary (optional, shows total counts)
```bash
python3 $RECIPES/trials_phase_summary.py <ID> $DIR/trials_summary.csv
# Shows total recruiting trials per phase (not just top 50).
# Example: "63 total: Ph3=7, Ph2=14, Ph1=4, Ph4=4, Other=34"
```

### Step 8: Catch missing drugs (recommended)
```bash
python3 $RECIPES/catch_missing_drugs.py <ID> $DIR
# Fetches ALL drugs (no phase filter), compares against phase CSVs.
# Writes drugs missed by per-phase search to other.csv.
# Excludes attrition (discontinued, suspended, no development reported).
# Catches drugs in phases like "Preclinical" that --phase DR may miss.
```

### Step 9: Generate report
```bash
python3 $RECIPES/landscape_report_generator.py $DIR "<INDICATION_NAME>" "<INDICATION_ID>" "<USER_INPUT>"
# Reads .meta.json files for accurate truncation warnings.
# Pipeline chart, mechanism density chart, top companies chart.
# Drug tables per phase, company ranking, deals, trials summary.
# USER_INPUT is the original user query; shown in header when it differs from resolved name.
```

## Output Rules

- ALWAYS list ALL drugs in tables. NEVER truncate with "+ N others".
- Give exact counts from API @totalResults.
- Show warning only when data is actually truncated (metadata-based).
- Do not add drugs from training data.
- Present the report generator output directly. Do not reformat its tables.
- Company classification uses phase-weighted scoring (Launched=5, Phase 3=4, Phase 2=3, Phase 1=2, Discovery/Preclinical=1):
  - **Leader**: score >= 10 (e.g. 2 launched drugs, or 1 launched + 2 Phase 3)
  - **Active**: score >= 4, OR company is major pharma (Pfizer, Novartis, Roche, Merck, AstraZeneca, J&J, Sanofi, AbbVie, Lilly, BMS, Amgen, Gilead, GSK, Bayer, Boehringer, Takeda, Novo Nordisk, Biogen, Regeneron, Vertex)
  - **Emerging**: score < 4 and not major pharma

## Output Format

```
# Competitive Landscape: <Indication>

## Market Overview
**Total drugs:** X | **Deals:** X | **Recruiting trials:** X

(ASCII charts: Pipeline by Phase, Competitive Density by Mechanism, Top Companies)

## Pipeline Summary
| Phase | Count |
|-------|-------|

### Launched (X)
| Drug | Company | Mechanism |
(list ALL)

### Phase 3 (X)
(list ALL)

(repeat for Phase 2, Phase 1, Discovery)

## Key Companies
| Company | Unique Drugs | Market Position |
|---------|-------------|-----------------|
(deduplicated — Leader/Active/Emerging based on drug count)

## Recent Deals
| Deal | Partner | Type | Date |
(sorted newest first)

## Recruiting Trials
| Phase | Trials |
|-------|--------|
```

## Recipes (8 total)

### resolve_indication.py — Indication ID resolution
```bash
python3 $RECIPES/resolve_indication.py "<INDICATION>"
# 5-strategy resolution: synonym table → NER → ontology → normalized retry → suffix strip
# Handles apostrophes, abbreviations (ALS, NSCLC), common synonyms
# Tested on 12 diverse indications — all correct
```

### fetch_indication_phase.sh — Paginated drug fetch
```bash
bash $RECIPES/fetch_indication_phase.sh <IND_ID> <PHASE> <OUTPUT_CSV> $PIPELINE_RECIPES
# Auto-paginates up to 300 drugs per phase. Auto-detects venv PATH.
# Writes .meta.json with totalResults for truncation detection.
# Rate limit: 3s between pages, guards empty results, no false 429 detection.
```

### enrich_mechanisms.py — SI mechanism enrichment
```bash
python3 $RECIPES/enrich_mechanisms.py $DIR
# Searches Drug Design (SI) by drug name for empty mechanism fields.
# Typical fill rate: 50-60%. Max 20 lookups per file.
# Example: pirarubicin → "DNA Topoisomerase II Inhibitors; DNA-Intercalating Drugs"
```

### group_biosimilars.py — Biosimilar grouping
```bash
python3 $RECIPES/group_biosimilars.py $DIR
# Detects "biosimilar"/"follow-on" in drug names, groups under originator.
# RA launched: 140 → 72 rows (68 biosimilars grouped).
# Shows: "adalimumab (+ 20 biosimilars)" instead of 20 separate rows.
```

### company_landscape.py — Deduplicated company analysis
```bash
python3 $RECIPES/company_landscape.py $DIR > $DIR/companies.csv
# Counts unique drugs per company (not drug-phase entries).
# Phase breakdown: launched, phase3, phase2, phase1, discovery.
```

### trials_phase_summary.py — Trial counts by phase
```bash
python3 $RECIPES/trials_phase_summary.py <IND_ID> $DIR/trials_summary.csv
# Makes per-phase API calls to get accurate totalResults.
# Shows total recruiting count, not just the top 50.
```

### resolve_target.py — Target/action name resolution
```bash
python3 $RECIPES/resolve_target.py "<TARGET>"
# 3-strategy resolution: synonym table → NER (Action entities) → ontology → normalized retry
# Returns canonical action name for use with --action flag in drugs search
# Handles abbreviations (GLP-1, PD-L1, EGFR, CDK4/6) and full names
# Example: "GLP-1 receptor" → "Glucagon-like peptide 1 receptor agonist"
```

### resolve_technology.py — Technology/modality name resolution
```bash
python3 $RECIPES/resolve_technology.py "<TECH>"
# 2-strategy resolution: synonym table → ontology (--category technology) → normalized retry
# Returns canonical technology name for use with --technology flag in drugs search
# Handles abbreviations (ADC, mRNA, CAR-T) and alternate spellings
# Example: "ADC" → "Antibody drug conjugate", "mRNA" → "mRNA therapy"
# Example: "gene therapy" → "Gene transfer system viral"
```

### landscape_report_generator.py — Report with ASCII charts
```bash
python3 $RECIPES/landscape_report_generator.py $DIR "<NAME>" "<ID>" "<USER_INPUT>"
# Reads .meta.json for accurate truncation warnings (no false positives).
# Pipeline chart, mechanism density chart, top companies chart.
# Wider table columns: drug (60), company (40), mechanism (50).
# USER_INPUT shown in header when it differs from resolved indication name.
```

NOTE: This skill reuses pipeline recipes for CSV conversion:
- `$PIPELINE_RECIPES/ci_drugs_to_csv.py`
- `$PIPELINE_RECIPES/deals_to_csv.py`
- `$PIPELINE_RECIPES/trials_to_csv.py`
