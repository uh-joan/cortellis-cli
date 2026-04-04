---
name: company-peers
description: /company-peers: Company Peer Benchmarking
---

# /company-peers — Company Peer Benchmarking

Benchmark a company against its peers: pipeline success rate, first-in-class drugs, therapeutic focus, deal activity, and pipeline depth.

## Usage

```
/company-peers "Novo Nordisk"
/company-peers "Eli Lilly"
/company-peers "Pfizer"
/company-peers 18614
```

## Workflow

### Setup
```bash
RECIPES="cli_anything/cortellis/skills/company-peers/recipes"
PIPELINE_RECIPES="cli_anything/cortellis/skills/pipeline/recipes"
DIR="/tmp/company_peers"
mkdir -p "$DIR"
```

### Step 0: Verify API credentials
```bash
python3 $PIPELINE_RECIPES/check_api.py
```
If this fails, do not proceed — the API credentials are invalid or expired.

### Step 1: Resolve company ID (if name given)
```bash
RESULT=$(python3 $PIPELINE_RECIPES/resolve_company.py "<COMPANY>")
# Output: company_id,company_name,active_drugs,method
```
If user provides a numeric ID, skip this step.

### Step 2: Get company analytics record
```bash
cortellis --json company-analytics get-company <COMPANY_ID> > $DIR/company.json
```

### Step 3: Identify peer companies by indication overlap
Extract the top 3 indication IDs from the company record (`Indications.Indication.@id`), then find peers by who has drugs in the same indications:
```bash
python3 $RECIPES/find_peers.py <COMPANY_ID> <IND_ID_1> <IND_ID_2> <IND_ID_3> > $DIR/peers.json
```
The recipe searches Launched, Phase 3, and Phase 2 drugs by indication, extracts originator companies, ranks by overlap frequency.
Returns top 10 peers as JSON with name, drug count, overlap score, and development phases.

### Step 4: Get analytics records for top peers (required for Step 5)
```bash
# For each peer, resolve their company ID and fetch analytics record:
cortellis --json company-analytics search-companies --query "<PEER_NAME>" --hits 1 > $DIR/peer_1_search.json
# Extract ID and fetch full record:
cortellis --json company-analytics get-company <PEER_ID> > $DIR/peer_1.json
```

### Step 5: Pipeline success rate for target + peers
```bash
cortellis --json company-analytics query-companies companyPipelineSuccess --id-list <COMPANY_ID>,<PEER_ID_1>,<PEER_ID_2>,... > $DIR/pipeline_success.json
```

### Step 6: First-in-class drugs for target company
```bash
cortellis --json company-analytics query-companies companyDrugFirstClass --id-list <COMPANY_ID> > $DIR/first_in_class.json
```

### Step 7: Recent deals for target company
```bash
cortellis --json deals search --principal "<COMPANY_NAME>" --hits 15 --sort-by "-dealDateStart" > $DIR/deals.json
```

### Generate report
```bash
python3 $RECIPES/peers_report_generator.py $DIR "<COMPANY_NAME>" <COMPANY_ID>
```

## Output Rules

- Skip empty sections automatically.
- Only report data from Cortellis results. No training data.
- Give exact numbers. No approximations.
- ALWAYS list ALL items in tables. No truncation.

## Methodology

Peers are identified by searching drugs in the company's top 3 indications across Launched, Phase 3, and Phase 2 phases. Companies are ranked by indication overlap (how many of the 3 indications they share) then by drug count. Top 10 are shown. This captures both commercial competitors (Launched) and near-term pipeline threats (Phase 2/3).

## Output Format

```
# Company Peer Benchmarking: <Company Name>

**ID:** X | **Size:** Large | **Country:** X
**Active Drugs:** X | **Patents:** X | **Deals:** X

## Therapeutic Focus
| Indication | Drug Count |
|------------|-----------|

## Peer Companies
| Company | Country | Active Drugs | Deals | Indication Overlap |
|---------|---------|-------------|-------|-------------------|

## Pipeline Success Benchmarking
| Company | Total Drugs | Successful | Success Rate |
|---------|-------------|------------|--------------|
(ASCII bar chart)

## First-in-Class Portfolio
| Drug | Indication | Target | Phase |
|------|-----------|--------|-------|

## Recent Deals
| Deal | Partner | Type | Date |
|------|---------|------|------|

## Next Steps
(navigation hints to /pipeline, /head-to-head for deeper analysis)
```

## Recipes

### Step 1 -> Resolve company name (reuses pipeline resolver)
```bash
python3 $PIPELINE_RECIPES/resolve_company.py "<COMPANY>"
# Output: company_id,company_name,active_drugs,method
```

### Steps 2-7 -> Collect data, then generate report
```bash
python3 $RECIPES/peers_report_generator.py $DIR "<COMPANY_NAME>" <COMPANY_ID>
# Reads: company.json, peers.json, peer_*.json,
#         pipeline_success.json, first_in_class.json, deals.json
# Outputs: formatted markdown with benchmark tables + charts + cross-skill hints
# Skips empty sections automatically
```

### find_peers.py — Drug-based peer identification
```bash
python3 $RECIPES/find_peers.py <COMPANY_ID> <IND_ID_1> <IND_ID_2> <IND_ID_3>
# Searches Launched + Phase 3 + Phase 2 drugs in each indication
# Extracts originators, tracks development phases per company
# Excludes target company, ranks by indication overlap + drug count
# Output: JSON array of top 10 peers with name, drugs, overlap, phases
```

### CSV export (optional)
```bash
python3 $RECIPES/peers_to_csv.py $DIR > peers.csv
# Outputs: one row per company (target + peers) with key metrics
# Columns: company_name, company_id, country, size, active_drugs,
#           patents_owned, deals, success_total, success_count, success_rate
```
