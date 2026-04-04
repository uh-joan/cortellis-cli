#!/usr/bin/env python3
"""Generate a deal deep-dive report from collected JSON data.

Usage: python3 deal_report_generator.py /tmp/deal_deep_dive

Reads JSON files from the directory and outputs a formatted markdown report.
"""
import html, json, re, sys, os

data_dir = sys.argv[1]

# ── Data loading with error tracking ─────────────────────────────────────────

_data_status = {}


def load_json(filename):
    path = os.path.join(data_dir, filename)
    if not os.path.exists(path):
        _data_status[filename] = "missing"
        return None
    try:
        with open(path) as f:
            d = json.load(f)
        if d.get("error"):
            _data_status[filename] = f"error: {d['error']}"
            return None
        if len(str(d)) < 50:
            _data_status[filename] = "empty"
            return None
        _data_status[filename] = "ok"
        return d
    except json.JSONDecodeError as e:
        _data_status[filename] = f"error: invalid JSON ({e})"
        return None
    except Exception as e:
        _data_status[filename] = f"error: {e}"
        return None


def extract_text(obj, key, default=""):
    if not isinstance(obj, dict):
        return default
    val = obj.get(key, default)
    if isinstance(val, dict):
        return val.get("$", val.get("@name", str(val)))
    return str(val) if val else default


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
    if isinstance(cur, str) and cur:
        return [cur]
    return []


def items_to_strings(items):
    result = []
    for i in items:
        if isinstance(i, dict):
            result.append(i.get("$", i.get("@name", str(i))))
        else:
            result.append(str(i))
    return result


# ── Load data ────────────────────────────────────────────────────────────────

deal = load_json("deal_expanded.json")
deal_std = load_json("deal_standard.json")
sources = load_json("deal_sources.json")
comparables = load_json("comparables.json")
drug_context = load_json("drug_context.json")

if not deal:
    print("Error: deal_expanded.json not found or empty", file=sys.stderr)
    sys.exit(1)

rec = deal.get("dealRecordOutput", deal)

# Merge: use standard record for fields missing in expanded
std_rec = {}
if deal_std:
    std_rec = deal_std.get("dealRecordOutput", deal_std)

# ── Header ───────────────────────────────────────────────────────────────────

title = rec.get("Title", std_rec.get("Title", "Unknown Deal"))
deal_id = rec.get("@id", std_rec.get("@id", "?"))
status = rec.get("Status", std_rec.get("Status", "?"))
start_date = rec.get("StartDate", std_rec.get("DateStart", "?"))
if isinstance(start_date, str) and start_date != "?":
    start_date = start_date[:10]
elif not start_date:
    start_date = std_rec.get("DateStart", "?")
    if isinstance(start_date, str):
        start_date = start_date[:10]
merger = rec.get("DealMergerAndAcquisition", rec.get("MergerAndAcquisition", "No"))

print(f"# Deal Deep Dive: {html.unescape(str(title))}")
print()
print(f"**ID:** {deal_id} | **Status:** {status} | **Date:** {start_date} | **M&A:** {merger}")
print()

# ── Parties ──────────────────────────────────────────────────────────────────

principal = rec.get("CompanyPrincipal", {})
partner = rec.get("CompanyPartner", {})
print("## Parties")
print()
print("| Role | Company | Type | ID |")
print("|------|---------|------|-----|")
if isinstance(principal, dict):
    print(f"| Principal | {principal.get('$', '?')} | {principal.get('@type', '?')} | {principal.get('@id', '?')} |")
else:
    print(f"| Principal | {principal} | - | - |")
if isinstance(partner, dict):
    print(f"| Partner | {partner.get('$', '?')} | {partner.get('@type', '?')} | {partner.get('@id', '?')} |")
else:
    print(f"| Partner | {partner} | - | - |")
print()

# ── Deal Structure ───────────────────────────────────────────────────────────

category = rec.get("Category", {})
agreement = category.get("AgreementType", rec.get("Type", "?"))
asset_types = items_to_strings(extract_list(category, "AssetTypes", "AssetType"))
txn_types = items_to_strings(extract_list(category, "TransactionTypes", "TransactionType"))
phase_start = rec.get("DealPhaseHighestStart", "?")
phase_now = rec.get("DealPhaseHighestNow", "?")
if phase_start == "?" and std_rec:
    std_drugs = extract_list(std_rec, "Drugs", "Drug")
    if std_drugs:
        d0 = std_drugs[0] if isinstance(std_drugs[0], dict) else {}
        phase_start = extract_text(d0, "PhaseHighestStart", "?")
        phase_now = extract_text(d0, "PhaseHighestNow", "?")

print("## Deal Structure")
print()
print("| Field | Value |")
print("|-------|-------|")
print(f"| Agreement Type | {agreement} |")
if asset_types:
    print(f"| Asset Types | {'; '.join(asset_types)} |")
if txn_types:
    print(f"| Transaction Types | {'; '.join(txn_types)} |")
print(f"| Phase at Signing | {phase_start} |")
print(f"| Current Phase | {phase_now} |")
print()

# ── Territories ──────────────────────────────────────────────────────────────

terr_incl = items_to_strings(extract_list(rec, "TerritoriesIncluded", "Territory"))
terr_excl_raw = rec.get("TerritoriesExcluded")
if terr_excl_raw and isinstance(terr_excl_raw, dict) and terr_excl_raw.get("Territory"):
    terr_excl = items_to_strings(extract_list(rec, "TerritoriesExcluded", "Territory"))
else:
    terr_excl = []

terr_incl = [t for t in terr_incl if t and t != "{}"]
terr_excl = [t for t in terr_excl if t and t != "{}"]
if terr_incl:
    print("## Territories")
    print()
    print(f"**Included:** {', '.join(terr_incl)}")
    if terr_excl:
        print(f"**Excluded:** {', '.join(terr_excl)}")
    print()

# ── Financial Terms ──────────────────────────────────────────────────────────

financials = []


def add_financial(label, val_key, status_key):
    val = rec.get(val_key, "")
    stat = rec.get(status_key, "")
    if val or (stat and stat not in ("Payment Unspecified", "Unknown", "")):
        financials.append((label, str(val) if val else "-", stat if stat else "-"))


add_financial("Total Projected (Signing)", "DealTotalProjectedSigningAmount", "DealTotalProjectedSigningDisclosureStatus")
add_financial("Total Projected (Current)", "DealTotalProjectedCurrentAmount", "DealTotalProjectedCurrentDisclosureStatus")
add_financial("Total Paid", "DealTotalPaidAmount", "DealTotalPaidDisclosureStatus")
add_financial("Upfront Payment", "DealUpfrontDisplay", "DealUpfrontDisclosureStatus")
add_financial("Milestones", "DealTotalMilestoneDisplay", "DealTotalMilestoneDisclosureStatus")
add_financial("Royalties", "DealRoyaltyDisplay", "DealRoyaltyDisclosureStatus")

fin_block = rec.get("Financials", {})
if isinstance(fin_block, dict):
    for key in fin_block:
        if key not in ("@id",) and fin_block[key]:
            val = fin_block[key]
            if isinstance(val, dict):
                val = val.get("$", str(val))
            financials.append((key, str(val), "-"))

if financials:
    print("## Financial Terms")
    print()
    print("| Component | Value | Disclosure |")
    print("|-----------|-------|------------|")
    for label, val, stat in financials:
        print(f"| {label} | {val} | {stat} |")
    print()

# ── Indications & Mechanisms ─────────────────────────────────────────────────

indications = items_to_strings(extract_list(rec, "Indications", "Indication"))
actions_primary = items_to_strings(extract_list(rec, "ActionsPrimary", "Action"))
actions_secondary = items_to_strings(extract_list(rec, "ActionsSecondary", "Action"))
technologies = items_to_strings(extract_list(rec, "Technologies", "Technology"))

if indications or actions_primary:
    print("## Indications & Mechanisms")
    print()
    if indications:
        print("**Indications:**")
        for ind in indications:
            print(f"- {ind}")
        print()
    if actions_primary:
        print(f"**Primary Mechanism:** {'; '.join(actions_primary)}")
    if actions_secondary:
        print(f"**Secondary Mechanisms:** {'; '.join(actions_secondary)}")
    if technologies:
        print(f"**Technologies:** {'; '.join(technologies)}")
    print()

# ── Drugs Involved ───────────────────────────────────────────────────────────

drugs = extract_list(rec, "DealDrugs", "Drug")
drug_strings = items_to_strings(drugs)
drug_strings = [d for d in drug_strings if d and d != "{}"]
if not drug_strings and std_rec:
    std_drugs = extract_list(std_rec, "Drugs", "Drug")
    for sd in std_drugs:
        if isinstance(sd, dict):
            dname = sd.get("DrugNameDisplay", sd.get("@name", ""))
            phase_s = extract_text(sd, "PhaseHighestStart", "")
            phase_n = extract_text(sd, "PhaseHighestNow", "")
            label = dname
            if phase_n:
                label += f" (Phase: {phase_s} -> {phase_n})"
            if label:
                drug_strings.append(label)
        else:
            drug_strings.append(str(sd))
if drug_strings:
    print(f"## Drugs Involved ({len(drug_strings)})")
    print()
    for d in drug_strings:
        print(f"- {d}")
    print()

# ── Deal Summary (full, no truncation) ───────────────────────────────────────

if std_rec:
    summary = std_rec.get("Summary", "")
    if summary and len(str(summary)) > 50:
        clean = re.sub(r"<[^>]+>", " ", str(summary))
        clean = html.unescape(" ".join(clean.split()))
        if clean:
            print("## Deal Summary")
            print()
            print(clean)
            print()

# ── Deal Timeline (ALL events, no truncation) ────────────────────────────────

events = extract_list(rec, "Events", "Event")
events = [e for e in events if isinstance(e, dict) and e.get("Date")]
if not events and std_rec:
    events = extract_list(std_rec, "TimeLine", "Event")
    events = [e for e in events if isinstance(e, dict) and e.get("Date")]
if events:
    print(f"## Deal Timeline ({len(events)} events)")
    print()
    print("| Date | Event |")
    print("|------|-------|")
    for e in events:
        edate = e.get("Date", e.get("@date", "?"))
        if isinstance(edate, str):
            edate = edate[:10]
        edesc = e.get("Description", "")
        if not edesc:
            stage = e.get("Stage", {})
            if isinstance(stage, dict):
                edesc = stage.get("$", "")
            if not edesc:
                edesc = e.get("StageNotes", e.get("Summary", ""))
        if isinstance(edesc, dict):
            edesc = edesc.get("$", str(edesc))
        edesc = html.unescape(re.sub(r"<[^>]+>", "", str(edesc)).strip())[:100]
        if not edesc:
            edesc = "Event recorded"
        print(f"| {edate} | {edesc} |")
    print()

# ── Comparable Deals (ALL, no truncation) ────────────────────────────────────

if comparables:
    # Handle both expanded and standard result keys
    comp_results = comparables.get("dealExpandedResultsOutput",
                   comparables.get("dealResultsOutput", {}))
    total = comp_results.get("@totalResults", "0")
    sr = comp_results.get("SearchResults", {})
    comp_deals = sr.get("Deal", []) if isinstance(sr, dict) else []
    if isinstance(comp_deals, dict):
        comp_deals = [comp_deals]
    # Filter out the current deal
    comp_deals = [d for d in comp_deals if d.get("@id", "") != str(deal_id)]
    if comp_deals:
        shown = len(comp_deals)
        total_int = int(total) if str(total).isdigit() else shown
        if total_int > shown:
            print(f"## Comparable Deals (showing {shown} of {total_int} total, sorted by most recent)")
        else:
            print(f"## Comparable Deals ({total_int} total)")
        print()
        print("| Deal | Principal | Partner | Type | Phase | Date |")
        print("|------|-----------|---------|------|-------|------|")
        for d in comp_deals:
            dtitle = d.get("Title", "?")[:50]
            dprinc = extract_text(d, "CompanyPrincipal", "?")[:25]
            dpart = extract_text(d, "CompanyPartner", "?")[:25]
            dtype = d.get("Type", "?")[:30]
            dphase = d.get("DealPhaseHighestNow", "?")
            ddate = d.get("StartDate", "?")
            if isinstance(ddate, str):
                ddate = ddate[:10]
            print(f"| {dtitle} | {dprinc} | {dpart} | {dtype} | {dphase} | {ddate} |")
        print()

# ── Sources (ALL, no truncation) ─────────────────────────────────────────────

if sources:
    src_list = extract_list(sources, "dealSourcesOutput", "Sources", "Source")
    if src_list:
        print(f"## Sources ({len(src_list)})")
        print()
        print("| Source | Type | ID |")
        print("|--------|------|-----|")
        for s in src_list:
            stitle = s.get("Title", s.get("$", "?"))
            if isinstance(stitle, dict):
                stitle = stitle.get("$", str(stitle))
            stype = s.get("@type", "?")
            sid = s.get("@id", "?")
            print(f"| {html.unescape(str(stitle)[:70])} | {stype} | {sid} |")
        print()

# ── Data Completeness ────────────────────────────────────────────────────────

print("## Data Completeness")
print()
print("| Source | Status |")
print("|--------|--------|")

source_labels = {
    "deal_expanded.json": "Expanded Deal Record",
    "deal_standard.json": "Standard Deal Record",
    "deal_sources.json": "Deal Sources",
    "comparables.json": "Comparable Deals",
    "drug_context.json": "Drug Context",
}

ok_count = 0
total_count = 0
for filename, label in source_labels.items():
    status = _data_status.get(filename, "not fetched")
    total_count += 1
    if status == "ok":
        ok_count += 1
        icon = "Available"
    elif status == "missing":
        icon = "Not fetched"
    elif status == "empty":
        icon = "Empty (no data)"
    else:
        icon = status
    print(f"| {label} | {icon} |")

pct = int(ok_count / total_count * 100) if total_count else 0
print(f"| **Overall** | **{ok_count}/{total_count} sources ({pct}%)** |")
print()

if pct < 100:
    missing = [source_labels.get(f, f) for f, s in _data_status.items()
               if s != "ok" and f in source_labels]
    if missing:
        print(f"*Missing/failed sources: {", ".join(missing)}. Results may be incomplete.*")
        print()
