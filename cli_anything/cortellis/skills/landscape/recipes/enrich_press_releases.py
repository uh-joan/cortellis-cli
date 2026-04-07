#!/usr/bin/env python3
"""
enrich_press_releases.py — Enrich landscape with recent press releases.

Searches press releases for top companies and writes summary.

Usage: python3 enrich_press_releases.py <landscape_dir> [indication_name]
"""

import csv
import os
import sys
import time

# Allow running as standalone script
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))

from cli_anything.cortellis.core import press_releases
from cli_anything.cortellis.core.client import CortellisClient
from cli_anything.cortellis.utils.data_helpers import read_csv_safe


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def get_top_company_names(landscape_dir, max_companies=10):
    """Read strategic_scores.csv, return list of company name strings.

    Returns up to max_companies company names in CPI rank order.
    """
    rows = read_csv_safe(os.path.join(landscape_dir, "strategic_scores.csv"))

    names = []
    seen = set()

    for row in rows:
        name = (row.get("company") or "").strip()
        if name and name not in seen:
            seen.add(name)
            names.append(name)
        if len(names) >= max_companies:
            break

    return names


def search_press_releases_for_company(company_name, client, max_hits=5):
    """Search press releases for a company by name.

    Returns list of raw record dicts from the API response.
    Sleeps 2s after the API call.
    """
    records = []
    try:
        result = press_releases.search(client, query=company_name, hits=max_hits)
        if result:
            if isinstance(result, dict):
                hits = (
                    result.get("pressReleaseList", {}).get("pressRelease", [])
                    or result.get("hits", [])
                    or result.get("results", [])
                    or []
                )
            elif isinstance(result, list):
                hits = result
            else:
                hits = []

            if not isinstance(hits, list):
                hits = [hits] if hits else []

            records = [h for h in hits if isinstance(h, dict)]
    except Exception as exc:
        print(f"[warn] press release search failed for {company_name!r}: {exc}", file=sys.stderr)

    time.sleep(2)
    return records


def extract_press_release(record):
    """Extract press release fields from an API record.

    Returns a dict with: company_name, title, date, summary.
    Note: company_name is populated by the caller.
    """
    if not isinstance(record, dict):
        return {}

    title = str(
        record.get("title") or record.get("headline") or record.get("name") or ""
    ).strip()

    date = str(
        record.get("date") or record.get("publishDate") or
        record.get("pubDate") or record.get("releaseDate") or ""
    ).strip()
    # Trim to YYYY-MM if longer
    if len(date) > 7 and "-" in date:
        date = date[:7]

    summary_raw = str(
        record.get("summary") or record.get("snippet") or
        record.get("abstract") or record.get("body") or ""
    ).strip()
    summary = summary_raw[:200] + ("..." if len(summary_raw) > 200 else "")

    return {
        "title": title,
        "date": date,
        "summary": summary,
    }


def write_press_releases_csv(releases, path):
    """Write press_releases_summary.csv. Writes header-only if releases is empty."""
    fieldnames = ["company_name", "title", "date", "summary"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for release in releases:
            writer.writerow(release)


def generate_press_releases_markdown(releases, indication_name, total_queried=None):
    """Produce recent_press_releases.md with a summary table and stats section."""
    lines = [f"## Recent Press Releases: {indication_name}", ""]

    if not releases:
        lines.append("_No press releases found._")
        lines.append("")
        lines.append("### Summary")
        denom = total_queried if total_queried is not None else 0
        lines.append(f"- 0 press releases found for 0/{denom} companies searched")
        lines.append("")
        return "\n".join(lines)

    # Table
    lines.append("| Company | Title | Date | Summary |")
    lines.append("|---|---|---|---|")
    for release in releases:
        company = release.get("company_name", "")
        title = release.get("title", "")
        date = release.get("date", "")
        summary = release.get("summary", "")
        # Truncate long titles for readability
        if len(title) > 80:
            title = title[:77] + "..."
        lines.append(f"| {company} | {title} | {date} | {summary} |")
    lines.append("")

    # Summary stats
    companies_with_releases = len({r.get("company_name", "") for r in releases if r.get("company_name")})
    total_companies_searched = total_queried if total_queried is not None else companies_with_releases

    # Most active company
    company_counts = {}
    for release in releases:
        c = release.get("company_name", "")
        if c:
            company_counts[c] = company_counts.get(c, 0) + 1
    most_active = max(company_counts.items(), key=lambda x: x[1]) if company_counts else None

    # Most recent release
    dated = [(r.get("date", ""), r.get("title", "")) for r in releases if r.get("date")]
    most_recent = max(dated, key=lambda x: x[0]) if dated else None

    lines.append("### Summary")
    lines.append(
        f"- {len(releases)} press releases found for {companies_with_releases}/{total_companies_searched} companies searched"
    )
    if most_active:
        lines.append(f"- Most active: {most_active[0]} ({most_active[1]} releases)")
    if most_recent:
        title_snippet = most_recent[1][:60] + ("..." if len(most_recent[1]) > 60 else "")
        lines.append(f"- Most recent: \"{title_snippet}\" ({most_recent[0]})")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print("Usage: enrich_press_releases.py <landscape_dir> [indication_name]", file=sys.stderr)
        sys.exit(1)

    landscape_dir = sys.argv[1]
    indication_name = sys.argv[2] if len(sys.argv) > 2 else None

    if not os.path.isdir(landscape_dir):
        print(f"Error: landscape directory not found: {landscape_dir}", file=sys.stderr)
        sys.exit(1)

    if not indication_name:
        indication_name = os.path.basename(landscape_dir).replace("-", " ").title()

    print(f"Fetching recent press releases for: {indication_name}")

    company_names = get_top_company_names(landscape_dir, max_companies=10)
    if not company_names:
        print("[info] No company names found in strategic_scores.csv.")

    client = CortellisClient()

    all_releases = []
    companies_with_releases = 0
    companies_without_releases = 0

    for company_name in company_names:
        records = search_press_releases_for_company(company_name, client)
        if records:
            companies_with_releases += 1
            for rec in records:
                release = extract_press_release(rec)
                release["company_name"] = company_name
                all_releases.append(release)
        else:
            companies_without_releases += 1

    # Write CSV
    csv_path = os.path.join(landscape_dir, "press_releases_summary.csv")
    write_press_releases_csv(all_releases, csv_path)
    print(f"Written: {csv_path}")

    # Write markdown
    md_path = os.path.join(landscape_dir, "recent_press_releases.md")
    md_content = generate_press_releases_markdown(all_releases, indication_name, total_queried=len(company_names))
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)
    print(f"Written: {md_path}")

    total = len(company_names)
    print(
        f"Summary: {companies_with_releases}/{total} companies had press releases "
        f"({companies_without_releases} with none), {len(all_releases)} total releases."
    )


if __name__ == "__main__":
    main()
