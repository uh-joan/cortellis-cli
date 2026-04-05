# Decider Trials — External BD Judgment Capture

## Purpose

This directory holds real-world trials of `/landscape` with external BD
deciders. Each trial captures one named human making one real decision, with
`/landscape` output used cold (no hand-editing, no pre-briefing).

The decider trial is the **only** validation step that breaks the
circular-validation loop the 2026-04-05 First Principles advisor flagged
against the hardening council. The internal harness
(`docs/validation_harness_runs/`) can catch regressions but cannot tell us
whether the output changes a real BD call.

## Status (2026-04-05)

**First trial scheduled.** Assigned to an external BD contact from
Joan's network, sourced via recruitment option 1 (network contact):

- **Name:** Carlos
- **Contact handle:** uh-carlos
- **Relationship to /landscape team:** network contact (BD/CI
  practitioner, independent of Joan's current employer and not
  involved in `/landscape` authorship or harness review)
- **Trial date:** scheduled for **2026-04-15** (10 days from assignment)
- **Decision under evaluation:** *to be nominated by Carlos at least
  48 hours before the trial — must be a real in-flight BD call within
  his current pipeline with an observable go/no-go outcome*
- **Author presence:** Joan (uh-joan) will attend the live read-along
  (in person or video call); Kimon (uh-kimon) will dial in as
  independent observer to cross-check Joan's post-trial interpretation
- **Record location:** `docs/decider_trials/2026-04-15-cs.md`
  (placeholder file created; to be populated immediately after the
  trial by Joan and cross-signed by Kimon)

This is the **last open gate** for promotion from `v0.9-internal` to
public `v0.9`. Carlos's trial is the first data point in the
correctness-evidence case the v09 hardening council identified as the
entire remaining epistemic gap. Until this trial lands, the skill
stays tagged `v0.9-internal` regardless of harness pass rate.

## Why This Cannot Be Self-Run

The v0.9 hardening plan is explicit:

> Do NOT use someone on your own team as the decider. They're not independent.

Joan (uh-joan) is the skill author and cannot fill the decider role. Any
internal reviewer (including the harness owner) fails the independence test
and cannot substitute for an external decider trial.

## Recruitment Plan (priority order)

1. **Network — free.** Pharma BD or CI contacts from prior companies /
   LinkedIn. Cost: relationship capital. Timeline: 1–2 weeks to find a live
   decision window.
2. **Favor — free.** A consultant who owes you a favor. Same timeline.
3. **Paid expert call — ~$300–600.** Intro / GLG / AlphaSights, 1 hour.
   Timeline: days, not weeks. **This is the fastest path if the network
   doesn't produce a candidate within 1 week.**

## Acceptance Criteria for a Valid Trial

A trial file in this directory counts toward v0.9 sign-off only if all of
the following are true:

- [ ] **Named decider** (first name at minimum, plus role/company context).
- [ ] **Real live decision** — not a hypothetical. The decider must name a
      decision they are currently making in the next 2–4 weeks with an
      observable outcome (go/no-go, pursue/pass).
- [ ] **Cold run** — `/landscape` executed exactly as a first-time user
      would run it. No hand-editing of outputs, no pre-briefing of the
      decider.
- [ ] **Live read-along** — author present (in person or on call) while the
      decider reads the three files (`strategic_briefing.md`,
      `scenario_library.md`, `report.md`).
- [ ] **Recorded verdict** — one-paragraph write-up in a new file named
      `YYYY-MM-DD-<initials>.md` in this directory, using the template
      below.

## Trial File Template

Copy this into a new `YYYY-MM-DD-<initials>.md` file after running a trial.

```markdown
# Decider Trial — <YYYY-MM-DD> — <initials>

**Decider:** <first name, role, company context>
**Relationship:** <network / favor / paid expert call>
**Decision under evaluation:** <one sentence — indication/target/technology>
**Decision window:** <when they will actually make the call>

## What /landscape said
<2–5 bullets summarising the headline output the decider actually read>

## What the decider did after reading
<same call / different call / ignored — be concrete>

## Top 3 complaints from the decider
1.
2.
3.

## Moments that mattered (the UX signal)
- Where did they pause or frown?
- Which sentences did they read twice?
- Did they say "I didn't know that" at any point?
- Did they say "this is wrong because..."?

## Author's assessment
Did this change their mind, confirm their mind, or waste their time?

## v0.10 implications
<concrete defects or scope items this trial surfaced>
```

## v0.9 Exit Gate

`/landscape` stays tagged `v0.9-internal` until this directory contains at
least one trial file that meets all acceptance criteria above. On first
valid trial:

- If verdict is "changed their call" or "confirmed their call with new
  signal": update `SKILL.md` status from `v0.9-internal` to `v0.9`, merge
  publicly.
- If verdict is "wasted their time" or "ignored": this is not a failure —
  it is a free v0.10 scoping document. Fold the decider's top-3 complaints
  into the v0.10 backlog and re-run with a different decider.

---

*Last updated: 2026-04-05. This README is a placeholder until the first
real trial lands.*
