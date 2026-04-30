---
name: pipeline
description: Use when a user asks about a specific company's drug pipeline, R&D portfolio, preclinical or clinical programs, or what a pharma or biotech company is working on. Triggers on company names (Novo Nordisk, Eli Lilly, Pfizer, Zealand Pharma) or company IDs.
---

# /pipeline — Company Pipeline Analysis

Analyze a company's full drug development pipeline, merging CI and Drug Design (SI) data for complete early-stage coverage.

## Usage

```
/pipeline "Novo Nordisk"
/pipeline "Eli Lilly"
/pipeline 18614
```

## Failure Modes to Avoid

**Skipping SI fetch because it "usually returns empty":**
Wrong — skips Steps 4a/4b because the Learned Optimization says SI is sparse → misses early-stage biotech compounds that only appear in SI.
Correct — always runs Steps 4a/4b; treats empty result as expected rather than skipping the call.

**Announcing completion before all phases are listed:**
Wrong — delivers a summary after listing Launched and Phase 3, omits Phase 1 and Preclinical sections.
Correct — all phases (Launched → Phase 3 → Phase 2 → Phase 1 merged → Preclinical merged) appear before the report is considered done.

**Approximating drug counts:**
```
# Wrong:
Total drugs (CI): ~40 (Launched: ~8, Phase 3: ~6, Phase 2: ~10, Phase 1: ~8, Discovery: ~8)

# Correct — use exact @totalResults from each API response:
Total drugs (CI): 43 (Launched: 8, Phase 3: 6, Phase 2: 11, Phase 1: 9, Discovery: 9)
```

## Workflow

<!-- Model routing
  haiku  — Step 1 (resolve company ID — lightweight classification)
  sonnet — Steps 2–8 (fetch CI/SI pipeline, deals, trials — script execution)
  opus   — Steps 8a, report generation, wiki compile (synthesis + external enrichment)
-->

### Step 1: Resolve company ID (if name given) <!-- model: haiku -->
```bash
RESULT=$(python3 $RECIPES/resolve_company.py "<COMPANY>")
# Output: company_id,company_name,active_drugs,method
```
The recipe handles ALL resolution internally — do NOT call NER or ontology separately.
Strategies (in order): NER match → ontology depth-1 → broad search → suffix search.

Tested on 50 major pharma companies — 98% success rate.

### Step 2: Get company profile
```bash
cortellis --json companies get <COMPANY_ID>
```

### Step 3: CI pipeline — Drugs by phase (paginated, fetches all)
Use `fetch_phase.sh` — auto-paginates with rate limit protection:
```bash
bash $RECIPES/fetch_phase.sh <COMPANY_ID> L  $DIR/launched.csv     $RECIPES
bash $RECIPES/fetch_phase.sh <COMPANY_ID> C3 $DIR/phase3.csv       $RECIPES
bash $RECIPES/fetch_phase.sh <COMPANY_ID> C2 $DIR/phase2.csv       $RECIPES
bash $RECIPES/fetch_phase.sh <COMPANY_ID> C1 $DIR/phase1_ci.csv    $RECIPES
bash $RECIPES/fetch_phase.sh <COMPANY_ID> DR $DIR/discovery_ci.csv $RECIPES
```

### Step 4a: Drug Design (SI) — Phase I compounds (paginated, up to 150)
```bash
bash $RECIPES/fetch_phase_si.sh \
  "organizationsOriginator:\"<COMPANY>\" AND developmentIsActive:Yes AND phaseHighest:\"Phase I\"" \
  $DIR/phase1_si.csv $RECIPES
```

### Step 4b: Drug Design (SI) — Preclinical compounds (paginated, up to 150)
```bash
bash $RECIPES/fetch_phase_si.sh \
  "organizationsOriginator:\"<COMPANY>\" AND developmentIsActive:Yes AND phaseHighest:\"Preclinical\"" \
  $DIR/preclinical_si.csv $RECIPES
```
Note: "Biological Testing" exists as a phase but has 0 active compounds across major pharma. Skip unless results are needed.

### Step 4c: Resolve per-indication phase mapping (1 batch API call)
```bash
# Find overlapping drug IDs
IDS=$(python3 $RECIPES/resolve_phase_indications.py find $DIR)

# Batch fetch full records (1 API call, up to 50 IDs)
cortellis --json drugs records $IDS > $DIR/overlap_records.json

# Rewrite CSVs with phase-specific indications
python3 $RECIPES/resolve_phase_indications.py rewrite $DIR
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

## Execution Rules

- **Announce each step before running it.** Example: "Step 1: Resolving company ID for Eli Lilly…", "Step 3: Fetching CI pipeline (Launched)…", "Step 4a: Fetching SI Phase I compounds…". Keep announcements to one line.
- Once the final report has been delivered to the user, **do not respond to background task completion notifications**. Discard them silently — they are late arrivals for steps already processed.

## Output Rules

- **ALWAYS list ALL drugs in EVERY table.** NEVER truncate with "+ N others", "+ more", "and others", or similar. Every single drug must have its own row — list every row in every CSV.
- Give exact counts from the API `@totalResults` field.
- Never approximate. Never say "~8" or "6-7".
- Do not add drugs from training data. Only report what the CLI returned.

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
```

## Recipes (CSV-based data pipeline)

All data flows through CSV files in `raw/pipeline/<slug>/`. Use the recipe scripts in `recipes/` — do NOT write your own parsers.

**CSV columns:** `name,id,phase,indication,mechanism,company,source`

### Setup
```bash
RECIPES="cli_anything/cortellis/skills/pipeline/recipes"
COMPANY_SLUG=$(echo "<COMPANY_NAME>" | tr '[:upper:]' '[:lower:]' | tr ' ' '-' | sed "s/'//g")
DIR="raw/pipeline/$COMPANY_SLUG"
mkdir -p "$DIR"
HEADER="name,id,phase,indication,mechanism,company,source"
```

### Step 3 → Save each CI phase to CSV (paginated, fetches all)
```bash
bash $RECIPES/fetch_phase.sh <ID> L    $DIR/launched.csv    $RECIPES
bash $RECIPES/fetch_phase.sh <ID> C3   $DIR/phase3.csv      $RECIPES
bash $RECIPES/fetch_phase.sh <ID> C2   $DIR/phase2.csv      $RECIPES
bash $RECIPES/fetch_phase.sh <ID> C1   $DIR/phase1_ci.csv   $RECIPES
bash $RECIPES/fetch_phase.sh <ID> DR   $DIR/discovery_ci.csv $RECIPES
```

### Step 4a → Save SI Phase I to CSV (paginated, up to 150)
```bash
bash $RECIPES/fetch_phase_si.sh \
  "organizationsOriginator:\"<COMPANY>\" AND developmentIsActive:Yes AND phaseHighest:\"Phase I\"" \
  $DIR/phase1_si.csv $RECIPES
```

### Step 4b → Save SI Preclinical to CSV (paginated, up to 150)
```bash
bash $RECIPES/fetch_phase_si.sh \
  "organizationsOriginator:\"<COMPANY>\" AND developmentIsActive:Yes AND phaseHighest:\"Preclinical\"" \
  $DIR/preclinical_si.csv $RECIPES
```

### Merge Phase 1 (CI + SI)
```bash
python3 $RECIPES/merge_dedup.py $DIR/phase1_ci.csv $DIR/phase1_si.csv > $DIR/phase1_merged.csv
```

### Merge Preclinical (CI Discovery + SI Preclinical)
```bash
python3 $RECIPES/merge_dedup.py $DIR/discovery_ci.csv $DIR/preclinical_si.csv > $DIR/preclinical_merged.csv
```

### Step 5 → Deals to CSV
```bash
cortellis --json deals search --principal "<COMPANY>" --hits 20 --sort-by "-dealDateStart" | python3 $RECIPES/deals_to_csv.py > $DIR/deals.csv
```

### Step 6 → Trials to CSV
```bash
cortellis --json trials search --sponsor "<COMPANY>" --recruitment-status Recruiting --hits 50 --sort-by "-trialDateStart" | python3 $RECIPES/trials_to_csv.py > $DIR/trials.csv
```

### Count therapeutic focus across ALL phases
```bash
cat $DIR/launched.csv $DIR/phase3.csv $DIR/phase2.csv $DIR/phase1_merged.csv $DIR/preclinical_merged.csv | python3 $RECIPES/count_by_field.py indication
```

### Step 4c → Resolve per-indication phase mapping
```bash
IDS=$(python3 $RECIPES/resolve_phase_indications.py find $DIR)
cortellis --json drugs records $IDS > $DIR/overlap_records.json
python3 $RECIPES/resolve_phase_indications.py rewrite $DIR
```

### Generate formatted report with ASCII charts
```bash
python3 $RECIPES/report_generator.py $DIR "<COMPANY_NAME>" "<COMPANY_ID>" "<ACTIVE_DRUGS>"
```
Produces: ASCII bar charts (pipeline distribution + therapeutic focus), summary table with truncation warnings, full drug tables per phase, deals table, and trials summary.

### Step 8a: External enrichment — Open Targets + bioRxiv (optional)
```bash
python3 $RECIPES/enrich_pipeline_external.py $DIR "<COMPANY_NAME>"
```
Fetches Open Targets tractability + genetic constraint for top pipeline mechanisms. Searches bioRxiv/medRxiv for recent preprints. Writes `opentargets_pipeline.md` and `biorxiv_pipeline.md` to the pipeline dir (embedded by compile_pipeline.py).

### Compile pipeline to wiki (Step 8 — optional)
```bash
python3 $RECIPES/compile_pipeline.py $DIR "<COMPANY_NAME>" --wiki-dir .
```
Upserts wiki/companies/<slug>.md with pipeline data.
Note: `--wiki-dir .` is required — the script uses the working directory to locate
the wiki. Always run from the project root (e.g. `cortellis-cli/`). Preserves existing landscape CPI data if the article was previously compiled by compile_dossier. Updates wiki/INDEX.md.

### Post-Run Review (run after report is delivered)
```bash
python3 $RECIPES/../post_run_reviewer.py pipeline $DIR "<COMPANY_NAME>"
```
Read the manifest output above. If you see a clear pattern worth encoding (e.g. an
optional enrichment step that consistently returns empty for certain company types),
update the `## Learned Optimizations` section below with a targeted patch. Only add
an optimization if it would generalize to future runs — not for one-off anomalies.

## Learned Optimizations
<!-- Auto-updated by post-run review. Confirmed across real runs: 14 companies including Pfizer, Amgen, Novo Nordisk, Zealand Pharma, Hanmi, Metsera, Structure Therapeutics, and others. -->

- **`phase1_si.csv` + `preclinical_si.csv` consistently return empty headers (50B) across all 14 tested companies** — SI (Springer Intelligence) compound data appears inaccessible or not covered under current subscription. These steps add 2 API calls with zero return. Treat as best-effort: fetch, but do not wait or retry if empty. The CI pipeline (phase1_ci, discovery_ci) is the reliable data source.
- **CI pipeline data dominates for established companies** — launched.csv, phase2.csv, phase3.csv are well-populated for large pharma. SI adds value only for early-stage biotechs not yet indexed in Cortellis CI.
