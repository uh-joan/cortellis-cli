# LLM Council Transcript — Landscape Strategic Layer Verification

**Date:** 2026-04-04
**Question:** Is the /landscape strategic layer implementation aligned with the original council recommendation?
**Previous Council:** council-transcript-landscape-strategy-20260404.md

---

## Alignment Score: 65%

The implementation delivers the three scripts by name but substitutes the hardest requirement (LLM narration) with templating, ships unjustified weights as if they were science, and validates on cases that cannot fail.

---

## Advisor Responses

### The Contrarian
70% aligned but strategic_narrative.py is a sleight-of-hand. Council said "structured LLM prompts referencing scored data" — what shipped is deterministic templating. That's not discipline, it's avoidance. Validation on 2 known leaders is confirmation bias, not rigor. The LLM omission is a real retreat from the recommendation.

### The First Principles Thinker
Core primitives correct (math + scenario + decision anchoring). Scenario analysis nailed it — crown jewel. But CPI weights (20/30/20/15/15) are arbitrary with no documented justification. 490 lines vs estimated 200 suggests scope creep. Foundations solid, weight-justification and line-bloat warrant audit.

### The Expansionist
Scenario analysis is the crown jewel — lean into it. Build multi-company exit scenarios, mechanism-exit scenarios, entry scenarios. Cross-skill composition is the biggest missed multiplier (/landscape → /drug-comparison → /mechanism-explorer as a chain). Add --narrate flag as optional for LLM layer.

### The Outsider
Dumb questions: (1) What do I DO differently after reading this? "Novo #1" is known. (2) Is it actually SHORTER? (3) Why should I trust 93.3 vs 74.6 (false precision — use tiers). (4) Validation on known leaders only tells me what I knew. Scenario analysis is the one genuinely useful output.

### The Executor
70% aligned, production-shippable. 3 gaps: (1) Therapeutic area parameterization (2 days), (2) LLM narration layer as --narrate flag (3 days, deterministic default), (3) Validation harness on historical snapshots (2 days). Defer cross-skill integration to v2.

---

## Peer Reviews

### Anonymization: A=Contrarian, B=First Principles, C=Expansionist, D=Outsider, E=Executor

**Review 1:** Strongest B (weights arbitrariness is most concrete critique). Biggest blind spot: E (managerial theater — can't ship with arbitrary weights behind a flag). All missed: construct validity of CPI — are the 5 factors even the right 5?

**Review 2:** Strongest A (catches specification violation). Biggest blind spot: C (expansion before base is audited). All missed: weights should be DERIVED from historical data, not chosen. Every reviewer treats it as policy debate when it's empirical.

**Review 3:** Strongest D (what would user DO differently is the only user-grounded review). Biggest blind spot: A (audits the miss, ignores the surplus). All missed: schema contract for downstream skills. If scenario outputs aren't machine-consumable, it's a report generator not a primitive.

**Review 4:** Strongest A (called the sleight-of-hand). Biggest blind spot: C (expansion before adoption = shelfware). All missed: the counterfactual — what would user do without /landscape?

**Review 5:** Strongest C (cross-skill = 10x leverage vs 10% polish). Biggest blind spot: D (hiding scores destroys machine-readable contract). All missed: sequencing and cost — no reviewer estimated effort or ranked fixes.

---

## Chairman's Synthesis

### Where the Council Agrees
- Scenario analysis is the only genuinely novel output — crown jewel
- LLM omission is a regression, not a simplification
- Validation is theater — two known leaders is a mirror, not a test
- Cross-skill integration is the biggest missed multiplier (silently dropped)

### Where the Council Clashes
- Ship vs rebuild: 70% shippable (E) vs CPI construct may be invalid (A)
- Templating acceptable as fallback? Expansionist yes, Contrarian no
- Does false precision matter? Outsider yes for humans, Executor no for machines

### Blind Spots
1. Construct validity of CPI — are the 5 factors the right 5?
2. Weights should be learned from data, not legislated by committee
3. Schema contract missing — downstream skills have nothing to consume
4. No counterfactual — what would user do WITHOUT this tool?
5. No effort ranking — reviews without priorities are wishlists

### Prioritized Backlog (leverage ÷ effort)

1. **Publish JSON output schema** (0.5 day) — unblocks all cross-skill integration
2. **Derive CPI weights from historical data** (2 days) — regression on deal outcomes, launch success
3. **Audit 5 CPI factors for construct validity** (1 day) — justify the factor set
4. **Add --narrate as optional LLM pass** (3 days) — honors Phase 3 spec
5. **Build one cross-skill composition** (2 days) — /landscape → /drug-swot
6. **Therapeutic area presets** (2 days) — polish, not foundation
7. **Kill decimal precision** (10 min) — tiers A/B/C, not 93.3 vs 74.6

### The Recommendation
Do not ship /landscape as "strategic layer complete." Rebrand honestly as `/landscape --scenarios` (v0.1) and gate CPI outputs behind experimental flag until foundation is fixed. Scenario analysis alone justifies v0.1 release.

### The One Thing to Do First
Publish the JSON output schema for /landscape and commit it to the repo before touching another line of code. Half a day, unblocks everything else.
