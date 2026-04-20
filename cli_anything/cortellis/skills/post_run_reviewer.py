#!/usr/bin/env python3
"""Post-run skill reviewer — generates a manifest of what a skill run produced.

Scans the skill's run directory, classifies each JSON/markdown file as
populated or empty, and prints a structured manifest for Claude to review.

Claude reads this output and decides whether to patch the skill's SKILL.md
with generalizable optimizations (e.g. "CPIC always empty for biologics").

Usage:
  python3 post_run_reviewer.py <skill_name> <run_dir> [input_label]

Examples:
  python3 post_run_reviewer.py drug-profile /tmp/drug_profile "semaglutide"
  python3 post_run_reviewer.py landscape /tmp/landscape_obesity "obesity"
  python3 post_run_reviewer.py pipeline /tmp/pipeline_novonordisk "Novo Nordisk"
"""
import json
import os
import sys

# JSON files considered "empty" if their content parses to one of these
_EMPTY_VALUES = ({}, [], "", None)
# Byte threshold: files under this are almost certainly empty/error responses
_SPARSE_THRESHOLD = 200


def classify_json(path):
    """Return ('populated', size) or ('empty', reason) or ('error', reason)."""
    try:
        size = os.path.getsize(path)
        with open(path) as f:
            raw = f.read().strip()
        if not raw or raw in ("{}", "[]", "null"):
            return "empty", "blank"
        try:
            data = json.loads(raw)
            if data in _EMPTY_VALUES:
                return "empty", "null/empty structure"
            if isinstance(data, dict) and len(data) == 0:
                return "empty", "empty dict"
            if isinstance(data, list) and len(data) == 0:
                return "empty", "empty list"
            # Check for API error wrappers
            if isinstance(data, dict):
                if data.get("error") or data.get("Error") or data.get("fault"):
                    return "empty", f"API error: {list(data.keys())[:3]}"
                # Sparse: parsed fine but suspiciously small
                if size < _SPARSE_THRESHOLD:
                    return "sparse", f"{size}b"
            return "populated", size
        except (json.JSONDecodeError, ValueError):
            if size < _SPARSE_THRESHOLD:
                return "empty", f"unparseable, {size}b"
            return "populated", size  # non-JSON but substantial (e.g. raw text)
    except OSError:
        return "error", "read error"


def scan_dir(run_dir):
    """Scan run_dir and return classified file list."""
    if not os.path.isdir(run_dir):
        return []

    results = []
    for fname in sorted(os.listdir(run_dir)):
        fpath = os.path.join(run_dir, fname)
        if not os.path.isfile(fpath):
            continue

        # Pagination metadata files are intentionally small — not content
        if fname.endswith(".meta.json"):
            continue

        if fname.endswith(".json"):
            status, detail = classify_json(fpath)
            results.append((fname, status, detail))
        elif fname.endswith(".md") or fname.endswith(".csv"):
            size = os.path.getsize(fpath)
            status = "populated" if size > _SPARSE_THRESHOLD else "sparse"
            results.append((fname, status, size))

    return results


def format_manifest(skill_name, run_dir, input_label, files):
    """Format the manifest for Claude to read."""
    lines = []
    lines.append(f"=== Post-Run Manifest: {skill_name} / {input_label} ===")
    lines.append(f"Run dir: {run_dir}")
    lines.append("")

    populated = [(f, d) for f, s, d in files if s == "populated"]
    sparse = [(f, d) for f, s, d in files if s == "sparse"]
    empty = [(f, d) for f, s, d in files if s == "empty"]
    errors = [(f, d) for f, s, d in files if s == "error"]
    missing = _expected_but_missing(skill_name, {f for f, s, d in files})

    if populated:
        lines.append(f"POPULATED ({len(populated)} files — data found):")
        for fname, detail in populated:
            size_str = f"{detail:,}b" if isinstance(detail, int) else str(detail)
            lines.append(f"  {fname:<35} {size_str}")
        lines.append("")

    if sparse:
        lines.append(f"SPARSE ({len(sparse)} files — minimal data):")
        for fname, detail in sparse:
            lines.append(f"  {fname:<35} {detail}")
        lines.append("")

    if empty:
        lines.append(f"EMPTY ({len(empty)} files — no data returned):")
        for fname, detail in empty:
            lines.append(f"  {fname:<35} ({detail})")
        lines.append("")

    if errors:
        lines.append(f"ERRORS ({len(errors)} files — failed to read):")
        for fname, detail in errors:
            lines.append(f"  {fname:<35} {detail}")
        lines.append("")

    if missing:
        lines.append(f"NOT RUN ({len(missing)} optional steps skipped):")
        for fname in sorted(missing):
            lines.append(f"  {fname}")
        lines.append("")

    lines.append("=" * 60)
    lines.append("")
    lines.append("REVIEW INSTRUCTIONS FOR CLAUDE:")
    lines.append("Read the manifest above and consider patching the skill's")
    lines.append("## Learned Optimizations section in SKILL.md — but ONLY if")
    lines.append("you see a finding that clearly generalizes beyond this single run.")
    lines.append("")
    lines.append("Good candidates to encode:")
    lines.append("  - An optional step that returned empty (e.g. cpic.json always")
    lines.append("    empty for biologics — skip for large-molecule drugs)")
    lines.append("  - An optional step that always errors for this input class")
    lines.append("  - A populated file that proves an optional step is worth running")
    lines.append("")
    lines.append("Do NOT patch for one-off anomalies. If unsure, skip.")
    lines.append("Use a targeted patch (find-replace on the Learned Optimizations")
    lines.append("section), not a full SKILL.md rewrite.")

    return "\n".join(lines)


def _expected_but_missing(skill_name, found_files):
    """Return optional files expected for this skill that weren't written."""
    OPTIONAL = {
        "drug-profile": {
            "cpic.json", "chembl.json", "biorxiv.json",
            "fda_approvals.json", "ema_approvals.json", "fda_patent.json",
            "ct_trials.json", "literature.json",
        },
        "landscape": {
            # Optional enrichment steps
            "trials_summary.csv", "regulatory_milestones.csv",
            "press_releases_summary.csv", "historical_timeline.md",
            "scenario_analysis.md", "loe_analysis.md",
            "approval_regions.json",
        },
        "pipeline": {
            # SI data (may be empty for some companies)
            "phase1_si.csv", "preclinical_si.csv",
            # External enrichment
            "opentargets_pipeline.md", "biorxiv_pipeline.md",
        },
        "target-profile": {
            # External enrichment — may be absent for niche targets
            "cpic.json", "chembl_target.json", "uniprot.json",
            "opentargets.json", "alphafold.json",
            "briefings.json", "publications.json",
        },
        "drug-comparison": {
            # Financials are empty for pipeline drugs
            "financials_1.json", "financials_2.json",
        },
    }
    expected = OPTIONAL.get(skill_name, set())
    return expected - found_files


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 post_run_reviewer.py <skill_name> <run_dir> [input_label]",
              file=sys.stderr)
        sys.exit(1)

    skill_name = sys.argv[1]
    run_dir = sys.argv[2]
    input_label = sys.argv[3] if len(sys.argv) > 3 else os.path.basename(run_dir)

    files = scan_dir(run_dir)
    if not files:
        print(f"No files found in {run_dir} — skipping review.", file=sys.stderr)
        sys.exit(0)

    print(format_manifest(skill_name, run_dir, input_label, files))
