#!/usr/bin/env python3
"""Collect and summarize data from 8+ Cortellis domains into a structured evidence brief.

The LLM uses this brief to synthesize a strategic SWOT analysis.

Usage: python3 swot_data_collector.py /tmp/drug_swot
"""
import html, json, re, sys, os
from collections import Counter

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
        # Domain-specific emptiness: check for expected output keys
        top_keys = [k for k in d.keys() if k.endswith("Output") or k.endswith("output")]
        if top_keys:
            inner = d[top_keys[0]]
            if not inner or (isinstance(inner, str) and len(inner.strip()) == 0):
                _data_status[filename] = "empty"
                return None
        elif len(str(d)) < 30:
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
    if not cur or isinstance(cur, str):
        return []
    return []


def extract_text(obj, key, default=""):
    if not isinstance(obj, dict):
        return default
    val = obj.get(key, default)
    if isinstance(val, dict):
        return val.get("$", val.get("@name", str(val)))
    return str(val) if val else default


def clean(text):
    """Strip HTML tags and decode entities."""
    if not text:
        return ""
    return html.unescape(re.sub(r"<[^>]+>", " ", str(text)).strip())


def safe_join(items, sep="; "):
    result = []
    for i in items:
        if isinstance(i, dict):
            result.append(i.get("$", i.get("@name", str(i))))
        else:
            result.append(str(i))
    return sep.join(result)


# ── 1. DRUG PROFILE ──────────────────────────────────────────────────────────

print("# EVIDENCE BRIEF FOR SWOT SYNTHESIS")
print()

drug_record = load_json("drug_record.json") or load_json("record.json")
rec = {}
if drug_record:
    rec = drug_record.get("drugRecordOutput", drug_record)

name = rec.get("DrugName", rec.get("@name", "Unknown"))
drug_id = rec.get("@id", "?")
phase = extract_text(rec, "PhaseHighest", "?")
originator = extract_text(rec, "CompanyOriginator", "?")

print("## 1. Drug Profile")
print(f"- **Name:** {name}")
print(f"- **ID:** {drug_id}")
print(f"- **Phase:** {phase}")
print(f"- **Originator:** {originator}")

# Indications
indics = extract_list(rec, "IndicationsPrimary", "Indication")
if indics:
    ind_names = [extract_text(i, "$", str(i)) if isinstance(i, dict) else str(i) for i in indics]
    print(f"- **Primary Indications ({len(indics)}):** {'; '.join(ind_names)}")

# Mechanism
actions = extract_list(rec, "ActionsPrimary", "Action")
if actions:
    act_names = [extract_text(a, "$", str(a)) if isinstance(a, dict) else str(a) for a in actions]
    print(f"- **Mechanism:** {'; '.join(act_names)}")

# Technology
tech = rec.get("Technology", "")
if isinstance(tech, dict):
    tech_list = tech.get("TechnologyType", tech.get("Type", []))
    if isinstance(tech_list, list):
        tech_names = [t.get("$", str(t)) if isinstance(t, dict) else str(t) for t in tech_list]
        print(f"- **Technology:** {'; '.join(tech_names)}")
    elif isinstance(tech_list, dict):
        print(f"- **Technology:** {extract_text(tech_list, '$', str(tech_list))}")
elif isinstance(tech, str) and tech:
    print(f"- **Technology:** {tech}")

# Brands
brands = rec.get("BrandNames", rec.get("BrandName", ""))
if isinstance(brands, dict):
    brand_list = brands.get("BrandName", [])
    if isinstance(brand_list, list):
        brands = "; ".join(str(b.get("$", b) if isinstance(b, dict) else b) for b in brand_list)
    elif isinstance(brand_list, dict):
        brands = brand_list.get("$", str(brand_list))
if brands:
    print(f"- **Brands:** {brands}")

# Safety warnings — full text, no truncation
safety = rec.get("SafetyInformation", rec.get("BlackBoxWarning", ""))
if isinstance(safety, dict):
    safety = safety.get("$", "")
if safety:
    print(f"- **Safety Warnings:** {clean(str(safety))}")

print()

# ── 2. FINANCIALS ─────────────────────────────────────────────────────────────

financials = load_json("financials.json")
if financials:
    fin_rec = financials.get("drugFinancialsOutput", financials)
    commentary = fin_rec.get("DrugSalesAndForecastCommentary", fin_rec.get("SalesCommentary", ""))
    if isinstance(commentary, dict):
        commentary = commentary.get("$", str(commentary))
    commentary = clean(str(commentary))

    print("## 2. Financial Data")
    if commentary:
        print(f"- **Sales Commentary:** {commentary}")
    else:
        print("- No financial commentary available")

    # Consensus data — full text
    consensus = fin_rec.get("ConsensusData", "")
    if isinstance(consensus, dict):
        consensus_text = clean(str(consensus.get("$", consensus)))
        if consensus_text and len(consensus_text) > 20:
            print(f"- **Consensus Forecast:** {consensus_text}")
    print()
else:
    print("## 2. Financial Data")
    print("- Not available (pre-commercial drug)")
    print()

# ── 3. DEVELOPMENT HISTORY ────────────────────────────────────────────────────

history = load_json("history.json")
if history:
    hist_rec = history.get("drugHistoryOutput", history)
    events = extract_list(hist_rec, "ChangeHistory", "Change")
    if not events:
        events = extract_list(hist_rec, "Events", "Event")
    # Filter to meaningful events, most recent first
    key_reasons = {"Approval", "Launch", "Phase change", "Regulatory submission",
                   "License agreement", "Clinical trial results", "Drug added",
                   "New Indication Added", "Regulatory Agency Decision",
                   "Safety update", "Label change", "Highest status change"}
    meaningful = []
    for e in reversed(events):
        reason = extract_text(e.get("Reason", {}), "$", "") if isinstance(e.get("Reason"), dict) else str(e.get("Reason", ""))
        detail = clean(e.get("DetailFormatted", e.get("Description", "")))
        if detail or reason in key_reasons:
            meaningful.append(e)
        if len(meaningful) >= 25:
            break
    print(f"## 3. Development History ({len(events)} total changes, {len(meaningful)} key milestones)")
    for e in meaningful:
        date = e.get("Date", "?")
        if isinstance(date, str) and len(date) > 10:
            date = date[:10]
        reason = extract_text(e.get("Reason", {}), "$", "") if isinstance(e.get("Reason"), dict) else ""
        detail = clean(e.get("DetailFormatted", ""))[:200]
        label = detail if detail else reason
        print(f"- [{date}] {label}")
    print()

# ── 4. ACTIVE TRIALS ──────────────────────────────────────────────────────────

trials = load_json("trials.json")
if trials:
    tr = trials.get("trialResultsOutput", {})
    total = tr.get("@totalResults", "0")
    sr = tr.get("SearchResults", {})
    trial_list = sr.get("Trial", []) if isinstance(sr, dict) else []
    if isinstance(trial_list, dict):
        trial_list = [trial_list]

    print(f"## 4. Active Clinical Trials ({total} total)")

    phase_counter = Counter()
    status_counter = Counter()
    for t in trial_list:
        phase_counter[t.get("Phase", "?")] += 1
        status_counter[t.get("RecruitmentStatus", "?")] += 1

    if phase_counter:
        print(f"- **By Phase:** {', '.join(f'{p}: {c}' for p, c in phase_counter.most_common())}")
    if status_counter:
        print(f"- **By Status:** {', '.join(f'{s}: {c}' for s, c in status_counter.most_common())}")

    # Show ALL fetched trials
    fetched = len(trial_list)
    total_int = int(total) if str(total).isdigit() else fetched
    if fetched < total_int:
        print(f"- **Recent Trials (showing {fetched} of {total_int}, sorted by most recent start):**")
    else:
        print(f"- **Trials ({fetched}):**")
    for t in trial_list:
        title = clean(t.get("TitleDisplay", t.get("Title", "?")))[:100]
        tphase = t.get("Phase", "?")
        status = t.get("RecruitmentStatus", "?")
        enroll = t.get("PatientCountEnrollment", "?")
        print(f"  - {title} | {tphase} | {status} | N={enroll}")
    print()

# ── 5. RECENT DEALS ──────────────────────────────────────────────────────────

deals = load_json("deals.json")
if deals:
    dr = deals.get("dealResultsOutput", {})
    total = dr.get("@totalResults", "0")
    sr = dr.get("SearchResults", {})
    deal_list = sr.get("Deal", []) if isinstance(sr, dict) else []
    if isinstance(deal_list, dict):
        deal_list = [deal_list]

    fetched = len(deal_list)
    total_int = int(total) if str(total).isdigit() else fetched
    if fetched < total_int:
        print(f"## 5. Recent Deals (showing {fetched} of {total_int} total)")
    else:
        print(f"## 5. Recent Deals ({total} total)")
    for d in deal_list:
        title = clean(d.get("Title", "?"))[:80]
        dtype = d.get("Type", "?")
        status = d.get("Status", "?")
        partner = d.get("CompanyPartner", "?")
        value = d.get("MaximumProjectedValueToPrincipal", "?")
        print(f"- {title}")
        print(f"  Type: {dtype} | Status: {status} | Partner: {partner} | Value: {value}")
    print()

# ── 6. PATENT LANDSCAPE ──────────────────────────────────────────────────────

patent = load_json("patent_expiry.json")
biosimilars = load_json("biosimilars.json")

print("## 6. Patent & Generic/Biosimilar Landscape")
if patent:
    rows = extract_list(patent, "Rowset", "Row")
    for r in rows:
        drug = extract_text(r, "Drug", "?")
        first_exp = r.get("PfFirstExpiryDate", "?")
        last_exp = r.get("PfLastExpiryDate", "?")
        if isinstance(first_exp, str) and len(first_exp) > 10:
            first_exp = first_exp[:10]
        if isinstance(last_exp, str) and len(last_exp) > 10:
            last_exp = last_exp[:10]
        print(f"- **Patent Window:** {first_exp} to {last_exp}")
else:
    print("- No patent expiry data available")

if biosimilars:
    br = biosimilars.get("drugResultsOutput", {})
    total = br.get("@totalResults", "0")
    sr = br.get("SearchResults", {})
    bio_list = sr.get("Drug", []) if isinstance(sr, dict) else []
    if isinstance(bio_list, dict):
        bio_list = [bio_list]
    if bio_list:
        print(f"- **Biosimilar/Generic Threats ({total}):**")
        for b in bio_list:
            bname = b.get("@name", "?")[:50]
            bphase = b.get("@phaseHighest", "?")
            bco = b.get("CompanyOriginator", "?")[:30]
            print(f"  - {bname} | {bphase} | {bco}")
    else:
        print("- No biosimilar/generic threats identified")
else:
    print("- No biosimilar search data")
print()

# ── 7. COMPETITIVE LANDSCAPE ─────────────────────────────────────────────────

comp_launched = load_json("competitors_launched.json") or load_json("competitors.json")
comp_p3 = load_json("competitors_p3.json")

print("## 7. Competitive Landscape")

if comp_launched:
    cr = comp_launched.get("drugResultsOutput", {})
    total = cr.get("@totalResults", "0")
    sr = cr.get("SearchResults", {})
    drugs = sr.get("Drug", []) if isinstance(sr, dict) else []
    if isinstance(drugs, dict):
        drugs = [drugs]
    drugs = [d for d in drugs if str(d.get("@id", "")) != str(drug_id)]

    if drugs:
        print(f"- **Launched Competitors ({total} total, same mechanism):**")
        co_counter = Counter()
        for d in drugs:
            co_counter[d.get("CompanyOriginator", "?")[:30]] += 1
        for d in drugs:
            dname = d.get("@name", "?")[:40]
            dco = d.get("CompanyOriginator", "?")[:25]
            print(f"  - {dname} ({dco})")
        print(f"- **Top Competitors by Company:** {', '.join(f'{c}: {n}' for c, n in co_counter.most_common(5))}")

if comp_p3:
    cr = comp_p3.get("drugResultsOutput", {})
    total = cr.get("@totalResults", "0")
    sr = cr.get("SearchResults", {})
    drugs = sr.get("Drug", []) if isinstance(sr, dict) else []
    if isinstance(drugs, dict):
        drugs = [drugs]
    drugs = [d for d in drugs if str(d.get("@id", "")) != str(drug_id)]

    if drugs:
        print(f"- **Phase 3 Pipeline Threats ({total} total):**")
        for d in drugs:
            dname = d.get("@name", "?")[:40]
            dco = d.get("CompanyOriginator", "?")[:25]
            indics = d.get("IndicationsPrimary", {}).get("Indication", "")
            if isinstance(indics, list):
                indics = "; ".join(str(i) for i in indics[:3])
            print(f"  - {dname} ({dco}) \u2014 {indics}")
print()

# ── 8. CORTELLIS EDITORIAL SWOT (reference) ──────────────────────────────────

cortellis_swot = load_json("cortellis_swot.json") or load_json("swot.json")
if cortellis_swot:
    swot_list = extract_list(cortellis_swot, "drugSwotsOutput", "SWOTs", "SWOT")
    print("## 8. Cortellis Editorial SWOT (reference \u2014 may be outdated)")
    for s in swot_list:
        swot_class = s.get("Class", "?")
        print(f"### Class: {swot_class}")
        _singular = {
            "Strengths": "Strength", "Weaknesses": "Weakness",
            "Opportunities": "Opportunity", "Threats": "Threat",
        }
        for dim in ["Strengths", "Weaknesses", "Opportunities", "Threats"]:
            items = s.get(dim, {}).get(_singular[dim], [])
            if isinstance(items, dict):
                items = [items]
            texts = []
            last_updated = None
            for item in items:
                text = clean(item.get("$", ""))
                if text.startswith("Last updated on"):
                    last_updated = text
                elif text:
                    texts.append(text)
            if last_updated:
                print(f"  **{dim} ({len(texts)} items) \u2014 {last_updated}:**")
            else:
                print(f"  **{dim} ({len(texts)} items):**")
            for t in texts[:5]:
                print(f"  - {t[:300]}")
            if len(texts) > 5:
                print(f"  - ... and {len(texts) - 5} more")
    print()
else:
    print("## 8. Cortellis Editorial SWOT")
    print("- Not available for this drug")
    print()

# ── DATA COMPLETENESS ────────────────────────────────────────────────────────

print("## Data Completeness")
print()
print("| Source | Status |")
print("|--------|--------|")

source_labels = {
    "drug_record.json": "Drug Record",
    "record.json": "Drug Record (alt)",
    "financials.json": "Financials",
    "history.json": "Development History",
    "trials.json": "Clinical Trials",
    "deals.json": "Deals",
    "patent_expiry.json": "Patent Expiry",
    "biosimilars.json": "Biosimilar Threats",
    "competitors_launched.json": "Competitors (Launched)",
    "competitors.json": "Competitors (alt)",
    "competitors_p3.json": "Competitors (Phase 3)",
    "cortellis_swot.json": "Editorial SWOT",
    "swot.json": "Editorial SWOT (alt)",
}

# Deduplicate alt sources — only show the one that was actually used
shown = set()
ok_count = 0
total_count = 0
for filename, label in source_labels.items():
    status = _data_status.get(filename)
    if status is None:
        continue  # file never attempted (alt path not needed)
    base_label = label.replace(" (alt)", "")
    if base_label in shown:
        continue
    shown.add(base_label)
    total_count += 1
    if status == "ok":
        ok_count += 1
        print(f"| {base_label} | Available |")
    elif status == "missing":
        print(f"| {base_label} | Not fetched |")
    elif status == "empty":
        print(f"| {base_label} | Empty (no data) |")
    else:
        print(f"| {base_label} | {status} |")

pct = int(ok_count / total_count * 100) if total_count else 0
print(f"| **Overall** | **{ok_count}/{total_count} sources ({pct}%)** |")
print()

if pct < 100:
    missing = []
    shown2 = set()
    for f, s in _data_status.items():
        if s != "ok" and f in source_labels:
            base = source_labels[f].replace(" (alt)", "")
            if base not in shown2:
                shown2.add(base)
                missing.append(base)
    if missing:
        print(f"*Missing/failed sources: {', '.join(missing)}. SWOT synthesis may have gaps in these areas.*")
        print()

print("---")
print("Use ONLY the evidence above to synthesize the Strategic SWOT.")
print("Every claim must cite a specific data point from this brief.")
