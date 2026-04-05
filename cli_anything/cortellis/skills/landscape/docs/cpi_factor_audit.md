# CPI Factor Construct Validity Audit

This document evaluates the construct validity of the five factors in the Competitive Pipeline Index (CPI). Each factor is examined for what it measures, its theoretical justification, predictive claims, and known limitations.

---

## Pipeline Breadth

**What it measures:** The number of unique drugs in a company's development pipeline, counted once per company regardless of clinical phase or indication.

**Why it's included:** Breadth signals organizational capacity, capital reserves, and R&D infrastructure. Companies with larger pipelines have more opportunities for success and are less vulnerable to single-program failure. In a risk-adjusted portfolio framework, breadth is a proxy for financial stability and institutional depth.

**What outcome it correlates with:** Companies with broad pipelines historically maintain stronger competitive positions in therapeutic areas, sustain more revenue streams, and have greater ability to absorb market losses in individual programs. We expect breadth to correlate with 5-year market share retention and deal-making capacity.

**How it could be wrong:** Breadth ignores quality. A company with 20 early-stage programs may be less competitive than one with 4 late-stage programs. Cortellis reports drugs in active development but may miss internal programs not yet disclosed. Smaller, focused biotech firms can outmaneuver large companies with bloated pipelines. Breadth also double-counts with phase score (discussed in Construct Validity Risks below).

---

## Phase Score

**What it measures:** A phase-weighted sum of pipeline drugs, assigning numerical values: Launched=5, Phase 3=4, Phase 2=3, Phase 1=2, Discovery=1. Higher scores indicate a pipeline skewed toward later-stage, higher-probability programs.

**Why it's included:** Phase is the strongest predictor of regulatory and commercial success. A Phase 3 program has >25% probability of approval; a Phase 1 program <5%. Phase score directly captures probability-weighted future revenue potential and reflects R&D productivity.

**What outcome it correlates with:** We expect phase score to be the strongest predictor of near-term competitive impact (next 2-5 years). Companies with high phase scores have more imminent launches and clinical data readouts, translating to faster market entry and earlier revenue recognition.

**How it could be wrong:** Phase advancement varies by indication and company strategy. Some companies deliberately delay Phase 3 entry to optimize commercial timing; others rush to meet internal targets. Phase data in Cortellis reflects most recent disclosed phase, not necessarily current regulatory discussions. Companies with many Phase 2 programs may generate fewer launches than those with fewer, more advanced programs. Success probability varies dramatically within a phase—a Phase 3 orphan drug is fundamentally different from a Phase 3 blockbuster-potential program.

---

## Mechanism Diversity

**What it measures:** The number of distinct molecular mechanisms of action represented in a company's pipeline. Higher diversity indicates exposure to multiple biological pathways and therapeutic strategies.

**Why it's included:** Mechanism diversity reduces concentration risk. A company with programs across 10 distinct mechanisms is less vulnerable to a single biological failure (e.g., class-wide toxicity signal) than one betting on 3 mechanisms. Diversity also signals scientific breadth and capability across multiple domains.

**What outcome it correlates with:** We expect diverse mechanism portfolios to correlate with greater resilience in adverse competitive scenarios (safety signals, clinical failures). Conversely, companies with clustered mechanisms may achieve faster competitive dominance in specific areas (e.g., four competing PD-1 programs beat one diverse program).

**How it could be wrong:** Diversity is inherently non-additive. Ten programs on the same mechanism contribute more to competitive advantage than ten programs on ten separate mechanisms. Cortellis mechanism classification can be inconsistent (e.g., "small molecule kinase inhibitor" vs. "tyrosine kinase inhibitor"). Companies focused on one mechanism (e.g., CRISPR or monoclonal antibodies) may dominate their therapeutic space despite low diversity scores. Therapeutic area heterogeneity is not captured—oncology mechanisms differ fundamentally from CNS mechanisms.

---

## Deal Activity

**What it measures:** The frequency with which a company appears in deals.csv (a dataset of pharma partnerships, acquisitions, and licensing deals), counting appearances as either principal or partner.

**Why it's included:** Deal activity signals recognition by peers, capital access, partnership momentum, and strategic positioning. Companies making and receiving deals are more integrated into the pharma ecosystem and benefit from external capital and validated partnerships.

**What outcome it correlates with:** We expect deal activity to correlate with access to capital, risk mitigation (risk-sharing with partners), and market leverage. High deal activity may also signal stronger business development teams and more favorable licensing terms.

**How it could be wrong:** Deal activity reflects historical deals; deals.csv is not a leading indicator. A company may have completed major partnerships years ago and be coasting on their benefit. Conversely, a company entering a deal may fail to execute (deal failure rates are ~30%). Cortellis deal data is incomplete; many small partnerships and academic collaborations are not captured. Large pharma companies appear in more deals by virtue of size; smaller biotech may have higher-quality deals but lower raw frequency.

---

## Trial Intensity

**What it measures:** The count of Phase 2 and Phase 3 clinical trials sponsored by a company in trials_by_sponsor.csv, capturing recruiting activity and trial capacity at stages closest to NDA/BLA submission.

**Why it's included:** Phase 2+3 trial intensity reflects near-term development momentum and resource deployment. Companies actively recruiting late-stage trials are demonstrating clinical confidence and readiness. Trial site activation is costly and signals serious commitment to regulatory timelines.

**What outcome it correlates with:** We expect trial intensity to correlate with probability of near-term regulatory approvals (next 1-3 years) and with speed to market for approved indications. High trial intensity may also proxy for stronger regulatory affairs and clinical operations teams.

**How it could be wrong:** Trial intensity is noisy. Large trials count the same as small trials. A single large Phase 3 oncology trial may involve 500+ sites and inflates intensity scores disproportionately to significance. Cortellis trials_by_sponsor data reflects publicly registered trials (ClinicalTrials.gov); companies may be running unreported Phase 1 or Phase 2 trials. Trial intensity captures capacity but not success—failed trials waste resources but still appear in intensity counts. Geographic bias: US trials are over-captured vs. European/Asian trials.

---

## Construct Validity Risks

### Double Counting

**The problem:** Pipeline breadth and phase score both reward companies for having drugs. A company with 10 drugs receives credit for breadth (10 points) and also for phase (e.g., if 5 are Phase 2, ~15 phase points). This double-weights the same underlying asset: drug count.

**Impact:** Two companies with identical pipelines but different phase distributions are not penalized for phase disadvantage as much as they should be. The correlation between breadth and phase is naturally high (0.6–0.8), inflating multicollinearity and unstable weights.

**Mitigation:** Consider normalizing phase score by breadth (average phase per drug) rather than summing. Or reduce breadth weight if empirical analysis shows it already correlates strongly with phase.

### Selection Bias

**The problem:** Cortellis coverage is not uniform. Large pharmaceutical companies and US-based biotech are heavily represented. Chinese and Indian generic manufacturers, regional players, and non-English-language companies are under-represented or absent.

**Impact:** For indications with strong non-US generic competition (e.g., anti-malarials, TB treatments), CPI rankings will systematically under-rank actual competitive intensity. For US-centric therapeutic areas (e.g., oncology, rare disease), CPI is more representative.

**Mitigation:** Document which therapeutic areas have geographic bias. Consider separate CPI models for global vs. US-centric indications, or explicitly weight CPI results by Cortellis coverage quality per indication.

### Temporal Mismatch

**The problem:** deals.csv contains historical deal records (with completion dates stretching back 10+ years). Pipeline data reflects current state. Mixing them creates asymmetric temporal weighting: a company with one deal from 2015 scores on that historical signal, while its current pipeline is also scored. The two types of evidence apply to different time horizons.

**Impact:** For indications where competitive leadership has shifted recently (2020–2026), companies with older, expired deal partnerships appear stronger than they should. Deals completed 5+ years ago may no longer be strategically relevant.

**Mitigation:** Weight deal activity by recency (exponential decay: recent deals weighted higher). Or use only deals from the last 3–5 years. Clearly document the deal date cutoff and temporal scope of CPI.

### Name Normalization

**The problem:** Company names in Cortellis, trials_by_sponsor.csv, and deals.csv are not consistently normalized. "Eli Lilly & Co", "Eli Lilly and Company", "Lilly", and "Eli Lilly Company" may represent the same entity but are stored as separate rows.

**Impact:** A single company's pipeline breadth, trial intensity, and deal activity can be fragmented across multiple name variants, artificially deflating its CPI score. This is especially problematic for older acquisitions (companies absorbed but operating under legacy names).

**Mitigation:** Implement entity-level reconciliation before computing CPI. Build a company name normalization dictionary (with NCBI Taxonomy, Cortellis IDs, or D-U-N-S numbers as canonical identifiers). Validate deduplicated records before aggregation.

