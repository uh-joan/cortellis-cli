---
name: target-profile
description: /target-profile: Deep Biological Target Profile
---

# /target-profile — Deep Biological Target Profile

Everything about a biological target as a drug target: biology, disease associations, genetic evidence, drug pipeline, protein interactions, and pharmacology data.

## Usage

```
/target-profile GLP-1
/target-profile EGFR
/target-profile PD-L1
/target-profile "BTK"
/target-profile "KRAS"
```

## Workflow

### Setup
```bash
RECIPES="cli_anything/cortellis/skills/target-profile/recipes"
TARGET_SLUG=$(echo "<TARGET_NAME>" | tr '[:upper:]' '[:lower:]' | tr ' ' '-' | sed "s/'//g")
DIR="raw/targets/$TARGET_SLUG"
mkdir -p "$DIR"
```

### Step 1: Resolve target ID and action name
```bash
RESULT=$(python3 $RECIPES/resolve_target_id.py "<TARGET>")
TARGET_ID=$(echo "$RESULT" | cut -d',' -f1)
TARGET_NAME=$(echo "$RESULT" | cut -d',' -f2)
GENE_SYMBOL=$(echo "$RESULT" | cut -d',' -f3)
ACTION_NAME=$(echo "$RESULT" | cut -d',' -f4-)
# Output: target_id,target_name,gene_symbol,action_name
```

### Step 2: Full target record
```bash
cortellis --json targets records $TARGET_ID > $DIR/record.json
```

### Step 3: Disease-drug associations
```bash
cortellis --json targets condition-drugs $TARGET_ID > $DIR/condition_drugs.json
```

### Step 4: Disease-gene associations
```bash
cortellis --json targets condition-genes $TARGET_ID > $DIR/condition_genes.json
```

### Step 5: Protein-protein interactions
```bash
cortellis --json targets interactions $TARGET_ID > $DIR/interactions.json
```

### Step 6: Drug pipeline by mechanism (CI domain)
```bash
bash $RECIPES/fetch_drugs_by_action.sh "$ACTION_NAME" $DIR/drugs_pipeline.json
```
If ACTION_NAME is empty, skip this step. Fetches ALL drugs (paginated, no cap).

### Step 7: Pharmacology data (Drug Design / SI)
```bash
cortellis --json drug-design pharmacology --query "$GENE_SYMBOL" --hits 50 > $DIR/pharmacology.json
```
Note: Use plain gene symbol as query, NOT `targetSynonyms:` prefix (not supported by pharmacology endpoint).

### Step 7b: IP landscape (patents)
```bash
cortellis --json targets patents $TARGET_ID > $DIR/patents.json
```

### Step 7c: Literature references
```bash
cortellis --json targets references $TARGET_ID > $DIR/references.json
```

### Step 8: Disease briefings (optional, may return 400 for some targets)
```bash
cortellis --json drug-design disease-briefings-search --query "$TARGET_NAME" --hits 3 > $DIR/briefings.json
```
If this fails, write `{}` to briefings.json and continue — the report generator skips empty sections.

### Step 8a: Recent publications
```bash
cortellis --json literature search --query "$GENE_SYMBOL" --hits 10 --sort-by "-date" > $DIR/literature.json
```
Fetches recent publications by gene symbol. May return 0 results — skip section if empty.

### Step 8b: UniProt + AlphaFold (external)
```bash
python3 $RECIPES/enrich_target_uniprot.py $DIR "$GENE_SYMBOL"
```
Fetches from UniProt REST API and AlphaFold EBI API (both public, no auth). Gene symbol search is exact-match with Swiss-Prot reviewed entries preferred.
Writes: `uniprot.json`, `alphafold.json`, `uniprot_summary.md`. Covers: protein size/MW, subcellular location, subunit structure, TM regions and domains, disease associations, PDB cross-refs, AlphaFold v6 structure link.

### Step 8c: Open Targets (external)
```bash
python3 $RECIPES/enrich_target_opentargets.py $DIR "$GENE_SYMBOL"
```
Fetches from Open Targets Platform GraphQL API (public, no auth). Resolves gene symbol → Ensembl ID automatically.
Writes: `opentargets.json`, `opentargets_summary.md`. Covers: tractability (SM/antibody/PROTAC), disease associations with evidence scores (0–1), gnomAD genetic constraint (LoF O/E), safety liabilities, known drugs cross-check.

### Step 8d: ChEMBL binding affinity (external)
```bash
python3 $RECIPES/enrich_target_chembl.py $DIR "$GENE_SYMBOL"
```
Fetches binding affinity data from public ChEMBL REST API (no auth). Searches by gene symbol via component synonyms (more reliable than name search).
Writes: `chembl_target.json`, `chembl_target_summary.md`. Covers top compounds by pChEMBL value (IC50, Ki, EC50).

### Step 8e: CPIC pharmacogenomics (external)
```bash
python3 $RECIPES/enrich_target_cpic.py $DIR "$GENE_SYMBOL"
```
Fetches gene-drug pairs, guidelines, and star alleles from CPIC PostgREST API (no auth).
Writes: `cpic_gene.json`, `cpic_gene_summary.md`. Most relevant for PK genes (CYP2C9, CYP2D6, VKORC1, etc.). Skips gracefully for non-PGx targets.

### Step 9: Generate report
```bash
python3 $RECIPES/target_report_generator.py $DIR
```

### Step 10: Compile to wiki
```bash
python3 $RECIPES/compile_target.py $DIR "$TARGET_NAME"
```
Always run this after Step 9. Writes `wiki/targets/<slug>.md` and updates `wiki/INDEX.md`.

## Execution Rules

- Once the final report has been delivered to the user, **do not respond to background task completion notifications**. Discard them silently — they are late arrivals for steps already processed.

## Output Rules

- Skip empty sections automatically.
- Only report data from Cortellis results. No training data.
- Give exact numbers. No approximations.
- **ALWAYS list ALL items in every table. No truncation.** This applies to disease associations, genetic evidence, drug pipeline, protein interactions, and pharmacology — every row must appear.

## Output Format

```
# Target Profile: <Target Name> (<Gene Symbol>)

**ID:** X | **Organism:** Human | **Family:** X
**Synonyms:** X, Y, Z

## Biology
| Field | Value |
|-------|-------|
| Function | ... |
| Subcellular Location | ... |
| Protein Family | ... |

## Disease Associations (X diseases)
| Disease | Drugs | Top Drug (Phase) |
|---------|-------|-------------------|

## Genetic Evidence (X associations)
| Disease | Gene | Evidence |
|---------|------|----------|

## Drug Pipeline (X total)
(ASCII bar chart by phase)

| Drug | Company | Phase | Indications |
|------|---------|-------|-------------|

## Protein Interactions (X)
| Partner | Interaction Type |
|---------|-----------------|

## Pharmacology (X records)
| Compound | Assay | Value | Unit |
|----------|-------|-------|------|

## Disease Briefings (if available)
```

## Recipes

### resolve_target_id.py — Target name to ID + action name
```bash
python3 $RECIPES/resolve_target_id.py "<TARGET>"
# Output: target_id,target_name,gene_symbol,action_name
# 4-strategy resolution: synonym table → targets search → NER → normalized retry
# Handles: GLP-1, GLP1R, EGFR, PD-L1, HER2, BRAF, BTK, JAK, KRAS, etc.
```

### target_report_generator.py — Formatted report from JSON files
```bash
python3 $RECIPES/target_report_generator.py $DIR
# Reads: record.json, condition_drugs.json, condition_genes.json,
#         interactions.json, drugs_pipeline.json, pharmacology.json, briefings.json
# Outputs: formatted markdown with ASCII pipeline chart, tables
# Skips empty sections automatically
```

### compile_target.py — Compile target profile to wiki (optional)
```bash
python3 $RECIPES/compile_target.py $DIR "$TARGET_NAME" [--wiki-dir DIR]
```
Produces wiki/targets/<slug>.md with frontmatter (gene_symbol, family, organism, disease_count, drug_count) and sections: Biology, Disease Associations, Drug Pipeline, Protein Interactions, Pharmacology, Data Sources. Updates wiki/INDEX.md. Uses [[wikilinks]] for drugs and companies.
