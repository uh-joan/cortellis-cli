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

from cli_anything.cortellis.utils.data_helpers import read_json_safe, read_md_safe
from cli_anything.cortellis.utils.wiki import (
    find_company_slug,
    find_target_slug_for_mechanism,
    normalize_drug_name,
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



# ---------------------------------------------------------------------------
# Verification layer
# ---------------------------------------------------------------------------

_PHASE_RANK = {
    "preclinical": 0,
    "phase 1": 1, "phase1": 1, "phase i": 1,
    "phase 1/2": 1, "phase 1/phase 2": 1,
    "phase 2": 2, "phase2": 2, "phase ii": 2,
    "phase 2/3": 2, "phase 2/phase 3": 2,
    "phase 3": 3, "phase3": 3, "phase iii": 3,
    "phase 4": 4, "phase4": 4, "phase iv": 4,
    "launched": 5, "approved": 5, "marketed": 5, "registered": 5,
}

_CT_PHASE_RANK = {
    "EARLY_PHASE1": 0,
    "PHASE1": 1,
    "PHASE2": 2,
    "PHASE3": 3,
    "PHASE4": 4,
}


def _cortellis_phase_rank(phase: str) -> int:
    """Map Cortellis phase string to numeric rank. Returns -1 if unrecognised."""
    return _PHASE_RANK.get((phase or "").lower().strip(), -1)


def _fda_has_approval(fda_approvals: dict) -> tuple[bool, str]:
    """Return (has_approval, brand_name) if FDA has any AP submission."""
    for entry in (fda_approvals or {}).get("results", []):
        for sub in entry.get("submissions", []):
            if sub.get("submission_status", "").upper() == "AP":
                brand = ""
                products = entry.get("products", [])
                if products:
                    brand = products[0].get("brand_name", "")
                return True, brand
    return False, ""


def _ct_highest_phase(ct_trials_json: dict) -> int:
    """Return highest phase rank found across CT.gov active trials."""
    trials = (ct_trials_json or {}).get("trials", [])
    highest = -1
    for t in trials:
        rank = _CT_PHASE_RANK.get(t.get("phase", ""), -1)
        if rank > highest:
            highest = rank
    return highest


def verify_claims(phase: str, fda_approvals: dict, ct_trials_json: dict,
                  trials_json: dict) -> dict:
    """Cross-check Cortellis claims against FDA and ClinicalTrials.gov.

    Returns:
        {verified: bool, verified_at: str, conflicts: list of dicts}

    Checks:
      1. Cortellis says Launched → FDA must have ≥1 AP approval.
      2. FDA has AP approval → Cortellis must say Launched (stale phase detection).
      3. CT.gov highest trial phase > Cortellis phase (Cortellis may be behind).
      4. Cortellis has >10 trials → CT.gov should show some active.
      5. CT.gov has >20 active trials → Cortellis should show >0.
    Only runs checks when the required data files exist.
    """
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    conflicts = []
    phase_rank = _cortellis_phase_rank(phase)
    is_launched = phase_rank >= 5

    if fda_approvals is not None:
        fda_count = len(fda_approvals.get("results", []))
        fda_approved, fda_brand = _fda_has_approval(fda_approvals)

        # Check 1: Launched in Cortellis but no FDA record
        if is_launched and fda_count == 0:
            conflicts.append({
                "field": "approval_status",
                "cortellis": phase,
                "external": "no FDA NDA/BLA records found",
                "source": "api.fda.gov",
                "note": "Drug is Launched in Cortellis but no FDA approval records returned — may be foreign-origin or branded differently",
            })

        # Check 2: FDA has approval but Cortellis phase is not Launched (stale data)
        if fda_approved and not is_launched:
            brand_note = f" ({fda_brand})" if fda_brand else ""
            conflicts.append({
                "field": "approval_status",
                "cortellis": phase,
                "external": f"FDA NDA/BLA approved{brand_note}",
                "source": "api.fda.gov",
                "note": f"FDA has an approved application{brand_note} but Cortellis shows phase '{phase}' — Cortellis record may be stale or drug approved under a different INN",
            })

    # Check 3: CT.gov highest phase > Cortellis phase (>1 step gap = likely stale)
    if ct_trials_json is not None and phase_rank >= 0:
        ct_highest = _ct_highest_phase(ct_trials_json)
        if ct_highest > phase_rank + 1:
            ct_phase_label = {0: "Early Phase 1", 1: "Phase 1", 2: "Phase 2", 3: "Phase 3", 4: "Phase 4"}.get(ct_highest, str(ct_highest))
            conflicts.append({
                "field": "development_phase",
                "cortellis": phase,
                "external": f"active {ct_phase_label} trials on CT.gov",
                "source": "clinicaltrials.gov",
                "note": f"CT.gov has active {ct_phase_label} trials but Cortellis shows '{phase}' — Cortellis phase may be outdated",
            })

    # Check 4: Cortellis has trials → CT.gov should see some active
    cortellis_trial_count = 0
    if trials_json:
        trial_data = trials_json.get("trialResultsOutput", trials_json)
        try:
            cortellis_trial_count = int(trial_data.get("@totalResults", 0))
        except (ValueError, TypeError):
            cortellis_trial_count = 0

    if ct_trials_json is not None:
        ct_count = ct_trials_json.get("ct_trial_count", 0)
        if cortellis_trial_count > 10 and ct_count == 0:
            conflicts.append({
                "field": "active_trial_count",
                "cortellis": cortellis_trial_count,
                "external": 0,
                "source": "clinicaltrials.gov",
                "note": "Cortellis reports trials but CT.gov shows 0 recruiting/active — trials may be completed or search term mismatch",
            })
        # Check 5: CT.gov sees many active trials but Cortellis has none
        if ct_count > 20 and cortellis_trial_count == 0:
            conflicts.append({
                "field": "active_trial_count",
                "cortellis": 0,
                "external": ct_count,
                "source": "clinicaltrials.gov",
                "note": "CT.gov shows active trials not reflected in Cortellis — may be post-launch studies or indication expansions",
            })

    verified = len(conflicts) == 0
    return {"verified": verified, "verified_at": now, "conflicts": conflicts}


# ---------------------------------------------------------------------------
# Article compiler
# ---------------------------------------------------------------------------

def compile_drug_article(drug_dir, drug_name, slug, base_dir=None):
    """Compile all drug profile JSON files into (meta, body)."""
    record = read_json_safe(os.path.join(drug_dir, "record.json"))
    swot = read_json_safe(os.path.join(drug_dir, "swot.json"))
    financials = read_json_safe(os.path.join(drug_dir, "financials.json"))
    history = read_json_safe(os.path.join(drug_dir, "history.json"))
    deals_json = read_json_safe(os.path.join(drug_dir, "deals.json"))
    trials_json = read_json_safe(os.path.join(drug_dir, "trials.json"))
    overview = extract_drug_overview(record) if record else {}
    name = overview.get("name") or drug_name
    # Recompute canonical slug from normalized INN name (not directory name)
    canonical_name = normalize_drug_name(name)
    if canonical_name:
        slug = slugify(canonical_name)
    phase = overview.get("phase", "")
    originator = overview.get("originator", "")
    mechanism = overview.get("mechanism", "")
    technology = overview.get("technology", "")
    indications = overview.get("indications", [])
    therapy_areas = overview.get("therapy_areas", [])
    aliases = overview.get("aliases", [])
    targets = overview.get("targets", [])

    literature = read_json_safe(os.path.join(drug_dir, "literature.json"))
    fda_approvals = read_json_safe(os.path.join(drug_dir, "fda_approvals.json"))
    ct_trials_json = read_json_safe(os.path.join(drug_dir, "ct_trials.json"))
    deals_summary = extract_deals_summary(deals_json)
    trials_summary = extract_trials_summary(trials_json)
    publications = extract_publications(literature) if literature else []
    fda_approval_count = len(fda_approvals.get("results", [])) if fda_approvals else 0
    ct_trial_count = ct_trials_json.get("ct_trial_count", 0) if ct_trials_json else 0
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Cross-check verification (only when external enrich files exist)
    verification = verify_claims(phase, fda_approvals, ct_trials_json, trials_json)

    # Build related: originator slug + indication slugs
    related = []
    if originator:
        related.append(find_company_slug(originator, base_dir))
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
        "fda_approval_count": fda_approval_count,
        "ct_trial_count": ct_trial_count,
        "verified": verification["verified"],
        "verified_at": verification["verified_at"],
        "conflicts": verification["conflicts"],
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
            wikilink(find_target_slug_for_mechanism(m, base_dir) or slugify(m), m) if m else m for m in mech_parts
        )
        body_parts.append(f"| Mechanism | {mech_links} |\n")
    else:
        body_parts.append(f"| Mechanism | - |\n")
    if technology:
        body_parts.append(f"| Technology | {technology} |\n")
    if originator:
        originator_link = wikilink(find_company_slug(originator, base_dir), originator)
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
        for t in trial_list:
            title = t.get("TitleDisplay", t.get("Title", "-"))[:60]
            tphase = t.get("Phase", "-")
            status = t.get("RecruitmentStatus", "-")
            enroll = t.get("PatientCountEnrollment", "-")
            body_parts.append(f"| {title} | {tphase} | {status} | {enroll} |\n")
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

    # Active Trials (ClinicalTrials.gov)
    ct_trials_md = read_md_safe(os.path.join(drug_dir, "ct_trials_summary.md"))
    if ct_trials_md:
        body_parts.append("## Active Trials (ClinicalTrials.gov)\n\n")
        for line in ct_trials_md.splitlines():
            if line.startswith("## ClinicalTrials.gov:"):
                continue
            body_parts.append(line + "\n")
        body_parts.append("\n")

    # Regulatory Timeline (from enrich_regulatory_milestones.py)
    reg_timeline_md = read_md_safe(os.path.join(drug_dir, "regulatory_timeline.md"))
    if reg_timeline_md:
        body_parts.append(reg_timeline_md)
        body_parts.append("\n")

    # FDA Approvals (from enrich_fda_approval.py)
    fda_summary_md = read_md_safe(os.path.join(drug_dir, "fda_summary.md"))
    if fda_summary_md:
        body_parts.append(fda_summary_md)
        body_parts.append("\n")

    # FDA Safety: adverse reactions, boxed warnings, recalls, shortages
    fda_safety_md = read_md_safe(os.path.join(drug_dir, "fda_safety.md"))
    if fda_safety_md:
        body_parts.append(fda_safety_md)
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

    meta, body = compile_drug_article(drug_dir, drug_name, slug, base_dir)
    slug = meta.get("slug", slug)  # use canonical slug from record (may differ from dir name)
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
