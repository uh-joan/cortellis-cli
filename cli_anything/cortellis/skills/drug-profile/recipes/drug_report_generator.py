#!/usr/bin/env python3
"""Generate a formatted drug profile report from collected JSON data.

Usage: python3 drug_report_generator.py /tmp/drug_profile/<drug_name>/

Reads JSON files from the directory:
  record.json, swot.json, financials.json, history.json, deals.json,
  trials.json, regulatory.json, competitors.json, competitors_p3.json,
  patent_expiry.json, biosimilars.json
"""
import csv, json, re, subprocess, sys, os
from collections import Counter

profile_dir = sys.argv[1]

# ── Data loading with error tracking ──────────────────────────────────��──────

_data_status = {}  # filename → "ok" | "empty" | "error: <msg>" | "missing"


def load_json(filename):
    path = os.path.join(profile_dir, filename)
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


# ── Timeline ─────────────────────────────────────────────────────────────────

def ascii_timeline(changes):
    """Generate ASCII timeline from development history — includes phase changes,
    approvals, safety events, and label expansions."""
    if not changes:
        return ""
    milestones = []
    for c in changes:
        date = c.get("Date", "")[:10]
        year = date[:4]
        reason = c.get("Reason", {})
        if isinstance(reason, dict):
            reason_text = reason.get("$", "")
        else:
            reason_text = str(reason)

        # Include meaningful milestone types
        if reason_text == "Highest status change":
            fields = c.get("FieldsChanged", {}).get("Field", {})
            if isinstance(fields, dict):
                new_val = fields.get("@newValue", "")
                old_val = fields.get("@oldValue", "")
                label = f"{old_val} \u2192 {new_val}" if old_val else new_val
                milestones.append((year, date, label))
        elif reason_text == "Drug added":
            milestones.append((year, date, "Drug added"))
        elif reason_text in ("New Indication Added", "Regulatory Agency Decision",
                             "License agreement", "Clinical trial results",
                             "Safety update", "Label change"):
            detail = re.sub(r"<[^>]+>", "", c.get("DetailFormatted", ""))[:80]
            label = detail.strip() if detail.strip() else reason_text
            milestones.append((year, date, label))

    if not milestones:
        return ""

    # Deduplicate by label, keep first occurrence
    seen = set()
    unique = []
    for year, date, label in milestones:
        if label not in seen:
            seen.add(label)
            unique.append((year, date, label))

    # Show up to 12 most meaningful milestones
    if len(unique) > 12:
        unique = unique[:12]

    if len(unique) < 2:
        return ""

    lines = ["```"]
    line1 = ""
    for year, date, label in unique:
        line1 += f" {year} \u2500\u2500"
    lines.append(line1.rstrip("\u2500"))
    for year, date, label in unique:
        lines.append(f"  {date}: {label}")
    lines.append("```")
    return "\n".join(lines)


# ── Load all data ────────────────────────────────────────────────────────────

record = load_json("record.json")
swot = load_json("swot.json")
financials = load_json("financials.json")
history = load_json("history.json")
deals = load_json("deals.json")
trials = load_json("trials.json")
regulatory = load_json("regulatory.json")
competitors = load_json("competitors.json")
competitors_p3 = load_json("competitors_p3.json")
patent_expiry = load_json("patent_expiry.json")
biosimilars = load_json("biosimilars.json")

if not record:
    print("Error: record.json not found or empty", file=sys.stderr)
    sys.exit(1)

# ─��� Extract record fields ────────────────────────────────────────────────────

rec = record.get("drugRecordOutput", record)
drug_name = rec.get("DrugName", rec.get("@name", "Unknown"))
drug_id = rec.get("@id", "?")
phase = rec.get("PhaseHighest", {})
if isinstance(phase, dict):
    phase = phase.get("$", "?")
originator = rec.get("CompanyOriginator", {})
if isinstance(originator, dict):
    originator = originator.get("$", originator.get("@name", "?"))

indications = rec.get("IndicationsPrimary", {}).get("Indication", [])
if isinstance(indications, dict):
    indications = [indications.get("$", str(indications))]
elif isinstance(indications, list):
    indications = [i.get("$", str(i)) if isinstance(i, dict) else str(i) for i in indications]

actions = rec.get("ActionsPrimary", {}).get("Action", [])
if isinstance(actions, dict):
    actions = [actions.get("$", str(actions))]
elif isinstance(actions, list):
    actions = [a.get("$", str(a)) if isinstance(a, dict) else str(a) for a in actions]

brands = rec.get("DrugNamesKey", {}).get("Name", [])
if isinstance(brands, dict):
    brands = [brands]
brand_names = [b.get("$", "") for b in brands if isinstance(b, dict)]

techs = rec.get("Technologies", {}).get("Technology", [])
if isinstance(techs, dict):
    techs = [techs.get("$", str(techs))]
elif isinstance(techs, list):
    techs = [t.get("$", str(t)) if isinstance(t, dict) else str(t) for t in techs]

# ── Report Output ────────────────────────────────────────────────────────────

print(f"# Drug Profile: {drug_name}")
print()
print(f"**ID:** {drug_id} | **Phase:** {phase} | **Originator:** {originator}")
if brand_names:
    print(f"**Brands:** {', '.join(brand_names)}")
print()

# Overview
print("## Overview")
print()
print("| Field | Value |")
print("|-------|-------|")
print(f"| Indications ({len(indications)}) | {'; '.join(indications)} |")
print(f"| Mechanism | {'; '.join(actions)} |")
print(f"| Technology | {'; '.join(techs)} |")
if rec.get("TherapyAreas"):
    areas = rec["TherapyAreas"].get("TherapyArea", [])
    if isinstance(areas, list):
        print(f"| Therapy Areas | {'; '.join(areas)} |")
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

# ── SWOT — use drug-swot evidence collector ──────────────────────────────────

_skills_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
swot_collector = os.path.join(_skills_dir, "drug-swot", "recipes", "swot_data_collector.py")
if os.path.exists(swot_collector):
    result = subprocess.run(
        ["python3", swot_collector, profile_dir],
        capture_output=True, text=True,
    )
    if result.stdout.strip():
        print("## Strategic SWOT Analysis")
        print()
        print(result.stdout)
elif swot:
    # Fallback: show editorial SWOT if collector not available
    swot_list = swot.get("drugSwotsOutput", {}).get("SWOTs", {}).get("SWOT", [])
    if isinstance(swot_list, dict):
        swot_list = [swot_list]
    if swot_list:
        print("## SWOT Analysis (Cortellis Editorial)")
        print()
        _singular = {"Strengths": "Strength", "Weaknesses": "Weakness",
                     "Opportunities": "Opportunity", "Threats": "Threat"}
        for swot_obj in swot_list:
            swot_class = swot_obj.get("Class", "")
            if swot_class:
                print(f"**Class: {swot_class}**")
                print()
            for section in ["Strengths", "Weaknesses", "Opportunities", "Threats"]:
                entries = swot_obj.get(section, {}).get(_singular[section], [])
                if isinstance(entries, dict):
                    entries = [entries]
                texts = []
                for e in entries:
                    text = re.sub(r"<[^>]+>", "", e.get("$", "")).strip()
                    if text and not text.startswith("Last updated on"):
                        texts.append(text)
                if texts:
                    print(f"### {section}")
                    for t in texts[:5]:
                        print(f"- {' '.join(t.split())[:250]}")
                    if len(texts) > 5:
                        print(f"- ... and {len(texts) - 5} more")
                    print()

# ── Financials (full commentary, no truncation) ─────────────────────────────

if financials:
    fin = financials.get("drugFinancialsOutput", {})
    commentary = fin.get("DrugSalesAndForecastCommentary", "")
    if commentary and len(str(commentary)) > 50:
        print("## Financial Data")
        print()
        clean = re.sub(r"<[^>]+>", " ", str(commentary))
        clean = " ".join(clean.split())
        print(clean)
        print()

# ── Competitive Landscape (launched + Phase 3) ──────────────────────────────

any_competitors = False

if competitors:
    comp_data = competitors.get("drugResultsOutput", {})
    total = comp_data.get("@totalResults", "0")
    comp_list = comp_data.get("SearchResults", {}).get("Drug", [])
    if isinstance(comp_list, dict):
        comp_list = [comp_list]
    if isinstance(comp_list, str):
        comp_list = []
    # Exclude self
    comp_list = [c for c in comp_list if str(c.get("@id", "")) != str(drug_id)]
    if comp_list:
        any_competitors = True
        print(f"## Competitive Landscape — Launched ({total} total, same mechanism)")
        print()
        print("| Drug | Company | Phase | Indications |")
        print("|------|---------|-------|-------------|")
        for c in comp_list:
            cname = c.get("@name", "?")[:45]
            cco = c.get("CompanyOriginator", "?")[:25]
            cphase = c.get("@phaseHighest", "?")
            cindics = c.get("IndicationsPrimary", {}).get("Indication", "")
            if isinstance(cindics, list):
                cindics = "; ".join(str(i) for i in cindics[:3])
            print(f"| {cname} | {cco} | {cphase} | {cindics} |")
        print()

if competitors_p3:
    comp_data = competitors_p3.get("drugResultsOutput", {})
    total = comp_data.get("@totalResults", "0")
    comp_list = comp_data.get("SearchResults", {}).get("Drug", [])
    if isinstance(comp_list, dict):
        comp_list = [comp_list]
    if isinstance(comp_list, str):
        comp_list = []
    comp_list = [c for c in comp_list if str(c.get("@id", "")) != str(drug_id)]
    if comp_list:
        any_competitors = True
        print(f"## Pipeline Threats — Phase 3 ({total} total, same mechanism)")
        print()
        print("| Drug | Company | Indications |")
        print("|------|---------|-------------|")
        for c in comp_list:
            cname = c.get("@name", "?")[:45]
            cco = c.get("CompanyOriginator", "?")[:25]
            cindics = c.get("IndicationsPrimary", {}).get("Indication", "")
            if isinstance(cindics, list):
                cindics = "; ".join(str(i) for i in cindics[:3])
            print(f"| {cname} | {cco} | {cindics} |")
        print()

# ── Drug Design / Pharmacology Enrichment ────────────────────────────────────

si_drug = load_json("si_drug.json")
pharmacology = load_json("pharmacology.json")

if si_drug or pharmacology:
    print("## Drug Design & Pharmacology")
    print()

    if si_drug:
        si_results = si_drug.get("drugResultsOutput", si_drug)
        si_list = si_results.get("SearchResults", {})
        if isinstance(si_list, dict):
            si_drugs = si_list.get("DrugResult", si_list.get("Drug", []))
            if isinstance(si_drugs, dict):
                si_drugs = [si_drugs]
            if isinstance(si_drugs, list) and si_drugs:
                d = si_drugs[0]
                print("| Field | Value |")
                print("|-------|-------|")
                for label, key in [("SI ID", "@id"), ("Name", "NameMain"),
                                   ("Phase", "PhaseHighest"), ("Biologic", "DrugIsBiologic")]:
                    val = d.get(key, "")
                    if isinstance(val, dict):
                        val = val.get("$", str(val))
                    if val:
                        print(f"| {label} | {val} |")
                # Molecular mechanisms
                mechs = d.get("MechanismsMolecular", {}).get("Mechanism", [])
                if isinstance(mechs, dict):
                    mechs = [mechs]
                if isinstance(mechs, list) and mechs:
                    mech_names = [m.get("$", str(m)) if isinstance(m, dict) else str(m) for m in mechs[:5]]
                    print(f"| Molecular Mechanisms | {'; '.join(mech_names)} |")
                print()

    if pharmacology:
        pharm_results = pharmacology.get("pharmacologyResultsOutput", pharmacology)
        total = pharm_results.get("@totalResults", "0")
        sr = pharm_results.get("SearchResults", {})
        records = sr.get("PharmacologyResult", []) if isinstance(sr, dict) else []
        if isinstance(records, dict):
            records = [records]
        if records:
            print(f"**Pharmacology ({total} records):**")
            print()
            print("| Compound | System | Target | Effect | Parameter | Value |")
            print("|----------|--------|--------|--------|-----------|-------|")
            for r in records[:10]:
                compound = extract_text(r, "TestedDrug", "?")[:20]
                system = extract_text(r, "ActivityPharmacologicalSystem", "?")
                target = extract_text(r, "ActivityPharmacologicalTypeValue", "?")[:25]
                effect = extract_text(r, "ActivityPharmacologicalEffect", "?")
                param = extract_text(r, "ParameterGiven", "?")
                value_str = "-"
                res_block = r.get("Results", {})
                res_list = res_block.get("Result", [])
                if isinstance(res_list, dict):
                    res_list = [res_list]
                if res_list:
                    v = res_list[0].get("Value", {})
                    if isinstance(v, dict):
                        value_str = v.get("$", "")
                    unit = res_list[0].get("@unit", extract_text(r, "UnitGiven", ""))
                    if value_str and unit:
                        value_str = f"{value_str} {unit}"
                print(f"| {compound} | {system} | {target} | {effect} | {param} | {value_str} |")
            print()

# ── Patent & Biosimilar Landscape ───────────────────────────────────────────��

if patent_expiry or biosimilars:
    print("## Patent & Biosimilar Landscape")
    print()
    if patent_expiry:
        rows = patent_expiry.get("Rowset", {}).get("Row", [])
        if isinstance(rows, dict):
            rows = [rows]
        for r in rows:
            drug = extract_text(r, "Drug", "?")
            first_exp = r.get("PfFirstExpiryDate", "?")
            last_exp = r.get("PfLastExpiryDate", "?")
            if isinstance(first_exp, str) and len(first_exp) > 10:
                first_exp = first_exp[:10]
            if isinstance(last_exp, str) and len(last_exp) > 10:
                last_exp = last_exp[:10]
            print(f"**Patent Window:** {first_exp} to {last_exp}")
        print()

    if biosimilars:
        br = biosimilars.get("drugResultsOutput", {})
        total = br.get("@totalResults", "0")
        sr = br.get("SearchResults", {})
        bio_list = sr.get("Drug", []) if isinstance(sr, dict) else []
        if isinstance(bio_list, dict):
            bio_list = [bio_list]
        if bio_list:
            print(f"**Biosimilar/Generic Threats ({total}):**")
            print()
            print("| Drug | Company | Phase |")
            print("|------|---------|-------|")
            for b in bio_list:
                bname = b.get("@name", "?")[:45]
                bco = b.get("CompanyOriginator", "?")[:25]
                bphase = b.get("@phaseHighest", "?")
                print(f"| {bname} | {bco} | {bphase} |")
            print()
        else:
            print("No biosimilar/generic threats identified.")
            print()

# ── Deals (ALL, no truncation) ───────────────────────────────────────────────

if deals:
    deal_data = deals.get("dealResultsOutput", {})
    total_deals = deal_data.get("@totalResults", "0")
    deal_list = deal_data.get("SearchResults", {}).get("Deal", [])
    if isinstance(deal_list, dict):
        deal_list = [deal_list]
    if isinstance(deal_list, str):
        deal_list = []
    if deal_list:
        print(f"## Deals ({total_deals} total)")
        print()
        print("| Deal | Partner | Type | Date |")
        print("|------|---------|------|------|")
        for d in deal_list:
            title = d.get("Title", "?")[:55]
            partner = d.get("CompanyPartner", "?")[:30]
            dtype = d.get("Type", "?")[:30]
            date = d.get("StartDate", d.get("DealDateStart", "?"))[:10]
            print(f"| {title} | {partner} | {dtype} | {date} |")
        print()

# ��─ Clinical Trials (ALL, no truncation) ─────────────────────────────────────

if trials:
    trial_data = trials.get("trialResultsOutput", {})
    total_trials = trial_data.get("@totalResults", "0")
    trial_list = trial_data.get("SearchResults", {}).get("Trial", [])
    if isinstance(trial_list, dict):
        trial_list = [trial_list]
    if isinstance(trial_list, str):
        trial_list = []
    if trial_list:
        print(f"## Clinical Trials ({total_trials} total)")
        print()
        print("| Trial | Phase | Status | Enrollment |")
        print("|-------|-------|--------|------------|")
        for t in trial_list:
            title = t.get("TitleDisplay", t.get("Title", "?"))[:55]
            tphase = t.get("Phase", "?")
            status = t.get("RecruitmentStatus", "?")
            enroll = t.get("PatientCountEnrollment", "?")
            print(f"| {title} | {tphase} | {status} | {enroll} |")
        print()

# ── Regulatory Documents ─────────────────────────────────────────────────────

if regulatory:
    reg_data = regulatory.get("regulatoryResultsOutput", regulatory)
    total_reg = reg_data.get("@totalResults", "0")
    if isinstance(total_reg, str) and total_reg.isdigit() and int(total_reg) > 0:
        reg_list = reg_data.get("SearchResults", {}).get("Regulatory", [])
        if isinstance(reg_list, dict):
            reg_list = [reg_list]
        if isinstance(reg_list, str):
            reg_list = []
        if reg_list:
            print(f"## Regulatory Documents ({total_reg} total)")
            print()
            print("*Note: These are regulatory filings and documents. For approval timeline analysis, use `/regulatory-pathway`.*")
            print()
            print("| Document | Region | Type | Date |")
            print("|----------|--------|------|------|")
            for r in reg_list:
                title = r.get("Title", "?")[:55]
                region = r.get("Region", "?")
                dtype = r.get("DocTypes", {}).get("DocType", "?")
                if isinstance(dtype, list):
                    dtype = dtype[0] if dtype else "?"
                date = r.get("DateDisplay", "?")
                print(f"| {title} | {region} | {dtype} | {date} |")
            print()

# ── Data Completeness Footer ─────────────────────────────────────────────────

print("## Data Completeness")
print()
print("| Source | Status |")
print("|--------|--------|")

source_labels = {
    "record.json": "Drug Record",
    "swot.json": "Editorial SWOT",
    "financials.json": "Financials",
    "history.json": "Development History",
    "deals.json": "Deals",
    "trials.json": "Clinical Trials",
    "regulatory.json": "Regulatory Documents",
    "competitors.json": "Competitors (Launched)",
    "competitors_p3.json": "Competitors (Phase 3)",
    "patent_expiry.json": "Patent Expiry",
    "biosimilars.json": "Biosimilar Threats",
    "si_drug.json": "Drug Design Record",
    "pharmacology.json": "Pharmacology Data",
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

completeness_pct = int(ok_count / total_count * 100) if total_count else 0
print(f"| **Overall** | **{ok_count}/{total_count} sources ({completeness_pct}%)** |")
print()

if completeness_pct < 100:
    missing = [source_labels.get(f, f) for f, s in _data_status.items()
               if s != "ok" and f in source_labels]
    if missing:
        print(f"*Missing/failed sources: {', '.join(missing)}. Results may be incomplete.*")
        print()
