# LLM Council Transcript — Drug Profile Skill Completeness
**Date:** April 4, 2026

---

## Original Question
> Is the cli_anything/cortellis/skills/drug-profile complete enough? Do we have gaps?

## Framed Question
**Question:** Is the `/drug-profile` skill complete enough for production use, or does it have meaningful gaps?

**Context:** This is a deep drug profile skill for a pharmaceutical intelligence CLI (Cortellis). It generates comprehensive single-drug reports by collecting data from 10 API endpoints: drug record, SWOT (now AI-generated from 8 data sources via drug-swot collector), financials, development history, deals, trials, regulatory documents, competitive landscape (same mechanism), patent expiry, and biosimilar threats. It has 2 recipe scripts: `resolve_drug.py` (NER + search-based drug name resolution with combo/biosimilar penalty scoring) and `drug_report_generator.py` (report assembly with ASCII timeline, tables, and subprocess call to drug-swot evidence collector). The CLI wraps the Cortellis API (17 data domains, 80+ commands). There are 21 other specialized skills that handle adjacent use cases. The SWOT section was recently upgraded from stale Cortellis editorial content to an AI-synthesized strategic SWOT pulling from financials, trials, deals, patents, and competitors.

**What's at stake:** Drug profiles are a core pharma intelligence deliverable. BD analysts, portfolio managers, and licensing teams use them for deal evaluation, competitive positioning, and investment decisions. Gaps in coverage or misleading presentation directly impact business decisions worth millions.

---

## Advisor Responses

### 1. The Contrarian

Three structural flaws that will burn you in production:

**1. The output rule says "ALWAYS list ALL items in tables. No truncation." The code hardcodes truncation everywhere.** Deals: `[:10]`. Trials: `[:10]`. Regulatory: `[:10]`. Competitors: `[:15]`. Indications: `[:5]`. The rule and the implementation are in direct contradiction. A drug like semaglutide has dozens of trials. A user doing deal evaluation gets 10 rows and has no indication they're missing the rest. This is not a gap — it's a lie.

**2. The regulatory section is mislabeled and wrong by design.** Step 8 queries `cortellis regulations search` — that's the regulatory documents/news endpoint, not drug approval status. The section header says "Regulatory" and implies approval history, but it's actually returning press documents and regulatory filings. For a deal evaluation or investment decision, someone will read "3 regulatory documents" and think they understand the approval landscape. They won't. The actual approval status lives in the drug record fields, not this endpoint.

**3. The financial section truncates to 500 characters of a commentary field.** `DrugSalesAndForecastCommentary` is a narrative blurb. For a drug with peak sales in the billions, the actual revenue figures, forecast years, and market trajectory are almost certainly in structured sales data fields that this skill never touches. You're pulling a paragraph preview where a `/sales-forecast` skill exists that presumably does this properly. The skill's own output rules say "give exact numbers" — then delivers a truncated paragraph.

The `resolve_drug.py` logic is solid. The SWOT subprocess delegation is reasonable. The fatal problem is that the report generator was built for a demo, not production — it lies about completeness and mislabels critical data sections.

### 2. The First Principles Thinker

The question presupposes "completeness" is the right lens. It isn't. The real question is: what is a drug profile actually for?

Drug profiles serve three distinct use cases: deal evaluation, competitive positioning, investment decisions. These require fundamentally different information architectures. The current implementation builds one report and assumes it serves all three. That's the core problem — not any specific gap.

**Deal evaluation**: risk-adjusted value, IP cliff timing, competitive threats to peak sales. The current tool captures IP expiry and competitors but truncates financials at 500 chars and misses combination drug signals. Fatal for deal work.

**Competitive positioning**: mechanism-level landscape, pipeline gaps, timing windows. Limiting competitors to "launched + Phase 3 only" destroys the forward-looking picture. Phase 1/2 entrants are where positioning decisions live.

**Investment decisions**: regulatory risk, trial failure patterns, sales trajectory. The history timeline drops approvals and trial results — the two most investment-relevant event types — keeping only phase transitions. This is backwards.

The SWOT being AI-generated from 8 sources is sophisticated infrastructure pointed at the wrong target. A SWOT is an interpretive output, not a data collection exercise. Generating it from endpoints before the analyst has formed a view inverts the workflow.

The actual question: this isn't one skill. It's three skills wearing the same coat. The 500-char financial truncation, the Phase 3-only competitors, and the history filter aren't bugs — they're symptoms of building a general report when the use cases demand specificity.

### 3. The Expansionist

The limits are the opportunity map. Every hard cap in this implementation is a feature request waiting to be unlocked.

Deals capped at 10? Licensing intelligence is worth serious money. Bump that to 50+ with deal-type filtering (licensing vs. acquisition vs. collaboration) and you have a standalone M&A screening tool. Trials at 10 is almost a joke for oncology drugs that have 40+ active studies across histologies. Full trial landscape with enrollment status, geographic reach, and combination partner tracking is a different product tier entirely.

The financial extraction truncated to 500 chars is the most painful gap. Sales commentary is where the alpha lives - analyst surprises, guidance revisions, market share shifts. That's not a summary field, that's the core of an investment thesis.

But here's what nobody is saying: the drug-design enrichment for early-stage drugs is accidentally brilliant. That's the rarest, highest-value data in pharma intelligence - what does the molecule actually do at a biological level? Expanding that beyond early-stage to ALL drugs, adding ADMET properties, off-target profiles, and structural analogs, turns this into a pharmacology dossier that medicinal chemists and BD teams will pay for separately.

The 21 adjacent skills are the real unlock. Right now `/drug-profile` is a hub. Build automatic cross-linking - when competitors are identified, auto-trigger `/drug-comparison`. When regulatory documents surface, auto-invoke `/regulatory-pathway`. When deals appear, auto-pull `/deal-deep-dive`. That transforms a static report into a living intelligence graph where one query fans out across the entire skill ecosystem.

Production-ready for basic use. Dramatically under-exploiting its own infrastructure for power users.

### 4. The Outsider

Three concrete gaps that would trip up a first-time user or a high-stakes use case:

**1. The report silently truncates data without telling the analyst.** Deals cap at 10, trials at 10, competitors at 15, financials at 500 chars, SWOT entries at 3 per category, indications at 5, mechanisms at 3. The headers show totals ("Deals (47 total)") but the table only shows 10. An analyst scanning fast will miss that. For million-dollar deal evaluation, "we checked 10 of 47 deals" is a different thing than "we checked all 47 deals." The SKILL.md even says "ALWAYS list ALL items in tables. No truncation." — but the code truncates anyway. That's a direct contradiction.

**2. The competitive landscape is too narrow to be useful.** It only shows launched drugs with the same mechanism. An analyst doing competitive positioning needs Phase 2/3 pipeline threats, not just what's already on the market. A drug could look like a category leader in the output and actually face five Phase 3 challengers that never appear. The `competitors_p3.json` file is fetched but never rendered in the report.

**3. The ASCII timeline is nearly empty for most drugs.** It only renders "highest status change" events and "drug added." Any drug that had regulatory submissions, Phase 2 failures, label expansions, or acquisitions — none of that appears. For a drug like semaglutide with 15 years of history, the timeline will show maybe 4 lines. That's not a development timeline; it's a skeleton.

These aren't polish issues. They're gaps that would cause an analyst to make a wrong call.

### 5. The Executor

Not production-ready. Here are the specific blockers:

**Hard failures waiting to happen:**

1. `load_json` bare `except:` silently returns `None` for corrupted JSON, permission errors, disk issues — user gets a partial report with zero indication anything went wrong. For a deal evaluation deliverable, silent data loss is a trust killer.

2. `ascii_timeline()` only captures "Highest status change" and "Drug added". Approvals, label expansions, safety updates, trial completions — all dropped. The timeline for a drug like tirzepatide would show 4 entries and look embarrassingly thin compared to what Cortellis actually holds.

3. Financial section: 500-char truncation on `DrugSalesAndForecastCommentary`. For a launched drug, this cuts off mid-sentence. No actual sales figures, no forecast numbers — just a prose snippet. Someone using this for investment decisions is getting incomplete data with no signal that it's incomplete.

4. Step 10 (Drug Design enrichment) exists in SKILL.md but the report generator has no code path for it. The JSON files are never read. The step runs, writes files, they get ignored.

5. Competitive landscape is launched-only (`--phase L`). If you're profiling an early-stage asset, you get no competitive context at all — which is exactly when competitive intelligence matters most.

**What Monday morning looks like:**

Fix in this order: (1) add explicit error logging in `load_json`, (2) expand `ascii_timeline` to capture approvals and safety events, (3) wire Drug Design JSON into the report generator, (4) add a `--phase C3` competitor pass alongside the launched-only pass.

The resolver and the table structures are solid. The skeleton is right. But the data gaps in timeline and financials would get caught immediately by anyone who cross-checks the output against Cortellis directly.

---

## Peer Reviews

### Anonymization Mapping
- Response A = The Expansionist
- Response B = The Contrarian
- Response C = The First Principles Thinker
- Response D = The Outsider
- Response E = The Executor

### Peer Review 1

**Strongest: Response B (Contrarian)** — sharpest contradiction identification, regulatory query mismatch is a semantic bug that causes confident wrong conclusions, not just incomplete data. Response E is close but B's framing is more precise.

**Biggest blind spot: Response A (Expansionist)** — treats limitations as feature roadmap, never engages with contradictions. Optimism about upside isn't analysis.

**All missed:** Authentication and API failure handling at the network layer. Every response assumes the 10 API calls succeed. None asks: what happens when 3 of 10 calls fail mid-execution? Does the user get a partial report with no indication of missing sections? For deal evaluation and investment decisions, a silently partial report is a liability. Response E touches bare `except:` but frames it as a code smell, not as a data-integrity risk.

### Peer Review 2

**Strongest: Response E (Executor)** — only one identifying runtime reliability issues and providing prioritized fix order. Makes it actionable, not just diagnostic.

**Biggest blind spot: Response A (Expansionist)** — frames every gap as "feature request" without defining "basic use." Praises Drug Design enrichment as brilliant without noting Response E correctly identifies the output is never read.

**All missed:** Authentication and API failure modes. None asks what happens when an API key is missing, rate-limited, or returns 5xx. A partially-populated profile that looks complete is worse than a hard failure.

### Peer Review 3

**Strongest: Response E (Executor)** — most actionable. Names five concrete bugs with specificity and provides prioritized fix order. Uniquely caught Drug Design output never read.

**Biggest blind spot: Response A (Expansionist)** — treats production gaps as feature requests. Invents a positive about Drug Design without verifying it's consumed.

**All missed:** API failure handling at the skill boundary. None questioned whether the skill signals incompleteness to the caller when data is missing — critical for downstream automation.

---

## Chairman Synthesis

### Where the Council Agrees

**The skill is not production-ready.** All five advisors, including the most generous (Expansionist), identify structural problems. The convergence is unusually tight on three points:

1. **Truncation contradicts the skill's own rules.** SKILL.md says "ALWAYS list ALL items. No truncation." The code hardcodes `[:10]`, `[:15]`, `[:5]` limits everywhere, and the financial commentary is cut at 500 characters mid-sentence. Headers show totals like "Deals (47 total)" while tables show 10. This is not a style issue — it is the output lying about its own completeness. Four of five advisors flagged this independently.

2. **The competitive landscape is blind to the pipeline.** Only launched drugs with the same mechanism are shown. Phase 3 competitor data is fetched (`competitors_p3.json`) but never rendered. For early-stage drugs, this means zero competitive context. Three advisors identified this as causing wrong decisions.

3. **Drug Design enrichment is dead code in practice.** Step 10 runs the enrichment and writes files. The report generator never reads them. The Executor caught this; the Expansionist praised it as "brilliant" without verifying the output is consumed. The peer reviews correctly flagged this gap.

### Where the Council Clashes

**Is this one skill or three?** The First Principles Thinker argues drug profiles for deal evaluation, competitive positioning, and investment decisions are fundamentally different information products and should be split. The Executor and Contrarian treat it as one skill with bugs to fix. The disagreement is real: splitting use cases produces better outputs but triples maintenance surface. The pragmatic answer is that the current skill fails at all three use cases for the same reasons (truncation, missing data), so fixing the shared foundation comes before any split.

**Are the limits bugs or features?** The Expansionist frames every cap as a future feature request. Everyone else frames them as contradictions against the skill's own stated rules. The peer reviews unanimously sided against the Expansionist here — when your documentation promises no truncation and your code truncates, that is a bug, not a roadmap item.

### Blind Spots the Council Caught

**Silent partial failure is the worst outcome.** No individual advisor made this their primary point, but all three peer reviews converged on it: `load_json` uses a bare `except:` that returns `None`. When 3 of 10 API calls fail, the user receives a report that looks complete but is missing sections. There is no error logging, no incompleteness signal, no indication to the caller that data is absent. A report that looks authoritative but is silently missing financial data or regulatory information is more dangerous than a hard failure.

**The regulatory query is semantically wrong.** The Contrarian uniquely caught that the regulatory section queries `regulations search`, which returns regulatory documents and news, not drug approval status or history. The section heading implies approval landscape; the data is press clippings.

### The Recommendation

**Do not ship this for production decision-making.** The skill produces reports that look authoritative but silently omit data, truncate against their own stated rules, ignore fetched competitor pipelines, discard drug design enrichment, and misrepresent regulatory documents as approval history. For deal evaluation and investment decisions — the stated use cases — a confident-looking but incomplete report is actively harmful.

The skill has solid bones: the resolver works, the SWOT delegation from 8 sources is well-architected, and the 10-endpoint data collection is the right scope. The problems are all in the last mile — how collected data becomes the output report. This is fixable without rearchitecting.

### The One Thing to Do First

Replace the bare `except:` in `load_json` with proper error logging and add a "Data Completeness" header to the report output that lists which API calls succeeded and which failed. Every other fix (truncation, timeline, competitors, Drug Design rendering) is less urgent than ensuring the user knows when they are looking at an incomplete picture. A partial report labeled as partial is safe. A partial report labeled as complete is a liability.

---

*LLM Council — 5 advisors, 3 peer reviews, 1 chairman synthesis — April 4, 2026*
