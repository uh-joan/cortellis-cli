"""Unit tests for enrich_deal_financials recipe.

No real API calls — all external I/O is mocked.

Run with:
    pytest cli_anything/cortellis/tests/test_deal_financials.py -v
"""
from __future__ import annotations

import csv
import io
import os
import sys
import tempfile
from unittest.mock import MagicMock, patch

import pytest

# Allow import without installing the package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

from cli_anything.cortellis.skills.landscape.recipes.enrich_deal_financials import (
    extract_deal_ids,
    extract_financials,
    fetch_expanded_deals,
    generate_comps_markdown,
    write_financials_csv,
    build_records,
    FINANCIALS_COLUMNS,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_DEALS_CSV = """\
id,title,principal,partner,type,date
D001,Deal Alpha,AcmePharma,BetaBio,License,2022-03-15
D002,Deal Beta,GammaCorp,,Acquisition,2023-07-01
D003,Deal Gamma,DeltaInc,EpsilonLtd,Co-development,2021-11-20
"""

SAMPLE_EXPANDED_DEAL_FULL = {
    "@id": "D001",
    "title": "Deal Alpha",
    "principal": "AcmePharma",
    "partner": "BetaBio",
    "dealType": "License",
    "date": "2022-03-15",
    "upfrontPayment": "50000000",
    "milestonePayments": "200000000",
    "royaltyRate": "10%",
    "totalDealValue": "250000000",
    "financialTermsText": "50M upfront, up to 200M in milestones, 10% royalty",
}

SAMPLE_EXPANDED_DEAL_NESTED = {
    "@id": "D002",
    "title": "Deal Beta",
    "financialTerms": {
        "upfrontPayment": "30000000",
        "milestonePayments": "100000000",
        "royaltyRate": "8%",
        "totalDealValue": "130000000",
        "termsText": "30M upfront, 100M milestones",
    },
}

SAMPLE_EXPANDED_DEAL_MISSING = {
    "@id": "D003",
    "title": "Deal Gamma",
    "dealType": "Co-development",
    "date": "2021-11-20",
    # No financial fields at all
}


# ---------------------------------------------------------------------------
# test_extract_deal_ids
# ---------------------------------------------------------------------------

class TestExtractDealIds:
    def test_reads_ids_from_deals_csv(self, tmp_path):
        csv_path = tmp_path / "deals.csv"
        csv_path.write_text(SAMPLE_DEALS_CSV, encoding="utf-8")
        ids = extract_deal_ids(str(tmp_path))
        assert ids == ["D001", "D002", "D003"]

    def test_returns_empty_when_no_file(self, tmp_path):
        ids = extract_deal_ids(str(tmp_path))
        assert ids == []

    def test_skips_rows_with_empty_id(self, tmp_path):
        csv_path = tmp_path / "deals.csv"
        csv_path.write_text(
            "id,title\n,No ID Deal\nD001,Real Deal\n",
            encoding="utf-8",
        )
        ids = extract_deal_ids(str(tmp_path))
        assert ids == ["D001"]

    def test_accepts_deal_id_column_name(self, tmp_path):
        csv_path = tmp_path / "deals.csv"
        csv_path.write_text(
            "deal_id,title\nX001,Deal X\nX002,Deal Y\n",
            encoding="utf-8",
        )
        ids = extract_deal_ids(str(tmp_path))
        assert ids == ["X001", "X002"]


# ---------------------------------------------------------------------------
# test_extract_financials_full
# ---------------------------------------------------------------------------

class TestExtractFinancialsFull:
    def test_top_level_fields(self):
        result = extract_financials(SAMPLE_EXPANDED_DEAL_FULL)
        assert result["upfront_payment"] == "50000000"
        assert result["milestone_payments"] == "200000000"
        assert result["royalty_rate"] == "10%"
        assert result["total_deal_value"] == "250000000"
        assert "upfront" in result["financial_terms_text"].lower()

    def test_nested_financial_terms(self):
        result = extract_financials(SAMPLE_EXPANDED_DEAL_NESTED)
        assert result["upfront_payment"] == "30000000"
        assert result["milestone_payments"] == "100000000"
        assert result["royalty_rate"] == "8%"
        assert result["total_deal_value"] == "130000000"

    def test_returns_strings_not_none(self):
        result = extract_financials(SAMPLE_EXPANDED_DEAL_FULL)
        for key in ("upfront_payment", "milestone_payments", "royalty_rate",
                    "total_deal_value", "financial_terms_text"):
            assert result[key] is not None
            assert isinstance(result[key], str)


# ---------------------------------------------------------------------------
# test_extract_financials_missing
# ---------------------------------------------------------------------------

class TestExtractFinancialsMissing:
    def test_missing_fields_default_to_empty_string(self):
        result = extract_financials(SAMPLE_EXPANDED_DEAL_MISSING)
        assert result["upfront_payment"] == ""
        assert result["milestone_payments"] == ""
        assert result["royalty_rate"] == ""
        assert result["total_deal_value"] == ""
        assert result["financial_terms_text"] == ""

    def test_none_input_returns_empty_strings(self):
        result = extract_financials(None)
        for key in ("upfront_payment", "milestone_payments", "royalty_rate",
                    "total_deal_value", "financial_terms_text"):
            assert result[key] == ""

    def test_empty_dict_returns_empty_strings(self):
        result = extract_financials({})
        for key in ("upfront_payment", "milestone_payments", "royalty_rate",
                    "total_deal_value", "financial_terms_text"):
            assert result[key] == ""

    def test_partial_fields_populated(self):
        deal = {"@id": "X", "upfrontPayment": "5000000"}
        result = extract_financials(deal)
        assert result["upfront_payment"] == "5000000"
        assert result["milestone_payments"] == ""
        assert result["royalty_rate"] == ""
        assert result["total_deal_value"] == ""


# ---------------------------------------------------------------------------
# test_generate_comps_markdown
# ---------------------------------------------------------------------------

class TestGenerateCompsMarkdown:
    def _make_records(self):
        return [
            {
                "deal_id": "D001",
                "title": "Deal Alpha",
                "principal": "AcmePharma",
                "partner": "BetaBio",
                "type": "License",
                "date": "2022-03-15",
                "upfront_payment": "50000000",
                "milestone_payments": "200000000",
                "royalty_rate": "10%",
                "total_deal_value": "250000000",
                "financial_terms_text": "",
            },
            {
                "deal_id": "D002",
                "title": "Deal Beta",
                "principal": "GammaCorp",
                "partner": "",
                "type": "Acquisition",
                "date": "2023-07-01",
                "upfront_payment": "800000000",
                "milestone_payments": "",
                "royalty_rate": "",
                "total_deal_value": "800000000",
                "financial_terms_text": "",
            },
        ]

    def test_produces_markdown_table(self):
        records = self._make_records()
        md = generate_comps_markdown(records)
        assert "# Deal Comparables" in md
        assert "| Deal |" in md
        assert "Deal Alpha" in md
        assert "Deal Beta" in md

    def test_sorted_by_total_value_desc(self):
        records = self._make_records()
        md = generate_comps_markdown(records)
        # Deal Beta (800M) should appear before Deal Alpha (250M)
        beta_pos = md.index("Deal Beta")
        alpha_pos = md.index("Deal Alpha")
        assert beta_pos < alpha_pos

    def test_summary_stats_present(self):
        records = self._make_records()
        md = generate_comps_markdown(records)
        assert "Median total value" in md
        assert "Most common type" in md
        assert "Date range" in md

    def test_includes_deals_with_financials_only(self):
        records = self._make_records()
        # Add a record with no financials
        records.append({
            "deal_id": "D003",
            "title": "Deal No Financials",
            "principal": "X",
            "partner": "",
            "type": "License",
            "date": "2020-01-01",
            "upfront_payment": "",
            "milestone_payments": "",
            "royalty_rate": "",
            "total_deal_value": "",
            "financial_terms_text": "",
        })
        md = generate_comps_markdown(records)
        assert "Deal No Financials" not in md


# ---------------------------------------------------------------------------
# test_generate_comps_empty
# ---------------------------------------------------------------------------

class TestGenerateCompsEmpty:
    def test_empty_records_list(self):
        md = generate_comps_markdown([])
        assert "No deals with financial terms available" in md

    def test_all_records_missing_financials(self):
        records = [
            {
                "deal_id": "D001",
                "title": "Deal Bare",
                "principal": "X",
                "partner": "",
                "type": "License",
                "date": "2022-01-01",
                "upfront_payment": "",
                "milestone_payments": "",
                "royalty_rate": "",
                "total_deal_value": "",
                "financial_terms_text": "",
            }
        ]
        md = generate_comps_markdown(records)
        assert "No deals with financial terms available" in md


# ---------------------------------------------------------------------------
# test_write_financials_csv
# ---------------------------------------------------------------------------

class TestWriteFinancialsCsv:
    def _sample_records(self):
        return [
            {
                "deal_id": "D001",
                "title": "Deal Alpha",
                "principal": "AcmePharma",
                "partner": "BetaBio",
                "type": "License",
                "date": "2022-03-15",
                "upfront_payment": "50000000",
                "milestone_payments": "200000000",
                "royalty_rate": "10%",
                "total_deal_value": "250000000",
                "financial_terms_text": "50M upfront",
            },
        ]

    def test_roundtrip_write_read(self, tmp_path):
        records = self._sample_records()
        out_path = str(tmp_path / "deal_financials.csv")
        write_financials_csv(records, out_path)

        assert os.path.exists(out_path)
        with open(out_path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

        assert len(rows) == 1
        row = rows[0]
        assert row["deal_id"] == "D001"
        assert row["title"] == "Deal Alpha"
        assert row["upfront_payment"] == "50000000"
        assert row["total_deal_value"] == "250000000"
        assert row["financial_terms_text"] == "50M upfront"

    def test_columns_match_spec(self, tmp_path):
        records = self._sample_records()
        out_path = str(tmp_path / "deal_financials.csv")
        write_financials_csv(records, out_path)

        with open(out_path, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader)

        assert header == FINANCIALS_COLUMNS

    def test_writes_empty_file_with_header(self, tmp_path):
        out_path = str(tmp_path / "deal_financials.csv")
        write_financials_csv([], out_path)

        with open(out_path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

        assert rows == []


# ---------------------------------------------------------------------------
# test_fetch_expanded_deals (mocked)
# ---------------------------------------------------------------------------

class TestFetchExpandedDeals:
    def test_calls_get_expanded_batch(self):
        mock_client = MagicMock()
        mock_response = [SAMPLE_EXPANDED_DEAL_FULL]

        with patch(
            "cli_anything.cortellis.skills.landscape.recipes.enrich_deal_financials.deals_intelligence.get_expanded_batch",
            return_value=mock_response,
        ) as mock_batch, patch(
            "cli_anything.cortellis.skills.landscape.recipes.enrich_deal_financials.time.sleep"
        ):
            results = fetch_expanded_deals(["D001"], mock_client)

        mock_batch.assert_called_once_with(mock_client, ["D001"])
        assert len(results) == 1

    def test_handles_batch_failure_gracefully(self):
        mock_client = MagicMock()

        with patch(
            "cli_anything.cortellis.skills.landscape.recipes.enrich_deal_financials.deals_intelligence.get_expanded_batch",
            side_effect=Exception("network error"),
        ), patch(
            "cli_anything.cortellis.skills.landscape.recipes.enrich_deal_financials.time.sleep"
        ):
            results = fetch_expanded_deals(["D001", "D002"], mock_client)

        assert results == []

    def test_batches_by_batch_size(self):
        mock_client = MagicMock()
        # 35 IDs should produce 2 batches (30 + 5)
        deal_ids = [f"D{i:03d}" for i in range(35)]

        with patch(
            "cli_anything.cortellis.skills.landscape.recipes.enrich_deal_financials.deals_intelligence.get_expanded_batch",
            return_value=[],
        ) as mock_batch, patch(
            "cli_anything.cortellis.skills.landscape.recipes.enrich_deal_financials.time.sleep"
        ):
            fetch_expanded_deals(deal_ids, mock_client)

        assert mock_batch.call_count == 2
        first_call_ids = mock_batch.call_args_list[0][0][1]
        assert len(first_call_ids) == 30
        second_call_ids = mock_batch.call_args_list[1][0][1]
        assert len(second_call_ids) == 5
