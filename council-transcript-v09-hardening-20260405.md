# LLM Council Transcript — /landscape v0.9 Hardening Sprint

**Date:** 2026-04-05
**Question:** Does the /landscape skill's v0.9 hardening sprint fulfill the prior council's recommendations (asthma verification, 78% alignment) and is v0.9 shippable?
**Previous baselines:** 65% (landscape strategy) → 78% (asthma verification) → **71% (this pass)**

---

## Final Alignment Score: 71%

**Down 7 points from the 78% baseline.** The five prior-council blockers were cleared in form (divestment fix landed, reproducibility test caught real non-determinism, fragmented-indication stress test passed, preset provenance tags shipped, harness exists) and the bonus work is real engineering. But the score drops because First Principles named a fatal methodological flaw that 4 of 5 peer reviewers independently ratified: three sprints of council-on-council validation have produced *consistency*, not *correctness*, and the "owner" blocker was delivered as a `@domain-reviewer` footer — ceremony, not accountability. Reality wins over process: the sprint hardened the machine against itself, not against a deciding human.

**Chairman's adjustment:** The advisor spread was wide (Executor "SHIP IT" vs Contrarian "not shippable" vs First Principles "wrong question"). Applying the prior council's rule — when domain and strategy disagree about a domain artifact, domain wins — here translates to *reality wins over process*. First Principles and 4/5 peer reviewers agreed the council loop is self-referential. That critique is load-bearing.

---

## Advisor Scores (chairman's reading)

| Advisor | Stance | Key Insight |
|---------|--------|-------------|
| The Executor | SHIP IT in 65 min | "Uncommitted code on a laptop is the biggest risk" |
| The Expansionist | SHIP + benchmark in 30d | "Adaptive tiers unlock $200K McKinsey-deck frontier" |
| The Outsider | BLOCK | "Math fixed, reader not. 'Score 2.52' means nothing" |
| The Contrarian | BLOCK v0.9, ship v0.9-rc1 | "Specialty-fit is theater; adaptive tiers are silent miscalibration" |
| The First Principles Thinker | WRONG QUESTION | "3 sprints, 0 users. Chiesi→SMB is consistency not correctness" |
| **Chairman (adjusted)** | **Ship internally; block public** | **"Need one decider in the room"** |

---

## What's Fulfilled (Literal Blocker Audit)

No advisor graded this directly — peer reviewers 1 and 4 flagged the oversight. On strict reading of the 5 prior blockers:

| # | Prior blocker | Status | Evidence |
|---|--------------|--------|----------|
| 1 | Fix divestment scenario: overlap × specialty-buyer-fit | **PASS** | Asthma top beneficiary is now Laboratoires SMB SA (Belgian specialty), not Chiesi. Unique-mechanism overlap × (1/(1+phase3plus/5)) × (1+0.01·min(total_drugs,5)) implemented in strategic_narrative.py + scenario_library.py. |
| 2 | Reproducibility test (24h re-run, diff tiers) | **PASS** | `test_strategic_reproducibility.py` 4/4 green. Caught real latent non-determinism (5 sorts without tiebreakers) and fixed. |
| 3 | Stress test on fragmented indication (IPF or rare CNS) | **PASS** | Full 14-step runs on IPF + ALS + I-O combo. Doc at `docs/fragmented_indication_stress_test.md`. Boehringer IPF #1 ground truth confirmed. |
| 4 | Preset provenance tags per recommendation | **PASS** | Every output has `*Preset: X — description*` header and `(preset: X)` suffix per recommendation. |
| 5 | Validation harness as explicit ticket with owner, not a footer | **FAIL** | `docs/validation_harness.md` exists with 5-indication test set and pass criteria. Owner is `@domain-reviewer` — a placeholder string, not a human. The prior council said "owner, not a footer" and received a footer with ceremony. |

**Strict score: 4 PASS, 1 FAIL.** Blocker 5 is the fulcrum of the 71% score.

### Bonus work (not in original blockers)

- `scenario_library.py` with 5 scenario types (top_exit, crowded_consolidation, loe_wave, new_entrant_disruption, pivotal_failure)
- `loe_analysis.py` — LOE/biosimilar proxy layer
- Adaptive percentile CPI tiers (triggered by stress-test finding of 95% Tier D collapse on IPF/ALS)
- 3 new therapeutic-area presets (respiratory, rare_cns, io_combo)
- Academic-institution filter (University of Tokyo → "license-in target")
- Unique-mechanism overlap counting (replaces drug-count artifact)

---

## Where the Council Agrees

- **Engineering shipped.** Divestment logic, reproducibility tiebreakers, adaptive tiers, scenario_library, 5-indication harness are real and functional. No advisor disputes the code.
- **Branch must be committed.** Contrarian, Executor, Expansionist all implicitly or explicitly agree that uncommitted work on a laptop is the highest-probability failure mode right now.
- **Reader layer is underbuilt.** Outsider leads, Contrarian's "silent miscalibration generator" and First Principles' "who used this?" all land on the same wall: the artifact does not tell a named person what to do.
- **`@domain-reviewer` is not a fulfilled blocker.** Contrarian explicit; Executor treats it as a 15-minute fix; neither considers it done.

---

## Where the Council Clashes

- **Ship vs don't ship.** Executor says ship Monday in 65 min because you cannot recruit a real user against an unmerged branch. First Principles says shipping without a user produces no learning signal. Both are right within their frame — the disagreement is whether "merge to main" and "ship to a decider" are the same event. They are not.
- **Adaptive tiers: fix or feature regression?** Expansionist calls it the invisible win unlocking rare disease and combos. Contrarian calls it semantic corruption — Tier A on ALS now means something different than Tier A on asthma, cross-indication comparability is broken. Peer reviewers 1, 2, 3 sided with Contrarian: "D sold a bug as a feature."
- **Scope: harden or expand?** Expansionist wants public benchmark in 30 days, compliance workflows. Contrarian and First Principles want a backtest and one real user respectively before any expansion. 4/5 peer reviewers flagged Expansionist as biggest blind spot — platform ambition before one externally validated call.
- **What rigor is possible at all.** Contrarian demands a backtest against 20 respiratory divestments. Peer Review 4 counters: no labeled ground-truth dataset of "correct" buyer-fit calls exists. B is asking for rigor that cannot be manufactured. Unresolved.

---

## Blind Spots the Council Caught (Peer Review Findings)

1. **Nobody audited the literal blocker checklist.** Every advisor pivoted to a preferred frame. Not one walked down the 5 blockers and graded each PASS/FAIL. Peer Reviews 1 and 4 caught this. Strict reading: blockers 1-4 PASS, blocker 5 FAIL.

2. **Cost of being wrong is absent from all 5 responses.** Peer Review 2: a BD exec acting on a miscalled beneficiary torches a real deal. No advisor discussed calibrated uncertainty, abstention on thin pipelines, or liability framing. Confidence labels are not UX polish — they're the difference between a tool and a lawsuit.

3. **Ground truth is self-referential.** Peer Review 3: "IPF Boehringer PASS" and "asthma = SMB" come from the same epistemic well — domain-expert vibes + council consensus. No independent pre-registered adversarial test set. Every PASS in the harness is circular. The sprint hardened the machine against itself, not reality.

4. **No named decision, no named decider.** Peer Review 4: all 5 advisors assumed the artifact is a briefing. None asked what specific decision /landscape is supposed to change, or whether a BD exec does anything differently than they would from a $0 Perplexity query. This is the missing v0.9 blocker.

5. **Cortellis licensing is the gating constraint.** Peer Review 5: auditable reports, public benchmarks, shareable BD artifacts, and open reference implementations all redistribute derived Cortellis data. No one checked TOS. Three of Expansionist's five roadmaps may be contractually dead before any engineering question matters. The single most expensive unchecked assumption in the sprint.

---

## The Recommendation

**Ship v0.9 internally. Do not ship v0.9 externally or publicly.**

Merge the branch to `main` this week — the Executor is right that uncommitted work is the dominant risk and you cannot recruit a user against a laptop. But tag it `v0.9-internal`, not `v0.9`.

Hold the public version, the benchmark, and any shareable artifact until three things are true:

1. **One named human BD decider** has run /landscape on one real in-flight decision and reported whether it changed their call.
2. **The harness has a named human owner** with a Slack handle and a due date, replacing `@domain-reviewer`.
3. **A written answer exists** to the question: "Does Cortellis TOS permit us to share this derived output with a third party?"

Any of those three failing blocks public v0.9. All three passing promotes `v0.9-internal` to `v0.9` and unlocks the Expansionist roadmap (benchmark, compliance workflows, scenario DSL expansion).

The prior council's blockers were substantially met. The new blocker — the one this council surfaced — is that **a process-validated tool with zero decider contact is indistinguishable from a well-formatted hallucination.**

---

## The One Thing to Do First

**Pick one real BD decision that one real human is making in the next two weeks. Run /landscape on it. Sit in the room while they read the output.**

Everything else — the merge, the benchmark, the reader layer, the TOS check, the owner handle — is downstream of whether that one person does something different after reading it.

---

## Delta Summary vs Prior Councils

| Metric | 2026-04-04 baseline | 2026-04-05 (asthma verif.) | **2026-04-05 (v0.9 hardening)** |
|---|---|---|---|
| Alignment score | 65% | 78% | **71%** |
| Direction | — | +13 | **-7** |
| Posture | "Rebuild needed" | "Ship v0.9 after hardening" | **"Ship internally; block public"** |
| Blockers closed | n/a | 1/5 (scenario fix) | 4/5 (strict) |
| New blocker surfaced | "scenario library thin", "loe layer", "reproducibility" | "divestment naive" | **"zero deciders", "circular ground truth", "Cortellis TOS"** |

The score drop is not a regression — it's the evaluation frame widening. Prior councils scored the code. This council scored the *evidence of real-world value*, and found the code strong but the evidence thin.

## Anonymization Mapping (for audit)

- Response A = The Outsider
- Response B = The Contrarian
- Response C = The Executor
- Response D = The Expansionist
- Response E = The First Principles Thinker
