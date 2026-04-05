# Fragmented Indication Stress Test: IPF, ALS, I-O Combo

_Run date: 2026-04-05 | Branch: feature/autonomous-skill-development_

## 1. Summary Table

| Indication | Mode | Total Drugs | Total Companies Scored | Tier A | Tier B | Tier C | Tier D | Top-3 Companies (CPI) |
|------------|------|-------------|------------------------|--------|--------|--------|--------|-----------------------|
| IPF | indication (ID 3771) | 187 | 149 | 1 | 1 | 5 | 142 | Boehringer Ingelheim (A, 90), Avalyn Pharma (B, 54), AstraZeneca (C, 34) |
| ALS | indication (ID 13430) | 216 | 166 | 0 | 1 | 8 | 157 | Ionis Pharma (B, 62), Eisai (C, 42), SineuGene (C, 39) |
| I-O combo | target: PD-L1 | 129 | 104 | 1 | 0 | 30 | 73 | NantCell (A, 78), Sichuan Biokin (C, 46), ImmuneOnco (C, 40) |

**Presets used:** IPF → `respiratory`, ALS → `rare_cns`, I-O combo → `io_combo`

**Deals fetched:** IPF 200/258 (capped), ALS 135/135 (complete), I-O combo 200/752 (capped, PD-L1 keyword query)

## 2. Failure Modes Observed

### 2a. Tier D collapse on thin pipelines
All 3 indications show 70–95% of scored companies landing in Tier D:
- IPF: 142/149 = **95.3% Tier D**
- ALS: 157/166 = **94.6% Tier D**
- I-O combo: 73/104 = **70.2% Tier D**

Root cause: CPI thresholds (A ≥ 80, B ≥ 60, C ≥ 40, D < 40) were calibrated on mature indications with broad company pipelines. In fragmented spaces, single-drug companies with no deal activity accumulate only phase_score points, landing at CPI 5–25. The tier system does not scale down — it produces a 95% D-tier distribution that is informationally useless for ranking.

### 2b. ALS: no Tier A company exists
ALS top CPI is 62 (Ionis, Tier B). The rare_cns preset amplifies phase_score (35%) and deal_activity (25%), which rewards depth — but ALS pipelines are thin across the board. Even Ionis with 2 launched drugs + Phase 3 program cannot cross the 80-point A threshold. **The A tier is structurally unreachable in rare CNS with <3 launched drugs.**

### 2c. I-O combo: deal query fallback documented
`dealActionsPrimary` is not a valid search field (API returns 500). The SKILL.md target-mode deal query (`--query "dealActionsPrimary:\"$ACTION_NAME\""`) fails silently. **Workaround used:** keyword query `--query "PD-L1"` (752 total deals, 200 fetched). This over-fetches (any mention of PD-L1, not just PD-L1-inhibitor deals). Downstream deal_activity scores are inflated for I-O combo.

### 2d. Specialty-buyer-fit collapses to noise on thin pipelines
ALS top_exit scenario: all 4 beneficiaries show `mechanism_overlap=1, fit_score=1.000`. When the exiting company has only 3 drugs across 2 mechanisms, every overlapping company has identical overlap=1. The specialty-buyer-fit formula `score = overlap × 1/(1 + phase3plus/5)` produces no differentiation — all tie at 1.0 and ranking is arbitrary.

IPF performed better: Avalyn Pharma scored `overlap=3, fit_score=3.0` as clear top beneficiary after Boehringer exit, because Boehringer had 5 programs across 5 mechanisms with meaningful overlap density.

## 3. Scenario Library Findings

| Indication | Top Exit Beneficiary | Fit Score | Meaningful? |
|------------|---------------------|-----------|-------------|
| IPF | Avalyn Pharma Inc | 3.000 | Yes — 3-mechanism overlap, no competing P3 programs |
| ALS | UMass Medical / Ractigen / Alnylam (tie) | 1.000 each | No — all tie, ranking is arbitrary |
| I-O combo | ImmunityBio Inc | 3.000 | Partial — 3-overlap but NantCell's programs are clinic-stage edge cases |

**LOE wave scenario:** All 3 indications returned no loe_metrics hits for the wave scenario (no mechanisms with ≥5 launched drugs across ≥3 companies, except PD-L1 itself in I-O which has 12 launched / 11 companies). Only I-O combo triggered the LOE/generics territory flag on PD-L1 inhibitors — correct signal.

**Pivotal failure (IPF):** Boehringer remains #1 even after nerandomilast (P3) removal — score drops 19→15 but lead over #2 Marnac (8) is still commanding. Validates that their franchise is not single-drug dependent.

## 4. Preset Fitness Assessment

| Indication | Preset | Effect vs Default |
|------------|--------|-------------------|
| IPF | `respiratory` (breadth 25, phase 25, trial_intensity 20) | Boehringer #1 with respiratory preset (CPI 90) vs default — trial_intensity bonus rewards BI's active trial footprint |
| ALS | `rare_cns` (phase 35, deal 25) | Ionis correctly elevated by phase weight (P3 + launched programs); Eisai benefits from trial_intensity even with thin deal sheet |
| I-O combo | `io_combo` (mech_diversity 30, trial_intensity 25) | NantCell #1 due to 9-drug breadth across 6 mechanisms; Western majors (MSD parent company absent, Merck KGaA #8) deprioritized because they hold fewer distinct mechanism programs in PD-L1 scope |

**Preset fitness verdict:** Presets improve ordering fidelity for IPF and ALS. For I-O combo the `io_combo` preset rewards multi-mechanism combinatorial players, which is analytically correct for the combo-therapy question but surfaces Chinese biotech as dominant (NantCell, Biokin, ImmuneOnco) due to pipeline breadth — may not reflect clinical precedence.

## 5. Ground-Truth Check: Boehringer #1 for IPF

**YES. Confirmed.** Boehringer Ingelheim International GmbH ranks #1 in IPF with:
- CPI: 90.0 (Tier A — only Tier A company)
- Breadth: 4 drugs (nintedanib launched + 3 pipeline programs)
- Phase score: 19 (highest in indication)
- Deal activity: 6
- Trial intensity: 1

Gap to #2 (Avalyn Pharma, CPI 54) is 36 points — unambiguous leader signal. Validation harness criterion: **PASS**.

## 6. Known Limitations Surfaced on Fragmented Data

1. **Tier thresholds not calibrated for rare/fragmented indications.** 95% D-tier rate on IPF and ALS renders tier distribution uninformative. A relative-tier system (top 5% → A, next 15% → B, etc.) would be more robust.

2. **Single-drug companies produce noise in top_exit scenario.** When 80%+ of companies have pipeline_breadth=1, mechanism_overlap is always 0 or 1, and specialty-buyer-fit degenerates to a binary flag.

3. **`dealActionsPrimary` field invalid in Cortellis deals API.** Target-mode deal fetch using `dealActionsPrimary:` query fails with HTTP 500. Keyword fallback works but over-fetches unrelated deals.

4. **LOE proxy metrics are structurally blind to rare disease.** All rare indications return 0 LOE risk flags because they have <5 launched drugs across <3 companies by definition. The LOE proxy is designed for mature markets.

5. **ALS Tier A structurally unreachable.** No company can reach CPI ≥ 80 in ALS with the rare_cns preset given the thin pipeline. The CPI ceiling is ~65 for this indication type.

6. **I-O combo via PD-L1 target mode misses combination regimens.** Drugs are fetched by `--phase-highest --action "Programmed cell death ligand 1 inhibitor"` only, missing drugs in combination trials where PD-L1 is not the primary mechanism. Total 129 drugs vs likely 500+ in any broad solid-tumor I-O landscape.

---
_All outputs written to: `raw/ipf/`, `raw/als/`, `raw/io-combo/`_
_Scripts used: resolve_indication.py, fetch_indication_phase.sh, fetch_drugs_paginated.sh, company_landscape.py, enrich_company_sizes.py, fetch_deals_paginated.sh, deals_analytics.py, trials_phase_summary.py, catch_missing_drugs.py, landscape_report_generator.py, strategic_scoring.py, opportunity_matrix.py, strategic_narrative.py, loe_analysis.py, scenario_library.py_
