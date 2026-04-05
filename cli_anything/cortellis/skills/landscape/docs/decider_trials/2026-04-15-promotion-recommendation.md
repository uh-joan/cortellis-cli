# Promotion Recommendation — 2026-04-15 Decider Trial

> **SIMULATION DISCLOSURE — READ FIRST**
> This recommendation is the output of a **dry-run executed on 2026-04-05** with all three roles (Joan, Carlos, Kimon) LLM-simulated. The trial date is 2026-04-15; this file was produced ten days early as an end-to-end workflow exercise. Everything below is provisional and non-binding. **The actual promotion of `SKILL.md` from `v0.9-internal` to public `v0.9` requires a real human decider trial satisfying all acceptance criteria in `docs/decider_trials/README.md`.** Do NOT edit `SKILL.md` based on this file.

---

## Dry-Run Verdict

The 2026-04-15 simulated trial returned **"Confirmed their call with new signal"** — the box checked in `2026-04-15-cs.md`. Per the README exit gate, this verdict maps to: promote `v0.9-internal` to public `v0.9`.

## Promotion Recommendation (Provisional)

**Hold at `v0.9-internal`. Do not promote based on this dry-run.**

The "confirmed with new signal" verdict is encouraging and suggests the tool's analytical logic is sound. However, the dry-run surfaced a **P0 workflow defect** that must be resolved before any production trial can be considered valid:

> `/landscape` could not be executed cold for the indication Carlos nominated (malignant pleural mesothelioma) because MPM raw data is absent from the repo. The cold-run criterion — the foundational requirement of the trial protocol — was not met. The trial proceeded on simulated output, not real tool output.

Promoting on the basis of a simulated output would misrepresent the evidence base. The README is explicit: the trial must use `/landscape` output "executed exactly as a first-time user would run it." That condition was not satisfied.

**Recommendation:** Schedule a second trial after the P0 defect is resolved (see below). If the second trial — with a real human decider, real cold run, real MPM raw data — returns "confirmed with new signal" or "changed their call," promote to public `v0.9`.

---

## What Must Be Fixed Before the Real Trial

### P0 — Raw-data-pull step (blocks trial validity)

The nomination-to-trial workflow must include an explicit data-pull step. Proposed protocol change:

1. **T-48h:** Carlos nominates indication.
2. **T-48h to T-24h (new step):** Joan verifies indication is covered by existing raw data. If not, executes `/landscape <indication>` to pull it and stages the three output files.
3. **T-24h:** Joan confirms output files exist and are unedited. Trial can proceed.
4. **T-0:** Live read-along with Carlos and Kimon.

Without this step, any nominated indication outside the pre-pulled set will repeat this dry-run's failure mode.

### P1 — Program-level pipeline table

Before the real trial, add a structured pipeline table to `strategic_briefing.md` output: asset, sponsor, phase, primary indication, expected readout date, overlap with nominated indication. Carlos's second-ranked complaint; directly affects term-sheet quality.

### P1 — Deal-comp triangulation methodology

When deal comps are sparse for the nominated indication, the output should offer a triangulation path (adjacent rare-indication comps + mechanism-class comps + asset-stage comps). Carlos's third-ranked complaint; affects valuation usefulness.

---

## What the Real Human Trial Must Replicate to Ratify This Dry-Run

To count as ratification of the dry-run's "confirmed with new signal" verdict, the production trial must satisfy all of the following:

- [ ] Real human decider — a named BD or CI practitioner not affiliated with the `/landscape` team, making a real in-flight decision with an observable go/no-go outcome within 2–4 weeks.
- [ ] Cold run on a covered indication — `/landscape` executed without pre-briefing or hand-editing on an indication for which raw data has already been pulled (or pulled at T-24h per the revised protocol above).
- [ ] Same or analogous decision type — an in-license, option, or partnership evaluation in a specialty oncology or rare-disease indication, so the trial stress-tests the same competitive-density and deal-comp use cases Carlos exercised.
- [ ] Kimon (or a designated independent observer) dials in as co-signer and provides independent notes with at least one genuine cross-check or disagreement signal.
- [ ] Verdict is "confirmed their call with new signal" or "changed their call." A "wasted their time" result on the real trial would override the dry-run's positive signal and trigger the v0.10 remediation path.

If all five conditions are met and the verdict is positive, Joan may update `SKILL.md` status from `v0.9-internal` to `v0.9` and merge externally.

---

## Summary

| Item | Status |
|------|--------|
| Dry-run verdict | Confirmed with new signal (simulated) |
| Promotion recommendation | **Hold at `v0.9-internal`** |
| Reason for hold | P0 raw-data gap prevented a valid cold run; verdict is based on simulated output |
| Next action | Resolve P0 workflow defect; schedule real human trial |
| `SKILL.md` edits | **None — do not edit** |

---

*Produced 2026-04-05 by Joan (uh-joan) and Kimon (uh-kimon) as LLM role-plays, as part of the 2026-04-15 dry-run. Non-binding pending real human trial.*
