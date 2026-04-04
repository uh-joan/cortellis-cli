---
name: clinical-landscape
description: /clinical-landscape: Clinical Trial Landscape
---

# /clinical-landscape — Clinical Trial Landscape

All clinical trials in an indication: phase distribution, sponsors, enrollment, recruitment status.

## Usage

```
/clinical-landscape obesity
/clinical-landscape "non-small cell lung cancer"
/clinical-landscape MASH
```

## Workflow

### Setup
```bash
RECIPES="cli_anything/cortellis/skills/clinical-landscape/recipes"
LANDSCAPE_RECIPES="cli_anything/cortellis/skills/landscape/recipes"
DIR="/tmp/clinical_landscape"
mkdir -p "$DIR"
```

### Step 1: Resolve indication ID
```bash
RESULT=$(python3 $LANDSCAPE_RECIPES/resolve_indication.py "<INDICATION>")
# Output: indication_id,indication_name
```

### Step 2: Search trials by indication across phases
```bash
cortellis --json trials search --indication "<INDICATION_NAME>" --phase "Phase 3" --hits 50 --sort-by "-trialDateStart" > $DIR/trials_p3.json
cortellis --json trials search --indication "<INDICATION_NAME>" --phase "Phase 2" --hits 50 --sort-by "-trialDateStart" > $DIR/trials_p2.json
cortellis --json trials search --indication "<INDICATION_NAME>" --phase "Phase 1" --hits 50 --sort-by "-trialDateStart" > $DIR/trials_p1.json
```

### Step 3: Search recruiting trials
```bash
cortellis --json trials search --indication "<INDICATION_NAME>" --recruitment-status "Recruiting" --hits 50 --sort-by "-trialDateStart" > $DIR/trials_recruiting.json
```

### Generate report
```bash
python3 $RECIPES/clinical_landscape_report.py $DIR "<INDICATION_NAME>" "<INDICATION_ID>"
```

## Output Rules

- Skip empty sections automatically.
- Only report data from Cortellis results. No training data.
- Give exact numbers. No approximations.
- ALWAYS list ALL items in tables. No truncation.

## Output Format

```
# Clinical Trial Landscape: <Indication>

**Total Trials:** X

## Phase Distribution
(ASCII bar chart)

## Top Sponsors
| Sponsor | Trial Count |

## Actively Recruiting (X trials)
| Trial | Phase | Sponsor | Enrollment | Start Date |

## Phase 3 Trials (X total)
| Trial | Sponsor | Status | Enrollment | Start Date |

## Phase 2 Trials (X total)
| Trial | Sponsor | Status | Enrollment | Start Date |

## Phase 1 Trials (X total)
| Trial | Sponsor | Status | Enrollment | Start Date |
```

## Recipes

### Step 1 -> Resolve indication (reuses landscape resolver)
```bash
python3 $LANDSCAPE_RECIPES/resolve_indication.py "<INDICATION>"
```

### Steps 2-3 -> Collect data, then generate report
```bash
python3 $RECIPES/clinical_landscape_report.py $DIR "<INDICATION_NAME>" "<INDICATION_ID>"
```
