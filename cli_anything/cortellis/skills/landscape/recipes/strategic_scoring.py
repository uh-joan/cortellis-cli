#!/usr/bin/env python3
"""
strategic_scoring.py — Strategic intelligence layer for landscape skill.

Usage: python3 strategic_scoring.py <landscape_dir> [preset_name]

Outputs:
  <landscape_dir>/strategic_scores.csv
  <landscape_dir>/mechanism_scores.csv
  Markdown summary to stdout
"""

import csv
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, date

# ---------------------------------------------------------------------------
# Preset loading
# ---------------------------------------------------------------------------

preset_name = sys.argv[2] if len(sys.argv) > 2 else "default"
preset_path = os.path.join(os.path.dirname(__file__), "..", "config", "presets", f"{preset_name}.json")
with open(preset_path) as f:
    preset = json.load(f)
WEIGHTS = preset["weights"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def read_csv_safe(path):
    """Return list of dicts; empty list if file missing."""
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def normalize_series(values):
    """Normalize a dict of {key: float} to 0-100 range."""
    if not values:
        return {}
    mn = min(values.values())
    mx = max(values.values())
    if mx == mn:
        return {k: 50.0 for k in values}
    return {k: (v - mn) / (mx - mn) * 100 for k, v in values.items()}


def parse_date(s):
    """Parse YYYY-MM-DD or return None."""
    try:
        return datetime.strptime(s.strip(), "%Y-%m-%d").date()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

PHASE_FILES = ["launched", "phase3", "phase2", "phase1", "discovery"]
PHASE_WEIGHTS = {
    "launched": 5,
    "phase3": 4,
    "phase2": 3,
    "phase1": 2,
    "discovery": 1,
}


def load_drug_rows(landscape_dir):
    """Return (all_drugs, phase_tag) where phase_tag maps drug name→phase key."""
    rows = []
    for phase_key in PHASE_FILES:
        path = os.path.join(landscape_dir, f"{phase_key}.csv")
        for row in read_csv_safe(path):
            row["_phase_key"] = phase_key
            rows.append(row)
    return rows


def load_companies(landscape_dir):
    return read_csv_safe(os.path.join(landscape_dir, "companies.csv"))


def load_deals(landscape_dir):
    return read_csv_safe(os.path.join(landscape_dir, "deals.csv"))


def load_deals_meta(landscape_dir):
    path = os.path.join(landscape_dir, "deals.meta.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_trials_by_sponsor(landscape_dir):
    """Prefer trials_by_sponsor.csv; fall back to trials.csv (sponsor column)."""
    path = os.path.join(landscape_dir, "trials_by_sponsor.csv")
    if os.path.exists(path):
        return read_csv_safe(path)
    # Fallback: aggregate trials.csv by sponsor
    trials_path = os.path.join(landscape_dir, "trials.csv")
    if not os.path.exists(trials_path):
        return []
    sponsor_map = defaultdict(lambda: {"phase2": 0, "phase3": 0, "total": 0})
    for row in read_csv_safe(trials_path):
        sponsor = (row.get("sponsor") or "").strip()
        if not sponsor:
            continue
        phase = (row.get("phase") or "").lower()
        sponsor_map[sponsor]["total"] += 1
        if "phase 2" in phase:
            sponsor_map[sponsor]["phase2"] += 1
        elif "phase 3" in phase:
            sponsor_map[sponsor]["phase3"] += 1
    result = []
    for company, counts in sponsor_map.items():
        result.append({"company": company, **{k: str(v) for k, v in counts.items()}})
    return result


def load_company_sizes(landscape_dir):
    path = os.path.join(landscape_dir, "company_sizes.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# CPI computation
# ---------------------------------------------------------------------------

def compute_cpi(landscape_dir):
    drug_rows = load_drug_rows(landscape_dir)
    companies_rows = load_companies(landscape_dir)
    deals_rows = load_deals(landscape_dir)
    trials_rows = load_trials_by_sponsor(landscape_dir)

    all_companies = set()
    for row in companies_rows:
        c = (row.get("company") or "").strip()
        if c:
            all_companies.add(c)

    # Also collect companies from drug rows
    for row in drug_rows:
        c = (row.get("company") or "").strip()
        if c:
            all_companies.add(c)

    # --- Pipeline breadth: unique drug ids per company ---
    company_drugs = defaultdict(set)  # company -> set of drug ids
    for row in drug_rows:
        company = (row.get("company") or "").strip()
        drug_id = (row.get("id") or row.get("name") or "").strip()
        if company and drug_id:
            company_drugs[company].add(drug_id)

    breadth = {c: len(company_drugs[c]) for c in all_companies}

    # --- Phase score: sum of phase weights per drug ---
    company_phase_score = defaultdict(float)
    for row in drug_rows:
        company = (row.get("company") or "").strip()
        phase_key = row.get("_phase_key", "discovery")
        if company:
            company_phase_score[company] += PHASE_WEIGHTS.get(phase_key, 1)

    phase_score = {c: company_phase_score.get(c, 0.0) for c in all_companies}

    # --- Mechanism diversity: distinct mechanisms per company ---
    company_mechanisms = defaultdict(set)
    for row in drug_rows:
        company = (row.get("company") or "").strip()
        mechs_raw = (row.get("mechanism") or "").strip()
        if company and mechs_raw:
            for m in mechs_raw.split(";"):
                m = m.strip()
                if m:
                    company_mechanisms[company].add(m.lower())

    mech_diversity = {c: len(company_mechanisms[c]) for c in all_companies}

    # --- Deal activity: appearances as principal or partner ---
    company_deal_count = defaultdict(int)
    for row in deals_rows:
        principal = (row.get("principal") or "").strip()
        partner = (row.get("partner") or "").strip()
        if principal:
            company_deal_count[principal] += 1
        if partner and partner != principal:
            company_deal_count[partner] += 1

    deal_activity = {c: company_deal_count.get(c, 0) for c in all_companies}

    # --- Trial intensity: phase2 + phase3 from trials_by_sponsor ---
    trial_intensity_raw = defaultdict(int)
    for row in trials_rows:
        company = (row.get("company") or "").strip()
        try:
            p2 = int(row.get("phase2") or 0)
        except ValueError:
            p2 = 0
        try:
            p3 = int(row.get("phase3") or 0)
        except ValueError:
            p3 = 0
        if company:
            trial_intensity_raw[company] += p2 + p3

    trial_intensity = {c: trial_intensity_raw.get(c, 0) for c in all_companies}

    # --- Normalize each dimension to 0-100 ---
    n_breadth = normalize_series(breadth)
    n_phase = normalize_series(phase_score)
    n_mech = normalize_series(mech_diversity)
    n_deals = normalize_series(deal_activity)
    n_trials = normalize_series(trial_intensity)

    # --- Weighted CPI ---
    cpi_scores = {}
    for c in all_companies:
        cpi = (
            n_breadth.get(c, 0) * WEIGHTS["pipeline_breadth"] / 100
            + n_phase.get(c, 0) * WEIGHTS["phase_score"] / 100
            + n_mech.get(c, 0) * WEIGHTS["mechanism_diversity"] / 100
            + n_deals.get(c, 0) * WEIGHTS["deal_activity"] / 100
            + n_trials.get(c, 0) * WEIGHTS["trial_intensity"] / 100
        )
        cpi_scores[c] = cpi

    # --- Position assignment ---
    # Sort by score desc, then company name asc for deterministic tiebreak
    sorted_companies = sorted(cpi_scores, key=lambda c: (-cpi_scores[c], c))
    n = len(sorted_companies)
    top20 = max(1, int(n * 0.20))
    next30 = max(1, int(n * 0.30))

    positions = {}
    for i, c in enumerate(sorted_companies):
        if i < top20:
            positions[c] = "Leader"
        elif i < top20 + next30:
            positions[c] = "Challenger"
        else:
            positions[c] = "Emerging"

    # Compute percentile-based tier thresholds for this run
    sorted_scores_desc = [round(cpi_scores[c], 2) for c in sorted_companies]
    set_cpi_tier_thresholds(sorted_scores_desc)

    result = {}
    for c in all_companies:
        score = round(cpi_scores[c], 2)
        result[c] = {
            "company": c,
            "cpi_tier": cpi_to_tier(score),
            "cpi_score": score,
            "pipeline_breadth": breadth.get(c, 0),
            "phase_score": round(phase_score.get(c, 0), 2),
            "mechanism_diversity": mech_diversity.get(c, 0),
            "deal_activity": deal_activity.get(c, 0),
            "trial_intensity": trial_intensity.get(c, 0),
            "position": positions.get(c, "Emerging"),
        }
    return result


# ---------------------------------------------------------------------------
# CPI tier helper — percentile-based, computed per-run
# ---------------------------------------------------------------------------

# Module-level holder; populated by compute_cpi() before first use.
_cpi_tier_thresholds = None


def set_cpi_tier_thresholds(sorted_scores):
    """Compute percentile-based tier thresholds from a sorted (desc) list of CPI scores.

    Tiers:
      A — top 10%  (requires cpi >= 40 floor; if no company meets it, best gets B)
      B — next 15% (10th–25th percentile from top)
      C — next 25% (25th–50th percentile from top)
      D — bottom 50%
    """
    global _cpi_tier_thresholds
    n = len(sorted_scores)
    if n == 0:
        _cpi_tier_thresholds = (40.0, 0.0, 0.0)
        return

    top10_idx = max(1, int(n * 0.10)) - 1        # last index in top 10%
    top25_idx = max(1, int(n * 0.25)) - 1        # last index in top 25%
    top50_idx = max(1, int(n * 0.50)) - 1        # last index in top 50%

    thresh_a = sorted_scores[top10_idx]   # score at 10th-percentile boundary
    thresh_b = sorted_scores[top25_idx]   # score at 25th-percentile boundary
    thresh_c = sorted_scores[top50_idx]   # score at 50th-percentile boundary

    _cpi_tier_thresholds = (thresh_a, thresh_b, thresh_c)


def cpi_to_tier(cpi):
    """Assign tier using percentile thresholds set by set_cpi_tier_thresholds().

    Tier A requires cpi_score >= 40 (floor); if the top-10% threshold is below 40,
    no company gets Tier A and the best company gets Tier B instead.
    """
    global _cpi_tier_thresholds
    if _cpi_tier_thresholds is None:
        # Fallback to fixed thresholds if called before thresholds are set
        if cpi >= 75: return "A"
        if cpi >= 50: return "B"
        if cpi >= 25: return "C"
        return "D"

    thresh_a, thresh_b, thresh_c = _cpi_tier_thresholds
    FLOOR_A = 40.0

    effective_a = max(thresh_a, FLOOR_A)
    if cpi >= effective_a:
        return "A"
    if cpi >= thresh_b:
        return "B"
    if cpi >= thresh_c:
        return "C"
    return "D"


# ---------------------------------------------------------------------------
# Mechanism crowding
# ---------------------------------------------------------------------------

def compute_mechanism_scores(landscape_dir):
    drug_rows = load_drug_rows(landscape_dir)

    # Per mechanism: collect drugs and companies
    mech_drugs = defaultdict(set)       # mech -> set of drug ids
    mech_companies = defaultdict(set)   # mech -> set of companies
    mech_phase_counts = defaultdict(lambda: defaultdict(int))  # mech -> phase_key -> count

    for row in drug_rows:
        drug_id = (row.get("id") or row.get("name") or "").strip()
        company = (row.get("company") or "").strip()
        mechs_raw = (row.get("mechanism") or "").strip()
        phase_key = row.get("_phase_key", "discovery")

        if not mechs_raw:
            continue

        for m in mechs_raw.split(";"):
            m = m.strip()
            if not m:
                continue
            mech_key = m.lower()
            if drug_id:
                mech_drugs[mech_key].add(drug_id)
            if company:
                mech_companies[mech_key].add(company)
            mech_phase_counts[mech_key][phase_key] += 1

    result = {}
    for mech in mech_drugs:
        active_count = len(mech_drugs[mech])
        company_count = len(mech_companies[mech])
        crowding_index = active_count * company_count
        result[mech] = {
            "mechanism": mech,
            "active_count": active_count,
            "launched": mech_phase_counts[mech].get("launched", 0),
            "phase3": mech_phase_counts[mech].get("phase3", 0),
            "phase2": mech_phase_counts[mech].get("phase2", 0),
            "phase1": mech_phase_counts[mech].get("phase1", 0),
            "discovery": mech_phase_counts[mech].get("discovery", 0),
            "company_count": company_count,
            "crowding_index": crowding_index,
        }
    return result


# ---------------------------------------------------------------------------
# Momentum indicators
# ---------------------------------------------------------------------------

def compute_momentum(landscape_dir):
    deals_rows = load_deals(landscape_dir)
    deals_meta = load_deals_meta(landscape_dir)
    total_results = int(deals_meta.get("totalResults", 0))

    today = date.today()

    recent_count = 0
    prior_count = 0

    for row in deals_rows:
        d = parse_date(row.get("date") or "")
        if d is None:
            continue
        delta = (today - d).days
        if delta <= 180:
            recent_count += 1
        elif delta <= 360:
            prior_count += 1

    if prior_count > 0:
        deal_momentum = round(recent_count / prior_count, 3)
    elif recent_count > 0:
        deal_momentum = float("inf")
    else:
        deal_momentum = 0.0

    return {
        "total_deals_indexed": total_results,
        "fetched_deals": len(deals_rows),
        "recent_6mo": recent_count,
        "prior_6mo": prior_count,
        "deal_momentum": deal_momentum,
    }


# ---------------------------------------------------------------------------
# CSV output
# ---------------------------------------------------------------------------

def write_strategic_scores(landscape_dir, cpi_data):
    path = os.path.join(landscape_dir, "strategic_scores.csv")
    fieldnames = [
        "company", "cpi_tier", "cpi_score", "pipeline_breadth", "phase_score",
        "mechanism_diversity", "deal_activity", "trial_intensity", "position"
    ]
    rows = sorted(cpi_data.values(), key=lambda r: (-r["cpi_score"], r["company"]))
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


def write_mechanism_scores(landscape_dir, mech_data):
    path = os.path.join(landscape_dir, "mechanism_scores.csv")
    fieldnames = [
        "mechanism", "active_count", "launched", "phase3", "phase2",
        "phase1", "discovery", "company_count", "crowding_index"
    ]
    rows = sorted(mech_data.values(), key=lambda r: (-r["crowding_index"], r["mechanism"]))
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


# ---------------------------------------------------------------------------
# Markdown report
# ---------------------------------------------------------------------------

def render_markdown(landscape_dir, cpi_data, mech_data, momentum):
    now = datetime.now().strftime("%Y-%m-%d %H:%M UTC")
    ind = os.path.basename(os.path.normpath(landscape_dir)).replace("-", " ").title()

    lines = [
        f"# Strategic Intelligence: {ind}",
        f"",
        f"_Data freshness: {now}_",
        f"",
        f"*Preset: {preset['name']} — {preset['description']}*",
        f"",
    ]

    # CPI table — top 15
    lines += [
        "## Competitive Position Index (Top 15)",
        "",
        "| Rank | Company | Tier | CPI | Breadth | Phase Score | Mech Diversity | Deals | Trials | Position |",
        "|------|---------|------|-----|---------|-------------|----------------|-------|--------|----------|",
    ]
    sorted_cpi = sorted(cpi_data.values(), key=lambda r: (-r["cpi_score"], r["company"]))
    for i, row in enumerate(sorted_cpi[:15], 1):
        lines.append(
            f"| {i} | {row['company']} | {row['cpi_tier']} | {int(round(row['cpi_score']))} | {row['pipeline_breadth']} "
            f"| {row['phase_score']:.0f} | {row['mechanism_diversity']} "
            f"| {row['deal_activity']} | {row['trial_intensity']} | {row['position']} |"
        )

    lines += [""]

    # Position summary
    from collections import Counter
    pos_counts = Counter(r["position"] for r in cpi_data.values())
    lines += [
        "## Position Distribution",
        "",
        f"- **Leaders**: {pos_counts.get('Leader', 0)} companies",
        f"- **Challengers**: {pos_counts.get('Challenger', 0)} companies",
        f"- **Emerging**: {pos_counts.get('Emerging', 0)} companies",
        "",
    ]

    # Mechanism crowding — top 10
    lines += [
        "## Top 10 Most Crowded Mechanisms",
        "",
        "| Mechanism | Active Drugs | Companies | Crowding Index |",
        "|-----------|-------------|-----------|----------------|",
    ]
    sorted_mech = sorted(mech_data.values(), key=lambda r: (-r["crowding_index"], r["mechanism"]))
    for row in sorted_mech[:10]:
        mech_display = row["mechanism"][:60]
        lines.append(
            f"| {mech_display} | {row['active_count']} | {row['company_count']} | {row['crowding_index']} |"
        )

    lines += [""]

    # Momentum
    dm = momentum["deal_momentum"]
    dm_str = f"{dm:.2f}" if dm != float("inf") else "∞"
    lines += [
        "## Deal Momentum",
        "",
        f"- Total deals indexed: **{momentum['total_deals_indexed']}**",
        f"- Deals in sample: **{momentum['fetched_deals']}**",
        f"- Recent 6 months: **{momentum['recent_6mo']}**",
        f"- Prior 6 months: **{momentum['prior_6mo']}**",
        f"- Momentum ratio (recent/prior): **{dm_str}**",
        "",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 strategic_scoring.py <landscape_dir>", file=sys.stderr)
        sys.exit(1)

    landscape_dir = sys.argv[1].rstrip("/")

    if not os.path.isdir(landscape_dir):
        print(f"Error: directory not found: {landscape_dir}", file=sys.stderr)
        sys.exit(1)

    cpi_data = compute_cpi(landscape_dir)
    mech_data = compute_mechanism_scores(landscape_dir)
    momentum = compute_momentum(landscape_dir)

    scores_path = write_strategic_scores(landscape_dir, cpi_data)
    mech_path = write_mechanism_scores(landscape_dir, mech_data)

    md = render_markdown(landscape_dir, cpi_data, mech_data, momentum)
    print(md)

    print(f"\n<!-- Output: {scores_path} -->", file=sys.stderr)
    print(f"<!-- Output: {mech_path} -->", file=sys.stderr)


if __name__ == "__main__":
    main()
