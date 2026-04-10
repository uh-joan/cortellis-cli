#!/usr/bin/env python3
"""
compile_target.py — Compile target profile data into wiki article.

Reads target profile JSON files and produces wiki/targets/<slug>.md.

Usage: python3 compile_target.py <target_dir> [target_name] [--wiki-dir DIR]
"""

import os
import sys
from datetime import datetime, timezone

# Allow running as standalone script
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))

from cli_anything.cortellis.utils.data_helpers import read_json_safe, safe_int
from cli_anything.cortellis.utils.wiki import (
    slugify,
    normalize_company_name,
    normalize_drug_name,
    find_company_slug,
    wiki_root,
    article_path,
    write_article,
    load_index_entries,
    update_index,
    wikilink,
    log_activity,
)


# ---------------------------------------------------------------------------
# Data extraction — uses actual Cortellis API response structure
# ---------------------------------------------------------------------------

def _unwrap_target(data):
    """Extract the Target dict from TargetRecordsOutput.Targets.Target."""
    if not data or not isinstance(data, dict):
        return {}
    target = data.get("TargetRecordsOutput", {}).get("Targets", {}).get("Target", {})
    if isinstance(target, list):
        target = target[0] if target else {}
    return target if isinstance(target, dict) else {}


def extract_target_overview(record):
    """Extract core fields from record.json. Returns dict."""
    target = _unwrap_target(record)
    if not target:
        return {}

    name = target.get("@namemain", "")
    target_id = target.get("@id", "")

    # Gene symbol: shortest all-caps synonym
    syn_list = target.get("Synonyms", {}).get("Synonym", [])
    if isinstance(syn_list, str):
        syn_list = [syn_list]
    synonyms = [s for s in syn_list if isinstance(s, str)]
    gene_symbol = ""
    for s in synonyms:
        if s.isupper() and len(s) <= 10:
            gene_symbol = s
            break

    # Family
    fam = target.get("Family", "")
    if isinstance(fam, dict):
        family = fam.get("$", fam.get("@name", ""))
    else:
        family = str(fam) if fam else ""

    # Subcellular location
    locs = target.get("Localizations", {}).get("Localization", [])
    if isinstance(locs, dict):
        locs = [locs]
    if isinstance(locs, list) and locs:
        loc_names = [l.get("$", l) if isinstance(l, dict) else str(l) for l in locs[:5]]
        location = "; ".join(loc_names)
    else:
        location = ""

    # Function / description
    function_desc = target.get("Description", "")
    if isinstance(function_desc, dict):
        function_desc = function_desc.get("$", str(function_desc))

    return {
        "name": name,
        "target_id": target_id,
        "gene_symbol": gene_symbol,
        "family": family,
        "location": location,
        "function": str(function_desc)[:500] if function_desc else "",
        "synonyms": synonyms[:10],
    }


def extract_disease_associations(condition_drugs):
    """Extract disease associations from condition_drugs.json.

    Returns list of {disease, drug_count, active_count, highest_phase}.
    """
    target = _unwrap_target(condition_drugs)
    conditions = target.get("ConditionDrugAssociations", {}).get("Condition", [])
    if isinstance(conditions, dict):
        conditions = [conditions]
    if not isinstance(conditions, list):
        return []

    phase_order = {
        "Launched": 0, "Pre-registration": 1, "Phase III": 2,
        "Phase II": 3, "Phase I": 4, "Preclinical": 5,
        "Biological Testing": 6, "Discovery": 7,
    }

    associations = []
    for c in conditions:
        if not isinstance(c, dict):
            continue
        cname = c.get("@name", "")
        if not cname:
            continue
        drug_ids = c.get("DrugId", [])
        if isinstance(drug_ids, dict):
            drug_ids = [drug_ids]
        if not isinstance(drug_ids, list):
            drug_ids = []
        active = [d for d in drug_ids if isinstance(d, dict) and d.get("@status") == "Active"]
        best_phase = "-"
        if drug_ids:
            valid = [d for d in drug_ids if isinstance(d, dict)]
            if valid:
                best = min(valid, key=lambda d: phase_order.get(d.get("@highestphase", "?"), 99))
                best_phase = best.get("@highestphase", "-")
        associations.append({
            "disease": cname,
            "drug_count": len(drug_ids),
            "active_count": len(active),
            "highest_phase": best_phase,
        })

    associations.sort(key=lambda x: -x["drug_count"])
    return associations


def extract_gene_associations(condition_genes):
    """Extract genetic evidence from condition_genes.json.

    Returns list of {disease, sources}.
    """
    target = _unwrap_target(condition_genes)
    gene_assocs = target.get("ConditionGeneAssociations", {}).get("Condition", [])
    if isinstance(gene_assocs, dict):
        gene_assocs = [gene_assocs]
    if not isinstance(gene_assocs, list):
        return []

    items = []
    for a in gene_assocs:
        if not isinstance(a, dict):
            continue
        cname = a.get("@name", "")
        if not cname:
            continue
        sources = a.get("Source", [])
        if isinstance(sources, dict):
            sources = [sources]
        if isinstance(sources, str):
            sources = [{"$": sources}]
        src_names = [s.get("$", s) if isinstance(s, dict) else str(s) for s in sources[:5]]
        items.append({"disease": cname, "sources": "; ".join(src_names)})

    return items


def extract_drug_pipeline(drugs_pipeline):
    """Extract drug pipeline from drugs_pipeline.json.

    Returns (total_count, list of {drug, company, phase, indications}).
    """
    if not drugs_pipeline or not isinstance(drugs_pipeline, dict):
        return 0, []

    results = drugs_pipeline.get("drugResultsOutput", {})
    total = safe_int(results.get("@totalResults", 0))
    drug_list = results.get("SearchResults", {}).get("Drug", [])
    if isinstance(drug_list, dict):
        drug_list = [drug_list]
    if not isinstance(drug_list, list):
        return total, []

    pipeline = []
    for d in drug_list:
        if not isinstance(d, dict):
            continue
        name = d.get("@name", "")
        if not name:
            continue
        phase = d.get("@phaseHighest", "-")

        co = d.get("CompanyOriginator", {})
        if isinstance(co, dict):
            company = co.get("@name", "")
        elif isinstance(co, list) and co:
            company = co[0].get("@name", "") if isinstance(co[0], dict) else ""
        else:
            company = ""

        inds = d.get("IndicationsPrimary", {}).get("Indication", [])
        if isinstance(inds, dict):
            inds = [inds]
        ind_names = "; ".join(
            i.get("@name", "") for i in inds[:3] if isinstance(i, dict) and i.get("@name")
        )

        pipeline.append({
            "drug": name,
            "company": company,
            "phase": phase,
            "indications": ind_names,
        })

    return total, pipeline


def extract_interactions(interactions):
    """Extract protein interactions from interactions.json.

    Returns list of {partner, direction, effect, mechanism}.
    """
    target = _unwrap_target(interactions)
    inter_list = target.get("Interactions", {}).get("Interaction", [])
    if isinstance(inter_list, dict):
        inter_list = [inter_list]
    if not isinstance(inter_list, list):
        return []

    items = []
    for i in inter_list:
        if not isinstance(i, dict):
            continue
        partner = i.get("CounterpartObject", {})
        if isinstance(partner, dict):
            partner = partner.get("$", "")
        elif not isinstance(partner, str):
            partner = ""
        if not partner:
            continue
        items.append({
            "partner": partner,
            "direction": i.get("Direction", "-"),
            "effect": i.get("Effect", "-"),
            "mechanism": i.get("Mechanism", "-"),
        })

    return items


def extract_pharmacology(pharmacology):
    """Extract pharmacology records from pharmacology.json.

    Returns list of {compound, assay, value, unit}.
    """
    if not pharmacology or not isinstance(pharmacology, dict):
        return []

    pharm_list = (
        pharmacology.get("drugDesignResultsOutput", {})
        .get("SearchResults", {})
        .get("PharmacologyRecord", [])
    )
    if isinstance(pharm_list, dict):
        pharm_list = [pharm_list]
    if not isinstance(pharm_list, list):
        return []

    items = []
    for p in pharm_list:
        if not isinstance(p, dict):
            continue
        compound = p.get("@drugName", "")
        if not compound:
            drug = p.get("Drug", {})
            compound = drug.get("@name", "") if isinstance(drug, dict) else ""
        assay = p.get("@assayType", "")
        if not assay:
            at = p.get("AssayType", {})
            assay = at.get("@name", "") if isinstance(at, dict) else str(at)
        value = p.get("@value", p.get("Value", "-"))
        unit = p.get("@unit", "")
        if not unit:
            u = p.get("Unit", {})
            unit = u.get("@name", "") if isinstance(u, dict) else str(u)
        items.append({"compound": compound, "assay": assay, "value": value, "unit": unit})

    return items


# ---------------------------------------------------------------------------
# Article compilation
# ---------------------------------------------------------------------------

def compile_target_article(target_dir, target_name, slug, base_dir=None):
    """Compile a full target profile article. Returns (meta, body)."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    record = read_json_safe(os.path.join(target_dir, "record.json"))
    condition_drugs = read_json_safe(os.path.join(target_dir, "condition_drugs.json"))
    condition_genes = read_json_safe(os.path.join(target_dir, "condition_genes.json"))
    interactions = read_json_safe(os.path.join(target_dir, "interactions.json"))
    drugs_pipeline = read_json_safe(os.path.join(target_dir, "drugs_pipeline.json"))
    pharmacology = read_json_safe(os.path.join(target_dir, "pharmacology.json"))

    overview = extract_target_overview(record)
    disease_associations = extract_disease_associations(condition_drugs)
    gene_assocs = extract_gene_associations(condition_genes)
    total_drugs, drug_pipeline = extract_drug_pipeline(drugs_pipeline)
    interaction_items = extract_interactions(interactions)
    pharm_items = extract_pharmacology(pharmacology)

    gene_symbol = overview.get("gene_symbol", "")
    family = overview.get("family", "")
    organism = overview.get("organism", "Human")
    display_name = overview.get("name") or target_name

    meta = {
        "title": display_name,
        "type": "target",
        "slug": slug,
        "compiled_at": now,
        "source_dir": target_dir,
        "gene_symbol": gene_symbol,
        "family": family,
        "organism": organism,
        "disease_count": len(disease_associations),
        "drug_count": total_drugs,
    }

    body_parts = []

    # Biology section
    body_parts.append("## Biology\n\n")
    bio_rows = []
    if overview.get("function"):
        bio_rows.append(("Function", overview["function"]))
    if overview.get("location"):
        bio_rows.append(("Subcellular Location", overview["location"]))
    if family:
        bio_rows.append(("Protein Family", family))
    if organism:
        bio_rows.append(("Organism", organism))
    if overview.get("synonyms"):
        bio_rows.append(("Synonyms", ", ".join(overview["synonyms"][:10])))

    if bio_rows:
        body_parts.append("| Field | Value |\n|---|---|\n")
        for field, value in bio_rows:
            body_parts.append(f"| {field} | {value} |\n")
        body_parts.append("\n")

    # Disease Associations — ALL rows, wikilink to indication articles
    if disease_associations:
        body_parts.append(f"## Disease Associations ({len(disease_associations)} diseases)\n\n")
        body_parts.append("| Disease | Total Drugs | Active | Highest Phase |\n|---|---|---|---|\n")
        for assoc in disease_associations:
            dis_slug = slugify(assoc["disease"])
            dis_link = wikilink(dis_slug, assoc["disease"])
            body_parts.append(
                f"| {dis_link}"
                f" | {assoc['drug_count']}"
                f" | {assoc['active_count']}"
                f" | {assoc['highest_phase']}"
                f" |\n"
            )
        body_parts.append("\n")

    # Genetic Evidence — ALL rows
    if gene_assocs:
        body_parts.append(f"## Genetic Evidence ({len(gene_assocs)} associations)\n\n")
        body_parts.append("| Disease | Evidence Sources |\n|---|---|\n")
        for item in gene_assocs:
            dis_slug = slugify(item["disease"])
            dis_link = wikilink(dis_slug, item["disease"])
            body_parts.append(f"| {dis_link} | {item['sources']} |\n")
        body_parts.append("\n")

    # Drug Pipeline — ALL rows, wikilink drugs + companies
    if drug_pipeline:
        body_parts.append(f"## Drug Pipeline ({total_drugs} total)\n\n")
        body_parts.append("| Drug | Company | Phase | Indications |\n|---|---|---|---|\n")
        for entry in drug_pipeline:
            drug_link = wikilink(slugify(normalize_drug_name(entry["drug"])), entry["drug"])
            comp = entry["company"]
            if comp:
                comp_slug = find_company_slug(comp, base_dir)
                comp_str = wikilink(comp_slug, normalize_company_name(comp))
            else:
                comp_str = "-"
            body_parts.append(
                f"| {drug_link}"
                f" | {comp_str}"
                f" | {entry['phase']}"
                f" | {entry['indications'] or '-'}"
                f" |\n"
            )
        body_parts.append("\n")

    # Protein Interactions — ALL rows, wikilink partners to target articles
    if interaction_items:
        body_parts.append(f"## Protein Interactions ({len(interaction_items)})\n\n")
        body_parts.append("| Partner | Direction | Effect | Mechanism |\n|---|---|---|---|\n")
        for item in interaction_items:
            partner = item["partner"]
            partner_link = wikilink(slugify(partner), partner)
            body_parts.append(
                f"| {partner_link}"
                f" | {item['direction']}"
                f" | {item['effect']}"
                f" | {item['mechanism']}"
                f" |\n"
            )
        body_parts.append("\n")

    # Pharmacology — ALL rows
    if pharm_items:
        body_parts.append(f"## Pharmacology ({len(pharm_items)} records)\n\n")
        body_parts.append("| Compound | Assay | Value | Unit |\n|---|---|---|---|\n")
        for item in pharm_items:
            body_parts.append(
                f"| {item['compound']}"
                f" | {item['assay']}"
                f" | {item['value']}"
                f" | {item['unit']}"
                f" |\n"
            )
        body_parts.append("\n")

    # Data Sources
    body_parts.append("## Data Sources\n\n")
    body_parts.append(f"- **Source directory:** `{target_dir}`\n")
    body_parts.append(f"- **Compiled at:** {now}\n")

    return meta, "".join(body_parts)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print("Usage: compile_target.py <target_dir> [target_name] [--wiki-dir DIR]", file=sys.stderr)
        sys.exit(1)

    target_dir = sys.argv[1]
    target_name = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else None

    # Parse --wiki-dir
    wiki_dir_override = None
    for i, arg in enumerate(sys.argv):
        if arg == "--wiki-dir" and i + 1 < len(sys.argv):
            wiki_dir_override = sys.argv[i + 1]

    if not os.path.isdir(target_dir):
        print(f"Error: target directory not found: {target_dir}", file=sys.stderr)
        sys.exit(1)

    if not target_name:
        target_name = os.path.basename(target_dir).replace("-", " ").upper()

    slug = slugify(target_name)
    base_dir = wiki_dir_override or os.getcwd()
    w_dir = wiki_root(base_dir)

    print(f"Compiling {target_name} target profile to wiki...")

    meta, body = compile_target_article(target_dir, target_name, slug, base_dir)
    path = article_path("targets", slug, base_dir)
    write_article(path, meta, body)
    print(f"  Written: {path}")

    entries = load_index_entries(w_dir)
    update_index(w_dir, entries)
    print(f"  Updated: {os.path.join(w_dir, 'INDEX.md')}")

    log_activity(w_dir, "compile", f"Target: {target_name}")
    print(f"Done. Wiki article compiled for {target_name}.")


if __name__ == "__main__":
    main()
