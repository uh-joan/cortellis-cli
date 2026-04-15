#!/usr/bin/env python3
"""
portfolio_report.py — Cross-indication portfolio comparison from compiled wiki.

Reads all wiki/indications/*.md articles and produces a portfolio-level
comparison table, company heatmap, and trend signals. No API calls needed.

Usage: python3 portfolio_report.py [--wiki-dir DIR]
"""

import os
import sys

# Allow running as standalone script
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))

from cli_anything.cortellis.utils.data_helpers import safe_float, safe_int
from cli_anything.cortellis.utils.wiki import wiki_root, list_articles


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    # Parse --wiki-dir
    wiki_dir_override = None
    for i, arg in enumerate(sys.argv):
        if arg == "--wiki-dir" and i + 1 < len(sys.argv):
            wiki_dir_override = sys.argv[i + 1]

    base_dir = wiki_dir_override or os.getcwd()
    w_dir = wiki_root(base_dir)

    # Load all indication articles
    articles = list_articles(w_dir, "indications")
    if not articles:
        print("No compiled landscape articles found. Run /landscape first.")
        sys.exit(0)

    # -----------------------------------------------------------------------
    # Section 1: Indication Comparison Table
    # -----------------------------------------------------------------------

    # Build rows sorted by total_drugs descending
    rows = []
    for art in articles:
        meta = art["meta"]
        title = meta.get("title", meta.get("slug", "Unknown"))
        total_drugs = safe_int(meta.get("total_drugs", 0))
        total_deals = safe_int(meta.get("total_deals", 0))
        top_company = meta.get("top_company", "-") or "-"
        freshness = meta.get("freshness_level", "unknown") or "unknown"

        phase_counts = meta.get("phase_counts")
        if phase_counts and isinstance(phase_counts, dict):
            launched = safe_int(phase_counts.get("launched"))
            phase3 = safe_int(phase_counts.get("phase3"))
            phase2 = safe_int(phase_counts.get("phase2"))
            phase1 = safe_int(phase_counts.get("phase1"))
            discovery = safe_int(phase_counts.get("discovery"))
            has_phases = True
        else:
            launched = phase3 = phase2 = phase1 = discovery = None
            has_phases = False

        rows.append({
            "title": title,
            "total_drugs": total_drugs,
            "launched": launched,
            "phase3": phase3,
            "phase2": phase2,
            "phase1": phase1,
            "discovery": discovery,
            "has_phases": has_phases,
            "total_deals": total_deals,
            "top_company": top_company,
            "freshness": freshness,
            "meta": meta,
        })

    rows.sort(key=lambda r: r["total_drugs"], reverse=True)

    print("## Cross-Indication Portfolio View")
    print(f"> Generated from {len(rows)} compiled landscape articles")
    print()
    print("### Indication Comparison")
    print("| Indication | Drugs | Launched | P3 | P2 | P1 | Discovery | Deals | Top Company | Freshness |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        if r["has_phases"]:
            launched_str = str(r["launched"])
            p3_str = str(r["phase3"])
            p2_str = str(r["phase2"])
            p1_str = str(r["phase1"])
            disc_str = str(r["discovery"])
        else:
            launched_str = p3_str = p2_str = p1_str = disc_str = "-"
        print(
            f"| {r['title']}"
            f" | {r['total_drugs']}"
            f" | {launched_str}"
            f" | {p3_str}"
            f" | {p2_str}"
            f" | {p1_str}"
            f" | {disc_str}"
            f" | {r['total_deals']}"
            f" | {r['top_company']}"
            f" | {r['freshness']} |"
        )
    print()

    # -----------------------------------------------------------------------
    # Section 2: Company Presence Across Indications
    # -----------------------------------------------------------------------

    # Build company → list of {indication, cpi_score, tier}
    company_map = {}  # company_name -> list of dicts
    for r in rows:
        meta = r["meta"]
        indication = r["title"]
        company_rankings = meta.get("company_rankings")
        if not company_rankings or not isinstance(company_rankings, list):
            continue
        for entry in company_rankings:
            if not isinstance(entry, dict):
                continue
            company = entry.get("company", "")
            if not company:
                continue
            if company not in company_map:
                company_map[company] = []
            company_map[company].append({
                "indication": indication,
                "cpi_score": safe_float(entry.get("cpi_score", 0)),
                "tier": entry.get("tier", ""),
            })

    # Filter to companies appearing in 2+ indications, sort by count descending
    multi_indication = [
        (company, entries)
        for company, entries in company_map.items()
        if len(entries) >= 2
    ]
    multi_indication.sort(key=lambda x: (-len(x[1]), x[0]))

    print("### Company Presence Across Indications")
    if multi_indication:
        print("| Company | Indications | Areas | Best CPI |")
        print("|---|---|---|---|")
        for company, entries in multi_indication:
            count = len(entries)
            areas = ", ".join(e["indication"].lower() for e in entries)
            best_cpi = max(e["cpi_score"] for e in entries)
            print(f"| {company} | {count} | {areas} | {best_cpi:.1f} |")
    else:
        print("*No companies appear across multiple indications in the current wiki.*")
    print()

    # -----------------------------------------------------------------------
    # Section 3: Portfolio Signals
    # -----------------------------------------------------------------------

    print("### Portfolio Signals")

    # Largest pipeline
    if rows:
        largest = rows[0]  # already sorted descending
        print(f"- Largest pipeline: {largest['title']} ({largest['total_drugs']} drugs)")

        # Smallest pipeline
        smallest = rows[-1]
        print(f"- Smallest pipeline: {smallest['title']} ({smallest['total_drugs']} drugs)")

    # Most deals
    if rows:
        most_deals_row = max(rows, key=lambda r: r["total_deals"])
        print(f"- Most deals: {most_deals_row['title']} ({most_deals_row['total_deals']})")

    # Most cross-indication company
    if multi_indication:
        top_company_name, top_company_entries = multi_indication[0]
        print(f"- Most cross-indication company: {top_company_name} ({len(top_company_entries)} areas)")
    else:
        print("- Most cross-indication company: N/A (no cross-indication data)")

    # Stale articles
    stale = [r["title"] for r in rows if r.get("freshness") not in ("ok", "")]
    if stale:
        print(f"- Stale data: {', '.join(stale)}")
    else:
        print("- Stale data: None (all articles fresh)")


if __name__ == "__main__":
    main()
