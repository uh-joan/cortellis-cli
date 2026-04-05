# LLM Council Transcript — Landscape Strategic Intelligence Layer

**Date:** 2026-04-04
**Question:** What strategic intelligence layer should we add to the /landscape skill?

---

## Framed Question

The /landscape skill currently generates comprehensive data: 502 drugs across 5 phases, 30 companies, 200 deals, 1,536 trials, mechanism density, 1,838 attrited drugs. But it's a DATA DUMP — presents what exists without telling users what it MEANS. What analytical layer transforms it into a competitive intelligence briefing a pharma exec can act on?

---

## Advisor Responses

### The Contrarian
Build computational analytics first: Competitive Position Index (phase-weighted count + mechanism diversity + deal velocity + trial intensity), Crowding vs Attrition matrix per mechanism. "Never let the LLM substitute for the math." Claude narrates computed results. The analytical backbone must be deterministic Python.

### The First Principles Thinker
Anchor to 4 executive decisions: enter/expand, partner/acquire, double down/cut, differentiate. Build: mechanism-phase density matrix, attrition-adjusted opportunity (group by mechanism + phase of failure), momentum vectors, concentration risk. Output should be SHORTER not longer.

### The Expansionist
6 analytical products: (1) White Space Map, (2) Company Strategy Profiles (archetypes: Broad Platform, Focused Bet, Fast Follower, Acquirer), (3) Mechanism Lifecycle Analysis (emergence/hype/shakeout/maturation), (4) Deal Intelligence (leading indicator), (5) Trial Velocity Dashboard, (6) Attrition Risk Scorecard.

### The Outsider
Finance analogy — scoring model → ranked lists → narrative. Three axes: Pipeline Strength, Momentum, Risk. 2x2 company matrix: Leaders/Fading Giants/Rising Challengers/Struggling. Scenario analysis: "what if lead drug fails?" — recompute rankings. Two-page output + appendix.

### The Executor
3 scripts: strategic_scoring.py (~200 lines), opportunity_matrix.py (~150 lines), strategic_narrative.py (~100 lines). Two days for prototype. Compute first, narrative second.

---

## Peer Reviews

### Anonymization: A=Contrarian, B=First Principles, C=Expansionist, D=Outsider, E=Executor

Review 1: Strongest A. All missed: data freshness — stale data + strategic layer = false precision.
Review 2: Strongest B. All missed: no iteration/drill-down capability.
Review 3: Strongest C (novel archetypes + lifecycle). All missed: no validation mechanism.
Review 4: Strongest D (scenario analysis most sophisticated). All missed: cross-skill integration.
Review 5: Strongest E (actionable). All missed: configurability by therapeutic area.

---

## Chairman's Synthesis

### Where the Council Agrees
All converge on: compute first, narrate second. No one proposed letting LLM generate conclusions from raw data. Also: current output is too long and too flat, attrition data is most underused asset.

### Where the Council Clashes
Scope: 2-3 scripts (A/E) vs 6 products (C). The clash is about sequencing, not philosophy.

### Blind Spots
1. Data freshness (stale data = false precision)
2. Configurability (oncology vs rare disease need different weights)
3. No validation (how do you know CPI is predictive?)
4. No iteration model (one-shot vs drill-down)
5. Cross-skill integration (/drug-comparison, /mechanism-explorer exist)

### The Recommendation
Build in 3 phases:
- Phase 1 (~3 days): strategic_scoring.py — CPI, mechanism crowding, momentum. Pure Python.
- Phase 2 (~1 week): opportunity_matrix.py — mechanism-phase heatmap, white space, attrition risk. Parameterized weights.
- Phase 3 (~1 week): strategic_narrative.py — structured LLM prompts for 2-page briefing + scenario analysis.

### The One Thing to Do First
Write strategic_scoring.py. Compute CPI from existing CSVs. Validate against known competitive dynamics for 3 indications. If the math doesn't pass the smell test, stop.
