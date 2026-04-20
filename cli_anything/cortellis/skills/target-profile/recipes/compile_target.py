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

from cli_anything.cortellis.utils.data_helpers import read_json_safe, read_md_safe, safe_int
from cli_anything.cortellis.utils.wiki import (
    slugify,
    normalize_company_name,
    normalize_drug_name,
    find_company_slug,
    find_indication_slug_for_disease,
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
    _cda = target.get("ConditionDrugAssociations", {})
    if not isinstance(_cda, dict):
        _cda = {}
    conditions = _cda.get("Condition", [])
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
    _cga = target.get("ConditionGeneAssociations", {})
    if not isinstance(_cga, dict):
        _cga = {}
    gene_assocs = _cga.get("Condition", [])
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
    _inter = target.get("Interactions", {})
    if not isinstance(_inter, dict):
        _inter = {}
    inter_list = _inter.get("Interaction", [])
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


def extract_patents(patents):
    """Extract patent records from patents.json.

    Handles actual API response shape: patentRecordsOutput.Patent[]
    Returns list of {patent_id, title, assignee, filing_date, status}.
    """
    if not patents or not isinstance(patents, dict):
        return []

    # Actual shape: {"patentRecordsOutput": {"Patent": [...]}}
    _pro = patents.get("patentRecordsOutput", {})
    if not isinstance(_pro, dict):
        _pro = {}
    pat_list = _pro.get("Patent", [])
    if not pat_list:
        # Legacy fallback via target unwrap
        target = _unwrap_target(patents)
        pat_list = target.get("Patents", {}).get("Patent", [])
    if isinstance(pat_list, dict):
        pat_list = [pat_list]
    if not isinstance(pat_list, list):
        return []

    items = []
    for p in pat_list:
        if not isinstance(p, dict):
            continue
        patent_id = p.get("@id", p.get("@patentNumber", ""))
        title = p.get("Title", p.get("@title", ""))
        if isinstance(title, dict):
            title = title.get("$", "")
        assignee = p.get("Assignee", p.get("@assignee", ""))
        if isinstance(assignee, dict):
            assignee = assignee.get("$", assignee.get("@name", ""))
        filing_date = p.get("@filingDate", p.get("FilingDate", ""))
        if isinstance(filing_date, dict):
            filing_date = filing_date.get("$", "")
        status = p.get("@status", p.get("Status", ""))
        if isinstance(status, dict):
            status = status.get("$", "")
        items.append({
            "patent_id": str(patent_id)[:30] if patent_id else "",
            "title": str(title)[:80] if title else "",
            "assignee": str(assignee)[:40] if assignee else "",
            "filing_date": str(filing_date)[:10] if filing_date else "",
            "status": str(status)[:20] if status else "",
        })

    return items


def extract_references(references):
    """Extract reference records from references.json.

    Handles actual API response shape: ReferenceRecordsOutput.Reference[]
    Fields: title (str), authors (semicolon-sep str), source.$ (journal), year (int)
    Returns list of {title, authors, journal, year}.
    """
    if not references or not isinstance(references, dict):
        return []

    # Actual shape: {"ReferenceRecordsOutput": {"Reference": [...]}}
    ref_list = references.get("ReferenceRecordsOutput", {}).get("Reference", [])
    if not ref_list:
        # Legacy fallback
        target = _unwrap_target(references)
        ref_list = target.get("References", {}).get("Reference", [])
    if isinstance(ref_list, dict):
        ref_list = [ref_list]
    if not isinstance(ref_list, list):
        return []

    items = []
    for r in ref_list:
        if not isinstance(r, dict):
            continue
        # Actual fields are lowercase
        title = r.get("title", r.get("Title", r.get("@title", "")))
        if isinstance(title, dict):
            title = title.get("$", "")
        # authors is a semicolon-separated string in the API response
        authors_raw = r.get("authors", r.get("Authors", r.get("Author", "")))
        if isinstance(authors_raw, list):
            authors = "; ".join(
                a.get("$", a.get("@name", str(a))) if isinstance(a, dict) else str(a)
                for a in authors_raw[:3]
            )
            if len(authors_raw) > 3:
                authors += " et al"
        elif isinstance(authors_raw, dict):
            authors = authors_raw.get("$", authors_raw.get("@name", ""))
        else:
            authors = str(authors_raw) if authors_raw else ""
        # journal: source.$ in actual response
        journal_raw = r.get("source", r.get("Journal", r.get("@journal", "")))
        if isinstance(journal_raw, dict):
            journal = journal_raw.get("$", journal_raw.get("@name", ""))
        else:
            journal = str(journal_raw) if journal_raw else ""
        year = r.get("year", r.get("@year", r.get("Year", "")))
        if isinstance(year, dict):
            year = year.get("$", "")
        items.append({
            "title": str(title)[:100] if title else "",
            "authors": str(authors)[:60] if authors else "",
            "journal": str(journal)[:50] if journal else "",
            "year": str(year)[:4] if year else "",
        })

    return items


def extract_publications(literature_data):
    """Extract publication records from literature API response.

    Returns list of {title, authors, journal, date, abstract_excerpt}.
    """
    if not literature_data or not isinstance(literature_data, dict):
        return []

    hits = (
        literature_data.get("literatureResultsOutput", {})
        .get("SearchResults", {})
        .get("Literature", [])
    )
    if isinstance(hits, dict):
        hits = [hits]
    if not isinstance(hits, list):
        return []

    pubs = []
    for record in hits:
        if not isinstance(record, dict):
            continue

        title = str(record.get("Title") or "").strip()

        authors_raw = record.get("Authors", {})
        if isinstance(authors_raw, dict):
            authors_raw = authors_raw.get("Author", [])
        if isinstance(authors_raw, str):
            authors_raw = [authors_raw]
        if not isinstance(authors_raw, list):
            authors_raw = []
        if authors_raw:
            first = str(authors_raw[0]).strip()
            authors = f"{first} et al" if len(authors_raw) > 1 else first
        else:
            authors = ""

        journal = str(record.get("PublicationName") or "").strip()

        date = str(record.get("IssueDate") or record.get("PublicationYear") or "").strip()
        if len(date) > 7 and "T" in date:
            date = date[:10]
        elif len(date) > 7 and "-" in date:
            date = date[:7]

        abstract_raw = str(record.get("Teaser") or "").strip()
        abstract_excerpt = abstract_raw[:200] + ("..." if len(abstract_raw) > 200 else "")

        if title:
            pubs.append({
                "title": title,
                "authors": authors,
                "journal": journal,
                "date": date,
                "abstract_excerpt": abstract_excerpt,
            })

    return pubs


# ---------------------------------------------------------------------------
# Verification layer
# ---------------------------------------------------------------------------

def verify_claims_target(target_name: str, total_drugs: int, disease_associations: list,
                         publication_count: int) -> dict:
    """Cross-check Cortellis target claims against ClinicalTrials.gov.

    Checks:
      1. If Cortellis reports >10 drugs for this target, CT.gov should have active trials.
      2. If publication_count == 0 and total_drugs > 5, flag PubMed enrichment needed.
    Only runs CT.gov check if clinicaltrials module is available (graceful skip on network error).

    Returns:
        {verified: bool, verified_at: str, conflicts: list of dicts}
    """
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    conflicts = []

    # Check 1: Active drugs → CT.gov should show trials
    if total_drugs > 10:
        try:
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))
            from cli_anything.cortellis.core import clinicaltrials
            ct_count = clinicaltrials.count_trials(target_name)
            if ct_count == 0:
                conflicts.append({
                    "field": "active_trial_count",
                    "cortellis": total_drugs,
                    "external": 0,
                    "source": "clinicaltrials.gov",
                    "note": f"Cortellis reports {total_drugs} drugs for {target_name} but CT.gov shows 0 trials — target name may differ in registry",
                })
        except Exception:
            pass  # Skip check if network unavailable

    # Check 2: Well-targeted drug with no publications
    if publication_count == 0 and total_drugs > 5:
        conflicts.append({
            "field": "publication_count",
            "cortellis": 0,
            "external": "unknown",
            "source": "cortellis-literature",
            "note": f"{total_drugs} drugs target this protein but 0 publications found — consider running PubMed enrichment",
        })

    verified = len(conflicts) == 0
    return {"verified": verified, "verified_at": now, "conflicts": conflicts}


# ---------------------------------------------------------------------------
# Article compilation
# ---------------------------------------------------------------------------

def compile_target_article(target_dir, target_name, slug, base_dir=None):
    """Compile a full target profile article. Returns (meta, body)."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    record = read_json_safe(os.path.join(target_dir, "record.json"))
    synonyms_data = read_json_safe(os.path.join(target_dir, "synonyms.json"))
    condition_drugs = read_json_safe(os.path.join(target_dir, "condition_drugs.json"))
    condition_genes = read_json_safe(os.path.join(target_dir, "condition_genes.json"))
    interactions = read_json_safe(os.path.join(target_dir, "interactions.json"))
    drugs_pipeline = read_json_safe(os.path.join(target_dir, "drugs_pipeline.json"))
    pharmacology = read_json_safe(os.path.join(target_dir, "pharmacology.json"))
    literature = read_json_safe(os.path.join(target_dir, "literature.json"))
    patents_data = read_json_safe(os.path.join(target_dir, "patents.json"))
    references_data = read_json_safe(os.path.join(target_dir, "references.json"))

    overview = extract_target_overview(record)
    disease_associations = extract_disease_associations(condition_drugs)
    gene_assocs = extract_gene_associations(condition_genes)
    total_drugs, drug_pipeline = extract_drug_pipeline(drugs_pipeline)
    interaction_items = extract_interactions(interactions)
    pharm_items = extract_pharmacology(pharmacology)
    publications = extract_publications(literature) if literature else []
    patent_items = extract_patents(patents_data)
    reference_items = extract_references(references_data)

    gene_symbol = overview.get("gene_symbol", "")
    family = overview.get("family", "")
    organism = overview.get("organism", "Human")
    display_name = overview.get("name") or target_name

    verification = verify_claims_target(
        target_name=display_name,
        total_drugs=total_drugs,
        disease_associations=disease_associations,
        publication_count=len(publications),
    )

    target_aliases = (synonyms_data or {}).get("synonyms", [])

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
        "publication_count": len(publications),
        "patent_count": len(patent_items),
        "reference_count": len(reference_items),
        "verified": verification["verified"],
        "verified_at": verification["verified_at"],
        "conflicts": verification["conflicts"],
        **({"aliases": target_aliases} if target_aliases else {}),
    }

    # Cross-profile links: indications + drugs + companies that hit this target
    indication_slugs = [slugify(d["disease"]) for d in disease_associations[:10] if d.get("disease")]
    drug_slugs = list(dict.fromkeys(
        slugify(normalize_drug_name(d["drug"])) for d in drug_pipeline[:20] if d.get("drug")
    ))
    company_slugs = list(dict.fromkeys(filter(None, (
        find_company_slug(d["company"], base_dir) for d in drug_pipeline[:20] if d.get("company")
    ))))
    if indication_slugs:
        meta["indications"] = indication_slugs
    related = list(dict.fromkeys(indication_slugs + drug_slugs + company_slugs))
    if related:
        meta["related"] = related

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
            dis_slug = find_indication_slug_for_disease(assoc["disease"], base_dir)
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
            dis_slug = find_indication_slug_for_disease(item["disease"], base_dir)
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

    # IP Landscape (patents)
    if patent_items:
        body_parts.append(f"## IP Landscape ({len(patent_items)} patents)\n\n")
        body_parts.append("| Patent ID | Title | Assignee | Date | Status |\n|---|---|---|---|---|\n")
        for item in patent_items:
            body_parts.append(
                f"| {item['patent_id']}"
                f" | {item['title']}"
                f" | {item['assignee']}"
                f" | {item['filing_date']}"
                f" | {item['status']}"
                f" |\n"
            )
        body_parts.append("\n")

    # Literature References
    if reference_items:
        body_parts.append(f"## Literature References ({len(reference_items)})\n\n")
        body_parts.append("| Title | Authors | Journal | Year |\n|---|---|---|---|\n")
        for item in reference_items:
            body_parts.append(
                f"| {item['title']}"
                f" | {item['authors']}"
                f" | {item['journal']}"
                f" | {item['year']}"
                f" |\n"
            )
        body_parts.append("\n")

    # Recent Publications
    if publications:
        body_parts.append(f"## Recent Publications ({len(publications)})\n\n")
        body_parts.append("| Title | Authors | Journal | Date |\n|---|---|---|---|\n")
        for pub in publications:
            title = pub.get("title", "")
            if len(title) > 80:
                title = title[:77] + "..."
            authors = pub.get("authors", "")
            journal = pub.get("journal", "")
            date = pub.get("date", "")
            body_parts.append(f"| {title} | {authors} | {journal} | {date} |\n")
        body_parts.append("\n")

    # UniProt + AlphaFold (from enrich_target_uniprot.py)
    uniprot_md = read_md_safe(os.path.join(target_dir, "uniprot_summary.md"))
    if uniprot_md:
        body_parts.append(uniprot_md)
        body_parts.append("\n")

    # Open Targets (from enrich_target_opentargets.py)
    opentargets_md = read_md_safe(os.path.join(target_dir, "opentargets_summary.md"))
    if opentargets_md:
        body_parts.append(opentargets_md)
        body_parts.append("\n")

    # ChEMBL binding affinity (from enrich_target_chembl.py)
    chembl_target_md = read_md_safe(os.path.join(target_dir, "chembl_target_summary.md"))
    if chembl_target_md:
        body_parts.append(chembl_target_md)
        body_parts.append("\n")

    # Pharmacogenomics (from enrich_target_cpic.py)
    cpic_gene_md = read_md_safe(os.path.join(target_dir, "cpic_gene_summary.md"))
    if cpic_gene_md:
        body_parts.append(cpic_gene_md)
        body_parts.append("\n")

    # Active Trials (ClinicalTrials.gov)
    ct_trials_md = read_md_safe(os.path.join(target_dir, "ct_trials_summary.md"))
    if ct_trials_md:
        body_parts.append("## Active Trials (ClinicalTrials.gov)\n\n")
        for line in ct_trials_md.splitlines():
            if line.startswith("## ClinicalTrials.gov:"):
                continue
            body_parts.append(line + "\n")
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

    # Canonical slug = directory basename (set once from $TARGET_SLUG in SKILL.md).
    # This prevents duplicate articles when the same target is compiled with different
    # name spellings (e.g., "Dipeptidyl peptidase 4" vs "DPP-4" → both → dpp-4.md).
    dir_slug = os.path.basename(target_dir.rstrip("/\\"))
    slug = dir_slug if dir_slug else slugify(target_name)

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

    from cli_anything.cortellis.core.graph_utils import refresh_graph
    refresh_graph(base_dir)

    print(f"Done. Wiki article compiled for {target_name}.")


if __name__ == "__main__":
    main()
