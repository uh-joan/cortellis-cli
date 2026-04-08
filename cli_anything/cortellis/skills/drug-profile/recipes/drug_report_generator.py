#!/usr/bin/env python3
"""Generate a formatted drug profile report from collected JSON data.

Usage: python3 drug_report_generator.py raw/drugs/<slug>/

Reads JSON files from the directory:
  record.json, swot.json, financials.json, history.json, deals.json, trials.json, regulatory.json

Outputs formatted markdown report with ASCII timeline.
"""
import csv, json, sys, os
from collections import Counter

if len(sys.argv) < 2:
    print(f"Usage: {sys.argv[0]} <profile_dir>", file=sys.stderr)
    sys.exit(1)
profile_dir = sys.argv[1]
if not os.path.isdir(profile_dir):
    print(f"Error: {profile_dir} is not a directory", file=sys.stderr)
    sys.exit(1)


def load_json(filename):
    path = os.path.join(profile_dir, filename)
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            d = json.load(f)
        # Check if effectively empty
        if len(str(d)) < 50:
            return None
        return d
    except (json.JSONDecodeError, KeyError, TypeError, ValueError, OSError):
        return None


def ascii_timeline(changes):
    """Generate ASCII timeline from development history."""
    if not changes:
        return ""
    # Extract key milestones with meaningful labels
    milestones = []
    for c in changes:
        date = c.get("Date", "")[:10]
        year = date[:4]
        reason = c.get("Reason", {})
        if isinstance(reason, dict):
            reason = reason.get("$", "")

        # Only include highest status changes (most meaningful)
        if reason == "Highest status change":
            fields = c.get("FieldsChanged", {}).get("Field", {})
            if isinstance(fields, dict):
                new_val = fields.get("@newValue", "")
                old_val = fields.get("@oldValue", "")
                label = f"{old_val} → {new_val}" if old_val else new_val
                milestones.append((year, date, label))
        elif reason == "Drug added":
            milestones.append((year, date, "Drug added"))

    if not milestones:
        return ""

    # Deduplicate by label (keep first occurrence)
    seen_labels = set()
    unique = []
    for year, date, label in milestones:
        if label not in seen_labels:
            seen_labels.add(label)
            unique.append((year, date, label))

    if len(unique) < 2:
        return ""

    # Build ASCII timeline
    lines = ["```"]
    line1 = ""
    for i, (year, date, label) in enumerate(unique):
        line1 += f" {year} ──"
    lines.append(line1.rstrip("─"))

    # Labels
    for year, date, label in unique:
        lines.append(f"  {date}: {label}")
    lines.append("```")
    return "\n".join(lines)


# Load all data
record = load_json("record.json")
swot = load_json("swot.json")
financials = load_json("financials.json")
history = load_json("history.json")
deals = load_json("deals.json")
trials = load_json("trials.json")
regulatory = load_json("regulatory.json")
competitors = load_json("competitors.json")

if not record:
    print("Error: record.json not found or empty", file=sys.stderr)
    sys.exit(1)

# Extract record fields
rec = record.get("drugRecordOutput", record)
drug_name = rec.get("DrugName", rec.get("@name", "Unknown"))
drug_id = rec.get("@id", "?")
phase = rec.get("PhaseHighest", {})
if isinstance(phase, dict):
    phase = phase.get("$", "?")
originator = rec.get("CompanyOriginator", {})
if isinstance(originator, dict):
    originator = originator.get("$", originator.get("@name", "?"))

# Indications
indications = rec.get("IndicationsPrimary", {}).get("Indication", [])
if isinstance(indications, dict):
    indications = [indications.get("$", str(indications))]
elif isinstance(indications, list):
    indications = [i.get("$", str(i)) if isinstance(i, dict) else str(i) for i in indications]

# Mechanism
actions = rec.get("ActionsPrimary", {}).get("Action", [])
if isinstance(actions, dict):
    actions = [actions.get("$", str(actions))]
elif isinstance(actions, list):
    actions = [a.get("$", str(a)) if isinstance(a, dict) else str(a) for a in actions]

# Brand names
brands = rec.get("DrugNamesKey", {}).get("Name", [])
if isinstance(brands, dict):
    brands = [brands]
brand_names = [b.get("$", "") for b in brands if isinstance(b, dict)]

# Technologies
techs = rec.get("Technologies", {}).get("Technology", [])
if isinstance(techs, dict):
    techs = [techs.get("$", str(techs))]
elif isinstance(techs, list):
    techs = [t.get("$", str(t)) if isinstance(t, dict) else str(t) for t in techs]

# Report
print(f"# Drug Profile: {drug_name}")
print()
print(f"**ID:** {drug_id} | **Phase:** {phase} | **Originator:** {originator}")
if brand_names:
    print(f"**Brands:** {', '.join(brand_names)}")
print()

print("## Overview")
print()
print(f"| Field | Value |")
print(f"|-------|-------|")
print(f"| Indications | {'; '.join(indications[:5])} |")
print(f"| Mechanism | {'; '.join(actions[:3])} |")
print(f"| Technology | {'; '.join(techs[:3])} |")
if rec.get("TherapyAreas"):
    areas = rec["TherapyAreas"].get("TherapyArea", [])
    if isinstance(areas, list):
        print(f"| Therapy Areas | {'; '.join(areas[:5])} |")
    else:
        print(f"| Therapy Areas | {areas} |")
print()

# Development Timeline
if history:
    changes = history.get("ChangeHistory", {}).get("Change", [])
    if isinstance(changes, dict):
        changes = [changes]
    timeline = ascii_timeline(changes)
    if timeline:
        print("## Development Timeline")
        print()
        print(timeline)
        print()
    print(f"Total history entries: {len(changes)}")
    print()

# SWOT
if swot:
    swot_data = swot.get("drugSwotsOutput", {})
    swot_text = str(swot_data)
    if len(swot_text) > 100:
        print("## SWOT Analysis")
        print()
        import re
        for section in ["Strengths", "Weaknesses", "Opportunities", "Threats"]:
            # Try to extract section content from XML-like text
            pattern = rf"<{section}>(.*?)</{section}>"
            match = re.search(pattern, swot_text, re.DOTALL | re.IGNORECASE)
            if match:
                content = re.sub(r"<[^>]+>", "", match.group(1)).strip()
                # Clean up and truncate
                content = " ".join(content.split())[:300]
                if content:
                    print(f"### {section}")
                    print(f"{content}")
                    print()
            elif section.lower() in swot_text.lower():
                print(f"### {section}")
                print("(Available in full record)")
                print()

# Financials
if financials:
    fin = financials.get("drugFinancialsOutput", {})
    commentary = fin.get("DrugSalesAndForecastCommentary", "")
    if commentary and len(str(commentary)) > 50:
        print("## Financial Data")
        print()
        # Clean HTML tags from commentary
        import re
        clean = re.sub(r"<[^>]+>", " ", str(commentary))
        clean = " ".join(clean.split())[:500]
        print(clean)
        print()

# Deals
if deals:
    deal_data = deals.get("dealResultsOutput", {})
    total_deals = deal_data.get("@totalResults", "0")
    sr = deal_data.get("SearchResults", {})
    deal_list = sr.get("Deal", []) if isinstance(sr, dict) else []
    if isinstance(deal_list, dict):
        deal_list = [deal_list]
    if deal_list:
        print(f"## Deals ({total_deals} total)")
        print()
        print("| Deal | Partner | Type | Date |")
        print("|------|---------|------|------|")
        for d in deal_list[:10]:
            title = d.get("Title", "?")[:50]
            partner = d.get("CompanyPartner", "?")[:25]
            dtype = d.get("Type", "?")[:25]
            date = d.get("StartDate", "?")[:10]
            print(f"| {title} | {partner} | {dtype} | {date} |")
        print()

# Trials
if trials:
    trial_data = trials.get("trialResultsOutput", {})
    total_trials = trial_data.get("@totalResults", "0")
    sr = trial_data.get("SearchResults", {})
    trial_list = sr.get("Trial", []) if isinstance(sr, dict) else []
    if isinstance(trial_list, dict):
        trial_list = [trial_list]
    if trial_list:
        print(f"## Clinical Trials ({total_trials} total)")
        print()
        print("| Trial | Phase | Status | Enrollment |")
        print("|-------|-------|--------|------------|")
        for t in trial_list[:10]:
            title = t.get("TitleDisplay", t.get("Title", "?"))[:50]
            tphase = t.get("Phase", "?")
            status = t.get("RecruitmentStatus", "?")
            enroll = t.get("PatientCountEnrollment", "?")
            print(f"| {title} | {tphase} | {status} | {enroll} |")
        print()

# Regulatory
if regulatory:
    reg_data = regulatory.get("regulatoryResultsOutput", {})
    total_reg = reg_data.get("@totalResults", "0")
    if int(total_reg) > 0:
        sr = reg_data.get("SearchResults", {})
        reg_list = sr.get("Regulatory", []) if isinstance(sr, dict) else []
        if isinstance(reg_list, dict):
            reg_list = [reg_list]
        print(f"## Regulatory ({total_reg} documents)")
        print()
        print("| Document | Region | Type | Date |")
        print("|----------|--------|------|------|")
        for r in reg_list[:10]:
            title = r.get("Title", "?")[:50]
            region = r.get("Region", "?")
            dtype = r.get("DocTypes", {}).get("DocType", "?")
            if isinstance(dtype, list):
                dtype = dtype[0] if dtype else "?"
            date = r.get("DateDisplay", "?")
            print(f"| {title} | {region} | {dtype} | {date} |")
        print()

# Competitors
if competitors:
    comp_data = competitors.get("drugResultsOutput", {})
    search_results = comp_data.get("SearchResults", {})
    if not isinstance(search_results, dict):
        search_results = {}
    comp_list = search_results.get("Drug", [])
    if isinstance(comp_list, dict):
        comp_list = [comp_list]
    if comp_list:
        print(f"## Competitive Landscape (same mechanism)")
        print()
        print("| Drug | Company | Phase | Indications |")
        print("|------|---------|-------|-------------|")
        for c in comp_list[:15]:
            cname = c.get("@name", "?")[:40]
            cco = c.get("CompanyOriginator", "?")[:20]
            cphase = c.get("@phaseHighest", "?")
            cindics = c.get("IndicationsPrimary", {}).get("Indication", "")
            if isinstance(cindics, list):
                cindics = "; ".join(cindics[:2])
            print(f"| {cname} | {cco} | {cphase} | {cindics} |")
        print()
