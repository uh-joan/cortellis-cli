# User Value Brainstorm: AI-Native Pharma Intelligence

> Branch: `explore/ai-native-architecture` | Date: 2026-04-07

---

## The Core Tension

The pharma CI industry is **70% data gathering, 30% analysis**. Everyone wants the inverse. Your system already flips this for single-indication snapshots — but the real work happens *between* snapshots, *across* indications, and in the *translation* from data to strategic action.

> "We're very data rich, but we're still struggling to have high-value insights."
> — Jason Smith, CTO of AI & Analytics, Within3

---

## Five Personas, Five Pain Stories

### 1. The BD&L Associate — "I have 48 hours to evaluate this deal"

**Their real day**: A licensing opportunity lands from a biotech. The BD associate needs: competitive landscape context, comparable deal terms, head-to-head clinical comparison, and a preliminary recommendation. They open Cortellis, Evaluate Pharma, DealForma, ClinicalTrials.gov, and three broker reports on AlphaSense. They reconcile compound names across databases. They build a comparison table in Excel. They format slides. 48 hours gone, half of it on data assembly.

**Current system pain**:
- No head-to-head drug comparison (`/compare drug1 vs drug2 vs drug3` doesn't exist)
- Deals data shows types and counts but **never financial terms** — the landscape skill calls basic `deals search`, not `deals-intelligence` which has upfront/milestone/royalty data
- No "deal comp table" — the most-requested BD artifact
- Must run `/drug-profile` three separate times and mentally assemble the comparison

**What 10x looks like**:
```
> /deal-eval survodutide --indication obesity

Loading compiled obesity landscape (April 4, fresh)...
Loading drug profile for survodutide...
Pulling 8 comparable GLP-1/glucagon deals from deals-intelligence...

DEAL EVALUATION MEMO: Survodutide (Boehringer Ingelheim)

Competitive Position: 4th entrant in dual-agonist mechanism
  - Behind: semaglutide (approved), tirzepatide (approved), orforglipron (Phase 3)
  - Differentiation: GLP-1/glucagon dual vs GIP/GLP-1

Comparable Deals (last 24 months):
  Asset          | Stage | Upfront | Milestones | Royalties
  ─────────────────────────────────────────────────────────
  amycretin      | Ph2   | $100M   | $1.9B      | mid-teens
  pemvidutide    | Ph2   | $75M    | $1.3B      | low-teens
  ...

Recommendation: Mechanism is crowding. Window closing.
Sources: [Cortellis drug records], [Deals-Intelligence API], [Compiled landscape]
```

**Time: 2 minutes instead of 2 days.**

---

### 2. The Portfolio Strategist — "Which of our 8 focus areas has the best opportunity?"

**Their real day**: They manage the company's therapeutic focus across multiple indications. Every quarter, they need a portfolio-level view: where are we strong, where are we weak, where should we allocate resources, where should we look for in-licensing targets. They run the same landscape analysis for each area, then manually build a cross-indication comparison in Excel.

**Current system pain**:
- **Zero cross-portfolio capability** — each landscape lives in its own `raw/<indication>/` silo
- CPI scores are explicitly "not comparable across diseases" (strategic_briefing.md warns this)
- No portfolio watchlist concept — must manually run each indication one at a time
- No way to answer "which area has the most white space?" without running 8 separate analyses and comparing manually
- 14 landscape directories already exist in `raw/` but they're islands

**What 10x looks like**:
```
> /portfolio "Metabolic" --areas obesity,t2d,mash,cardiovascular

Loading compiled landscapes (all fresh within 7 days)...
Cross-portfolio analysis:

                 Obesity    T2D       MASH      CV
Drugs in dev     478        612       203       891
White space      ██░░░░     ░░░░░░    ██████    ███░░░
Deal velocity    ▲ high     → stable  ▲▲ surge  → stable
Our position     Tier A     Tier A    Tier C    Tier B

STRATEGIC SIGNAL: MASH has highest white space + surging deal
velocity + weakest current position = biggest opportunity gap.

Recommended action: Prioritize MASH in-licensing screen.
3 target assets identified in compiled KB: [survodutide,
resmetirom analog, THR-β agonist-2]
```

**Answered in 30 seconds from compiled wiki. Zero API calls.**

---

### 3. The CI Analyst — "What changed since my last report?"

**Their real day**: They produce weekly competitor briefs and quarterly landscape reports. The industry standard format is **"What's New / So What / What's Next"**. They triage hundreds of email alerts from Cortellis, Citeline, and Google Alerts per week. They manually determine which alerts are strategically significant. They rebuild the same landscape in new slides for R&D, commercial, and BD — three audiences, same data, different framing.

**Current system pain**:
- **No change detection whatsoever** — each run overwrites `raw/<indication>/` with no versioning
- No diff capability ("3 new Phase 2 entries since last run" is impossible to surface)
- The `freshness.json` tracks when data was fetched but doesn't trigger re-fetches or comparisons
- No export to deliverable formats — output is markdown/CSV, but CI analysts deliver PowerPoint and Excel
- No audience-aware formatting — analyst gets the same output a VP would get
- No automated monitoring or scheduled runs

**What 10x looks like**:
```
> /landscape obesity --diff

OBESITY PIPELINE CHANGES (March 15 → April 7, 2026)

NEW ENTRIES:
  + Drug X (Company Y) — Phase 1, oral small molecule, novel MoA
  + Drug Z (Company W) — Phase 1, peptide, GLP-1/GIP/glucagon triple

PHASE ADVANCES:
  ▲ survodutide: Phase 2 → Phase 3 (Boehringer, March 22)

DISCONTINUED:
  ✗ compound-ABC (Company Q) — Phase 2 suspended, safety signal

DEAL ACTIVITY (3 new):
  - Company A ↔ Company B: licensing, $420M total, March 28
  - Company C acquisition of Company D pipeline, April 2
  - Company E → Company F: co-development, undisclosed

STRATEGIC IMPLICATIONS:
  Triple-agonist mechanism emerging (2 new Phase 1 entries).
  Crowding in dual-agonist space increasing — 4th Phase 3 entrant.
  Deal velocity accelerating (3 deals in 23 days vs 2/month avg).

> /export pptx --template quarterly-update
Saved: obesity-update-2026-Q1.pptx (12 slides)
```

---

### 4. The Clinical Development Lead — "I need competitive context for our regulatory meeting Tuesday"

**Their real day**: Preparing for an FDA Type B meeting or an advisory committee. They need to know: what endpoints are competitors using, what trial designs are in play, what's the regulatory precedent for this indication, what are the upcoming PDUFA dates. They pull from ClinicalTrials.gov, FDA.gov, and Cortellis — manually cross-referencing.

**Current system pain**:
- Trial data is **aggregate only** — "5,888 recruiting trials" but no specific trial IDs, endpoints, or completion dates
- **Regulatory module is never called** by any skill — `regulations search` exists in the CLI but landscape/drug-profile don't use it
- No regulatory timeline view (PDUFA dates, EMA opinions)
- No trial design comparison (endpoints, patient populations, comparator arms)
- Drug profile shows 10 trials but without expected readout dates

**What 10x looks like**:
```
> /landscape obesity --view regulatory

REGULATORY TIMELINE: Obesity (next 18 months)

Q3 2026  ● semaglutide 2.4mg — PDUFA (CV label expansion)
         ○ survodutide — Phase 3 primary readout expected
Q4 2026  ○ orforglipron — Phase 3 completion expected
Q1 2027  ● tirzepatide — EU MAA decision (sleep apnea)
H1 2027  ○ orforglipron — NDA submission expected

TRIAL DESIGN COMPARISON (Phase 3, active):
  Drug          | N     | Primary Endpoint     | Comparator | Duration
  ──────────────────────────────────────────────────────────────────
  semaglutide   | 4,500 | MACE                 | placebo    | 104 wks
  survodutide   | 3,200 | % body weight change | placebo    | 68 wks
  orforglipron  | 2,800 | % body weight change | sema 2.4mg | 72 wks

REGULATORY PRECEDENT:
  3 approved GLP-1 agonists for obesity (semaglutide, liraglutide, tirzepatide)
  FDA precedent: 5% body weight loss threshold for approval
  [[Sources: Cortellis regulatory search, FDA.gov]]
```

---

### 5. The VP / Executive — "I have 2 hours to prep for the board"

**Their real day**: They need a 5-slide summary covering 3 therapeutic areas. They ask the CI team, who spends a day reformatting existing analyses into executive-friendly slides. The VP's vocabulary is different from the analyst's — they don't want CPI scores, they want "are we winning or losing?"

**Current system pain**:
- Output vocabulary is analyst-grade, not executive-grade ("CPI 87.3, Tier A" vs "market leader")
- No visual output — ASCII bar charts don't go into board decks
- No multi-area summary — can't produce a 3-area overview in one artifact
- The strategic_briefing.md is the closest to executive-ready but still 78 lines of markdown with tables
- No PowerPoint, Excel, or PDF export — zero hits for these formats in any recipe

**What 10x looks like**:
```
> /board-brief "Metabolic Portfolio" --areas obesity,t2d,mash --slides 5

Generating executive brief...
Loading 3 compiled landscapes...

Slide 1: Portfolio Overview (bubble chart: areas by opportunity vs position)
Slide 2: Obesity — Market Leader (12 drugs, 3 blockbusters, low risk)
Slide 3: T2D — Strong Position (8 drugs, but LOE exposure 2028-2030)
Slide 4: MASH — Opportunity Gap (3 drugs, high white space, deal window)
Slide 5: Recommendation — Prioritize MASH BD, protect T2D lifecycle

Saved: metabolic-board-brief-2026-Q2.pptx
```

---

## The Eight Unmet Needs (Mapped to AI-Native Solutions)

| # | Unmet Need | Current State | AI-Native Solution | Enabling Tech |
|---|-----------|---------------|-------------------|---------------|
| 1 | **"What changed?"** | Every run is a cold start, overwrites previous data | Versioned snapshots + diff engine + "What's New / So What / What's Next" framing | Temporal layer, compiled KB |
| 2 | **Cross-portfolio comparison** | Each indication is an island, CPI not comparable | Normalized cross-indication scoring, portfolio heatmaps | Compiled wiki with cross-landscape index |
| 3 | **Deal financial terms** | Deals show types/counts but no $$$ | Wire `deals-intelligence` into landscape + deal comp tables | Already in the API, just unwired |
| 4 | **Head-to-head drug comparison** | Run drug-profile 3x, compare mentally | `/compare` skill that auto-generates side-by-side tables | Compiled drug articles + diff |
| 5 | **Export to deliverable formats** | Markdown + CSV only | PowerPoint, Excel, PDF export with templates | python-pptx, openpyxl |
| 6 | **Regulatory timeline** | Regulatory module exists but no skill calls it | Regulatory milestone view with PDUFA dates, trial readouts | Already in the API, just unwired |
| 7 | **Strategic signal translation** | System says WHAT happened, analyst says WHY it matters | AI interprets events relative to your specific program and stage | Compiled KB enables reasoning over accumulated context |
| 8 | **Audience-aware output** | Same output for analyst, BD, and VP | Role-aware formatting: detailed (analyst), summary (BD), visual (exec) | Template system + LLM-driven reformatting |

---

## The Gaps That Knowledge Compilation Specifically Addresses

### Gap A: The Cold Start Problem
**Today**: Every session begins with zero context. The LLM knows nothing about obesity until it runs 50+ API calls.
**With compiled KB**: Session starts with `wiki/INDEX.md` injected. LLM immediately knows: 478 drugs in development, top 5 companies, mechanism distribution, recent deal velocity. Answers simple questions in seconds.

### Gap B: The Cross-Reference Problem
**Today**: "How does Novo Nordisk's position in obesity compare to their T2D position?" requires running two full landscapes and manual comparison.
**With compiled KB**: `wiki/companies/novo-nordisk.md` already has cross-indication CPI scores, deal history, and portfolio breadth. One file read.

### Gap C: The Institutional Memory Problem
**Today**: Analyst ran a deep obesity analysis in March. In April, they run it again from scratch. The March insight that "triple-agonist mechanism is emerging" is lost.
**With compiled KB**: March analysis is compiled into `wiki/indications/obesity.md`. April run produces a diff: "Since March analysis: 2 new triple-agonist entries confirm emerging trend."

### Gap D: The "I Wish I Knew What I Don't Know" Problem
**Today**: Analysts find what they search for. They don't discover what they didn't think to search for.
**With Graphify + compiled KB**: Graph analysis of the wiki surfaces: "Company X has quiet Phase 1 programs against 3 of the top 5 targets in your focus area — possible stealth strategy." The analyst didn't search for Company X. The graph found the pattern.

### Gap E: The Strategic Translation Gap
**Today**: System outputs data. Analyst provides interpretation. The step from "3 new Phase 2 entries" to "mechanism is crowding, window closing for licensing" is entirely human.
**With compiled KB**: The LLM reasons over accumulated context — previous landscape, deal patterns, historical phase transitions — and generates the "So What" and "What's Next" automatically. The analyst validates and refines, not writes from scratch.

---

## What Users Do OUTSIDE This Tool That Should Be INSIDE

| Activity | Current Tool | Why It's Outside | How to Bring Inside |
|----------|-------------|-----------------|-------------------|
| Deal financial benchmarking | DealForma, manual Excel | Landscape skill doesn't call deals-intelligence | Wire `deals-intelligence` expanded records |
| Sales forecasts / market sizing | Evaluate Pharma | Different vendor, different data source | Out of scope (different API), but could ingest as `raw/` sources for KB |
| Earnings call analysis | AlphaSense | Qualitative content, not in Cortellis | Could ingest key quotes as `raw/` sources for KB |
| Conference intelligence | Manual from posters/abstracts | `conferences search` exists but no skill calls it | Add `enrich_conference_data.py` recipe |
| Trial design comparison | ClinicalTrials.gov + manual | `trials search` exists with rich filtering but landscape only uses aggregate counts | Add `trial_design_comparison.py` recipe |
| Regulatory milestone tracking | FDA.gov + manual | `regulations search` exists but no skill calls it | Add `enrich_regulatory_milestones.py` recipe |
| Multi-source reconciliation | Excel (5 tabs, 5 databases) | Each database is separate | Compiled KB becomes the reconciled single source |
| Slide production | PowerPoint (manual) | No export capability | Add `export_pptx.py` with templates |

---

## The 8 "I Wish I Could..." Moments (From Industry Research)

These are real frustrations documented across pharma CI practitioners:

1. **"I wish I didn't have to open five tabs to answer one question about a competitor."**
   → Compiled KB: one wiki article per drug, cross-referenced

2. **"I wish the alert told me WHY it matters, not just that something changed."**
   → Strategic signal translation: LLM interprets events against compiled landscape context

3. **"I wish I could produce a conference readout in 2 hours instead of 2 days."**
   → Conference skill that ingests abstracts → compiles into KB → generates "What's New / So What"

4. **"I wish the landscape document updated itself instead of me rebuilding it every quarter."**
   → Freshness-aware KB that auto-refreshes stale articles, surfaces diffs

5. **"I wish BD could see the same data without me reformatting it for them."**
   → Audience-aware export: analyst view, BD view, exec view from same compiled KB

6. **"I wish I could ask in plain English and get a structured answer with sources."**
   → Already works via Claude Code chat. KB makes the answers richer and faster.

7. **"I wish the rNPV model refreshed when a competitor trial read out."**
   → Out of scope for Cortellis data, but temporal diff layer would trigger the signal

8. **"I wish I knew what I don't know."**
   → Graphify discovers non-obvious entity patterns. KB accumulates cross-session insight.

---

## The Killer Scenarios

### Scenario 1: "Monday Morning Refresh"
*Every Monday, the CI analyst needs to know what changed across 3 therapeutic areas.*

**Today**: Re-run 3 landscapes (15+ minutes each), visually compare with last week's output, write up changes manually. Total: ~2 hours.

**With KB**: `wiki/` articles are compiled and versioned. `/diff obesity,t2d,mash --since last-monday` produces a change report in 30 seconds. The analyst spends 15 minutes validating and adding "So What" commentary. Total: 20 minutes.

### Scenario 2: "The Deal Call"
*BD gets a call: "Company X wants to out-license their Phase 2 obesity asset. Interested?"*

**Today**: Run `/drug-profile`, run `/landscape obesity`, manually search for comparable deals, build a preliminary assessment. Total: 3-4 hours if the analyst knows the system well.

**With KB**: Obesity landscape is already compiled and fresh. Drug profile is one API call + compiled against existing KB context. Deal comps are pre-indexed from deals-intelligence. `/deal-eval <asset>` produces a 2-page memo in 5 minutes.

### Scenario 3: "Board Prep Thursday"
*VP needs a portfolio overview covering 4 therapeutic areas by Friday.*

**Today**: CI team spends Thursday running 4 landscapes, reformatting into slides. Delivers late Friday. VP presents Monday without having reviewed deeply.

**With KB**: 4 areas already compiled and fresh. `/board-brief --areas obesity,t2d,mash,cv --slides 8` generates a PowerPoint in 2 minutes. VP reviews Thursday evening, sends feedback, refined deck Friday morning.

### Scenario 4: "Conference War Room"
*ASCO starts Monday. 47 abstracts relevant to your oncology portfolio drop Sunday night.*

**Today**: Team of 3 analysts spends Monday-Wednesday reading abstracts, building comparison tables, writing summaries. Distributes Thursday. Competitors already acted.

**With KB**: Abstracts ingested as `raw/` sources Sunday night. Compiled against existing oncology landscape KB by Monday 6am. By 8am: "12 abstracts change competitive dynamics. Key signals: Company X showed superiority data vs SOC in 2L NSCLC. Company Y's biomarker selection strategy revealed." Team spends Monday morning on validation and strategic framing. Distributed by noon Monday.

### Scenario 5: "The Stealth Competitor"
*A mid-cap biotech has been quietly building a position in your therapeutic area.*

**Today**: Nobody notices until they announce a Phase 3 trial or a major deal. The alert arrives, but without portfolio context.

**With KB + Graphify**: The knowledge graph shows Company Z has Phase 1 programs against 3 of the top 5 targets in your area, all registered in the last 6 months. Graph analysis flags: "Emerging cluster: Company Z building broad target coverage in [indication]. Pattern resembles Vertex's 2019 CF build-out strategy." The analyst didn't search for Company Z. The system found the pattern.

---

## Summary: Where Value Lives

```
                        DATA              INSIGHT           ACTION
                        (Cortellis)       (Compiled KB)     (Deliverables)

Current system:         ████████████      ██░░░░░░░░░░      ░░░░░░░░░░░░
                        Strong            Partial            None

With AI-native KB:      ████████████      ██████████████     ████████████
                        Same data         Accumulated,       PPTX, XLSX,
                        (API is truth)    cross-referenced,  audience-aware,
                                          temporal,          role-specific
                                          discoverable
```

The data layer is solved. The insight layer is partially built (landscape scoring is excellent). The action layer — turning insight into deliverables, tracking changes over time, comparing across areas, surfacing what you didn't know to look for — is where the AI-native architecture creates transformative value.
