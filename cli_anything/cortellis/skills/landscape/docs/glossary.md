# Landscape Skill — Glossary

## Core Metrics

**CPI (Competitive Position Index)**
- **Definition:** Weighted company score from 0–100 measuring competitive strength within a single indication.
- **Formula:** Aggregation of pipeline_breadth (drug count by phase), phase_score (weighting advanced phases), mechanism_diversity (unique MOA count), deal_activity (historical M&A/licensing), and trial_intensity (active trial count). Weights vary by preset (respiratory, rare_cns, io_combo, default).
- **Caveat:** Not comparable across indications. A company with CPI 41 in ALS is not equivalent in competitive strength to a company with CPI 41 in asthma — tiers are percentile-based within each indication.

**Tier A / B / C / D (Company Tiers)**
- **Definition:** Percentile-based ranking within the current indication only. Tier A = top 10%; Tier B = next 15%; Tier C = next 25%; Tier D = bottom 50%. Tier A also enforces a floor: CPI ≥ 40.
- **Formula:** Percentile rank by CPI within indication, then apply floor threshold.
- **Caveat:** Not portable across indications. A Tier A company in ALS (e.g., Ionis with CPI ~62) is not equivalent to a Tier A in IPF (e.g., Boehringer with CPI ~90). Always contextualize tier by indication.

**Position (Leader / Challenger / Emerging)**
- **Definition:** Strategic position category based on CPI rank within indication.
- **Formula:** Top 20% by CPI = Leader; next 30% = Challenger; remainder = Emerging.
- **Caveat:** Position is relative to the current indication's competitive set, not absolute market power.

## Competitive Dynamics

**Mechanism Overlap**
- **Definition:** Count of unique mechanisms shared between two companies (often used to assess M&A acquirer-target fit).
- **Formula:** Set cardinality of MOA codes in common, not drug count. (Prior artifact: drug count was used; this is the correct definition.)
- **Caveat:** Overlap alone does not predict deal success — commercial, regulatory, and clinical factors dominate.

**Specialty-Buyer-Fit**
- **Definition:** Heuristic score assessing how well a buyer profile matches a target's therapeutic niche.
- **Formula:** `overlap × (1 / (1 + phase3plus/5)) × (1 + 0.01·min(total_drugs_in_ind, 5))`, where overlap is mechanism count, phase3plus is count of Phase 3+ drugs, total_drugs is target's drug count.
  - Term 1 (overlap): reward shared mechanisms.
  - Term 2 (1 / (1 + phase3plus/5)): penalize late-stage clinical risk (Phase 3+ has higher execution risk and timeline uncertainty).
  - Term 3 (1 + 0.01·min(..., 5)): modest bonus for pipeline breadth (capped at 5 drugs).
- **Caveat:** Not backtested against real divestment transactions. This is a heuristic; use domain expertise to validate. Do not act on this score alone.

**Crowding Index**
- **Definition:** Measure of mechanism saturation: active_count × company_count for a given mechanism.
- **Formula:** (number of active drugs in mechanism) × (number of companies developing in mechanism).
- **Caveat:** Higher crowding indicates competitive density, not necessarily unviability. Some crowded mechanisms have multiple winners; others have clear winners and casualties.

**Deal Momentum**
- **Definition:** Ratio of recent deal activity (6-month window) to prior deal activity (6-month window), indicating acceleration or deceleration.
- **Formula:** (deals in recent 6 months) / (deals in prior 6 months). Ratio = 1.0 = steady state; >1.0 = accelerating; <1.0 = slowing.
- **Caveat:** High momentum in a small deal window can be noise. Interpret momentum in context of absolute deal count.

## Data Quality & Confidence

**Confidence Labels (HIGH / MEDIUM / LOW / ABSTAIN)**
- **Definition:** Indicator of data sufficiency for a specific analytical claim.
- **HIGH:** ≥3 companies with ≥2 drugs each in the scenario's mechanism(s), deal/trial coverage ≥70% for relevant companies.
- **MEDIUM:** 2–3 companies or incomplete deal/trial data, but sufficient to form a defensible hypothesis.
- **LOW:** <2 companies or <50% data coverage; scenario is illustrative only.
- **ABSTAIN:** Data too thin to justify any claim; do not act on this scenario.
- **Caveat:** Confidence reflects data density, not prediction accuracy. A HIGH-confidence scenario can still be wrong if domain assumptions shift.

**LOE (Loss of Exclusivity) Exposure**
- **Definition:** Heuristic proxy for pipeline vulnerability to generic/biosimilar erosion.
- **Formula:** launched_count / total_pipeline. Flagged (risk) if ≥50%.
- **Caveat:** Not calibrated against real LOE dates or regulatory timelines. This is a rough indicator; consult regulatory databases for exact exclusivity windows.

## Output Semantics

**Strategic Briefing**
- **Definition:** Human-readable narrative summary of competitive landscape, top companies, scenario analysis, and strategic decision guidance for a single indication.
- **Format:** Markdown with executive summary, positioning matrix, scenario analysis, and decision framings.
- **Caveat:** Generated from deterministic scoring logic, not LLM predictions. Validate against domain expertise before acting.

**Scenario Library**
- **Definition:** Parameterized set of hypothetical competitive situations (e.g., "if company X exits, who benefits") with computed beneficiaries ranked by overlap and specialty-buyer-fit.
- **Format:** CSV or JSON with scenario parameters, top-N acquirer/licensor candidates, and confidence label.
- **Caveat:** Scenarios are static snapshots; real-world divestments involve regulatory, financial, and strategic factors not in this model.

---

*Definitions and formulas frozen as of 2026-04-05. Report discrepancies to the landscape skill owner.*
