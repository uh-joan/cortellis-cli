# Plan: CLI-Anything Cortellis CLI

## Context

Build a CLI-Anything style Python CLI for the Cortellis pharmaceutical intelligence platform at `/Users/janisaez/code/cortellis-cli/`. The user owns the Cortellis MCP server (`uh-joan/cortellis-mcp-server`) which wraps 20 Cortellis REST API tools with Digest auth. We'll build a Python Click CLI that calls the Cortellis API directly (not wrapping the MCP server), following CLI-Anything conventions (namespace packages, REPL, dual JSON/human output, SKILL.md).

## Directory Structure

```
cortellis-cli/
├── setup.py
├── README.md
├── cli_anything/                     # NO __init__.py (PEP 420 namespace)
│   └── cortellis/                    # HAS __init__.py
│       ├── __init__.py
│       ├── __main__.py
│       ├── cortellis_cli.py          # Click groups + REPL entry
│       ├── core/
│       │   ├── __init__.py
│       │   ├── client.py             # Digest auth HTTP client (requests)
│       │   ├── query_builder.py      # Cortellis query syntax (LINKED, RANGE, ::)
│       │   ├── drugs.py
│       │   ├── companies.py
│       │   ├── deals.py
│       │   ├── trials.py
│       │   ├── regulatory.py
│       │   ├── ontology.py
│       │   ├── analytics.py
│       │   ├── literature.py
│       │   ├── conferences.py
│       │   ├── press_releases.py
│       │   └── ner.py
│       ├── utils/
│       │   ├── __init__.py
│       │   ├── output.py             # Dual JSON/human formatting (Rich tables)
│       │   └── repl_skin.py          # Interactive REPL
│       ├── skills/
│       │   └── SKILL.md
│       └── tests/
│           ├── __init__.py
│           ├── TEST.md
│           ├── test_core.py          # Unit tests (mocked HTTP)
│           └── test_e2e.py           # E2E tests (real API, skip if no creds)
```

## Command Hierarchy

```
cli-anything-cortellis [--json]
├── drugs
│   ├── search [--query, --company, --indication, --action, --phase, --technology, --drug-name, --country, --offset, --hits, --sort-by, --historic, --status-date]
│   └── get <id> [--category report|swot|financial]
├── companies
│   ├── search [--query, --name, --country, --size, --deals-count, --indications, --actions, --technologies, --status, --offset, --hits, --sort-by]
│   └── get <id>
├── deals
│   ├── search [--query, --drug, --indication, --type, --status, --principal, --partner, --phase-start, --phase-now, --technologies, --action, --date-start, --date-end, --offset, --sort-by]
│   └── get <id> [--category basic|expanded]
├── trials
│   ├── search [--query, --indication, --phase, --status, --sponsor, --funder-type, --enrollment, --date-start, --date-end, --identifier, --offset, --hits, --sort-by]
│   └── get <id> [--category report|sites]
├── regulations
│   ├── search [--query, --region, --doc-category, --doc-type, --language, --offset, --hits, --sort-by]
│   └── get <id> [--category metadata|source]
├── conferences
│   ├── search [--query, --offset, --hits, --sort-by]
│   └── get <id>
├── literature
│   ├── search [--query, --offset, --hits, --sort-by]
│   └── get <id>
├── press-releases
│   ├── search [--query, --offset, --hits, --sort-by]
│   └── get <id-list>
├── ontology
│   ├── search [--term, --category, --indication, --company, --drug, --target, --technology, --action]
│   ├── top-level [--category] [--counts] [--dataset]
│   ├── children [--category, --tree-code] [--counts] [--dataset]
│   └── parents [--category, --tree-code]
├── analytics
│   └── run <query-name> [--drug-id, --indication-id, --action-id, --company-id, --trial-id, --id, --id-list, --format]
└── ner
    └── match <text> [--urls/--no-urls]
```

## Key Architecture Decisions

1. **`requests.auth.HTTPDigestAuth`** — Python's `requests` handles Digest auth natively. The MCP server's 100+ lines of manual MD5 → one line: `session.auth = HTTPDigestAuth(user, pwd)`

2. **Centralized query builder** — The MCP server scatters query building across 10+ tools. We consolidate into `query_builder.py` with the Cortellis query syntax patterns:
   - `LINKED()` for drug/company development status compound fields
   - `RANGE()` for numeric/date filtering
   - `::` (double colon) for numeric IDs vs `:` for text values
   - Historic mode field name switching (`developmentStatus*` → `developmentStatusHistoric*`)

3. **Core/CLI separation** — Core modules are pure functions (client + params → dict). CLI is pure Click. Enables unit testing without Click context.

4. **Lazy client init** — Client created in root group callback, stored in `ctx.obj`. Credentials validated on first API call (so `--help` works without creds).

5. **No undo/redo, no backend.py** — Cortellis is read-only. The HTTP client IS the backend.

6. **Credentials** — `CORTELLIS_USERNAME` / `CORTELLIS_PASSWORD` env vars, with `python-dotenv` .env support.

## Dependencies

**Runtime**: `click>=8.1`, `requests>=2.31`, `rich>=13.0`, `prompt_toolkit>=3.0`, `python-dotenv>=1.0`
**Dev**: `pytest>=7.0`, `pytest-mock>=3.0`, `responses>=0.23`

## Build Order

| Step | What | Files |
|------|------|-------|
| 1 | Package scaffolding | `setup.py`, all `__init__.py`, `__main__.py` |
| 2 | HTTP client | `core/client.py` |
| 3 | Query builder | `core/query_builder.py` |
| 4 | Output formatting | `utils/output.py` |
| 5 | First 2 domains (proof of concept) | `core/drugs.py`, `core/companies.py` |
| 6 | CLI with drugs+companies groups | `cortellis_cli.py` (partial) |
| 7 | Unit tests for query builder | `tests/test_core.py` |
| 8 | Remaining 9 domain modules | `core/deals.py` through `core/ner.py` |
| 9 | Complete CLI groups | `cortellis_cli.py` (full) |
| 10 | REPL | `utils/repl_skin.py` + integration |
| 11 | Documentation | `SKILL.md`, `TEST.md`, `README.md` |
| 12 | E2E tests | `tests/test_e2e.py` |

## Verification

1. `pip install -e .` succeeds
2. `cli-anything-cortellis --help` shows all 10 command groups
3. `cli-anything-cortellis drugs search --phase L --hits 5` returns human-readable results
4. `cli-anything-cortellis --json drugs search --phase L --hits 5` returns raw JSON
5. `cli-anything-cortellis drugs get 101964 --category report` fetches tirzepatide
6. `pytest tests/test_core.py` passes (no creds needed)
7. `pytest tests/test_e2e.py` passes (with creds in env)
8. REPL mode launches and accepts `drugs search --phase L`

## Critical Files (in order of importance)

1. `cli_anything/cortellis/core/client.py` — HTTP client with Digest auth
2. `cli_anything/cortellis/core/query_builder.py` — Cortellis query syntax engine
3. `cli_anything/cortellis/cortellis_cli.py` — Click command definitions + REPL
4. `cli_anything/cortellis/utils/output.py` — Dual-mode formatting
5. `setup.py` — Namespace package config
