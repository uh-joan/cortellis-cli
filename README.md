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
git clone https://github.com/uh-joan/cortellis-cli.git
cd cortellis-cli
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
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

## Configuration

Credentials are stored in a `.env` file. Set them up with:

```bash
cortellis setup    # full wizard (recommended)
cortellis config   # just credentials
```

## Requirements

- Python 3.9+
- Cortellis API credentials (ask your admin)
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) — install with `npm install -g @anthropic-ai/claude-code`, then `claude login`

## Development

```bash
pip install -e ".[dev]"
pytest cli_anything/cortellis/tests/test_core.py    # 88 unit tests, no creds needed
pytest cli_anything/cortellis/tests/test_e2e.py     # E2E tests, needs creds
```
