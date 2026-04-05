# LLM Council Transcript — Asthma Output Verification

**Date:** 2026-04-05
**Question:** Does the /landscape skill's strategic layer (as shown in actual asthma outputs) fulfill the original council recommendation?
**Previous baseline:** 65% (council-transcript-landscape-verification-20260404.md)

---

## Final Alignment Score: 78%

Up from 65% baseline (+13 points). Ship v0.9 after hardening sprint.

**Chairman's adjustment:** Advisor average was 83%, but the domain expert's structural critique of the scenario model should outweigh polish-focused reviews. When domain and strategy disagree on a strategy artifact in a domain context, domain wins.

---

## Advisor Scores

| Advisor | Score | Key Insight |
|---------|-------|-------------|
| Strategy Consultant | 88% | "M&A-grade insight, ship it" |
| Data Science Skeptic | 82% | "Compute-first honored, precision concerns" |
| Pharma Domain Expert | 78% | "Leader rankings correct, scenario model naive" |
| Product Manager | 85% | "4/5 blind spots closed, need validation harness" |
| Chairman (adjusted) | **78%** | "Domain expert's critique is load-bearing" |

---

## What's Fulfilled (Council Agreement)

- Compute-first, narrate-second (CPI tiers A/B/C/D replace false decimal precision)
- 4 executive decisions anchored with concrete targets
- Scenario analysis delivers non-obvious insight (GSK exit → Chiesi inheritance)
- Output is 2 pages, shorter not longer
- Data freshness watermarks throughout
- 5 therapeutic area presets (default/oncology/rare_disease/neuro/metabolic)
- Cross-skill composition (swot_composition.md)
- 4 of 5 original blind spots closed

## What Still Falls Short

1. **Scenario library is thin** — only "top company exits", need 3-5 scenario types
2. **GSK-exit scenario is mechanism-overlap naive** — real divestments go to specialty buyers
3. **No validation harness** — footer "validate against expertise" is a buck-pass
4. **Domain-naive recommendations** — U Tokyo as partner target, no LOE layer, no severity segmentation
5. **Preset-to-output traceability invisible** downstream

---

## Blind Spots (Peer Reviews)

1. **Asthma is the easy case** — mature, consolidated, stable. Not stressed against fragmented indications
2. **The GSK-exit insight may be a model artifact** — mechanism-overlap math, not divestment logic
3. **No reproducibility check** — can same query produce same tiers tomorrow?
4. **No user model** — BD analyst? VP? Consultant? Different users need different layers
5. **65% baseline is self-referential** — delta measures calibration drift, not ground truth

---

## Chairman's Recommendation

**Ship v0.9 after scoped hardening sprint. Do not rebuild. Do not call done.**

### Hardening sprint (v0.9 blockers):
1. Fix divestment scenario: overlap × specialty-buyer-fit
2. Add reproducibility test (24h re-run, diff tiers)
3. Stress test on fragmented indication (IPF or rare CNS)
4. Add preset provenance tags to recommendations
5. Validation harness as explicit ticket with owner, not a footer

### Deferred to v1.0:
- LOE/biosimilar layer
- Scenario library expansion (3-5 types)
- Therapeutic area-specific domain tuning (respiratory preset)

---

## The One Thing to Do First

**Fix the divestment scenario model.**

Not the biggest gap — traceability and validation are arguably bigger — but the only flaw that makes the skill **actively misleading**. Every other shortcoming produces an incomplete artifact; this one produces a confidently-wrong artifact with a named company attached.

Replace overlap-only with overlap × specialty-buyer-fit. Re-run asthma. If Chiesi is still the answer, defensible. If it changes to Covis or a specialty player, the original headline was the artifact the domain expert warned about — caught before a user did.
