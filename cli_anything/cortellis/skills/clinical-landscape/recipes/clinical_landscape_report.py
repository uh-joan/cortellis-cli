#!/usr/bin/env python3
"""Generate a clinical trial landscape report from collected JSON data.

Usage: python3 clinical_landscape_report.py /tmp/clinical_landscape "indication name"
"""
import json, sys, os
from collections import Counter

data_dir = sys.argv[1]
indication = sys.argv[2] if len(sys.argv) > 2 else "Unknown"
indication_id = sys.argv[3] if len(sys.argv) > 3 else ""

# ── Data loading with error tracking ─────────────────────────────────────────

_data_status = {}


def load_json(filename):
    path = os.path.join(data_dir, filename)
    if not os.path.exists(path):
        _data_status[filename] = "missing"
        return None
    try:
        with open(path) as f:
            d = json.load(f)
        if d.get("error"):
            _data_status[filename] = f"error: {d['error']}"
            return None
        if len(str(d)) < 50:
            _data_status[filename] = "empty"
            return None
        _data_status[filename] = "ok"
        return d
    except json.JSONDecodeError as e:
        _data_status[filename] = f"error: invalid JSON ({e})"
        return None
    except Exception as e:
        _data_status[filename] = f"error: {e}"
        return None


def extract_trials(data):
    if not data:
        return [], "0"
    results = data.get("trialResultsOutput", {})
    total = results.get("@totalResults", "0")
    search = results.get("SearchResults", {})
    if not isinstance(search, dict):
        return [], total
    trials = search.get("Trial", [])
    if isinstance(trials, dict):
        trials = [trials]
    return trials, total


def bar_chart(data, title, max_width=35, char="\u2588"):
    if not data:
        return ""
    max_val = max(v for _, v in data)
    if max_val == 0:
        return ""
    lines = [title, "\u2500" * 55]
    for label, value in data:
        bar_len = int(value / max_val * max_width) if max_val > 0 else 0
        bar = char * max(bar_len, 1)
        lines.append(f"  {label:20s} {bar} {value}")
    return "\n".join(lines)


def format_sponsor(raw):
    """Extract sponsor name, handling dicts and lists properly."""
    if isinstance(raw, dict):
        company = raw.get("Company", raw.get("$", raw.get("@name", "?")))
        if isinstance(company, list):
            return "; ".join(str(c) for c in company[:3])
        return str(company)
    return str(raw) if raw else "?"


def trial_table(trials):
    """Render ALL trials — no truncation."""
    rows = []
    for t in trials:
        title = (t.get("TitleDisplay", t.get("Title", "?")))[:55]
        sponsor = format_sponsor(
            t.get("CompaniesSponsor", t.get("LeadSponsor", t.get("Sponsor", "?")))
        )[:30]
        phase = t.get("Phase", "?")
        status = t.get("RecruitmentStatus", "?")
        enrollment = t.get("PatientCountEnrollment", "?")
        start = t.get("DateStart", t.get("StartDate", "?"))
        if isinstance(start, str):
            start = start[:10]
        rows.append(f"| {title} | {phase} | {sponsor} | {status} | {enrollment} | {start} |")
    return rows


# ── Load all trial data ──────────────────────────────────────────────────────

p3_trials, p3_total = extract_trials(load_json("trials_p3.json"))
p2_trials, p2_total = extract_trials(load_json("trials_p2.json"))
p1_trials, p1_total = extract_trials(load_json("trials_p1.json"))
recruiting, rec_total = extract_trials(load_json("trials_recruiting.json"))

all_trials = p3_trials + p2_trials + p1_trials
grand_total = int(p3_total) + int(p2_total) + int(p1_total)
fetched_total = len(all_trials)

print(f"# Clinical Trial Landscape: {indication}")
if indication_id:
    print(f"**Indication ID:** {indication_id}")
print()
print(f"**Phase 3:** {p3_total} | **Phase 2:** {p2_total} | **Phase 1:** {p1_total} | **Recruiting:** {rec_total}")
print()

# Phase distribution chart (uses @totalResults — accurate even with fetch caps)
phase_data = [
    ("Phase 3", int(p3_total)),
    ("Phase 2", int(p2_total)),
    ("Phase 1", int(p1_total)),
]
chart = bar_chart(phase_data, "Trial Distribution by Phase")
if chart:
    print("## Phase Distribution")
    print()
    print("```")
    print(chart)
    print("```")
    print()

# Top sponsors — built from fetched trials, labeled honestly
sponsor_counter = Counter()
for t in all_trials:
    sponsor = format_sponsor(
        t.get("CompaniesSponsor", t.get("LeadSponsor", t.get("Sponsor", "")))
    )
    if sponsor and sponsor != "?":
        sponsor_counter[sponsor[:40]] += 1

if sponsor_counter:
    if fetched_total < grand_total:
        print(f"## Top Sponsors (based on {fetched_total} fetched of {grand_total} total trials)")
    else:
        print(f"## Top Sponsors ({len(sponsor_counter)} unique)")
    print()
    print("| Sponsor | Trials |")
    print("|---------|--------|")
    for sp, count in sponsor_counter.most_common(20):
        print(f"| {sp} | {count} |")
    print()

# ── Trial tables by phase — ALL fetched trials shown ─────────────────────────

def print_phase_section(trials, phase_name, total_str):
    if not trials:
        return
    fetched = len(trials)
    total = int(total_str)
    if fetched < total:
        print(f"## {phase_name} Trials (showing {fetched} of {total} total)")
    else:
        print(f"## {phase_name} Trials ({total} total)")
    print()
    print("| Trial | Phase | Sponsor | Status | Enrollment | Start |")
    print("|-------|-------|---------|--------|------------|-------|")
    for row in trial_table(trials):
        print(row)
    print()


# Recruiting
if recruiting:
    fetched_rec = len(recruiting)
    total_rec = int(rec_total)
    if fetched_rec < total_rec:
        print(f"## Actively Recruiting (showing {fetched_rec} of {total_rec} total)")
    else:
        print(f"## Actively Recruiting ({rec_total} trials)")
    print()
    print("| Trial | Phase | Sponsor | Status | Enrollment | Start |")
    print("|-------|-------|---------|--------|------------|-------|")
    for row in trial_table(recruiting):
        print(row)
    print()

print_phase_section(p3_trials, "Phase 3", p3_total)
print_phase_section(p2_trials, "Phase 2", p2_total)
print_phase_section(p1_trials, "Phase 1", p1_total)

# ── Data Completeness ────────────────────────────────────────────────────────

print("## Data Completeness")
print()
print("| Source | Fetched | Total | Coverage |")
print("|--------|---------|-------|----------|")

sources = [
    ("Phase 3 trials", "trials_p3.json", len(p3_trials), int(p3_total)),
    ("Phase 2 trials", "trials_p2.json", len(p2_trials), int(p2_total)),
    ("Phase 1 trials", "trials_p1.json", len(p1_trials), int(p1_total)),
    ("Recruiting trials", "trials_recruiting.json", len(recruiting), int(rec_total)),
]

any_truncated = False
for label, filename, fetched, total in sources:
    status = _data_status.get(filename, "not fetched")
    if status == "ok":
        if total > 0:
            pct = int(fetched / total * 100)
            coverage = f"{pct}%"
            if fetched < total:
                any_truncated = True
        else:
            coverage = "0 trials"
        print(f"| {label} | {fetched} | {total} | {coverage} |")
    elif status == "missing":
        print(f"| {label} | — | — | Not fetched |")
    else:
        print(f"| {label} | — | — | {status} |")

print()

if any_truncated:
    print("*Some phases have more trials than fetched (sorted by most recent start date). Sponsor rankings reflect the fetched sample only. Increase `--hits` in the workflow for full coverage.*")
    print()
print("*Sort order: most recent trial start date first (`-trialDateStart`). Fetched trials are the newest, not necessarily the most clinically significant.*")
print()
