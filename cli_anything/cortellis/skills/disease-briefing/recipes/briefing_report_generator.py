#!/usr/bin/env python3
"""Generate a disease briefing report from collected JSON data.

Usage: python3 briefing_report_generator.py /tmp/disease_briefing "disease name"
"""
import json, re, sys, os

data_dir = sys.argv[1]
disease_name = sys.argv[2] if len(sys.argv) > 2 else "Unknown"
max_chars = int(sys.argv[3]) if len(sys.argv) > 3 else 5000


def load_json(filename):
    path = os.path.join(data_dir, filename)
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            d = json.load(f)
        if isinstance(d, dict) and len(str(d)) < 50:
            return None
        return d
    except Exception:
        return None


def load_text(filename):
    path = os.path.join(data_dir, filename)
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            return f.read().strip()
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


print(f"# Disease Briefing: {disease_name}")
print()

# Search results
search = load_json("briefing_search.json")
if not search or search.get("error"):
    if search and search.get("error"):
        print(f"**API Error:** {search['error']}")
        print()
        print("Disease briefings require a **premium Drug Design subscription**.")
        print("Contact your Cortellis administrator for access.")
        print()
        print(f"*Alternative: Run `/indication-deep-dive {disease_name}` for a disease overview using standard CI data.*")
    else:
        print("No disease briefings found for this topic.")
        print()
        print(f"*Try `/indication-deep-dive {disease_name}` instead.*")
    sys.exit(0)

results = search.get("diseaseBriefingResultsOutput", search)
total = results.get("@totalResults", "0")
briefings = extract_list(results, "SearchResults", "DiseaseBriefing")
if not briefings:
    briefings = extract_list(results, "SearchResults", "DiseaseBriefingResult")

print(f"**Briefings Found:** {total}")
print()

if not briefings:
    print("No briefing records available.")
    sys.exit(0)

# Show overview of each briefing
for i, b in enumerate(briefings[:5], 1):
    bid = b.get("@id", "?")
    title = b.get("Title", b.get("@name", b.get("DiseaseName", f"Briefing {i}")))
    if isinstance(title, dict):
        title = title.get("$", str(title))

    print(f"## Briefing {i}: {title}")
    print()
    print(f"**ID:** {bid}")
    print()

    # Try to show fields
    for key in ("Disease", "TherapeuticArea", "UpdateDate", "LastModifiedDate"):
        val = b.get(key, "")
        if isinstance(val, dict):
            val = val.get("$", val.get("@name", str(val)))
        if val:
            print(f"**{key}:** {val}")

    # Sections from the briefing record
    record = load_json(f"briefing_record_{i}.json")
    if not record:
        record = load_json("briefing_record.json") if i == 1 else None
    if record:
        rec = record.get("diseaseBriefingRecordOutput", record)
        sections_data = rec.get("Sections", rec.get("Section", []))
        if isinstance(sections_data, dict):
            sections = sections_data.get("Section", [])
            if isinstance(sections, dict):
                sections = [sections]
        elif isinstance(sections_data, list):
            sections = sections_data
        else:
            sections = []

        if sections:
            print()
            print(f"### Sections ({len(sections)})")
            print()
            print("| # | Section | ID |")
            print("|---|---------|-----|")
            for j, s in enumerate(sections, 1):
                stitle = s.get("Title", s.get("@name", s.get("$", f"Section {j}")))
                if isinstance(stitle, dict):
                    stitle = stitle.get("$", str(stitle))
                sid = s.get("@id", "?")
                print(f"| {j} | {stitle} | {sid} |")
            print()

    # Section text files
    for j in range(1, 10):
        text = load_text(f"section_{i}_{j}.txt")
        if not text:
            text = load_text(f"section_{j}.txt") if i == 1 else None
        if text:
            cleaned = clean_html(text)
            cleaned = " ".join(cleaned.split())[:max_chars]
            if cleaned and len(cleaned) > 20:
                print(f"### Section {j} Content")
                print()
                print(cleaned)
                print()

    print()

# Cross-skill hints
print("## Related Analysis")
print()
print(f"*Run `/landscape {disease_name}` for competitive landscape.*")
print(f"*Run `/indication-deep-dive {disease_name}` for drugs, trials, deals, and regulatory.*")
print(f"*Run `/clinical-landscape {disease_name}` for clinical trial analysis.*")
