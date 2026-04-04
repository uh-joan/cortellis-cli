#!/usr/bin/env python3
"""Generate a complete indication analysis report.

Usage: python3 indication_report_generator.py /tmp/indication_deep_dive "indication name"
"""
import json, re, sys, os
from collections import Counter

data_dir = sys.argv[1]
indication = sys.argv[2] if len(sys.argv) > 2 else "Unknown"


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


def extract_drugs(data):
    if not data:
        return [], "0"
    r = data.get("drugResultsOutput", {})
    total = r.get("@totalResults", "0")
    drugs = r.get("SearchResults", {}).get("Drug", [])
    if isinstance(drugs, dict):
        drugs = [drugs]
    return drugs, total


def bar_chart(data, title, max_width=35, char="█"):
    if not data:
        return ""
    max_val = max(v for _, v in data)
    if max_val == 0:
        return ""
    lines = [title, "─" * 55]
    for label, value in data:
        bar_len = int(value / max_val * max_width) if max_val > 0 else 0
        lines.append(f"  {label:20s} {char * max(bar_len, 1)} {value}")
    return "\n".join(lines)


def clean_html(text):
    return re.sub(r"<[^>]+>", " ", str(text)).strip() if text else ""


# Load all data
launched, l_total = extract_drugs(load_json("drugs_launched.json"))
p3, p3_total = extract_drugs(load_json("drugs_p3.json"))
p2, p2_total = extract_drugs(load_json("drugs_p2.json"))

trials_data = load_json("trials.json")
deals_data = load_json("deals.json")
reg_data = load_json("regulatory.json")
lit_data = load_json("literature.json")

print(f"# Indication Deep Dive: {indication}")
print()
print(f"**Launched:** {l_total} | **Phase 3:** {p3_total} | **Phase 2:** {p2_total}")
print()

# Drug pipeline chart
chart_data = [("Launched", int(l_total)), ("Phase 3", int(p3_total)), ("Phase 2", int(p2_total))]
chart = bar_chart(chart_data, "Drug Pipeline by Phase")
if chart:
    print("## Drug Pipeline")
    print()
    print("```")
    print(chart)
    print("```")
    print()

# Launched drugs
if launched:
    print(f"### Launched Drugs ({l_total})")
    print()
    print("| Drug | Company | Mechanism |")
    print("|------|---------|-----------|")
    for d in launched[:20]:
        name = d.get("@name", "?")[:35]
        co = d.get("CompanyOriginator", "?")[:25]
        actions = d.get("ActionsPrimary", {}).get("Action", "?")
        if isinstance(actions, list):
            actions = "; ".join(str(a) for a in actions[:2])
        print(f"| {name} | {co} | {actions} |")
    print()

# Phase 3
if p3:
    print(f"### Phase 3 ({p3_total})")
    print()
    print("| Drug | Company | Mechanism |")
    print("|------|---------|-----------|")
    for d in p3[:15]:
        name = d.get("@name", "?")[:35]
        co = d.get("CompanyOriginator", "?")[:25]
        actions = d.get("ActionsPrimary", {}).get("Action", "?")
        if isinstance(actions, list):
            actions = "; ".join(str(a) for a in actions[:2])
        print(f"| {name} | {co} | {actions} |")
    print()

# Phase 2
if p2:
    print(f"### Phase 2 ({p2_total})")
    print()
    print("| Drug | Company | Mechanism |")
    print("|------|---------|-----------|")
    for d in p2[:15]:
        name = d.get("@name", "?")[:35]
        co = d.get("CompanyOriginator", "?")[:25]
        actions = d.get("ActionsPrimary", {}).get("Action", "?")
        if isinstance(actions, list):
            actions = "; ".join(str(a) for a in actions[:2])
        print(f"| {name} | {co} | {actions} |")
    print()

# Trials
if trials_data:
    tr = trials_data.get("trialResultsOutput", {})
    total = tr.get("@totalResults", "0")
    trials = tr.get("SearchResults", {}).get("Trial", [])
    if isinstance(trials, dict):
        trials = [trials]
    if trials:
        print(f"## Clinical Trials ({total} total)")
        print()
        print("| Trial | Phase | Status | Enrollment | Start |")
        print("|-------|-------|--------|------------|-------|")
        for t in trials[:20]:
            title = (t.get("TitleDisplay", t.get("Title", "?")))[:50]
            phase = t.get("Phase", "?")
            status = t.get("RecruitmentStatus", "?")
            enroll = t.get("PatientCountEnrollment", "?")
            start = t.get("StartDate", "?")
            if isinstance(start, str):
                start = start[:10]
            print(f"| {title} | {phase} | {status} | {enroll} | {start} |")
        print()

# Deals
if deals_data:
    dr = deals_data.get("dealResultsOutput", {})
    total = dr.get("@totalResults", "0")
    deals = dr.get("SearchResults", {}).get("Deal", [])
    if isinstance(deals, dict):
        deals = [deals]
    if deals:
        print(f"## Recent Deals ({total} total)")
        print()
        print("| Deal | Principal | Partner | Type | Date |")
        print("|------|-----------|---------|------|------|")
        for d in deals[:15]:
            title = d.get("Title", "?")[:45]
            princ = d.get("CompanyPrincipal", "?")[:20]
            part = d.get("CompanyPartner", "?")[:20]
            dtype = d.get("Type", "?")[:25]
            date = d.get("StartDate", "?")
            if isinstance(date, str):
                date = date[:10]
            print(f"| {title} | {princ} | {part} | {dtype} | {date} |")
        print()

# Regulatory
if reg_data:
    rr = reg_data.get("regulatoryResultsOutput", {})
    total = rr.get("@totalResults", "0")
    regs = rr.get("SearchResults", {}).get("Regulatory", [])
    if isinstance(regs, dict):
        regs = [regs]
    if regs:
        print(f"## Regulatory Documents ({total} total)")
        print()
        print("| Document | Region | Type | Date |")
        print("|----------|--------|------|------|")
        for r in regs[:10]:
            title = r.get("Title", "?")[:50]
            region = r.get("Region", "?")
            dtype = r.get("DocTypes", {}).get("DocType", "?")
            if isinstance(dtype, list):
                dtype = dtype[0]
            if isinstance(dtype, dict):
                dtype = dtype.get("$", str(dtype))
            date = r.get("DateDisplay", "?")
            print(f"| {title} | {region} | {dtype} | {date} |")
        print()

# Literature
if lit_data:
    lr = lit_data.get("literatureResultsOutput", {})
    total = lr.get("@totalResults", "0")
    pubs = lr.get("SearchResults", {}).get("Literature", [])
    if isinstance(pubs, dict):
        pubs = [pubs]
    if pubs:
        print(f"## Literature ({total} total)")
        print()
        print("| Title | Authors | Year |")
        print("|-------|---------|------|")
        for p in pubs[:10]:
            title = clean_html(p.get("Title", "?"))[:50]
            authors = p.get("Authors", {})
            if isinstance(authors, dict):
                al = authors.get("Author", [])
                if isinstance(al, list):
                    authors = "; ".join(str(a) for a in al[:3])
                else:
                    authors = str(al)
            authors = str(authors)[:30]
            year = p.get("Year", "?")
            print(f"| {title} | {authors} | {year} |")
        print()
