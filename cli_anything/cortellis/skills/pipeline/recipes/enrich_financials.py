#!/usr/bin/env python3
"""
enrich_financials.py — Enrich company pipeline with investment profile via web search.

Two-provider strategy:
  Brave Search  — profile query: exact company-name match → Crunchbase/PitchBook/Yahoo
                  snippets are dense with structured funding data; no drift to similar names
  Exa keyword   — news query: type=keyword for recency without semantic drift

Writes:
  financials_summary.md  — wiki-safe ## Investment Profile section
  financials.json        — raw search data for debugging/re-runs

Skips gracefully if neither BRAVE_API_KEY nor EXA_API_KEY is set.

Usage: python3 enrich_financials.py <pipeline_dir> "<company_name>"
"""

import json
import os
import re
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))

from dotenv import load_dotenv
load_dotenv()

import html
import requests

BRAVE_API_URL = "https://api.search.brave.com/res/v1/web/search"
EXA_API_URL = "https://api.exa.ai/search"
CURRENT_YEAR = date.today().year


# ---------------------------------------------------------------------------
# Search providers
# ---------------------------------------------------------------------------

def brave_search(api_key: str, query: str, count: int = 5) -> list[dict]:
    """Brave web search — returns [{title, url, description}]."""
    try:
        resp = requests.get(
            BRAVE_API_URL,
            headers={"Accept": "application/json", "X-Subscription-Token": api_key},
            params={"q": query, "count": count},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json().get("web", {}).get("results", [])
    except Exception as e:
        print(f"  Brave search error: {e}", file=sys.stderr)
        return []


def exa_search(api_key: str, query: str, num_results: int = 4) -> list[dict]:
    """Exa keyword search — returns [{title, url, text}]."""
    try:
        resp = requests.post(
            EXA_API_URL,
            headers={"x-api-key": api_key, "Content-Type": "application/json"},
            json={
                "query": query,
                "numResults": num_results,
                "type": "keyword",
                "contents": {"text": {"maxCharacters": 2500}},
                "startPublishedDate": f"{CURRENT_YEAR - 2}-01-01T00:00:00.000Z",
            },
            timeout=20,
        )
        resp.raise_for_status()
        return resp.json().get("results", [])
    except Exception as e:
        print(f"  Exa search error: {e}", file=sys.stderr)
        return []


# ---------------------------------------------------------------------------
# Extraction (runs on Brave description snippets — short, structured)
# ---------------------------------------------------------------------------

_RAISED_RE = re.compile(
    r'raised\s+\$\s*([\d,]+(?:\.\d+)?)\s*([BMbm](?:illion)?)',
    re.IGNORECASE,
)
_TOTAL_RAISED_RE = re.compile(
    r'total(?:ly)?\s+raised[^$]{0,20}\$\s*([\d,]+(?:\.\d+)?)\s*([BMbm])',
    re.IGNORECASE,
)
_TOTAL_FUNDING_RE = re.compile(
    r'[Tt]otal\s+[Ff]unding\s+\$\s*([\d,]+(?:\.\d+)?)\s*([BMbm])',
)
_MEDIA_TAG_RE = re.compile(r'\[(?:Image|Photo|Video|Caption):[^\]]*\]', re.IGNORECASE)
_SERIES_FWD_RE = re.compile(
    r'Series\s+([A-F])\s+(?:round\s+)?(?:of\s+)?(?:for\s+)?\$\s*([\d,]+(?:\.\d+)?)\s*([BMbm])',
    re.IGNORECASE,
)
_SERIES_REV_RE = re.compile(
    r'\$\s*([\d,]+(?:\.\d+)?)\s*([BMbm])[^.]{0,40}[Ss]eries\s+([A-F])',
    re.IGNORECASE,
)
_TICKER_RE = re.compile(
    r'\b(NYSE|NASDAQ|KOSDAQ|KOSPI|HKEX|TSX|ASX|LSE|Euronext|SIX|XETRA)\s*[:\(]\s*([A-Z0-9\.\-]{1,10})',
    re.IGNORECASE,
)
_ACQUIRED_RE = re.compile(
    r'(?:acquired\s+by|acquisition\s+by|acquisition\s+of\s+\w[\w\s]+\s+by)\s+([\w\s&,\.]+?)(?:\s+for\s+\$[\d\.,]+[BMbm]|\s+in\s+a\s+deal|\.|,)',
    re.IGNORECASE,
)
_IPO_RE = re.compile(r'\bIPO\b|\binitial public offering\b', re.IGNORECASE)
_MARKET_CAP_RE = re.compile(
    r'market\s+cap(?:italization)?\s+(?:of\s+)?(?:approximately\s+)?\$\s*([\d,]+(?:\.\d+)?)\s*([BMbm])',
    re.IGNORECASE,
)


def _normalize_amount(value: str, unit: str) -> str:
    v = value.replace(",", "")
    u = unit.upper()[0] if unit else ""
    try:
        n = float(v)
        if u == "B":
            return f"${n:g}B"
        if u == "M":
            return f"${n:g}M"
    except ValueError:
        pass
    return f"${value}{unit}"


def _to_float_m(val: str, unit: str) -> float:
    try:
        n = float(val.replace(",", ""))
        return n * (1000 if unit.upper().startswith("B") else 1)
    except ValueError:
        return 0


def extract_facts(snippets: list[str], company_name: str) -> dict:
    """Extract structured facts from Brave description snippets.

    Snippets are short (~120 chars) and come from structured sources
    (Crunchbase, PitchBook, Yahoo Finance), so regex is reliable here.
    """
    name_word = company_name.split()[0].lower()
    # Only use snippets that mention the company
    relevant = [s for s in snippets if name_word in s.lower()] or snippets
    combined = "\n".join(relevant)

    facts: dict = {}

    # Ticker — require company name within 300 chars
    for m in _TICKER_RE.finditer(combined):
        window = combined[max(0, m.start() - 300): m.end() + 300].lower()
        if name_word in window:
            facts["ticker"] = m.group(2).upper()
            facts["exchange"] = m.group(1).upper()
            break

    # Market cap
    for m in _MARKET_CAP_RE.finditer(combined):
        facts["market_cap"] = _normalize_amount(m.group(1), m.group(2))
        break

    # Acquisition
    for m in _ACQUIRED_RE.finditer(combined):
        acquirer = m.group(1).strip().rstrip(".,")
        if len(acquirer) < 60:
            facts["acquired_by"] = acquirer
            break

    # IPO — only if company name is in the same sentence
    for sent in re.split(r'(?<=[.!?])\s+', combined):
        if _IPO_RE.search(sent) and name_word in sent.lower():
            facts["ipo_mentioned"] = True
            break

    # Series round — forward "Series B $215M" and reverse "$215M Series B"
    series: list[tuple[str, str, str]] = [
        (m.group(1), m.group(2), m.group(3)) for m in _SERIES_FWD_RE.finditer(combined)
    ] + [
        (m.group(3), m.group(1), m.group(2)) for m in _SERIES_REV_RE.finditer(combined)
    ]
    if series:
        best = sorted(series, key=lambda x: x[0].upper(), reverse=True)[0]
        facts["latest_round"] = f"Series {best[0].upper()} · {_normalize_amount(best[1], best[2])}"

    # Total raised
    m = _TOTAL_RAISED_RE.search(combined) or _TOTAL_FUNDING_RE.search(combined)
    if m:
        facts["total_raised"] = _normalize_amount(m.group(1), m.group(2))
    else:
        raised_all = _RAISED_RE.findall(combined)
        if raised_all:
            best_r = max(raised_all, key=lambda x: _to_float_m(x[0], x[1]))
            facts["total_raised"] = _normalize_amount(best_r[0], best_r[1])

    return facts


def extract_investors(snippets: list[str]) -> list[str]:
    """Extract investor names from Brave description snippets."""
    combined = "\n".join(snippets)
    candidates: list[str] = []
    for pattern in [
        r'(?:led by|investors?(?:\s+include)?|backed by|participation from)[:\s]+([^\.]{10,200})',
        r'(?:key investors|notable investors)[:\s]+([^\.]{10,200})',
    ]:
        for m in re.finditer(pattern, combined, re.IGNORECASE):
            candidates.append(m.group(1).strip())

    if not candidates:
        return []

    raw = " · ".join(candidates[:3])
    investors = [
        i.strip().strip(",")
        for i in re.split(r",\s*(?:and\s+)?|\band\b\s*", raw)
        if 3 < len(i.strip()) < 50
        and not re.search(r'[\d%$]', i)
        and re.search(r'[A-Z]', i)
    ]
    seen: set[str] = set()
    unique: list[str] = []
    for inv in investors:
        inv = html.unescape(inv)
        if inv.lower() not in seen:
            seen.add(inv.lower())
            unique.append(inv)
    return unique[:8]


def extract_bullets(exa_results: list[dict], company_name: str) -> list[str]:
    """Extract recent development bullets from Exa full-text results."""
    name_word = company_name.split()[0].lower()
    bullets: list[str] = []
    seen: set[str] = set()

    for r in exa_results:
        text = _MEDIA_TAG_RE.sub("", r.get("text") or "").strip()
        for sent in re.split(r'(?<=[.!?])\s+', text):
            sent = sent.strip()
            if len(sent) < 40 or len(sent) > 250:
                continue
            if not (
                name_word in sent.lower()
                or re.search(r'\b(phase [123]|FDA|EMA|acquired|IPO|raised|approved|data|trial|deal)\b', sent, re.IGNORECASE)
            ):
                continue
            if re.search(r'(click here|cookie|privacy policy|subscribe|sign up|©|learn more|stage:|a sign with|the company logo|PRNewswire|Business Wire|\bAdvertisement\b)', sent, re.IGNORECASE):
                continue
            # Skip markdown/frontmatter artifacts from structured article pages
            if re.match(r'^[-#•·]|^(title|description|summary):', sent):
                continue
            key = re.sub(r'\s+', ' ', sent.lower()[:80])
            if key not in seen:
                seen.add(key)
                bullets.append(sent)
            if len(bullets) >= 4:
                return bullets

    return bullets


# ---------------------------------------------------------------------------
# Markdown builder
# ---------------------------------------------------------------------------

def build_markdown(
    facts: dict,
    investors: list[str],
    bullets: list[str],
    profile_results: list[dict],
    news_results: list[dict],
) -> str:
    today = date.today().strftime("%b %Y")
    lines = ["## Investment Profile\n\n"]

    if facts.get("acquired_by"):
        status = f"Acquired by {facts['acquired_by']}"
    elif facts.get("ticker"):
        exchange = facts.get("exchange", "")
        status = f"Public · {exchange}: {facts['ticker']}" if exchange else f"Public · {facts['ticker']}"
    elif facts.get("total_raised") or facts.get("latest_round"):
        # Has funding rounds → private company (IPO mention may be aspirational)
        status = "Private"
    elif facts.get("ipo_mentioned"):
        status = "Public / IPO"
    else:
        status = "Private"

    lines.append(f"**Status:** {status} | *Updated: {today}*\n\n")

    if facts.get("market_cap"):
        lines.append(f"**Market cap:** ~{facts['market_cap']}\n\n")
    if facts.get("total_raised"):
        lines.append(f"**Total raised:** {facts['total_raised']}\n\n")
    if facts.get("latest_round"):
        lines.append(f"**Latest round:** {facts['latest_round']}\n\n")
    if investors:
        lines.append(f"**Key investors:** {', '.join(investors)}\n\n")

    if bullets:
        lines.append("### Recent Developments\n\n")
        for b in bullets:
            lines.append(f"- {b}\n")
        lines.append("\n")

    source_urls = list(dict.fromkeys(
        r["url"] for r in profile_results + news_results if r.get("url")
    ))[:4]
    if source_urls:
        src = " · ".join(f"[{_domain(u)}]({u})" for u in source_urls)
        lines.append(f"*Sources: {src} — {today}*\n")

    return "".join(lines)


def _domain(url: str) -> str:
    m = re.search(r'https?://(?:www\.)?([^/]+)', url)
    if m:
        parts = m.group(1).split(".")
        return parts[-2] if len(parts) >= 2 else m.group(1)
    return url


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: enrich_financials.py <pipeline_dir> <company_name>", file=sys.stderr)
        sys.exit(1)

    pipeline_dir = sys.argv[1]
    company_name = sys.argv[2]

    brave_key = os.environ.get("BRAVE_API_KEY", "").strip()
    exa_key = os.environ.get("EXA_API_KEY", "").strip()

    if not brave_key and not exa_key:
        print("  Skipping financial enrichment: no BRAVE_API_KEY or EXA_API_KEY set", file=sys.stderr)
        sys.exit(0)

    print(f"Enriching investment profile for: {company_name}")

    profile_results: list[dict] = []
    news_results: list[dict] = []

    # Brave: exact-match profile query → structured funding snippets
    if brave_key:
        print("  Brave: fetching investment profile…")
        profile_results = brave_search(
            brave_key,
            f'"{company_name}" biotech pharma funding investors raised stock',
            count=5,
        )
        print(f"  Brave: {len(profile_results)} results")

    # Exa keyword: news query → recent developments with full text
    if exa_key:
        print("  Exa: fetching recent news…")
        news_results = exa_search(
            exa_key,
            f'"{company_name}" deal trial FDA approved partnership {CURRENT_YEAR}',
            num_results=4,
        )
        print(f"  Exa: {len(news_results)} results")

    if not profile_results and not news_results:
        print(f"  No results found for {company_name} — skipping", file=sys.stderr)
        sys.exit(0)

    # Strip HTML tags from Brave snippets before extraction
    _html_tag_re = re.compile(r'<[^>]+>')
    brave_snippets = [
        html.unescape(_html_tag_re.sub("", r.get("description") or r.get("title") or ""))
        for r in profile_results
    ]
    facts = extract_facts(brave_snippets, company_name)
    investors = extract_investors(brave_snippets)

    # Extract bullets from Exa full text
    bullets = extract_bullets(news_results, company_name)

    print(f"  Facts: {facts}")
    print(f"  Investors: {investors[:3]}")
    print(f"  Bullets: {len(bullets)}")

    os.makedirs(pipeline_dir, exist_ok=True)

    raw = {
        "company_name": company_name,
        "profile_results": [
            {"title": r.get("title"), "url": r.get("url"), "description": r.get("description")}
            for r in profile_results
        ],
        "news_results": [
            {"title": r.get("title"), "url": r.get("url"), "published": r.get("publishedDate")}
            for r in news_results
        ],
        "facts": facts,
        "investors": investors,
    }
    json_path = os.path.join(pipeline_dir, "financials.json")
    with open(json_path, "w") as f:
        json.dump(raw, f, indent=2)
    print(f"  Written: {json_path}")

    md = build_markdown(facts, investors, bullets, profile_results, news_results)
    md_path = os.path.join(pipeline_dir, "financials_summary.md")
    with open(md_path, "w") as f:
        f.write(md)
    print(f"  Written: {md_path}")
    print(f"Investment profile enrichment complete for {company_name}.")


if __name__ == "__main__":
    main()
