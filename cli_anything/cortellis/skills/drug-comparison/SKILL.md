---
name: drug-comparison
description: /drug-comparison: Side-by-Side Drug Comparison
---

# /drug-comparison — Side-by-Side Drug Comparison

Compare two or more drugs head-to-head: phase, mechanism, indications, SWOT, financials, trials, deals, and competitive context.

## Usage

```
/drug-comparison tirzepatide vs semaglutide
/drug-comparison "durvalumab" "pembrolizumab"
/drug-comparison ozempic wegovy mounjaro
```

## Workflow

### Setup
```bash
RECIPES="cli_anything/cortellis/skills/drug-comparison/recipes"
DRUG_RECIPES="cli_anything/cortellis/skills/drug-profile/recipes"
DIR="/tmp/drug_comparison"
mkdir -p "$DIR"
```

### Step 1: Parse drug names from input
Extract drug names from the user input. Split on "vs", "versus", commas, or spaces. Minimum 2 drugs required.

### Step 2: Resolve each drug ID
For each drug name, reuse the drug-profile resolver:
```bash
RESULT=$(python3 $DRUG_RECIPES/resolve_drug.py "<DRUG_NAME>")
# Output: drug_id,drug_name,phase,indication_count
```
If user provides a numeric ID, skip resolution for that drug.

### Step 3: Fetch full record for each drug
```bash
cortellis --json drugs get <DRUG_ID_1> --category report --include-sources > $DIR/record_1.json
cortellis --json drugs get <DRUG_ID_2> --category report --include-sources > $DIR/record_2.json
```

### Step 4: SWOT analysis for each drug (Cortellis editorial — may be outdated)
```bash
cortellis --json drugs swots <DRUG_ID_1> > $DIR/swot_1.json
cortellis --json drugs swots <DRUG_ID_2> > $DIR/swot_2.json
```
May be empty for niche/early-stage drugs -- skip section if empty for both.
For comprehensive per-drug SWOTs, use `/drug-swot` on each drug separately.

### Step 5: Financial data for each drug
```bash
cortellis --json drugs financials <DRUG_ID_1> > $DIR/financials_1.json
cortellis --json drugs financials <DRUG_ID_2> > $DIR/financials_2.json
```
May be empty for non-launched drugs -- skip section if empty for both.

### Step 6: Development history for each drug
```bash
cortellis --json drugs history <DRUG_ID_1> > $DIR/history_1.json
cortellis --json drugs history <DRUG_ID_2> > $DIR/history_2.json
```

### Step 7: Active trials for each drug
```bash
cortellis --json trials search --query "trialInterventionsPrimaryAloneNameDisplay:<DRUG_NAME_1>" --hits 10 --sort-by "-trialDateStart" > $DIR/trials_1.json
cortellis --json trials search --query "trialInterventionsPrimaryAloneNameDisplay:<DRUG_NAME_2>" --hits 10 --sort-by "-trialDateStart" > $DIR/trials_2.json
```

### Step 8: Recent deals for each drug
```bash
cortellis --json deals search --drug "<DRUG_NAME_1>" --hits 10 --sort-by "-dealDateStart" > $DIR/deals_1.json
cortellis --json deals search --drug "<DRUG_NAME_2>" --hits 10 --sort-by "-dealDateStart" > $DIR/deals_2.json
```

### Generate report
```bash
python3 $RECIPES/comparison_report_generator.py $DIR
```

## Output Rules

- **Skip empty sections.** If SWOT/financials are empty for BOTH drugs, omit the section entirely.
- Only report data from Cortellis results. No training data.
- Give exact numbers. No approximations.
- ALWAYS list ALL items in tables. No truncation.
- Present data side-by-side wherever possible for easy comparison.
- Show "Showing X of Y" when trials or deals are truncated.
- Include Data Coverage footer with data availability per drug.

## Output Format

```
# Drug Comparison: <Drug A> vs <Drug B>

## At a Glance
| Field | <Drug A> | <Drug B> |
|-------|----------|----------|
| Phase | X | Y |
| Originator | X | Y |
| Indications | N | M |
| Mechanism | X | Y |
| Technology | X | Y |
| Brands | X | Y |

## Indications
| Indication | <Drug A> | <Drug B> |
|------------|----------|----------|
| Obesity | Phase 3 | Launched |
| Diabetes | Launched | Launched |

## Development Timeline
### <Drug A>
(ASCII timeline)
### <Drug B>
(ASCII timeline)

## SWOT Comparison (if available for either)
| Dimension | <Drug A> | <Drug B> |
|-----------|----------|----------|
| Strengths | ... | ... |
| Weaknesses | ... | ... |
| Opportunities | ... | ... |
| Threats | ... | ... |

## Financial Comparison (if available for either)
| Metric | <Drug A> | <Drug B> |
|--------|----------|----------|
| Commentary | ... | ... |

## Clinical Trials
### <Drug A> (N trials)
| Trial | Phase | Status | Enrollment |
### <Drug B> (M trials)
| Trial | Phase | Status | Enrollment |

## Deals
### <Drug A> (N deals)
| Deal | Partner | Type | Date |
### <Drug B> (M deals)
| Deal | Partner | Type | Date |

## Verdict
Key differentiators summary.
```

## Recipes

### Step 2 -> Resolve drug names (reuses drug-profile resolver)
```bash
python3 $DRUG_RECIPES/resolve_drug.py "<DRUG_NAME>"
# Output: drug_id,drug_name,phase,indication_count
```

### Steps 3-8 -> Collect data, then generate comparison report
```bash
python3 $RECIPES/comparison_report_generator.py $DIR
# Reads: record_N.json, swot_N.json, financials_N.json, history_N.json,
#         trials_N.json, deals_N.json (for N = 1, 2, 3, ...)
# Outputs: side-by-side markdown comparison with tables
# Supports 2+ drugs — scales columns dynamically
# Skips empty sections automatically
```

### CSV export (optional)
```bash
python3 $RECIPES/drugs_comparison_to_csv.py $DIR > comparison.csv
# Outputs: one row per drug with key comparison fields
# Columns: drug_name, drug_id, phase, originator, indications, mechanisms,
#           technologies, brands, therapy_areas, trial_count, deal_count
```
