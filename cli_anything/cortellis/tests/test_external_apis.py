"""Smoke tests for external API modules in cli_anything/cortellis/core/.

All HTTP calls are mocked — no network access required.
Run with:
    uv run python -m pytest cli_anything/cortellis/tests/test_external_apis.py --tb=short -q
"""
from __future__ import annotations

import io
import json
import sys
import os
import unittest
from unittest.mock import patch, MagicMock

# Ensure project root is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))


# ---------------------------------------------------------------------------
# Helper: build a mock requests.Response
# ---------------------------------------------------------------------------

def _mock_response(payload: dict | list, status: int = 200) -> MagicMock:
    m = MagicMock()
    m.status_code = status
    m.json.return_value = payload
    return m


def _mock_urllib_response(payload: dict | list) -> MagicMock:
    """Return a context-manager mock for urllib.request.urlopen."""
    body = json.dumps(payload).encode("utf-8")
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=cm)
    cm.__exit__ = MagicMock(return_value=False)
    cm.read.return_value = body
    return cm


# ---------------------------------------------------------------------------
# 1. biorxiv
# ---------------------------------------------------------------------------

class TestBiorxiv(unittest.TestCase):
    def test_search_returns_normalized_list(self):
        from cli_anything.cortellis.core import biorxiv

        raw = {
            "resultList": {
                "result": [
                    {
                        "doi": "10.1/x",
                        "title": "Test Paper",
                        "authorString": "Smith J",
                        "firstPublicationDate": "2024-01-01",
                        "abstractText": "Abstract here",
                        "source": "PPR",
                    }
                ]
            }
        }

        with patch("cli_anything.cortellis.core.biorxiv.requests.get",
                   return_value=_mock_response(raw)):
            results = biorxiv.search("semaglutide", limit=1)

        self.assertEqual(len(results), 1)
        r = results[0]
        self.assertEqual(r["doi"], "10.1/x")
        self.assertEqual(r["title"], "Test Paper")
        self.assertEqual(r["authors"], "Smith J")
        self.assertEqual(r["date"], "2024-01-01")
        self.assertEqual(r["abstract"], "Abstract here")


# ---------------------------------------------------------------------------
# 2. chembl
# ---------------------------------------------------------------------------

class TestChembl(unittest.TestCase):
    def test_search_molecule_returns_normalized_list(self):
        from cli_anything.cortellis.core import chembl

        raw = {
            "molecules": [
                {
                    "molecule_chembl_id": "CHEMBL1234",
                    "pref_name": "SEMAGLUTIDE",
                    "max_phase": 4,
                    "molecule_type": "Protein",
                    "oral": False,
                    "parenteral": True,
                    "molecule_properties": None,
                    "biotherapeutic": None,
                    "molecule_structures": None,
                }
            ]
        }

        # search_molecule tries exact match first (returns results), so one call
        with patch("cli_anything.cortellis.core.chembl.requests.get",
                   return_value=_mock_response(raw)):
            results = chembl.search_molecule("semaglutide", limit=1)

        self.assertEqual(len(results), 1)
        m = results[0]
        self.assertEqual(m["chembl_id"], "CHEMBL1234")
        self.assertEqual(m["name"], "SEMAGLUTIDE")
        self.assertEqual(m["max_phase"], 4)


# ---------------------------------------------------------------------------
# 3. clinicaltrials
# ---------------------------------------------------------------------------

class TestClinicaltrials(unittest.TestCase):
    def test_count_trials_returns_int(self):
        from cli_anything.cortellis.core import clinicaltrials

        raw = {"totalCount": 42}
        mock_resp = _mock_urllib_response(raw)

        with patch("cli_anything.cortellis.core.clinicaltrials.urllib.request.urlopen",
                   return_value=mock_resp):
            count = clinicaltrials.count_trials("semaglutide")

        self.assertEqual(count, 42)


# ---------------------------------------------------------------------------
# 4. cpic
# ---------------------------------------------------------------------------

class TestCpic(unittest.TestCase):
    def test_search_drug_returns_list(self):
        from cli_anything.cortellis.core import cpic

        raw = [{"drugid": "warfarin", "name": "warfarin", "guidelineid": 1, "rxnormid": "11289"}]

        with patch("cli_anything.cortellis.core.cpic.requests.get",
                   return_value=_mock_response(raw)):
            results = cpic.search_drug("warfarin")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["drugid"], "warfarin")
        self.assertEqual(results[0]["name"], "warfarin")


# ---------------------------------------------------------------------------
# 5. ema
# ---------------------------------------------------------------------------

class TestEma(unittest.TestCase):
    def test_search_medicines_returns_list(self):
        from cli_anything.cortellis.core import ema

        # EMA fetches a JSON report endpoint via urllib; the response may be
        # {"data": [...]} or a plain list.
        raw_record = {
            "name_of_medicine": "Ozempic",
            "active_substance": "semaglutide",
            "medicine_status": "Authorised",
            "therapeutic_area_mesh": "Diabetes Mellitus, Type 2",
            "therapeutic_indication": "Treatment of type 2 diabetes",
            "marketing_authorisation_date": "06/02/2018",
            "orphan_medicine": "No",
            "biosimilar": "No",
            "prime_priority_medicine": "No",
            "ema_product_number": "EMEA/H/C/004174",
            "marketing_authorisation_developer_applicant_holder": "Novo Nordisk A/S",
            "conditional_approval": "No",
            "atc_code_human": "A10BJ06",
            "medicine_url": "https://www.ema.europa.eu/en/medicines/human/EPAR/ozempic",
        }
        mock_resp = _mock_urllib_response({"data": [raw_record]})

        with patch("cli_anything.cortellis.core.ema.urllib.request.urlopen",
                   return_value=mock_resp):
            results = ema.search_medicines(active_substance="semaglutide", limit=5)

        self.assertGreaterEqual(len(results), 1)
        r = results[0]
        self.assertEqual(r["medicine_name"], "Ozempic")
        self.assertIn("semaglutide", r["active_substance"].lower())
        self.assertEqual(r["status"], "Authorised")


# ---------------------------------------------------------------------------
# 6. fda
# ---------------------------------------------------------------------------

class TestFda(unittest.TestCase):
    def test_top_adverse_reactions_returns_list(self):
        from cli_anything.cortellis.core import fda

        raw = {
            "results": [
                {"term": "nausea", "count": 100},
                {"term": "vomiting", "count": 50},
            ]
        }

        with patch("cli_anything.cortellis.core.fda.requests.get",
                   return_value=_mock_response(raw)):
            results = fda.top_adverse_reactions("semaglutide", limit=5)

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["reaction"], "nausea")
        self.assertEqual(results[0]["count"], 100)
        self.assertEqual(results[1]["reaction"], "vomiting")
        self.assertEqual(results[1]["count"], 50)


# ---------------------------------------------------------------------------
# 7. opentargets
# ---------------------------------------------------------------------------

class TestOpentargets(unittest.TestCase):
    def test_search_target_returns_list(self):
        from cli_anything.cortellis.core import opentargets

        raw = {
            "data": {
                "search": {
                    "hits": [
                        {
                            "id": "ENSG00000112164",
                            "entity": "target",
                            "object": {
                                "__typename": "Target",
                                "id": "ENSG00000112164",
                                "approvedSymbol": "GLP1R",
                                "approvedName": "glucagon like peptide 1 receptor",
                                "biotype": "protein_coding",
                            },
                        }
                    ]
                }
            }
        }

        with patch("cli_anything.cortellis.core.opentargets.requests.post",
                   return_value=_mock_response(raw)):
            results = opentargets.search_target("GLP1R")

        self.assertEqual(len(results), 1)
        r = results[0]
        self.assertEqual(r["ensembl_id"], "ENSG00000112164")
        self.assertEqual(r["symbol"], "GLP1R")
        self.assertEqual(r["name"], "glucagon like peptide 1 receptor")


# ---------------------------------------------------------------------------
# 8. pubmed
# ---------------------------------------------------------------------------

class TestPubmed(unittest.TestCase):
    def test_search_and_fetch_returns_list(self):
        from cli_anything.cortellis.core import pubmed

        esearch_payload = {"esearchresult": {"idlist": ["12345678"]}}
        esummary_payload = {
            "result": {
                "uids": ["12345678"],
                "12345678": {
                    "uid": "12345678",
                    "title": "Semaglutide in Type 2 Diabetes",
                    "authors": [{"name": "Smith J"}, {"name": "Doe A"}],
                    "source": "N Engl J Med",
                    "pubdate": "2024 Jan",
                },
            }
        }

        call_count = 0

        def urlopen_side_effect(req, timeout=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _mock_urllib_response(esearch_payload)
            return _mock_urllib_response(esummary_payload)

        with patch("cli_anything.cortellis.core.pubmed.urllib.request.urlopen",
                   side_effect=urlopen_side_effect):
            results = pubmed.search_and_fetch("semaglutide", max_results=3)

        self.assertEqual(len(results), 1)
        r = results[0]
        self.assertEqual(r["title"], "Semaglutide in Type 2 Diabetes")
        self.assertEqual(r["pmid"], "12345678")
        self.assertEqual(r["journal"], "N Engl J Med")
        self.assertIn("Smith J", r["authors_str"])


# ---------------------------------------------------------------------------
# 9. uniprot
# ---------------------------------------------------------------------------

class TestUniprot(unittest.TestCase):
    def test_search_returns_normalized_list(self):
        from cli_anything.cortellis.core import uniprot

        raw = {
            "results": [
                {
                    "primaryAccession": "P43220",
                    "uniProtkbId": "GLP1R_HUMAN",
                    "proteinDescription": {
                        "recommendedName": {
                            "fullName": {"value": "Glucagon-like peptide 1 receptor"}
                        }
                    },
                    "genes": [{"geneName": {"value": "GLP1R"}}],
                    "sequence": {"length": 463, "molWeight": 53026},
                    "comments": [],
                    "features": [],
                    "uniProtKBCrossReferences": [],
                    "keywords": [],
                }
            ]
        }

        with patch("cli_anything.cortellis.core.uniprot.requests.get",
                   return_value=_mock_response(raw)):
            results = uniprot.search("GLP1R", limit=3)

        self.assertEqual(len(results), 1)
        r = results[0]
        self.assertEqual(r["accession"], "P43220")
        self.assertEqual(r["protein_name"], "Glucagon-like peptide 1 receptor")
        self.assertEqual(r["gene_symbol"], "GLP1R")


if __name__ == "__main__":
    unittest.main()
