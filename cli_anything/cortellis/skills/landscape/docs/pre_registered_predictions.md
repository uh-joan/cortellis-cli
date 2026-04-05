# Pre-Registered Predictions Log

**Purpose:** Break the council/harness circular validation loop by recording `/landscape` predictions BEFORE human review, then adjudicating them against reality later.

**Format:** Append-only log. Each entry is a concrete falsifiable claim from a `/landscape` run, NOT a generic ranking. Entries are timestamped and never edited after creation. Adjudication is recorded in a separate column with a later date.

---

## Log

| Date | Indication | Prediction | Source | Confidence | Adjudication Date | Verdict | Notes |
|------|-----------|-----------|--------|-----------|------------------|---------|-------|
| 2026-04-05 | Asthma | GSK plc will remain in top 3 by CPI for 12 months (current rank #1, CPI ~95). | `raw/asthma/strategic_briefing.md` | HIGH | — | PENDING | Baseline leadership assertion. Falsifiable at 2027-04-05 if new acquisitions or divestments shift the top 3. |
| 2026-04-05 | Asthma | If GSK plc divests asthma franchise, Laboratoires SMB SA is the most probable acquirer (specialty-buyer-fit rank #1, overlap 3 mechanisms, fit score 2.52). | `raw/asthma/strategic_briefing.md` scenario analysis | MEDIUM | — | PENDING | Falsifiable if/when GSK divests. If divestment occurs and SMB is not selected, verdict = FALSE. |
| 2026-04-05 | IPF | Boehringer Ingelheim International GmbH will maintain #1 position (CPI ~90, 36 pt gap over #2 Avalyn Pharma) through 2026-12-31. | `raw/ipf/strategic_scores.md` | HIGH | — | PENDING | Top-quartile confidence based on nintedanib market dominance and pipeline breadth. CPI gap (36 pts) is structural. Falsifiable at 2026-12-31 if IPF market structure shifts materially. |
| 2026-04-05 | IPF | Deal momentum will remain <1.0 (slowing) through 2026-Q3 (current momentum ratio 0.47, recent 7 vs prior 15 deals). | `raw/ipf/strategic_scores.md` | MEDIUM | — | PENDING | Reflect declining IPF deal activity. Falsifiable if Q2/Q3 2026 deal count >10 and reverses momentum ratio. |
| 2026-04-05 | ALS | Ionis Pharmaceuticals Inc will maintain top-3 CPI rank (current rank #1, CPI 62, 20 pt gap over #2 Eisai) regardless of pivotal readout outcomes through 2026-12-31. | `raw/als/strategic_scores.md` | MEDIUM | — | PENDING | Reflects rare-CNS weighting favoring phase + deal commitment. Falsifiable if major clinical failure (negative Phase 3) + mass partner exits occur, OR if Ionis divests ALS assets. Requires evidence, not speculation. |

---

## Adjudication Rules

1. Each entry is created with an initial PENDING status.
2. Adjudication occurs in a separate row (same table) with a later date.
3. Verdict is one of: TRUE, FALSE, INCONCLUSIVE (e.g., company acquired, data not yet published).
4. Notes field captures rationale and any caveats (e.g., "data source updated," "clinical outcome was neutral, not negative").
5. Never edit or delete a row after creation. Corrections are logged as new entries with explicit contradiction notes.

---

*Log started: 2026-04-05. This is the ground-truth falsifiability record for landscape predictions.*
