#!/usr/bin/env python3
"""Convert deals-intelligence expanded search JSON -> CSV.

Usage: cortellis --json deals-intelligence search --query "semaglutide" --hits 10 | python3 deals_expanded_to_csv.py > deals.csv
   Or: python3 deals_expanded_to_csv.py < search_results.json > deals.csv
"""
import csv, json, sys


def extract_text(obj, key, default=""):
    val = obj.get(key, default)
    if isinstance(val, dict):
        return val.get("$", val.get("@name", str(val)))
    if isinstance(val, list):
        items = []
        for v in val[:5]:
            if isinstance(v, dict):
                items.append(v.get("$", v.get("@name", str(v))))
            else:
                items.append(str(v))
        return "; ".join(items)
    return str(val) if val else default


data = json.load(sys.stdin)
results = data.get("dealExpandedResultsOutput", data.get("dealResultsOutput", {}))
sr = results.get("SearchResults", {})
if isinstance(sr, str):
    sr = {}
deals = sr.get("Deal", [])
if isinstance(deals, dict):
    deals = [deals]

writer = csv.writer(sys.stdout)
writer.writerow([
    "id", "title", "principal", "partner", "type", "transaction_type",
    "status", "territories", "total_projected", "upfront", "milestones",
    "royalties", "phase_start", "phase_now", "indications", "date",
])

for d in deals:
    did = d.get("@id", "")
    title = d.get("Title", "")[:100]
    principal = extract_text(d, "CompanyPrincipal")
    partner = extract_text(d, "CompanyPartner")
    dtype = d.get("Type", d.get("DealAgreementType", ""))
    txn_type = d.get("DealTransactionType", "")
    status = d.get("Status", "")

    # Territories
    territories = d.get("TerritoriesIncluded", {})
    if isinstance(territories, dict):
        terr_list = territories.get("Territory", [])
        if isinstance(terr_list, str):
            terr_list = [terr_list]
        elif isinstance(terr_list, list):
            terr_list = [t.get("$", str(t)) if isinstance(t, dict) else str(t) for t in terr_list]
        territories = "; ".join(terr_list)
    else:
        territories = str(territories) if territories else ""

    # Financials
    total_proj = d.get("DealTotalProjectedSigningAmount", d.get("DealTotalProjectedCurrentAmount", ""))
    upfront = d.get("DealUpfrontDisplay", "")
    milestones = d.get("DealTotalMilestoneDisplay", "")
    royalties = d.get("DealRoyaltyDisplay", "")

    phase_start = d.get("DealPhaseHighestStart", "")
    phase_now = d.get("DealPhaseHighestNow", "")

    ind_obj = d.get("Indications", {})
    if isinstance(ind_obj, dict):
        ind_list = ind_obj.get("Indication", [])
        if isinstance(ind_list, str):
            indications = ind_list
        elif isinstance(ind_list, list):
            indications = "; ".join(
                i.get("$", str(i)) if isinstance(i, dict) else str(i)
                for i in ind_list[:5]
            )
        elif isinstance(ind_list, dict):
            indications = ind_list.get("$", str(ind_list))
        else:
            indications = ""
    else:
        indications = str(ind_obj) if ind_obj else ""

    date = d.get("StartDate", "")
    if isinstance(date, str):
        date = date[:10]

    writer.writerow([
        did, title, principal, partner, dtype, txn_type, status,
        territories, total_proj, upfront, milestones, royalties,
        phase_start, phase_now, indications, date,
    ])
