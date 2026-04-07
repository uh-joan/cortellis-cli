"""Tests for compile_pipeline.py — pipeline wiki compiler."""

import csv
import os
import sys

import pytest

from cli_anything.cortellis.utils.wiki import (
    read_article,
    article_path,
    slugify,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_csv(path, rows):
    if not rows:
        open(path, "w").close()
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


DRUG_ROW = {
    "name": "DrugA",
    "id": "123",
    "phase": "Launched",
    "indication": "Type 2 Diabetes",
    "mechanism": "GLP-1 Agonist",
    "company": "Novo Nordisk",
    "source": "cortellis",
}


def _build_pipeline_dir(tmp_path, company="Novo Nordisk"):
    """Create a minimal pipeline directory for testing."""
    pipeline_dir = os.path.join(str(tmp_path), "raw", slugify(company))
    os.makedirs(pipeline_dir, exist_ok=True)

    _write_csv(os.path.join(pipeline_dir, "launched.csv"), [DRUG_ROW])
    _write_csv(
        os.path.join(pipeline_dir, "phase3.csv"),
        [dict(DRUG_ROW, name="DrugB", id="456", phase="Phase 3")],
    )
    _write_csv(
        os.path.join(pipeline_dir, "phase2.csv"),
        [dict(DRUG_ROW, name="DrugC", id="789", phase="Phase 2")],
    )
    # phase1_merged.csv and preclinical_merged.csv may be empty
    _write_csv(os.path.join(pipeline_dir, "phase1_merged.csv"), [])
    _write_csv(os.path.join(pipeline_dir, "preclinical_merged.csv"), [])
    _write_csv(os.path.join(pipeline_dir, "other.csv"), [])
    _write_csv(os.path.join(pipeline_dir, "deals.csv"), [])
    _write_csv(os.path.join(pipeline_dir, "trials.csv"), [])

    return pipeline_dir


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCompilePipelineCreatesArticle:
    def test_compile_creates_company_article(self, tmp_path, monkeypatch):
        """Running compile_pipeline.main() creates wiki/companies/<slug>.md."""
        pipeline_dir = _build_pipeline_dir(tmp_path, "Novo Nordisk")
        wiki_base = str(tmp_path)

        monkeypatch.setattr(
            sys, "argv",
            ["compile_pipeline.py", pipeline_dir, "Novo Nordisk", "--wiki-dir", wiki_base],
        )

        from cli_anything.cortellis.skills.pipeline.recipes import compile_pipeline
        compile_pipeline.main()

        expected = os.path.join(wiki_base, "wiki", "companies", "novo-nordisk.md")
        assert os.path.exists(expected), f"Expected {expected} to exist"

    def test_article_has_correct_type(self, tmp_path, monkeypatch):
        """Compiled article frontmatter has type: company."""
        pipeline_dir = _build_pipeline_dir(tmp_path)
        wiki_base = str(tmp_path)

        monkeypatch.setattr(
            sys, "argv",
            ["compile_pipeline.py", pipeline_dir, "Novo Nordisk", "--wiki-dir", wiki_base],
        )

        from cli_anything.cortellis.skills.pipeline.recipes import compile_pipeline
        compile_pipeline.main()

        path = os.path.join(wiki_base, "wiki", "companies", "novo-nordisk.md")
        art = read_article(path)
        assert art is not None
        assert art["meta"]["type"] == "company"
        assert art["meta"]["slug"] == "novo-nordisk"
        assert art["meta"]["title"] == "Novo Nordisk"


class TestPipelineDataInFrontmatter:
    def test_pipeline_key_exists(self, tmp_path, monkeypatch):
        """Frontmatter contains a 'pipeline' key."""
        pipeline_dir = _build_pipeline_dir(tmp_path)
        wiki_base = str(tmp_path)

        monkeypatch.setattr(
            sys, "argv",
            ["compile_pipeline.py", pipeline_dir, "Novo Nordisk", "--wiki-dir", wiki_base],
        )

        from cli_anything.cortellis.skills.pipeline.recipes import compile_pipeline
        compile_pipeline.main()

        path = os.path.join(wiki_base, "wiki", "companies", "novo-nordisk.md")
        art = read_article(path)
        assert "pipeline" in art["meta"], "frontmatter should have 'pipeline' key"

    def test_pipeline_phase_counts(self, tmp_path, monkeypatch):
        """pipeline key in frontmatter contains per-phase counts and total."""
        pipeline_dir = _build_pipeline_dir(tmp_path)
        wiki_base = str(tmp_path)

        monkeypatch.setattr(
            sys, "argv",
            ["compile_pipeline.py", pipeline_dir, "Novo Nordisk", "--wiki-dir", wiki_base],
        )

        from cli_anything.cortellis.skills.pipeline.recipes import compile_pipeline
        compile_pipeline.main()

        path = os.path.join(wiki_base, "wiki", "companies", "novo-nordisk.md")
        art = read_article(path)
        pipeline = art["meta"]["pipeline"]

        assert pipeline["launched"] == 1
        assert pipeline["phase3"] == 1
        assert pipeline["phase2"] == 1
        assert pipeline["phase1"] == 0
        assert pipeline["preclinical"] == 0
        assert pipeline["total"] == 3

    def test_pipeline_dir_stored(self, tmp_path, monkeypatch):
        """pipeline key stores the source directory."""
        pipeline_dir = _build_pipeline_dir(tmp_path)
        wiki_base = str(tmp_path)

        monkeypatch.setattr(
            sys, "argv",
            ["compile_pipeline.py", pipeline_dir, "Novo Nordisk", "--wiki-dir", wiki_base],
        )

        from cli_anything.cortellis.skills.pipeline.recipes import compile_pipeline
        compile_pipeline.main()

        path = os.path.join(wiki_base, "wiki", "companies", "novo-nordisk.md")
        art = read_article(path)
        assert art["meta"]["pipeline"]["pipeline_dir"] == pipeline_dir


class TestUpsertExistingArticle:
    def test_upserts_existing_article(self, tmp_path, monkeypatch):
        """Existing company data (e.g. landscape CPI indications) is preserved on upsert."""
        from cli_anything.cortellis.utils.wiki import write_article

        wiki_base = str(tmp_path)
        company_slug = "acme-pharma"

        # Pre-create a company article with landscape data
        existing_meta = {
            "title": "Acme Pharma",
            "type": "company",
            "slug": company_slug,
            "best_cpi": "88.5",
            "indications": {
                "obesity": {
                    "indication": "Obesity",
                    "cpi_tier": "1",
                    "cpi_score": 88.5,
                    "position": "Leader",
                    "pipeline_breadth": 5,
                    "phase_score": 80.0,
                    "mechanism_diversity": 3,
                    "deal_activity": 2,
                    "trial_intensity": 4,
                }
            },
        }
        existing_path = os.path.join(wiki_base, "wiki", "companies", f"{company_slug}.md")
        write_article(existing_path, existing_meta, "## Overview\n\nExisting body.\n")

        # Build pipeline dir
        pipeline_dir = _build_pipeline_dir(tmp_path, "Acme Pharma")
        monkeypatch.setattr(
            sys, "argv",
            ["compile_pipeline.py", pipeline_dir, "Acme Pharma", "--wiki-dir", wiki_base],
        )

        from cli_anything.cortellis.skills.pipeline.recipes import compile_pipeline
        compile_pipeline.main()

        art = read_article(existing_path)
        assert art is not None
        # Pipeline data was added
        assert "pipeline" in art["meta"]
        assert art["meta"]["pipeline"]["total"] == 3
        # Existing landscape data was preserved
        assert "indications" in art["meta"]
        assert art["meta"]["indications"]["obesity"]["cpi_score"] == 88.5
        assert art["meta"]["best_cpi"] == "88.5"

    def test_second_compile_updates_pipeline(self, tmp_path, monkeypatch):
        """Running compile twice updates pipeline counts correctly."""
        pipeline_dir = _build_pipeline_dir(tmp_path)
        wiki_base = str(tmp_path)

        from cli_anything.cortellis.skills.pipeline.recipes import compile_pipeline

        # First compile — 3 drugs total
        monkeypatch.setattr(
            sys, "argv",
            ["compile_pipeline.py", pipeline_dir, "Novo Nordisk", "--wiki-dir", wiki_base],
        )
        compile_pipeline.main()

        # Add a phase 3 drug
        phase3_path = os.path.join(pipeline_dir, "phase3.csv")
        _write_csv(phase3_path, [
            dict(DRUG_ROW, name="DrugB", id="456", phase="Phase 3"),
            dict(DRUG_ROW, name="DrugD", id="999", phase="Phase 3"),
        ])

        # Second compile — 4 drugs total
        monkeypatch.setattr(
            sys, "argv",
            ["compile_pipeline.py", pipeline_dir, "Novo Nordisk", "--wiki-dir", wiki_base],
        )
        compile_pipeline.main()

        path = os.path.join(wiki_base, "wiki", "companies", "novo-nordisk.md")
        art = read_article(path)
        assert art["meta"]["pipeline"]["phase3"] == 2
        assert art["meta"]["pipeline"]["total"] == 4


class TestPipelineUpdatesIndex:
    def test_updates_index(self, tmp_path, monkeypatch):
        """compile_pipeline updates wiki/INDEX.md with the company entry."""
        pipeline_dir = _build_pipeline_dir(tmp_path)
        wiki_base = str(tmp_path)

        monkeypatch.setattr(
            sys, "argv",
            ["compile_pipeline.py", pipeline_dir, "Novo Nordisk", "--wiki-dir", wiki_base],
        )

        from cli_anything.cortellis.skills.pipeline.recipes import compile_pipeline
        compile_pipeline.main()

        index_path = os.path.join(wiki_base, "wiki", "INDEX.md")
        assert os.path.exists(index_path), "wiki/INDEX.md should be created"
        content = open(index_path).read()
        assert "Novo Nordisk" in content

    def test_index_has_companies_section(self, tmp_path, monkeypatch):
        """INDEX.md has a Companies section after compile."""
        pipeline_dir = _build_pipeline_dir(tmp_path)
        wiki_base = str(tmp_path)

        monkeypatch.setattr(
            sys, "argv",
            ["compile_pipeline.py", pipeline_dir, "Novo Nordisk", "--wiki-dir", wiki_base],
        )

        from cli_anything.cortellis.skills.pipeline.recipes import compile_pipeline
        compile_pipeline.main()

        content = open(os.path.join(wiki_base, "wiki", "INDEX.md")).read()
        assert "## Companies" in content


class TestPipelineBodySections:
    def test_body_has_pipeline_overview_section(self, tmp_path, monkeypatch):
        """Article body contains ## Pipeline Overview section."""
        pipeline_dir = _build_pipeline_dir(tmp_path)
        wiki_base = str(tmp_path)

        monkeypatch.setattr(
            sys, "argv",
            ["compile_pipeline.py", pipeline_dir, "Novo Nordisk", "--wiki-dir", wiki_base],
        )

        from cli_anything.cortellis.skills.pipeline.recipes import compile_pipeline
        compile_pipeline.main()

        path = os.path.join(wiki_base, "wiki", "companies", "novo-nordisk.md")
        art = read_article(path)
        assert "## Pipeline Overview" in art["body"]

    def test_body_has_drugs_by_phase_section(self, tmp_path, monkeypatch):
        """Article body contains ## Pipeline Drugs by Phase section."""
        pipeline_dir = _build_pipeline_dir(tmp_path)
        wiki_base = str(tmp_path)

        monkeypatch.setattr(
            sys, "argv",
            ["compile_pipeline.py", pipeline_dir, "Novo Nordisk", "--wiki-dir", wiki_base],
        )

        from cli_anything.cortellis.skills.pipeline.recipes import compile_pipeline
        compile_pipeline.main()

        path = os.path.join(wiki_base, "wiki", "companies", "novo-nordisk.md")
        art = read_article(path)
        assert "## Pipeline Drugs by Phase" in art["body"]

    def test_body_lists_drugs(self, tmp_path, monkeypatch):
        """Article body lists drug names from CSVs."""
        pipeline_dir = _build_pipeline_dir(tmp_path)
        wiki_base = str(tmp_path)

        monkeypatch.setattr(
            sys, "argv",
            ["compile_pipeline.py", pipeline_dir, "Novo Nordisk", "--wiki-dir", wiki_base],
        )

        from cli_anything.cortellis.skills.pipeline.recipes import compile_pipeline
        compile_pipeline.main()

        path = os.path.join(wiki_base, "wiki", "companies", "novo-nordisk.md")
        art = read_article(path)
        assert "DrugA" in art["body"]
        assert "DrugB" in art["body"]
        assert "DrugC" in art["body"]
