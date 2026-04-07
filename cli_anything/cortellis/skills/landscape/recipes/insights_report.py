#!/usr/bin/env python3
"""
insights_report.py — View accumulated session insights from the wiki.

Usage: python3 insights_report.py [--wiki-dir DIR] [--days 30] [--indication SLUG]
"""

import os
import sys

# Allow running as standalone script
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))

from cli_anything.cortellis.utils.insights_extractor import load_recent_insights
from cli_anything.cortellis.utils.wiki import wiki_root, log_activity


def main():
    wiki_dir_override = None
    max_age_days = 30
    indication = None

    i = 1
    while i < len(sys.argv):
        if sys.argv[i] == "--wiki-dir" and i + 1 < len(sys.argv):
            wiki_dir_override = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--days" and i + 1 < len(sys.argv):
            try:
                max_age_days = int(sys.argv[i + 1])
            except ValueError:
                pass
            i += 2
        elif sys.argv[i] == "--indication" and i + 1 < len(sys.argv):
            indication = sys.argv[i + 1]
            i += 2
        else:
            i += 1

    base_dir = wiki_dir_override or os.getcwd()
    insights = load_recent_insights(base_dir, max_age_days=max_age_days, indication=indication)

    # Build report
    lines = []
    lines.append("## Accumulated Insights Report\n")
    filter_note = f" for `{indication}`" if indication else ""
    lines.append(f"> {len(insights)} insight session(s) from last {max_age_days} days{filter_note}\n\n")

    if not insights:
        lines.append("_No insights found. Run a landscape analysis to accumulate insights._\n")
    else:
        for ins in insights:
            meta = ins["meta"]
            title = meta.get("title", "Unknown")
            ts = meta.get("timestamp", "")[:10]
            lines.append(f"### {title} ({ts})\n\n")

            # Extract bullets from body
            bullet_count = 0
            for line in ins["body"].split("\n"):
                stripped = line.strip()
                if stripped.startswith("- ") and bullet_count < 6:
                    lines.append(f"{stripped}\n")
                    bullet_count += 1
            lines.append("\n")

    report = "".join(lines)
    print(report)

    # Write to wiki/INSIGHTS_REPORT.md
    w_dir = wiki_root(base_dir)
    report_path = os.path.join(w_dir, "INSIGHTS_REPORT.md")
    os.makedirs(w_dir, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)

    log_activity(w_dir, "insight", "Generated insights report")


if __name__ == "__main__":
    main()
