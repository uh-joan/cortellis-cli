#!/usr/bin/env python3
"""
signals_report.py — Generate strategic intelligence report from compiled wiki.

Scans all indication articles for changes, ranks signals by severity,
and produces a comprehensive cross-portfolio intelligence report.

Usage: python3 signals_report.py [--wiki-dir DIR] [--days 30]
"""

import os
import sys

# Allow running as standalone script
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))

from cli_anything.cortellis.utils.intelligence import generate_signals_report, extract_signals
from cli_anything.cortellis.utils.wiki import wiki_root, log_activity


def main():
    # Parse --wiki-dir and --days
    wiki_dir_override = None
    max_age_days = 30
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
        else:
            i += 1

    base_dir = wiki_dir_override or os.getcwd()

    signals = extract_signals(base_dir, max_age_days=max_age_days)
    report = generate_signals_report(base_dir, max_age_days=max_age_days)
    print(report)

    # Also write to wiki/SIGNALS_REPORT.md
    w_dir = wiki_root(base_dir)
    report_path = os.path.join(w_dir, "SIGNALS_REPORT.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)

    log_activity(w_dir, "signal", f"Generated signals report ({len(signals)} signals)")


if __name__ == "__main__":
    main()
