---
name: combination-landscape
description: /combination-landscape: Combination Therapy Landscape
---

# /combination-landscape — Combination Therapy Landscape

Combination therapies in an indication: what's being combined with what, by phase and company.

## Usage

```
/combination-landscape "non-small cell lung cancer"
/combination-landscape obesity
/combination-landscape MASH
```

## Workflow

### Setup
```bash
RECIPES="cli_anything/cortellis/skills/combination-landscape/recipes"
DIR="/tmp/combination_landscape"
mkdir -p "$DIR"
```

### Step 1: Resolve indication
```bash
# Resolve indication (inlined — no landscape dependency)
IND_RESULT=$(cortellis --json ner match "<INDICATION>")
IND_ID=$(echo "$IND_RESULT" | python3 -c "
import json,sys
d=json.load(sys.stdin)
entities=d.get('NamedEntityRecognition',{}).get('Entities',{}).get('Entity',[])
if isinstance(entities,dict): entities=[entities]
for e in entities:
    if e.get('@type') in ('Indication','Condition'):
        print(e.get('@id','')); break
" 2>/dev/null)
IND_NAME=$(echo "$IND_RESULT" | python3 -c "
import json,sys
d=json.load(sys.stdin)
entities=d.get('NamedEntityRecognition',{}).get('Entities',{}).get('Entity',[])
if isinstance(entities,dict): entities=[entities]
for e in entities:
    if e.get('@type') in ('Indication','Condition'):
        print(e.get('@name','')); break
" 2>/dev/null)
# Fallback if NER fails:
# cortellis --json ontology search --query "<INDICATION>" --category indication --hits 3
```

### Step 2 & 3: Search combination drugs and trials (run in parallel)

**Drug search — two strategies, paginated, merged:**

Write an inline Python script that:
1. Runs both strategies with pagination (50 per page, up to 10 pages each):
   - Strategy 1 (name-based): `cortellis --json drugs search --indication <IND_ID> --query "drugNameDisplay:+" --hits 50 --page <N>`
   - Strategy 2 (technology-based): `cortellis --json drugs search --indication <IND_ID> --technology "Co-formulation" --hits 50 --page <N>`
2. Deduplicates results by drug `@id`
3. Writes merged output to `$DIR/combos.json`
4. Writes `$DIR/combos.meta.json` with:
   ```json
   {
     "strategy1_total": <int>,
     "strategy2_total": <int>,
     "merged_unique": <int>,
     "search_strategies_used": "name-based (+), technology-based (Co-formulation)"
   }
   ```

**Trial search — two strategies, paginated, merged:**

Two complementary title searches capture different combination patterns:
- Strategy 1: `--title "combination"` — catches trials named "X in Combination With Y" (3110 for NSCLC)
- Strategy 2: `--title "plus"` — catches trials named "X Plus Y" that may NOT mention "combination" (827 for NSCLC)

Both paginate (50/page, up to 10 pages each). Merge and deduplicate by trial `@Id`. Write to `$DIR/combo_trials.json`.

The `InterventionsPrimaryDisplay.Intervention` field in trial records contains the structured regimen (e.g., "pembrolizumab plus docetaxel"). Extract this for the report's Components column on trials.

**Run both searches in parallel:**
```bash
python3 - <<'EOF'
# inline drug pagination + merge script
EOF
&

# paginated trial search loop
for page in $(seq 1 10); do ...done
wait
```

### Generate report
```bash
python3 $RECIPES/combination_report.py $DIR "$IND_NAME" "$IND_ID"
```

## Output Rules

- Skip empty sections automatically.
- Only report data from Cortellis results. No training data.
- Give exact numbers. No approximations.
- Show "Showing X of Y" when results are truncated.
- Drug searches are paginated (up to 500 per strategy).
- Trial searches are paginated (up to 500).

## Precision Notes
- **Drug search** uses name-based ("+" in name) and technology-based ("Co-formulation") heuristics — captures branded combinations and co-formulations
- **Trial search** uses dual title strategy ("combination" + "plus") — captures regimen-based combinations (e.g., "pembrolizumab plus docetaxel") that the drug search misses
- The `InterventionsPrimaryDisplay` field in trial records provides structured combination components
- Drug search may miss investigational regimens administered as separate agents; trial search compensates for this gap
- Trial title matching may include some false positives; cross-reference with `/clinical-landscape` for enrollment-level detail

## Output Format

```
# Combination Landscape: <Indication>

## Combination Drugs (X total)
| Drug | Components | Company | Phase | Mechanism |

## Combination Trials (X total)
| Trial | Phase | Sponsor | Status | Enrollment |

## Top Companies in Combinations
| Company | Combinations |
```

## Recipes

### Steps 1-3 -> Collect data, then generate report
```bash
python3 $RECIPES/combination_report.py $DIR "$IND_NAME" "$IND_ID"
```
