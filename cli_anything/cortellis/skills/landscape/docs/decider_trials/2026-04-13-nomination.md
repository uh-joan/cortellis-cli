# Decider Trial — Nomination — 2026-04-13 — Carlos

**WARNING — Simulation note:** This nomination is being generated on 2026-04-05 by an LLM role-playing Carlos as a dry-run of the 2026-04-13 nomination step. A production trial requires a real human BD practitioner making a real in-flight decision. This file exists to exercise the trial workflow end-to-end before the actual 2026-04-15 session.

**Nominator:** Carlos (uh-carlos) — Director, Business Development & Competitive Intelligence, mid-sized specialty pharma (~$2B revenue, respiratory/fibrosis focus, US-EU footprint)
**Nomination date:** 2026-04-13
**Scheduled trial date:** 2026-04-15

## Decision under evaluation

In-license or option-to-license a Phase 2-ready small-molecule TEAD inhibitor for unresectable malignant pleural mesothelioma (MPM) with potential expansion into NF2-mutant NSCLC, from a Series B biotech currently running a 24-patient Phase 1/2 dose-escalation study (data read-out expected Q3 2026).

## Why this decision

The asset entered our formal BD screening committee in mid-March 2026 after a CDA was signed. The originator biotech has initiated parallel discussions with two other mid-cap acquirers, creating a competitive process with a soft exclusivity window closing around May 9, 2026. The go/no-go hinges on two questions: (1) whether the MPM competitive landscape is defensible given merck's lurbinectedin label expansion discussions and the broader Hippo/YAP-TEAD crowding, and (2) whether the NF2-mutant NSCLC expansion thesis holds up under competitive scrutiny given current ADC saturation in that space. Our internal CI team has done a first-pass pull, but the committee chair asked for an independent landscape read before the term-sheet decision meeting scheduled for April 28.

## Decision window

Internal BD committee vote on whether to submit a term sheet: **April 28, 2026**. If committee approves, a non-binding LOI would be issued to the biotech by May 2, 2026, ahead of their exclusivity window close on May 9.

## Observable outcome

Within 2–4 weeks of the trial date (by May 9, 2026), one of the following will be externally or semi-externally visible:
- A signed LOI or exclusivity agreement referenced in the biotech's next investor update or disclosed in a subsequent financing announcement
- An internal committee outcome Carlos can confirm verbally to Joan and Kimon post-vote (April 28 is within 13 days of trial)
- Alternatively, if the committee passes, the asset will surface on partnering databases or the biotech will re-open their process publicly

The April 28 committee vote is the clearest hard checkpoint — Carlos can report the outcome within 24 hours of that meeting.

## Cortellis coverage check (for Joan)

Joan should run the following on 2026-04-15 (cold, no pre-briefing):

```
/landscape "malignant pleural mesothelioma"
```

Secondary pull to check NSCLC expansion thesis and TEAD inhibitor competitive density:

```
/landscape "NF2-mutant NSCLC"
```

Both MPM and NF2-mutant NSCLC are within Cortellis's standard oncology coverage. MPM has a well-populated drug pipeline (lurbinectedin, nivolumab combinations, tumor-treating fields entries) and active deal history. NF2/TEAD is a named target class in Cortellis with at least three programs indexed as of late 2025 (Vivace Therapeutics, Vesalius Bio, IAG).

If `/landscape` requires a target-level invocation rather than indication-level, also try:

```
/landscape --target "TEAD1"
```

The indication-level MPM pull is the primary test. The NF2/NSCLC secondary pull is optional but would stress-test whether `/landscape` handles niche indication + mechanism overlap correctly.

## Acceptance checklist (from decider_trials/README.md)

- [x] Named decider (Carlos, Director BD/CI, mid-sized specialty pharma, respiratory/fibrosis focus)
- [x] Real live decision (simulated as-if: in-license/option for TEAD inhibitor in MPM with NF2-NSCLC expansion thesis)
- [x] Observable outcome within 2–4 weeks (committee vote April 28; LOI by May 2; exclusivity window closes May 9)
- [x] Indication supported by Cortellis coverage (MPM and NF2-mutant NSCLC are standard oncology coverage areas)
- [x] Independent of /landscape authorship (Carlos is external network contact, not on Joan's team)
- [x] Nominated >=48 hours before trial (2026-04-13 nomination → 2026-04-15 trial)
