# Cortellis AI-native knowledge base - Intelligence that compounds

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

The pharma analyst that never sleeps. Cortellis data, deterministic skill pipelines, a self-building knowledge base, and exports ready for the boardroom — powered by AI that compounds with every session.

## The Problem

Pharma CI analysts spend **70% of their time gathering data** and 30% on actual analysis. Every landscape starts from scratch. Insights from last month's analysis vanish. Five database tabs open to answer one question about a competitor. The quarterly report means rebuilding everything from zero.

Built on [Karpathy's LLM Wiki pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f): knowledge is compiled once and kept current, not re-derived on every query. The wiki is a persistent, compounding artifact.

## Install

```bash
pip install git+https://github.com/uh-joan/cortellis-cli.git
cortellis setup    # credentials + API test, 30 seconds
```

## Three Layers

A CLI for raw data access, a **harness** for deterministic multi-step analysis, and a compounding wiki that gets smarter with every session.

### 1. CLI — 13 Data Domains, 80+ Commands

```bash
cortellis drugs search --phase L --indication 238 --hits 10
cortellis --json deals search --drug "semaglutide" | jq .
cortellis trials search --phase C3 --indication obesity
cortellis regulations search --region USA
```

Drugs, companies, deals, trials, regulatory, targets, drug design, ontology, analytics, conferences, literature, press releases, NER.

### 2. Skills — Multi-Step Analysis Workflows

Slash commands that orchestrate full analytical pipelines — works with [Claude Code](https://docs.anthropic.com/en/docs/claude-code) or [OpenAI Codex](https://github.com/openai/codex):

| Command | What it does |
|---------|-------------|
| `/landscape obesity` | Competitive landscape — CPI rankings, mechanism crowding, deals, opportunities |
| `/pipeline "Novo Nordisk"` | Company pipeline — all phases, deals, trials |
| `/drug-profile tirzepatide` | Deep drug profile — SWOT, financials, history, competitors |
| `/target-profile GLP-1` | Target biology — disease associations, drug pipeline, pharmacology |
| `/drug-comparison tirzepatide vs semaglutide` | Head-to-head comparison across all dimensions |
| `/conference-intel ASCO 2026` | Conference briefing — "What's New / So What / What's Next" |
| `/signals` | Strategic intelligence report across all analyzed landscapes |
| `/insights` | Accumulated analytical insights from previous sessions |

**Skills are self-evolving.** The more you use them, the faster and smarter they get. Entity lookups are cached so repeated runs skip API calls entirely. After each run, a reviewer checks what worked and what was empty, and encodes the patterns directly into the skill — so next time it skips what's known to be irrelevant for that drug class or indication. Ships pre-seeded with common patterns from real runs; compounds from there.

Every skill runs through the **harness** — a deterministic DAG executor (`cortellis run-skill`) that sequences steps, hard-fails on any error, and guarantees the same output whether triggered from chat, the web UI, or the CLI directly. No silent gaps, no improvised steps.

```bash
cortellis run-skill landscape obesity      # same pipeline as /landscape in chat
cortellis run-skill pipeline "Novo Nordisk"
cortellis run-skill drug-profile tirzepatide --dry-run  # preview execution plan
```

→ **[Knowledge base commands](KNOWLEDGE_BASE.md)** — `wiki refresh`, `changelog`, `ingest`, `/signals`, `/insights`.

### 3. Knowledge Base — Persistent, Compounding Intelligence

Every analysis compiles into a persistent wiki that gets richer over time.

```
wiki/
├── INDEX.md                 ← Master catalog (auto-maintained)
├── log.md                   ← Chronological activity record
├── indications/             ← Compiled landscape articles (14+)
├── companies/               ← Cross-indication company profiles (100+)
├── drugs/                   ← Drug profile articles
├── targets/                 ← Target biology articles
├── insights/sessions/       ← Session-derived analytical insights
├── graph.json               ← NetworkX knowledge graph
└── GRAPH_REPORT.md          ← Entity clusters, god nodes, bridges
```

**Compile** — each skill run writes wiki articles with YAML frontmatter and `[[wikilinks]]`. **Accumulate** — session hooks capture conversation insights automatically. **Inject** — next session starts with everything in context. **Lint** — 7 structural health checks keep the wiki healthy.

**Open in [Obsidian](https://obsidian.md)** for graph view, backlinks, and visual navigation — `Open folder as vault → wiki/`.

## Web UI

Prefer a browser? The same intelligence is available as a web app:

```bash
cortellis web          # opens http://localhost:7337
cortellis web --dev    # hot-reload mode for UI development (requires node/npm)
```

Chat with your compiled wiki, run queries, and explore the knowledge graph — no terminal required. The UI is built during `cortellis setup`.

## See It In Action

Start the CLI with Claude Code (default) or OpenAI Codex:

```bash
cortellis                        # Claude Code (default)
cortellis --engine codex         # OpenAI Codex
```

The SessionStart hook injects compiled wiki context — the AI already knows your landscapes, signals, and previous insights.

```
you> what is the competitive landscape for obesity?
```

Answers **in seconds** from compiled knowledge. No pipeline, no API calls. 772 drugs, CPI rankings, mechanism analysis — all from the wiki.

```
you> how does Novo Nordisk's position compare across our analyzed indications?
```

Cross-references `wiki/companies/novo-nordisk.md` — CPI 95.0 in obesity, 77.5 in GLP-1.

```
you> compare all our analyzed indications
```

14 indications in one table, sorted by pipeline size.

```
you> what changed in the obesity landscape?
```

Drug count deltas by phase, deal velocity, company ranking shifts.

```
you> show me how the obesity pipeline has evolved over the last year
```

Fetches **real historical data** via Cortellis `change_history` API. Phase 3 nearly doubled in 12 months (17 to 32). Tirzepatide launched Dec 2025. Survodutide entered Phase 3 Mar 2026.

```
you> export the obesity landscape as a PowerPoint deck
```

8-slide PPTX. Also: Excel (5 sheets), BD brief (deal comps + licensing targets), executive brief (5 bullets, plain language).

```
you> compare tirzepatide vs semaglutide
```

Head-to-head: phase, mechanism, indications, trials, deals — side-by-side.

```
you> what have we learned from previous analyses?
```

Accumulated session insights — key findings, scenarios, implications from past runs.

**Exit.** The SessionEnd hook captures the transcript, extracts insights, writes to `daily/`. Next session starts with those insights — **the system remembers**.

## Requirements

- **Python 3.9+**
- **[Cortellis API credentials](https://www.cortellis.com)** — active subscription required
- **AI engine** (choose one, both optional — all CLI commands work without them):
  - **[Claude Code](https://docs.anthropic.com/en/docs/claude-code)** — `npm install -g @anthropic-ai/claude-code` + `claude login`
  - **[OpenAI Codex](https://github.com/openai/codex)** — `npm install -g @openai/codex` + `codex login --device-auth` (ChatGPT Plus/Pro subscription)
- **[Obsidian](https://obsidian.md)** *(optional)* — for wiki graph view and visual navigation
- **NetworkX** — included automatically; builds `wiki/graph.json` after every skill run
