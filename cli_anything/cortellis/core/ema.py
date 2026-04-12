#!/usr/bin/env python3
"""EMA (European Medicines Agency) public JSON API client — no auth required.

Endpoints: https://www.ema.europa.eu/en/documents/report/<endpoint>
Rate limit: public API — 1s sleep between calls to be respectful.
"""

import time
import urllib.request
import urllib.parse
import urllib.error
import json
from typing import Optional

_BASE_URL = "https://www.ema.europa.eu/en/documents/report"
_SLEEP = 1.0  # seconds between calls


def _get(endpoint: str) -> list:
    """Fetch an EMA JSON report endpoint. Returns list of records."""
    url = f"{_BASE_URL}/{endpoint}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "cortellis-cli/1.0",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            data = json.loads(raw)
        # EMA returns {data: [...]} or legacy direct array
        if isinstance(data, dict) and "data" in data:
            return data["data"] if isinstance(data["data"], list) else []
        if isinstance(data, list):
            return data
        return []
    except urllib.error.HTTPError as e:
        print(f"[ema] HTTP {e.code} for {endpoint}")
        return []
    except Exception as e:
        print(f"[ema] Error fetching {endpoint}: {e}")
        return []
    finally:
        time.sleep(_SLEEP)


def _parse_date(ema_date: str) -> str:
    """Convert EMA date 'DD Month YYYY' → 'YYYY-MM-DD'. Returns '' on failure."""
    if not ema_date:
        return ""
    months = {
        "January": "01", "February": "02", "March": "03", "April": "04",
        "May": "05", "June": "06", "July": "07", "August": "08",
        "September": "09", "October": "10", "November": "11", "December": "12",
    }
    parts = ema_date.strip().split()
    if len(parts) == 3 and parts[1] in months:
        return f"{parts[2]}-{months[parts[1]]}-{parts[0].zfill(2)}"
    return ema_date


# ---------------------------------------------------------------------------
# Medicines
# ---------------------------------------------------------------------------

def search_medicines(
    active_substance: Optional[str] = None,
    therapeutic_area: Optional[str] = None,
    status: Optional[str] = None,          # Authorised | Withdrawn | Refused | Suspended
    orphan: Optional[bool] = None,
    biosimilar: Optional[bool] = None,
    prime: Optional[bool] = None,
    limit: int = 100,
) -> list[dict]:
    """Search EU-approved medicines.

    Returns list of dicts with: medicine_name, active_substance, status,
    therapeutic_area, authorisation_date, orphan_medicine, biosimilar,
    prime, product_number.
    """
    records = _get("medicines-output-medicines_json-report_en.json")

    if active_substance:
        term = active_substance.lower()
        records = [r for r in records if term in (r.get("active_substance") or "").lower()
                   or term in (r.get("international_non_proprietary_name_common_name") or "").lower()]
    if therapeutic_area:
        term = therapeutic_area.lower()
        records = [r for r in records if term in (r.get("therapeutic_area_mesh") or "").lower()
                   or term in (r.get("therapeutic_indication") or "").lower()]
    if status:
        records = [r for r in records if (r.get("medicine_status") or "").lower() == status.lower()]
    if orphan is True:
        records = [r for r in records if r.get("orphan_medicine") == "Yes"]
    if biosimilar is True:
        records = [r for r in records if r.get("biosimilar") == "Yes"]
    if prime is True:
        records = [r for r in records if r.get("prime_priority_medicine") == "Yes"]

    out = []
    for r in records[:limit]:
        raw_date = r.get("marketing_authorisation_date") or r.get("opinion_adopted_date", "")
        # EMA dates come as DD/MM/YYYY
        if raw_date and "/" in raw_date:
            parts = raw_date.split("/")
            if len(parts) == 3:
                raw_date = f"{parts[2]}-{parts[1]}-{parts[0]}"
        out.append({
            "medicine_name": r.get("name_of_medicine", ""),
            "active_substance": r.get("active_substance") or r.get("international_non_proprietary_name_common_name", ""),
            "status": r.get("medicine_status", ""),
            "therapeutic_area": r.get("therapeutic_area_mesh", ""),
            "therapeutic_indication": r.get("therapeutic_indication", ""),
            "authorisation_date": raw_date,
            "orphan_medicine": r.get("orphan_medicine", ""),
            "biosimilar": r.get("biosimilar", ""),
            "prime": r.get("prime_priority_medicine", ""),
            "product_number": r.get("ema_product_number", ""),
            "company_name": r.get("marketing_authorisation_developer_applicant_holder", ""),
            "conditional_approval": r.get("conditional_approval", ""),
            "atc_code": r.get("atc_code_human", ""),
            "url": r.get("medicine_url", ""),
        })
    return out


# ---------------------------------------------------------------------------
# Orphan designations
# ---------------------------------------------------------------------------

def get_orphan_designations(condition: Optional[str] = None, limit: int = 50) -> list[dict]:
    """Get EMA orphan drug designations.

    Returns list of dicts with: medicine_name, active_substance, condition,
    designation_status, designation_date, sponsor.
    """
    records = _get("medicines-output-orphan_designations-json-report_en.json")

    if condition:
        term = condition.lower()
        records = [r for r in records if term in (r.get("condition") or "").lower()]

    return [
        {
            "medicine_name": r.get("medicine_name", ""),
            "active_substance": r.get("active_substance", ""),
            "condition": r.get("condition", ""),
            "designation_status": r.get("designation_status", ""),
            "designation_date": _parse_date(r.get("designation_date", "")),
            "sponsor": r.get("sponsor", ""),
        }
        for r in records[:limit]
    ]


# ---------------------------------------------------------------------------
# Supply shortages
# ---------------------------------------------------------------------------

def get_supply_shortages(
    medicine_name: Optional[str] = None,
    status: Optional[str] = None,   # Ongoing | Resolved
    limit: int = 50,
) -> list[dict]:
    """Get EMA medicine supply shortage reports.

    Returns list of dicts with: medicine_name, active_substance,
    supply_shortage_status, shortage_start, shortage_end, reason.
    """
    records = _get("shortages-output-json-report_en.json")

    if medicine_name:
        term = medicine_name.lower()
        records = [r for r in records if term in (r.get("medicine_affected") or "").lower()
                   or term in (r.get("international_non_proprietary_name_inn_or_common_name") or "").lower()]
    if status:
        records = [r for r in records if (r.get("supply_shortage_status") or "").lower() == status.lower()]

    def _fmt(d):
        if d and "/" in d:
            p = d.split("/")
            if len(p) == 3:
                return f"{p[2]}-{p[1]}-{p[0]}"
        return d or ""

    return [
        {
            "medicine_name": r.get("medicine_affected", ""),
            "active_substance": r.get("international_non_proprietary_name_inn_or_common_name", ""),
            "supply_shortage_status": r.get("supply_shortage_status", ""),
            "shortage_start": _fmt(r.get("start_of_shortage_date", "")),
            "expected_resolution": _fmt(r.get("expected_resolution_date", "")),
            "alternatives_available": r.get("availability_of_alternatives", ""),
            "therapeutic_area": r.get("therapeutic_area_mesh", ""),
        }
        for r in records[:limit]
    ]


# ---------------------------------------------------------------------------
# Safety referrals
# ---------------------------------------------------------------------------

def get_safety_referrals(
    medicine_name: Optional[str] = None,
    safety_only: bool = False,
    limit: int = 50,
) -> list[dict]:
    """Get EMA EU-wide safety reviews (referrals).

    Returns list of dicts with: referral_name, active_substance,
    procedure_start, procedure_end, safety_referral, outcome.
    """
    records = _get("referrals-output-json-report_en.json")

    if medicine_name:
        term = medicine_name.lower()
        records = [r for r in records if term in (r.get("referral_name") or "").lower()
                   or term in (r.get("international_non_proprietary_name_inn_common_name") or "").lower()]
    if safety_only:
        records = [r for r in records if r.get("safety_referral") in ("Sì", "Yes")]

    def _fmt(d):
        if d and "/" in d:
            p = d.split("/")
            if len(p) == 3:
                return f"{p[2]}-{p[1]}-{p[0]}"
        return d or ""

    return [
        {
            "referral_name": r.get("referral_name", ""),
            "active_substance": r.get("international_non_proprietary_name_inn_common_name", ""),
            "status": r.get("current_status", ""),
            "procedure_start": _fmt(r.get("procedure_start_date", "")),
            "ec_decision_date": _fmt(r.get("european_commission_decision_date", "")),
            "safety_referral": r.get("safety_referral", ""),
            "prac_recommendation": r.get("prac_recommendation", ""),
            "referral_type": r.get("referral_type", ""),
            "url": r.get("referral_url", ""),
        }
        for r in records[:limit]
    ]


# ---------------------------------------------------------------------------
# DHPCs (Direct Healthcare Professional Communications)
# ---------------------------------------------------------------------------

def get_dhpcs(active_substance: Optional[str] = None, limit: int = 20) -> list[dict]:
    """Get EMA Direct Healthcare Professional Communications (safety letters).

    Returns list of dicts with: medicine_name, active_substance,
    dhpc_date, reason, therapeutic_area.
    """
    records = _get("dhpc-output-json-report_en.json")

    if active_substance:
        term = active_substance.lower()
        records = [r for r in records if term in (r.get("active_substance") or "").lower()
                   or term in (r.get("medicine_name") or "").lower()]

    return [
        {
            "medicine_name": r.get("medicine_name", ""),
            "active_substance": r.get("active_substance", ""),
            "dhpc_date": _parse_date(r.get("dhpc_date", "")),
            "reason": r.get("reason", ""),
            "therapeutic_area": r.get("therapeutic_area", ""),
        }
        for r in records[:limit]
    ]
