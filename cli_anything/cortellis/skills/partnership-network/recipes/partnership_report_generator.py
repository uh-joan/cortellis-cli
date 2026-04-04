#!/usr/bin/env python3
"""Generate a partnership network report from deal search data.

Usage: python3 partnership_report_generator.py /tmp/partnership_network "entity name"
"""
import json, sys, os
from collections import Counter

data_dir = sys.argv[1]
entity_name = sys.argv[2] if len(sys.argv) > 2 else "Unknown"


def load_json(filename):
    path = os.path.join(data_dir, filename)
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            d = json.load(f)
        if len(str(d)) < 50:
            return None
        return d
    except Exception:
        return None


def extract_deals(data):
    if not data:
        return [], "0"
    r = data.get("dealResultsOutput", {})
    total = r.get("@totalResults", "0")
    deals = r.get("SearchResults", {}).get("Deal", [])
    if isinstance(deals, dict):
        deals = [deals]
    return deals, total


def bar_chart(data, title, max_width=35, char="█"):
    if not data:
        return ""
    max_val = max(v for _, v in data)
    if max_val == 0:
        return ""
    lines = [title, "─" * 55]
    for label, value in data:
        bar_len = int(value / max_val * max_width) if max_val > 0 else 0
        lines.append(f"  {label:25s} {char * max(bar_len, 1)} {value}")
    return "\n".join(lines)


# Merge deals from principal and partner searches
all_deals = []
seen_ids = set()

for fname in ("deals_principal.json", "deals_partner.json", "deals.json"):
    deals, total = extract_deals(load_json(fname))
    for d in deals:
        did = d.get("@id", "")
        if did not in seen_ids:
            seen_ids.add(did)
            all_deals.append(d)

print(f"# Partnership Network: {entity_name}")
print()
print(f"**Total Unique Deals:** {len(all_deals)}")
print()

if not all_deals:
    print("No deals found.")
    sys.exit(0)

# Top partners
partner_counter = Counter()
partner_latest = {}
for d in all_deals:
    princ = d.get("CompanyPrincipal", "?")
    part = d.get("CompanyPartner", "?")
    date = d.get("StartDate", d.get("MostRecentEventDate", ""))
    if isinstance(date, str):
        date = date[:10]

    # The "other" company is the partner
    other = part if entity_name.lower() in str(princ).lower() else princ
    other = str(other)[:35]
    partner_counter[other] += 1
    if other not in partner_latest or (date and date > partner_latest.get(other, "")):
        partner_latest[other] = date

if partner_counter:
    print(f"## Top Partners ({len(partner_counter)} unique)")
    print()
    print("| Partner | Deals | Latest |")
    print("|---------|-------|--------|")
    for p, count in partner_counter.most_common(15):
        latest = partner_latest.get(p, "?")
        print(f"| {p} | {count} | {latest} |")
    print()

# Deal types
type_counter = Counter()
for d in all_deals:
    dtype = d.get("Type", "Unknown")
    type_counter[str(dtype)[:40]] += 1

if type_counter:
    print("## Deal Types")
    print()
    chart = bar_chart(list(type_counter.most_common(8)), "Deals by Type")
    if chart:
        print("```")
        print(chart)
        print("```")
        print()

    print("| Type | Count |")
    print("|------|-------|")
    for dtype, count in type_counter.most_common():
        print(f"| {dtype} | {count} |")
    print()

# Timeline by year
year_counter = Counter()
for d in all_deals:
    date = d.get("StartDate", "")
    if isinstance(date, str) and len(date) >= 4:
        year_counter[date[:4]] += 1

if year_counter:
    sorted_years = sorted(year_counter.items())[-10:]
    chart = bar_chart(sorted_years, "Deals by Year (last 10)")
    if chart:
        print("## Partnership Timeline")
        print()
        print("```")
        print(chart)
        print("```")
        print()

# Full deal list
print(f"## All Deals ({len(all_deals)})")
print()
print("| Deal | Principal | Partner | Type | Date |")
print("|------|-----------|---------|------|------|")
for d in all_deals[:30]:
    title = d.get("Title", "?")[:45]
    princ = d.get("CompanyPrincipal", "?")[:20]
    part = d.get("CompanyPartner", "?")[:20]
    dtype = d.get("Type", "?")[:25]
    date = d.get("StartDate", "?")
    if isinstance(date, str):
        date = date[:10]
    print(f"| {title} | {princ} | {part} | {dtype} | {date} |")
print()
