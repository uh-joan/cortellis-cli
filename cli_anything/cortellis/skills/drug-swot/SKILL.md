---
name: drug-swot
description: /drug-swot: AI-Generated Strategic SWOT Analysis
---

# /drug-swot — AI-Generated Strategic SWOT Analysis

Generate a comprehensive, data-driven SWOT analysis for any drug by synthesizing real-time data from 8 Cortellis domains: drug profile, financials, clinical trials, deals, patents, competitors, regulatory events, and pharmacology. Unlike the static Cortellis editorial SWOTs (often years out of date), this skill produces a fresh analysis grounded in current data.

## Usage

```
/drug-swot tirzepatide
/drug-swot semaglutide
/drug-swot "pembrolizumab"
```

## Why This Exists

Cortellis provides editorial SWOTs (`drugs swots <ID>`) that are often outdated:
- semaglutide diabetes SWOT last updated Nov 2021
- References obsolete competitors (e.g., ITCA-650, abandoned in 2020)
- No integration with current sales data, active trials, or recent deals
- Grouped by therapeutic class, not tailored to the drug's competitive reality

This skill pulls live data from 8 domains and asks the LLM to synthesize a strategic SWOT that reflects the drug's actual position today.

## Workflow

### Setup
```bash
RECIPES="cli_anything/cortellis/skills/drug-swot/recipes"
DRUG_RECIPES="cli_anything/cortellis/skills/drug-profile/recipes"
DIR="/tmp/drug_swot"
mkdir -p "$DIR"
```

### Step 1: Resolve drug ID
```bash
RESULT=$(python3 $DRUG_RECIPES/resolve_drug.py "<DRUG_NAME>")
# Output: drug_id,drug_name,phase,indication_count
```

### Step 2: Drug record (profile, indications, mechanism, brands)
```bash
cortellis --json drugs get <DRUG_ID> --category report --include-sources > $DIR/drug_record.json
```

### Step 3: Financial data (sales actuals and forecasts)
```bash
cortellis --json drugs financials <DRUG_ID> > $DIR/financials.json
```

### Step 4: Development history (milestones, timeline)
```bash
cortellis --json drugs history <DRUG_ID> > $DIR/history.json
```

### Step 5: Active clinical trials
```bash
cortellis --json trials search --query "trialInterventionsPrimaryAloneNameDisplay:<DRUG_NAME>" --hits 50 --sort-by "-trialDateStart" > $DIR/trials.json
```

### Step 6: Recent deals
```bash
cortellis --json deals search --drug "<DRUG_NAME>" --hits 50 --sort-by "-dealDateStart" > $DIR/deals.json
```

### Step 7: Patent landscape
```bash
cortellis --json company-analytics query-drugs drugPatentProductExpiry --id-list <DRUG_ID> > $DIR/patent_expiry.json
cortellis --json drugs search --drug-name "<DRUG_NAME> biosimilar" --hits 10 > $DIR/biosimilars.json
```

### Step 8: Top competitors (same mechanism, launched or Phase 3)
```bash
cortellis --json drugs search --action "<PRIMARY_ACTION>" --phase L --hits 20 > $DIR/competitors_launched.json
cortellis --json drugs search --action "<PRIMARY_ACTION>" --phase C3 --hits 20 > $DIR/competitors_p3.json
```

### Step 9: Cortellis editorial SWOT (as reference input, not final output)
```bash
cortellis --json drugs swots <DRUG_ID> > $DIR/cortellis_swot.json
```

### Generate report
```bash
python3 $RECIPES/swot_data_collector.py $DIR
```

The recipe collects and summarizes data from all files into a structured evidence brief.
The LLM then synthesizes the SWOT from this evidence — NOT from training data.

## SWOT Synthesis Instructions

After running the recipe, you have an evidence brief. Use ONLY this data to generate the SWOT.

### Strengths (Internal, Positive)
Draw from: drug record (mechanism differentiation, formulation advantages), financial data (revenue growth, market position), trial results (efficacy data, head-to-head wins), regulatory approvals, patent protection timeline.

### Weaknesses (Internal, Negative)
Draw from: drug record (safety warnings, black box, contraindications), financial data (pricing pressure, market share loss), trial data (adverse events, discontinuation rates), regulatory issues (REMS, label restrictions), formulation limitations.

### Opportunities (External, Positive)
Draw from: active trials (new indications, line extensions), deals (new partnerships, geographic expansion), competitor failures/withdrawals, unmet need in target indications, patent runway.

### Threats (External, Negative)
Draw from: competitor pipeline (Phase 3 threats, biosimilars), patent expiry timeline, deals (competitor partnerships), pricing/reimbursement pressure, regulatory headwinds.

## Output Rules

- EVERY statement must cite specific data from the evidence brief (trial name, sales figure, patent date, deal partner, etc.)
- NO generic pharma commentary — everything must be specific to this drug
- Include the Cortellis editorial SWOT date to show the contrast
- Flag any area where data was unavailable
- Use exact numbers: "$22.9B in 2025", not "strong sales"
- Compare to competitors by name with specific metrics

## Output Format

```
# Strategic SWOT: <Drug Name>

**Generated:** <today's date> | **Cortellis Editorial SWOT:** <last update date>
**Phase:** <phase> | **Originator:** <company> | **Revenue:** <latest annual>

## Strengths
1. **<Category>**: <Evidence-backed statement> [Source: <data point>]
2. ...

## Weaknesses
1. **<Category>**: <Evidence-backed statement> [Source: <data point>]
2. ...

## Opportunities
1. **<Category>**: <Evidence-backed statement> [Source: <data point>]
2. ...

## Threats
1. **<Category>**: <Evidence-backed statement> [Source: <data point>]
2. ...

## Strategic Position Summary
<2-3 sentence synthesis of the drug's overall competitive position>

## Data Sources
- Drug Record: <drug_id>
- Financial Data: <available/unavailable>
- Trials: <N active>
- Deals: <N recent>
- Patents: <expiry range>
- Competitors: <N launched>, <N Phase 3>
- Cortellis SWOT: <date> (used as reference only)
```

## Recipes

### Steps 1-9 -> Collect data, then generate evidence brief
```bash
python3 $RECIPES/swot_data_collector.py $DIR
# Reads all JSON files, extracts key facts, outputs structured evidence brief
# The LLM uses this brief to synthesize the final SWOT
```
