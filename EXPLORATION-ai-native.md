# AI-Native Architecture Exploration for Cortellis CLI

> Branch: `explore/ai-native-architecture` | Date: 2026-04-07

---

## Part 1: Where We Are

The `cortellis-cli` is a **17,700-line Python CLI** wrapping the Cortellis REST API. But it's more than a wrapper — it already has an AI orchestration layer:

- **Claude Code as agent harness** — reads SKILL.md files, executes multi-step workflows
- **14-step landscape pipeline** — fetch → enrich → score → analyze → narrate
- **21+ recipe scripts** — strategic scoring (CPI), SWOT, scenario analysis, narrative generation
- **MCP server** already exists at `github.com/uh-joan/cortellis-mcp-server`

**The key insight from codebase analysis**: `core/*.py` modules are commodity HTTP pass-throughs. ALL intelligence lives in the skill recipes. The system already does proto-knowledge-compilation — `narrate.py` produces `narrate_context.json`, `strategic_scoring.py` computes CPI rankings — it just stops one step short and **throws away the reasoning after each session**.

---

## Part 2: The Paradigm Shift — What "AI-Native" Actually Means in 2026

### The Agent Harness Era

"Agent Harness" is the defining architectural concept of 2026. The formula:

> **Agent = Model + Harness**

The harness is everything around the LLM: tool dispatch, memory, state, permissions, context management, lifecycle hooks, safety rails. Two teams using the same model achieve 60% vs 98% task completion based entirely on harness quality. Meta's ~$2B Manus acquisition (Dec 2025) was buying the harness, not the model.

**Claude Code IS an agent harness.** Your system already runs inside one. The question isn't "should we use an agent harness?" — it's "how do we build a pharma-specialized harness layer on top?"

Sources: [Anthropic Engineering](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents), [LangChain Anatomy](https://blog.langchain.com/the-anatomy-of-an-agent-harness/), swyx IMPACT framework

### Karpathy's Knowledge Compilation

Andrej Karpathy (April 2026) published the most influential architecture for this problem — the **LLM Knowledge Base**:

```
raw/          ← immutable source documents (API responses, papers, clips)
wiki/         ← LLM-compiled, LLM-maintained structured markdown
  INDEX.md    ← navigational index the LLM reads to find relevant articles
  concepts/   ← one article per concept, with [[wikilinks]]
output/       ← query results, slides, charts
```

**Four operations**: Ingest → Compile → Query → Lint

The compiler analogy: `raw/` is source code, the LLM is the compiler, `wiki/` is the executable, lint is the test suite, queries are runtime.

**Why this beats RAG at personal/team scale** (~50-500 articles): The LLM reads a structured INDEX.md and navigates [[wikilinks]] to find relevant articles. No vector DB, no embeddings, no cosine similarity. At this scale, an LLM reading a structured index outperforms vector similarity because the LLM understands intent while cosine similarity finds word overlap. RAG becomes necessary only at ~2,000+ articles.

**The context-as-RAM insight**: If the context window is RAM and model weights are disk, then context engineering is memory management. What you load into the context window before each operation determines what the LLM can reason over. A 1M-token context holds ~3.75MB of text — **12 complete landscape analyses simultaneously**.

Sources: [Karpathy llm-wiki gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f), [Karpathy tweet](https://x.com/karpathy/status/2039805659525644595), [VentureBeat](https://venturebeat.com/data/karpathy-shares-llm-knowledge-base-architecture-that-bypasses-rag-with-an)

---

## Part 3: Four Tools That Map Directly

### 1. Graphify — Knowledge Graphs from Code + Docs

[github.com/safishamsi/graphify](https://github.com/safishamsi/graphify)

**What it is**: An AI skill that transforms folders of files into queryable knowledge graphs. Two-pass architecture:
- **Pass 1 (deterministic)**: tree-sitter AST parsing extracts code structure — no LLM needed
- **Pass 2 (LLM-driven)**: Claude subagents extract concepts, relationships, design rationale from docs/papers/images

Outputs: interactive HTML visualization, markdown report, persistent JSON graph.

**Tech**: NetworkX + Leiden clustering (graspologic) + tree-sitter + vis.js. **No Neo4j, no server, runs entirely locally.**

**71.5x fewer tokens per query** vs reading raw files (on a 52-file corpus). The graph becomes a compact, navigable representation.

**Pharma application**: Run `/graphify` over `raw/obesity/` (36 files, ~300KB) to automatically discover entity relationships — drug→target→mechanism→company connections — without writing graph construction code. The Leiden community detection would surface therapeutic clusters (e.g., "all GLP-1 agonists cluster together with Novo Nordisk and Lilly").

### 2. Claude Memory Compiler — Persistent Knowledge from Conversations

[github.com/coleam00/claude-memory-compiler](https://github.com/coleam00/claude-memory-compiler)

**What it is**: Directly implements Karpathy's architecture for Claude Code sessions. Conversations → flush.py extracts insights → compile.py organizes into structured articles → session-start hook injects index into next session.

**Architecture**:
```
Conversation → hooks → flush.py → daily/YYYY-MM-DD.md → compile.py → knowledge/
                                                                        ├── concepts/
                                                                        ├── connections/
                                                                        ├── qa/
                                                                        └── index.md
```

**No vector DB by design**. At personal scale, Claude reading `index.md` outperforms RAG. Articles use Obsidian-style `[[wikilinks]]` and YAML frontmatter.

**Cost**: ~$0.02-0.05 per session flush, ~$0.50 daily compile, ~$0.25 per query.

**Pharma application**: Each `/landscape` or `/pipeline` skill execution becomes a "session" that gets flushed. Strategic conclusions, competitive positions, deal patterns accumulate across runs. Next time you analyze obesity, the system starts with: "Previous analysis (2026-03-15): Novo Nordisk leads with CPI 87.3, rising challenger Boehringer entered via ADC mechanism..."

### 3. Graphify + Memory Compiler = Pharma Intelligence KB

The two tools are **complementary, not competing**:

| Layer | Tool | Role |
|-------|------|------|
| Structure discovery | Graphify | Automatically find entity relationships in landscape data |
| Knowledge persistence | Memory Compiler | Accumulate analytical insights across sessions |
| Navigation | Karpathy INDEX.md | LLM reads structured index to find relevant compiled knowledge |

### 4. The Harness Layer — What Ties It Together

The agent harness pattern (Anthropic, Nov 2025) provides the orchestration:

- **Initializer agent**: Sets up state (git, progress files, feature lists)
- **Worker agent**: Makes incremental progress per session
- **Lifecycle hooks**: Session start (inject KB), session end (flush insights), error recovery
- **Permission gates**: Confirmation before multi-step skills (50+ API calls)
- **Progress tracking**: `freshness.json` already exists but is display-only — make it load-bearing

---

## Part 4: The Vision — Cortellis Pharma Intelligence KB

### Architecture

```
                         ┌─────────────────────────────────────┐
                         │         ANALYST QUESTION             │
                         └──────────────┬──────────────────────┘
                                        │
                         ┌──────────────▼──────────────────────┐
                         │      PHARMA AGENT HARNESS            │
                         │  (Claude Code + OMC + Cortellis)     │
                         │                                      │
                         │  ┌────────────┐  ┌────────────────┐ │
                         │  │ KB Router  │  │ Freshness Gate  │ │
                         │  │ wiki/ hit? │  │ < 7 days old?  │ │
                         │  └─────┬──────┘  └───────┬────────┘ │
                         │        │                  │          │
                         └────────┼──────────────────┼──────────┘
                                  │                  │
                    ┌─────────────▼──┐     ┌────────▼────────┐
                    │  COMPILED KB    │     │  LIVE API PATH   │
                    │  (wiki/)        │     │  (core/*.py)     │
                    │                 │     │                  │
                    │  INDEX.md       │     │  Cortellis REST  │
                    │  drugs/         │     │  → raw/ CSVs     │
                    │  targets/       │     │  → compile       │
                    │  indications/   │     │  → update wiki/  │
                    │  deals/         │     │                  │
                    │  companies/     │     │  (MCP server     │
                    │  landscapes/    │     │   also available) │
                    └─────────────────┘     └─────────────────┘
                              │                      │
                              └──────────┬───────────┘
                                         │
                         ┌───────────────▼─────────────────────┐
                         │     KNOWLEDGE COMPILATION LOOP       │
                         │                                      │
                         │  1. Ingest: API → raw/ markdown      │
                         │  2. Compile: raw/ → wiki/ articles   │
                         │  3. Graph: Graphify discovers links  │
                         │  4. Lint: stale data, contradictions │
                         │  5. Diff: what changed since last?   │
                         └──────────────────────────────────────┘
```

### The Three Layers

#### Layer 1: Knowledge Compilation (Karpathy pattern)

Transform the existing landscape output into a **persistent, LLM-optimized wiki**.

```
wiki/
  INDEX.md                          ← Master index with one-line summaries
  indications/
    obesity.md                      ← Full landscape: 47 drugs, key players,
                                       mechanism distribution, deal velocity
    nsclc.md
  drugs/
    semaglutide.md                  ← Mechanism, trials, approvals, deals,
                                       competitive position, [[Novo Nordisk]]
    tirzepatide.md                  ← [[Eli Lilly]], dual GIP/GLP-1, [[obesity]]
  targets/
    glp1-receptor.md                ← All drugs, crowding index, pathway context
    egfr.md
  companies/
    novo-nordisk.md                 ← Portfolio across indications, CPI by area,
                                       deal history, strategic position
  deals/
    recent-licensing-obesity.md     ← Deal patterns, average values, key terms
  landscapes/
    obesity-2026-04-07.md           ← Compiled dossier: full strategic analysis,
                                       CPI rankings, 2x2 matrix, scenarios
```

**Each article**: YAML frontmatter (sources, related, last_compiled, freshness) + structured prose with [[wikilinks]] + reasoning scaffolds.

**The compile step** (`compile_dossier.py`): Reads ALL files in `raw/<indication>/` and produces/updates wiki articles. This is Step 15 added after the existing landscape pipeline's Step 14 (narrate.py).

**What this enables**: "Compare the competitive position of Novo Nordisk across obesity, T2D, and MASH" — answered by loading 3 compiled landscape dossiers into context. No API calls. Pre-compiled reasoning with cross-references.

#### Layer 2: Temporal Intelligence (Memory Compiler pattern)

**The system currently has no memory.** Every run is a snapshot that forgets it ever happened.

Add temporal awareness:

1. **Versioned snapshots**: `raw/obesity/2026-04-07/` instead of `raw/obesity/`
2. **Diff engine** (`diff_landscape.py`): Compare two snapshots → change report
   - "Novo Nordisk: +2 drugs since last run (CPI 87.3 → 89.1)"
   - "New entrant: Boehringer Ingelheim entered with survodutide (Phase 3)"
   - "Deal alert: 3 new licensing deals in last 30 days"
3. **Session memory** (Memory Compiler): Each skill run gets flushed → strategic conclusions persist
   - "Previous analysis noted obesity landscape is consolidating around dual-agonist mechanisms"
   - "User flagged Amgen's AMG 133 as one to watch (2026-03-15)"
4. **Freshness-aware routing**: Before fetching, check wiki article `last_compiled` date. If fresh, answer from wiki. If stale, re-fetch and re-compile.

#### Layer 3: Structure Discovery (Graphify pattern)

Run Graphify over compiled wiki to automatically discover:

- **Entity clusters**: Which drugs/companies/targets form natural groupings?
- **Hidden connections**: "Company X has deals with 3 of the top 5 target owners in this space"
- **God nodes**: Which entities are most connected? (likely the dominant companies)
- **Surprising paths**: Drug A → Target B → Pathway C → Disease D (non-obvious indication expansion)

This replaces the "build a Neo4j knowledge graph" proposal with something that runs locally, requires no infrastructure, and produces a navigable visual + queryable JSON.

---

## Part 5: Concrete Implementation Plan

### Phase 1: Knowledge Compilation (2-3 weeks) — HIGHEST IMPACT

**Goal**: After a landscape run, produce a persistent wiki article that future sessions can reason over.

```python
# cli_anything/cortellis/skills/landscape/recipes/compile_dossier.py
#
# Reads: raw/<indication>/*.csv, *.json, strategic_scores.csv, narrate_context.json
# Writes: wiki/indications/<indication>.md, wiki/INDEX.md (updated)
#         wiki/companies/<company>.md (created/updated for top players)
#         wiki/drugs/<drug>.md (created/updated for key drugs)
#
# Format: YAML frontmatter + [[wikilinks]] + reasoning scaffolds
# Trigger: Step 15 in landscape SKILL.md, after narrate.py
```

Key decisions:
- Wiki lives at project root: `wiki/` (gitignored, user data)
- INDEX.md is the master nav — loaded at session start
- Articles use `last_compiled` + `source_freshness` in frontmatter
- Cross-references via `[[drug-name]]` wikilinks

### Phase 2: Freshness-Aware Routing (1-2 weeks) — QUICK WIN

**Goal**: Don't re-fetch data that's already fresh.

```python
# cli_anything/cortellis/core/cache_manager.py
#
# check_freshness(indication, max_age_days=7) -> FreshnessResult
#   - reads wiki/indications/<indication>.md frontmatter
#   - returns FRESH (skip fetch), STALE (re-fetch), MISSING (full run)
#
# Integration: skill_router.py gets a fast-path:
#   if fresh wiki article exists → answer from wiki
#   else → run full skill pipeline → compile → update wiki
```

The `freshness.json` infrastructure already exists in `strategic_scoring.py:475` — currently display-only. Make it load-bearing.

### Phase 3: Session Memory (2-3 weeks) — ACCUMULATING INTELLIGENCE

**Goal**: Each analysis enriches a growing knowledge base.

Adapt the Claude Memory Compiler pattern:
- **flush**: After each `/landscape`, `/pipeline`, or `/drug-profile` run, extract key findings into `daily/YYYY-MM-DD.md`
- **compile**: Periodically synthesize daily logs into wiki articles
- **inject**: Session-start hook loads `wiki/INDEX.md` into context
- **lint**: Weekly health check — stale articles, contradictions, orphans

This means the system gets smarter with use. The 5th obesity analysis builds on insights from the previous 4.

### Phase 4: Temporal Diff (2-3 weeks) — "WHAT CHANGED?"

**Goal**: Track pipeline evolution over time.

```python
# cli_anything/cortellis/skills/landscape/recipes/diff_landscape.py
#
# compare_snapshots(indication, date_a, date_b) -> ChangeReport
#   - New drugs entering pipeline
#   - Phase advancements / failures
#   - New deals
#   - CPI ranking changes
#   - Company position shifts
```

Version `raw/` by date. Diff reports become wiki articles themselves: `wiki/landscapes/obesity-changes-2026-04.md`.

### Phase 5: Graphify Integration (1-2 weeks) — STRUCTURE DISCOVERY

**Goal**: Automatically discover entity relationships.

```bash
pip install graphifyy
graphify wiki/ --mode deep
# Produces: graph.html (visual), GRAPH_REPORT.md (key nodes), graph.json (queryable)
```

Run after compile step to surface non-obvious connections across the wiki.

### What We Skip

| Approach | Why Skip |
|----------|----------|
| **Fine-tuning** | Claude with compiled context outperforms fine-tuned 7B. Cortellis data licensing unclear. |
| **Vector DB / RAG** | At pharma KB scale (<500 articles), INDEX.md + wikilinks beat cosine similarity. Revisit at 2,000+ articles. |
| **Neo4j / heavy graph DB** | Graphify + NetworkX runs locally, zero infra. Landscape data is <2,000 nodes. |
| **Specialized sub-agents** | Fragments reasoning context. Best landscape analyses require cross-domain reasoning (pipeline + deals + trials). |
| **smolagents / LangChain** | You already have the best harness (Claude Code + OMC). Switching frameworks adds abstraction without value. |
| **LLM-as-Knowledge-Base** | Zero-hallucination requirement for pharma. The API is truth; the wiki is compiled truth; the LLM reasons over both. |

---

## Part 6: What This Looks Like In Practice

### Today
```
User: "What's the competitive landscape for obesity?"
System: [50+ API calls, 5+ minutes, produces CSVs in raw/obesity/, narrates, done]
        [Next session: starts from scratch, no memory of this analysis]
```

### After Phase 1-3
```
User: "What's the competitive landscape for obesity?"
System: [Checks wiki/indications/obesity.md — compiled 3 days ago, FRESH]
        [Loads dossier into context — 47 drugs, CPI rankings, deal patterns]
        "Based on our compiled landscape (last updated April 4):
         Novo Nordisk leads with CPI 87.3 (12 drugs, 8 launched).
         Key shift since March: Boehringer entered with survodutide (Phase 3).
         Deal velocity: 3 new licensing deals in last 30 days, average $420M.
         [[See full dossier: wiki/landscapes/obesity-2026-04-04.md]]"
        [Answered in 2 seconds, zero API calls]

User: "How does that compare to their position in MASH?"
System: [Loads wiki/indications/mash.md — also fresh]
        "Cross-landscape comparison:
         Novo Nordisk: CPI 87.3 (obesity, Tier A) vs CPI 61.2 (MASH, Tier B)
         Their MASH position is weaker — only 3 drugs vs 12 in obesity.
         However, semaglutide Phase 3 MASH data expected Q3 2026...
         [[See: wiki/companies/novo-nordisk.md]]"
        [Still zero API calls — cross-referenced from compiled wiki]

User: "What changed in the last month?"
System: [Loads wiki/landscapes/obesity-changes-2026-04.md]
        "Pipeline changes (March 7 → April 7):
         +2 new Phase 1 entries (both oral small molecules)
         +1 Phase 2 → Phase 3 advancement (survodutide)
         -1 Phase 2 discontinuation (Company Y, undisclosed reason)
         Deal activity: 3 new deals, $1.2B total projected value"
```

---

## Part 7: The Bigger Picture

What we're building is not "a CLI with AI features." It's a **pharmaceutical intelligence operating system** where:

1. **The Cortellis API** is the filesystem — the source of truth for raw data
2. **The wiki/** is compiled memory — pre-reasoned, cross-referenced, navigable
3. **The agent harness** (Claude Code + OMC) is the kernel — orchestrating tools, managing context, enforcing permissions
4. **The analyst** is the user — asking strategic questions, not writing queries
5. **Graphify** is the structure discovery engine — finding connections humans miss
6. **The memory compiler** is the learning loop — each session makes the system smarter

This maps directly to Karpathy's vision: the LLM is the kernel of a new operating system where **context is RAM, compiled knowledge is the executable, and the API is the filesystem**.

---

## References

- [Karpathy: LLM Knowledge Bases (gist)](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
- [Karpathy: Context Engineering > Prompt Engineering](https://x.com/karpathy/status/1937902205765607626)
- [Anthropic: Effective Harnesses for Long-Running Agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)
- [LangChain: Anatomy of an Agent Harness](https://blog.langchain.com/the-anatomy-of-an-agent-harness/)
- [Graphify](https://github.com/safishamsi/graphify) — NetworkX + Leiden + tree-sitter knowledge graphs
- [Claude Memory Compiler](https://github.com/coleam00/claude-memory-compiler) — Karpathy pattern for Claude Code
- [PharmAgents (bioRxiv 2026)](https://arxiv.org/html/2503.22164v1) — Multi-agent drug discovery
- [AAAI 2025: RAG-Enhanced LLM Agents for Drug Discovery](https://arxiv.org/abs/2502.17506)
- [The Virtual Biotech (bioRxiv 2026)](https://www.biorxiv.org/content/10.64898/2026.02.23.707551v1) — Multi-agent harness for therapeutic discovery
