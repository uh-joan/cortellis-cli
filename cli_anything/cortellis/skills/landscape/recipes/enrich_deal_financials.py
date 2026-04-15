#!/usr/bin/env python3
"""
enrich_deal_financials.py — Enrich landscape deals with financial terms.

Reads deals.csv, fetches expanded deal records via deals-intelligence API,
and writes deal_financials.csv + deal_comps.md with financial terms.

Usage: python3 enrich_deal_financials.py <landscape_dir>
"""

import csv
import os
import sys
import time

# Allow running as standalone script
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))

from dotenv import load_dotenv
from cli_anything.cortellis.core.client import CortellisClient
from cli_anything.cortellis.core import deals_intelligence

BATCH_SIZE = 30
BATCH_SLEEP_SEC = 3

FINANCIALS_COLUMNS = [
    "deal_id",
    "title",
    "principal",
    "partner",
    "type",
    "date",
    "upfront_payment",
    "milestone_payments",
    "royalty_rate",
    "total_deal_value",
    "financial_terms_text",
]


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def extract_deal_ids(landscape_dir):
    """Read deals.csv and return list of deal IDs."""
    path = os.path.join(landscape_dir, "deals.csv")
    if not os.path.exists(path):
        return []
    ids = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            deal_id = (row.get("id") or row.get("deal_id") or "").strip()
            if deal_id:
                ids.append(deal_id)
    return ids


def _read_deals_csv(landscape_dir):
    """Return dict of deal_id -> row for metadata lookup."""
    path = os.path.join(landscape_dir, "deals.csv")
    if not os.path.exists(path):
        return {}
    result = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            deal_id = (row.get("id") or row.get("deal_id") or "").strip()
            if deal_id:
                result[deal_id] = row
    return result


# ---------------------------------------------------------------------------
# API fetching
# ---------------------------------------------------------------------------

def fetch_expanded_deals(deal_ids, client):
    """Fetch expanded deal records in batches of BATCH_SIZE.

    Returns list of expanded deal dicts.
    """
    results = []
    for i in range(0, len(deal_ids), BATCH_SIZE):
        batch = deal_ids[i:i + BATCH_SIZE]
        try:
            response = deals_intelligence.get_expanded_batch(client, batch)
            deals = _extract_deals_from_response(response)
            results.extend(deals)
        except Exception as exc:
            print(
                f"[warn] batch fetch failed for ids {batch[:3]}...: {exc}",
                file=sys.stderr,
            )
        if i + BATCH_SIZE < len(deal_ids):
            time.sleep(BATCH_SLEEP_SEC)
    return results


def _extract_deals_from_response(response):
    """Extract deal list from API response envelope."""
    if not response:
        return []
    if isinstance(response, list):
        return response
    # Try common envelope patterns
    for key in ("deals", "data", "results", "items", "dealRecords"):
        val = response.get(key)
        if isinstance(val, list):
            return val
        if isinstance(val, dict):
            # e.g. {"dealRecords": {"Deal": [...]}}
            for inner_key in ("Deal", "deal", "items"):
                inner = val.get(inner_key)
                if isinstance(inner, list):
                    return inner
                if isinstance(inner, dict):
                    return [inner]
    # Single deal response
    if isinstance(response, dict) and ("@id" in response or "dealId" in response):
        return [response]
    return []


# ---------------------------------------------------------------------------
# Financial field extraction
# ---------------------------------------------------------------------------

def _safe_str(value):
    """Return string representation of value, or empty string if None/missing."""
    if value is None:
        return ""
    return str(value).strip()


def _get_nested(obj, *keys):
    """Walk nested dict/list by keys, returning empty string if any step fails."""
    current = obj
    for key in keys:
        if not isinstance(current, dict):
            return ""
        current = current.get(key)
        if current is None:
            return ""
    return _safe_str(current)


def extract_financials(expanded_deal):
    """Extract financial fields from an expanded deal record.

    The Cortellis expanded deal JSON may nest financial data under several
    possible key paths. Each field is tried defensively; missing fields
    produce empty strings.
    """
    if not expanded_deal or not isinstance(expanded_deal, dict):
        return {
            "upfront_payment": "",
            "milestone_payments": "",
            "royalty_rate": "",
            "total_deal_value": "",
            "financial_terms_text": "",
        }

    # upfront_payment: try multiple paths
    upfront = (
        _safe_str(expanded_deal.get("upfrontPayment"))
        or _get_nested(expanded_deal, "financialTerms", "upfrontPayment")
        or _get_nested(expanded_deal, "FinancialTerms", "UpfrontPayment")
        or _get_nested(expanded_deal, "financial_terms", "upfront_payment")
        or ""
    )

    # milestone_payments
    milestones = (
        _safe_str(expanded_deal.get("milestonePayments"))
        or _safe_str(expanded_deal.get("totalMilestones"))
        or _get_nested(expanded_deal, "financialTerms", "milestonePayments")
        or _get_nested(expanded_deal, "FinancialTerms", "MilestonePayments")
        or _get_nested(expanded_deal, "financial_terms", "milestone_payments")
        or ""
    )

    # royalty_rate
    royalty = (
        _safe_str(expanded_deal.get("royaltyRate"))
        or _get_nested(expanded_deal, "financialTerms", "royaltyRate")
        or _get_nested(expanded_deal, "FinancialTerms", "RoyaltyRate")
        or _get_nested(expanded_deal, "financial_terms", "royalty_rate")
        or ""
    )

    # total_deal_value
    total_value = (
        _safe_str(expanded_deal.get("totalDealValue"))
        or _safe_str(expanded_deal.get("dealValue"))
        or _get_nested(expanded_deal, "financialTerms", "totalDealValue")
        or _get_nested(expanded_deal, "FinancialTerms", "TotalDealValue")
        or _get_nested(expanded_deal, "financial_terms", "total_deal_value")
        or ""
    )

    # financial_terms_text: free-text summary if present
    terms_text = (
        _safe_str(expanded_deal.get("financialTermsText"))
        or _safe_str(expanded_deal.get("termsDescription"))
        or _get_nested(expanded_deal, "financialTerms", "termsText")
        or _get_nested(expanded_deal, "FinancialTerms", "TermsText")
        or ""
    )

    return {
        "upfront_payment": upfront,
        "milestone_payments": milestones,
        "royalty_rate": royalty,
        "total_deal_value": total_value,
        "financial_terms_text": terms_text,
    }


# ---------------------------------------------------------------------------
# Building records
# ---------------------------------------------------------------------------

def build_records(expanded_deals, csv_meta):
    """Merge expanded deal financials with CSV metadata into flat records."""
    records = []
    for deal in expanded_deals:
        if not deal:
            continue
        deal_id = (
            _safe_str(deal.get("@id"))
            or _safe_str(deal.get("dealId"))
            or _safe_str(deal.get("id"))
        )
        csv_row = csv_meta.get(deal_id, {})

        title = (
            _safe_str(deal.get("title"))
            or _safe_str(deal.get("dealTitle"))
            or csv_row.get("title", "")
        )
        principal = (
            _safe_str(deal.get("principal"))
            or _safe_str(deal.get("licensee"))
            or csv_row.get("principal", "")
        )
        partner = (
            _safe_str(deal.get("partner"))
            or _safe_str(deal.get("licensor"))
            or csv_row.get("partner", "")
        )
        deal_type = (
            _safe_str(deal.get("dealType"))
            or _safe_str(deal.get("type"))
            or csv_row.get("type", "")
        )
        date = (
            _safe_str(deal.get("date"))
            or _safe_str(deal.get("dealDate"))
            or csv_row.get("date", "")
        )

        financials = extract_financials(deal)

        records.append({
            "deal_id": deal_id,
            "title": title,
            "principal": principal,
            "partner": partner,
            "type": deal_type,
            "date": date,
            **financials,
        })
    return records


# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------

def write_financials_csv(records, path):
    """Write deal_financials.csv with financial columns."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FINANCIALS_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)


def _safe_float_value(val):
    """Parse a numeric value from a financial string, stripping currency symbols."""
    if not val:
        return None
    import re as _re
    cleaned = val.replace(",", "").replace("$", "").strip()
    cleaned = _re.sub(r'(\d)[Mm]\b', r'\1e6', cleaned)
    cleaned = _re.sub(r'(\d)[Bb]\b', r'\1e9', cleaned)
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return None


def generate_comps_markdown(records):
    """Generate deal_comps.md with a comparable deals table.

    Only includes deals with at least one financial field populated.
    Table is sorted by total_deal_value descending.
    """
    financial_fields = ["upfront_payment", "milestone_payments", "royalty_rate", "total_deal_value", "financial_terms_text"]

    # Filter to deals with at least one financial field populated
    with_financials = [
        r for r in records
        if any(r.get(f, "") for f in financial_fields)
    ]

    if not with_financials:
        return "# Deal Comparables\n\n_No deals with financial terms available._\n"

    # Sort by total_deal_value descending (numeric parse best-effort)
    def sort_key(r):
        v = _safe_float_value(r.get("total_deal_value", ""))
        return v if v is not None else -1.0

    sorted_deals = sorted(with_financials, key=sort_key, reverse=True)

    # Summary stats
    values = [_safe_float_value(r.get("total_deal_value", "")) for r in with_financials]
    numeric_values = [v for v in values if v is not None and v > 0]

    median_value = ""
    if numeric_values:
        sorted_vals = sorted(numeric_values)
        mid = len(sorted_vals) // 2
        if len(sorted_vals) % 2 == 0:
            median_value = f"${(sorted_vals[mid - 1] + sorted_vals[mid]) / 2:,.0f}"
        else:
            median_value = f"${sorted_vals[mid]:,.0f}"

    # Most common deal type
    from collections import Counter
    type_counts = Counter(r.get("type", "") for r in with_financials if r.get("type", ""))
    most_common_type = type_counts.most_common(1)[0][0] if type_counts else "N/A"

    # Date range
    dates = sorted(r.get("date", "")[:10] for r in with_financials if r.get("date", ""))
    date_range = f"{dates[0]} to {dates[-1]}" if len(dates) >= 2 else (dates[0] if dates else "N/A")

    lines = [
        "# Deal Comparables",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Deals with financials | {len(with_financials)} |",
        f"| Median total value | {median_value or 'N/A'} |",
        f"| Most common type | {most_common_type} |",
        f"| Date range | {date_range} |",
        "",
        "## Comparable Deals",
        "",
        "| Deal | Principal | Partner | Type | Date | Upfront | Milestones | Royalty | Total Value |",
        "|------|-----------|---------|------|------|---------|------------|---------|-------------|",
    ]

    for r in sorted_deals:
        title = (r.get("title") or r.get("deal_id") or "")[:50]
        lines.append(
            f"| {title}"
            f" | {r.get('principal', '')[:30]}"
            f" | {r.get('partner', '')[:30]}"
            f" | {r.get('type', '')}"
            f" | {r.get('date', '')[:10]}"
            f" | {r.get('upfront_payment', '')}"
            f" | {r.get('milestone_payments', '')}"
            f" | {r.get('royalty_rate', '')}"
            f" | {r.get('total_deal_value', '')}"
            f" |"
        )

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print("Usage: enrich_deal_financials.py <landscape_dir>", file=sys.stderr)
        sys.exit(1)

    landscape_dir = sys.argv[1]
    if not os.path.isdir(landscape_dir):
        print(f"Error: landscape directory not found: {landscape_dir}", file=sys.stderr)
        sys.exit(1)

    deal_ids = extract_deal_ids(landscape_dir)
    if not deal_ids:
        print(f"[info] no deals found in {landscape_dir}; nothing to do", file=sys.stderr)
        # Write empty artifacts so downstream tools see stable files
        write_financials_csv([], os.path.join(landscape_dir, "deal_financials.csv"))
        with open(os.path.join(landscape_dir, "deal_comps.md"), "w", encoding="utf-8") as f:
            f.write("# Deal Comparables\n\n_No deals available._\n")
        return

    print(f"[deal_financials] fetching expanded records for {len(deal_ids)} deals...", file=sys.stderr)

    load_dotenv()
    client = CortellisClient()
    expanded_deals = fetch_expanded_deals(deal_ids, client)

    csv_meta = _read_deals_csv(landscape_dir)
    records = build_records(expanded_deals, csv_meta)

    # Write outputs
    csv_path = os.path.join(landscape_dir, "deal_financials.csv")
    write_financials_csv(records, csv_path)

    md_path = os.path.join(landscape_dir, "deal_comps.md")
    comps_md = generate_comps_markdown(records)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(comps_md)

    financial_fields = ["upfront_payment", "milestone_payments", "royalty_rate", "total_deal_value", "financial_terms_text"]
    with_financials = sum(
        1 for r in records if any(r.get(field, "") for field in financial_fields)
    )
    print(
        f"[deal_financials] {landscape_dir}: "
        f"deals={len(deal_ids)} fetched={len(expanded_deals)} "
        f"with_financials={with_financials}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
