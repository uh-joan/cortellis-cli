#!/usr/bin/env python3
"""
compute_delta.py — Diff two versions of an internal document.

Returns a dict with:
  added_lines, removed_lines  — text diff counts (A)
  added_entities, removed_entities — entity delta (A)
  claude_summary — prose summary of what changed (B)
  csv_table — list of {key, column, old, new, pct} rows (C, CSV only)
"""

import csv
import difflib
import io
import os
import re
import shutil
import subprocess
import sys


def compute_delta(
    old_path: str,
    new_path: str,
    old_text: str,
    new_text: str,
    old_entity_slugs: list[str],
    new_entity_slugs: list[str],
) -> dict:
    old_set = set(old_entity_slugs)
    new_set = set(new_entity_slugs)

    # A: text diff
    old_lines = old_text.splitlines()
    new_lines = new_text.splitlines()
    diff = list(difflib.unified_diff(old_lines, new_lines, lineterm=""))
    added_lines = [l[1:] for l in diff if l.startswith("+") and not l.startswith("+++")]
    removed_lines = [l[1:] for l in diff if l.startswith("-") and not l.startswith("---")]

    # C: CSV numeric delta (before calling Claude, so summary can mention it)
    ext = os.path.splitext(old_path)[1].lower()
    csv_table = _csv_delta(old_path, new_path) if ext == ".csv" else None

    # B: Claude prose summary (only if meaningful change)
    claude_summary = None
    if len(added_lines) + len(removed_lines) > 5:
        claude_summary = _claude_summary(old_text, new_text, csv_table)

    return {
        "added_lines": len(added_lines),
        "removed_lines": len(removed_lines),
        "added_entities": sorted(new_set - old_set),
        "removed_entities": sorted(old_set - new_set),
        "claude_summary": claude_summary,
        "csv_table": csv_table,
    }


def format_changelog_entry(delta: dict, timestamp: str) -> str:
    """Render a changelog entry in markdown."""
    lines = [f"## {timestamp}", ""]

    if delta.get("claude_summary"):
        lines += [f"**Summary:** {delta['claude_summary']}", ""]

    entity_parts = []
    if delta["added_entities"]:
        entity_parts.append("Added: " + ", ".join(f"`{s}`" for s in delta["added_entities"]))
    if delta["removed_entities"]:
        entity_parts.append("Removed: " + ", ".join(f"`{s}`" for s in delta["removed_entities"]))
    if entity_parts:
        lines += [f"**Entities:** {' · '.join(entity_parts)}", ""]

    a, r = delta["added_lines"], delta["removed_lines"]
    if a or r:
        net = a - r
        lines += [f"**Content:** +{a} lines, −{r} lines ({net:+d} net)", ""]

    if delta.get("csv_table"):
        lines += ["**Numeric changes:**", ""]
        lines += ["| Entity | Column | Old | New | Δ |", "|--------|--------|-----|-----|---|"]
        for row in delta["csv_table"]:
            lines.append(
                f"| {row['key']} | {row['column']} | {row['old']} | {row['new']} | {row['pct']:+.1f}% |"
            )
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _csv_delta(old_path: str, new_path: str) -> list[dict] | None:
    """Compare numeric cells between two CSV files. Returns changed rows only."""
    try:
        old_rows = _load_csv(old_path)
        new_rows = _load_csv(new_path)
    except Exception:
        return None

    if not old_rows or not new_rows:
        return None

    # Use first column as the row key
    key_col = list(old_rows[0].keys())[0]
    old_by_key = {r[key_col]: r for r in old_rows}
    new_by_key = {r[key_col]: r for r in new_rows}

    changes = []
    for key, new_row in new_by_key.items():
        old_row = old_by_key.get(key)
        if not old_row:
            continue
        for col, new_val in new_row.items():
            if col == key_col:
                continue
            old_num = _parse_num(old_row.get(col, ""))
            new_num = _parse_num(new_val)
            if old_num is None or new_num is None or old_num == 0:
                continue
            pct = (new_num - old_num) / abs(old_num) * 100
            if abs(pct) >= 1.0:  # only report ≥1% change
                changes.append({
                    "key": key,
                    "column": col,
                    "old": _fmt_num(old_num),
                    "new": _fmt_num(new_num),
                    "pct": pct,
                })

    # Sort by absolute change descending
    changes.sort(key=lambda x: abs(x["pct"]), reverse=True)
    return changes[:20] if changes else None  # cap at 20 rows


def _load_csv(path: str) -> list[dict]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _parse_num(val: str) -> float | None:
    """Strip currency symbols, commas, B/M suffixes and parse as float."""
    if not val:
        return None
    clean = re.sub(r"[$,\s]", "", str(val).strip())
    multiplier = 1.0
    if clean.upper().endswith("B"):
        multiplier = 1e9
        clean = clean[:-1]
    elif clean.upper().endswith("M"):
        multiplier = 1e6
        clean = clean[:-1]
    elif clean.upper().endswith("K"):
        multiplier = 1e3
        clean = clean[:-1]
    try:
        return float(clean) * multiplier
    except ValueError:
        return None


def _fmt_num(n: float) -> str:
    if abs(n) >= 1e9:
        return f"${n / 1e9:.1f}B"
    if abs(n) >= 1e6:
        return f"${n / 1e6:.1f}M"
    if abs(n) >= 1e3:
        return f"${n / 1e3:.1f}K"
    return f"{n:.2f}"


def _claude_summary(old_text: str, new_text: str, csv_table: list[dict] | None) -> str | None:
    claude = shutil.which("claude")
    if not claude:
        return None

    csv_hint = ""
    if csv_table:
        top = csv_table[:5]
        csv_hint = "\n\nKey numeric changes:\n" + "\n".join(
            f"  {r['key']} / {r['column']}: {r['old']} → {r['new']} ({r['pct']:+.1f}%)" for r in top
        )

    prompt = (
        "You are summarising the difference between two versions of a pharmaceutical market document. "
        "Write ONE concise sentence (max 40 words) describing what materially changed. "
        "Focus on strategic implications (revised forecasts, new drugs mentioned, changed market share). "
        "Do not start with 'The document'.\n\n"
        f"--- OLD (excerpt) ---\n{old_text[:2000]}\n\n"
        f"--- NEW (excerpt) ---\n{new_text[:2000]}"
        f"{csv_hint}"
    )

    try:
        result = subprocess.run(
            [claude, "--print", "-p", prompt, "--max-turns", "1"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        summary = result.stdout.strip()
        return summary if summary else None
    except Exception:
        return None
