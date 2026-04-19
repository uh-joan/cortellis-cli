#!/usr/bin/env python3
"""
extract_changes.py — Generate a competitive landscape changelog narrative.

Since wiki/ is gitignored, this script synthesizes history from:
  - raw/<slug>/historical_snapshots.csv  (monthly phase-count time series)
  - raw/<slug>/phase_timeline.csv        (individual drug phase transitions)
  - raw/<slug>/strategic_scores.csv      (current company CPI rankings)
  - wiki/indications/<slug>.md           (current compiled state + company_rankings)

Usage:
    python3 extract_changes.py <wiki_file> <raw_dir> <indication_name>
"""

import sys
import os
import csv
import re
from datetime import datetime
from collections import defaultdict

# ── helpers ──────────────────────────────────────────────────────────────────

def parse_frontmatter(path: str) -> dict:
    """Extract YAML-like frontmatter from a wiki markdown file."""
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        content = f.read()
    m = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not m:
        return {}
    import yaml
    try:
        return yaml.safe_load(m.group(1)) or {}
    except Exception:
        # Fallback: simple key: value parsing for non-nested fields
        meta = {}
        for line in m.group(1).splitlines():
            if ":" in line and not line.startswith(" ") and not line.startswith("-"):
                k, _, v = line.partition(":")
                meta[k.strip()] = v.strip().strip("'\"")
        return meta


def load_csv(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def fmt_delta(a, b) -> str:
    """Return '+N' / '-N' / 'unchanged' for numeric delta."""
    try:
        d = int(b) - int(a)
        return f"+{d}" if d > 0 else str(d)
    except (TypeError, ValueError):
        return "?"


def month_label(date_str: str) -> str:
    """'2025-04-01' → 'Apr 2025'"""
    try:
        return datetime.strptime(date_str[:10], "%Y-%m-%d").strftime("%b %Y")
    except ValueError:
        return date_str[:7]


# ── phase timeline events ────────────────────────────────────────────────────

NOTABLE_TRANSITIONS = {
    ("Phase 3 Clinical", "Registered"),
    ("Registered", "Launched"),
    ("Phase 2 Clinical", "Phase 3 Clinical"),
    ("Phase 1 Clinical", "Phase 2 Clinical"),
}

TRANSITION_LABEL = {
    ("Phase 3 Clinical", "Registered"):    "filed for approval",
    ("Registered", "Launched"):            "launched",
    ("Phase 2 Clinical", "Phase 3 Clinical"): "advanced to Phase 3",
    ("Phase 1 Clinical", "Phase 2 Clinical"): "advanced to Phase 2",
}


def load_notable_transitions(raw_dir: str) -> list[dict]:
    """Return notable phase transitions sorted newest-first, last 24 months.

    Deduplicates by (drug_id, date, transition) — phase_timeline.csv sometimes
    has one row without company and one with company for the same event.
    """
    rows = load_csv(os.path.join(raw_dir, "phase_timeline.csv"))
    cutoff = "2024-04-01"  # ~24 months back
    seen: set[tuple] = set()
    events = []
    for r in rows:
        date = r.get("date", "")
        if date < cutoff:
            continue
        transition_key = (r.get("phase_from", "").strip(), r.get("phase_to", "").strip())
        if transition_key not in NOTABLE_TRANSITIONS:
            continue
        drug_id = r.get("drug_id", "").strip()
        dedup_key = (drug_id, date, transition_key)
        if dedup_key in seen:
            continue
        seen.add(dedup_key)
        events.append({
            "date": date,
            "drug": r.get("drug_name", "").split(",")[0].strip(),
            "label": TRANSITION_LABEL[transition_key],
            "company": r.get("company", "").strip(),
        })
    events.sort(key=lambda x: x["date"], reverse=True)
    return events


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 4:
        print("Usage: extract_changes.py <wiki_file> <raw_dir> <indication_name>")
        sys.exit(1)

    wiki_file, raw_dir, indication = sys.argv[1], sys.argv[2], sys.argv[3]

    # 1. Current state from wiki frontmatter
    meta = parse_frontmatter(wiki_file)
    compiled_at = meta.get("compiled_at", "")[:10] if meta.get("compiled_at") else "unknown"
    total_drugs_now = meta.get("total_drugs", "?")
    meta.get("top_company", "?")
    phase_counts_now = meta.get("phase_counts", {}) or {}

    # 2. Historical snapshots
    snapshots = load_csv(os.path.join(raw_dir, "historical_snapshots.csv"))

    # 3. Notable phase transitions
    transitions = load_notable_transitions(raw_dir)

    # 4. Current company rankings (from wiki or strategic_scores.csv)
    company_rankings = meta.get("company_rankings", []) or []
    if not company_rankings:
        scores = load_csv(os.path.join(raw_dir, "strategic_scores.csv"))
        company_rankings = [
            {"company": r["company"], "cpi_score": float(r.get("cpi_score", 0))}
            for r in scores[:5]
        ]

    # ── Print header ───────────────────────────────────────────────────────
    if snapshots:
        date_range = f"{month_label(snapshots[0]['date'])} → {month_label(snapshots[-1]['date'])}"
        n_months = len(snapshots)
    else:
        date_range = compiled_at
        n_months = 1

    print(f"## Changelog: {indication} ({date_range})")
    print()

    # ── Current snapshot ──────────────────────────────────────────────────
    print("### Current State")
    print(f"- Compiled: {compiled_at}")
    print(f"- Total drugs tracked: {total_drugs_now}")
    if phase_counts_now:
        launched = phase_counts_now.get("launched", "?")
        p3 = phase_counts_now.get("phase3", "?")
        p2 = phase_counts_now.get("phase2", "?")
        p1 = phase_counts_now.get("phase1", "?")
        print(f"- Pipeline: {launched} launched | {p3} Phase 3 | {p2} Phase 2 | {p1} Phase 1")
    if company_rankings:
        top3 = company_rankings[:3]
        ranking_str = " | ".join(
            f"#{i+1} {r['company']} (CPI {r.get('cpi_score', '?')})"
            for i, r in enumerate(top3)
        )
        print(f"- Top companies: {ranking_str}")
    print()

    # ── Phase count evolution ─────────────────────────────────────────────
    if len(snapshots) >= 2:
        print("### Phase Count Evolution")
        first = snapshots[0]
        last = snapshots[-1]

        # Total change
        total_first = int(first.get("total", first.get("drugs_tracked", 0)))
        total_last = int(last.get("total", last.get("drugs_tracked", 0)))
        total_delta = fmt_delta(total_first, total_last)
        print(f"- Total ({month_label(first['date'])} → {month_label(last['date'])}): "
              f"{total_first} → {total_last} ({total_delta})")

        # Phase 3 trend
        p3_first = int(first.get("phase3", 0))
        p3_last = int(last.get("phase3", 0))
        if p3_first != p3_last:
            print(f"- Phase 3: {p3_first} → {p3_last} ({fmt_delta(p3_first, p3_last)})")

        # Phase 2 trend
        p2_first = int(first.get("phase2", 0))
        p2_last = int(last.get("phase2", 0))
        if p2_first != p2_last:
            print(f"- Phase 2: {p2_first} → {p2_last} ({fmt_delta(p2_first, p2_last)})")

        # Launched trend
        l_first = int(first.get("launched", 0))
        l_last = int(last.get("launched", 0))
        if l_first != l_last:
            print(f"- Launched: {l_first} → {l_last} ({fmt_delta(l_first, l_last)})")

        print()

        # Month-by-month notable jumps (>= 3 drugs change in total)
        notable_months = []
        for i in range(1, len(snapshots)):
            prev, curr = snapshots[i - 1], snapshots[i]
            try:
                prev_total = int(prev.get("total", prev.get("drugs_tracked", 0)))
                curr_total = int(curr.get("total", curr.get("drugs_tracked", 0)))
                delta = curr_total - prev_total
            except (ValueError, TypeError):
                continue
            if abs(delta) >= 3:
                notable_months.append({
                    "date": curr["date"],
                    "prev_total": prev_total,
                    "curr_total": curr_total,
                    "delta": delta,
                    "p3_delta": int(curr.get("phase3", 0)) - int(prev.get("phase3", 0)),
                })

        if notable_months:
            print("### Notable Monthly Jumps")
            for m in notable_months:
                sign = "+" if m["delta"] > 0 else ""
                line = (f"- {month_label(m['date'])}: total {m['prev_total']} → {m['curr_total']} "
                        f"({sign}{m['delta']})")
                if abs(m["p3_delta"]) >= 2:
                    p3_sign = "+" if m["p3_delta"] > 0 else ""
                    line += f", Phase 3 {p3_sign}{m['p3_delta']}"
                print(line)
            print()

    elif len(snapshots) == 1:
        s = snapshots[0]
        print(f"### First Compiled: {month_label(s['date'])}")
        print(f"- Total: {s.get('total', s.get('drugs_tracked', '?'))}")
        print(f"- Phase 3: {s.get('phase3', '?')} | Phase 2: {s.get('phase2', '?')}")
        print()

    else:
        print("_No historical snapshot data found in raw directory._")
        print()

    # ── Recent notable drug transitions ───────────────────────────────────
    if transitions:
        print("### Recent Drug Events (last 24 months)")
        # Group by month, show up to 15 events
        by_month: dict[str, list] = defaultdict(list)
        for t in transitions:
            by_month[t["date"][:7]].append(t)

        for month_key in sorted(by_month.keys(), reverse=True):
            for e in by_month[month_key]:
                company_part = f" ({e['company']})" if e["company"] else ""
                print(f"- {month_label(e['date'])}: **{e['drug']}**{company_part} — {e['label']}")
        print()

    # ── Footer ────────────────────────────────────────────────────────────
    print("---")
    if n_months > 1:
        print(f"_Data spans {n_months} monthly snapshots. "
              f"Company rankings reflect current compiled state only._")
    else:
        print("_Only one snapshot available. Run /landscape periodically to build history._")


if __name__ == "__main__":
    main()
