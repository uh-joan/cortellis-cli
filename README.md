# Cortellis CLI

```
  ╔═════════════════════════════════════════════════════════════════════════════╗
  ║                                                                             ║
  ║    ██████╗ ██████╗ ██████╗ ████████╗███████╗██╗     ██╗     ██╗███████╗     ║
  ║   ██╔════╝██╔═══██╗██╔══██╗╚══██╔══╝██╔════╝██║     ██║     ██║██╔════╝     ║
  ║   ██║     ██║   ██║██████╔╝   ██║   █████╗  ██║     ██║     ██║███████╗     ║
  ║   ██║     ██║   ██║██╔══██╗   ██║   ██╔══╝  ██║     ██║     ██║╚════██║     ║
  ║   ╚██████╗╚██████╔╝██║  ██║   ██║   ███████╗███████╗███████╗██║███████║     ║
  ║    ╚═════╝ ╚═════╝ ╚═╝  ╚═╝   ╚═╝   ╚══════╝╚══════╝╚══════╝╚═╝╚══════╝     ║
  ║                                                                             ║
  ║            P h a r m a c e u t i c a l   I n t e l l i g e n c e            ║
  ╚═════════════════════════════════════════════════════════════════════════════╝
```

> **Disclaimer:** This is an **unofficial, community-built tool**. It is not affiliated with, endorsed by, or supported by Clarivate, Cortellis, or any of their subsidiaries. Use at your own risk. You must have valid Cortellis API credentials and an active subscription to use this tool. Respect your organization's data usage policies and API terms of service.

The entire Cortellis pharmaceutical intelligence platform in your terminal. Ask questions in plain English — AI does the rest.

## Quick Start

```bash
pip install git+https://github.com/uh-joan/cortellis-cli.git
cortellis setup
```

The setup wizard walks you through credentials, tests your API connection, and checks Claude Code is ready. Takes 30 seconds.

## Usage

```bash
cortellis
```

Then just ask:

```
you> what drugs are on the market for obesity in the US?

  Found 8 launched drugs for obesity in the US:
  - Semaglutide (Wegovy/Ozempic) — Novo Nordisk
  - Tirzepatide (Zepbound/Mounjaro) — Eli Lilly
  - Liraglutide (Saxenda) — Novo Nordisk
  ...

you> tell me more about tirzepatide

  Tirzepatide is a dual GIP/GLP-1 receptor agonist developed by Eli Lilly...

you> show me Novo Nordisk's latest deals

  Found 47 deals. Top results:
  ...

you> find targets associated with GLP-1

you> what Phase 3 trials are running for diabetes?

you> exit
```

Use `--debug` to see what API calls are being made behind the scenes:

```bash
cortellis chat --debug
```

## What You Can Ask About

17 data domains covering the full Cortellis platform:

| Domain | Ask things like... |
|--------|-------------------|
| **Drugs** | "launched drugs for obesity", "tell me about semaglutide", "drug financials for tirzepatide" |
| **Companies** | "show me Pfizer's profile", "find companies in oncology" |
| **Deals** | "Novo Nordisk deals in 2023", "licensing deals for GLP-1" |
| **Trials** | "Phase 3 trials for diabetes", "trials sponsored by Moderna" |
| **Regulatory** | "FDA approvals for semaglutide", "regulatory docs in EU" |
| **Conferences** | "ASCO presentations about immunotherapy" |
| **Literature** | "publications about VEGF inhibitors" |
| **Press Releases** | "Pfizer press releases about acquisitions" |
| **Ontology** | "look up obesity indication ID", "synonyms for diabetes" |
| **Analytics** | "trial durations for tirzepatide", "patent landscape for Novo Nordisk" |
| **Targets** | "targets associated with PD-L1", "gene-disease associations" |
| **Drug Design** | "pharmacology data for aspirin", "disease briefings for obesity" |

## Direct CLI

Every command works without AI chat. Use `--json` for machine-readable output:

```bash
# Human-readable tables
cortellis drugs search --phase L --indication 238 --hits 10
cortellis companies get 18614
cortellis deals search --principal "Novo Nordisk" --hits 20

# JSON for scripting and piping
cortellis --json drugs search --phase L --hits 5 | jq '.drugs[].drugName'

# Interactive REPL
cortellis repl
```

17 command groups, 80+ subcommands. Run `cortellis --help` for the full list.

## Skills (AI Workflows)

Four pre-built skills automate multi-step analysis:

| Skill | What it does |
|-------|-------------|
| `/pipeline` | Full company pipeline report (CI + Drug Design, all phases, deals, trials) |
| `/landscape` | Competitive landscape by indication, target, or technology |
| `/drug-profile` | Deep profile for a single drug (SWOT, financials, history, competitors) |

These work as slash commands inside [Claude Code](https://docs.anthropic.com/en/docs/claude-code):

**If you cloned the repo (working inside it):**
```bash
cd cortellis-cli
claude
> /pipeline "Novo Nordisk"
> /landscape obesity
> /drug-profile tirzepatide
```

**From any directory (plugin mode):**
```bash
git clone https://github.com/uh-joan/cortellis-cli.git
claude --plugin-dir ./cortellis-cli
> /cortellis:pipeline "Novo Nordisk"
> /cortellis:landscape obesity
> /cortellis:drug-profile tirzepatide
```

## Agent Integration

The CLI is designed to be used by AI agents. Any agent that can run shell commands can:

1. **Discover** — `which cortellis` finds it on `$PATH`
2. **Learn capabilities** — `cortellis repl` banner shows absolute paths to SKILL.md files
3. **Execute** — `cortellis --json drugs search --phase L` returns structured JSON
4. **Handle errors** — errors return `{"error": "...", "type": "...", "details": {...}}` in `--json` mode

## Installation

**For users:**
```bash
pip install git+https://github.com/uh-joan/cortellis-cli.git
cortellis setup
```

**For developers:**
```bash
git clone https://github.com/uh-joan/cortellis-cli.git
cd cortellis-cli
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cortellis setup
```

## Configuration

Credentials are stored in a `.env` file. Set them up with:

```bash
cortellis setup    # full wizard (recommended)
cortellis config   # just credentials
```

Or set environment variables directly:
```bash
export CORTELLIS_USERNAME="your-username"
export CORTELLIS_PASSWORD="your-password"
```

## Requirements

- Python 3.9+
- Cortellis API credentials (ask your admin)
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) (optional) — needed for AI chat mode and slash commands. Install with `npm install -g @anthropic-ai/claude-code`, then `claude login`

## Development

```bash
pip install -e ".[dev]"
pytest cli_anything/cortellis/tests/test_core.py    # 88 unit tests, no creds needed
pytest cli_anything/cortellis/tests/test_e2e.py     # E2E tests, needs creds
```
