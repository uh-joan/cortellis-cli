# Weight Derivation Methodology

## 1. Problem Statement

The Competitive Pipeline Index (CPI) currently assigns weights to five factors via committee consensus: pipeline breadth (20%), phase score (30%), mechanism diversity (20%), deal activity (15%), and trial intensity (15%). These weights reflect expert judgment and organizational convention, not empirical validation.

This document describes how CPI weights **should** be derived when longitudinal data becomes available. The goal is to replace committee-derived weights with a statistically principled methodology that is defensible, reproducible, and calibrated to actual competitive outcomes.

### Current Weights (Baseline)
```
Pipeline breadth:      20%
Phase score:           30%
Mechanism diversity:   20%
Deal activity:         15%
Trial intensity:       15%
Total:               100%
```

These weights have served as the default, but they were never systematically validated against historical competitive outcomes.

---

## 2. Proposed Methodology

### 2.1 Define the Outcome Variable

Selecting the right outcome is critical. The outcome must be:
- **Observable** at a specific point in time (not subjective)
- **Causally downstream** of the CPI factors (competition determines outcomes, not vice versa)
- **Mechanistically related** to the five CPI factors

Candidate outcomes:

| Outcome | Definition | Advantages | Disadvantages |
|---------|-----------|-----------|-----------------|
| **Drug launches (next 5 years)** | Number of FDA/EMA approvals from company's pipeline | Direct measure of competitive output | Approval is influenced by regulation, not just competition |
| **Cumulative deal value** | Sum of partnership/licensing deal values in next 5 years | Reflects market's valuation of pipeline | Deal value data is often private or estimated |
| **5-year market cap change** | % change in company market cap relative to index | Integrates all competitive outcomes | Influenced by factors outside pipeline (debt, buybacks, M&A) |
| **R&D productivity** | (Cumulative deal value + approvals) / R&D spend | Efficiency metric | Requires accurate R&D spend data |
| **Indication-level market share** | Company's % market share in indication at Year 5 | Direct measure of competitive position | Requires detailed market data per indication |

**Recommended primary outcome:** Drug launches in next 5 years (approval count), with 5-year market share change as secondary validation.

### 2.2 Collect Historical Snapshots

To regress outcomes against factors, we need point-in-time factor scores at the same time horizon as the outcome.

**Snapshot design:**
1. Select 20+ indications with well-documented competitive dynamics (e.g., GLP-1 obesity, PD-1 oncology, PCSK9 hyperlipidemia, tau Alzheimer's, SGLT2i diabetes).
2. For each indication, capture Cortellis pipeline state **as of 3–5 years ago** (2020, 2021, 2022 snapshots).
3. Compute the five CPI factors per company at each snapshot date.
4. Observe the outcome (approvals, market share) for Year 0–5 forward from each snapshot.

**Data collection challenges:**
- Cortellis does not archive historical pipeline snapshots. We cannot retroactively ask "What was the phase of Drug X on January 1, 2021?"
- Alternative: Use regulatory databases (FDA CBER/CDER) to infer phase from clinical trial registration dates and regulatory documents.
- Deal records must be filtered to only those known at the snapshot date (no forward-looking future deals).

**Example snapshot:**
```
Indication: GLP-1 receptor agonists for obesity
Snapshot date: 2021-01-01
Companies to analyze: Novo Nordisk, Eli Lilly, Amgen, Viking, Viking, Structure
Factors computed: breadth, phase, diversity, deals (as of 2021), trials (active 2021)
Outcome observed: FDA approvals (2021–2026), market share (2026)
```

### 2.3 Regress Outcomes Against Factors

Once factor scores and outcomes are collected across indications and time horizons, fit a linear regression:

```
outcome_i = β₀ + β₁·breadth_i + β₂·phase_i + β₃·diversity_i + β₄·deals_i + β₅·trials_i + εᵢ
```

Where:
- `outcome_i` = outcome for indication *i* (e.g., launch count in next 5 years)
- `breadth_i`, `phase_i`, etc. = factor scores for indication *i* at snapshot
- `β₁, β₂, β₃, β₄, β₅` = regression coefficients (unnormalized weights)

**Weight normalization:**
```
Normalized weight = |β_j| / Σ|β_k|
```

This ensures weights sum to 100% and are proportional to factor importance.

**Example output:**
```
Raw coefficients:
  breadth:      0.8    → 20% (0.8 / 4.0)
  phase:        1.2    → 30% (1.2 / 4.0)
  diversity:    0.6    → 15% (0.6 / 4.0)
  deals:        0.8    → 20% (0.8 / 4.0)
  trials:       0.6    → 15% (0.6 / 4.0)
  ____________
  Total:        4.0    → 100%

R² = 0.58 (model explains 58% of variance in outcomes)
```

### 2.4 Cross-Validation

To assess generalization, use k-fold cross-validation:

1. Randomly partition indications into 5 folds (80% training, 20% hold-out).
2. Train regression on 4 folds; predict on held-out fold.
3. Compute R² and Mean Absolute Error (MAE) on predictions.
4. Repeat 5 times and average metrics.

**Acceptance criteria:**
- **Cross-validated R² ≥ 0.40** (model generalizes to unseen indications)
- **Cross-validated MAE ≤ 15% of mean outcome** (prediction error is acceptable)

If cross-validation fails, investigate:
- Missing factors (e.g., company size, cash position)
- Non-linear relationships (use polynomial or interaction terms)
- Indication-specific heterogeneity (consider stratified weights by therapeutic area)

---

## 3. Data Requirements

Implementing the weight derivation methodology requires:

| Data | Source | Current Status | Gap |
|------|--------|-----------------|-----|
| Historical pipeline snapshots (2020–2022) | Cortellis API / Regulatory databases | Not available via Cortellis API | Requires manual archival or FDA CBER/CDER mining |
| Deal records with completion dates | deals.csv | Available | Sufficient |
| Trial registry data (Phase 2+3) | ClinicalTrials.gov / trials_by_sponsor.csv | Available | Sufficient |
| Outcome data (approvals, deals) | FDA CDER/CBER, regulatory approvals database | Publicly available | Requires curation and validation |
| Company name normalization | D-U-N-S, Cortellis company IDs | Partial in Cortellis | Requires build-out |

**Critical blocker:** Cortellis does not provide point-in-time historical snapshots. To proceed, we would need to:
1. Archive Cortellis API responses on a quarterly basis starting now (for future analyses)
2. Retrospectively reconstruct 2020–2022 pipeline state from FDA documents and trial registries
3. Partner with Cortellis for historical data export (if available under enterprise agreements)

---

## 4. Alternative: Expert Elicitation via Analytic Hierarchy Process (AHP)

If historical data is unavailable or insufficient, derive weights through **expert consensus** using the Analytic Hierarchy Process:

### 4.1 Recruitment
- Recruit 10–15 pharma strategists, analysts, or R&D leaders
- Seek diversity of backgrounds: large pharma, biotech, venture capital, regulatory affairs

### 4.2 Pairwise Comparison Protocol
Present experts with pairwise comparisons:
- "For predicting competitive position in an indication, is **pipeline breadth** MORE important, LESS important, or EQUALLY important as **phase score**?"
- Use a 9-point scale: 1 (equal), 3 (moderately more important), 5 (strongly more important), 7 (very strongly), 9 (absolutely more important)

All pairs: 5 factors = 10 pairwise comparisons per expert.

### 4.3 Compute Eigenvector Weights
1. For each expert, construct a 5×5 pairwise comparison matrix
2. Compute the principal eigenvector (represents the expert's weight vector)
3. Check consistency ratio (CR). **CR < 0.10** indicates internally consistent preferences.
4. Discard responses with CR > 0.10 (expert contradicted themselves)

### 4.4 Synthesize Across Experts
- Geometric mean of each factor's weight across experts
- Report mean weight and confidence interval (std dev)

### 4.5 Validation
Test derived weights on known competitive cases (e.g., rank companies in GLP-1 obesity; check against actual 2026 market shares). If rankings diverge significantly from reality, iterate with experts to identify missing factors or misweighted priorities.

**Advantage:** Faster and more feasible than regression; leverages expert intuition.
**Disadvantage:** Subjective; expert disagreement may be high; not empirically validated.

---

## 5. Validation Protocol

Regardless of derivation method (regression or AHP), empirically validate weights against **known competitive cases** before deployment:

### 5.1 Case Selection
Choose 5 indications where competitive dynamics are well-understood and outcomes are settled (2023–2026):
1. **GLP-1 receptor agonists (obesity)** — Novo Nordisk dominant; clear winners/losers
2. **PD-1/PD-L1 checkpoint inhibitors (oncology)** — Merck, Bristol Myers, Roche leaders; numerous failed entrants
3. **Alzheimer's amyloid monoclonal antibodies** — Eli Lilly and Biogen leaders; Eli Lilly ascendant
4. **SGLT2 inhibitors (diabetes/heart failure)** — Dapagliflozin, empagliflozin clear winners
5. **PCSK9 inhibitors (hyperlipidemia)** — Amgen and Sanofi leaders; modest market penetration

### 5.2 Historical Ranking vs. Actual Outcome
1. Compute CPI scores for each company in each indication using **historical snapshot data** (2021 or 2022 pipeline state)
2. Rank companies by CPI score
3. Compare against **actual 2023–2026 outcome** (launch success, market share, deal activity)
4. Compute correlation between CPI rank and outcome rank (Spearman ρ)

**Pass criterion:** ρ ≥ 0.60 for at least 4 out of 5 indications.

### 5.3 Divergence Analysis
If rankings diverge significantly:
- **Hypothesis 1:** Model is missing a factor (e.g., manufacturing capability, regulatory relationships)
- **Hypothesis 2:** Therapeutic area specificity (weights vary by indication; one global weight set is insufficient)
- **Hypothesis 3:** Non-stationarity (factors predictive in 2021 are not predictive in 2026; pharma dynamics shifted)

Investigate and iterate.

---

## 6. Honest Limitations

The CPI, even when empirically derived, has fundamental limitations:

### 6.1 Variance Unexplained
Pipeline-based competition explains ~50–70% of variation in outcomes. **30–50% is unexplained.** This residual variance comes from:
- **Execution quality** — R&D team skill, operational efficiency, manufacturing scale-up
- **Business development** — licensing deals, partnerships, M&A timelines
- **Regulatory luck** — approval decisions influenced by committee composition, FDA guidance changes
- **Market dynamics** — reimbursement, physician adoption, patient preference (not captured in pipeline)

CPI is a **necessary but not sufficient** predictor.

### 6.2 Therapeutic Area Heterogeneity
Factors likely predict outcomes differently by therapeutic area:
- In **oncology** (success probability high if mechanism is novel), phase score may dominate
- In **rare disease** (small markets, partnerships critical), deal activity may dominate
- In **generic-heavy areas** (cardiovascular), breadth may matter less

A single global weight set is a compromise. Ideally, derive weights separately per therapeutic area (requires more data).

### 6.3 Black Swan Events
The model assumes **current patterns persist.** Unprecedented events are invisible:
- Safety signals (torsades de pointes affecting entire class)
- Regulatory shocks (FDA guidance changes, manufacturing crises)
- Geopolitical disruption (tariffs, supply chain breaks)
- Paradigm shifts (new mechanism displaces entire strategy)

None of these are predictable from pipeline data.

### 6.4 Company Adaptation and Strategy Shifts
Pharma companies pivot in response to competitive signals. The regression assumes **static preferences** — that a company with a broad Phase 1 pipeline in 2021 will pursue the same strategy in 2026. In reality, competitive pressure, M&A, executive changes, and capital constraints drive strategic pivots that are not captured in historical snapshots.

### 6.5 Temporal Decay
Weights derived from 2020–2022 data may not apply to 2026–2030 outcomes. Scientific breakthroughs, regulatory path changes, or market shifts can alter factor importance. Weights should be **re-derived every 3–5 years** as new data accumulates.

---

## 7. Implementation Roadmap

### Phase 1: Data Archival (Ongoing)
- Begin quarterly snapshots of Cortellis pipeline data, deals, and trials
- Establish data governance: standardize company names, archive dates, documentation

### Phase 2: Retrospective Reconstruction (6–12 months)
- Mine FDA CBER/CDER databases for Phase 2/3 trial data (2020–2022)
- Curate outcome data (approvals, deal values, market shares) for 20+ indications
- Validate company name normalization across Cortellis, FDA, and trials registries

### Phase 3: Regression Analysis (3–6 months)
- Fit linear regression model
- Perform cross-validation and sensitivity analysis
- Generate candidate weight set

### Phase 4: Expert Validation (2–3 months)
- Present results to pharma strategists for peer review
- Run validation cases (GLP-1, PD-1, Alzheimer's, etc.)
- Iterate if R² or validation ρ fall below thresholds

### Phase 5: Deployment
- Document final weights and methodology
- Integrate into CPI pipeline
- Establish re-derivation cadence (every 3–5 years)

---

## 8. Conclusion

The current CPI weights (20/30/20/15/15) represent informed judgment but lack empirical grounding. This methodology provides a rigorous path to **evidence-based weights** that are defensible and reproducible.

Implementing this approach requires:
1. **Substantial data work** (retrospective reconstruction, ongoing archival)
2. **Statistical rigor** (regression, cross-validation, sensitivity analysis)
3. **Practical validation** (testing against known competitive cases)
4. **Honest uncertainty acknowledgment** (CPI is predictive, not deterministic)

Until empirical weights are derived, the current 20/30/20/15/15 weights are acceptable heuristics. When data becomes available, they should be replaced with statistically validated, therapeutic-area-specific weights that are recalibrated every 3–5 years.

