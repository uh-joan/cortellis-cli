#!/usr/bin/env python3
"""
compile_drug.py — Compile drug profile data into wiki article.

Reads drug profile JSON files and produces wiki/drugs/<slug>.md.

Usage: python3 compile_drug.py <drug_dir> [drug_name] [--wiki-dir DIR]
"""

import os
import sys
from datetime import datetime, timezone

# Allow running as standalone script
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))

from cli_anything.cortellis.utils.data_helpers import read_json_safe
from cli_anything.cortellis.utils.wiki import (
    slugify,
    wiki_root,
    article_path,
    load_index_entries,
    update_index,
    write_article,
    wikilink,
    log_activity,
)


# ---------------------------------------------------------------------------
# Data extraction
# ---------------------------------------------------------------------------

def extract_drug_overview(record):
    """Extract key fields from record.json."""
    rec = record.get("drugRecordOutput", record)

    name = rec.get("DrugName", rec.get("@name", "Unknown"))
    drug_id = rec.get("@id", "")

    phase = rec.get("PhaseHighest", {})
    if isinstance(phase, dict):
        phase = phase.get("$", "")

    # Originator / company
    originator = rec.get("CompanyOriginator", {})
    if isinstance(originator, dict):
        originator = originator.get("$", originator.get("@name", ""))

    # Indications
    indications_raw = rec.get("IndicationsPrimary", {}).get("Indication", [])
    if isinstance(indications_raw, dict):
        indications_raw = [indications_raw]
    indications = []
    for i in indications_raw:
        if isinstance(i, dict):
            indications.append(i.get("$", str(i)))
        else:
            indications.append(str(i))

    # Mechanism (primary actions)
    actions_raw = rec.get("ActionsPrimary", {}).get("Action", [])
    if isinstance(actions_raw, dict):
        actions_raw = [actions_raw]
    actions = []
    for a in actions_raw:
        if isinstance(a, dict):
            actions.append(a.get("$", str(a)))
        else:
            actions.append(str(a))
    mechanism = "; ".join(actions[:3]) if actions else ""

    # Technology
    techs_raw = rec.get("Technologies", {}).get("Technology", [])
    if isinstance(techs_raw, dict):
        techs_raw = [techs_raw]
    techs = []
    for t in techs_raw:
        if isinstance(t, dict):
            techs.append(t.get("$", str(t)))
        else:
            techs.append(str(t))
    technology = "; ".join(techs[:3]) if techs else ""

    # Therapy areas
    areas_raw = rec.get("TherapyAreas", {}).get("TherapyArea", [])
    if isinstance(areas_raw, str):
        areas_raw = [areas_raw]
    elif isinstance(areas_raw, dict):
        areas_raw = [areas_raw]
    therapy_areas = []
    for a in areas_raw:
        if isinstance(a, dict):
            therapy_areas.append(a.get("$", str(a)))
        else:
            therapy_areas.append(str(a))

    # Aliases: brand names + full formulation DrugName + research codes
    aliases = []
    # DrugName itself (full formulation name) is an alias if different from base INN
    if name:
        aliases.append(name)
    brand_names_raw = rec.get("DrugNamesKey", {}).get("Name", [])
    if isinstance(brand_names_raw, dict):
        brand_names_raw = [brand_names_raw]
    for n in brand_names_raw:
        val = n.get("$", "") if isinstance(n, dict) else str(n)
        if val and val not in aliases:
            aliases.append(val)
    synonyms_raw = rec.get("DrugSynonyms", {}).get("Name", [])
    if isinstance(synonyms_raw, dict):
        synonyms_raw = [synonyms_raw]
    for s in synonyms_raw:
        val = s.get("Value", "") if isinstance(s, dict) else str(s)
        if val and val not in aliases:
            aliases.append(val)

    # Targets from Targets.Target
    targets_raw = rec.get("Targets", {}).get("Target", [])
    if isinstance(targets_raw, dict):
        targets_raw = [targets_raw]
    targets = []
    for t in targets_raw:
        tname = t.get("Name", "") if isinstance(t, dict) else str(t)
        if tname and tname not in targets:
            targets.append(tname)

    return {
        "name": name,
        "id": drug_id,
        "phase": phase,
        "indications": indications,
        "mechanism": mechanism,
        "technology": technology,
        "originator": originator,
        "therapy_areas": therapy_areas,
        "aliases": aliases,
        "targets": targets,
    }


def extract_deals_summary(deals_json):
    """Extract count, types, and latest deal from deals.json."""
    if not deals_json:
        return {}
    deal_data = deals_json.get("dealResultsOutput", deals_json)
    total = deal_data.get("@totalResults", "0")
    deal_list = deal_data.get("SearchResults", {}).get("Deal", [])
    if isinstance(deal_list, dict):
        deal_list = [deal_list]
    types = {}
    for d in deal_list:
        dtype = d.get("Type", "Unknown")
        types[dtype] = types.get(dtype, 0) + 1
    latest = deal_list[0].get("StartDate", "")[:10] if deal_list else ""
    return {"total": total, "types": types, "latest": latest, "deals": deal_list}


def extract_trials_summary(trials_json):
    """Extract count, recruiting status, and phase distribution from trials.json."""
    if not trials_json:
        return {}
    trial_data = trials_json.get("trialResultsOutput", trials_json)
    total = trial_data.get("@totalResults", "0")
    trial_list = trial_data.get("SearchResults", {}).get("Trial", [])
    if isinstance(trial_list, dict):
        trial_list = [trial_list]
    recruiting = sum(
        1 for t in trial_list
        if "recruit" in str(t.get("RecruitmentStatus", "")).lower()
    )
    phases = {}
    for t in trial_list:
        p = t.get("Phase", "Unknown")
        phases[p] = phases.get(p, 0) + 1
    return {
        "total": total,
        "recruiting": recruiting,
        "phase_distribution": phases,
        "trials": trial_list,
    }


def extract_competitors(competitors_json):
    """Extract list of competitors from competitors.json."""
    if not competitors_json:
        return []
    comp_data = competitors_json.get("drugResultsOutput", competitors_json)
    comp_list = comp_data.get("SearchResults", {}).get("Drug", [])
    if isinstance(comp_list, dict):
        comp_list = [comp_list]
    result = []
    for c in comp_list:
        name = c.get("@name", c.get("DrugName", ""))
        phase = c.get("@phaseHighest", c.get("PhaseHighest", {}).get("$", ""))
        company = c.get("CompanyOriginator", "")
        if isinstance(company, dict):
            company = company.get("$", company.get("@name", ""))
        actions_raw = c.get("ActionsPrimary", {}).get("Action", [])
        if isinstance(actions_raw, dict):
            actions_raw = [actions_raw]
        actions = []
        for a in actions_raw:
            if isinstance(a, dict):
                actions.append(a.get("$", str(a)))
            else:
                actions.append(str(a))
        mechanism = "; ".join(actions[:2]) if actions else ""
        result.append({"name": name, "phase": phase, "mechanism": mechanism, "company": company})
    return result


# ---------------------------------------------------------------------------
# Article compiler
# ---------------------------------------------------------------------------

def compile_drug_article(drug_dir, drug_name, slug):
    """Compile all drug profile JSON files into (meta, body)."""
    record = read_json_safe(os.path.join(drug_dir, "record.json"))
    swot = read_json_safe(os.path.join(drug_dir, "swot.json"))
    financials = read_json_safe(os.path.join(drug_dir, "financials.json"))
    history = read_json_safe(os.path.join(drug_dir, "history.json"))
    deals_json = read_json_safe(os.path.join(drug_dir, "deals.json"))
    trials_json = read_json_safe(os.path.join(drug_dir, "trials.json"))
    competitors_json = read_json_safe(os.path.join(drug_dir, "competitors.json"))

    overview = extract_drug_overview(record) if record else {}
    name = overview.get("name") or drug_name
    phase = overview.get("phase", "")
    originator = overview.get("originator", "")
    mechanism = overview.get("mechanism", "")
    technology = overview.get("technology", "")
    indications = overview.get("indications", [])
    therapy_areas = overview.get("therapy_areas", [])
    aliases = overview.get("aliases", [])
    targets = overview.get("targets", [])

    deals_summary = extract_deals_summary(deals_json)
    trials_summary = extract_trials_summary(trials_json)
    competitors = extract_competitors(competitors_json)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Build related: originator slug + indication slugs
    related = []
    if originator:
        related.append(slugify(originator))
    for ind in indications[:5]:
        ind_slug = slugify(ind)
        if ind_slug not in related:
            related.append(ind_slug)

    # Frontmatter
    meta = {
        "title": name,
        "type": "drug",
        "slug": slug,
        "compiled_at": now,
        "source_dir": drug_dir,
        "phase": phase,
        "originator": originator,
        "mechanism": mechanism,
        "indication_count": len(indications),
        "indications": [slugify(i) for i in indications],
        "related": related,
    }
    # Aliases: Obsidian resolves any alias to this article
    # Includes brand names, research codes, and full Cortellis formulation names
    if aliases:
        # Remove the canonical slug/name from aliases to avoid redundancy
        clean_aliases = [a for a in aliases if slugify(a) != slug and a != name]
        if clean_aliases:
            meta["aliases"] = clean_aliases

    # ---------------------------------------------------------------------------
    # Body
    # ---------------------------------------------------------------------------
    body_parts = []

    # Overview table
    body_parts.append("## Overview\n\n")
    body_parts.append("| Field | Value |\n|---|---|\n")
    body_parts.append(f"| Phase | {phase} |\n")
    if mechanism:
        # Link individual mechanism/target terms to target articles
        mech_parts = [m.strip() for m in mechanism.split(";")]
        mech_links = "; ".join(
            wikilink(slugify(m), m) if m else m for m in mech_parts
        )
        body_parts.append(f"| Mechanism | {mech_links} |\n")
    else:
        body_parts.append(f"| Mechanism | - |\n")
    if technology:
        body_parts.append(f"| Technology | {technology} |\n")
    if originator:
        originator_link = wikilink(slugify(originator), originator)
        body_parts.append(f"| Originator | {originator_link} |\n")
    if indications:
        ind_links = "; ".join(
            wikilink(slugify(i), i) for i in indications[:10]
        )
        body_parts.append(f"| Indications | {ind_links} |\n")
    if therapy_areas:
        body_parts.append(f"| Therapy Areas | {'; '.join(therapy_areas[:5])} |\n")
    body_parts.append("\n")

    # Development History
    if history:
        changes = history.get("ChangeHistory", {}).get("Change", [])
        if isinstance(changes, dict):
            changes = [changes]
        milestones = []
        for c in changes:
            date = c.get("Date", "")[:10]
            reason = c.get("Reason", {})
            if isinstance(reason, dict):
                reason = reason.get("$", "")
            if reason == "Highest status change":
                fields = c.get("FieldsChanged", {}).get("Field", {})
                if isinstance(fields, dict):
                    new_val = fields.get("@newValue", "")
                    old_val = fields.get("@oldValue", "")
                    label = f"{old_val} → {new_val}" if old_val else new_val
                    milestones.append((date, label))
            elif reason == "Drug added":
                milestones.append((date, "Drug added"))
        if milestones:
            body_parts.append("## Development History\n\n")
            # Deduplicate by label, keep earliest occurrence
            seen = set()
            for date, label in milestones:
                if label not in seen:
                    seen.add(label)
                    body_parts.append(f"- **{date}**: {label}\n")
            body_parts.append("\n")

    # SWOT Analysis
    if swot and len(str(swot)) > 100:
        import re
        swot_data = swot.get("drugSwotsOutput", swot)
        swot_text = str(swot_data)
        swot_sections = []
        for section in ["Strengths", "Weaknesses", "Opportunities", "Threats"]:
            pattern = rf"<{section}>(.*?)</{section}>"
            match = re.search(pattern, swot_text, re.DOTALL | re.IGNORECASE)
            if match:
                content = re.sub(r"<[^>]+>", "", match.group(1)).strip()
                content = " ".join(content.split())
                if content:
                    swot_sections.append((section, content))
        if swot_sections:
            body_parts.append("## SWOT Analysis\n\n")
            for section, content in swot_sections:
                body_parts.append(f"### {section}\n\n{content}\n\n")

    # Competitive Landscape
    if competitors:
        body_parts.append("## Competitive Landscape\n\n")
        body_parts.append("| Drug | Phase | Mechanism | Company |\n|---|---|---|---|\n")
        for c in competitors:
            comp_link = wikilink(slugify(c["company"]), c["company"]) if c["company"] else "-"
            body_parts.append(
                f"| {c['name']} | {c['phase']} | {c['mechanism']} | {comp_link} |\n"
            )
        body_parts.append("\n")

    # Deals
    if deals_summary.get("deals"):
        deal_list = deals_summary["deals"]
        total = deals_summary.get("total", len(deal_list))
        body_parts.append(f"## Deals ({total} total)\n\n")
        body_parts.append("| Title | Partner | Type | Date |\n|---|---|---|---|\n")
        for d in deal_list[:10]:
            title = d.get("Title", "-")[:60]
            partner = d.get("CompanyPartner", "-")[:30]
            dtype = d.get("Type", "-")
            date = d.get("StartDate", "-")[:10]
            body_parts.append(f"| {title} | {partner} | {dtype} | {date} |\n")
        body_parts.append("\n")

    # Clinical Trials
    if trials_summary.get("trials"):
        trial_list = trials_summary["trials"]
        total = trials_summary.get("total", len(trial_list))
        body_parts.append(f"## Clinical Trials ({total} total)\n\n")
        body_parts.append("| Title | Phase | Status | Enrollment |\n|---|---|---|---|\n")
        for t in trial_list[:10]:
            title = t.get("TitleDisplay", t.get("Title", "-"))[:60]
            tphase = t.get("Phase", "-")
            status = t.get("RecruitmentStatus", "-")
            enroll = t.get("PatientCountEnrollment", "-")
            body_parts.append(f"| {title} | {tphase} | {status} | {enroll} |\n")
        body_parts.append("\n")

    # Data Sources
    body_parts.append("## Data Sources\n\n")
    body_parts.append(f"- **Source directory:** `{drug_dir}`\n")
    body_parts.append(f"- **Compiled at:** {now}\n")
    files_present = []
    for fname in ["record.json", "swot.json", "financials.json", "history.json",
                  "deals.json", "trials.json", "competitors.json"]:
        if os.path.exists(os.path.join(drug_dir, fname)):
            files_present.append(fname)
    if files_present:
        body_parts.append(f"- **Files:** {', '.join(files_present)}\n")

    return meta, "".join(body_parts)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print(
            "Usage: compile_drug.py <drug_dir> [drug_name] [--wiki-dir DIR]",
            file=sys.stderr,
        )
        sys.exit(1)

    drug_dir = sys.argv[1]

    drug_name = None
    wiki_dir_override = None

    i = 2
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == "--wiki-dir" and i + 1 < len(sys.argv):
            wiki_dir_override = sys.argv[i + 1]
            i += 2
        elif not arg.startswith("--"):
            drug_name = arg
            i += 1
        else:
            i += 1

    if not os.path.isdir(drug_dir):
        print(f"Error: drug directory not found: {drug_dir}", file=sys.stderr)
        sys.exit(1)

    if not drug_name:
        drug_name = os.path.basename(drug_dir.rstrip("/")).replace("-", " ").title()

    slug = slugify(drug_name)
    base_dir = wiki_dir_override or os.getcwd()
    w_dir = wiki_root(base_dir)

    print(f"Compiling {drug_name} drug profile to wiki...")

    meta, body = compile_drug_article(drug_dir, drug_name, slug)
    drug_art_path = article_path("drugs", slug, base_dir)

    write_article(drug_art_path, meta, body)
    print(f"  Written: {drug_art_path}")

    # Rebuild INDEX.md
    entries = load_index_entries(w_dir)
    update_index(w_dir, entries)
    print(f"  Updated: {os.path.join(w_dir, 'INDEX.md')}")

    log_activity(w_dir, "compile", f"Drug: {drug_name}")

    print(f"Done. Wiki article compiled for {drug_name}.")


if __name__ == "__main__":
    main()
