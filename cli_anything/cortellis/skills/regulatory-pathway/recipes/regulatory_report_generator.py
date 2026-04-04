#!/usr/bin/env python3
"""Generate a regulatory pathway report from collected JSON data.

Usage: python3 regulatory_report_generator.py /tmp/regulatory_pathway "drug name"
"""
import json, re, sys, os
from collections import Counter

data_dir = sys.argv[1]
drug_name = sys.argv[2] if len(sys.argv) > 2 else "Unknown"


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


def clean_html(text):
    if not text:
        return ""
    return re.sub(r"<[^>]+>", " ", str(text)).strip()


def extract_list(obj, *keys):
    cur = obj
    for k in keys:
        if not isinstance(cur, dict):
            return []
        cur = cur.get(k, {})
    if isinstance(cur, dict):
        return [cur]
    if isinstance(cur, list):
        return cur
    return []


# Load search results
search = load_json("reg_search.json")
if not search:
    print("Error: reg_search.json not found", file=sys.stderr)
    sys.exit(1)

results = search.get("regulatoryResultsOutput", {})
total = results.get("@totalResults", "0")
docs = extract_list(results, "SearchResults", "Regulatory")

print(f"# Regulatory Pathway: {drug_name}")
print()

# Count by region
region_counter = Counter()
for d in docs:
    region = d.get("Region", "Unknown")
    region_counter[region] += 1

regions_str = ", ".join(f"{r} ({c})" for r, c in region_counter.most_common(5))
print(f"**Total Documents:** {total} | **Regions:** {regions_str}")
print()

# Approval Timeline — filter to approval-type documents
approval_types = ["Original Approval", "Supplemental Approval", "Marketing Authorization",
                  "Variation", "Extension", "Renewal"]
approvals = []
for d in docs:
    doc_type = d.get("DocTypes", {}).get("DocType", "")
    if isinstance(doc_type, list):
        doc_type = doc_type[0] if doc_type else ""
    if isinstance(doc_type, dict):
        doc_type = doc_type.get("$", str(doc_type))
    is_approval = any(at.lower() in doc_type.lower() for at in approval_types)
    if is_approval:
        approvals.append(d)

if approvals:
    print("## Approval Timeline")
    print()
    print("| Date | Document | Region | Type | Status |")
    print("|------|----------|--------|------|--------|")
    for d in approvals:
        date = d.get("DateDisplay", "?")
        title = d.get("Title", "?")[:60]
        region = d.get("Region", "?")
        doc_type = d.get("DocTypes", {}).get("DocType", "?")
        if isinstance(doc_type, list):
            doc_type = doc_type[0]
        if isinstance(doc_type, dict):
            doc_type = doc_type.get("$", str(doc_type))
        status = d.get("Status", "?")
        print(f"| {date} | {title} | {region} | {doc_type} | {status} |")
    print()

# Key Approvals with abstracts
key_docs = approvals[:3] if approvals else docs[:3]
if key_docs:
    print("## Key Documents")
    print()
    for d in key_docs:
        title = d.get("Title", "Unknown")
        region = d.get("Region", "?")
        date = d.get("DateDisplay", "?")
        doc_type = d.get("DocTypes", {}).get("DocType", "?")
        if isinstance(doc_type, list):
            doc_type = "; ".join(doc_type[:2])
        if isinstance(doc_type, dict):
            doc_type = doc_type.get("$", str(doc_type))
        source = d.get("Source", "?")
        abstract = clean_html(d.get("Abstract", ""))
        abstract = " ".join(abstract.split())[:400]

        print(f"### {title[:80]}")
        print(f"**Region:** {region} | **Date:** {date} | **Type:** {doc_type}")
        print(f"**Source:** {source}")
        if abstract:
            print()
            print(abstract)
        print()

# Documents by Region
if region_counter:
    print("## Documents by Region")
    print()
    print("| Region | Count |")
    print("|--------|-------|")
    for region, count in region_counter.most_common():
        print(f"| {region} | {count} |")
    print()

# Citation graph
for i in range(1, 6):
    cited = load_json(f"cited_{i}.json")
    cited_by = load_json(f"cited_by_{i}.json")
    if cited or cited_by:
        print(f"## Citation Graph (Document #{i})")
        print()
        if cited:
            cited_docs = extract_list(cited, "CitedDocumentOutput", "Documents")
            if cited_docs:
                print(f"### Documents Cited ({len(cited_docs)})")
                print()
                print("| Document | Date | Region |")
                print("|----------|------|--------|")
                for cd in cited_docs[:10]:
                    ct = cd.get("Title", "?")[:55]
                    cdate = cd.get("Date", "?")
                    cregion = cd.get("Region", "?")
                    print(f"| {ct} | {cdate} | {cregion} |")
                print()
        if cited_by:
            cb_docs = extract_list(cited_by, "CitedByOutput", "Documents")
            if cb_docs:
                print(f"### Cited By ({len(cb_docs)})")
                print()
                print("| Document | Date | Region |")
                print("|----------|------|--------|")
                for cb in cb_docs[:10]:
                    ct = cb.get("Title", "?")[:55]
                    cdate = cb.get("Date", "?")
                    cregion = cb.get("Region", "?")
                    print(f"| {ct} | {cdate} | {cregion} |")
                print()
        break  # Only show first citation graph

# Document type breakdown
type_counter = Counter()
for d in docs:
    dt = d.get("DocTypes", {}).get("DocType", "Unknown")
    if isinstance(dt, list):
        for t in dt:
            type_counter[t] += 1
    elif isinstance(dt, dict):
        type_counter[dt.get("$", str(dt))] += 1
    else:
        type_counter[str(dt)] += 1

if type_counter:
    print("## Document Types")
    print()
    print("| Type | Count |")
    print("|------|-------|")
    for dtype, count in type_counter.most_common():
        print(f"| {dtype} | {count} |")
    print()

# Full document list
if docs:
    print(f"## All Regulatory Documents ({total} total, showing {len(docs)})")
    print()
    print("| # | Title | Region | Type | Date |")
    print("|---|-------|--------|------|------|")
    for i, d in enumerate(docs, 1):
        title = d.get("Title", "?")[:55]
        region = d.get("Region", "?")
        doc_type = d.get("DocTypes", {}).get("DocType", "?")
        if isinstance(doc_type, list):
            doc_type = doc_type[0]
        if isinstance(doc_type, dict):
            doc_type = doc_type.get("$", str(doc_type))
        date = d.get("DateDisplay", "?")
        print(f"| {i} | {title} | {region} | {doc_type} | {date} |")
    print()
