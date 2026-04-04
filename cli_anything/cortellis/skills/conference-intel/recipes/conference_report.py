#!/usr/bin/env python3
"""Generate a conference intelligence report.

Usage: python3 conference_report.py /tmp/conference_intel "keyword"
"""
import json, re, sys, os
from datetime import datetime

data_dir = sys.argv[1]
keyword = sys.argv[2] if len(sys.argv) > 2 else "Unknown"


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


# Load search results
search = load_json("conferences.json")
if not search:
    print(f"# Conference Intelligence: {keyword}")
    print()
    print("No conference data found.")
    sys.exit(0)

results = search.get("conferenceResultsOutput", search)
total = results.get("@totalResults", "0")
confs = extract_list(results, "SearchResults", "Conference")

print(f"# Conference Intelligence: {keyword}")
print()
print(f"**Total Results:** {total}")
print(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}")
print()

if not confs:
    print("No conferences found matching the keyword.")
    sys.exit(0)

# Conference list
total_int = int(total) if str(total).isdigit() else len(confs)
if total_int > len(confs):
    print(f"## Conferences (showing {len(confs)} of {total_int})")
else:
    print(f"## Conferences ({len(confs)} total)")
print()
print("| # | Title | Date | Location |")
print("|---|-------|------|----------|")
for i, c in enumerate(confs, 1):
    # Conference title can be in @title, Title, or ConferenceName
    title = c.get("@title", c.get("Title", ""))
    if not title:
        cn = c.get("ConferenceName", {})
        title = cn.get("$", cn.get("@name", "?")) if isinstance(cn, dict) else str(cn)
    if isinstance(title, dict):
        title = title.get("$", str(title))
    title = clean_html(str(title))[:55]
    date = c.get("DateStart", c.get("Date", c.get("DateDisplay", "?")))
    if isinstance(date, str):
        date = date[:10]
    # Location or ConferenceName for meeting info
    conf_name = c.get("ConferenceName", {})
    if isinstance(conf_name, dict):
        conf_name = conf_name.get("$", "")
    location = c.get("Location", c.get("City", str(conf_name)[:30] if conf_name else "?"))
    if isinstance(location, dict):
        location = location.get("$", str(location))
    location = str(location)[:30]
    print(f"| {i} | {title} | {date} | {location} |")
print()

# Detailed records
for i in range(1, 6):
    record = load_json(f"conference_{i}.json")
    if not record:
        continue
    rec = record.get("conferenceRecordOutput", record)
    title = rec.get("Title", rec.get("@name", f"Conference {i}"))
    if isinstance(title, dict):
        title = title.get("$", str(title))

    print(f"### {clean_html(str(title))[:80]}")
    print()

    for key in ("Date", "DateDisplay", "Location", "City", "Country", "Organizer", "Source"):
        val = rec.get(key, "")
        if isinstance(val, dict):
            val = val.get("$", str(val))
        if val:
            print(f"**{key}:** {val}")

    abstract = clean_html(rec.get("Abstract", rec.get("Teaser", "")))
    abstract = " ".join(abstract.split())[:400]
    if abstract:
        print()
        print(abstract)
    print()

# Data Coverage footer
print("## Data Coverage")
print()
print("| Metric | Value |")
print("|--------|-------|")
total_int = int(total) if str(total).isdigit() else len(confs)
if total_int > len(confs):
    print(f"| Conferences | showing {len(confs)} of {total_int} |")
else:
    print(f"| Conferences | {len(confs)} (complete) |")
details_loaded = sum(1 for i in range(1, 6) if load_json(f"conference_{i}.json"))
print(f"| Detailed records | {details_loaded} of top 5 |")
print(f"| Generated | {datetime.now().strftime('%Y-%m-%d %H:%M UTC')} |")
