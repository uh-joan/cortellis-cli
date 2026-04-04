#!/usr/bin/env python3
"""
Pipeline run manifest — integrity tracking for cortellis pipeline runs.

Usage:
  python3 manifest.py write <pipeline_dir> <step_name> <exit_code> [csv_file]
      Append a step entry to <pipeline_dir>/manifest.json.

  python3 manifest.py validate <pipeline_dir>
      Validate that all expected steps ran, exited 0, and produced non-empty CSVs.
      Exits 1 if any validation fails.

  python3 manifest.py report <pipeline_dir>
      Print a human-readable markdown summary of the pipeline run.
"""

import csv
import json
import os
import sys
from datetime import datetime, timezone

EXPECTED_STEPS = [
    "api_check",
    "resolve_company",
    "launched",
    "phase3",
    "phase2",
    "phase1_ci",
    "discovery_ci",
    "phase1_si",
    "preclinical_si",
    "merge_phase1",
    "merge_preclinical",
    "resolve_indications",
    "deals",
    "trials",
    "catch_missing",
]

PAGINATION_LIMIT = 150


def _manifest_path(pipeline_dir):
    return os.path.join(pipeline_dir, "manifest.json")


def _load_manifest(pipeline_dir):
    path = _manifest_path(pipeline_dir)
    if not os.path.exists(path):
        return {"steps": []}
    with open(path, "r") as f:
        return json.load(f)


def _save_manifest(pipeline_dir, data):
    path = _manifest_path(pipeline_dir)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def _count_csv_rows(csv_file):
    """Return number of data rows (excluding header), or None on error."""
    if not csv_file or not os.path.exists(csv_file):
        return None
    try:
        with open(csv_file, newline="") as f:
            reader = csv.reader(f)
            rows = list(reader)
        # Subtract 1 for header row; if file is empty, return 0
        return max(0, len(rows) - 1) if rows else 0
    except Exception:
        return None


def cmd_write(args):
    if len(args) < 3:
        print("Usage: manifest.py write <pipeline_dir> <step_name> <exit_code> [csv_file]", file=sys.stderr)
        sys.exit(1)

    pipeline_dir = args[0]
    step_name = args[1]
    exit_code = int(args[2])
    csv_file = args[3] if len(args) >= 4 else None

    row_count = _count_csv_rows(csv_file)

    entry = {
        "step": step_name,
        "exit_code": exit_code,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "csv_file": csv_file,
        "row_count": row_count,
    }

    data = _load_manifest(pipeline_dir)
    data["steps"].append(entry)
    _save_manifest(pipeline_dir, data)
    print(f"Recorded step '{step_name}' (exit={exit_code}, rows={row_count})")


def cmd_validate(args):
    if len(args) < 1:
        print("Usage: manifest.py validate <pipeline_dir>", file=sys.stderr)
        sys.exit(1)

    pipeline_dir = args[0]
    data = _load_manifest(pipeline_dir)
    steps = data.get("steps", [])

    step_map = {s["step"]: s for s in steps}

    total = len(steps)
    failures = []
    warnings = []
    empty_csvs = []

    # Check all expected steps are present
    for expected in EXPECTED_STEPS:
        if expected not in step_map:
            failures.append(f"Missing step: {expected}")
            continue
        step = step_map[expected]

        # Non-zero exit code
        if step["exit_code"] != 0:
            failures.append(f"{expected}: non-zero exit code ({step['exit_code']})")

        # CSV with 0 rows
        if step["csv_file"] is not None and step["row_count"] == 0:
            empty_csvs.append(expected)
            failures.append(f"{expected}: CSV has 0 data rows")

        # Pagination warning
        if step["row_count"] is not None and step["row_count"] >= PAGINATION_LIMIT:
            warnings.append(f"{expected}: {step['row_count']} rows (pagination limit — may be incomplete)")

    passed = total - len([f for f in failures if "non-zero" in f or "0 data rows" in f or "Missing" not in f])
    # Simpler: count steps that have no failure
    passed_steps = sum(
        1 for s in EXPECTED_STEPS
        if s in step_map and step_map[s]["exit_code"] == 0 and not (
            step_map[s]["csv_file"] is not None and step_map[s]["row_count"] == 0
        )
    )

    print(f"Pipeline Validation Summary")
    print(f"  Total steps recorded : {total}")
    print(f"  Expected steps       : {len(EXPECTED_STEPS)}")
    print(f"  Passed               : {passed_steps}")
    print(f"  Failed               : {len(failures)}")
    print(f"  Empty CSVs           : {len(empty_csvs)}")
    print(f"  Warnings             : {len(warnings)}")

    if failures:
        print("\nFailures:")
        for f in failures:
            print(f"  - {f}")

    if warnings:
        print("\nWarnings:")
        for w in warnings:
            print(f"  - {w}")

    if failures:
        sys.exit(1)
    else:
        print("\nAll checks passed.")


def cmd_report(args):
    if len(args) < 1:
        print("Usage: manifest.py report <pipeline_dir>", file=sys.stderr)
        sys.exit(1)

    pipeline_dir = args[0]
    data = _load_manifest(pipeline_dir)
    steps = data.get("steps", [])
    step_map = {s["step"]: s for s in steps}

    print("## Pipeline Run Summary")
    print()
    print("| Step | Status | Rows | Time |")
    print("|------|--------|------|------|")

    warnings = []

    for expected in EXPECTED_STEPS:
        if expected not in step_map:
            print(f"| {expected} | MISSING | — | — |")
            continue

        step = step_map[expected]
        status = "✓" if step["exit_code"] == 0 else f"✗ (exit {step['exit_code']})"
        rows = str(step["row_count"]) if step["row_count"] is not None else "—"
        ts = step.get("timestamp", "—")

        print(f"| {expected} | {status} | {rows} | {ts} |")

        if step["row_count"] is not None and step["row_count"] >= PAGINATION_LIMIT:
            warnings.append(f"{expected}: {step['row_count']} rows (pagination limit — may be incomplete)")

    # Print any steps in manifest that aren't expected
    extra = [s for s in steps if s["step"] not in EXPECTED_STEPS]
    for step in extra:
        status = "✓" if step["exit_code"] == 0 else f"✗ (exit {step['exit_code']})"
        rows = str(step["row_count"]) if step["row_count"] is not None else "—"
        ts = step.get("timestamp", "—")
        print(f"| {step['step']} (extra) | {status} | {rows} | {ts} |")

    if warnings:
        print()
        print("**Warnings:**")
        for w in warnings:
            print(f"- {w}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    mode = sys.argv[1]
    rest = sys.argv[2:]

    if mode == "write":
        cmd_write(rest)
    elif mode == "validate":
        cmd_validate(rest)
    elif mode == "report":
        cmd_report(rest)
    else:
        print(f"Unknown mode: {mode}", file=sys.stderr)
        print("Modes: write, validate, report", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
