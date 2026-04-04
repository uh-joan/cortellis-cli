#!/usr/bin/env python3
"""Generate a company peer benchmarking report from collected JSON data.

Usage: python3 peers_report_generator.py /tmp/company_peers "Company Name" company_id

Reads JSON files from the directory and outputs a formatted markdown report
with peer comparison tables and ASCII charts.
"""
import json, sys, os
from collections import Counter

data_dir = sys.argv[1]
company_name = sys.argv[2] if len(sys.argv) > 2 else "Unknown"
company_id = sys.argv[3] if len(sys.argv) > 3 else ""


def load_json(filename):
    path = os.path.join(data_dir, filename)
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            d = json.load(f)
        if isinstance(d, dict) and len(str(d)) < 50:
            return None
        return d
    except Exception:
        return None


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
    if isinstance(cur, str):
        return [cur]
    return []


def bar_chart(data, title, max_width=35, char="█"):
    if not data:
        return ""
    max_val = max(v for _, v in data)
    if max_val == 0:
        return ""
    lines = [title, "─" * 55]
    for label, value in data:
        bar_len = int(value / max_val * max_width) if max_val > 0 else 0
        bar = char * max(bar_len, 0)
        lines.append(f"  {label:25s} {bar} {value:.1f}%")
    return "\n".join(lines)


# Load company record
company = load_json("company.json")
if not company:
    print("Error: company.json not found or empty", file=sys.stderr)
    sys.exit(1)

rec = company.get("companyRecordOutput", company)

# Header
name = rec.get("@name", company_name)
cid = rec.get("@id", company_id)
size = rec.get("@companySize", "?")
country = rec.get("HqCountry", "?")
active_drugs = rec.get("Drugs", {}).get("@activeDevelopment", "?")
patents = rec.get("Patents", {}).get("@owner", "?")
deals_count = rec.get("Deals", {}).get("@current", "?")
website = rec.get("WebSite", "")

print(f"# Company Peer Benchmarking: {name}")
print()
print(f"**ID:** {cid} | **Size:** {size} | **Country:** {country}")
print(f"**Active Drugs:** {active_drugs} | **Patents Owned:** {patents} | **Deals:** {deals_count}")
if website:
    print(f"**Website:** {website}")
print()

# Therapeutic focus
indications = extract_list(rec, "Indications", "Indication")
if indications:
    print("## Therapeutic Focus")
    print()
    print("| # | Indication |")
    print("|---|-----------|")
    for i, ind in enumerate(indications[:15], 1):
        if isinstance(ind, dict):
            ind_name = ind.get("$", str(ind))
        else:
            ind_name = str(ind)
        print(f"| {i} | {ind_name} |")
    if len(indications) > 15:
        print(f"| ... | +{len(indications) - 15} more |")
    print()

# Mechanisms
actions = extract_list(rec, "Actions", "Action")
if actions:
    print("## Key Mechanisms")
    print()
    print("| # | Mechanism |")
    print("|---|----------|")
    for i, act in enumerate(actions[:10], 1):
        if isinstance(act, dict):
            act_name = act.get("$", str(act))
        else:
            act_name = str(act)
        print(f"| {i} | {act_name} |")
    print()

# Peer identification from find_peers.py output
peers_data = load_json("peers.json")
top_peers = []
if peers_data and isinstance(peers_data, list):
    top_peers = peers_data[:10]
    print("## Peer Companies (by indication overlap)")
    print()
    print("| Company | Overlap | Drugs in Shared Indications | Phases |")
    print("|---------|---------|---------------------------|--------|")
    for peer in top_peers:
        pname = peer.get("name", "?")[:35]
        overlap = peer.get("indication_overlap", 0)
        max_ov = peer.get("max_overlap", 3)
        drugs = peer.get("launched_drugs_in_shared_indications", 0)
        phases = ", ".join(peer.get("phases", [])) if isinstance(peer.get("phases"), list) else "?"
        print(f"| {pname} | {overlap}/{max_ov} | {drugs} | {phases} |")
    print()

# Pipeline Success Benchmarking
pipeline_success = load_json("pipeline_success.json")
if pipeline_success:
    rows = extract_list(pipeline_success, "Rowset", "Row")
    if rows:
        print("## Pipeline Success Rate")
        print()
        print("| Company | Total Drugs | Successful | Success Rate |")
        print("|---------|-------------|------------|--------------|")
        chart_data = []
        for row in rows:
            co = row.get("Company", {})
            co_name = co.get("$", "?") if isinstance(co, dict) else str(co)
            total = row.get("CompanyDrugsAll", 0)
            success = row.get("CompanyDrugsSuccess", 0)
            ratio = row.get("CompanySuccessRatio", 0)
            print(f"| {co_name[:35]} | {total} | {success} | {ratio}% |")
            chart_data.append((co_name[:25], float(ratio) if ratio else 0))
        print()

        # ASCII chart
        if chart_data:
            chart = bar_chart(chart_data, "Pipeline Success Rate (%)")
            if chart:
                print("```")
                print(chart)
                print("```")
                print()

# First-in-Class Portfolio
fic = load_json("first_in_class.json")
if fic:
    rows = extract_list(fic, "Rowset", "Row")
    if rows:
        print(f"## First-in-Class Portfolio ({len(rows)} entries)")
        print()
        print("| Drug | Indication | Target | Phase | Class Rank |")
        print("|------|-----------|--------|-------|------------|")
        for row in rows[:20]:
            drug = row.get("Drug", {})
            drug_name = drug.get("$", "?") if isinstance(drug, dict) else "?"
            ind = row.get("ClassComponentIndication", {})
            ind_name = ind.get("$", "?") if isinstance(ind, dict) else "?"
            target = row.get("ClassComponentTarget", {})
            target_name = target.get("$", "?") if isinstance(target, dict) else "?"
            status = row.get("DrugStatus", {})
            phase = status.get("$", "?") if isinstance(status, dict) else "?"
            rank = row.get("ClassRank", "?")
            print(f"| {drug_name[:30]} | {ind_name[:30]} | {target_name[:25]} | {phase} | {rank} |")
        if len(rows) > 20:
            print(f"| ... | +{len(rows) - 20} more entries | | | |")
        print()

# Recent Deals
deals = load_json("deals.json")
if deals:
    deal_data = deals.get("dealResultsOutput", {})
    total_deals = deal_data.get("@totalResults", "0")
    deal_list = extract_list(deal_data, "SearchResults", "Deal")
    if deal_list:
        print(f"## Recent Deals ({total_deals} total)")
        print()
        print("| Deal | Partner | Type | Date |")
        print("|------|---------|------|------|")
        for d in deal_list[:15]:
            title = d.get("Title", "?")[:50]
            partner = d.get("CompanyPartner", "?")[:25]
            dtype = d.get("Type", "?")[:25]
            date = d.get("StartDate", "?")[:10]
            print(f"| {title} | {partner} | {dtype} | {date} |")
        print()

# Peer analytics records
for fname in sorted(os.listdir(data_dir)):
    if fname.startswith("peer_") and fname.endswith(".json") and not fname.startswith("peers_"):
        peer_data = load_json(fname)
        if not peer_data:
            continue
        prec = peer_data.get("companyRecordOutput", peer_data)
        pname = prec.get("@name", "?")
        p_active = prec.get("Drugs", {}).get("@activeDevelopment", "?")
        p_deals = prec.get("Deals", {}).get("@current", "?")
        p_patents = prec.get("Patents", {}).get("@owner", "?")

# Cross-skill hints
print("## Next Steps")
print()
print(f"*Run `/pipeline \"{company_name}\"` for full pipeline analysis.*")
print(f"*Run `/head-to-head \"{company_name}\" vs \"<PEER>\"` for pairwise comparison.*")
print()

# Summary comparison
print("## Summary")
print()
print(f"| Metric | **{name}** |")
print(f"|--------|--------|")
print(f"| Active Drugs | {active_drugs} |")
print(f"| Patents Owned | {patents} |")
print(f"| Active Deals | {deals_count} |")
print(f"| Top Indications | {len(indications)} |")
print(f"| Top Mechanisms | {len(actions)} |")
if top_peers:
    print(f"| Identified Peers | {len(top_peers)} |")
print()
