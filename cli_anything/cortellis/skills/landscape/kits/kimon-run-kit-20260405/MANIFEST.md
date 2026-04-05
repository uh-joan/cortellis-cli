# Kimon Run Kit — kimon-run-kit-20260405

| Field | Value |
|-------|-------|
| Kit version | kimon-run-kit-20260405 |
| Built | 2026-04-05 |
| Built by | worker-kit (landscape-council-act team) |
| Retrospective blind test protocol ID | retrospective-blind-v1-20260405 |

## Purpose

Frozen artifact set for independent harness re-run by the observer role (independence pass
scheduled per `docs/validation_harness.md`). The observer re-runs the kit from scratch,
compares hashes, and records findings in `FINDINGS.md`.

## One-command invocation

```bash
bash cli_anything/cortellis/skills/landscape/kits/kimon-run-kit-20260405/run_kit.sh
```

Run from the repository root (`/Users/janisaez/code/cortellis-cli`).

## Expected harness outcomes (reference for observer comparison)

| Indication | Preset | strategic_scores.md | strategic_briefing.md | scenario_library.md | opportunity_matrix.csv |
|------------|--------|--------------------|-----------------------|---------------------|------------------------|
| asthma | default | regenerated | regenerated | regenerated | regenerated |
| ipf | respiratory | regenerated | regenerated | regenerated | regenerated |
| als | rare_cns | regenerated | regenerated | regenerated | regenerated |
| obesity | default | regenerated | regenerated | regenerated | regenerated |
| alzheimers-disease | default | regenerated | regenerated | regenerated | regenerated |

Indications with no `raw/` folder present are skipped with a printed note.

Reproducibility gate: `pytest cli_anything/cortellis/tests/test_strategic_reproducibility.py` must pass 4/4.

Hash reference: see `EXPECTED_HASHES.txt` (sha256 of each produced `.md` file).

## What the observer must NOT do

- Do not edit any source files, recipe scripts, or configuration files before running.
- Do not tune weights, presets, or thresholds.
- Do not re-run partial subsets of the kit and report partial results as a full run.
- Do not modify `EXPECTED_HASHES.txt` before comparing.

## How to report deviations

1. Copy `FINDINGS_TEMPLATE.md` to `FINDINGS.md` inside this kit directory.
2. Fill in each section honestly, including any hash mismatches and your plain-English read.
3. Do not alter `EXPECTED_HASHES.txt` or regenerated output files to force hash matches.
4. Send or commit `FINDINGS.md` to the team-lead for review.
