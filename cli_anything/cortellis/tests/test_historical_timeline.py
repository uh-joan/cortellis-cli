"""Tests for the historical pipeline timeline recipe."""

import csv
import json
import os
import sys
from datetime import datetime, timezone

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

from cli_anything.cortellis.skills.landscape.recipes.enrich_historical_timeline import (
    get_top_drug_ids,
    extract_phase_transitions,
    reconstruct_monthly_snapshots,
    write_phase_timeline_csv,
    write_historical_snapshots_csv,
    generate_historical_report,
    PHASE_LABELS,
)


def _write_csv(path, header, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        for row in rows:
            w.writerow(row)


class TestGetTopDrugIds:
    def test_reads_launched_and_phase3(self, tmp_path):
        d = tmp_path / "landscape"
        d.mkdir()
        header = ["name", "id", "phase", "indication", "mechanism", "company", "source"]
        _write_csv(str(d / "launched.csv"), header, [
            ["DrugA", "101", "Launched", "Obesity", "MechX", "CoA", "src"],
            ["DrugB", "102", "Launched", "Obesity", "MechY", "CoB", "src"],
        ])
        _write_csv(str(d / "phase3.csv"), header, [
            ["DrugC", "103", "Phase 3", "Obesity", "MechX", "CoC", "src"],
        ])
        _write_csv(str(d / "phase2.csv"), header, [
            ["DrugD", "104", "Phase 2", "Obesity", "MechZ", "CoD", "src"],
        ])
        result = get_top_drug_ids(str(d), max_drugs=10)
        ids = [did for did, _ in result]
        assert "101" in ids
        assert "102" in ids
        assert "103" in ids
        assert "104" in ids

    def test_caps_at_max_drugs(self, tmp_path):
        d = tmp_path / "landscape"
        d.mkdir()
        header = ["name", "id", "phase", "indication", "mechanism", "company", "source"]
        rows = [[f"Drug{i}", str(i), "Launched", "Obesity", "Mech", "Co", "src"] for i in range(20)]
        _write_csv(str(d / "launched.csv"), header, rows)
        result = get_top_drug_ids(str(d), max_drugs=5)
        assert len(result) == 5

    def test_deduplicates(self, tmp_path):
        d = tmp_path / "landscape"
        d.mkdir()
        header = ["name", "id", "phase", "indication", "mechanism", "company", "source"]
        _write_csv(str(d / "launched.csv"), header, [["DrugA", "101", "L", "Ob", "M", "C", "s"]])
        _write_csv(str(d / "phase3.csv"), header, [["DrugA", "101", "P3", "Ob", "M", "C", "s"]])
        result = get_top_drug_ids(str(d), max_drugs=10)
        assert len(result) == 1

    def test_empty_dir(self, tmp_path):
        d = tmp_path / "landscape"
        d.mkdir()
        result = get_top_drug_ids(str(d))
        assert result == []


class TestExtractPhaseTransitions:
    def _make_histories(self):
        return {
            "101": {
                "name": "DrugA",
                "changes": [
                    {
                        "@type": "updated",
                        "Date": "2024-06-15T00:00:00Z",
                        "Reason": {"@id": "10", "$": "Highest status change"},
                        "FieldsChanged": {"Field": {
                            "@newValue": "Phase 2 Clinical",
                            "@newId": "C2",
                            "@oldValue": "Phase 1 Clinical",
                            "@oldId": "C1",
                            "@name": "drugPhaseHighest",
                        }},
                    },
                    {
                        "@type": "updated",
                        "Date": "2025-03-01T00:00:00Z",
                        "Reason": {"@id": "10", "$": "Highest status change"},
                        "FieldsChanged": {"Field": {
                            "@newValue": "Phase 3 Clinical",
                            "@oldValue": "Phase 2 Clinical",
                            "@name": "drugPhaseHighest",
                        }},
                    },
                    {
                        "@type": "updated",
                        "Date": "2025-01-01T00:00:00Z",
                        "Reason": {"@id": "5", "$": "Source updates"},
                        "FieldsChanged": {"Field": {"@name": "summary"}},
                    },
                ],
            },
        }

    def test_extracts_phase_changes_only(self):
        histories = self._make_histories()
        transitions = extract_phase_transitions(histories)
        # Should get 2 phase transitions (reason 10), not the source update (reason 5)
        assert len(transitions) == 2

    def test_extracts_correct_fields(self):
        histories = self._make_histories()
        transitions = extract_phase_transitions(histories)
        t = transitions[0]
        assert t["drug_id"] == "101"
        assert t["drug_name"] == "DrugA"
        assert t["phase_from"] == "Phase 1 Clinical"
        assert t["phase_to"] == "Phase 2 Clinical"
        assert t["date"] == "2024-06-15"

    def test_sorted_by_date(self):
        histories = self._make_histories()
        transitions = extract_phase_transitions(histories)
        dates = [t["date"] for t in transitions]
        assert dates == sorted(dates)

    def test_empty_histories(self):
        assert extract_phase_transitions({}) == []

    def test_handles_trio_status_change(self):
        histories = {
            "200": {
                "name": "DrugB",
                "changes": [{
                    "@type": "UPDATED",
                    "Date": "2025-06-01T00:00:00Z",
                    "Reason": {"@id": "26", "$": "Development status: trio change"},
                    "FieldsChanged": {"Field": [
                        {"@newValue": "Phase 3 Clinical", "@oldValue": "Phase 2 Clinical", "@name": "developmentStatus"},
                        {"@value": "Novo Nordisk", "@id": "18614", "@name": "company"},
                        {"@value": "Obesity", "@name": "indication"},
                    ]},
                }],
            },
        }
        transitions = extract_phase_transitions(histories)
        assert len(transitions) == 1
        assert transitions[0]["phase_to"] == "Phase 3 Clinical"
        assert transitions[0]["company"] == "Novo Nordisk"
        assert transitions[0]["indication"] == "Obesity"


class TestReconstructMonthlySnapshots:
    def test_basic_reconstruction(self):
        transitions = [
            {"drug_id": "101", "date": "2024-01-15", "phase_to": "Phase 1 Clinical"},
            {"drug_id": "101", "date": "2025-06-15", "phase_to": "Phase 2 Clinical"},
            {"drug_id": "102", "date": "2024-03-01", "phase_to": "Phase 3 Clinical"},
        ]
        drug_ids = [("101", "DrugA"), ("102", "DrugB")]
        snapshots = reconstruct_monthly_snapshots(transitions, drug_ids, months=12)
        assert len(snapshots) == 13  # 12 months + current
        # Last snapshot should have drug 101 in phase2, drug 102 in phase3
        last = snapshots[-1]
        assert last["total"] >= 1

    def test_empty_transitions(self):
        snapshots = reconstruct_monthly_snapshots([], [("101", "D")], months=6)
        assert len(snapshots) == 7
        assert all(s["total"] == 0 for s in snapshots)


class TestWriteCSVs:
    def test_write_phase_timeline(self, tmp_path):
        transitions = [
            {"drug_id": "101", "drug_name": "A", "date": "2024-01-01",
             "phase_from": "P1", "phase_to": "P2", "indication": "Ob",
             "company": "Co", "country": "US"},
        ]
        path = str(tmp_path / "timeline.csv")
        write_phase_timeline_csv(transitions, path)
        assert os.path.exists(path)
        rows = list(csv.DictReader(open(path)))
        assert len(rows) == 1
        assert rows[0]["drug_name"] == "A"

    def test_write_historical_snapshots(self, tmp_path):
        snapshots = [
            {"date": "2024-01-01", "launched": 5, "phase3": 10, "phase2": 20,
             "phase1": 30, "discovery": 15, "total": 80, "drugs_tracked": 80},
        ]
        path = str(tmp_path / "snapshots.csv")
        write_historical_snapshots_csv(snapshots, path)
        assert os.path.exists(path)
        rows = list(csv.DictReader(open(path)))
        assert rows[0]["launched"] == "5"


class TestGenerateReport:
    def test_has_sections(self):
        transitions = [
            {"drug_id": "101", "drug_name": "DrugA", "date": "2025-03-01",
             "phase_from": "Phase 2 Clinical", "phase_to": "Phase 3 Clinical",
             "indication": "Obesity", "company": "Novo", "country": "US"},
        ]
        snapshots = [
            {"date": "2025-01-01", "launched": 5, "phase3": 10, "phase2": 20,
             "phase1": 30, "discovery": 15, "total": 80, "drugs_tracked": 80},
            {"date": "2026-01-01", "launched": 7, "phase3": 12, "phase2": 22,
             "phase1": 32, "discovery": 17, "total": 90, "drugs_tracked": 90},
        ]
        report = generate_historical_report(transitions, snapshots, "Obesity")
        assert "Historical Pipeline Timeline" in report
        assert "Pipeline Evolution" in report
        assert "Growth Summary" in report
        assert "Phase 3 Entries" in report
        assert "DrugA" in report

    def test_empty_transitions(self):
        report = generate_historical_report([], [{"date": "2025-01-01", "launched": 0, "phase3": 0,
            "phase2": 0, "phase1": 0, "discovery": 0, "total": 0, "drugs_tracked": 0}], "Test")
        assert "Historical Pipeline Timeline" in report
