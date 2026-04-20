# Knowledge Base Commands

Reference for commands that manage the wiki knowledge base: refreshing compiled articles, ingesting documents, browsing signals, and recalling insights.

---

## `cortellis wiki refresh` — Rebuild compiled articles

Refreshes the wiki without starting a chat session. Three tiers of increasing depth.

| Flag | Tier | What runs | LLM? |
|------|------|-----------|------|
| *(none)* | 1 — compile-only | Recompiles all wiki articles from existing `raw/` data | No |
| `--fetch` | 2 — fetch+compile | Re-fetches API data for drugs, targets, companies, then recompiles | No |
| `--full` | 3 — full refresh | Runs the full HarnessRunner workflow per entity, including LLM synthesis | Yes |

```bash
# Tier 1 — fast compile from cached data
cortellis wiki refresh

# Tier 2 — re-pull structured data, no LLM
cortellis wiki refresh --fetch
cortellis wiki refresh --fetch --type drug          # drugs only
cortellis wiki refresh --fetch --type drug,target   # multiple types

# Tier 3 — full pipeline including LLM synthesis
cortellis wiki refresh --full
cortellis wiki refresh --full --type indication     # indications only

# Preview without writing anything
cortellis wiki refresh --dry-run
cortellis wiki refresh --full --dry-run
```

**Supported types:** `drug`, `target`, `company`, `indication`, `conference`

**Tier 2 scope:** drugs, targets, companies only — indications and conferences require LLM steps (use `--full`).

**Tier 3 scope:** all types. Equivalent to running each `run-skill` for every known entity. Expected runtime: several hours for a large wiki.

**Scheduling example:**
```bash
# Nightly: re-fetch drugs and targets, no LLM
0 2 * * * cortellis wiki refresh --fetch --type drug,target

# Weekly: full refresh of all indications
0 3 * * 0 cortellis wiki refresh --full --type indication
```

---

## `cortellis run-skill changelog <indication>` — Pipeline history

Shows how a landscape has evolved over time — monthly phase counts, phase transitions, recent launches. No API calls at runtime; reads CSVs written during the last `/landscape` run.

```bash
cortellis run-skill changelog obesity
cortellis run-skill changelog MASH
cortellis run-skill changelog "non-small cell lung cancer"

cortellis run-skill changelog obesity --dry-run     # preview execution plan
```

**Prerequisite:** `/landscape <indication>` must have been run at least once.

**What you get:**
- Monthly snapshot table (every 3 months): Launched / Phase 3 / Phase 2 / Phase 1 / Discovery / Total
- Growth summary: absolute and % change over the period
- Recent Phase 3 entries: drug, date, prior phase, company
- Recent launches

**Also available as slash command:** `/changelog obesity`

---

## `cortellis run-skill enrich <indication>` — Fill deep profiles for priority entities

After running `/landscape`, the indication article is compiled but individual drug, company, and target profiles may still be stubs. `enrich` fills those gaps automatically — running `drug-profile`, `pipeline`, and `target-profile` for all priority entities missing a deep wiki article, then recompiling the indication and rebuilding the wiki index.

```bash
cortellis run-skill enrich obesity
cortellis run-skill enrich MASH
cortellis run-skill enrich "cardiovascular disease"

cortellis run-skill enrich obesity --dry-run     # preview what would run
```

**Prerequisite:** `/landscape <indication>` must have been run first — `enrich` reads the `enrichment_manifest.json` it produces.

**What gets profiled:**
| Entity type | Criteria |
|---|---|
| Drugs | Launched + Phase 3, normalized name, no existing deep profile |
| Companies | CPI tier A or B with score ≥ 15, no existing pipeline article |
| Targets | Mechanisms with ≥ 3 active drugs, wiki-resolvable, no existing target profile |

**Idempotent:** Re-running skips entities already profiled. Safe to run after partial failures.

**Workflow:**
```
enrich_drugs → enrich_companies → enrich_targets → recompile → wiki_refresh
```

**Web UI:** Each indication article shows a KB coverage callout (e.g. `KB coverage: 30% · 13/43 entities profiled`) with an **Enrich →** button. Hover over the entities count for a per-type breakdown. Turns green + disabled when coverage reaches 100%.

**Also available as slash command:** `/enrich <indication>`

---

## `cortellis run-skill ingest <file>` — Add internal documents to the wiki

Ingests any internal document as a wiki node with wikilinks to known entities (drugs, companies, targets, indications). Makes internal docs surface in `/signals` alongside Cortellis data.

```bash
cortellis run-skill ingest raw/internal/deal_memo_novo_nordisk.md
cortellis run-skill ingest raw/internal/expert_call_obesity_kol.txt
cortellis run-skill ingest raw/internal/bd_assessment_masld_2026.md

cortellis run-skill ingest raw/internal/deal_memo.md --dry-run
```

**Supported formats:** `.md`, `.txt`, `.csv` — convert `.pdf`/`.pptx` first with `pandoc`.

**Output:**
```
wiki/internal/<slug>.md    ← entity-linked article with [[wikilinks]]
```

**Also available as slash command:** `/ingest <file>`

---

## `cortellis run-skill ingest-internal <file> <indication>` — Ingest + merge into indication

Like `ingest` but also extracts commercial sections (market forecasts, epidemiology, physician insights, reimbursement, unmet need) and merges them directly into the indication wiki article in one step.

```bash
cortellis run-skill ingest-internal raw/internal/obesity/Obesity_Forecast.csv obesity
cortellis run-skill ingest-internal raw/internal/masld/Clarivate_MASLD_Epidemiology.pdf masld
cortellis run-skill ingest-internal raw/internal/obesity/GLP1_Physician_Insights.pptx obesity
```

**Supported formats:** `.md`, `.txt`, `.csv`, `.pdf`, `.pptx`, `.xlsx`

**Output:**
```
wiki/internal/<slug>.md           ← entity-linked article
wiki/indications/<indication>.md  ← updated with extracted commercial sections
```

**vs `/ingest`:** Use `ingest` for deal memos, expert call notes, general research — documents where you just want cross-linking. Use `ingest-internal` when the document contains structured commercial data (forecasts, market share, epidemiology numbers) that should live inside the indication article.

**Idempotent:** Safe to re-run — duplicate section headers are detected and skipped.

**Also available as slash command:** `/ingest-internal <file> <indication>`

---

## `/signals` — Morning intelligence briefing

Scans all compiled wiki articles and raw staging files for pipeline changes, emerging science, and high-confidence genetic evidence. No API calls — reads from `wiki/` and `raw/`.

```
/signals
```

**What it scans:**
```
wiki/indications/*.md          → phase count diffs vs previous compile
raw/drugs/*/biorxiv.json       → preprints < 60 days old
raw/targets/*/opentargets.json → disease associations ≥ 0.70
raw/*/press_releases_summary.csv → recent press releases
```

**Output ranked by severity (CRITICAL → HIGH → MEDIUM → LOW):**
- Pipeline shifts: phase count changes
- Emerging science: recent preprints across all profiled drugs/targets
- High genetic evidence targets: Open Targets scores ≥ 0.70
- Deal velocity from indication articles

```
wiki/SIGNALS_REPORT.md    ← overwrites on each run (timestamped)
```

---

## `/insights` — Recall accumulated findings

Surfaces key findings, scenarios, and strategic implications captured by the SessionEnd hook across all past sessions. No API calls — reads from `wiki/insights/sessions/`.

```
/insights
/insights --indication obesity
/insights --indication masld
```

**What it reads:**
```
wiki/insights/sessions/    ← session-derived insight files
wiki/log.md                ← chronological activity record
```

**What you get:**
- Key findings by indication (from past sessions)
- Open strategic questions still unresolved
- Scenarios flagged for monitoring
- Timeline of past analyses

---

## Wiki structure

All commands compile into `wiki/`. Articles cross-link with `[[wikilinks]]` and are readable in [Obsidian](https://obsidian.md) as a graph vault.

```
wiki/
├── INDEX.md                     ← master catalog (auto-maintained)
├── SIGNALS_REPORT.md            ← latest competitive signals
├── log.md                       ← chronological activity record
├── graph.json                   ← NetworkX knowledge graph
├── GRAPH_REPORT.md              ← entity clusters, god nodes, bridges
├── indications/<slug>.md
├── drugs/<slug>.md
├── targets/<slug>.md
├── companies/<slug>.md
├── conferences/<slug>.md
├── internal/<slug>.md           ← ingested documents
└── insights/sessions/           ← session-derived insights
```
