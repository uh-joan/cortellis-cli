#!/usr/bin/env python3
"""PubMed/NCBI E-utilities API client — free, no auth required.

Rate limit: 3 requests/second without API key (10/sec with key).
"""

import time
import urllib.parse
import urllib.request
import json

ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
ESUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"


def search(query: str, max_results: int = 10, sort: str = "relevance") -> list:
    """Search PubMed and return list of PMIDs.

    Params:
      db=pubmed, term=<query>, retmax=<max_results>,
      sort=relevance|pub_date, retmode=json
    Returns list of PMID strings.
    Sleeps 0.4s after call (stay under 3 req/sec).
    """
    params = {
        "db": "pubmed",
        "term": query,
        "retmax": str(max_results),
        "sort": sort,
        "retmode": "json",
    }
    url = ESEARCH_URL + "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        pmids = data.get("esearchresult", {}).get("idlist", [])
    except Exception:
        pmids = []
    finally:
        time.sleep(0.4)
    return pmids


def fetch_summaries(pmids: list) -> dict:
    """Fetch document summaries for a list of PMIDs.

    Endpoint: esummary.fcgi?db=pubmed&id=<comma-separated>&retmode=json
    Returns dict keyed by PMID with summary fields:
      title, authors (list of {'name': ...}), source (journal),
      pubdate, uid
    Sleeps 0.4s after call.
    """
    if not pmids:
        return {}
    params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "json",
    }
    url = ESUMMARY_URL + "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        result = data.get("result", {})
        # Remove the 'uids' key — it's a list, not a summary
        result.pop("uids", None)
    except Exception:
        result = {}
    finally:
        time.sleep(0.4)
    return result


def search_and_fetch(query: str, max_results: int = 10) -> list:
    """Combined search + fetch. Returns list of publication dicts:
    {title, authors_str, journal, date, pmid, source='pubmed'}
    """
    pmids = search(query, max_results=max_results)
    if not pmids:
        return []

    summaries = fetch_summaries(pmids)
    results = []
    for pmid in pmids:
        rec = summaries.get(pmid, {})
        if not rec:
            continue

        title = str(rec.get("title") or "").strip()

        authors_raw = rec.get("authors", [])
        if isinstance(authors_raw, list) and authors_raw:
            first = authors_raw[0]
            first_name = first.get("name", "") if isinstance(first, dict) else str(first)
            authors_str = f"{first_name} et al" if len(authors_raw) > 1 else first_name
        else:
            authors_str = ""

        journal = str(rec.get("source") or "").strip()
        date = str(rec.get("pubdate") or "").strip()
        # Normalize date to YYYY-MM if possible
        if len(date) > 7 and " " in date:
            parts = date.split()
            # e.g. "2024 Jan" -> "2024-01"
            month_map = {
                "Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04",
                "May": "05", "Jun": "06", "Jul": "07", "Aug": "08",
                "Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12",
            }
            if len(parts) >= 2 and parts[1] in month_map:
                date = f"{parts[0]}-{month_map[parts[1]]}"
            elif len(parts) >= 1:
                date = parts[0]

        if title:
            results.append({
                "title": title,
                "authors_str": authors_str,
                "journal": journal,
                "date": date,
                "pmid": pmid,
                "source": "pubmed",
            })

    return results
