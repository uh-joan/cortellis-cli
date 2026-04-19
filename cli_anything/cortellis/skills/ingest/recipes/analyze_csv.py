#!/usr/bin/env python3
"""
analyze_csv.py — Analyze a structured CSV and produce a narrative intelligence article.

Uses Python for fact extraction + Claude CLI (Haiku) for narrative generation.
Falls back to a formatted markdown table if Claude is unavailable.
"""

import csv
import os
import re
import shutil
import subprocess
from pathlib import Path


# ── Type detection ─────────────────────────────────────────────────────────────

def detect_csv_type(headers: list, filename: str) -> str:
    h = " ".join(str(x) for x in headers).lower()
    f = filename.lower()

    if any(x in h for x in ["sales", "revenue"]) or "$" in h:
        return "sales_forecast"
    if any(x in h for x in ["patient share", " share"]):
        return "patient_share"
    if any(x in h for x in ["prevalence", " cases", "population", "epidemiol"]):
        return "epidemiology"
    if any(x in h for x in ["price", "cost", "pptd", "per treated"]):
        return "pricing"

    # Fallback to filename
    for kw, t in [("sales", "sales_forecast"), ("share", "patient_share"),
                  ("epidem", "epidemiology"), ("prevalence", "epidemiology"),
                  ("price", "pricing"), ("forecast", "sales_forecast")]:
        if kw in f:
            return t

    return "generic"


# ── Numeric helpers ────────────────────────────────────────────────────────────

def _parse_val(v) -> float | None:
    if v is None:
        return None
    s = str(v).strip()
    if s in ("", "-", "N/A", "n/a", "—"):
        return None
    cleaned = re.sub(r"[$,\s%]", "", s)
    try:
        return float(cleaned)
    except ValueError:
        return None


def _fmt(v: float | None, dollar: bool = True) -> str:
    if v is None:
        return "—"
    prefix = "$" if dollar else ""
    if abs(v) >= 1_000_000:
        return f"{prefix}{v/1_000_000:.1f}T"
    if abs(v) >= 1_000:
        return f"{prefix}{v/1_000:.1f}B"
    if abs(v) >= 1:
        return f"{prefix}{v:.1f}M"
    return f"{prefix}{v:.2f}M"


def _year_cols(headers: list) -> list:
    """Return [(index, year_str)] for year columns."""
    result = []
    for i, h in enumerate(headers):
        if re.match(r"^(20\d{2})$", str(h).strip()):
            result.append((i, str(h).strip()))
    return result


# ── Facts extraction ───────────────────────────────────────────────────────────

def extract_facts(rows: list, csv_type: str) -> dict:
    if not rows:
        return {}

    headers = rows[0]
    ycols = _year_cols(headers)
    facts = {
        "type": csv_type,
        "years": [y for _, y in ycols],
        "year_range": f"{ycols[0][1]}–{ycols[-1][1]}" if len(ycols) >= 2 else "",
    }

    if csv_type == "sales_forecast" and ycols:
        total_vals = None
        drug_rows = []

        for row in rows[1:]:
            if not row or not row[0].strip():
                continue
            label = row[0].strip()
            if label.lower() in ("brand", "generic", "sales", ""):
                continue

            vals = {}
            for idx, yr in ycols:
                if idx < len(row):
                    v = _parse_val(row[idx])
                    if v is not None:
                        vals[yr] = v

            if not vals:
                continue

            if any(x in label.lower() for x in ["total", "market"]) and total_vals is None:
                total_vals = (label, vals)
            else:
                drug_rows.append((label, vals))

        if total_vals:
            _, vals = total_vals
            pts = sorted(vals.items())
            if pts:
                start_yr, start_v = pts[0]
                end_yr, end_v = pts[-1]
                peak_yr, peak_v = max(pts, key=lambda x: x[1])
                facts["total_market"] = {
                    "start": (start_yr, start_v),
                    "end": (end_yr, end_v),
                    "peak": (peak_yr, peak_v),
                }
                n = int(end_yr) - int(start_yr)
                if n > 0 and start_v and end_v:
                    facts["cagr"] = round(((end_v / start_v) ** (1 / n) - 1) * 100, 1)

        # Rank drugs by peak value, filter noise
        ranked = []
        for label, vals in drug_rows:
            peak = max(vals.values(), default=0)
            if peak > 50:  # >$50M threshold
                ranked.append((label, vals, peak))
        ranked.sort(key=lambda x: x[2], reverse=True)
        facts["drugs"] = [(label, vals) for label, vals, _ in ranked[:10]]

    elif csv_type == "epidemiology" and ycols:
        metrics = []
        for row in rows[1:]:
            if not row or not row[0].strip():
                continue
            label = row[0].strip()
            vals = {yr: _parse_val(row[idx]) for idx, yr in ycols if idx < len(row)}
            vals = {k: v for k, v in vals.items() if v is not None}
            if vals:
                metrics.append((label, vals))
        facts["metrics"] = metrics[:20]

    elif csv_type in ("patient_share", "pricing") and ycols:
        entries = []
        for row in rows[1:]:
            if not row or not row[0].strip():
                continue
            label = row[0].strip()
            vals = {yr: _parse_val(row[idx]) for idx, yr in ycols if idx < len(row)}
            vals = {k: v for k, v in vals.items() if v is not None}
            if vals:
                entries.append((label, vals))
        facts["entries"] = entries[:15]

    return facts


# ── Prompts ────────────────────────────────────────────────────────────────────

_SYSTEM = {
    "sales_forecast": (
        "You are a pharmaceutical market intelligence analyst. "
        "Write a concise intelligence briefing (400–500 words, markdown) from this market forecast data.\n"
        "Include:\n"
        "1. Headline: total market size at start/peak/end with CAGR\n"
        "2. Markdown table: top drugs with 2025/2030/2034 values and a Trend column "
        "(e.g. Peak 2030, LOE erosion / Rising / Long-term winner)\n"
        "3. 4–5 strategic insights (class dynamics, LOE timings, emerging threats, generics)\n"
        "4. One-paragraph Key Takeaway for a BD/strategy audience\n"
        "Be specific with numbers. Use bold for key figures. No preamble."
    ),
    "patient_share": (
        "You are a pharmaceutical market intelligence analyst. "
        "Write a concise intelligence briefing (300–400 words, markdown) from this patient share data.\n"
        "Include: share leaders and trajectory, notable share shifts, drugs gaining vs losing share, "
        "strategic positioning implications. Be specific with numbers. No preamble."
    ),
    "epidemiology": (
        "You are a pharmaceutical market intelligence analyst. "
        "Write a concise intelligence briefing (300–400 words, markdown) from this epidemiology data.\n"
        "Include: total patient population, prevalence trends, treatment gap (diagnosed vs treated), "
        "geographic variation if present, market sizing implications. Be specific. No preamble."
    ),
    "pricing": (
        "You are a pharmaceutical market intelligence analyst. "
        "Write a concise intelligence briefing (300–400 words, markdown) from this pricing data.\n"
        "Include: current price levels, trajectory, comparative positioning, generic/payer pressure signals. "
        "Be specific with numbers. No preamble."
    ),
    "generic": (
        "You are a pharmaceutical market intelligence analyst. "
        "Write a concise 200–300 word markdown summary of this data. "
        "Identify the key metric, trend over time, and top 3 strategic implications. No preamble."
    ),
}


def _build_prompt(facts: dict, rows: list, filename: str) -> str:
    csv_type = facts.get("type", "generic")
    system = _SYSTEM.get(csv_type, _SYSTEM["generic"])

    lines = [f"Filename: {filename}", f"Data type: {csv_type}"]

    if facts.get("year_range"):
        lines.append(f"Period: {facts['year_range']}")

    if "total_market" in facts:
        tm = facts["total_market"]
        lines.append(
            f"Total market: {_fmt(tm['start'][1])} ({tm['start'][0]}) → "
            f"{_fmt(tm['peak'][1])} ({tm['peak'][0]} peak) → "
            f"{_fmt(tm['end'][1])} ({tm['end'][0]})"
        )

    if "cagr" in facts:
        lines.append(f"CAGR: {facts['cagr']}%")

    if facts.get("drugs"):
        lines.append("\nTop drugs by peak value:")
        key_years = [y for y in ("2025", "2027", "2030", "2032", "2034") if y in facts.get("years", [])]
        for label, vals in facts["drugs"][:8]:
            yv = "  |  ".join(f"{yr}: {_fmt(vals.get(yr))}" for yr in key_years if yr in vals)
            lines.append(f"  • {label}: {yv}")

    # Raw CSV preview
    preview = "\n".join(",".join(str(c) for c in r) for r in rows[:35])

    return (
        f"{system}\n\n"
        f"--- EXTRACTED FACTS ---\n"
        f"{chr(10).join(lines)}\n\n"
        f"--- CSV DATA (first 35 rows) ---\n"
        f"{preview}\n\n"
        f"Write the intelligence briefing now:"
    )


# ── LLM call ──────────────────────────────────────────────────────────────────

def _call_claude(prompt: str) -> str | None:
    claude = shutil.which("claude")
    if not claude:
        return None
    try:
        result = subprocess.run(
            [claude, "--print", "-p", prompt, "--max-turns", "1"],
            capture_output=True, text=True, timeout=120,
        )
        out = result.stdout.strip()
        return out if result.returncode == 0 and len(out) > 100 else None
    except Exception:
        return None


# ── Fallback table ─────────────────────────────────────────────────────────────

def _fallback_table(rows: list) -> str:
    if not rows:
        return ""
    headers = rows[0]
    sep = "| " + " | ".join("---" for _ in headers) + " |"
    head = "| " + " | ".join(str(h) for h in headers) + " |"
    body = []
    for row in rows[1:26]:
        if any(str(c).strip() for c in row):
            padded = list(row) + [""] * max(0, len(headers) - len(row))
            body.append("| " + " | ".join(str(c) for c in padded[:len(headers)]) + " |")
    return "\n".join([head, sep] + body)


# ── Data appendix ─────────────────────────────────────────────────────────────

_KEY_YEARS = {"2024", "2025", "2027", "2028", "2030", "2032", "2034", "2035", "2037"}


def _data_appendix(rows: list, filename: str) -> str:
    """Build a condensed source data table for appending to the narrative."""
    if not rows:
        return ""
    headers = rows[0]
    ycols = _year_cols(headers)

    # For wide CSVs (many year columns), keep only key years
    if len(ycols) > 8:
        keep_idx = {i for i, yr in ycols if yr in _KEY_YEARS}
        # Always keep first non-year column (label column = 0)
        keep_idx.add(0)
        col_indices = [i for i in range(len(headers)) if i == 0 or i in keep_idx]
    else:
        col_indices = list(range(len(headers)))

    def _pick(row):
        padded = list(row) + [""] * max(0, len(headers) - len(row))
        return [padded[i] for i in col_indices]

    sel_headers = _pick(headers)
    head = "| " + " | ".join(str(h) for h in sel_headers) + " |"
    sep = "| " + " | ".join("---" for _ in sel_headers) + " |"

    body = []
    for row in rows[1:41]:
        picked = _pick(row)
        if any(str(c).strip() for c in picked):
            body.append("| " + " | ".join(str(c) for c in picked) + " |")

    table = "\n".join([head, sep] + body)
    return (
        f"\n\n---\n\n## Source Data\n\n"
        f"{table}\n\n"
        f"*Source: `{filename}`*"
    )


# ── Public entry ───────────────────────────────────────────────────────────────

def analyze_csv(path: str) -> str:
    """Analyze a CSV file and return a narrative + source data appendix."""
    content = Path(path).read_text(encoding="utf-8-sig", errors="replace")
    rows = list(csv.reader(content.splitlines()))
    if not rows:
        return content

    filename = Path(path).name
    headers = rows[0]
    csv_type = detect_csv_type(headers, filename)
    facts = extract_facts(rows, csv_type)
    prompt = _build_prompt(facts, rows, filename)
    narrative = _call_claude(prompt)
    appendix = _data_appendix(rows, filename)

    if narrative:
        return narrative + appendix

    return _fallback_table(rows) + appendix
