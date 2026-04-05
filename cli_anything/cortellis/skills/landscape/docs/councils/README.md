# LLM Council Audit Trail — /landscape

Full record of council-on-council validation for the `/landscape` skill's
strategic layer, from baseline review through v0.9 hardening verification.

## Reading order (chronological)

1. **council-*-landscape-strategy-20260404** — initial 7-blocker review
   of the strategic layer. Baseline alignment: 65%.
2. **council-*-landscape-verification-20260404** — post-fix verification
   of the 7 blockers. Still 65%: scenario library thin, LOE layer
   absent, reproducibility unverified.
3. **council-*-asthma-verification-20260405** — domain-expert override
   on the divestment scenario. 78%. Ground truth: asthma top beneficiary
   is Laboratoires SMB SA (specialty), not Chiesi (diversified). Issued
   5 new blockers for the v0.9 hardening sprint.
4. **council-*-v09-hardening-20260405** — evaluation of the v0.9
   hardening sprint. 71% (down 7). First Principles surfaced the
   methodological flaw that 4/5 peer reviewers ratified: three sprints
   of council-on-council validation produced *consistency*, not
   *correctness*. Recommendation: ship internally, block public, until
   three gates close (decider trial, real harness owner, Cortellis
   TOS answer).
5. **council-transcript-v09-verification-20260405** — this-session
   verification of whether the v09 recommendations have been addressed.
   Two gates closed with caveats; one (decider trial) remains the last
   open item.

## Sibling skill audit

- **council-report-drug-comparison-verification-20260405.html** —
  cross-branch sibling artifact. Evaluates fixes to the `/drug-comparison`
  skill (work lives on `feature/autonomous-skill-development`). Included
  here for shared audit trail; actual code fixes do not live on this
  branch.

## Why council-on-council?

Each council follows Karpathy's LLM Council methodology:

1. Five independent advisors (Contrarian, First Principles, Expansionist,
   Outsider, Executor) each answer in 150–300 words.
2. Responses anonymized (A–E), then peer-reviewed by a second agent pass.
3. Chairman synthesizes into a verdict with explicit "where they agree,"
   "where they clash," and "blind spots caught in peer review."

The output is an audit-grade artifact: every material architecture
decision in v0.9 has a reviewable paper trail showing which advisor
pushed for what and why the final call was made.

## Score trajectory

| Date | Session | Score | Posture |
|---|---|---|---|
| 2026-04-04 | landscape-strategy | 65% | "Rebuild needed" |
| 2026-04-04 | landscape-verification | 65% | "7 blockers open" |
| 2026-04-05 | asthma-verification | 78% | "Ship v0.9 after hardening" |
| 2026-04-05 | v09-hardening | 71% | "Ship internally; block public" |
| 2026-04-05 | v09-verification | — | "Internal-only stands" |

The score drop from 78 → 71 is not a regression; it's the evaluation
frame widening from *code quality* to *evidence of real-world value*.
The v0.9-internal release is gated on closing Gate 1 (one real decider
trial) before promotion to public v0.9.
