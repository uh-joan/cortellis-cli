#!/usr/bin/env python3
"""Generate a formatted target profile report from collected JSON files.

Usage: python3 target_report_generator.py raw/targets/<slug>/
"""
import json
import sys
import os
from collections import Counter


data_dir = sys.argv[1] if len(sys.argv) > 1 else "raw/targets/unknown"


def load_json(filename):
    path = os.path.join(data_dir, filename)
    if not os.path.exists(path):
        return None
    with open(path) as f:
        content = f.read().strip()
        if not content:
            return None
        return json.loads(content)


def bar_chart(data, title, max_width=40, char="█"):
    if not data:
        return ""
    max_val = max(v for _, v in data)
    if max_val == 0:
        return ""
    lines = [title, "─" * 60]
    for label, value in data:
        bar_len = int(value / max_val * max_width)
        bar = char * max(bar_len, 1)
        lines.append(f"  {label:35s} {bar} {value}")
    return "\n".join(lines)


# Load all data
record = load_json("record.json")
condition_drugs = load_json("condition_drugs.json")
condition_genes = load_json("condition_genes.json")
interactions = load_json("interactions.json")
drugs_pipeline = load_json("drugs_pipeline.json")
pharmacology = load_json("pharmacology.json")
briefings = load_json("briefings.json")

# Parse target record
target_name = "Unknown"
target_id = "?"
gene_symbol = ""
organism = ""
synonyms = []
function_desc = ""
family = ""
subcellular = ""

if record:
    # Handle targets records API response: TargetRecordsOutput.Targets.Target
    targets = record.get("TargetRecordsOutput", {}).get("Targets", {}).get("Target", {})
    if isinstance(targets, list):
        targets = targets[0] if targets else {}
    target_name = targets.get("@namemain", target_name)
    target_id = targets.get("@id", target_id)
    # Extract gene symbol from synonyms (shortest all-caps)
    syn_list = targets.get("Synonyms", {}).get("Synonym", [])
    if isinstance(syn_list, str):
        syn_list = [syn_list]
    synonyms = [s for s in syn_list if isinstance(s, str)][:10]
    for s in synonyms:
        if s.isupper() and len(s) <= 10:
            gene_symbol = s
            break
    # Family
    fam = targets.get("Family", "")
    if isinstance(fam, dict):
        family = fam.get("$", fam.get("@name", ""))
    elif isinstance(fam, str):
        family = fam
    # Organism from Localizations or default
    organism = "Human"
    # Function from Description
    function_desc = targets.get("Description", "")
    if isinstance(function_desc, dict):
        function_desc = function_desc.get("$", str(function_desc))
    # Subcellular location
    locs = targets.get("Localizations", {}).get("Localization", [])
    if isinstance(locs, dict):
        locs = [locs]
    if isinstance(locs, list) and locs:
        loc_names = [l.get("$", l) if isinstance(l, dict) else str(l) for l in locs[:3]]
        subcellular = "; ".join(loc_names)

# Header
gene_label = f" ({gene_symbol})" if gene_symbol else ""
print(f"# Target Profile: {target_name}{gene_label}")
print()
print(f"**ID:** {target_id} | **Organism:** {organism or 'Human'} | **Family:** {family or 'N/A'}")
if synonyms:
    print(f"**Synonyms:** {', '.join(synonyms)}")
print()

# Biology
print("## Biology")
print()
print("| Field | Value |")
print("|-------|-------|")
if function_desc:
    func_short = str(function_desc)[:200]
    print(f"| Function | {func_short} |")
if subcellular:
    print(f"| Subcellular Location | {subcellular} |")
if family:
    print(f"| Protein Family | {family} |")
print()

# Disease associations (condition-drug)
if condition_drugs:
    target_data = condition_drugs.get("TargetRecordsOutput", {}).get("Targets", {}).get("Target", {})
    if isinstance(target_data, list):
        target_data = target_data[0] if target_data else {}
    conditions = target_data.get("ConditionDrugAssociations", {}).get("Condition", [])
    if isinstance(conditions, dict):
        conditions = [conditions]
    if conditions:
        # Each condition has @name and DrugId[] with @highestphase, @status
        disease_data = []
        for c in conditions:
            cname = c.get("@name", "Unknown")
            drug_ids = c.get("DrugId", [])
            if isinstance(drug_ids, dict):
                drug_ids = [drug_ids]
            active = [d for d in drug_ids if d.get("@status") == "Active"]
            total = len(drug_ids)
            # Find highest phase drug
            phase_order = {"Launched": 0, "Pre-registration": 1, "Phase III": 2, "Phase II": 3,
                           "Phase I": 4, "Preclinical": 5, "Biological Testing": 6, "Discovery": 7}
            best_phase = "?"
            if drug_ids:
                best = min(drug_ids, key=lambda d: phase_order.get(d.get("@highestphase", "?"), 99))
                best_phase = best.get("@highestphase", "?")
            disease_data.append((cname, total, len(active), best_phase))

        # Sort by total drugs descending
        disease_data.sort(key=lambda x: -x[1])

        print(f"## Disease Associations ({len(disease_data)} diseases)")
        print()
        print("| Disease | Total Drugs | Active | Highest Phase |")
        print("|---------|-------------|--------|---------------|")
        for cname, total, active, best_phase in disease_data:
            print(f"| {cname[:50]} | {total} | {active} | {best_phase} |")
        print()

# Genetic evidence (condition-gene)
if condition_genes:
    target_data = condition_genes.get("TargetRecordsOutput", {}).get("Targets", {}).get("Target", {})
    if isinstance(target_data, list):
        target_data = target_data[0] if target_data else {}
    gene_assocs = target_data.get("ConditionGeneAssociations", {}).get("Condition", [])
    if isinstance(gene_assocs, dict):
        gene_assocs = [gene_assocs]
    if gene_assocs:
        print(f"## Genetic Evidence ({len(gene_assocs)} associations)")
        print()
        print("| Disease | Evidence Sources |")
        print("|---------|-----------------|")
        for a in gene_assocs:
            cname = a.get("@name", "?")
            sources = a.get("Source", [])
            if isinstance(sources, dict):
                sources = [sources]
            if isinstance(sources, str):
                sources = [{"$": sources}]
            src_names = [s.get("$", s) if isinstance(s, dict) else str(s) for s in sources[:3]]
            print(f"| {cname[:45]} | {'; '.join(src_names)[:50]} |")
        print()

# Drug pipeline
if drugs_pipeline:
    results = drugs_pipeline.get("drugResultsOutput", {})
    total = results.get("@totalResults", "?")
    drug_list = results.get("SearchResults", {}).get("Drug", [])
    if isinstance(drug_list, dict):
        drug_list = [drug_list]

    if drug_list:
        # Phase distribution
        phase_counts = Counter()
        for d in drug_list:
            phase_counts[d.get("@phaseHighest", "?")] += 1

        phase_data = []
        for p in ["Launched", "Pre-registration", "Phase 3 Clinical", "Phase 2 Clinical", "Phase 1 Clinical", "Preclinical", "Discovery"]:
            if phase_counts.get(p, 0) > 0:
                phase_data.append((p, phase_counts[p]))

        print(f"## Drug Pipeline ({total} total)")
        print()
        print("```")
        print(bar_chart(phase_data, "Pipeline by Phase"))
        print("```")
        print()

        print("| Drug | Company | Phase | Indications |")
        print("|------|---------|-------|-------------|")
        for d in drug_list:
            name = d.get("@name", "?")[:50]
            company = ""
            co = d.get("CompanyOriginator", {})
            if isinstance(co, dict):
                company = co.get("@name", "")
            elif isinstance(co, list) and co:
                company = co[0].get("@name", "")
            company = company[:35]
            phase = d.get("@phaseHighest", "?")
            inds = d.get("IndicationsPrimary", {}).get("Indication", [])
            if isinstance(inds, dict):
                inds = [inds]
            ind_names = "; ".join(i.get("@name", "") for i in inds[:3] if isinstance(i, dict))[:50]
            print(f"| {name} | {company} | {phase} | {ind_names} |")
        print()

# Protein interactions
if interactions:
    target_data = interactions.get("TargetRecordsOutput", {}).get("Targets", {}).get("Target", {})
    if isinstance(target_data, list):
        target_data = target_data[0] if target_data else {}
    inter_list = target_data.get("Interactions", {}).get("Interaction", [])
    if isinstance(inter_list, dict):
        inter_list = [inter_list]
    if inter_list:
        # Filter to meaningful interactions (skip long chemical names)
        meaningful = [i for i in inter_list if len(i.get("CounterpartObject", {}).get("$", "")) < 60]
        if not meaningful:
            meaningful = inter_list
        print(f"## Protein Interactions ({len(inter_list)} total)")
        print()
        print("| Partner | Direction | Effect | Mechanism |")
        print("|---------|-----------|--------|-----------|")
        for i in meaningful:
            partner = i.get("CounterpartObject", {}).get("$", "?")
            direction = i.get("Direction", "?")
            effect = i.get("Effect", "?")
            mechanism = i.get("Mechanism", "?")
            print(f"| {partner[:40]} | {direction[:10]} | {effect[:15]} | {mechanism[:15]} |")
        print()

# Pharmacology
if pharmacology:
    pharm_results = pharmacology.get("drugDesignResultsOutput", {}).get("SearchResults", {})
    pharm_list = pharm_results.get("PharmacologyRecord", [])
    if isinstance(pharm_list, dict):
        pharm_list = [pharm_list]
    if pharm_list:
        print(f"## Pharmacology ({len(pharm_list)} records)")
        print()
        print("| Compound | Assay | Value | Unit |")
        print("|----------|-------|-------|------|")
        for p in pharm_list:
            compound = p.get("@drugName", p.get("Drug", {}).get("@name", "?"))
            assay = p.get("@assayType", p.get("AssayType", ""))
            if isinstance(assay, dict):
                assay = assay.get("@name", "")
            value = p.get("@value", p.get("Value", "?"))
            unit = p.get("@unit", p.get("Unit", ""))
            if isinstance(unit, dict):
                unit = unit.get("@name", "")
            print(f"| {str(compound)[:35]} | {str(assay)[:25]} | {str(value)[:15]} | {str(unit)[:10]} |")
        print()

# Disease briefings
if briefings:
    brief_results = briefings.get("drugDesignResultsOutput", {}).get("SearchResults", {})
    brief_list = brief_results.get("DiseaseBriefing", [])
    if isinstance(brief_list, dict):
        brief_list = [brief_list]
    if brief_list:
        print(f"## Disease Briefings ({len(brief_list)})")
        print()
        for b in brief_list[:3]:
            bname = b.get("@name", b.get("@title", "?"))
            bid = b.get("@id", "?")
            print(f"- **{bname}** (ID: {bid})")
        print()
