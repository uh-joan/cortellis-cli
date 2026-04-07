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
    wiki_root,
    article_path,
    write_article,
    load_index_entries,
    update_index,
    wikilink,
)


# ---------------------------------------------------------------------------
# Data extraction
# ---------------------------------------------------------------------------

def extract_target_overview(record):
    """Extract core fields from record.json.

    Returns dict with: name, gene_symbol, family, organism, function.
    record.json is the raw Cortellis targets record response.
    """
    if not record:
        return {}

    # Handle wrapped response (list or dict with 'targets' key)
    target = record
    if isinstance(record, dict):
        targets = record.get("targets") or record.get("data") or []
        if isinstance(targets, list) and targets:
            target = targets[0]
        elif isinstance(targets, dict):
            target = targets
    elif isinstance(record, list) and record:
        target = record[0]

    if not isinstance(target, dict):
        return {}

    name = (
        target.get("targetName")
        or target.get("name")
        or target.get("preferredName")
        or ""
    )
    gene_symbol = (
        target.get("geneSymbol")
        or target.get("gene_symbol")
        or target.get("geneId")
        or ""
    )
    family = (
        target.get("targetFamily")
        or target.get("family")
        or target.get("proteinFamily")
        or ""
    )
    organism = (
        target.get("organism")
        or target.get("species")
        or "Human"
    )
    function = (
        target.get("function")
        or target.get("biologicalFunction")
        or target.get("description")
        or ""
    )
    location = (
        target.get("subcellularLocation")
        or target.get("location")
        or ""
    )
    synonyms = target.get("synonyms") or target.get("aliases") or []
    if isinstance(synonyms, str):
        synonyms = [s.strip() for s in synonyms.split(",") if s.strip()]

    return {
        "name": name,
        "gene_symbol": gene_symbol,
        "family": family,
        "organism": organism,
        "function": function,
        "location": location,
        "synonyms": synonyms,
    }


def extract_disease_associations(condition_drugs):
    """Extract disease associations from condition_drugs.json.

    Returns list of {disease, drug_count, highest_phase}.
    """
    if not condition_drugs:
        return []

    # Handle wrapped response
    items = condition_drugs
    if isinstance(condition_drugs, dict):
        items = (
            condition_drugs.get("conditionDrugs")
            or condition_drugs.get("conditions")
            or condition_drugs.get("data")
            or []
        )
    if not isinstance(items, list):
        return []

    associations = []
    for item in items:
        if not isinstance(item, dict):
            continue
        disease = (
            item.get("conditionName")
            or item.get("condition")
            or item.get("disease")
            or item.get("name")
            or ""
        )
        drug_count = safe_int(
            item.get("drugCount")
            or item.get("drug_count")
            or item.get("totalDrugs")
            or len(item.get("drugs", []))
        )
        highest_phase = (
            item.get("highestPhase")
            or item.get("highest_phase")
            or item.get("phase")
            or "-"
        )
        if disease:
            associations.append({
                "disease": disease,
                "drug_count": drug_count,
                "highest_phase": highest_phase,
            })

    return associations


def extract_drug_pipeline(drugs_pipeline):
    """Extract drug pipeline from drugs_pipeline.json.

    Returns list of {drug, company, phase, indications}.
    """
    if not drugs_pipeline:
        return []

    # Handle wrapped response
    items = drugs_pipeline
    if isinstance(drugs_pipeline, dict):
        items = (
            drugs_pipeline.get("drugs")
            or drugs_pipeline.get("data")
            or drugs_pipeline.get("results")
            or []
        )
    if not isinstance(items, list):
        return []

    pipeline = []
    for item in items:
        if not isinstance(item, dict):
            continue
        drug = (
            item.get("drugName")
            or item.get("drug_name")
            or item.get("name")
            or ""
        )
        company = (
            item.get("company")
            or item.get("companyName")
            or item.get("originator")
            or ""
        )
        phase = (
            item.get("highestPhase")
            or item.get("phase")
            or item.get("developmentPhase")
            or "-"
        )
        indications = (
            item.get("indications")
            or item.get("indication")
            or item.get("conditions")
            or ""
        )
        if isinstance(indications, list):
            indications = "; ".join(str(i) for i in indications if i)
        if drug:
            pipeline.append({
                "drug": drug,
                "company": company,
                "phase": phase,
                "indications": indications,
            })

    return pipeline


# ---------------------------------------------------------------------------
# Article compilation
# ---------------------------------------------------------------------------

def compile_target_article(target_dir, target_name, slug):
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
    drug_pipeline = extract_drug_pipeline(drugs_pipeline)

    # Extract interactions list
    interaction_items = interactions
    if isinstance(interactions, dict):
        interaction_items = (
            interactions.get("interactions")
            or interactions.get("data")
            or interactions.get("results")
            or []
        )

    # Extract pharmacology records
    pharm_items = pharmacology
    if isinstance(pharmacology, dict):
        pharm_items = (
            pharmacology.get("pharmacology")
            or pharmacology.get("data")
            or pharmacology.get("results")
            or []
        )

    # Extract gene associations from condition_genes
    gene_items = condition_genes
    if isinstance(condition_genes, dict):
        gene_items = (
            condition_genes.get("conditionGenes")
            or condition_genes.get("genes")
            or condition_genes.get("data")
            or []
        )

    # Frontmatter
    gene_symbol = overview.get("gene_symbol", "")
    family = overview.get("family", "")
    organism = overview.get("organism", "Human")

    meta = {
        "title": target_name,
        "type": "target",
        "slug": slug,
        "compiled_at": now,
        "source_dir": target_dir,
        "gene_symbol": gene_symbol,
        "family": family,
        "organism": organism,
        "disease_count": len(disease_associations),
        "drug_count": len(drug_pipeline),
    }

    # Build body
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
        synonyms_str = ", ".join(overview["synonyms"][:10])
        bio_rows.append(("Synonyms", synonyms_str))

    if bio_rows:
        body_parts.append("| Field | Value |\n|---|---|\n")
        for field, value in bio_rows:
            body_parts.append(f"| {field} | {value} |\n")
        body_parts.append("\n")
    else:
        body_parts.append(f"Target: **{target_name}**")
        if gene_symbol:
            body_parts.append(f" ({gene_symbol})")
        body_parts.append("\n\n")

    # Disease Associations section
    if disease_associations:
        body_parts.append(f"## Disease Associations ({len(disease_associations)} diseases)\n\n")
        body_parts.append("| Disease | Drugs | Highest Phase |\n|---|---|---|\n")
        for assoc in disease_associations:
            dis_slug = slugify(assoc["disease"])
            dis_link = wikilink(dis_slug, assoc["disease"])
            body_parts.append(
                f"| {dis_link}"
                f" | {assoc['drug_count']}"
                f" | {assoc['highest_phase']}"
                f" |\n"
            )
        body_parts.append("\n")

    # Genetic Evidence section
    if gene_items and isinstance(gene_items, list) and gene_items:
        body_parts.append(f"## Genetic Evidence ({len(gene_items)} associations)\n\n")
        body_parts.append("| Disease | Gene | Evidence |\n|---|---|---|\n")
        for item in gene_items[:20]:
            if not isinstance(item, dict):
                continue
            disease = (
                item.get("conditionName")
                or item.get("condition")
                or item.get("disease")
                or "-"
            )
            gene = item.get("geneSymbol") or item.get("gene") or gene_symbol or "-"
            evidence = (
                item.get("evidence")
                or item.get("evidenceType")
                or item.get("associationType")
                or "-"
            )
            body_parts.append(f"| {disease} | {gene} | {evidence} |\n")
        body_parts.append("\n")

    # Drug Pipeline section
    if drug_pipeline:
        body_parts.append(f"## Drug Pipeline ({len(drug_pipeline)} drugs)\n\n")
        body_parts.append("| Drug | Company | Phase | Indications |\n|---|---|---|---|\n")
        for entry in drug_pipeline:
            drug_slug = slugify(entry["drug"])
            drug_link = wikilink(drug_slug, entry["drug"])
            comp = entry["company"]
            comp_str = wikilink(slugify(comp), comp) if comp else "-"
            body_parts.append(
                f"| {drug_link}"
                f" | {comp_str}"
                f" | {entry['phase']}"
                f" | {entry['indications'] or '-'}"
                f" |\n"
            )
        body_parts.append("\n")

    # Protein Interactions section
    if interaction_items and isinstance(interaction_items, list) and interaction_items:
        body_parts.append(f"## Protein Interactions ({len(interaction_items)})\n\n")
        body_parts.append("| Partner | Interaction Type |\n|---|---|\n")
        for item in interaction_items[:30]:
            if not isinstance(item, dict):
                continue
            partner = (
                item.get("partnerName")
                or item.get("partner")
                or item.get("interactorName")
                or item.get("targetName")
                or "-"
            )
            itype = (
                item.get("interactionType")
                or item.get("type")
                or item.get("relationship")
                or "-"
            )
            body_parts.append(f"| {partner} | {itype} |\n")
        body_parts.append("\n")

    # Pharmacology section
    if pharm_items and isinstance(pharm_items, list) and pharm_items:
        body_parts.append(f"## Pharmacology ({len(pharm_items)} records)\n\n")
        body_parts.append("| Compound | Assay | Value | Unit |\n|---|---|---|---|\n")
        for item in pharm_items[:20]:
            if not isinstance(item, dict):
                continue
            compound = (
                item.get("compoundName")
                or item.get("compound")
                or item.get("drugName")
                or item.get("name")
                or "-"
            )
            assay = (
                item.get("assayType")
                or item.get("assay")
                or item.get("parameter")
                or "-"
            )
            value = (
                item.get("value")
                or item.get("activityValue")
                or "-"
            )
            unit = (
                item.get("unit")
                or item.get("activityUnit")
                or "-"
            )
            body_parts.append(f"| {compound} | {assay} | {value} | {unit} |\n")
        body_parts.append("\n")

    # Data Sources section
    body_parts.append("## Data Sources\n\n")
    body_parts.append(f"- **Source directory:** `{target_dir}`\n")
    body_parts.append(f"- **Compiled at:** {now}\n")
    if record:
        body_parts.append("- **record.json:** Full target record from Cortellis Targets\n")
    if condition_drugs:
        body_parts.append("- **condition_drugs.json:** Disease-drug associations\n")
    if drugs_pipeline:
        body_parts.append("- **drugs_pipeline.json:** CI drug pipeline by mechanism\n")
    if pharmacology:
        body_parts.append("- **pharmacology.json:** Drug Design (SI) pharmacology data\n")

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

    # Derive target name from directory if not provided
    if not target_name:
        target_name = os.path.basename(target_dir).replace("-", " ").upper()

    slug = slugify(target_name)
    base_dir = wiki_dir_override or os.getcwd()
    w_dir = wiki_root(base_dir)

    print(f"Compiling {target_name} target profile to wiki...")

    # Compile target article
    meta, body = compile_target_article(target_dir, target_name, slug)
    path = article_path("targets", slug, base_dir)
    write_article(path, meta, body)
    print(f"  Written: {path}")

    # Rebuild INDEX.md
    entries = load_index_entries(w_dir)
    update_index(w_dir, entries)
    print(f"  Updated: {os.path.join(w_dir, 'INDEX.md')}")

    print(f"Done. Wiki article compiled for {target_name}.")


if __name__ == "__main__":
    main()
