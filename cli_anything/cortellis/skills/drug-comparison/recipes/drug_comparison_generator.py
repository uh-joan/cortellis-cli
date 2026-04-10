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

    Handles the nested drugRecordOutput structure from the Cortellis API.
    """
    drug = record.get("drugRecordOutput", record)

    full_name = drug.get("DrugName") or drug.get("drugName") or "Unknown"
    # Use just the INN (first word/phrase before parenthesis or comma)
    import re
    name = re.split(r"\s*[\(,]", full_name)[0].strip() or full_name

    # Phase: {"@id": "L", "$": "Launched"}
    phase_raw = drug.get("PhaseHighest") or drug.get("phase") or {}
    phase = phase_raw.get("$") if isinstance(phase_raw, dict) else str(phase_raw) or "Unknown"

    # Indications: {"Indication": [{"@id": "...", "$": "Obesity"}, ...]}
    ind_raw = drug.get("IndicationsPrimary") or drug.get("IndicationsSecondary") or {}
    ind_list = ind_raw.get("Indication", []) if isinstance(ind_raw, dict) else []
    if isinstance(ind_list, dict):
        ind_list = [ind_list]
    indications = [i.get("$", "") for i in ind_list if isinstance(i, dict)]
    indication_count = len(indications)

    # Mechanism: {"Action": [{"@id": "...", "$": "GLP-1 receptor agonist"}, ...]}
    actions_raw = drug.get("ActionsPrimary") or {}
    actions_list = actions_raw.get("Action", []) if isinstance(actions_raw, dict) else []
    if isinstance(actions_list, dict):
        actions_list = [actions_list]
    mechanism = "; ".join(a.get("$", "") for a in actions_list if isinstance(a, dict)) or "Unknown"

    # Technology: {"Technology": [{"@id": "...", "$": "Peptide"}, ...]}
    tech_raw = drug.get("Technologies") or {}
    tech_list = tech_raw.get("Technology", []) if isinstance(tech_raw, dict) else []
    if isinstance(tech_list, dict):
        tech_list = [tech_list]
    technology = "; ".join(t.get("$", "") for t in tech_list if isinstance(t, dict)) or "Unknown"

    # Company: {"@id": "...", "$": "Eli Lilly & Co"}
    orig_raw = drug.get("CompanyOriginator") or {}
    company = orig_raw.get("$") if isinstance(orig_raw, dict) else str(orig_raw) or "Unknown"

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
    # API returns: {"trialResultsOutput": {"@totalResults": "324", "SearchResults": {"Trial": [...]}}}
    output = trials_json.get("trialResultsOutput", trials_json)
    total = int(output.get("@totalResults") or output.get("totalResults") or 0)

    search = output.get("SearchResults") or {}
    hits = search.get("Trial", [])
    if isinstance(hits, dict):
        hits = [hits]

    recruiting = sum(
        1 for t in hits
        if isinstance(t, dict)
        and str(t.get("RecruitmentStatus") or "").lower() in ("recruiting", "enrolling by invitation")
    )

    phase3 = sum(
        1 for t in hits
        if isinstance(t, dict)
        and "3" in str(t.get("Phase") or "")
    )

    return {
        "total": total,
        "recruiting": recruiting,
        "phase3": phase3,
    }


def extract_deal_summary(deals_json: dict) -> dict:
    """Extract deal counts and metadata from a Cortellis deals search result."""
    # API returns: {"dealResultsOutput": {"@totalResults": "12", "SearchResults": {"Deal": [...]}}}
    output = deals_json.get("dealResultsOutput", deals_json)
    total = int(output.get("@totalResults") or output.get("totalResults") or 0)

    search = output.get("SearchResults") or {}
    hits = search.get("Deal", [])
    if isinstance(hits, dict):
        hits = [hits]

    # Latest deal date
    dates = []
    for d in hits:
        if not isinstance(d, dict):
            continue
        date = d.get("StartDate") or d.get("MostRecentEventDate")
        if date:
            dates.append(str(date)[:10])  # trim to YYYY-MM-DD
    latest_date = sorted(dates, reverse=True)[0] if dates else None

    # Deal types
    types_seen: set[str] = set()
    for d in hits:
        if not isinstance(d, dict):
            continue
        dtype = d.get("Type")
        if dtype:
            types_seen.add(str(dtype))
    deal_types = "; ".join(sorted(types_seen)) if types_seen else None

    return {
        "total": total,
        "latest_date": latest_date,
        "deal_types": deal_types,
    }


def extract_financials(financials_json: dict) -> dict:
    """Extract WW actual + forecast sales from a Cortellis financials response."""
    output = financials_json.get("drugFinancialsOutput", {})
    if not output or isinstance(output, str):
        return {"actual": {}, "forecast": {}}

    entries = output.get("Financials", {})
    if not entries:
        return {"actual": {}, "forecast": {}}

    items = entries.get("Financial", [])
    if isinstance(items, dict):
        items = [items]

    actual: dict[int, float] = {}
    forecast: dict[int, float] = {}
    for item in items:
        if not isinstance(item, dict) or item.get("Region") != "WW":
            continue
        year = item.get("Year")
        sales = item.get("Sales", 0)
        if year is None or not sales:
            continue
        if item.get("Forecast") == "Y":
            forecast[int(year)] = float(sales)
        else:
            actual[int(year)] = float(sales)

    return {"actual": actual, "forecast": forecast}


def sales_trajectory_chart(
    names: list[str],
    financials_list: list[dict],
    max_width: int = 35,
) -> str:
    """Render an ASCII multi-drug sales trajectory chart (actual + forecast)."""
    # Collect all years with data across all drugs
    all_years: set[int] = set()
    for fin in financials_list:
        all_years.update(fin["actual"].keys())
        all_years.update(fin["forecast"].keys())

    if not all_years:
        return ""

    years = sorted(all_years)

    # Find global max for scaling
    all_values = []
    for fin in financials_list:
        all_values.extend(fin["actual"].values())
        all_values.extend(fin["forecast"].values())
    global_max = max(all_values) if all_values else 1

    chars = ["█", "▓", "░", "▒"]
    lines = ["## Sales Trajectory (WW, $M)", ""]
    lines.append("```")
    lines.append(f"{'Year':<6}  " + "  ".join(f"{n[:18]:<18}" for n in names))
    lines.append("─" * (6 + 2 + 20 * len(names)))

    for year in years:
        row_parts = []
        for i, fin in enumerate(financials_list):
            actual_val = fin["actual"].get(year)
            forecast_val = fin["forecast"].get(year)
            val = actual_val if actual_val is not None else forecast_val
            is_forecast = actual_val is None and forecast_val is not None
            if val:
                bar_len = max(1, int(val / global_max * max_width))
                char = "░" if is_forecast else chars[i % 2]
                bar = char * bar_len
                suffix = "~" if is_forecast else " "
                row_parts.append(f"{bar:<35} {suffix}{val:>7,.0f}M")
            else:
                row_parts.append(f"{'—':<35}  {'N/A':>7}")
        lines.append(f"{year:<6}  " + "  ".join(row_parts))

    lines.append("")
    lines.append(f"  {'█'} = actual   {'░'} = forecast   ~ = forecast")
    lines.append("```")
    lines.append("")

    # Legend
    for i, name in enumerate(names):
        lines.append(f"  {chars[i % 2] * 3}  {name}")
    lines.append("")

    return "\n".join(lines)


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
    financials_list: list[dict] | None = None,
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

    # --- Sales Trajectory ---
    if financials_list:
        chart = sales_trajectory_chart(names, financials_list)
        if chart:
            lines.append(chart)

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
    financials_list = []

    for n in indices:
        drug_record = _load_json(os.path.join(directory, f"drug_{n}.json"))
        trials_data = _load_json(os.path.join(directory, f"trials_{n}.json"))
        deals_data = _load_json(os.path.join(directory, f"deals_{n}.json"))
        financials_data = _load_json(os.path.join(directory, f"financials_{n}.json"))

        profiles.append(extract_drug_profile(drug_record))
        trial_summaries.append(extract_trial_summary(trials_data))
        deal_summaries.append(extract_deal_summary(deals_data))
        financials_list.append(extract_financials(financials_data))

    has_financials = any(
        f["actual"] or f["forecast"] for f in financials_list
    )
    markdown = generate_comparison_markdown(
        profiles, trial_summaries, deal_summaries,
        financials_list=financials_list if has_financials else None,
    )
    print(markdown)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <comparison_dir>", file=sys.stderr)
        sys.exit(1)
    main(sys.argv[1])
