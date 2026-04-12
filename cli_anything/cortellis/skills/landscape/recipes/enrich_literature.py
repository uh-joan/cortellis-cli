#!/usr/bin/env python3
"""
enrich_literature.py — Enrich landscape with recent publications.

Searches literature for top drugs and writes publication summary.

Usage: python3 enrich_literature.py <landscape_dir> [indication_name]
"""

import csv
import os
import sys
import time

# Allow running as standalone script
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))

from cli_anything.cortellis.core import literature
from dotenv import load_dotenv
from cli_anything.cortellis.core.client import CortellisClient
from cli_anything.cortellis.utils.data_helpers import read_csv_safe


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def get_top_drug_names(landscape_dir, max_drugs=10):
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


def search_literature_for_drug(drug_name, client, max_hits=5):
    """Search literature for a drug by name.

    Returns list of raw record dicts from the API response.
    Falls back to PubMed if Cortellis returns < 3 results.
    Sleeps 2s after the Cortellis API call.
    """
    records = []
    try:
        result = literature.search(client, query=drug_name, hits=max_hits)
        if result:
            if isinstance(result, dict):
                hits = (
                    # Cortellis literature-v2 response shape
                    result.get("literatureResultsOutput", {}).get("SearchResults", {}).get("Literature", [])
                    # Legacy / alternate shapes
                    or result.get("literatureList", {}).get("literature", [])
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
        print(f"[warn] literature search failed for {drug_name!r}: {exc}", file=sys.stderr)

    time.sleep(2)

    # If Cortellis returned < 3 results, try PubMed
    if len(records) < 3:
        try:
            from cli_anything.cortellis.core import pubmed
            pubmed_results = pubmed.search_and_fetch(drug_name, max_results=5)
            for r in pubmed_results:
                r["_source"] = "pubmed"
            records.extend(pubmed_results)
        except Exception as e:
            print(f"[warn] PubMed fallback failed for {drug_name}: {e}", file=sys.stderr)

    return records


def extract_publication(record):
    """Extract publication fields from a literature API record.

    Handles both Cortellis and PubMed record shapes.
    PubMed records have _source='pubmed' and use authors_str directly.
    Returns a dict with: drug_name, title, authors, journal, date, abstract_excerpt.
    Note: drug_name is populated by the caller.
    """
    if not isinstance(record, dict):
        return {}

    title = str(
        record.get("title") or record.get("articleTitle") or record.get("name") or ""
    ).strip()

    # PubMed records pre-compute authors_str; Cortellis uses a list
    if record.get("_source") == "pubmed":
        authors = str(record.get("authors_str") or "").strip()
    else:
        authors_raw = (
            record.get("authors")
            or record.get("authorList")
            or record.get("author")
            or []
        )
        if isinstance(authors_raw, list) and authors_raw:
            first = authors_raw[0]
            if isinstance(first, dict):
                first_name = (
                    first.get("lastName") or first.get("name") or first.get("authorName") or ""
                ).strip()
                initials = (first.get("initials") or first.get("firstName") or "").strip()
                if initials:
                    first_name = f"{first_name} {initials[:2]}"
            else:
                first_name = str(first).strip()
            authors = f"{first_name} et al" if len(authors_raw) > 1 else first_name
        elif isinstance(authors_raw, str):
            authors = authors_raw.strip()
        else:
            authors = ""

    journal = str(
        record.get("journal") or record.get("journalName") or
        record.get("source") or record.get("publicationName") or ""
    ).strip()

    date = str(
        record.get("date") or record.get("publicationDate") or
        record.get("pubDate") or record.get("year") or ""
    ).strip()
    # Trim to YYYY-MM if longer
    if len(date) > 7 and "-" in date:
        date = date[:7]

    abstract_raw = str(
        record.get("abstract") or record.get("abstractText") or ""
    ).strip()
    abstract_excerpt = abstract_raw[:200] + ("..." if len(abstract_raw) > 200 else "")

    return {
        "title": title,
        "authors": authors,
        "journal": journal,
        "date": date,
        "abstract_excerpt": abstract_excerpt,
    }


def write_literature_csv(publications, path):
    """Write literature_summary.csv. Writes header-only if publications is empty."""
    fieldnames = ["drug_name", "title", "authors", "journal", "date", "abstract_excerpt"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for pub in publications:
            writer.writerow(pub)


def generate_publications_markdown(publications, indication_name, total_queried=None):
    """Produce recent_publications.md with a summary table and stats section."""
    lines = [f"## Recent Publications: {indication_name}", ""]

    if not publications:
        lines.append("_No publications found._")
        lines.append("")
        lines.append("### Summary")
        denom = total_queried if total_queried is not None else 0
        lines.append(f"- 0 publications found for 0/{denom} drugs searched")
        lines.append("")
        return "\n".join(lines)

    # Table
    lines.append("| Drug | Title | Authors | Journal | Date |")
    lines.append("|---|---|---|---|---|")
    for pub in publications:
        drug = pub.get("drug_name", "")
        title = pub.get("title", "")
        authors = pub.get("authors", "")
        journal = pub.get("journal", "")
        date = pub.get("date", "")
        # Truncate long titles for readability
        if len(title) > 80:
            title = title[:77] + "..."
        lines.append(f"| {drug} | {title} | {authors} | {journal} | {date} |")
    lines.append("")

    # Summary stats
    drugs_with_pubs = len({p.get("drug_name", "") for p in publications if p.get("drug_name")})
    total_drugs_searched = total_queried if total_queried is not None else drugs_with_pubs

    # Most published drug
    drug_counts = {}
    for pub in publications:
        d = pub.get("drug_name", "")
        if d:
            drug_counts[d] = drug_counts.get(d, 0) + 1
    most_published = max(drug_counts.items(), key=lambda x: x[1]) if drug_counts else None

    # Most recent publication
    dated = [(p.get("date", ""), p.get("title", "")) for p in publications if p.get("date")]
    most_recent = max(dated, key=lambda x: x[0]) if dated else None

    lines.append("### Summary")
    lines.append(
        f"- {len(publications)} publications found for {drugs_with_pubs}/{total_drugs_searched} drugs searched"
    )
    if most_published:
        lines.append(f"- Most published: {most_published[0]} ({most_published[1]} publications)")
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
        print("Usage: enrich_literature.py <landscape_dir> [indication_name]", file=sys.stderr)
        sys.exit(1)

    landscape_dir = sys.argv[1]
    indication_name = sys.argv[2] if len(sys.argv) > 2 else None

    if not os.path.isdir(landscape_dir):
        print(f"Error: landscape directory not found: {landscape_dir}", file=sys.stderr)
        sys.exit(1)

    if not indication_name:
        indication_name = os.path.basename(landscape_dir).replace("-", " ").title()

    print(f"Fetching recent publications for: {indication_name}")

    drug_names = get_top_drug_names(landscape_dir, max_drugs=10)
    if not drug_names:
        print("[info] No drug names found in launched.csv or phase3.csv.")

    load_dotenv()
    client = CortellisClient()

    all_publications = []
    drugs_with_pubs = 0
    drugs_without_pubs = 0

    for drug_name in drug_names:
        records = search_literature_for_drug(drug_name, client)
        if records:
            drugs_with_pubs += 1
            for rec in records:
                pub = extract_publication(rec)
                pub["drug_name"] = drug_name
                all_publications.append(pub)
        else:
            drugs_without_pubs += 1

    # Write CSV
    csv_path = os.path.join(landscape_dir, "literature_summary.csv")
    write_literature_csv(all_publications, csv_path)
    print(f"Written: {csv_path}")

    # Write markdown
    md_path = os.path.join(landscape_dir, "recent_publications.md")
    md_content = generate_publications_markdown(all_publications, indication_name, total_queried=len(drug_names))
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)
    print(f"Written: {md_path}")

    total = len(drug_names)
    print(
        f"Summary: {drugs_with_pubs}/{total} drugs had publications "
        f"({drugs_without_pubs} with none), {len(all_publications)} total publications."
    )


if __name__ == "__main__":
    main()
