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

> **Disclaimer:** Unofficial, community-built tool. Not affiliated with Clarivate or Cortellis. Requires valid API credentials and an active subscription.

The entire Cortellis platform in your terminal — 17 data domains, 80+ commands. Ask questions in plain English or use the CLI directly.

## Install

```bash
pip install git+https://github.com/uh-joan/cortellis-cli.git
cortellis setup    # credentials + API test, 30 seconds
```

Requires Python 3.9+ and [Cortellis API credentials](https://www.cortellis.com). [Claude Code](https://docs.anthropic.com/en/docs/claude-code) is optional (needed for AI chat and slash commands).

## AI Chat

```bash
cortellis
```

```
you> what drugs are on the market for obesity in the US?
you> tell me more about tirzepatide
you> show me Novo Nordisk's latest deals
you> what Phase 3 trials are running for diabetes?
```

Covers drugs, companies, deals, trials, regulatory, targets, drug design, ontology, analytics, conferences, literature, and press releases.

## Direct CLI

```bash
cortellis drugs search --phase L --indication 238 --hits 10
cortellis --json drugs search --phase L --hits 5 | jq '.drugs[].drugName'
cortellis repl    # interactive mode
```

Run `cortellis --help` for the full command list.

## Skills

Pre-built multi-step analysis workflows, available as slash commands in [Claude Code](https://docs.anthropic.com/en/docs/claude-code):

| Command | What it does |
|---------|-------------|
| `/pipeline "Novo Nordisk"` | Full company pipeline (all phases, deals, trials) |
| `/landscape obesity` | Competitive landscape by indication, target, or technology |
| `/drug-profile tirzepatide` | Deep drug profile (SWOT, financials, history, competitors) |

**From this repo:**
```bash
claude
> /pipeline "Eli Lilly"
```

**From anywhere (plugin mode):**
```bash
git clone https://github.com/uh-joan/cortellis-cli.git
claude --plugin-dir ./cortellis-cli
> /cortellis:pipeline "Eli Lilly"
```

## Agent Integration

Any AI agent that can run shell commands can use the CLI:

```bash
which cortellis                                    # discover
cortellis --json drugs search --phase L --hits 5   # structured JSON output
# errors: {"error": "...", "type": "...", "details": {...}}
```

The REPL banner shows absolute paths to SKILL.md files for capability discovery.

## Development

```bash
git clone https://github.com/uh-joan/cortellis-cli.git
cd cortellis-cli
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest cli_anything/cortellis/tests/test_core.py    # 88 unit tests, no creds
pytest cli_anything/cortellis/tests/test_e2e.py     # E2E, needs creds
```
