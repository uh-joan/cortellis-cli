# Landscape Skill — Validation Harness

## Owner Assignment

**Status:** ASSIGNED + FIRST RUN COMPLETE (2026-04-05).

- **Name:** Joan
- **Contact handle:** uh-joan
- **Assignment date:** 2026-04-05
- **First run date:** 2026-04-05 — see `docs/validation_harness_runs/2026-04-05.md`
- **First-run verdict:** 4/4 available indications PASS (NSCLC deferred — raw data not pulled). Provisional pass criteria met.
- **Cadence after first run:** re-run on every change touching scoring logic (`strategic_scoring.py`), narrative logic (`strategic_narrative.py`), or preset weights; quarterly backstop otherwise.

## Independent Co-Reviewer (Gate 2 independence closure)

To address the independence gap (Joan is both skill author and primary harness owner), a second reviewer has been assigned:

- **Name:** Kimon
- **Contact handle:** uh-kimon
- **Assignment date:** 2026-04-05
- **Role:** Independent harness co-reviewer. Not involved in `/landscape` scoring/narrative authorship. Runs the 5-indication harness independently of Joan and signs off on pass/fail without access to Joan's interpretation of edge cases.
- **First independent run:** scheduled **2026-04-12** (one week from assignment).
- **Cadence:** quarterly independent pass, plus any run Joan flags as materially affecting scoring logic, preset weights, or the scenario library.
- **Escalation rule:** if Kimon's independent run disagrees with Joan's harness result on any indication, that indication is marked `AMBIGUOUS` in `docs/validation_harness_runs/` and held until a tie-breaker run (Carlos, or a new domain reviewer) resolves it.

With this assignment, the former "Joan is both author and owner" caveat is **closed upon Kimon's first independent run landing**. Until that run lands, Gate 2 status is **closed-with-scheduled-independent-pass**; after it lands and passes, Gate 2 is fully closed.

**Version**: v0.9
**Cadence**: Re-run on every change that touches scoring logic (`strategic_scoring.py`),
narrative logic (`strategic_narrative.py`), or preset weights.

---

## Purpose

This document defines the explicit validation harness for the landscape skill.
It replaces the informal "validate against expertise" footer with testable pass criteria
and a structured review checklist.

---

## Test Set

Five indications with known ground-truth leaders. Data reflects the 2024–2025 competitive
landscape as assessed by domain review.

| # | Indication | Expected leader(s) | Rationale |
|---|-----------|-------------------|-----------|
| 1 | Obesity | Novo Nordisk #1 | semaglutide franchise dominant; tirzepatide not yet launched in 2024–5 |
| 2 | Asthma | GSK / AstraZeneca / Chiesi top 3 | broad inhaled + biologic portfolios |
| 3 | Alzheimer's disease | Eli Lilly #1 | donanemab Phase 3 data; leading amyloid franchise |
| 4 | NSCLC | AstraZeneca / Merck / Roche top 3 | EGFR/PD-L1/PD-1 franchise depth |
| 5 | IPF | Boehringer Ingelheim #1 | nintedanib market leader |

---

## Pass Criteria

The known leader must appear in the **top 3 by CPI score** for at least **4 of 5** indications.

Any regression (previously passing indication now failing) blocks the release.

---

## Review Checklist

To be executed manually by the domain reviewer, approximately 1 hour per quarter.

- [ ] Tier A companies match clinical/commercial reality in 3 or more indications
- [ ] Scenario library output for asthma: divestment beneficiary is a plausible specialty buyer,
      not a large diversified pharma company
- [ ] Academic and government institutions never appear as "acquisition target" in any scenario
- [ ] Preset provenance (name + description) is visible in all output files and reports
- [ ] Reproducibility test (`test_strategic_reproducibility.py`) is passing in CI

---

## How to Run the Harness

For each indication in the test set, run the full landscape pipeline and inspect
`strategic_scores.csv`:

```bash
# Example: asthma with default preset
python3 cli_anything/cortellis/skills/landscape/recipes/strategic_scoring.py \
    cli_anything/cortellis/skills/landscape/raw/asthma

# Example: asthma with respiratory preset
python3 cli_anything/cortellis/skills/landscape/recipes/strategic_scoring.py \
    cli_anything/cortellis/skills/landscape/raw/asthma respiratory
```

Check that `strategic_scores.csv` ranks the expected leader in position 1–3.

Run the reproducibility test:

```bash
pytest cli_anything/cortellis/tests/test_strategic_reproducibility.py -v
```

---

## Exit Criteria for v0.9

All items below must be green before the v0.9 release tag:

1. Pass criteria met: known leader in top 3 for 4/5 indications.
2. Review checklist fully checked (domain reviewer sign-off).
3. Reproducibility test passing in CI on main branch.
4. Preset provenance verified in outputs for all three therapeutic presets
   (`respiratory`, `rare_cns`, `io_combo`).

---

## Known Limitations (Out of Scope for v0.9)

The following are acknowledged gaps that are explicitly deferred to domain reviewer
judgement and not covered by automated tests:

- Exact loss-of-exclusivity (LOE) dates per compound
- Real deal financial values (upfront, milestones, royalties)
- Indication-specific clinical nuance (e.g., responder subpopulations, biomarker stratification)
- Late-breaking data from conferences not yet indexed in Cortellis

These limitations should be noted in the landscape output footer but do not block v0.9.
