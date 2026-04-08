#!/usr/bin/env python3
"""
diff_landscape.py — Compare current landscape with its previous snapshot.

Reads compiled wiki articles and surfaces changes in drug counts,
deal activity, and company rankings without any API calls.

Usage: python3 diff_landscape.py <indication_slug> [--wiki-dir DIR]
"""

import os
import sys

# Allow running as standalone script
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))

from cli_anything.cortellis.utils.wiki import (
    article_path,
    diff_snapshots,
    read_article,
)


# ---------------------------------------------------------------------------
# Markdown formatting
# ---------------------------------------------------------------------------

PHASE_LABELS = {
    "launched": "Launched",
    "phase3": "Phase 3",
    "phase2": "Phase 2",
    "phase1": "Phase 1",
    "discovery": "Discovery",
    "other": "Other",
}


def _fmt_delta(delta: int) -> str:
    """Format an integer delta with explicit +/- sign."""
    if delta > 0:
        return f"+{delta}"
    elif delta < 0:
        return str(delta)
    return "0"


def format_diff_markdown(diff: dict, indication_title: str) -> str:
    """Render a diff dict as a markdown report."""
    drug_changes = diff["drug_changes"]
    deal_changes = diff["deal_changes"]
    companies = diff["company_changes"]

    lines = []

    lines.append(f"## Landscape Changes: {indication_title}")
    lines.append(
        f"**Period**: {(diff['previous_date'] or 'N/A')[:10]} → {(diff['current_date'] or 'N/A')[:10]}"
        f" ({diff['days_between']} days)"
    )
    lines.append("")

    # Drug Pipeline
    lines.append("### Drug Pipeline")
    by_phase = drug_changes.get("by_phase") or {}
    total = drug_changes["total"]

    if by_phase:
        lines.append("| Phase | Before | After | Change |")
        lines.append("|---|---|---|---|")
        for phase_key in ("launched", "phase3", "phase2", "phase1", "discovery", "other"):
            if phase_key not in by_phase:
                continue
            p = by_phase[phase_key]
            label = PHASE_LABELS.get(phase_key, phase_key)
            lines.append(
                f"| {label} | {p['before']} | {p['after']} | {_fmt_delta(p['delta'])} |"
            )
        lines.append(
            f"| **Total** | **{total['before']}** | **{total['after']}** |"
            f" **{_fmt_delta(total['delta'])}** |"
        )
    else:
        lines.append(
            f"- Before: {total['before']} drugs → After: {total['after']} drugs"
            f" ({_fmt_delta(total['delta'])})"
        )

    lines.append("")

    # Deal Activity
    lines.append("### Deal Activity")
    lines.append(
        f"- Before: {deal_changes['before']} deals → After: {deal_changes['after']} deals"
        f" ({_fmt_delta(deal_changes['delta'])})"
    )
    lines.append("")

    # Company Rankings
    lines.append("### Company Rankings")
    new_in = companies["new_in_top10"]
    dropped = companies["dropped_from_top10"]
    lines.append(f"- **New in top 10:** {', '.join(new_in) if new_in else 'None'}")
    lines.append(f"- **Dropped from top 10:** {', '.join(dropped) if dropped else 'None'}")

    if companies["top_company_changed"]:
        lines.append("- Top company: changed")
    else:
        lines.append("- Top company: unchanged")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print(
            "Usage: diff_landscape.py <indication_slug> [--wiki-dir DIR]",
            file=sys.stderr,
        )
        sys.exit(1)

    indication_slug = sys.argv[1]

    # Parse --wiki-dir
    wiki_dir_override = None
    for i, arg in enumerate(sys.argv):
        if arg == "--wiki-dir" and i + 1 < len(sys.argv):
            wiki_dir_override = sys.argv[i + 1]

    base_dir = wiki_dir_override or os.getcwd()

    path = article_path("indications", indication_slug, base_dir)
    article = read_article(path)

    if article is None:
        print(
            f"Error: no wiki article found for '{indication_slug}' at {path}",
            file=sys.stderr,
        )
        sys.exit(1)

    current_meta = article["meta"] or {}
    previous_snapshot = current_meta.get("previous_snapshot")

    if not previous_snapshot:
        print(
            "No previous snapshot available. "
            "Run the landscape pipeline again to enable diffs."
        )
        sys.exit(0)

    indication_title = current_meta.get("title") or indication_slug
    diff = diff_snapshots(current_meta, previous_snapshot)
    print(format_diff_markdown(diff, indication_title))


if __name__ == "__main__":
    main()
