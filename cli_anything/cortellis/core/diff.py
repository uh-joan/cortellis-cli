"""diff.py — Lightweight wiki-vs-live diff engine for autonomous refresh triggering.

Fetches minimal live counts from the Cortellis API (one drug search + one deal
search, hits=1 each) and compares them to the compiled article metadata.

Usage:
    from cli_anything.cortellis.core.diff import compute_diff, scan_all
    result = compute_diff("obesity", client, base_dir=".")
    if result["should_refresh"]:
        # trigger: cortellis run-skill landscape obesity
"""

import os
from datetime import datetime, timezone
from typing import Optional

from cli_anything.cortellis.core import drugs as _drugs
from cli_anything.cortellis.utils.wiki import article_path, read_article, list_articles, wiki_root


_PLURAL = {
    "indication": "indications",
    "company":    "companies",
    "drug":       "drugs",
    "target":     "targets",
}

_DEFAULT_THRESHOLDS = {
    "indication": {"new_drugs": 1, "max_age_days": 7},
    "company":    {"new_drugs": 1, "max_age_days": 7},
    "drug":       {               "max_age_days": 7},
}


def _total(response: dict, key: str) -> int:
    output = response.get(key, {})
    if isinstance(output, dict):
        try:
            return int(output.get("@totalResults", 0))
        except (ValueError, TypeError):
            return 0
    return 0


def _age_days(compiled_at: str) -> int:
    if not compiled_at:
        return 9999
    try:
        dt = datetime.fromisoformat(compiled_at.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - dt).days
    except (ValueError, TypeError):
        return 9999


def _detect_type(slug: str, base_dir: str) -> str:
    for atype, plural in _PLURAL.items():
        if os.path.exists(article_path(plural, slug, base_dir)):
            return atype
    return "unknown"


def _read_indication_id(source_dir: str) -> Optional[str]:
    """Read the numeric indication ID from the raw data directory."""
    path = os.path.join(source_dir, "approval_regions.json")
    if not os.path.exists(path):
        return None
    try:
        import json
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return str(data.get("indication_id", "")) or None
    except Exception:
        return None


def fetch_live_counts(indication_name: str, client, indication_id: Optional[str] = None) -> dict:
    """Fetch total drug count for an indication from the live API.

    Uses the numeric indication_id for the drug search LINKED block query.
    """
    # Numeric indication_id works directly as the --indication parameter;
    # the query builder emits developmentStatusIndicationId:238 (no quotes).
    drug_resp = _drugs.search(client, indication=indication_id or indication_name, hits=1)
    return {
        "total_drugs": _total(drug_resp, "drugResultsOutput"),
        "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def compute_diff(
    slug: str,
    client,
    base_dir: str = ".",
    article_type: Optional[str] = None,
    thresholds: Optional[dict] = None,
) -> dict:
    """Compare a compiled wiki article against live Cortellis API counts.

    Returns a dict with: slug, type, title, compiled_at, age_days, delta,
    should_refresh, reason.
    """
    if article_type is None:
        article_type = _detect_type(slug, base_dir)

    if article_type not in ("indication", "company", "drug"):
        return {
            "slug": slug, "type": article_type,
            "error": f"unsupported type: {article_type}",
            "should_refresh": False,
        }

    art = read_article(article_path(_PLURAL.get(article_type, f"{article_type}s"), slug, base_dir))
    if art is None:
        return {
            "slug": slug, "type": article_type,
            "error": "article not found",
            "should_refresh": True, "reason": "missing",
        }

    meta = art["meta"]
    title = meta.get("title", slug)
    compiled_at = meta.get("compiled_at", "")
    age = _age_days(compiled_at)
    prev_drugs = int(meta.get("total_drugs") or 0)
    prev_deals = int(meta.get("total_deals") or 0)

    thr = thresholds or _DEFAULT_THRESHOLDS.get(article_type, {})
    max_age = thr.get("max_age_days", 14)
    drug_thr = thr.get("new_drugs", 3)

    if article_type == "indication":
        source_dir = meta.get("source_dir", "")
        indication_id = _read_indication_id(source_dir) if source_dir else None
        live = fetch_live_counts(title, client, indication_id=indication_id)
        live_drugs = live["total_drugs"]
    else:
        live_drugs = None

    drug_delta = (live_drugs - prev_drugs) if live_drugs is not None else None

    reasons = []
    if age >= max_age:
        reasons.append(f"age {age}d >= {max_age}d threshold")
    if drug_delta is not None and drug_delta >= drug_thr:
        reasons.append(f"+{drug_delta} drugs (threshold: {drug_thr})")

    return {
        "slug": slug,
        "type": article_type,
        "title": title,
        "compiled_at": compiled_at,
        "age_days": age,
        "delta": {
            "total_drugs": {"before": prev_drugs, "after": live_drugs, "delta": drug_delta},
        },
        "should_refresh": bool(reasons),
        "reason": "; ".join(reasons) if reasons else "within threshold",
    }


def scan_all(
    client,
    base_dir: str = ".",
    types: Optional[set] = None,
    thresholds: Optional[dict] = None,
) -> list:
    """Scan all wiki articles and return diff results, refresh candidates first."""
    articles = list_articles(wiki_root(base_dir))
    results = []

    for art in articles:
        meta = art.get("meta") or {}
        atype = meta.get("type", "")
        slug = meta.get("slug", "")
        if not slug or not atype:
            continue
        if types and atype not in types:
            continue
        results.append(compute_diff(slug, client, base_dir=base_dir,
                                    article_type=atype, thresholds=thresholds))

    results.sort(key=lambda r: (not r.get("should_refresh"), -r.get("age_days", 0)))
    return results
