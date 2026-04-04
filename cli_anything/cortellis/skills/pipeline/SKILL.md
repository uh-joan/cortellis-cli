---
name: pipeline
description: /pipeline: Company Pipeline Analysis
---

# /pipeline — Company Pipeline Analysis

Analyze a company's full drug development pipeline, merging CI and Drug Design (SI) data for complete early-stage coverage.

## Usage

```
/pipeline "Novo Nordisk"
/pipeline "Eli Lilly"
/pipeline 18614
```

## Workflow

### Step 0: Verify API credentials
```bash
python3 $RECIPES/check_api.py
```
If this fails, do not proceed — the API credentials are invalid or expired.

### Step 1: Resolve company ID (if name given)
```bash
RESULT=$(python3 $RECIPES/resolve_company.py "<COMPANY>")
python3 $RECIPES/manifest.py write /tmp/pipeline resolve_company $?
# Output: company_id,company_name,active_drugs,method
```
The recipe handles ALL resolution internally — do NOT call NER or ontology separately.
Strategies (in order): NER match → ontology depth-1 → broad search → suffix search.

Tested on 50 major pharma companies. Resolution may be less reliable for mid-size biotechs, subsidiaries, or recently renamed companies. If resolution fails, the script outputs method=FAIL — check this before proceeding.

### Step 2: Get company profile
```bash
cortellis --json companies get <COMPANY_ID>
```

### Step 3: CI pipeline — Drugs by phase
Run for each phase:
```bash
cortellis --json drugs search --company <COMPANY_ID> --phase L --hits 50
cortellis --json drugs search --company <COMPANY_ID> --phase C3 --hits 50
cortellis --json drugs search --company <COMPANY_ID> --phase C2 --hits 50
cortellis --json drugs search --company <COMPANY_ID> --phase C1 --hits 50
cortellis --json drugs search --company <COMPANY_ID> --phase DR --hits 50
```

### Step 4a: Drug Design (SI) — Phase I compounds (merge with CI Phase 1)
```bash
cortellis --json drug-design search-drugs --query "organizationsOriginator:\"<COMPANY>\" AND developmentIsActive:Yes AND phaseHighest:\"Phase I\"" --hits 50
```

### Step 4b: Drug Design (SI) — Preclinical compounds (merge with CI Discovery)
```bash
cortellis --json drug-design search-drugs --query "organizationsOriginator:\"<COMPANY>\" AND developmentIsActive:Yes AND phaseHighest:\"Preclinical\"" --hits 50
```
Note: "Biological Testing" exists as a phase but has 0 active compounds across major pharma. Skip unless results are needed.

### Step 4c: Resolve per-indication phase mapping (1 batch API call)
```bash
# Find overlapping drug IDs
IDS=$(python3 $RECIPES/resolve_phase_indications.py find /tmp/pipeline)

# Batch fetch full records (1 API call, up to 50 IDs)
cortellis --json drugs records $IDS > /tmp/pipeline/overlap_records.json

# Rewrite CSVs with phase-specific indications
python3 $RECIPES/resolve_phase_indications.py rewrite /tmp/pipeline
```
This replaces the generic "all indications" with only the indications at that specific phase. For example, semaglutide in the Phase 2 CSV will only show Phase 2 indications (cirrhosis, MASLD), not its Launched indications (T2D, obesity).

### Step 5: Recent deals
```bash
cortellis --json deals search --principal "<COMPANY>" --hits 20 --sort-by "-dealDateStart"
```

### Step 6: Active trials (fetch enough for accurate counts)
```bash
cortellis --json trials search --sponsor "<COMPANY>" --recruitment-status Recruiting --hits 50 --sort-by "-trialDateStart"
```

### Step 7: Catch missing drugs (recommended)
```bash
python3 $RECIPES/catch_missing_drugs.py <COMPANY_ID> $DIR
# Fetches ALL drugs (no phase filter), compares against phase CSVs.
# Writes drugs missed by per-phase search to other.csv.
# Excludes attrition (discontinued, suspended, no development reported).
# Catches drugs in phases like "Preclinical" that --phase DR may miss.
```

## Merge Rules

- **Phase 1**: merge CI Phase 1 (C1) + Step 4a SI Phase I → deduplicate by name
- **Preclinical**: merge CI Discovery (DR) + Step 4b SI Biological Testing → deduplicate by name
- Always deduplicate by drug name — if a drug appears in both CI and SI, list it once
- Do not label or distinguish the source — just show unified sections

## Output Rules

- **ALWAYS list ALL drugs in EVERY table.** NEVER truncate with "+ N others", "+ more", "and others", or similar. Every single drug must have its own row. Up to 150 per phase (with pagination).
- Give exact counts from the API `@totalResults` field.
- Never approximate. Never say "~8" or "6-7".
- Do not add drugs from training data. Only report what the CLI returned.

## Data Integrity

The pipeline includes a **run manifest** (`manifest.py`) that tracks every step's success or failure.

After each major step, record the result:
```bash
python3 $RECIPES/manifest.py write /tmp/pipeline <step_name> $? [csv_file]
```

Before generating the report, validate the run:
```bash
python3 $RECIPES/manifest.py validate /tmp/pipeline
```
This checks that all 14 expected steps completed, no step exited non-zero, and no CSV has 0 data rows. It exits with code 1 if any check fails — **do not generate the report if validation fails**. Instead, report the failures to the user.

After the report, append a run summary:
```bash
python3 $RECIPES/manifest.py report /tmp/pipeline
```
This prints a table with each step's status, row count, and timestamp, plus warnings for any phase hitting the 150-drug pagination limit.

## Output Format

```
# Pipeline Report: <Company>

## Summary
- Total drugs (CI): X (Launched: X, Phase 3: X, Phase 2: X, Phase 1: X, Discovery: X)
- SI active compounds: X
- Active recruiting trials: X
- Recent deals: X

## Launched (X)
| Drug | Indication | Mechanism |
|------|-----------|-----------|
(list ALL — no truncation)

## Phase 3 (X)
| Drug | Indication | Mechanism |
|------|-----------|-----------|
(list ALL)

## Phase 2 (X)
| Drug | Indication | Mechanism |
|------|-----------|-----------|
(list ALL)

## Phase 1 (X)
| Drug | Indication | Mechanism |
|------|-----------|-----------|
(list ALL — use the "Steps 3+4 → Merge CI + SI" recipe below to merge and deduplicate)

## Preclinical (X)
| Drug | Indication | Mechanism | Biologic |
|------|-----------|-----------|----------|
(list ALL — use the "Steps 3+4 → Merge" recipe to merge CI Discovery + remaining SI compounds not in Phase 1. Every drug gets its own row, NO summaries.)

## Therapeutic Focus
Count indications across ALL CI phases (Launched + Phase 3 + Phase 2 + Phase 1 + Discovery). Use the count_by_indication recipe on ALL phase results combined. NOT just one phase, NOT just SI.

## Recent Deals
| Deal | Partner | Type | Date |
|------|---------|------|------|
(list ALL up to 20)

## Recruiting Trials (X total)
| Indication | Trial Count |
|-----------|-------------|
(count indications from ALL fetched trials — use --hits 50 in Step 6 to get enough data. State the total from @totalResults.)

## Attrition Summary
(count of discontinued/suspended/withdrawn drugs with breakdown by status — generated automatically from catch_missing_drugs.py output)

## Competitive Context (optional)
(top 3 indications with total market drug counts at Launched/Phase 3/Phase 2 — run competitive_context.py)

## Pipeline Changes (optional, requires previous snapshot)
(phase advances, regressions, new additions, removals since last run — run diff_pipeline.py)
```

## Recipes (CSV-based data pipeline)

All data flows through CSV files in `/tmp/pipeline/`. Use the recipe scripts in `recipes/` — do NOT write your own parsers.

**CSV columns:** `name,id,phase,indication,mechanism,company,source`

### Setup
```bash
RECIPES="cli_anything/cortellis/skills/pipeline/recipes"
mkdir -p /tmp/pipeline
rm -f /tmp/pipeline/manifest.json
HEADER="name,id,phase,indication,mechanism,company,source"
```

### Step 0 → Verify API credentials
```bash
python3 $RECIPES/check_api.py
python3 $RECIPES/manifest.py write /tmp/pipeline api_check $?
```
If this step fails (exit code 1), stop the pipeline and inform the user that API credentials need to be refreshed.

### Step 3 → Save each CI phase to CSV
```bash
echo "$HEADER" > /tmp/pipeline/launched.csv
cortellis --json drugs search --company <ID> --phase L --hits 50 | python3 $RECIPES/ci_drugs_to_csv.py >> /tmp/pipeline/launched.csv
python3 $RECIPES/manifest.py write /tmp/pipeline launched $? /tmp/pipeline/launched.csv

echo "$HEADER" > /tmp/pipeline/phase3.csv
cortellis --json drugs search --company <ID> --phase C3 --hits 50 | python3 $RECIPES/ci_drugs_to_csv.py >> /tmp/pipeline/phase3.csv
python3 $RECIPES/manifest.py write /tmp/pipeline phase3 $? /tmp/pipeline/phase3.csv

echo "$HEADER" > /tmp/pipeline/phase2.csv
cortellis --json drugs search --company <ID> --phase C2 --hits 50 | python3 $RECIPES/ci_drugs_to_csv.py >> /tmp/pipeline/phase2.csv
python3 $RECIPES/manifest.py write /tmp/pipeline phase2 $? /tmp/pipeline/phase2.csv

echo "$HEADER" > /tmp/pipeline/phase1_ci.csv
cortellis --json drugs search --company <ID> --phase C1 --hits 50 | python3 $RECIPES/ci_drugs_to_csv.py >> /tmp/pipeline/phase1_ci.csv
python3 $RECIPES/manifest.py write /tmp/pipeline phase1_ci $? /tmp/pipeline/phase1_ci.csv

echo "$HEADER" > /tmp/pipeline/discovery_ci.csv
cortellis --json drugs search --company <ID> --phase DR --hits 50 | python3 $RECIPES/ci_drugs_to_csv.py >> /tmp/pipeline/discovery_ci.csv
python3 $RECIPES/manifest.py write /tmp/pipeline discovery_ci $? /tmp/pipeline/discovery_ci.csv
```

### Step 4a → Save SI Phase I to CSV
```bash
echo "$HEADER" > /tmp/pipeline/phase1_si.csv
cortellis --json drug-design search-drugs --query "organizationsOriginator:\"<COMPANY>\" AND developmentIsActive:Yes AND phaseHighest:\"Phase I\"" --hits 50 | python3 $RECIPES/si_drugs_to_csv.py >> /tmp/pipeline/phase1_si.csv
python3 $RECIPES/manifest.py write /tmp/pipeline phase1_si $? /tmp/pipeline/phase1_si.csv
```

### Step 4b → Save SI Preclinical to CSV
```bash
echo "$HEADER" > /tmp/pipeline/preclinical_si.csv
cortellis --json drug-design search-drugs --query "organizationsOriginator:\"<COMPANY>\" AND developmentIsActive:Yes AND phaseHighest:\"Preclinical\"" --hits 50 | python3 $RECIPES/si_drugs_to_csv.py >> /tmp/pipeline/preclinical_si.csv
python3 $RECIPES/manifest.py write /tmp/pipeline preclinical_si $? /tmp/pipeline/preclinical_si.csv
```

### Merge Phase 1 (CI + SI)
```bash
python3 $RECIPES/merge_dedup.py /tmp/pipeline/phase1_ci.csv /tmp/pipeline/phase1_si.csv > /tmp/pipeline/phase1_merged.csv
python3 $RECIPES/manifest.py write /tmp/pipeline merge_phase1 $? /tmp/pipeline/phase1_merged.csv
```

### Merge Preclinical (CI Discovery + SI Preclinical)
```bash
python3 $RECIPES/merge_dedup.py /tmp/pipeline/discovery_ci.csv /tmp/pipeline/preclinical_si.csv > /tmp/pipeline/preclinical_merged.csv
python3 $RECIPES/manifest.py write /tmp/pipeline merge_preclinical $? /tmp/pipeline/preclinical_merged.csv
```

### Step 5 → Deals to CSV
```bash
cortellis --json deals search --principal "<COMPANY>" --hits 20 --sort-by "-dealDateStart" | python3 $RECIPES/deals_to_csv.py > /tmp/pipeline/deals.csv
python3 $RECIPES/manifest.py write /tmp/pipeline deals $? /tmp/pipeline/deals.csv
```

### Step 6 → Trials to CSV
```bash
cortellis --json trials search --sponsor "<COMPANY>" --recruitment-status Recruiting --hits 50 --sort-by "-trialDateStart" | python3 $RECIPES/trials_to_csv.py > /tmp/pipeline/trials.csv 2>/tmp/pipeline/trials_meta.txt
python3 $RECIPES/manifest.py write /tmp/pipeline trials $? /tmp/pipeline/trials.csv
```
Note: `trials_to_csv.py` prints `totalResults=N` to stderr. Capture it to pass as the 5th argument to `report_generator.py`.

### Count therapeutic focus across ALL phases
```bash
cat /tmp/pipeline/launched.csv /tmp/pipeline/phase3.csv /tmp/pipeline/phase2.csv /tmp/pipeline/phase1_merged.csv /tmp/pipeline/preclinical_merged.csv | python3 $RECIPES/count_by_field.py indication
```

### Step 4c → Resolve per-indication phase mapping
```bash
IDS=$(python3 $RECIPES/resolve_phase_indications.py find /tmp/pipeline)
cortellis --json drugs records $IDS > /tmp/pipeline/overlap_records.json
python3 $RECIPES/resolve_phase_indications.py rewrite /tmp/pipeline
python3 $RECIPES/manifest.py write /tmp/pipeline resolve_indications $?
```

### Step 7 → Catch missing drugs
```bash
python3 $RECIPES/catch_missing_drugs.py <COMPANY_ID> /tmp/pipeline
python3 $RECIPES/manifest.py write /tmp/pipeline catch_missing $? /tmp/pipeline/other.csv
```
Note: The script reads from the correct filenames (`phase1_ci.csv`, `discovery_ci.csv`, `phase1_merged.csv`, `preclinical_merged.csv`), logs API errors to stderr, and writes attrited drugs (discontinued/suspended/withdrawn) to `attrition.csv` for the Attrition Summary section.

### Validate pipeline integrity
```bash
python3 $RECIPES/manifest.py validate /tmp/pipeline
```
If validation fails (exit code 1), report the failures to the user instead of generating the report.

### Generate formatted report with ASCII charts
```bash
TOTAL_TRIALS=$(grep -oP 'totalResults=\K\d+' /tmp/pipeline/trials_meta.txt 2>/dev/null)
python3 $RECIPES/report_generator.py /tmp/pipeline "<COMPANY_NAME>" "<COMPANY_ID>" "<ACTIVE_DRUGS>" "$TOTAL_TRIALS"
```
Produces: ASCII bar charts (pipeline distribution + therapeutic focus), summary table with truncation warnings (at 150-drug pagination limit), full drug tables per phase, attrition summary, deals table, and trials summary. The `TOTAL_TRIALS` argument (extracted from Step 6's stderr) uses the API's `@totalResults` for accurate trial counts.

### Append run summary
```bash
python3 $RECIPES/manifest.py report /tmp/pipeline
```

### Save snapshot for future comparison
```bash
python3 $RECIPES/snapshot_pipeline.py /tmp/pipeline <COMPANY_ID>
```
Saves all CSVs and manifest to `~/.cortellis/pipeline_snapshots/<company_id>/<date>/` for future diff comparisons.

### Compare against previous run (optional)
```bash
python3 $RECIPES/diff_pipeline.py /tmp/pipeline <COMPANY_ID>
```
If a previous snapshot exists, outputs a "Pipeline Changes" section showing phase advances, regressions, new additions, and removals since the last run. Skip on first run.

### Competitive context (optional, adds ~9 API calls)
```bash
python3 $RECIPES/competitive_context.py /tmp/pipeline "<COMPANY_NAME>"
```
Queries drug counts for the company's top 3 indications across Launched, Phase 3, and Phase 2. Shows competitive density and provides navigation hints to `/landscape` and `/company-peers` skills.

### Pagination for large companies (when a phase hits 50 limit)
```bash
# Use fetch_phase.sh instead of direct cortellis call — auto-paginates with rate limit protection
bash $RECIPES/fetch_phase.sh <COMPANY_ID> L /tmp/pipeline/launched.csv $RECIPES
bash $RECIPES/fetch_phase.sh <COMPANY_ID> C3 /tmp/pipeline/phase3.csv $RECIPES
# etc.
```
Fetches up to 150 drugs per phase (3 pages). Sleeps 1s between pages to avoid rate limits.
