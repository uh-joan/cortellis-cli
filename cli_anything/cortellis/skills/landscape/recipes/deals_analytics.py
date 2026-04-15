#!/usr/bin/env python3
"""Analyze deals from CSV and output markdown analytics section.

Usage: python3 deals_analytics.py <deals_csv> [deals_meta_json]

Reads deals.csv (title,id,principal,partner,type,date) and produces:
- Deal type breakdown (bar chart)
- Top deal-makers (most active companies)
- Deal velocity (deals per quarter)
- Date range covered

Outputs markdown to stdout.
"""
import csv
import json
import os
import sys
from collections import Counter
from datetime import datetime


def load_deals(csv_path):
    if not os.path.exists(csv_path):
        return []
    with open(csv_path) as f:
        return list(csv.DictReader(f))


def quarter_key(date_str):
    """Convert date string to 'YYYY-QN' format."""
    try:
        dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
        q = (dt.month - 1) // 3 + 1
        return f"{dt.year}-Q{q}"
    except (ValueError, TypeError):
        return None


def bar_chart(data, title, max_width=35, char="█"):
    if not data:
        return ""
    max_val = max(v for _, v in data)
    if max_val == 0:
        return ""
    lines = [title, "─" * 55]
    for label, value in data:
        bar_len = int(value / max_val * max_width) if max_val > 0 else 0
        lines.append(f"  {label:35s} {char * max(bar_len, 1)} {value}")
    return "\n".join(lines)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 deals_analytics.py <deals_csv> [deals_meta_json]", file=sys.stderr)
        sys.exit(1)

    csv_path = sys.argv[1]
    meta_path = sys.argv[2] if len(sys.argv) > 2 else None

    deals = load_deals(csv_path)
    if not deals:
        print("No deals to analyze.", file=sys.stderr)
        sys.exit(0)

    # Load metadata
    total_all_time = len(deals)
    if meta_path and os.path.exists(meta_path):
        try:
            with open(meta_path) as f:
                meta = json.load(f)
            total_all_time = int(meta.get("totalResults", len(deals)))
        except Exception:
            pass

    # Date range
    dates = [d.get("date", "")[:10] for d in deals if d.get("date", "")[:10]]
    dates_sorted = sorted(dates)
    oldest = dates_sorted[0] if dates_sorted else "?"
    newest = dates_sorted[-1] if dates_sorted else "?"

    print("## Deal Analytics")
    print()
    print(f"**{len(deals)} deals analyzed** (of {total_all_time} all-time) | **Period:** {oldest} to {newest}")
    print()

    # Deal type breakdown
    type_counts = Counter(d.get("type", "Unknown") for d in deals)
    type_data = type_counts.most_common(10)
    if type_data:
        print("```")
        print(bar_chart(type_data, "Deal Type Breakdown"))
        print("```")
        print()

    # Top deal-makers (companies appearing as principal or partner)
    company_counts = Counter()
    for d in deals:
        principal = d.get("principal", "").strip()
        partner = d.get("partner", "").strip()
        if principal:
            company_counts[principal] += 1
        if partner:
            company_counts[partner] += 1

    top_companies = company_counts.most_common(10)
    if top_companies:
        print("### Top Deal-Makers")
        print()
        print("| Company | Deals | Role |")
        print("|---------|-------|------|")
        for company, count in top_companies:
            # Determine primary role
            as_principal = sum(1 for d in deals if d.get("principal", "").strip() == company)
            as_partner = sum(1 for d in deals if d.get("partner", "").strip() == company)
            if as_principal > as_partner:
                role = f"Principal ({as_principal}), Partner ({as_partner})"
            else:
                role = f"Partner ({as_partner}), Principal ({as_principal})"
            print(f"| {company[:40]} | {count} | {role} |")
        print()

    # Deal velocity by quarter
    quarter_counts = Counter()
    for d in deals:
        qk = quarter_key(d.get("date", ""))
        if qk:
            quarter_counts[qk] += 1

    quarters_sorted = sorted(quarter_counts.items())
    if quarters_sorted:
        print("### Deal Velocity (by quarter)")
        print()
        print("```")
        print(bar_chart(quarters_sorted, "Deals per Quarter", char="▓"))
        print("```")
        print()

    # Value summary (if available)
    # Note: deals.csv doesn't include financial fields yet
    # This section is ready for when deals_to_csv.py is extended

    # Summary stats
    print("### Summary")
    print()
    print("| Metric | Value |")
    print("|--------|-------|")
    print(f"| Deals analyzed | {len(deals)} |")
    print(f"| All-time total | {total_all_time} |")
    print(f"| Date range | {oldest} to {newest} |")
    print(f"| Unique deal types | {len(type_counts)} |")
    print(f"| Unique companies involved | {len(company_counts)} |")
    if quarters_sorted:
        avg_per_q = len(deals) / len(quarters_sorted)
        print(f"| Avg deals per quarter | {avg_per_q:.1f} |")
    print()
