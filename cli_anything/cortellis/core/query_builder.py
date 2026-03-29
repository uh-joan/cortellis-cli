"""Cortellis query syntax builder.

Cortellis uses a proprietary query language with these patterns:
  - field:value           text/enum match
  - field::id             numeric ID match (double colon)
  - LINKED(a AND b)       compound field grouping (development status)
  - RANGE(>=lo;<=hi)      numeric or date range

This module provides helpers to build these expressions without
scattering string formatting across domain modules.
"""

import re
from typing import Optional, Union


def text(field: str, value: str) -> str:
    """Return ``field:value`` expression. Quotes value if it contains spaces."""
    if " " in value:
        return f'{field}:"{value}"'
    return f"{field}:{value}"


def numeric_id(field: str, value: Union[int, str]) -> str:
    """Return ``field::id`` expression (double-colon for numeric IDs)."""
    return f"{field}::{value}"


def linked(*expressions: str) -> str:
    """Return ``LINKED(expr1 AND expr2 ...)`` compound expression.

    Used for development status compound fields that must be evaluated
    together (e.g. indication + action + phase within one status record).
    """
    combined = " AND ".join(e for e in expressions if e)
    return f"LINKED({combined})"


def range_expr(field: str, lo: Optional[Union[int, str]] = None, hi: Optional[Union[int, str]] = None) -> str:
    """Return ``RANGE(field, lo, hi)`` expression.

    Pass None for an open-ended bound.
    """
    lo_str = str(lo) if lo is not None else ""
    hi_str = str(hi) if hi is not None else ""
    return f"RANGE({field}, {lo_str}, {hi_str})"


def and_(*expressions: str) -> str:
    """Join non-empty expressions with AND."""
    parts = [e for e in expressions if e]
    if not parts:
        return ""
    return " AND ".join(parts)


def or_(*expressions: str) -> str:
    """Join non-empty expressions with OR."""
    parts = [e for e in expressions if e]
    if not parts:
        return ""
    return " OR ".join(parts)


def build_drug_query(
    query: Optional[str] = None,
    company: Optional[str] = None,
    indication: Optional[str] = None,
    action: Optional[str] = None,
    phase: Optional[str] = None,
    technology: Optional[str] = None,
    drug_name: Optional[str] = None,
    country: Optional[str] = None,
    historic: bool = False,
    phase_terminated: Optional[str] = None,
    status_date: Optional[str] = None,
) -> Optional[str]:
    """Build a Cortellis drug search query string from CLI options.

    When ``historic`` is True, uses ``developmentStatusHistoric*`` field names
    instead of ``developmentStatus*``.
    """
    parts = []

    if query:
        parts.append(query)
    if drug_name:
        parts.append(text("drugNamesAll", drug_name))
    if action:
        parts.append(text("actionsPrimary", action))
    if technology:
        parts.append(text("technologies", technology))
    if phase_terminated:
        # Support OR/AND between multiple phase codes (e.g. "DX OR NDR")
        tokens = re.split(r'\s+(OR|AND)\s+', phase_terminated)
        if len(tokens) > 1:
            # tokens = [val, op, val, op, val, ...]
            operator = tokens[1]  # first operator
            phases = tokens[::2]  # every other element is a value
            formatted = []
            for p in phases:
                p = p.strip()
                if re.match(r'^[A-Z0-9]+$', p):
                    formatted.append(f"phaseTerminated::{p}")
                else:
                    formatted.append(f'phaseTerminated:"{p}"')
            parts.append(f"({f' {operator} '.join(formatted)})")
        else:
            # Single value
            if re.match(r'^[A-Z0-9]+$', phase_terminated):
                parts.append(f"phaseTerminated::{phase_terminated}")
            else:
                parts.append(text("phaseTerminated", phase_terminated))

    # Development status LINKED block
    prefix = "developmentStatusHistoric" if historic else "developmentStatus"
    linked_parts = []
    if indication:
        linked_parts.append(text(f"{prefix}IndicationId", indication))
    if phase:
        linked_parts.append(text(f"{prefix}PhaseId", phase))
    if company:
        linked_parts.append(text(f"{prefix}CompanyId", company))
    if country:
        linked_parts.append(text(f"{prefix}CountryId", country))
    if status_date:
        field = f"{prefix}Date"
        linked_parts.append(text(field, status_date))

    if linked_parts:
        parts.append(linked(*linked_parts))

    return and_(*parts) if parts else None


def build_company_query(
    query: Optional[str] = None,
    name: Optional[str] = None,
    country: Optional[str] = None,
    size: Optional[str] = None,
    deals_count: Optional[str] = None,
    indications: Optional[str] = None,
    actions: Optional[str] = None,
    technologies: Optional[str] = None,
    status: Optional[str] = None,
) -> Optional[str]:
    parts = []
    if query:
        parts.append(query)
    if name:
        parts.append(text("companyNameDisplay", name))
    if country:
        parts.append(text("companyHqCountry", country))

    if size is not None:
        size_str = str(size).strip()
        op = "<" if size_str.startswith("<") else ">"
        val_str = size_str.lstrip("<>")
        try:
            val = float(val_str) * 1_000_000_000
            parts.append(f"companyCategoryCompanySize:RANGE({op}{val:.0f})")
        except ValueError:
            parts.append(text("companyCategoryCompanySize", size_str))

    if deals_count is not None:
        dc = str(deals_count).strip()
        op = "<" if dc.startswith("<") else ">"
        val_str = dc.lstrip("<>")
        try:
            val = int(val_str)
            parts.append(f"companyDealsCount:RANGE({op}{val})")
        except ValueError:
            parts.append(text("companyDealsCount", dc))

    if indications:
        parts.append(text("companyIndicationsKey", indications))
    if actions:
        parts.append(text("companyActionsKey", actions))
    if technologies:
        parts.append(text("companyTechnologiesKey", technologies))
    if status:
        # Map short phase codes to full text values expected by the API
        _STATUS_MAP = {
            "S": "Suspended", "DR": "Preclinical", "CU": "Clinical",
            "C1": "Phase 1 Clinical", "C2": "Phase 2 Clinical",
            "C3": "Phase 3 Clinical", "PR": "Pre-registration",
            "R": "Registered", "L": "Launched", "OL": "Outlicensed",
            "NDR": "No Development Reported", "DX": "Discontinued", "W": "Withdrawn",
        }
        status_val = _STATUS_MAP.get(status.upper(), status)
        parts.append(f"LINKED(statusLinked:{status_val})")

    return and_(*parts) if parts else None


def build_deals_query(
    query: Optional[str] = None,
    drug: Optional[str] = None,
    indication: Optional[str] = None,
    deal_type: Optional[str] = None,
    status: Optional[str] = None,
    principal: Optional[str] = None,
    partner: Optional[str] = None,
    action: Optional[str] = None,
    date_start: Optional[str] = None,
    date_end: Optional[str] = None,
    # Additional MCP params
    indication_partner_company: Optional[str] = None,
    phase_start: Optional[str] = None,
    phase_now: Optional[str] = None,
    deal_status: Optional[str] = None,
    summary: Optional[str] = None,
    title_summary: Optional[str] = None,
    technology: Optional[str] = None,
    title: Optional[str] = None,
    actions_primary: Optional[str] = None,
    principal_hq: Optional[str] = None,
    territories_included: Optional[str] = None,
    territories_excluded: Optional[str] = None,
    date_most_recent: Optional[str] = None,
    max_value_paid_to_partner: Optional[str] = None,
    total_projected_current_amount: Optional[str] = None,
    min_value_paid_to_partner: Optional[str] = None,
    total_paid_amount: Optional[str] = None,
    disclosure_status: Optional[str] = None,
) -> Optional[str]:
    parts = []
    if query:
        parts.append(query)
    if drug:
        parts.append(text("dealDrugNamesAll", drug))
    if indication:
        parts.append(text("indications", indication))
    if indication_partner_company:
        parts.append(text("dealDrugCompanyPartnerIndications", indication_partner_company))
    if deal_type:
        parts.append(text("dealType", deal_type))
    # status maps to dealStatus field
    if status:
        parts.append(text("dealStatus", status))
    if deal_status:
        parts.append(text("dealStatus", deal_status))
    if principal:
        parts.append(text("dealCompanyPrincipal", principal))
    if partner:
        parts.append(text("dealCompanyPartner", partner))
    if principal_hq:
        parts.append(text("dealCompanyPrincipalHq", principal_hq))
    if action:
        parts.append(text("actionsPrimary", action))
    if actions_primary:
        parts.append(text("dealDrugActionsPrimary", actions_primary))
    if technology:
        parts.append(text("technologies", technology))
    if title:
        parts.append(text("dealTitle", title))
    if summary:
        parts.append(text("dealSummary", summary))
    if title_summary:
        parts.append(text("dealTitleSummary", title_summary))
    if phase_start:
        parts.append(text("dealPhaseHighestStart", phase_start))
    if phase_now:
        parts.append(text("dealPhaseHighestNow", phase_now))
    if territories_included:
        parts.append(text("dealTerritoriesIncluded", territories_included))
    if territories_excluded:
        parts.append(text("dealTerritoriesExcluded", territories_excluded))
    if date_start:
        parts.append(text("dealDateStart", date_start))
    if date_end:
        parts.append(text("dealDateEnd", date_end))
    if date_most_recent:
        parts.append(text("dealDateEventMostRecent", date_most_recent))
    if max_value_paid_to_partner:
        parts.append(text("dealValuePaidToPartnerMaxNumber", max_value_paid_to_partner))
    if min_value_paid_to_partner:
        parts.append(text("dealValuePaidToPartnerMinNumber", min_value_paid_to_partner))
    if total_projected_current_amount:
        parts.append(text("dealTotalProjectedCurrentAmount", total_projected_current_amount))
    if total_paid_amount:
        parts.append(text("dealTotalPaidAmount", total_paid_amount))
    if disclosure_status:
        parts.append(text("dealValuePaidToPrincipalMaxDisclosureStatus", disclosure_status))
    return and_(*parts) if parts else None


def build_trials_query(
    query: Optional[str] = None,
    indication: Optional[str] = None,
    phase: Optional[str] = None,
    recruitment_status: Optional[str] = None,
    status: Optional[str] = None,
    sponsor: Optional[str] = None,
    funder_type: Optional[str] = None,
    identifier: Optional[str] = None,
    title: Optional[str] = None,
    date_start: Optional[str] = None,
    date_end: Optional[str] = None,
    enrollment: Optional[str] = None,
) -> Optional[str]:
    parts = []
    if query:
        parts.append(query)
    if indication:
        # Numeric IDs use double-colon; text values use single colon
        if re.match(r'^\d+$', indication):
            parts.append(f"indications::{indication}")
        else:
            parts.append(f'indications:"{indication}"')
    if phase:
        # Short codes (e.g. "C3", "3") use double-colon; descriptive text uses single colon
        if re.match(r'^[A-Z0-9]+$', phase):
            parts.append(f"trialPhase::{phase}")
        else:
            parts.append(text("trialPhase", phase))
    # recruitment_status takes precedence; fall back to status for backward compat
    rs = recruitment_status or status
    if rs:
        parts.append(text("trialRecruitmentStatus", rs))
    if sponsor:
        parts.append(text("trialCompaniesSponsor", sponsor))
    if funder_type:
        parts.append(text("trialFunderType", funder_type))
    if identifier:
        parts.append(text("trialIdentifiers", identifier))
    if title:
        parts.append(text("trialTitleOfficial", title))
    if enrollment:
        parts.append(text("trialPatientCountEnrollment", enrollment))
    if date_start:
        parts.append(text("trialDateStart", date_start))
    if date_end:
        parts.append(text("trialDateEnd", date_end))
    return and_(*parts) if parts else None


def build_regulatory_query(
    query: Optional[str] = None,
    region: Optional[str] = None,
    doc_category: Optional[str] = None,
    doc_type: Optional[str] = None,
    language: Optional[str] = None,
    prod_category: Optional[str] = None,
    include_outdated: bool = False,
) -> Optional[str]:
    parts = []
    if query:
        parts.append(query)
    if region:
        parts.append(text("regulatoryRegion", region))
    if doc_category:
        parts.append(f'regulatoryDocCategory:"{doc_category}"')
    if doc_type:
        parts.append(f'regulatoryDocType:"{doc_type}"')
    if language:
        parts.append(text("regulatoryLanguages", language))
    if prod_category:
        parts.append(f'regulatoryProdCategory:"{prod_category}"')
    if not include_outdated:
        # Only add status filter if not already present
        combined = and_(*parts) if parts else ""
        if "regulatorystatus:" not in combined.lower():
            parts.append("regulatoryStatus:valid")
    return and_(*parts) if parts else None
