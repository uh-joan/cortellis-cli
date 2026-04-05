# Retrospective Blind Test Protocol v1

**Protocol ID:** `retrospective-blind-v1-20260405`

**Committed:** 2026-04-05

## Purpose and Epistemic Framing

Replace the scheduled prospective Carlos trial with a retrospective blind test. The skill must be validated against decisions a human decider actually made and observed outcomes, not against hypothetical future scenarios. This protocol implements the 68% council's core recommendation: move from ceremonial prospective testing to falsifiable retrospective evidence.

Goal: produce a defensible data point in 1 week by testing the skill against real historical decisions with known outcomes, eliminating post-hoc tuning bias.

## Decision Selection Criteria

The decider must select 3 historical decisions that satisfy ALL of the following:

1. **Recency:** made within the last 90 days (on or after ~2026-01-05)
2. **Ownership:** the decider's own decisions, not their team's or management's directives
3. **Observable outcome:** go/no-go decision, name/target selected, investment amount committed — something verifiable in hindsight
4. **Domain coverage:** indication, target, technology, or compound discovery — something Cortellis covers

**No cherry-picking.** Decisions MUST be selected and locked BEFORE the skill is run. The decider writes a 3-4 sentence description of each decision's context WITHOUT revealing what they actually decided. The outcome is blind; the rubric scorer sees only the context and the skill's output.

## Information Cutoff Protocol

1. Decider specifies the approximate date each decision was made (e.g., "2026-02-15").
2. Joan runs `/landscape <indication>` cold with a `--as-of <cutoff_date>` flag if the skill supports temporal queries. If not available, run the current state and explicitly flag the leakage risk in the results document as a v0.10 gap.
3. All outputs are frozen — no annotation, no cherry-picked quotes. Handed to the blind scorer as-is.

## Blind Scoring Rubric

**Scorer receives:**
- The decider's 3-4 sentence decision context (blind to actual outcome)
- The frozen `/landscape` output files
- NO metadata about what was decided

**Scoring dimensions (each scored per decision):**

### Alignment
- **Match:** The skill's recommendation or key insights align with what the decider actually chose
- **Contradict:** The skill suggests the opposite action
- **Orthogonal:** The skill output is unrelated to the decision made

*Example: Decider chose to pursue indication X; skill flags X as most promising → Match. Skill flags Y instead → Contradict. Skill generates data on compounds, decider chose partnership partner → Orthogonal.*

### Confidence
- **High:** The output points clearly at one action or recommendation
- **Medium:** Multiple interpretations present, but one is stronger
- **Low:** Ambiguous; unclear which action the output supports

*Example: High = "indication X is top-opportunity with 3+ supporting data points." Low = "indication X shows potential, but Y and Z also viable."*

### Actionability
- **Actionable:** A BD analyst could make a decision by Monday with this output alone
- **Informational-only:** Useful context but requires follow-up analysis to act
- **Unclear:** Insufficient to guide action

*Example: Actionable = clear go/no-go recommendation. Informational-only = detailed market data but no synthesis. Unclear = contradictory signals.*

### Surprise Factor
- **Obvious:** The output confirms what the decider already knew
- **Non-obvious:** The output reveals something unexpected or non-intuitive
- **Wrong:** The output is factually incorrect or misleading

*Example: Obvious = "COVID vaccines are a big market" (known). Non-obvious = "overlooked indication X has 4x the patient population." Wrong = incorrect prevalence data.*

**For each decision:** scorer writes a one-sentence verdict summarizing the alignment and actionability.

## Independence Architecture

**Rubric author:** Whoever fills in this document and commits it first (timestamp = 2026-04-05). By committing BEFORE the trial runs, the rubric is time-stamped and immutable. Git log is the tamper-proof record. The 68% council's critique of Joan-as-SPOF is explicitly acknowledged: the rubric cannot be tuned to results.

**Blind scorer:** MUST NOT be:
- The same person who wrote this rubric
- The person who selected the decider
- The person who runs the `/landscape` skill
- Privy to the decider's actual decisions until scoring is complete

**Third-party rubric reviewer (TBD):** A separate person who reviews this document BEFORE scoring begins to catch:
- Ambiguous scoring definitions
- Rubric design that favors a particular outcome
- Missing edge cases

Flagged as v0.9-external blocker; role TBD. The three roles (rubric author, blind scorer, reviewer) CANNOT collapse to one person.

## Pass/Fail Criteria

**PASS (promote to v0.9-external):**
- ≥2 of 3 decisions scored "Match" with "Actionable"
- At least 1 decision has "Non-obvious" surprise factor

**FAIL (hold at v0.9-internal):**
- 0 or 1 decision scored "Match"
- OR all decisions scored "Obvious"
- OR any decision scored "Wrong"

**AMBIGUOUS (re-run with different decider):**
- 1–2 decisions scored "Match" but all are "Obvious"
- OR all decisions scored "Orthogonal"

## Commitments

This protocol is committed to git on 2026-04-05. **Any change to the rubric, scoring dimensions, or pass/fail criteria after results are collected invalidates the trial.** A new trial requires a new commit with a new protocol ID.

The blind test must be completed within 7 days. Deviations from the protocol must be flagged in the results document before adjudication.
