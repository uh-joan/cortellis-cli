---
name: cortellis-cli
description: Full command reference for the Cortellis pharmaceutical intelligence CLI (17 command groups, 80+ subcommands)
---

# Cortellis CLI Skill

A CLI-Anything skill for querying the Cortellis pharmaceutical intelligence platform.

## What It Does

`cortellis` provides command-line access to Cortellis data across 17 domains:
drugs, companies, deals, clinical trials, regulatory events, conferences, literature,
press releases, ontology, analytics, named entity recognition (NER), company analytics,
deals intelligence, drug design, targets, AI chat, and configuration.

All commands support dual output: human-readable Rich tables (default) or raw JSON (`--json` flag).

## Invocation

```bash
cortellis [--json] <command-group> <subcommand> [options]
```

## Available Commands

### drugs
- `drugs search` — search drugs by phase, indication, action, company, technology, country, etc. Supports `--historic` for historical development status.
- `drugs get <id>` — fetch drug record; `--category` accepts `report`, `swot`, or `financial`
- `drugs records <id> [<id2> ...]` — batch get multiple drug records by ID
- `drugs autocomplete <text>` — typeahead autocomplete suggestions for drug names
- `drugs batch-sources <id> [<id2> ...]` — batch get source documents for multiple drugs
- `drugs ci-matrix` — fetch competitive intelligence matrix for drugs
- `drugs companies-by-taxonomy` — get companies linked to a taxonomy term
- `drugs financials <id>` — get financial data (sales & forecasts) for a drug
- `drugs history <id>` — get development status change history for a drug
- `drugs molfile <id>` — get MOL file (chemical structure) for a drug
- `drugs sources <id>` — get source documents for a drug
- `drugs structure-image <id>` — download structure image for a drug
- `drugs structure-search <smiles>` — search drugs by chemical structure (SMILES)
- `drugs swots <id>` — get SWOT analysis for a drug

### companies
- `companies search` — search by name, country, size, indication, technology
- `companies get <id>` — fetch company record
- `companies records <id> [<id2> ...]` — batch get multiple company records by ID
- `companies sources <id>` — get source documents for a company

### deals
- `deals search` — search by drug, indication, type, status, principal/partner company, date range
- `deals get <id>` — fetch deal record; `--category` accepts `basic` or `expanded`
- `deals records <id> [<id2> ...]` — batch get multiple deal records by ID
- `deals sources <id>` — get source documents for a deal

### trials
- `trials search` — search by indication, phase, status, sponsor, funder type, date range, identifier
- `trials get <id>` — fetch trial record; `--category` accepts `report` or `sites`
- `trials records <id> [<id2> ...]` — batch get multiple trial records by ID
- `trials sources <id>` — get source documents for a clinical trial
- `trials id-mappings` — fetch ID mappings for a trial entity type

### regulations
- `regulations search` — search by region, document category/type, language
- `regulations get <id>` — fetch regulatory document; `--category` accepts `metadata` or `source`
- `regulations cited-by <id>` — get documents that cite a regulatory document
- `regulations cited-documents <id>` — get documents cited by a regulatory document
- `regulations db-rir` — list Regulatory Intelligence Reports hierarchy (Drugs & Biologics)
- `regulations db-rs` — list Regulatory Summaries hierarchy (Drugs & Biologics)
- `regulations grc <id>` — get a specific Global Regulatory Comparison report
- `regulations grc-list <id>` — get list of items in a GRC report
- `regulations grc-reports` — list available Global Regulatory Comparison reports
- `regulations regions-entitled` — get regions the user is entitled to access
- `regulations snapshot <id>` — get a snapshot of a regulatory document

### conferences
- `conferences search` — keyword search
- `conferences get <id>` — fetch conference record

### literature
- `literature search` — keyword search
- `literature get <id>` — fetch literature record
- `literature records <id> [<id2> ...]` — batch get multiple literature records by ID
- `literature molfile <id>` — get MOL file (chemical structure) for a literature record
- `literature structure-image <id>` — download structure image for a literature record
- `literature structure-search <smiles>` — search literature by chemical structure (SMILES)

### press-releases
- `press-releases search` — keyword search
- `press-releases get <id> [<id2> ...]` — fetch one or more press releases

### ontology
- `ontology search` — search ontology by term, category, indication, company, drug, target, technology, action
- `ontology top-level` — list top-level ontology nodes (optionally with counts)
- `ontology children` — list child nodes for a given category and tree code
- `ontology parents` — list parent nodes for a given category and tree code
- `ontology summary` — fetch an ontology summary for an entity
- `ontology synonyms` — fetch synonyms for a term in a taxonomy category
- `ontology synonyms-by-id` — fetch synonyms for a taxonomy node by numeric ID
- `ontology id-map` — map IDs for a given entity type between ID systems

### analytics
- `analytics run <query-name>` — execute a named analytics query; accepts `--drug-id`, `--indication-id`, `--action-id`, `--company-id`, `--trial-id`, `--id`, `--id-list`, `--format`

### ner
- `ner match <text>` — match named entities in free text; `--urls/--no-urls` controls URL inclusion

### company-analytics
- `company-analytics search-companies` — search companies in analytics context
- `company-analytics get-company <id>` — get company record in analytics context
- `company-analytics get-companies <id> [<id2> ...]` — batch get companies
- `company-analytics search-drugs` — search drugs in analytics context
- `company-analytics search-deals` — search deals in analytics context
- `company-analytics search-patents` — search patents in analytics context
- `company-analytics query-companies <kpi>` — run a company KPI query (e.g. `companyPipelineSuccess`)
- `company-analytics query-drugs <query>` — run a drug analytics query
- `company-analytics id-map` — map IDs between CI and SI
- `company-analytics company-model <id>` — get peer finder model for a company
- `company-analytics search-model` — search peer finder models
- `company-analytics similar-companies <id>` — find similar companies using peer finder

### deals-intelligence
- `deals-intelligence search` — search expanded deal records
- `deals-intelligence get <id>` — get expanded deal record with full financials
- `deals-intelligence records <id> [<id2> ...]` — batch get expanded deal records (up to 30)
- `deals-intelligence contracts <id>` — get deal contract documents
- `deals-intelligence contract-document <id>` — get contract document as PDF or TXT

### drug-design
- `drug-design search-drugs` — search drugs in SI domain
- `drug-design get-drugs <id> [<id2> ...]` — batch get drug records (up to 25 IDs)
- `drug-design molfile <id>` — get MOL file for a drug structure
- `drug-design structure-image <id>` — get structure image for a drug
- `drug-design pharmacology` — search pharmacology data
- `drug-design pharmacokinetics` — search pharmacokinetics data
- `drug-design patents <id> [<id2> ...]` — batch get patent records (up to 25)
- `drug-design references <id> [<id2> ...]` — batch get reference records (up to 25)
- `drug-design disease-briefings <id> [<id2> ...]` — batch get disease briefing records (up to 10)
- `drug-design disease-briefings-search` — search disease briefings
- `drug-design disease-briefing-text <id>` — get disease briefing section text
- `drug-design disease-briefing-media <id>` — get embedded media from a disease briefing

### targets
- `targets search` — search targets
- `targets records <id> [<id2> ...]` — batch get target records (up to 50 IDs)
- `targets drugs <id> [<id2> ...]` — get drug records in targets context (up to 25)
- `targets patents <id> [<id2> ...]` — get patent records in targets context (up to 25)
- `targets references <id> [<id2> ...]` — get reference records in targets context (up to 25)
- `targets trials <id> [<id2> ...]` — get trial records in targets context (up to 25)
- `targets interactions <id>` — get interactions for targets
- `targets sequences <id>` — get sequences for targets
- `targets condition-drugs <id>` — get drug-condition associations for targets
- `targets condition-genes <id>` — get gene-condition associations for targets
- `targets condition-variants <id>` — get gene variant-condition associations for targets

### chat
- `chat` — start an AI chat session for querying Cortellis in natural language; powered by Claude Code. Accepts `--debug` to show API commands being executed.

### config
- `config` — interactively set Cortellis API credentials and save them to a `.env` file

## Example Invocations

```bash
# Search Phase 3 drugs for diabetes (human-readable output)
cortellis drugs search --phase 3 --indication "diabetes"

# Same search with raw JSON output, pipe to jq
cortellis --json drugs search --phase 3 --indication "diabetes" | jq '.drugs[].drugName'

# Fetch tirzepatide report
cortellis drugs get 101964 --category report

# Find licensing deals in 2023
cortellis deals search --type licensing --date-start 2023-01-01 --date-end 2023-12-31

# Clinical trials for lung cancer in Phase 3
cortellis trials search --phase 3 --indication "lung cancer"

# Browse ontology indications
cortellis ontology top-level --category indication --counts

# Identify entities in text
cortellis ner match "Ozempic showed efficacy in type 2 diabetes"

# Search companies in analytics context
cortellis company-analytics search-companies --query "Pfizer"

# Find similar companies using peer finder
cortellis company-analytics similar-companies 12345

# Get expanded deal record with full financials
cortellis deals-intelligence get 98765

# Search expanded deals with financial detail
cortellis deals-intelligence search --indication "oncology"

# Search drugs in the drug design (SI) domain
cortellis drug-design search-drugs --query "semaglutide"

# Search pharmacology data
cortellis drug-design pharmacology --target "GLP1R"

# Search targets
cortellis targets search --query "GLP-1 receptor"

# Get drug-condition associations for a target
cortellis targets condition-drugs 55555

# Launch AI chat mode (requires Claude Code)
cortellis chat

# Launch interactive REPL
cortellis
```

## Output Modes

- **Default (human-readable)**: Rich tables and formatted output for interactive use
- **JSON (`--json`)**: Raw API JSON response for scripting and piping

The `--json` flag goes before the command group:
```bash
cortellis --json drugs search --phase 3
```

## REPL Mode

Running `cortellis` without arguments launches an interactive REPL where you type commands without the binary prefix:

```
cortellis> drugs search --phase 3
cortellis> --json companies search --country USA
cortellis> exit
```

## AI Chat Mode

`cortellis chat` launches Claude Code with full Cortellis knowledge pre-loaded. Ask questions in plain English:

```bash
cortellis chat
# > show me Phase 3 drugs for obesity
# > what deals did Pfizer close in 2023?
# > find GLP-1 receptor targets
```

Requires the `claude` CLI (Claude Code subscription). Use `--debug` to see the underlying API commands.

## Configuration

Credentials are read from environment variables or a `.env` file:
- `CORTELLIS_USERNAME`
- `CORTELLIS_PASSWORD`

Run `cortellis config` to set credentials interactively.
