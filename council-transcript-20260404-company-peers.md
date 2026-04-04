# LLM Council Transcript — Company Peers Skill

**Date:** 2026-04-04
**Question:** Is the `/company-peers` skill complete enough for production use? What gaps exist?

---

## Framed Question

The `/company-peers` skill benchmarks a pharma company against its peers. It has 4 recipe scripts, reuses the pipeline's company resolver, and uses the company-analytics API. It identifies peers by searching launched drugs in the company's top 3 indications, then compares pipeline success rates, first-in-class drugs, and deals. The skill has never been counciled before.

---

## Advisor Responses

### The Contrarian

Not production-ready. Three blockers: (1) bare `except Exception: return []` silently swallows all errors — users get empty peer list with no indication of failure. (2) Report generator reads `peers_ind*.json` files that SKILL.md never instructs creating — broken dependency. (3) Peer identification limited to Launched drugs (`--phase L`) excludes Phase 3 competitors — strategically misleading for competitive positioning.

Also: no manifest/integrity checking, no credential check, no cross-skill hints. Step 4 marked "optional" with no decision criteria creates inconsistent outputs across runs.

### The First Principles Thinker

The core question is "what makes someone a real competitor?" Current answer: "who else has launched drugs in same indications" — a proxy, not the thing itself.

Five gaps: (1) Launched-only bias ignores pipeline threats — Phase 3 assets are 2-3 year market competitors. (2) Indication ID matching too narrow — mechanism overlap is often more predictive. (3) Metrics show size not positioning (active drugs, deals count). (4) No stage-weighting — fading competitor scored same as growing one. (5) Self-referential gap — report shows peers but doesn't position the company within its own peer set.

The skill surfaces a peer list. It doesn't yet answer "how do we compare" — the actual question.

### The Expansionist

Functionally solid but playing defense. Missing: forward-looking signals (trial momentum via trials search), technology platform intelligence (company-analytics technologies endpoint), network effects (partnership-network skill), deal terms (deals-intelligence), emerging peers (Phase 2 companies as future competitors + acquisition targets).

Next version should add two more recipes: forward-looking (trial momentum + technology platform) and relational (deals intelligence + partnership network). That doubles strategic value without rebuilding what works.

### The Outsider

Peer finding only looks at approved drugs — most dangerous competitors are those not yet approved. Overlap score ignores stage. "Top 10" is arbitrary — niche companies have 3 peers, large pharma have 40. Success rate undefined (Phase 2→3? Overall?). No financial dimension (revenue, market cap, R&D spend). Head-to-head tool depends on this peer selection but criteria too narrow to trust.

### The Executor

Two concrete bugs plus several gaps.

BUG 1: find_peers.py outputs flat JSON to peers.json but report generator reads peers_ind*.json with company search response schema (companyResultsOutput.SearchResults.Company) — incompatible filename AND schema. Peer table always empty.

BUG 2: find_peers.py returns (name, drug_count, overlap) but report expects (@id, @name, Country, Drugs.@activeDevelopment, Deals.@current) — schema mismatch produces empty rows even if filename fixed.

GAP: Step 4 "optional" but Step 5 needs peer IDs from it — undocumented dependency.

Monday fix: rewrite report generator lines 118-152 to read peers.json directly using the flat array schema.

---

## Peer Reviews

### Anonymization Mapping
- Response A = The Contrarian
- Response B = The First Principles Thinker
- Response C = The Expansionist
- Response D = The Outsider
- Response E = The Executor

### Review 1
**Strongest: E** — concrete, reproducible bugs. Falsifiable claims, not opinions.
**Blind spot: E** — focuses on plumbing, says nothing about strategic framing.
**All missed:** Schema contract between skills as a first-class concern.

### Review 2
**Strongest: B** — attacks root assumption that launched-drug overlap = competitive threat.
**Blind spot: B** — no prioritization between strategic enhancement and correctness fix.
**All missed:** Data freshness. Cortellis has known lag. Stale approvals compound Launched-only bias.

### Review 3
**Strongest: A** — silent `except Exception: return []` is the most dangerous production characteristic.
**Blind spot: A** — bundles blockers with nice-to-haves.
**All missed:** Observability. No logging, no audit trail, no reproducibility.

### Review 4
**Strongest: D** — "Top 10 is arbitrary" underrated insight. Breaks at niche and large-pharma tails.
**Blind spot: D** — financial data (revenue, market cap) not in Cortellis scope.
**All missed:** User can't interpret methodology — selection criteria invisible.

### Review 5
**Strongest: E** — actionable Monday fix.
**Blind spot: C** — feature roadmap not production readiness assessment.
**All missed:** No test fixture = silent regression on any change.

---

## Chairman's Synthesis

### Where the Council Agrees

Every advisor concluded NOT production-ready. Three convergence points:
1. Filename/schema mismatch is a hard breakage — fires on every run
2. Launched-only peer search is a strategic liability
3. Silent error handling masks all failures

### Where the Council Clashes

Severity framing: Executor sees schema bug as bounded Monday fix. First Principles sees Launched-only scope as the deeper problem. Both are right for different horizons.

Depth of "peer" concept: Contrarian/Outsider want correctness. First Principles wants reconceptualization. Expansionist wants forward-looking signals. These belong to different release milestones.

### Blind Spots the Council Caught

1. No schema contract between find_peers.py and report generator
2. Data freshness unaddressed — Cortellis approval lag compounds bias
3. No observability — no logging, no audit trail, no reproducibility
4. Methodology opaque to users — "Top 10" with no explanation
5. No test fixtures — regressions go undetected

### The Recommendation

Do not ship. Fix in two phases:

Phase 1 (Make it work): Fix schema mismatch, replace bare except, add credential check, document Step 4 dependency.

Phase 2 (Make it credible): Expand to Phase 2/3 peers, document methodology in output, add data timestamps, cross-skill hints.

### The One Thing to Do First

Fix the schema contract between find_peers.py and the report generator. Rewrite the report to read peers.json directly using the flat JSON schema that find_peers.py actually produces. Until the basic data flow works, nothing else matters.
