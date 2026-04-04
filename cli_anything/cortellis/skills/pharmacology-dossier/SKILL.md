---
name: pharmacology-dossier
description: /pharmacology-dossier: Pharmacology & Drug Design Dossier
---

# /pharmacology-dossier — Pharmacology & Drug Design Dossier

Pharmacology, pharmacokinetics, structure, and preclinical data for a compound from Drug Design (Science Intelligence) APIs.

## Usage

```
/pharmacology-dossier semaglutide
/pharmacology-dossier tirzepatide
/pharmacology-dossier "EGFR inhibitor"
```

## Workflow

### Setup
```bash
RECIPES="cli_anything/cortellis/skills/pharmacology-dossier/recipes"
DRUG_RECIPES="cli_anything/cortellis/skills/drug-profile/recipes"
DIR="/tmp/pharmacology_dossier"
mkdir -p "$DIR"
```

### Step 1: Resolve drug name
```bash
RESULT=$(python3 $DRUG_RECIPES/resolve_drug.py "<DRUG_NAME>")
# Output: drug_id,drug_name,phase,indication_count
```

### Step 2: Search pharmacology data
```bash
cortellis --json drug-design pharmacology --query "<DRUG_NAME>" --hits 20 > $DIR/pharmacology.json
```

### Step 3: Search pharmacokinetics data
```bash
cortellis --json drug-design pharmacokinetics --query "<DRUG_NAME>" --hits 20 > $DIR/pharmacokinetics.json
```

### Step 4: Search Drug Design drug record
```bash
cortellis --json drug-design search-drugs --query "<DRUG_NAME>" --hits 5 > $DIR/si_drugs.json
```

### Step 5: Get structure image (if available)
```bash
cortellis --json drug-design get-drugs <SI_DRUG_ID> > $DIR/si_drug_record.json
```

### Step 6: Search disease briefings (optional)
```bash
cortellis --json drug-design disease-briefings-search --query "<DRUG_NAME>" --hits 3 > $DIR/briefings.json
```
May return 400 for some drugs — write `{}` and continue.

### Generate report
```bash
python3 $RECIPES/pharmacology_report_generator.py $DIR "<DRUG_NAME>"
```

## Output Rules

- Skip empty sections automatically.
- Only report data from Cortellis results. No training data.
- Give exact numbers with units. No approximations.

## Output Format

```
# Pharmacology Dossier: <Drug Name>

## Drug Design Record
| Field | Value |
|-------|-------|
| SI ID | X |
| Phase | X |
| Mechanism | X |

## Pharmacology (X records)
| Compound | Assay | Target | Value | Unit | Species |

## Pharmacokinetics (X records)
| Compound | Parameter | Value | Unit | Route | Species |

## Disease Briefings (if available)
| Briefing | Disease |
```

## Recipes

### Step 1 -> Resolve drug name (reuses drug-profile resolver)
```bash
python3 $DRUG_RECIPES/resolve_drug.py "<DRUG_NAME>"
```

### Steps 2-6 -> Collect data, then generate report
```bash
python3 $RECIPES/pharmacology_report_generator.py $DIR "<DRUG_NAME>"
```
