#!/usr/bin/env python3
"""
drug_comparison_generator.py — Generate side-by-side drug comparison.

Reads drug records, trial data, and deal data from a comparison directory
and produces a formatted comparison markdown.

Usage: python3 drug_comparison_generator.py <comparison_dir>
"""

import json
import os
import sys
from typing import Any


def discover_drugs(directory: str) -> list[int]:
    """Scan for drug_N.json files, return sorted list of indices."""
    indices = []
    for fname in os.listdir(directory):
        if fname.startswith("drug_") and fname.endswith(".json"):
            stem = fname[len("drug_") : -len(".json")]
            if stem.isdigit():
                indices.append(int(stem))
    return sorted(indices)


def _safe_get(obj: Any, *keys: str, default: Any = None) -> Any:
    """Traverse nested dicts/lists safely."""
    current = obj
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key, default)
        elif isinstance(current, list) and key == "0":
            current = current[0] if current else default
        else:
            return default
        if current is None:
            return default
    return current


def extract_drug_profile(record: dict) -> dict:
    """Extract key fields from a Cortellis drug record.

    Handles the nested JSON structure defensively — missing fields return None.
    """
    # Top-level drug data may be nested under a 'drug' key or at root
    drug = record.get("drug", record)

    name = (
        drug.get("drugNameDisplay")
        or drug.get("drugName")
        or drug.get("name")
        or "Unknown"
    )

    phase = (
        drug.get("highestPhaseDisplay")
        or drug.get("highestPhase")
        or drug.get("phase")
        or "Unknown"
    )

    # Indications: may be a list or a count field
    indications_raw = drug.get("indications") or drug.get("indicationList") or []
    if isinstance(indications_raw, list):
        indications = [
            ind.get("indicationDisplay") or ind.get("indication") or str(ind)
            for ind in indications_raw
            if isinstance(ind, dict)
        ]
        if not indications and indications_raw:
            indications = [str(i) for i in indications_raw]
    else:
        indications = []

    indication_count = drug.get("indicationCount") or len(indications) or 0

    # Mechanism / action
    mechanism = (
        _safe_get(drug, "actions", "0", "actionDisplay")
        or _safe_get(drug, "actions", "0", "action")
        or drug.get("actionDisplay")
        or drug.get("primaryAction")
        or "Unknown"
    )
    if isinstance(drug.get("actions"), list) and drug["actions"]:
        first = drug["actions"][0]
        if isinstance(first, dict):
            mechanism = first.get("actionDisplay") or first.get("action") or mechanism

    # Technology / modality
    technology = (
        _safe_get(drug, "technologies", "0", "technologyDisplay")
        or _safe_get(drug, "technologies", "0", "technology")
        or drug.get("technologyDisplay")
        or drug.get("technology")
        or "Unknown"
    )
    if isinstance(drug.get("technologies"), list) and drug["technologies"]:
        first = drug["technologies"][0]
        if isinstance(first, dict):
            technology = (
                first.get("technologyDisplay") or first.get("technology") or technology
            )

    # Company / originator
    company = (
        _safe_get(drug, "originators", "0", "companyNameDisplay")
        or _safe_get(drug, "originators", "0", "companyName")
        or drug.get("originatorDisplay")
        or drug.get("originator")
        or "Unknown"
    )
    if isinstance(drug.get("originators"), list) and drug["originators"]:
        first = drug["originators"][0]
        if isinstance(first, dict):
            company = (
                first.get("companyNameDisplay")
                or first.get("companyName")
                or company
            )

    return {
        "name": name,
        "phase": phase,
        "indications": indications,
        "indication_count": indication_count,
        "mechanism": mechanism,
        "technology": technology,
        "company": company,
    }


def extract_trial_summary(trials_json: dict) -> dict:
    """Extract trial counts from a Cortellis trials search result."""
    hits = (
        trials_json.get("hits")
        or trials_json.get("trials")
        or trials_json.get("results")
        or []
    )
    if not isinstance(hits, list):
        hits = []

    total = trials_json.get("totalResults") or trials_json.get("total") or len(hits)

    recruiting = sum(
        1
        for t in hits
        if isinstance(t, dict)
        and str(
            t.get("trialStatusDisplay") or t.get("trialStatus") or t.get("status") or ""
        ).lower()
        in ("recruiting", "enrolling")
    )

    phase3 = sum(
        1
        for t in hits
        if isinstance(t, dict)
        and "3" in str(t.get("trialPhaseDisplay") or t.get("trialPhase") or t.get("phase") or "")
    )

    return {
        "total": total,
        "recruiting": recruiting,
        "phase3": phase3,
    }


def extract_deal_summary(deals_json: dict) -> dict:
    """Extract deal counts and metadata from a Cortellis deals search result."""
    hits = (
        deals_json.get("hits")
        or deals_json.get("deals")
        or deals_json.get("results")
        or []
    )
    if not isinstance(hits, list):
        hits = []

    total = deals_json.get("totalResults") or deals_json.get("total") or len(hits)

    # Latest deal date
    dates = []
    for d in hits:
        if not isinstance(d, dict):
            continue
        date = d.get("dealDateStartDisplay") or d.get("dealDateStart") or d.get("date")
        if date:
            dates.append(str(date))
    latest_date = sorted(dates, reverse=True)[0] if dates else None

    # Deal types
    types_seen: set[str] = set()
    for d in hits:
        if not isinstance(d, dict):
            continue
        dtype = d.get("dealTypeDisplay") or d.get("dealType") or d.get("type")
        if dtype:
            types_seen.add(str(dtype))
    deal_types = "; ".join(sorted(types_seen)) if types_seen else None

    return {
        "total": total,
        "latest_date": latest_date,
        "deal_types": deal_types,
    }


def identify_differentiators(profiles: list[dict]) -> list[str]:
    """Compare profiles and generate bullet points for meaningful differences."""
    bullets = []
    if len(profiles) < 2:
        return bullets

    names = [p["name"] for p in profiles]

    # Phase differences
    phases = [p["phase"] for p in profiles]
    unique_phases = set(phases)
    if len(unique_phases) > 1:
        phase_parts = " vs ".join(f"{n} is {ph}" for n, ph in zip(names, phases))
        bullets.append(phase_parts)

    # Mechanism differences
    mechs = [p["mechanism"] for p in profiles]
    unique_mechs = set(mechs)
    if len(unique_mechs) > 1:
        mech_parts = " vs ".join(mechs)
        bullets.append(f"Different mechanisms: {mech_parts}")

    # Indication breadth
    counts = [p["indication_count"] for p in profiles]
    if len(set(counts)) > 1:
        max_count = max(counts)
        max_idx = counts.index(max_count)
        others = [
            f"{names[i]}'s {counts[i]}"
            for i in range(len(names))
            if i != max_idx
        ]
        bullets.append(
            f"{names[max_idx]} targets {max_count} indications vs "
            + " vs ".join(others)
        )

    # Technology differences
    techs = [p["technology"] for p in profiles]
    unique_techs = set(techs)
    if len(unique_techs) > 1:
        tech_parts = " vs ".join(techs)
        bullets.append(f"Different technologies: {tech_parts}")

    return bullets


def generate_comparison_markdown(
    profiles: list[dict],
    trial_summaries: list[dict],
    deal_summaries: list[dict],
) -> str:
    """Build full comparison with side-by-side tables."""
    names = [p["name"] for p in profiles]
    title_names = " vs ".join(names)

    lines = [f"# Drug Comparison: {title_names}", ""]

    # --- Overview table ---
    lines.append("## Overview")
    header = "| Attribute | " + " | ".join(names) + " |"
    sep = "|---|" + "---|" * len(names)
    lines.append(header)
    lines.append(sep)

    def row(label: str, values: list[Any]) -> str:
        return "| " + label + " | " + " | ".join(str(v) for v in values) + " |"

    lines.append(row("Phase", [p["phase"] for p in profiles]))
    lines.append(row("Mechanism", [p["mechanism"] for p in profiles]))
    lines.append(row("Technology", [p["technology"] for p in profiles]))
    lines.append(row("Indications", [p["indication_count"] for p in profiles]))
    lines.append(row("Company", [p["company"] for p in profiles]))
    lines.append("")

    # --- Clinical Trials table ---
    lines.append("## Clinical Trials")
    lines.append(header)
    lines.append(sep)
    lines.append(row("Total Trials", [t["total"] for t in trial_summaries]))
    lines.append(row("Recruiting", [t["recruiting"] for t in trial_summaries]))
    lines.append(row("Phase 3", [t["phase3"] for t in trial_summaries]))
    lines.append("")

    # --- Deal Activity table ---
    lines.append("## Deal Activity")
    lines.append(header)
    lines.append(sep)
    lines.append(row("Total Deals", [d["total"] for d in deal_summaries]))
    lines.append(row("Latest Deal", [d["latest_date"] or "N/A" for d in deal_summaries]))
    lines.append(row("Deal Types", [d["deal_types"] or "N/A" for d in deal_summaries]))
    lines.append("")

    # --- Key Differentiators ---
    differentiators = identify_differentiators(profiles)
    if differentiators:
        lines.append("## Key Differentiators")
        for bullet in differentiators:
            lines.append(f"- {bullet}")
        lines.append("")

    return "\n".join(lines)


def _load_json(path: str) -> dict:
    """Load JSON from path, return empty dict on any error."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {}


def main(directory: str) -> None:
    indices = discover_drugs(directory)
    if not indices:
        print("No drug_N.json files found in directory.", file=sys.stderr)
        sys.exit(1)

    profiles = []
    trial_summaries = []
    deal_summaries = []

    for n in indices:
        drug_record = _load_json(os.path.join(directory, f"drug_{n}.json"))
        trials_data = _load_json(os.path.join(directory, f"trials_{n}.json"))
        deals_data = _load_json(os.path.join(directory, f"deals_{n}.json"))

        profiles.append(extract_drug_profile(drug_record))
        trial_summaries.append(extract_trial_summary(trials_data))
        deal_summaries.append(extract_deal_summary(deals_data))

    markdown = generate_comparison_markdown(profiles, trial_summaries, deal_summaries)
    print(markdown)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <comparison_dir>", file=sys.stderr)
        sys.exit(1)
    main(sys.argv[1])
