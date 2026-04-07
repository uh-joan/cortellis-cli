#!/usr/bin/env python3
"""
enrich_regulatory_milestones.py — Enrich landscape with regulatory timeline.

Searches regulatory events for top drugs (launched + Phase 3) across US, EU, JP.
Extracts submissions, approvals, PDUFA dates, label changes.

Usage: python3 enrich_regulatory_milestones.py <landscape_dir> [indication_name]
"""

import csv
import os
import sys
import time
from datetime import datetime, timezone

# Allow running as standalone script
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))

from cli_anything.cortellis.core import regulatory
from cli_anything.cortellis.core.client import CortellisClient
from cli_anything.cortellis.utils.data_helpers import read_csv_safe


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def get_top_drug_names(landscape_dir, max_drugs=20):
    """Read launched.csv and phase3.csv, return list of drug name strings.

    Prefers launched drugs first, then phase3. Caps at max_drugs.
    """
    launched_rows = read_csv_safe(os.path.join(landscape_dir, "launched.csv"))
    phase3_rows = read_csv_safe(os.path.join(landscape_dir, "phase3.csv"))

    names = []
    seen = set()

    for row in launched_rows + phase3_rows:
        name = (row.get("name") or row.get("drug_name") or row.get("drug") or "").strip()
        if name and name not in seen:
            seen.add(name)
            names.append(name)
        if len(names) >= max_drugs:
            break

    return names


def search_regulatory_for_drug(drug_name, client, regions=None, max_hits=10):
    """Search regulatory events for a drug across regions.

    Returns list of event dicts with: event_id, drug_name, region,
    doc_category, doc_type, date, title.
    """
    if regions is None:
        regions = ["USA", "EU", "Japan"]

    events = []

    for region in regions:
        try:
            result = regulatory.search(
                client,
                query=drug_name,
                region=region,
                hits=max_hits,
            )
            hits = []
            if result:
                # Try common response shapes
                if isinstance(result, dict):
                    hits = (
                        result.get("regulatoryDocumentList", {}).get("regulatoryDocument", [])
                        or result.get("hits", [])
                        or result.get("results", [])
                        or []
                    )
                elif isinstance(result, list):
                    hits = result

            if not isinstance(hits, list):
                hits = [hits] if hits else []

            for hit in hits:
                if not isinstance(hit, dict):
                    continue
                event_id = str(
                    hit.get("id") or hit.get("documentId") or hit.get("regulatoryId") or ""
                )
                doc_category = (
                    hit.get("docCategory") or hit.get("documentCategory") or
                    hit.get("doc_category") or ""
                )
                doc_type = (
                    hit.get("docType") or hit.get("documentType") or
                    hit.get("doc_type") or ""
                )
                date = (
                    hit.get("date") or hit.get("statusDate") or
                    hit.get("publicationDate") or ""
                )
                title = (
                    hit.get("title") or hit.get("documentTitle") or
                    hit.get("name") or ""
                )
                events.append({
                    "event_id": event_id,
                    "drug_name": drug_name,
                    "region": region,
                    "doc_category": str(doc_category),
                    "doc_type": str(doc_type),
                    "date": str(date)[:10] if date else "",
                    "title": str(title),
                })
        except Exception as exc:
            print(f"[warn] regulatory search failed for {drug_name!r} in {region}: {exc}", file=sys.stderr)

        time.sleep(2)

    return events


def classify_milestone(event):
    """Classify a regulatory event into a milestone type.

    Returns one of: approval, submission, label_change, advisory_committee, other.
    """
    doc_type = (event.get("doc_type") or event.get("docType") or "").lower()
    doc_category = (event.get("doc_category") or event.get("docCategory") or "").lower()
    combined = doc_type + " " + doc_category

    if any(kw in combined for kw in ("approval", "marketing authorization")):
        return "approval"
    if any(kw in combined for kw in ("submission", "application", "nda", "bla", "maa")):
        return "submission"
    if any(kw in combined for kw in ("label", "labeling", "supplement")):
        return "label_change"
    if any(kw in combined for kw in ("advisory", "committee", "panel")):
        return "advisory_committee"
    return "other"


def write_milestones_csv(events, path):
    """Write regulatory_milestones.csv. Writes header-only if events is empty."""
    fieldnames = [
        "event_id", "drug_name", "region", "doc_category",
        "doc_type", "date", "title", "milestone_type",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for event in events:
            row = dict(event)
            if "milestone_type" not in row:
                row["milestone_type"] = classify_milestone(event)
            writer.writerow(row)


def generate_timeline_markdown(events, indication_name):
    """Produce regulatory_timeline.md with recent/upcoming and historical sections."""
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Split into recent/upcoming (last 12 months + future) vs historical
    recent_events = []
    historical_events = []

    for event in events:
        date = event.get("date", "")
        # Compute 12-months-ago cutoff (approximate: subtract 1 from year portion)
        if date:
            try:
                year = int(date[:4])
                cutoff_year = int(now_str[:4]) - 1
                cutoff_month = int(now_str[5:7])
                event_year = year
                event_month = int(date[5:7]) if len(date) >= 7 else 1
                # future or within last 12 months
                if date >= now_str or (
                    event_year > cutoff_year or
                    (event_year == cutoff_year and event_month >= cutoff_month)
                ):
                    recent_events.append(event)
                else:
                    historical_events.append(event)
            except (ValueError, IndexError):
                historical_events.append(event)
        else:
            historical_events.append(event)

    recent_events.sort(key=lambda e: e.get("date", ""))
    historical_events.sort(key=lambda e: e.get("date", ""), reverse=True)

    lines = [f"## Regulatory Timeline: {indication_name}", ""]

    # Recent & Upcoming
    lines.append("### Recent & Upcoming")
    if recent_events:
        lines.append("| Drug | Region | Milestone | Date | Title |")
        lines.append("|------|--------|-----------|------|-------|")
        for e in recent_events:
            milestone = e.get("milestone_type") or classify_milestone(e)
            lines.append(
                f"| {e.get('drug_name', '')} "
                f"| {e.get('region', '')} "
                f"| {milestone} "
                f"| {e.get('date', '')} "
                f"| {e.get('title', '')} |"
            )
    else:
        lines.append("_No recent or upcoming regulatory events found._")
    lines.append("")

    # Historical
    lines.append("### Historical")
    if historical_events:
        lines.append("| Drug | Region | Milestone | Date | Title |")
        lines.append("|------|--------|-----------|------|-------|")
        for e in historical_events:
            milestone = e.get("milestone_type") or classify_milestone(e)
            lines.append(
                f"| {e.get('drug_name', '')} "
                f"| {e.get('region', '')} "
                f"| {milestone} "
                f"| {e.get('date', '')} "
                f"| {e.get('title', '')} |"
            )
    else:
        lines.append("_No historical regulatory events found._")
    lines.append("")

    # Summary
    lines.append("### Summary")
    drugs_with_events = len({e.get("drug_name", "") for e in events if e.get("drug_name")})
    approvals = sum(1 for e in events if (e.get("milestone_type") or classify_milestone(e)) == "approval")
    submissions = sum(1 for e in events if (e.get("milestone_type") or classify_milestone(e)) == "submission")

    region_counts = {}
    for e in events:
        r = e.get("region", "unknown")
        region_counts[r] = region_counts.get(r, 0) + 1

    coverage_parts = [f"{r} ({n} events)" for r, n in sorted(region_counts.items())]

    lines.append(f"- {drugs_with_events} drugs with regulatory activity")
    lines.append(f"- {approvals} approvals, {submissions} submissions")
    if coverage_parts:
        lines.append(f"- Coverage: {', '.join(coverage_parts)}")
    else:
        lines.append("- Coverage: none")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print("Usage: enrich_regulatory_milestones.py <landscape_dir> [indication_name]", file=sys.stderr)
        sys.exit(1)

    landscape_dir = sys.argv[1]
    indication_name = sys.argv[2] if len(sys.argv) > 2 else None

    if not os.path.isdir(landscape_dir):
        print(f"Error: landscape directory not found: {landscape_dir}", file=sys.stderr)
        sys.exit(1)

    if not indication_name:
        indication_name = os.path.basename(landscape_dir).replace("-", " ").title()

    print(f"Fetching regulatory milestones for: {indication_name}")

    drug_names = get_top_drug_names(landscape_dir, max_drugs=20)
    if not drug_names:
        print("[info] No drug names found in launched.csv or phase3.csv.")

    client = CortellisClient()

    all_events = []
    drugs_with_events = 0
    drugs_without_events = 0

    for drug_name in drug_names:
        events = search_regulatory_for_drug(drug_name, client)
        if events:
            drugs_with_events += 1
            for e in events:
                e["milestone_type"] = classify_milestone(e)
            all_events.extend(events)
        else:
            drugs_without_events += 1

    # Write CSV (header-only if no events)
    csv_path = os.path.join(landscape_dir, "regulatory_milestones.csv")
    write_milestones_csv(all_events, csv_path)
    print(f"Written: {csv_path}")

    # Write markdown timeline
    md_path = os.path.join(landscape_dir, "regulatory_timeline.md")
    md_content = generate_timeline_markdown(all_events, indication_name)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)
    print(f"Written: {md_path}")

    total = len(drug_names)
    print(
        f"Summary: {drugs_with_events}/{total} drugs had regulatory events "
        f"({drugs_without_events} with none), {len(all_events)} total events."
    )


if __name__ == "__main__":
    main()
