# LLM Council Verification — /landscape v0.9 Hardening

**Date:** 2026-04-05
**Question:** Has council-transcript-v09-hardening-20260405.md been completely addressed?

---

## Framed Question

The v09 council recommended: "Ship v0.9 internally. Do not ship v0.9 externally or publicly."

**Three public-release exit gates:**
1. One named human BD decider runs /landscape on a real decision and reports whether it changed their call
2. Harness has a named human owner (replacing `@domain-reviewer`)
3. Written answer on whether Cortellis TOS permits sharing derived output

**Plus Executor's dominant risk:** Uncommitted work on a laptop.

## Current State (verified from disk)

- **Gate 2 (Harness owner):** Assigned to Joan (uh-joan), first harness run complete 2026-04-05, 4/4 PASS on NSCLC/obesity/asthma/Alzheimer's/IPF. Document acknowledges independence gap — Joan is both author and owner, tracked to v0.10.
- **Gate 3 (TOS):** ANSWERED 2026-04-05. Derived outputs shareable with attribution; code relicensed MIT. LICENSE file present at repo root.
- **Gate 1 (Decider trial):** ✗ Framework exists (`docs/decider_trials/README.md`) with acceptance criteria, recruitment plan, trial file template. **Status: "No trials recorded yet."**
- **Branch state:** ALL v09 work UNCOMMITTED. 3 modified files + 13 untracked files/dirs.
- **SKILL.md:** Does NOT contain `v0.9-internal` string. Version gating only mentioned in decider_trials README.

---

## Advisor Responses

### Contrarian

The council is flattering itself. "3 sprints, 0 users = consistency not correctness" was the right critique in v09, and nothing has changed that logic. Gate 2 is structurally satisfied in the weakest possible sense: Joan ran the harness, Joan wrote the harness, Joan passed the harness. The document itself admits this is an independence gap — that admission doesn't close the gap, it just names it. Gate 3 (TOS) is answered, but a self-written tos_check.md isn't legal counsel; it's a developer's reading of a license. Gate 1 isn't just "the last open item" — it is the entire verification strategy, because Gates 2 and 3 both have asterisks. The branch state is a separate catastrophe: no human trial has been run, and if the laptop dies tonight, the sprint doesn't exist. This work is not close to external release. The council's "ship internally" recommendation was correct and remains the ceiling.

### First Principles Thinker

Strip away the sprint vocabulary and ask the fundamental question: what does it mean for a landscape skill to be correct? It means a human decision-maker, facing real uncertainty, received output that either confirmed or changed their call in a way they could defend. None of the three gates directly test that. Gate 2 tests reproducibility on a curated test set — necessary but not sufficient. Gate 3 tests legal permission to share — irrelevant if the output is wrong. Gate 1 tests the thing that actually matters, and it has zero data points. The independence gap in Gate 2 is not a bureaucratic formality; it's a first-principles problem. A skill author running their own harness is not validation, it's self-assessment. The framing of "Gate 1 carries the independent-judgment load" is correct but understated — Gate 1 isn't carrying load, it's carrying the entire epistemic case for external release.

### Expansionist

Look at what's actually been built during this sprint: a validation harness, a scenario library, a glossary, pre-registered predictions, a fragmented indication stress test, a decider trial framework, a TOS clearance document, three presets, and five council reports. That's a real body of infrastructure. The Expansionist's instinct is to ask: does the absence of Gate 1 data actually block value delivery? For an internal audience — BD team members who understand the tool's limitations — the answer is probably no. The harness passing 4/4 on NSCLC/obesity/asthma/Alzheimer's/IPF is not nothing. The strategic narrative and scoring improvements are real. The decider trial framework is ready to run. The question isn't whether to ship externally — it isn't — it's whether to use the internal ship as a forcing function to get Gate 1 data from real internal users, which would close the loop without waiting for an external expert call.

### Outsider

From outside the pharmaceutical informatics bubble: this project has a commit problem that predates all the gates. Everything described — modified files, 13 untracked files, council reports, LICENSE, validation harness — exists only on one laptop. That is not a software project in any professional sense; it is a working directory. Before debating external release gates, the question is whether this sprint survives the weekend. The outsider also notices that the "internal ship" recommendation from v09 has no operational definition. Internal to whom? Who has access? Who has been notified? An internal ship without a named internal user list and a delivery mechanism is just "not external," which is the current state anyway. The TOS answer being self-written by the developer is the kind of thing that gets companies in trouble — not because the developer is wrong, but because "we did our own reading" is not a defensible position if it matters.

### Executor

The dominant risk I flagged in v09 was uncommitted work on a laptop. It is still true. Nothing else matters until that is resolved. Here is what needs to happen in order: commit everything to the branch tonight, push to remote, create the PR. That takes 15 minutes and eliminates the highest-severity risk in the entire project. After that, the gate analysis is straightforward: Gate 1 is open, Gates 2 and 3 are closed with acknowledged caveats. The decider trial framework is built; what's missing is a named human and a scheduled call. The independence gap in Gate 2 is real but the council correctly identified it as a v0.10 item, not a v0.9 blocker, provided Gate 1 runs. The SKILL.md version gating is a 10-minute fix — add `v0.9-internal` to the skill metadata and a runtime warning. None of this is hard. The only hard thing is Gate 1, and that requires a human outside this room.

---

## Peer Review

**Strongest:** First Principles Thinker. Cuts through gate-counting to identify that Gate 1 is the entire epistemic case, not just one of three items. The distinction between reproducibility (Gate 2) and correctness (Gate 1) is the sharpest framing in the council.

**Biggest blind spot:** Expansionist. The suggestion to use internal ship as a forcing function for Gate 1 data is the right instinct but glosses over the fact that internal users at a pharma company are still users with decision-making consequences — "internal" doesn't mean "zero stakes."

**All missed:** Nobody addressed the SKILL.md gap directly enough. The v09 council specifically recommended version gating at the skill level. That recommendation is unimplemented. A user running `/landscape` today has no indication they are on an internal-only build. That is not a policy gap — it is a user-facing omission that could cause the external-ship gate to be violated accidentally.

---

## Chairman Verdict

### Where the Council Agrees

Gate 1 (decider trial) is the only gate that validates correctness, and it has zero data points. Everything else — harness, TOS, scenario library, council reports — is infrastructure for correctness, not evidence of it. The branch must be committed before any other conversation. The independence gap in Gate 2 is real, acknowledged, and correctly deferred to v0.10 provided Gate 1 runs.

### Where the Council Clashes

Expansionist believes internal ship creates momentum toward Gate 1 closure. Contrarian and Outsider believe the independence gap and self-written TOS make even the internal ship weaker than it appears. First Principles and Executor are aligned: commit the work, then close Gate 1, in that order. The Contrarian's skepticism about TOS is worth noting but is not a sprint-blocking issue — the risk of a developer's TOS reading being wrong is real but low-severity for internal use.

### Blind Spots the Council Caught

1. **SKILL.md version gating is missing.** The v09 council recommended it. It wasn't implemented. A user can run `/landscape` with no indication they're on an internal-only build. This is the most actionable gap that isn't Gate 1.
2. **"Internal ship" has no operational definition.** Who are the internal users? What's the delivery mechanism? Without answers, internal ship = status quo.
3. **TOS self-assessment is not legal clearance.** Fine for internal use, insufficient for external. The council treated it as fully closed — it is conditionally closed.

### The Recommendation

**Internal-only. Do not promote to v0.9 external.** The v09 council's recommendation stands unchanged. Gates 2 and 3 are structurally satisfied with caveats. Gate 1 is the entire remaining case for external release, and it has zero data. The branch-uncommitted problem means the internal ship itself is not yet real — it exists only on a laptop.

**Conditional path to v0.9 external:**
1. Commit + push tonight (eliminates highest-severity risk)
2. Add `v0.9-internal` warning to SKILL.md (closes version-gating gap)
3. Run one named decider trial with real decision and real human (closes Gate 1)

At that point, all three gates are satisfied and the council has no remaining grounds to block external release.

### The One Thing to Do First

**Commit and push the branch. Right now.** Not after the decider trial, not after the SKILL.md fix, not after this council synthesis. Every other recommendation is contingent on the work surviving the weekend.

---

## v09 Verification Scorecard

| Gate | V09 Council Requirement | Current Status | Verdict |
|---|---|---|---|
| 1 | Decider trial with real human | Framework only, zero trials | **OPEN** |
| 2 | Harness owner (not `@domain-reviewer`) | Joan assigned, 4/4 PASS, independence gap acknowledged | **CLOSED with caveat** |
| 3 | Cortellis TOS answer | Answered, MIT LICENSE, attribution policy | **CLOSED with caveat** |
| Exec | Commit the branch | All work uncommitted | **OPEN — highest severity** |
| Gate | SKILL.md `v0.9-internal` marker | Not present | **OPEN — not flagged by v09 council explicitly but implied** |

**Overall:** v09 council's "internal-only" recommendation is unchanged. Structural work is substantial but the two externally-verifiable items (Gate 1 real-user data + branch commit) remain open.

---

*Generated 2026-04-05. Single-advisor council invocation.*
