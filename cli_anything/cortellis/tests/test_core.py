"""Unit tests for Cortellis CLI core modules.

All tests mock HTTP calls via the ``responses`` library — no API credentials
are needed.  Run with::

    pytest cli_anything/cortellis/tests/test_core.py
"""
from __future__ import annotations

import json
import sys
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
import responses as responses_lib
from responses import matchers

from cli_anything.cortellis.core.client import CortellisClient, BASE_URL
from cli_anything.cortellis.core import query_builder as qb
from cli_anything.cortellis.core import ontology
from cli_anything.cortellis.core import analytics
from cli_anything.cortellis.core import literature
from cli_anything.cortellis.core import conferences
from cli_anything.cortellis.utils.output import (
    _print_json,
    _print_human,
    _cell_value,
    _humanize,
    _ordered_keys,
)


# ===========================================================================
# 1. Query builder tests
# ===========================================================================

class TestQueryBuilderPrimitives:
    def test_text(self):
        assert qb.text("drugName", "aspirin") == "drugName:aspirin"

    def test_numeric_id(self):
        assert qb.numeric_id("drugId", 12345) == "drugId::12345"

    def test_numeric_id_string(self):
        assert qb.numeric_id("drugId", "12345") == "drugId::12345"

    def test_linked_single(self):
        result = qb.linked("developmentStatusPhaseId:L")
        assert result == "LINKED(developmentStatusPhaseId:L)"

    def test_linked_multiple(self):
        result = qb.linked(
            "developmentStatusIndicationId:cancer",
            "developmentStatusPhaseId:L",
        )
        assert result == "LINKED(developmentStatusIndicationId:cancer AND developmentStatusPhaseId:L)"

    def test_linked_skips_empty(self):
        result = qb.linked("a:1", "", "b:2")
        assert result == "LINKED(a:1 AND b:2)"

    def test_range_both_bounds(self):
        assert qb.range_expr("dealDate", "2020-01-01", "2023-12-31") == "RANGE(dealDate, 2020-01-01, 2023-12-31)"

    def test_range_min_only(self):
        assert qb.range_expr("startDate", "2020-01-01") == "RANGE(startDate, 2020-01-01, )"

    def test_range_max_only(self):
        assert qb.range_expr("startDate", None, "2023-12-31") == "RANGE(startDate, , 2023-12-31)"

    def test_range_numeric(self):
        assert qb.range_expr("enrollmentCount", 100, 500) == "RANGE(enrollmentCount, 100, 500)"

    def test_and_joins(self):
        assert qb.and_("a:1", "b:2", "c:3") == "a:1 AND b:2 AND c:3"

    def test_and_skips_empty(self):
        assert qb.and_("a:1", "", "c:3") == "a:1 AND c:3"

    def test_and_single(self):
        assert qb.and_("a:1") == "a:1"

    def test_and_all_empty_returns_empty(self):
        assert qb.and_("", "") == ""

    def test_or_joins(self):
        assert qb.or_("a:1", "b:2") == "a:1 OR b:2"

    def test_or_skips_empty(self):
        assert qb.or_("", "b:2") == "b:2"


class TestBuildDrugQuery:
    def test_single_field(self):
        result = qb.build_drug_query(drug_name="aspirin")
        assert result == "drugNamesAll:aspirin"

    def test_multiple_fields(self):
        result = qb.build_drug_query(drug_name="aspirin", country="US")
        assert "drugNamesAll:aspirin" in result
        assert "developmentStatusCountryId:US" in result

    def test_phase_creates_linked(self):
        result = qb.build_drug_query(phase="L")
        assert result == "LINKED(developmentStatusPhaseId:L)"

    def test_phase_and_indication(self):
        result = qb.build_drug_query(phase="L", indication="cancer")
        assert "LINKED(" in result
        assert "developmentStatusIndicationId:cancer" in result
        assert "developmentStatusPhaseId:L" in result

    def test_historic_mode_switches_prefix(self):
        result = qb.build_drug_query(phase="L", historic=True)
        assert result is not None
        assert "developmentStatusHistoricPhaseId:L" in result
        assert "developmentStatusPhaseId:L" not in result or "Historic" in result

    def test_non_historic_uses_normal_prefix(self):
        result = qb.build_drug_query(phase="L", historic=False)
        assert result is not None
        assert "developmentStatusPhaseId:L" in result
        assert "Historic" not in result

    def test_free_query_passthrough(self):
        result = qb.build_drug_query(query="drugName:aspirin AND country:US")
        assert result == "drugName:aspirin AND country:US"

    def test_all_none_returns_none(self):
        assert qb.build_drug_query() is None


class TestBuildCompanyQuery:
    def test_name_only(self):
        assert qb.build_company_query(name="Pfizer") == "companyNameDisplay:Pfizer"

    def test_country_and_size(self):
        result = qb.build_company_query(country="US", size="Large")
        assert "companyHqCountry:US" in result
        assert "companyCategoryCompanySize:Large" in result

    def test_all_none_returns_none(self):
        assert qb.build_company_query() is None


class TestBuildDealsQuery:
    def test_date_range(self):
        result = qb.build_deals_query(date_start="2020-01-01", date_end="2023-12-31")
        assert "dealDateStart:2020-01-01" in result
        assert "dealDateEnd:2023-12-31" in result

    def test_drug_and_type(self):
        result = qb.build_deals_query(drug="aspirin", deal_type="Licensing")
        assert "dealDrugNamesAll:aspirin" in result
        assert "dealType:Licensing" in result

    def test_all_none_returns_none(self):
        assert qb.build_deals_query() is None


class TestBuildTrialsQuery:
    def test_phase_and_status(self):
        result = qb.build_trials_query(phase="Phase III", status="Ongoing")
        assert 'trialPhase:"Phase III"' in result
        assert "trialRecruitmentStatus:Ongoing" in result

    def test_date_range(self):
        result = qb.build_trials_query(date_start="2020-01-01")
        assert "trialDateStart:2020-01-01" in result

    def test_all_none_returns_none(self):
        assert qb.build_trials_query() is None


class TestBuildRegulatoryQuery:
    def test_region_and_doc_type(self):
        result = qb.build_regulatory_query(region="US", doc_type="Label")
        assert "regulatoryRegion:US" in result
        assert 'regulatoryDocType:"Label"' in result

    def test_all_none_returns_none(self):
        # With include_outdated=False (default), regulatoryStatus:valid is appended
        result = qb.build_regulatory_query()
        assert result == "regulatoryStatus:valid"

    def test_all_none_include_outdated_returns_none(self):
        assert qb.build_regulatory_query(include_outdated=True) is None


# ===========================================================================
# 2. Client tests
# ===========================================================================

class TestCortellisClientLazyInit:
    def test_no_session_before_first_request(self):
        client = CortellisClient(username="user", password="pass")
        assert client._session is None

    def test_session_created_on_property_access(self):
        client = CortellisClient(username="user", password="pass")
        session = client.session
        assert session is not None
        assert client._session is not None

    def test_session_reused(self):
        client = CortellisClient(username="user", password="pass")
        s1 = client.session
        s2 = client.session
        assert s1 is s2


class TestCortellisClientGet:
    @responses_lib.activate
    def test_get_success(self):
        url = BASE_URL + "cortellis/drugs1/search"
        payload = {"totalCount": 1, "hits": [{"drugId": "101964", "drugName": "tirzepatide"}]}
        responses_lib.add(responses_lib.GET, url, json=payload, status=200)

        client = CortellisClient(username="user", password="pass")
        result = client.get("cortellis/drugs1/search")
        assert result == payload

    @responses_lib.activate
    def test_get_passes_params(self):
        url = BASE_URL + "cortellis/drugs1/search"
        payload = {"totalCount": 0, "hits": []}
        responses_lib.add(responses_lib.GET, url, json=payload, status=200)

        client = CortellisClient(username="user", password="pass")
        client.get("cortellis/drugs1/search", params={"query": "drugName:aspirin", "hits": 5})

        assert len(responses_lib.calls) == 1
        called_params = responses_lib.calls[0].request.url
        assert "query=" in called_params
        assert "hits=" in called_params

    @responses_lib.activate
    def test_http_error_raises(self):
        url = BASE_URL + "cortellis/drugs1/search"
        responses_lib.add(responses_lib.GET, url, json={"error": "Unauthorized"}, status=401)

        client = CortellisClient(username="bad", password="creds")
        import requests
        with pytest.raises(requests.HTTPError):
            client.get("cortellis/drugs1/search")

    @responses_lib.activate
    def test_digest_auth_header_sent(self):
        """Client must set up Digest auth on the session."""
        url = BASE_URL + "cortellis/drugs1/search"
        responses_lib.add(responses_lib.GET, url, json={}, status=200)

        client = CortellisClient(username="testuser", password="testpass")
        # Access the session property to confirm auth is configured
        from requests.auth import HTTPDigestAuth
        assert isinstance(client.session.auth, HTTPDigestAuth)
        assert client.session.auth.username == "testuser"
        assert client.session.auth.password == "testpass"

    def test_credentials_from_env(self, monkeypatch):
        monkeypatch.setenv("CORTELLIS_USERNAME", "envuser")
        monkeypatch.setenv("CORTELLIS_PASSWORD", "envpass")
        client = CortellisClient()
        assert client.username == "envuser"
        assert client.password == "envpass"

    def test_explicit_credentials_override_env(self, monkeypatch):
        monkeypatch.setenv("CORTELLIS_USERNAME", "envuser")
        client = CortellisClient(username="explicit")
        assert client.username == "explicit"

    @responses_lib.activate
    def test_close_clears_session(self):
        url = BASE_URL + "test"
        responses_lib.add(responses_lib.GET, url, json={}, status=200)

        client = CortellisClient(username="user", password="pass")
        _ = client.session  # trigger session creation
        client.close()
        assert client._session is None


# ===========================================================================
# 3. Domain module tests
# ===========================================================================

class TestOntologyDomain:
    @responses_lib.activate
    def test_top_level_with_category(self):
        url = BASE_URL + "ontologies-v1/taxonomy/indication/root"
        responses_lib.add(responses_lib.GET, url, json={"items": []}, status=200)

        client = CortellisClient(username="u", password="p")
        result = ontology.top_level(client, category="indication")
        assert result == {"items": []}

    @responses_lib.activate
    def test_search(self):
        url = BASE_URL + "ontologies-v1/taxonomy/indication/search/cancer"
        payload = {"results": []}
        responses_lib.add(responses_lib.GET, url, json=payload, status=200)

        client = CortellisClient(username="u", password="p")
        result = ontology.search(client, category="indication", term="cancer")
        assert result == payload

    @responses_lib.activate
    def test_children(self):
        url = BASE_URL + "ontologies-v1/taxonomy/indication/children/1.1"
        responses_lib.add(responses_lib.GET, url, json={"nodes": []}, status=200)

        client = CortellisClient(username="u", password="p")
        ontology.children(client, category="indication", tree_code="1.1")

        assert responses_lib.calls[0].request.url == url

    @responses_lib.activate
    def test_parents(self):
        url = BASE_URL + "ontologies-v1/taxonomy/indication/parent/1.1.2"
        responses_lib.add(responses_lib.GET, url, json={"nodes": []}, status=200)

        client = CortellisClient(username="u", password="p")
        ontology.parents(client, category="indication", tree_code="1.1.2")

        assert responses_lib.calls[0].request.url == url


class TestAnalyticsDomain:
    @responses_lib.activate
    def test_run_query_name_in_path(self):
        url = BASE_URL + "analytics-v2/analysis/drugPipelineByPhase"
        responses_lib.add(responses_lib.GET, url, json={"data": []}, status=200)

        client = CortellisClient(username="u", password="p")
        analytics.run(client, query_name="drugPipelineByPhase")

        assert responses_lib.calls[0].request.url == url

    @responses_lib.activate
    def test_run_with_drug_id(self):
        url = BASE_URL + "analytics-v2/analysis/drugTimeline"
        responses_lib.add(responses_lib.GET, url, json={}, status=200)

        client = CortellisClient(username="u", password="p")
        analytics.run(client, query_name="drugTimeline", drug_id="101964")

        req_url = responses_lib.calls[0].request.url
        assert "drugId=101964" in req_url

    @responses_lib.activate
    def test_run_with_id_list(self):
        url = BASE_URL + "analytics-v2/analysis/batchQuery"
        responses_lib.add(responses_lib.GET, url, json={}, status=200)

        client = CortellisClient(username="u", password="p")
        analytics.run(client, query_name="batchQuery", id_list=["1", "2", "3"])

        req_url = responses_lib.calls[0].request.url
        assert "idList=1%2C2%2C3" in req_url or "idList=1,2,3" in req_url


class TestLiteratureDomain:
    @responses_lib.activate
    def test_search_with_query(self):
        url = BASE_URL + "literature-v2/literature/search"
        payload = {"totalCount": 2, "hits": []}
        responses_lib.add(responses_lib.GET, url, json=payload, status=200)

        client = CortellisClient(username="u", password="p")
        result = literature.search(client, query="aspirin AND cancer")
        assert result == payload
        assert "query=aspirin" in responses_lib.calls[0].request.url

    @responses_lib.activate
    def test_search_default_pagination(self):
        url = BASE_URL + "literature-v2/literature/search"
        responses_lib.add(responses_lib.GET, url, json={}, status=200)

        client = CortellisClient(username="u", password="p")
        literature.search(client)

        req_url = responses_lib.calls[0].request.url
        assert "offset=0" in req_url
        assert "hits=10" in req_url

    @responses_lib.activate
    def test_get_by_id(self):
        url = BASE_URL + "literature-v2/literature/LIT123"
        payload = {"literatureId": "LIT123", "title": "A study"}
        responses_lib.add(responses_lib.GET, url, json=payload, status=200)

        client = CortellisClient(username="u", password="p")
        result = literature.get(client, "LIT123")
        assert result == payload


class TestConferencesDomain:
    @responses_lib.activate
    def test_search_with_query(self):
        url = BASE_URL + "conference-v2/conference/search"
        payload = {"hits": [{"conferenceId": "C1", "name": "ASCO 2024"}]}
        responses_lib.add(responses_lib.GET, url, json=payload, status=200)

        client = CortellisClient(username="u", password="p")
        result = conferences.search(client, query="ASCO")
        assert result == payload

    @responses_lib.activate
    def test_get_by_id(self):
        url = BASE_URL + "conference-v2/conference/C1"
        payload = {"conferenceId": "C1"}
        responses_lib.add(responses_lib.GET, url, json=payload, status=200)

        client = CortellisClient(username="u", password="p")
        result = conferences.get(client, "C1")
        assert result == payload


# ---------------------------------------------------------------------------
# Domain tests for modules not yet written — test via query_builder only
# ---------------------------------------------------------------------------

class TestDrugsViaQueryBuilder:
    """Tests for drugs domain logic exercised through query_builder."""

    def test_drugs_search_builds_correct_params_phase(self):
        q = qb.build_drug_query(phase="L")
        assert q == "LINKED(developmentStatusPhaseId:L)"

    def test_drugs_search_builds_correct_params_company(self):
        q = qb.build_drug_query(company="Pfizer", phase="Phase III")
        assert q is not None
        assert "LINKED(" in q
        assert "developmentStatusCompanyId:Pfizer" in q
        assert 'developmentStatusPhaseId:"Phase III"' in q

    def test_drugs_get_with_category_query_string(self):
        # Category is passed as a path/param in the CLI — just verify
        # the query builder doesn't interfere with simple gets
        q = qb.build_drug_query(drug_name="tirzepatide")
        assert q == "drugNamesAll:tirzepatide"


class TestDealsViaQueryBuilder:
    def test_deals_date_range_query(self):
        q = qb.build_deals_query(date_start="2022-01-01", date_end="2022-12-31")
        assert "dealDateStart:2022-01-01" in q
        assert "dealDateEnd:2022-12-31" in q

    def test_deals_principal_and_partner(self):
        q = qb.build_deals_query(principal="AstraZeneca", partner="Merck")
        assert "dealCompanyPrincipal:AstraZeneca" in q
        assert "dealCompanyPartner:Merck" in q


# ===========================================================================
# 4. Output formatting tests
# ===========================================================================

class TestCellValue:
    def test_none_returns_empty(self):
        assert _cell_value(None) == ""

    def test_scalar_string(self):
        assert _cell_value("hello") == "hello"

    def test_scalar_int(self):
        assert _cell_value(42) == "42"

    def test_long_string_truncated(self):
        long_str = "a" * 100
        result = _cell_value(long_str, max_len=80)
        assert len(result) <= 80
        assert result.endswith("…")

    def test_short_string_not_truncated(self):
        assert _cell_value("short") == "short"

    def test_empty_list(self):
        assert _cell_value([]) == ""

    def test_list_of_scalars(self):
        result = _cell_value(["a", "b", "c"])
        assert "a" in result and "b" in result and "c" in result

    def test_list_truncated_at_five(self):
        result = _cell_value(["a", "b", "c", "d", "e", "f"])
        assert "+1 more" in result

    def test_list_of_dicts_shows_count(self):
        result = _cell_value([{"k": "v"}, {"k": "v2"}])
        assert "[2 items]" == result

    def test_dict_shows_key_count(self):
        result = _cell_value({"a": 1, "b": 2})
        assert "2 keys" in result


class TestHumanize:
    def test_camel_case(self):
        assert _humanize("drugName") == "Drug Name"

    def test_snake_case(self):
        assert _humanize("drug_name") == "Drug Name"

    def test_all_caps_acronym(self):
        # Verify doesn't crash on all-caps
        result = _humanize("drugID")
        assert isinstance(result, str)

    def test_simple_word(self):
        assert _humanize("phase") == "Phase"


class TestOrderedKeys:
    def test_priority_keys_come_first(self):
        records = [{"phase": "L", "drugName": "aspirin", "drugId": "1"}]
        keys = _ordered_keys(records)
        assert keys.index("drugId") < keys.index("drugName")
        assert keys.index("drugName") < keys.index("phase")

    def test_non_priority_keys_included(self):
        records = [{"customField": "val", "drugId": "1"}]
        keys = _ordered_keys(records)
        assert "customField" in keys
        assert "drugId" in keys

    def test_keys_from_all_records(self):
        records = [{"drugId": "1"}, {"companyId": "2"}]
        keys = _ordered_keys(records)
        assert "drugId" in keys
        assert "companyId" in keys


class TestPrintJson:
    def test_dict_serialised(self, capsys):
        _print_json({"key": "value"})
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data == {"key": "value"}

    def test_list_serialised(self, capsys):
        _print_json([1, 2, 3])
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data == [1, 2, 3]

    def test_none_serialised(self, capsys):
        _print_json(None)
        out = capsys.readouterr().out
        assert json.loads(out) is None


class TestPrintHuman:
    def test_none_prints_no_data(self, capsys):
        # Rich prints to its own console — patch _console to capture
        with patch("cli_anything.cortellis.utils.output._console") as mock_console:
            _print_human(None)
            mock_console.print.assert_called_once()
            call_args = mock_console.print.call_args[0][0]
            assert "No data" in call_args

    def test_empty_list_prints_no_results(self):
        with patch("cli_anything.cortellis.utils.output._console") as mock_console:
            _print_human([])
            mock_console.print.assert_called_once()
            call_args = mock_console.print.call_args[0][0]
            assert "No results" in call_args

    def test_list_of_dicts_calls_render_table(self):
        records = [{"drugId": "1", "drugName": "aspirin"}]
        with patch("cli_anything.cortellis.utils.output._render_table") as mock_table:
            _print_human(records)
            mock_table.assert_called_once_with(records)

    def test_dict_calls_render_dict(self):
        record = {"drugId": "1", "drugName": "aspirin"}
        with patch("cli_anything.cortellis.utils.output._render_dict") as mock_dict:
            _print_human(record)
            mock_dict.assert_called_once_with(record)

    def test_scalar_prints_as_string(self):
        with patch("cli_anything.cortellis.utils.output._console") as mock_console:
            _print_human("hello world")
            mock_console.print.assert_called_once_with("hello world")
