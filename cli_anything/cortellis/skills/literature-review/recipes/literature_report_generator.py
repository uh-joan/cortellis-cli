#!/usr/bin/env python3
"""Generate a literature review report from collected JSON data.

Usage: python3 literature_report_generator.py /tmp/literature_review "topic"
"""
import json, re, sys, os
from collections import Counter

data_dir = sys.argv[1]
topic = sys.argv[2] if len(sys.argv) > 2 else "Unknown"


def load_json(filename):
    path = os.path.join(data_dir, filename)
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            d = json.load(f)
        if len(str(d)) < 50:
            return None
        return d
    except Exception:
        return None


def clean_html(text):
    if not text:
        return ""
    return re.sub(r"<[^>]+>", " ", str(text)).strip()


def extract_list(obj, *keys):
    cur = obj
    for k in keys:
        if not isinstance(cur, dict):
            return []
        cur = cur.get(k, {})
    if isinstance(cur, dict):
        return [cur]
    if isinstance(cur, list):
        return cur
    return []


def bar_chart(data, title, max_width=35, char="█"):
    if not data:
        return ""
    max_val = max(v for _, v in data)
    if max_val == 0:
        return ""
    lines = [title, "─" * 55]
    for label, value in data:
        bar_len = int(value / max_val * max_width) if max_val > 0 else 0
        bar = char * max(bar_len, 1)
        lines.append(f"  {label:20s} {bar} {value}")
    return "\n".join(lines)


# Load search results
search = load_json("lit_search.json")
if not search:
    print("Error: lit_search.json not found", file=sys.stderr)
    sys.exit(1)

results = search.get("literatureResultsOutput", {})
total = results.get("@totalResults", "0")
pubs = extract_list(results, "SearchResults", "Literature")

print(f"# Literature Review: {topic}")
print()
print(f"**Total Results:** {total} (showing {len(pubs)})")
print()

# Publication by year
year_counter = Counter()
for p in pubs:
    year = p.get("Year", p.get("PublicationYear", ""))
    if year:
        year_counter[str(year)] += 1

if year_counter:
    sorted_years = sorted(year_counter.items())
    chart = bar_chart(sorted_years[-10:], "Publications by Year (last 10 years)")
    if chart:
        print("## Publication Timeline")
        print()
        print("```")
        print(chart)
        print("```")
        print()

# Top journals
journal_counter = Counter()
for p in pubs:
    journal = p.get("Journal", p.get("JournalName", ""))
    if isinstance(journal, dict):
        journal = journal.get("$", journal.get("@name", ""))
    if journal:
        journal_counter[str(journal)[:40]] += 1

if journal_counter:
    print(f"## Top Journals ({len(journal_counter)} unique)")
    print()
    print("| Journal | Publications |")
    print("|---------|-------------|")
    for j, count in journal_counter.most_common(10):
        print(f"| {j} | {count} |")
    print()

# Key publications table
if pubs:
    print(f"## Key Publications ({len(pubs)} shown)")
    print()
    print("| # | Title | Authors | Journal | Year |")
    print("|---|-------|---------|---------|------|")
    for i, p in enumerate(pubs[:30], 1):
        title = p.get("Title", p.get("TitleDisplay", "?"))
        if isinstance(title, dict):
            title = title.get("$", str(title))
        title = clean_html(str(title))[:55]

        authors = p.get("Authors", p.get("AuthorDisplay", ""))
        if isinstance(authors, dict):
            author_list = authors.get("Author", [])
            if isinstance(author_list, str):
                authors = author_list
            elif isinstance(author_list, list):
                authors = "; ".join(str(a) for a in author_list[:3])
                if len(author_list) > 3:
                    authors += f" +{len(author_list)-3}"
            else:
                authors = str(author_list)
        elif isinstance(authors, list):
            authors = "; ".join(str(a) for a in authors[:3])
        authors = str(authors)[:35]

        journal = p.get("Journal", p.get("JournalName", ""))
        if isinstance(journal, dict):
            journal = journal.get("$", journal.get("@name", ""))
        journal = str(journal)[:25]

        year = p.get("Year", p.get("PublicationYear", "?"))

        print(f"| {i} | {title} | {authors} | {journal} | {year} |")
    print()

# Batch records with abstracts
batch = load_json("lit_batch.json")
if batch:
    batch_results = batch.get("literatureRecordsOutput", batch)
    records = extract_list(batch_results, "Literature")
    if not records:
        records = extract_list(batch_results, "Records", "Literature")
    if records:
        print(f"## Publication Details ({len(records)} records)")
        print()
        for i, r in enumerate(records[:10], 1):
            title = r.get("Title", r.get("TitleDisplay", "?"))
            if isinstance(title, dict):
                title = title.get("$", str(title))
            title = clean_html(str(title))

            authors = r.get("Authors", r.get("AuthorDisplay", ""))
            if isinstance(authors, dict):
                authors = authors.get("$", str(authors))
            elif isinstance(authors, list):
                authors = "; ".join(
                    a.get("$", str(a)) if isinstance(a, dict) else str(a)
                    for a in authors[:5]
                )

            journal = r.get("Journal", r.get("JournalName", ""))
            if isinstance(journal, dict):
                journal = journal.get("$", journal.get("@name", ""))

            year = r.get("Year", r.get("PublicationYear", "?"))

            abstract = clean_html(r.get("Abstract", ""))
            abstract = " ".join(abstract.split())[:300]

            print(f"### {i}. {title[:80]}")
            print(f"**Authors:** {authors}")
            print(f"**Journal:** {journal} | **Year:** {year}")
            if abstract:
                print()
                print(abstract)
            print()
