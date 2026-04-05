#!/usr/bin/env python3
"""
scenario_library.py — Counterfactual scenario analysis for landscape data.

Usage: python3 scenario_library.py <landscape_dir> <indication_name> [--scenarios all|<name,...>]

Available scenarios:
  top_exit              — Top company exits; ranks beneficiaries by specialty-buyer-fit
  crowded_consolidation — Crowded mechanism consolidates to top-3 winners
  loe_wave              — LOE wave simulation using loe_metrics.csv (run loe_analysis.py first)
  new_entrant_disruption — Novel well-funded entrant targets white-space mechanisms
  pivotal_failure       — Top-3 company's flagship phase-3 drug fails

Pure computation, stdlib only. Output markdown to stdout.
"""

import csv
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _audit_trail import (
    build_audit_trail, render_audit_trail_markdown, write_audit_trail_json,
    compute_freshness, render_freshness_warning, write_freshness_json,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def read_csv_safe(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def safe_float(val, default=0.0):
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def safe_int(val, default=0):
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


PHASE_FILES = ["launched", "phase3", "phase2", "phase1", "discovery"]
PHASE_WEIGHTS = {"launched": 5, "phase3": 4, "phase2": 3, "phase1": 2, "discovery": 1}


def load_drug_rows(landscape_dir):
    rows = []
    for phase_key in PHASE_FILES:
        path = os.path.join(landscape_dir, f"{phase_key}.csv")
        for row in read_csv_safe(path):
            row["_phase_key"] = phase_key
            rows.append(row)
    return rows


def get_company_mechanisms(drug_rows):
    """Returns dict: company -> set of mechanism strings (lowercased)."""
    result = defaultdict(set)
    for row in drug_rows:
        company = (row.get("company") or "").strip()
        mechs_raw = (row.get("mechanism") or "").strip()
        if not company or not mechs_raw:
            continue
        for m in mechs_raw.split(";"):
            m = m.strip().lower()
            if m:
                result[company].add(m)
    return result


def get_company_phase_counts(drug_rows):
    """Returns dict: company -> {phase_key -> count}."""
    result = defaultdict(lambda: defaultdict(int))
    for row in drug_rows:
        company = (row.get("company") or "").strip()
        if company:
            result[company][row["_phase_key"]] += 1
    return result


# ---------------------------------------------------------------------------
# Scenario 1: top_exit
# ---------------------------------------------------------------------------

def scenario_top_exit(landscape_dir, indication_name):
    """
    Top company exits the indication.
    Beneficiary score = overlap_count * (1 / (1 + own_phase3plus_count / 5))
    — specialty-buyer-fit formula: rewards companies with overlapping mechanisms
      but not yet saturated in late-stage.
    """
    scores = read_csv_safe(os.path.join(landscape_dir, "strategic_scores.csv"))
    drug_rows = load_drug_rows(landscape_dir)

    if not scores:
        return "## Scenario: Top Company Exit\n\n_No strategic_scores.csv found. Run strategic_scoring.py first._\n"

    top_company = scores[0].get("company", "").strip()
    top_cpi = safe_float(scores[0].get("cpi_score", 0))

    # Mechanisms held by top company
    top_drugs = [r for r in drug_rows if (r.get("company") or "").strip() == top_company]
    top_mechs = set()
    for d in top_drugs:
        for m in (d.get("mechanism") or "").split(";"):
            m = m.strip().lower()
            if m:
                top_mechs.add(m)

    # Phase counts per company (from drug rows, excluding top company)
    company_mechs = get_company_mechanisms(drug_rows)
    company_phase_counts = get_company_phase_counts(drug_rows)

    # Count total drugs per company in this indication (for thin-pipeline tiebreak)
    company_total_drug_count = Counter()
    for row in drug_rows:
        company = (row.get("company") or "").strip()
        if company:
            company_total_drug_count[company] += 1

    beneficiary_scores = {}
    for row in scores[1:]:  # skip top company
        company = (row.get("company") or "").strip()
        if not company:
            continue
        overlap = len(company_mechs[company] & top_mechs)
        if overlap == 0:
            continue
        phase3plus = (company_phase_counts[company].get("phase3", 0)
                      + company_phase_counts[company].get("launched", 0))
        total_drugs = company_total_drug_count.get(company, 0)
        # specialty-fit: overlap × (1/(1+phase3plus/5)) × (1 + 0.01 × min(total_drugs, 5))
        # Small engagement multiplier breaks ties on thin pipelines (where all companies have
        # phase3plus=0 and identical base fit=1.0) without overriding overlap-count differences.
        # max multiplier = 1.05 — marginal on mature pipelines, decisive only for true ties.
        fit_score = overlap * (1.0 / (1 + phase3plus / 5.0)) * (1.0 + 0.01 * min(total_drugs, 5))
        beneficiary_scores[company] = round(fit_score, 3)

    top5 = sorted(beneficiary_scores.items(), key=lambda x: x[1], reverse=True)[:5]

    # Confidence scoring for top_exit
    # HIGH if top score >= 2× 2nd; MEDIUM if >= 1.25×; LOW otherwise; ABSTAIN if top 3 within 0.1
    confidence = "LOW"
    abstain = False
    if len(top5) >= 3:
        s1, s2, s3 = top5[0][1], top5[1][1], top5[2][1]
        if abs(s1 - s3) <= 0.1:
            abstain = True
            confidence = "ABSTAIN"
        elif s2 > 0 and s1 >= 2 * s2:
            confidence = "HIGH"
        elif s2 > 0 and s1 >= 1.25 * s2:
            confidence = "MEDIUM"
    elif len(top5) == 2:
        s1, s2 = top5[0][1], top5[1][1]
        if abs(s1 - s2) <= 0.1:
            abstain = True
            confidence = "ABSTAIN"
        elif s2 > 0 and s1 >= 2 * s2:
            confidence = "HIGH"
        elif s2 > 0 and s1 >= 1.25 * s2:
            confidence = "MEDIUM"
    elif len(top5) == 1:
        confidence = "LOW"

    lines = [
        f"## Scenario 1: Top Company Exit — confidence: {confidence}",
        "",
        f"*Preset: top_exit — Specialty-buyer-fit formula: score = overlap × 1/(1 + phase3plus/5)*",
        f"*Assumption: Overlap × specialty-buyer-fit ranking; does not model deal prices.*",
        "",
        f"**Exiting company:** {top_company} (CPI: {top_cpi:.1f})",
        f"**Programs removed:** {len(top_drugs)} drugs across {len(top_mechs)} mechanisms",
        "",
    ]

    if abstain:
        lines += [
            "⚠ **Insufficient signal — thin pipeline or flat distribution.** Scenario does not produce a distinguishable ranking. Do not act on this scenario alone.",
            "",
            "→ **Action:** Do not act on this scenario; gather more signal (more drugs, more deals, more trials).",
        ]
    else:
        lines += [
            "**Top 5 beneficiaries** (companies with overlapping mechanisms, weighted by pipeline fit):",
            "",
            "| Rank | Company | Mechanism Overlap | Phase3+ Count | Fit Score |",
            "|------|---------|------------------|---------------|-----------|",
        ]

        for i, (company, score) in enumerate(top5, 1):
            overlap = len(company_mechs[company] & top_mechs)
            phase3plus = (company_phase_counts[company].get("phase3", 0)
                          + company_phase_counts[company].get("launched", 0))
            lines.append(f"| {i} | {company[:40]} | {overlap} | {phase3plus} | {score:.3f} |")

        if not top5:
            lines.append("_No other companies share mechanisms with the top company._")

        top_beneficiary = top5[0][0] if top5 else "unknown"
        lines += [
            "",
            f"→ **Action:** Prioritize business development outreach to {top_beneficiary} as primary acquirer. Confidence: {confidence}. Key assumption: mechanism overlap is a reliable proxy for strategic fit.",
        ]

    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Scenario 2: crowded_consolidation
# ---------------------------------------------------------------------------

def scenario_crowded_consolidation(landscape_dir, indication_name):
    """
    Most crowded mechanism consolidates: top-3 companies win, rest exit.
    """
    mech_scores = read_csv_safe(os.path.join(landscape_dir, "mechanism_scores.csv"))
    drug_rows = load_drug_rows(landscape_dir)

    if not mech_scores:
        return "## Scenario: Crowded Consolidation\n\n_No mechanism_scores.csv found. Run strategic_scoring.py first._\n"

    # Most crowded mechanism
    top_mech = mech_scores[0]
    mech_name = top_mech.get("mechanism", "?")
    mech_drug_count = safe_int(top_mech.get("active_count", 0))
    mech_company_count = safe_int(top_mech.get("company_count", 0))

    # Companies in that mechanism, ranked by phase score within mechanism
    mech_company_phase_score = defaultdict(float)
    mech_company_drug_count = defaultdict(int)
    for row in drug_rows:
        mechs_raw = (row.get("mechanism") or "").strip()
        company = (row.get("company") or "").strip()
        if not company:
            continue
        for m in mechs_raw.split(";"):
            if m.strip().lower() == mech_name.lower():
                mech_company_phase_score[company] += PHASE_WEIGHTS.get(row["_phase_key"], 1)
                mech_company_drug_count[company] += 1

    ranked_companies = sorted(mech_company_phase_score.items(), key=lambda x: x[1], reverse=True)
    winners = ranked_companies[:3]
    losers = ranked_companies[3:]

    drugs_lost = sum(mech_company_drug_count[c] for c, _ in losers)
    companies_exiting = len(losers)

    # Exposure: % of pipeline in this crowded mechanism
    company_phase_counts = get_company_phase_counts(drug_rows)
    company_total = {c: sum(v for v in company_phase_counts[c].values()) for c in mech_company_phase_score}

    all_exposed = sorted(
        [(c, mech_company_drug_count[c], company_total.get(c, 1))
         for c in mech_company_phase_score],
        key=lambda x: x[1] / x[2],
        reverse=True
    )
    top5_exposed = all_exposed[:5]  # show top 5 of N; total shown in header

    # Confidence scoring for crowded_consolidation
    # HIGH if top mechanism has >= 2× active drug count of #2; MEDIUM if >= 1.5×; LOW otherwise
    second_mech_count = safe_int(mech_scores[1].get("active_count", 0)) if len(mech_scores) > 1 else 0
    if second_mech_count > 0 and mech_drug_count >= 2 * second_mech_count:
        confidence = "HIGH"
    elif second_mech_count > 0 and mech_drug_count >= 1.5 * second_mech_count:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    lines = [
        f"## Scenario 2: Crowded Mechanism Consolidation — confidence: {confidence}",
        "",
        f"*Preset: crowded_consolidation — Top-3 companies win; remainder exit.*",
        f"*Assumption: Phase-score ranking determines winners; no modeling of IP or regulatory moats.*",
        "",
        f"**Crowded mechanism:** {mech_name}",
        f"**Scope:** {mech_drug_count} active drugs, {mech_company_count} companies",
        "",
        "**Likely winners** (highest phase score in this mechanism):",
        "",
        "| Rank | Company | Mechanism Phase Score | Drugs in Mechanism |",
        "|------|---------|----------------------|--------------------|",
    ]

    for i, (company, score) in enumerate(winners, 1):
        lines.append(f"| {i} | {company[:40]} | {score:.0f} | {mech_company_drug_count[company]} |")

    lines += [
        "",
        f"**Shakeout:** {companies_exiting} companies exit → {drugs_lost} drugs/programs removed",
        "",
        f"**Most exposed companies** (top {len(top5_exposed)} of {len(all_exposed)} — % of total pipeline in this mechanism):",
        "",
        "| Company | Mech Drugs | Total Pipeline | Exposure % |",
        "|---------|-----------|----------------|------------|",
    ]

    for company, mech_drugs, total in top5_exposed:
        pct = mech_drugs / total * 100 if total > 0 else 0
        lines.append(f"| {company[:40]} | {mech_drugs} | {total} | {pct:.1f}% |")

    top_winner = winners[0][0] if winners else "unknown"
    lines += [
        "",
        f"→ **Action:** Monitor {top_winner} as consolidation frontrunner; assess exposed companies as acquisition or partnership targets. Confidence: {confidence}. Key assumption: phase-score rank is a reliable predictor of consolidation survival.",
    ]

    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Scenario 3: loe_wave
# ---------------------------------------------------------------------------

def scenario_loe_wave(landscape_dir, indication_name):
    """
    LOE wave simulation. Requires loe_metrics.csv (run loe_analysis.py first).
    """
    loe_path = os.path.join(landscape_dir, "loe_metrics.csv")
    loe_metrics = read_csv_safe(loe_path)

    if not loe_metrics:
        return (
            "## Scenario 3: LOE Wave\n\n"
            "_loe_metrics.csv not found. Run loe_analysis.py first to generate LOE data._\n"
        )

    # Sort by loe_exposure_pct descending
    loe_metrics.sort(key=lambda r: safe_float(r.get("loe_exposure_pct", 0)), reverse=True)
    top5 = loe_metrics[:5]
    high_risk = [r for r in loe_metrics if r.get("risk_flag") == "HIGH"]

    # Confidence scoring for loe_wave
    # HIGH if any company has refill_gap >= 5 AND loe_exposure_pct > 0.6
    # MEDIUM if >= 3 AND > 0.5
    # LOW otherwise
    # ABSTAIN if no companies have launched drugs
    companies_with_launched = [r for r in loe_metrics if safe_int(r.get("launched", 0)) > 0]
    if not companies_with_launched:
        confidence = "ABSTAIN"
        abstain = True
    else:
        abstain = False
        high_signal = any(
            safe_int(r.get("refill_gap", 0)) >= 5 and safe_float(r.get("loe_exposure_pct", 0)) > 0.6
            for r in loe_metrics
        )
        medium_signal = any(
            safe_int(r.get("refill_gap", 0)) >= 3 and safe_float(r.get("loe_exposure_pct", 0)) > 0.5
            for r in loe_metrics
        )
        if high_signal:
            confidence = "HIGH"
        elif medium_signal:
            confidence = "MEDIUM"
        else:
            confidence = "LOW"

    lines = [
        f"## Scenario 3: LOE Wave — confidence: {confidence}",
        "",
        f"*Preset: loe_wave — Proxy: all launched drugs treated as LOE-exposed; no exact patent dates.*",
        f"*Assumption: refill_gap = launched - phase3; positive gap = insufficient pipeline backfill.*",
        "",
    ]

    if abstain:
        lines += [
            "⚠ **Insufficient signal — thin pipeline or flat distribution.** Scenario does not produce a distinguishable ranking. Do not act on this scenario alone.",
            "",
            "→ **Action:** Do not act on this scenario; gather more signal (more drugs, more deals, more trials).",
        ]
    else:
        lines += [
            "**Top 5 companies by LOE exposure:**",
            "",
            "| Rank | Company | Launched | Phase 3 | Refill Gap | LOE Exposure % | Risk |",
            "|------|---------|---------|---------|------------|----------------|------|",
        ]

        for i, row in enumerate(top5, 1):
            launched = safe_int(row.get("launched", 0))
            phase3 = safe_int(row.get("phase3", 0))
            refill_gap = safe_int(row.get("refill_gap", launched - phase3))
            loe_pct = safe_float(row.get("loe_exposure_pct", 0)) * 100
            risk = row.get("risk_flag", "low")
            risk_display = "**HIGH**" if risk == "HIGH" else "low"
            lines.append(
                f"| {i} | {row.get('company','?')[:40]} | {launched} | {phase3} "
                f"| {refill_gap:+d} | {loe_pct:.1f}% | {risk_display} |"
            )

        top_loe_company = top5[0].get("company", "unknown") if top5 else "unknown"
        lines += [
            "",
            f"**{len(high_risk)} of {len(loe_metrics)} companies** face HIGH LOE risk "
            f"(refill_gap ≥ 3 or exposure > 50%).",
            "",
            "**Pipeline refill gap interpretation:**",
            "- Positive gap → launched portfolio outpaces pipeline backfill → revenue cliff risk",
            "- Negative gap → pipeline exceeds launched base → healthy replacement cadence",
            "",
            f"→ **Action:** Engage {top_loe_company} as a potential in-licensing or partnership target given LOE exposure. Confidence: {confidence}. Key assumption: launched drug count is a reliable proxy for LOE exposure without exact patent expiry dates.",
        ]

    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Scenario 4: new_entrant_disruption
# ---------------------------------------------------------------------------

def scenario_new_entrant_disruption(landscape_dir, indication_name):
    """
    Well-funded new entrant targets white-space or low-company mechanisms.
    Incumbents most threatened = high-CPI companies that don't touch that mechanism.
    """
    opportunities = read_csv_safe(os.path.join(landscape_dir, "opportunity_matrix.csv"))
    scores = read_csv_safe(os.path.join(landscape_dir, "strategic_scores.csv"))
    drug_rows = load_drug_rows(landscape_dir)

    if not opportunities:
        return "## Scenario: New Entrant Disruption\n\n_No opportunity_matrix.csv found._\n"

    # White space: status=White Space or (opportunity_score>0.05 with <=2 companies)
    targets = [
        r for r in opportunities
        if r.get("status") == "White Space"
        or (safe_float(r.get("opportunity_score", 0)) > 0.05 and safe_int(r.get("companies", 99)) <= 2)
    ]
    targets.sort(key=lambda r: safe_float(r.get("opportunity_score", 0)), reverse=True)
    targets = targets[:3]

    # Confidence scoring for new_entrant_disruption
    # HIGH if white-space mechanism has opp_score >= 0.5 AND >= 3 incumbents identifiable
    # MEDIUM if opp_score >= 0.3
    # LOW otherwise
    # ABSTAIN if no white-space mechanisms exist
    original_targets = [
        r for r in opportunities
        if r.get("status") == "White Space"
        or (safe_float(r.get("opportunity_score", 0)) > 0.05 and safe_int(r.get("companies", 99)) <= 2)
    ]
    if not original_targets:
        confidence = "ABSTAIN"
        abstain = True
    else:
        abstain = False
        top_opp = original_targets[0] if original_targets else None
        top_opp_score = safe_float(top_opp.get("opportunity_score", 0)) if top_opp else 0.0
        # Count identifiable incumbents for top target (done below after company_mechs built)
        # Defer to after company_mechs is available — placeholder, updated below
        confidence = "LOW"
        _top_opp_score_for_conf = top_opp_score

    if not targets:
        # Fall back to lowest-company mechanisms with any drugs
        targets = sorted(
            [r for r in opportunities if safe_int(r.get("total", 0)) > 0],
            key=lambda r: safe_int(r.get("companies", 99))
        )[:3]

    company_mechs = get_company_mechanisms(drug_rows)

    # Finalize confidence now that company_mechs is available
    if not abstain:
        top_target = original_targets[0] if original_targets else (targets[0] if targets else None)
        top_opp_score_final = safe_float(top_target.get("opportunity_score", 0)) if top_target else 0.0
        top_mech_lower = (top_target.get("mechanism", "") if top_target else "").lower()
        incumbents_count = sum(
            1 for row in scores[:10]
            if top_mech_lower not in company_mechs.get((row.get("company") or "").strip(), set())
        )
        if top_opp_score_final >= 0.5 and incumbents_count >= 3:
            confidence = "HIGH"
        elif top_opp_score_final >= 0.3:
            confidence = "MEDIUM"
        else:
            confidence = "LOW"

    lines = [
        f"## Scenario 4: New Entrant Disruption — confidence: {confidence}",
        "",
        f"*Preset: new_entrant_disruption — Well-funded entrant exploits white-space mechanisms.*",
        f"*Assumption: Incumbents not present in a mechanism are most threatened by a new entrant claiming it.*",
        "",
    ]

    if abstain:
        lines += [
            "⚠ **Insufficient signal — thin pipeline or flat distribution.** Scenario does not produce a distinguishable ranking. Do not act on this scenario alone.",
            "",
            "→ **Action:** Do not act on this scenario; gather more signal (more drugs, more deals, more trials).",
        ]
        lines.append("")
        return "\n".join(lines)

    lines.append("**Target white-space / low-competition mechanisms:**")
    lines.append("")

    for mech_row in targets:
        mech_name = mech_row.get("mechanism", "?")
        mech_lower = mech_name.lower()
        status = mech_row.get("status", "?")
        companies_in_mech = safe_int(mech_row.get("companies", 0))
        opp_score = safe_float(mech_row.get("opportunity_score", 0))

        # High-CPI incumbents NOT in this mechanism
        threatened = []
        for row in scores[:10]:
            company = (row.get("company") or "").strip()
            if not company:
                continue
            if mech_lower not in company_mechs.get(company, set()):
                cpi = safe_float(row.get("cpi_score", 0))
                threatened.append((company, cpi))
        total_threatened = len(threatened)
        threatened = threatened[:4]  # show top 4 of N; total shown in label

        lines += [
            f"### Mechanism: {mech_name}",
            f"- **Status:** {status} | **Companies active:** {companies_in_mech} | **Opportunity score:** {opp_score:.4f}",
            f"- **Most threatened incumbents** (top {len(threatened)} of {total_threatened} — high CPI, no presence in this mechanism):",
        ]
        if threatened:
            for company, cpi in threatened:
                lines.append(f"  - {company[:45]} (CPI: {cpi:.1f})")
        else:
            lines.append("  - _All top-10 companies already active in this mechanism._")
        lines.append("")

    top_mech_name = targets[0].get("mechanism", "the identified white-space mechanism") if targets else "the identified mechanism"
    lines += [
        f"→ **Action:** Track new entrant filings in {top_mech_name}; alert threatened incumbents to prepare competitive response. Confidence: {confidence}. Key assumption: opportunity score captures unmet mechanism-level need.",
        "",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Scenario 5: pivotal_failure
# ---------------------------------------------------------------------------

def scenario_pivotal_failure(landscape_dir, indication_name):
    """
    A top-3 company's flagship phase-3 drug fails.
    Remove that drug + its mechanisms from phase 3, show pipeline composition shifts.
    """
    scores = read_csv_safe(os.path.join(landscape_dir, "strategic_scores.csv"))
    drug_rows = load_drug_rows(landscape_dir)

    if not scores:
        return "## Scenario: Pivotal Failure\n\n_No strategic_scores.csv found._\n"

    # Top-3 companies by CPI
    top3 = [r.get("company", "").strip() for r in scores[:3] if r.get("company")]
    if not top3:
        return "## Scenario: Pivotal Failure\n\n_Insufficient company data._\n"

    target_company = top3[0]  # flagship = #1 ranked company

    # Find their highest-weighted phase-3 drug
    p3_drugs = [r for r in drug_rows
                if r["_phase_key"] == "phase3"
                and (r.get("company") or "").strip() == target_company]

    if not p3_drugs:
        # Try second or third company
        for candidate in top3[1:]:
            p3_drugs = [r for r in drug_rows
                        if r["_phase_key"] == "phase3"
                        and (r.get("company") or "").strip() == candidate]
            if p3_drugs:
                target_company = candidate
                break

    if not p3_drugs:
        return (
            "## Scenario 5: Pivotal Failure\n\n"
            f"_No phase-3 drugs found for top-3 companies ({', '.join(top3)})._\n"
        )

    # Flagship = first phase-3 drug for that company
    flagship = p3_drugs[0]
    flagship_name = (flagship.get("name") or flagship.get("id") or "unnamed drug").strip()
    flagship_mechs = set()
    for m in (flagship.get("mechanism") or "").split(";"):
        m = m.strip().lower()
        if m:
            flagship_mechs.add(m)

    # Before: phase-3 mechanism distribution
    p3_mech_before = Counter()
    for row in drug_rows:
        if row["_phase_key"] != "phase3":
            continue
        for m in (row.get("mechanism") or "").split(";"):
            m = m.strip().lower()
            if m:
                p3_mech_before[m] += 1

    total_p3_before = sum(p3_mech_before.values())

    # After: remove flagship drug's mechanisms
    p3_mech_after = Counter(p3_mech_before)
    for m in flagship_mechs:
        if m in p3_mech_after:
            p3_mech_after[m] -= 1
            if p3_mech_after[m] <= 0:
                del p3_mech_after[m]

    total_p3_after = sum(p3_mech_after.values())

    # Company ranking shift: remove this drug from phase score
    company_phase_scores_before = defaultdict(float)
    company_phase_scores_after = defaultdict(float)
    drug_id = (flagship.get("id") or flagship.get("name") or "").strip()

    for row in drug_rows:
        company = (row.get("company") or "").strip()
        row_drug_id = (row.get("id") or row.get("name") or "").strip()
        weight = PHASE_WEIGHTS.get(row["_phase_key"], 1)
        company_phase_scores_before[company] += weight
        # After: exclude the flagship drug
        if row_drug_id != drug_id or (row.get("company") or "").strip() != target_company:
            company_phase_scores_after[company] += weight

    # Top-5 ranking before and after
    rank_before = sorted(company_phase_scores_before.items(), key=lambda x: x[1], reverse=True)[:5]
    rank_after = sorted(company_phase_scores_after.items(), key=lambda x: x[1], reverse=True)[:5]

    # Top mech share before/after
    top_mech_before = p3_mech_before.most_common(1)
    top_mech_after = p3_mech_after.most_common(1)

    # Confidence scoring for pivotal_failure
    # HIGH if top-3 ranking shifts after the failure
    # MEDIUM if only share shifts but ranks hold
    # LOW if neither
    after_rank_map = {company: (i, score) for i, (company, score) in enumerate(rank_after, 1)}
    rank_before_map = {company: i for i, (company, _) in enumerate(rank_before, 1)}

    top3_before = [company for company, _ in rank_before[:3]]
    rank_shifted = False
    share_shifted = False

    for company, score_before in rank_before[:3]:
        after_rank, score_after = after_rank_map.get(company, (rank_before_map[company], score_before))
        if isinstance(after_rank, int) and after_rank != rank_before_map[company]:
            rank_shifted = True
        if abs(score_after - score_before) > 0:
            share_shifted = True

    if rank_shifted:
        confidence = "HIGH"
    elif share_shifted:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    lines = [
        f"## Scenario 5: Pivotal Failure — confidence: {confidence}",
        "",
        f"*Preset: pivotal_failure — Removes flagship phase-3 drug and recalculates pipeline composition.*",
        f"*Assumption: Drug removal is immediate; no out-licensing or salvage scenarios modeled.*",
        "",
        f"**Company:** {target_company}",
        f"**Flagship drug:** {flagship_name}",
        f"**Mechanisms affected:** {', '.join(sorted(flagship_mechs)) if flagship_mechs else 'unknown'}",
        "",
        f"**Phase-3 pipeline: {total_p3_before} drugs before → {total_p3_after} drugs after**",
        "",
    ]

    if top_mech_before:
        tm_name, tm_count = top_mech_before[0]
        tm_share_before = tm_count / total_p3_before * 100 if total_p3_before else 0
        lines.append(f"- Top mechanism before: **{tm_name}** ({tm_count} drugs, {tm_share_before:.1f}% share)")

    if top_mech_after:
        tm_name, tm_count = top_mech_after[0]
        tm_share_after = tm_count / total_p3_after * 100 if total_p3_after else 0
        lines.append(f"- Top mechanism after: **{tm_name}** ({tm_count} drugs, {tm_share_after:.1f}% share)")

    lines += [
        "",
        "**Company ranking shift (by total phase score):**",
        "",
        "| Rank Before | Company | Score Before | Rank After | Score After |",
        "|------------|---------|-------------|------------|-------------|",
    ]

    for i, (company, score_before) in enumerate(rank_before, 1):
        after_rank, score_after = after_rank_map.get(company, ("—", score_before))
        lines.append(
            f"| {i} | {company[:35]} | {score_before:.0f} | {after_rank} | {score_after:.0f} |"
        )

    # Identify new #1 after failure if rank shifted
    new_leader = rank_after[0][0] if rank_after else "unknown"
    lines += [
        "",
        f"→ **Action:** If {target_company}'s flagship fails, reassess {new_leader} as new pipeline leader; review partnership and competitive positioning. Confidence: {confidence}. Key assumption: phase-score is a reliable proxy for competitive standing.",
        "",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

SCENARIO_MAP = {
    "top_exit": scenario_top_exit,
    "crowded_consolidation": scenario_crowded_consolidation,
    "loe_wave": scenario_loe_wave,
    "new_entrant_disruption": scenario_new_entrant_disruption,
    "pivotal_failure": scenario_pivotal_failure,
}


def main():
    if len(sys.argv) < 3:
        print(
            "Usage: python3 scenario_library.py <landscape_dir> <indication_name> [--scenarios all|<name,...>]",
            file=sys.stderr,
        )
        print(f"Available scenarios: {', '.join(SCENARIO_MAP)}", file=sys.stderr)
        sys.exit(1)

    landscape_dir = sys.argv[1].rstrip("/")
    indication_name = sys.argv[2]

    # Parse --scenarios flag
    selected = list(SCENARIO_MAP.keys())  # default: all
    for i, arg in enumerate(sys.argv[3:], 3):
        if arg == "--scenarios" and i + 1 < len(sys.argv):
            val = sys.argv[i + 1]
            if val != "all":
                selected = [s.strip() for s in val.split(",") if s.strip() in SCENARIO_MAP]
            break

    if not os.path.isdir(landscape_dir):
        print(f"Error: directory not found: {landscape_dir}", file=sys.stderr)
        sys.exit(1)

    from datetime import datetime
    now = datetime.now().strftime("%Y-%m-%d %H:%M UTC")

    print(f"# Scenario Library: {indication_name}")
    print(f"")
    print(f"*Generated: {now}*")
    print(f"*Scenarios: {', '.join(selected)}*")
    print(f"")
    print("> **Reading this output:** CPI = Competitive Position Index, scale 0–100, higher is better. Tier A/B/C/D are **relative to this indication only** (A = top 10%, D = bottom 50%) — not comparable across diseases. White Space = opportunity gap with no current late-stage competition. ABSTAIN confidence = data too thin to rank; **not** the same as \"weakest recommendation\". Full definitions: `docs/glossary.md`.")
    print(f"")

    _freshness = compute_freshness(landscape_dir)
    _freshness_warning = render_freshness_warning(_freshness)
    if _freshness_warning:
        print(_freshness_warning.rstrip("\n"))
        print()

    print("---")
    print("")

    for name in selected:
        fn = SCENARIO_MAP[name]
        output = fn(landscape_dir, indication_name)
        print(output)
        print("---")
        print("")

    audit = build_audit_trail(
        script_name="scenario_library.py",
        landscape_dir=landscape_dir,
        preset_name=", ".join(selected) if selected else None,
        preset_weights=None,
    )
    print(render_audit_trail_markdown(audit))
    write_audit_trail_json(audit, landscape_dir, "scenario_library.py")
    write_freshness_json(_freshness, landscape_dir)


if __name__ == "__main__":
    main()
