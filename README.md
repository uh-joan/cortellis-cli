# Cortellis

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

The pharma analyst that never sleeps. Cortellis data, analytical skills, a self-building knowledge base, and exports ready for the boardroom — powered by Cortellis data and AI that compounds with every session.

## Install

```bash
pip install git+https://github.com/uh-joan/cortellis-cli.git
cortellis setup    # credentials + API test, 30 seconds
```

Requires Python 3.9+ and [Cortellis API credentials](https://www.cortellis.com). [Claude Code](https://docs.anthropic.com/en/docs/claude-code) needed for AI chat and skills.

## Quick Start

```bash
cortellis                    # AI chat mode
cortellis drugs search ...   # Direct CLI
cortellis repl               # Interactive REPL
```

## Three Layers

### 1. CLI — 13 Data Domains, 80+ Commands

```bash
cortellis drugs search --phase L --indication 238 --hits 10
cortellis --json deals search --drug "semaglutide" | jq .
cortellis trials search --phase C3 --indication obesity
cortellis regulations search --region USA
```

Drugs, companies, deals, trials, regulatory, targets, drug design, ontology, analytics, conferences, literature, press releases, NER.

### 2. Skills — Multi-Step Analysis Workflows

Slash commands in Claude Code that orchestrate full analytical pipelines:

| Command | What it does |
|---------|-------------|
| `/landscape obesity` | Competitive landscape — CPI rankings, mechanism crowding, deals, opportunities |
| `/pipeline "Novo Nordisk"` | Company pipeline — all phases, deals, trials |
| `/drug-profile tirzepatide` | Deep drug profile — SWOT, financials, history, competitors |
| `/target-profile GLP-1` | Target biology — disease associations, drug pipeline, pharmacology |
| `/drug-comparison tirzepatide vs semaglutide` | Head-to-head comparison across all dimensions |
| `/conference-intel ASCO 2026` | Conference briefing with "What's New / So What / What's Next" |
| `/signals` | Strategic intelligence report across all analyzed landscapes |
| `/insights` | Accumulated analytical insights from previous sessions |

### 3. Knowledge Base — Persistent, Compounding Intelligence

Following [Karpathy's LLM Wiki pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f): every analysis compiles into a persistent wiki that gets richer over time.

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

**How it works:**
- **Compile**: Each skill run compiles structured data into wiki articles with YAML frontmatter and `[[wikilinks]]`
- **Accumulate**: Session hooks capture conversation insights via Claude Code lifecycle events
- **Inject**: Next session starts with wiki INDEX + strategic signals + previous insights in context
- **Query**: Claude answers from compiled knowledge in seconds instead of re-running pipelines
- **Lint**: 7 structural health checks (broken links, orphans, stale data, missing refs)

**Open in Obsidian** for graph view, backlinks, and visual navigation:
```
Obsidian → Open folder as vault → select wiki/
```

## See It In Action

Start the CLI. The SessionStart hook injects compiled wiki context — Claude already knows your landscapes, signals, and previous insights.

```
cortellis

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

Runs `portfolio_report.py` — 14 indications in one table, sorted by pipeline size.

```
you> what changed in the obesity landscape?
```

Runs `diff_landscape.py` — drug count deltas by phase, deal velocity, company ranking shifts.

```
you> show me how the obesity pipeline has evolved over the last year
```

Fetches **real historical data** via Cortellis `change_history` API. Phase 3 nearly doubled in 12 months (17 to 32). Tirzepatide launched Dec 2025. Survodutide entered Phase 3 Mar 2026.

```
you> any strategic signals across the portfolio?
```

Runs `signals_report.py` — high/medium/low severity signals with action templates.

```
you> export the obesity landscape as a PowerPoint deck
```

Generates 8-slide PPTX (16:9, Calibri, pharma styling). Also available: Excel workbook (5 sheets), BD brief (deal comps + licensing targets), executive brief (5 bullets, plain language).

```
you> compare tirzepatide vs semaglutide
```

Head-to-head: phase, mechanism, indications, trials, deals — side-by-side table.

```
you> check the wiki health
```

7 lint checks: broken wikilinks, orphan pages, stale articles, missing cross-refs.

```
you> what have we learned from previous analyses?
```

Shows accumulated session insights — key findings, scenarios, implications from past runs.

**Exit the session.** The SessionEnd hook captures the transcript, extracts insights, and writes to `daily/`. Next session starts with those insights injected — the system remembers and compounds.

## Wiki Management

```bash
python3 $RECIPES/wiki_manage.py status             # KB health summary
python3 $RECIPES/wiki_manage.py reset              # Fresh start (raw/ preserved)
python3 $RECIPES/wiki_manage.py remove obesity      # Remove one indication + refs
python3 $RECIPES/wiki_manage.py prune              # Clean orphaned articles
```

## Architecture

```
Cortellis REST API (Digest auth)
       │
  core/*.py ── 13 domain modules (thin API wrappers)
       │
  skills/ ── 8 SKILL.md workflows + 30+ recipe scripts
       │
  wiki/ ── Compiled knowledge base (Karpathy pattern)
       │
  hooks/ ── Claude Code lifecycle hooks (SessionStart/End/PreCompact)
       │
  daily/ ── Conversation logs → compiled into wiki insights
```

## Development

```bash
git clone https://github.com/uh-joan/cortellis-cli.git
cd cortellis-cli
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest cli_anything/cortellis/tests/test_core.py -v     # 521 unit tests, no creds
pytest cli_anything/cortellis/tests/test_e2e.py -v      # E2E, needs creds
```

Optional: `pip install -e ".[graph]"` for NetworkX knowledge graph features.
