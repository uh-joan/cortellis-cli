"""Tests for the wiki knowledge compilation infrastructure."""

import csv
import json
import os
import sys
from datetime import datetime, timezone, timedelta

import pytest

from cli_anything.cortellis.utils.wiki import (
    slugify,
    wiki_root,
    article_path,
    read_article,
    write_article,
    update_index,
    load_index_entries,
    list_articles,
    check_freshness,
    wikilink,
    diff_snapshots,
    log_activity,
)


class TestSlugify:
    def test_simple_name(self):
        assert slugify("Novo Nordisk") == "novo-nordisk"

    def test_apostrophe(self):
        assert slugify("Alzheimer's Disease") == "alzheimers-disease"

    def test_preserves_hyphens(self):
        assert slugify("GLP-1 Receptor") == "glp-1-receptor"

    def test_special_chars(self):
        assert slugify("Merck & Co., Inc.") == "merck-co-inc"

    def test_multiple_spaces(self):
        assert slugify("  Eli   Lilly  ") == "eli-lilly"

    def test_already_slug(self):
        assert slugify("obesity") == "obesity"

    def test_unicode_apostrophe(self):
        assert slugify("Parkinson\u2019s") == "parkinsons"


class TestWikiRoot:
    def test_creates_directory(self, tmp_path):
        root = wiki_root(str(tmp_path))
        assert os.path.isdir(root)
        assert root == os.path.join(str(tmp_path), "wiki")

    def test_idempotent(self, tmp_path):
        root1 = wiki_root(str(tmp_path))
        root2 = wiki_root(str(tmp_path))
        assert root1 == root2


class TestArticlePath:
    def test_indication(self, tmp_path):
        p = article_path("indications", "obesity", str(tmp_path))
        assert p.endswith("wiki/indications/obesity.md")

    def test_company(self, tmp_path):
        p = article_path("companies", "novo-nordisk", str(tmp_path))
        assert p.endswith("wiki/companies/novo-nordisk.md")


class TestReadWriteArticle:
    def test_round_trip(self, tmp_path):
        path = os.path.join(str(tmp_path), "test.md")
        meta = {"title": "Obesity", "type": "indication", "total_drugs": 478}
        body = "## Executive Summary\n\nObesity landscape overview.\n"

        write_article(path, meta, body)
        result = read_article(path)

        assert result is not None
        assert result["meta"]["title"] == "Obesity"
        assert result["meta"]["total_drugs"] == 478
        assert "Executive Summary" in result["body"]

    def test_read_missing_file(self):
        assert read_article("/nonexistent/path.md") is None

    def test_read_no_frontmatter(self, tmp_path):
        path = os.path.join(str(tmp_path), "plain.md")
        with open(path, "w") as f:
            f.write("# Just markdown\n\nNo frontmatter here.\n")
        result = read_article(path)
        assert result is not None
        assert result["meta"] == {}
        assert "Just markdown" in result["body"]

    def test_creates_parent_dirs(self, tmp_path):
        path = os.path.join(str(tmp_path), "deep", "nested", "article.md")
        write_article(path, {"title": "Test"}, "Body")
        assert os.path.exists(path)

    def test_preserves_unicode(self, tmp_path):
        path = os.path.join(str(tmp_path), "unicode.md")
        meta = {"title": "Sj\u00f6gren's Syndrome"}
        write_article(path, meta, "Body with \u00e9\u00e8\u00ea")
        result = read_article(path)
        assert result["meta"]["title"] == "Sj\u00f6gren's Syndrome"


class TestUpdateIndex:
    def test_creates_index(self, tmp_path):
        wiki_dir = os.path.join(str(tmp_path), "wiki")
        os.makedirs(wiki_dir)
        entries = [
            {
                "type": "indications",
                "slug": "obesity",
                "title": "Obesity",
                "total_drugs": 478,
                "top_company": "Novo Nordisk (95.0)",
                "compiled_at": "2026-04-07T18:30:00Z",
                "freshness": "ok",
            },
        ]
        update_index(wiki_dir, entries)
        idx_path = os.path.join(wiki_dir, "INDEX.md")
        assert os.path.exists(idx_path)
        content = open(idx_path).read()
        assert "Obesity" in content
        assert "478" in content
        assert "Novo Nordisk" in content

    def test_multiple_types(self, tmp_path):
        wiki_dir = os.path.join(str(tmp_path), "wiki")
        os.makedirs(wiki_dir)
        entries = [
            {
                "type": "indications",
                "slug": "obesity",
                "title": "Obesity",
                "compiled_at": "2026-04-07",
            },
            {
                "type": "companies",
                "slug": "novo-nordisk",
                "title": "Novo Nordisk",
                "summary": "obesity",
                "best_cpi": "95.0",
                "compiled_at": "2026-04-07",
            },
        ]
        update_index(wiki_dir, entries)
        content = open(os.path.join(wiki_dir, "INDEX.md")).read()
        assert "## Indications" in content
        assert "## Companies" in content


class TestLoadIndexEntries:
    def test_scans_articles(self, tmp_path):
        wiki_dir = os.path.join(str(tmp_path), "wiki")
        ind_dir = os.path.join(wiki_dir, "indications")
        os.makedirs(ind_dir)
        write_article(
            os.path.join(ind_dir, "obesity.md"),
            {"title": "Obesity", "slug": "obesity", "compiled_at": "2026-04-07", "total_drugs": 478},
            "Body",
        )
        entries = load_index_entries(wiki_dir)
        assert len(entries) == 1
        assert entries[0]["title"] == "Obesity"
        assert entries[0]["total_drugs"] == 478


class TestCheckFreshness:
    def _write_indication(self, base_dir, slug, compiled_at, freshness_level="ok", source_dir=None):
        """Helper to create a test indication article."""
        path = article_path("indications", slug, base_dir)
        meta = {
            "title": slug.title(),
            "slug": slug,
            "compiled_at": compiled_at,
            "freshness_level": freshness_level,
        }
        if source_dir:
            meta["source_dir"] = source_dir
        write_article(path, meta, "Test body")

    def test_missing_article(self, tmp_path):
        assert check_freshness("nonexistent", base_dir=str(tmp_path)) == "missing"

    def test_fresh_article(self, tmp_path):
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        self._write_indication(str(tmp_path), "obesity", now)
        assert check_freshness("obesity", base_dir=str(tmp_path)) == "fresh"

    def test_stale_article(self, tmp_path):
        old = (datetime.now(timezone.utc) - timedelta(days=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
        self._write_indication(str(tmp_path), "obesity", old)
        assert check_freshness("obesity", max_age_days=7, base_dir=str(tmp_path)) == "stale"

    def test_hard_freshness_overrides(self, tmp_path):
        """Even a recently compiled article is stale if source data is hard-stale."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        source_dir = "raw/obesity"
        self._write_indication(str(tmp_path), "obesity", now, source_dir=source_dir)

        # Create a hard-stale freshness.json
        raw_dir = os.path.join(str(tmp_path), source_dir)
        os.makedirs(raw_dir, exist_ok=True)
        with open(os.path.join(raw_dir, "freshness.json"), "w") as f:
            json.dump({"staleness_level": "hard"}, f)

        assert check_freshness("obesity", base_dir=str(tmp_path)) == "stale"

    def test_no_compiled_at(self, tmp_path):
        path = article_path("indications", "obesity", str(tmp_path))
        write_article(path, {"title": "Obesity", "slug": "obesity"}, "No date")
        assert check_freshness("obesity", base_dir=str(tmp_path)) == "stale"


class TestWikilink:
    def test_with_display(self):
        assert wikilink("novo-nordisk", "Novo Nordisk") == r"[[novo-nordisk\|Novo Nordisk]]"

    def test_without_display(self):
        assert wikilink("obesity") == "[[obesity]]"

    def test_same_slug_and_display(self):
        assert wikilink("obesity", "obesity") == "[[obesity]]"


class TestListArticles:
    def test_returns_all_types(self, tmp_path):
        wiki_dir = os.path.join(str(tmp_path), "wiki")
        ind_dir = os.path.join(wiki_dir, "indications")
        co_dir = os.path.join(wiki_dir, "companies")
        os.makedirs(ind_dir)
        os.makedirs(co_dir)
        write_article(
            os.path.join(ind_dir, "obesity.md"),
            {"title": "Obesity", "slug": "obesity", "type": "indication"},
            "Body",
        )
        write_article(
            os.path.join(co_dir, "novo-nordisk.md"),
            {"title": "Novo Nordisk", "slug": "novo-nordisk", "type": "company"},
            "Body",
        )
        results = list_articles(wiki_dir)
        assert len(results) == 2
        paths = [r["path"] for r in results]
        assert any("obesity.md" in p for p in paths)
        assert any("novo-nordisk.md" in p for p in paths)

    def test_filter_by_type(self, tmp_path):
        wiki_dir = os.path.join(str(tmp_path), "wiki")
        ind_dir = os.path.join(wiki_dir, "indications")
        co_dir = os.path.join(wiki_dir, "companies")
        os.makedirs(ind_dir)
        os.makedirs(co_dir)
        write_article(
            os.path.join(ind_dir, "obesity.md"),
            {"title": "Obesity", "slug": "obesity"},
            "Body",
        )
        write_article(
            os.path.join(co_dir, "novo-nordisk.md"),
            {"title": "Novo Nordisk", "slug": "novo-nordisk"},
            "Body",
        )
        results = list_articles(wiki_dir, article_type="indications")
        assert len(results) == 1
        assert "obesity.md" in results[0]["path"]

    def test_returns_meta(self, tmp_path):
        wiki_dir = os.path.join(str(tmp_path), "wiki")
        ind_dir = os.path.join(wiki_dir, "indications")
        os.makedirs(ind_dir)
        write_article(
            os.path.join(ind_dir, "obesity.md"),
            {"title": "Obesity", "slug": "obesity", "total_drugs": 478},
            "Body",
        )
        results = list_articles(wiki_dir, article_type="indications")
        assert results[0]["meta"]["title"] == "Obesity"
        assert results[0]["meta"]["total_drugs"] == 478

    def test_empty_dir(self, tmp_path):
        wiki_dir = os.path.join(str(tmp_path), "wiki")
        os.makedirs(wiki_dir)
        assert list_articles(wiki_dir) == []

    def test_missing_type_dir(self, tmp_path):
        wiki_dir = os.path.join(str(tmp_path), "wiki")
        os.makedirs(wiki_dir)
        # Only indications dir exists
        ind_dir = os.path.join(wiki_dir, "indications")
        os.makedirs(ind_dir)
        write_article(
            os.path.join(ind_dir, "obesity.md"),
            {"title": "Obesity", "slug": "obesity"},
            "Body",
        )
        # companies/drugs dirs don't exist — should not raise
        results = list_articles(wiki_dir)
        assert len(results) == 1


class TestDiffSnapshots:
    def test_basic_diff(self):
        current = {
            "title": "Obesity", "compiled_at": "2026-04-07T18:00:00Z",
            "total_drugs": 772, "total_deals": 200,
            "phase_counts": {"launched": 15, "phase3": 51, "phase2": 113, "phase1": 155, "discovery": 106, "other": 332},
            "company_rankings": [
                {"company": "Novo Nordisk", "cpi_score": 95.0, "tier": "A"},
                {"company": "Eli Lilly", "cpi_score": 70.6, "tier": "A"},
                {"company": "NewCo", "cpi_score": 30.0, "tier": "B"},
            ],
        }
        previous = {
            "compiled_at": "2026-04-01T12:00:00Z",
            "total_drugs": 750, "total_deals": 185,
            "phase_counts": {"launched": 14, "phase3": 48, "phase2": 110, "phase1": 150, "discovery": 100, "other": 328},
            "company_rankings": [
                {"company": "Novo Nordisk", "cpi_score": 93.0, "tier": "A"},
                {"company": "Eli Lilly", "cpi_score": 68.0, "tier": "A"},
                {"company": "OldCo", "cpi_score": 28.0, "tier": "B"},
            ],
        }
        diff = diff_snapshots(current, previous)
        assert diff["drug_changes"]["total"]["delta"] == 22
        assert diff["deal_changes"]["delta"] == 15
        assert diff["drug_changes"]["by_phase"]["launched"]["delta"] == 1
        assert "NewCo" in diff["company_changes"]["new_in_top10"]
        assert "OldCo" in diff["company_changes"]["dropped_from_top10"]

    def test_no_phase_counts(self):
        current = {"title": "Test", "compiled_at": "2026-04-07", "total_drugs": 100, "total_deals": 50}
        previous = {"compiled_at": "2026-04-01", "total_drugs": 90, "total_deals": 45}
        diff = diff_snapshots(current, previous)
        assert diff["drug_changes"]["total"]["delta"] == 10
        assert diff["drug_changes"]["by_phase"] == {}

    def test_missing_previous_fields(self):
        current = {"title": "Test", "compiled_at": "2026-04-07", "total_drugs": 100}
        previous = {"compiled_at": "2026-04-01"}
        diff = diff_snapshots(current, previous)
        assert diff["drug_changes"]["total"]["before"] == 0
        assert diff["drug_changes"]["total"]["after"] == 100


def _write_csv(path, rows):
    """Helper: write a list-of-dicts to a CSV file."""
    if not rows:
        open(path, "w").close()
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


class TestLogActivity:
    def test_creates_log_file(self, tmp_path):
        wiki_dir = str(tmp_path / "wiki")
        os.makedirs(wiki_dir)
        log_activity(wiki_dir, "compile", "Test: Obesity landscape")
        log_path = os.path.join(wiki_dir, "log.md")
        assert os.path.exists(log_path)
        content = open(log_path).read()
        assert "Wiki Activity Log" in content
        assert "compile | Test: Obesity landscape" in content

    def test_appends_multiple(self, tmp_path):
        wiki_dir = str(tmp_path / "wiki")
        os.makedirs(wiki_dir)
        log_activity(wiki_dir, "compile", "Entry 1")
        log_activity(wiki_dir, "query", "Entry 2")
        content = open(os.path.join(wiki_dir, "log.md")).read()
        assert "compile | Entry 1" in content
        assert "query | Entry 2" in content


class TestCompileDossierIntegration:
    """Integration tests for compile_dossier.main() end-to-end."""

    def _build_landscape(self, tmp_path):
        """Create a minimal raw/test-indication/ directory and return its path."""
        landscape_dir = os.path.join(str(tmp_path), "raw", "test-indication")
        os.makedirs(landscape_dir, exist_ok=True)

        # strategic_scores.csv — 3 companies
        _write_csv(
            os.path.join(landscape_dir, "strategic_scores.csv"),
            [
                {
                    "company": "Alpha Pharma",
                    "cpi_tier": "1",
                    "cpi_score": "92.5",
                    "pipeline_breadth": "5",
                    "phase_score": "80",
                    "mechanism_diversity": "3",
                    "deal_activity": "2",
                    "trial_intensity": "4",
                    "position": "Leader",
                },
                {
                    "company": "Beta Bio",
                    "cpi_tier": "2",
                    "cpi_score": "75.0",
                    "pipeline_breadth": "3",
                    "phase_score": "60",
                    "mechanism_diversity": "2",
                    "deal_activity": "1",
                    "trial_intensity": "2",
                    "position": "Challenger",
                },
                {
                    "company": "Gamma Therapeutics",
                    "cpi_tier": "3",
                    "cpi_score": "50.0",
                    "pipeline_breadth": "1",
                    "phase_score": "40",
                    "mechanism_diversity": "1",
                    "deal_activity": "0",
                    "trial_intensity": "1",
                    "position": "Niche",
                },
            ],
        )

        # mechanism_scores.csv — 2 rows
        _write_csv(
            os.path.join(landscape_dir, "mechanism_scores.csv"),
            [
                {
                    "mechanism": "GLP-1 Agonist",
                    "active_count": "10",
                    "launched": "3",
                    "phase3": "2",
                    "phase2": "3",
                    "phase1": "2",
                    "discovery": "0",
                    "company_count": "8",
                    "crowding_index": "75",
                },
                {
                    "mechanism": "SGLT-2 Inhibitor",
                    "active_count": "5",
                    "launched": "2",
                    "phase3": "1",
                    "phase2": "1",
                    "phase1": "1",
                    "discovery": "0",
                    "company_count": "4",
                    "crowding_index": "40",
                },
            ],
        )

        # opportunity_matrix.csv — 2 rows
        _write_csv(
            os.path.join(landscape_dir, "opportunity_matrix.csv"),
            [
                {
                    "mechanism": "Novel Target",
                    "status": "White Space",
                    "total": "1",
                    "companies": "1",
                    "opportunity_score": "0.8500",
                },
                {
                    "mechanism": "GLP-1 Agonist",
                    "status": "Crowded Pipeline",
                    "total": "10",
                    "companies": "8",
                    "opportunity_score": "0.1200",
                },
            ],
        )

        # freshness.json
        with open(os.path.join(landscape_dir, "freshness.json"), "w") as f:
            json.dump({"staleness_level": "ok", "computed_at_utc": "2026-04-07T00:00:00Z"}, f)

        # deals.csv — empty (just needs to exist)
        open(os.path.join(landscape_dir, "deals.csv"), "w").close()

        # launched.csv — 1 row
        _write_csv(
            os.path.join(landscape_dir, "launched.csv"),
            [
                {
                    "name": "DrugA",
                    "id": "123",
                    "phase": "Launched",
                    "indication": "Test Indication",
                    "mechanism": "GLP-1 Agonist",
                    "company": "Alpha Pharma",
                    "source": "cortellis",
                }
            ],
        )

        # phase3.csv — 1 row
        _write_csv(
            os.path.join(landscape_dir, "phase3.csv"),
            [
                {
                    "name": "DrugB",
                    "id": "456",
                    "phase": "Phase 3",
                    "indication": "Test Indication",
                    "mechanism": "SGLT-2 Inhibitor",
                    "company": "Beta Bio",
                    "source": "cortellis",
                }
            ],
        )

        return landscape_dir

    def test_compiles_indication_article(self, tmp_path, monkeypatch):
        landscape_dir = self._build_landscape(tmp_path)
        wiki_base = str(tmp_path)

        monkeypatch.setattr(
            sys, "argv",
            [
                "compile_dossier.py",
                landscape_dir,
                "Test Indication",
                "--wiki-dir",
                wiki_base,
            ],
        )

        from cli_anything.cortellis.skills.landscape.recipes import compile_dossier
        compile_dossier.main()

        # Indication article exists
        ind_path = os.path.join(wiki_base, "wiki", "indications", "test-indication.md")
        assert os.path.exists(ind_path), f"Expected {ind_path} to exist"

        art = read_article(ind_path)
        assert art is not None
        assert art["meta"]["title"] == "Test Indication"
        assert art["meta"]["type"] == "indication"
        assert art["meta"]["slug"] == "test-indication"

        # Required sections in body
        body = art["body"]
        assert "## Executive Summary" in body
        assert "## Competitive Landscape" in body
        assert "## Mechanism Analysis" in body

    def test_compiles_company_articles(self, tmp_path, monkeypatch):
        landscape_dir = self._build_landscape(tmp_path)
        wiki_base = str(tmp_path)

        monkeypatch.setattr(
            sys, "argv",
            [
                "compile_dossier.py",
                landscape_dir,
                "Test Indication",
                "--wiki-dir",
                wiki_base,
            ],
        )

        from cli_anything.cortellis.skills.landscape.recipes import compile_dossier
        compile_dossier.main()

        companies_dir = os.path.join(wiki_base, "wiki", "companies")
        assert os.path.isdir(companies_dir), "wiki/companies/ should exist"

        # All 3 companies in strategic_scores should have articles
        for company_slug in ("alpha-pharma", "beta-bio", "gamma-therapeutics"):
            p = os.path.join(companies_dir, f"{company_slug}.md")
            assert os.path.exists(p), f"Expected company article: {p}"

    def test_compiles_index(self, tmp_path, monkeypatch):
        landscape_dir = self._build_landscape(tmp_path)
        wiki_base = str(tmp_path)

        monkeypatch.setattr(
            sys, "argv",
            [
                "compile_dossier.py",
                landscape_dir,
                "Test Indication",
                "--wiki-dir",
                wiki_base,
            ],
        )

        from cli_anything.cortellis.skills.landscape.recipes import compile_dossier
        compile_dossier.main()

        index_path = os.path.join(wiki_base, "wiki", "INDEX.md")
        assert os.path.exists(index_path), "wiki/INDEX.md should exist"
        content = open(index_path).read()
        assert "Test Indication" in content


class TestDiffLandscapeIntegration:
    def _build_raw_dir(self, tmp_path, slug="test-ind", extra_drug=False):
        """Create a minimal raw/<slug>/ directory and return its path."""
        raw_dir = tmp_path / "raw" / slug
        raw_dir.mkdir(parents=True, exist_ok=True)

        strategic_rows = [
            {
                "company": "Alpha Pharma",
                "cpi_tier": "1",
                "cpi_score": "92.5",
                "pipeline_breadth": "5",
                "phase_score": "80",
                "mechanism_diversity": "3",
                "deal_activity": "2",
                "trial_intensity": "4",
                "position": "Leader",
            },
        ]
        if extra_drug:
            strategic_rows.append(
                {
                    "company": "Beta Bio",
                    "cpi_tier": "2",
                    "cpi_score": "70.0",
                    "pipeline_breadth": "3",
                    "phase_score": "60",
                    "mechanism_diversity": "2",
                    "deal_activity": "1",
                    "trial_intensity": "2",
                    "position": "Challenger",
                }
            )

        _write_csv(
            str(raw_dir / "strategic_scores.csv"),
            strategic_rows,
        )
        _write_csv(
            str(raw_dir / "mechanism_scores.csv"),
            [
                {
                    "mechanism": "GLP-1 Agonist",
                    "active_count": "10" if not extra_drug else "15",
                    "launched": "3",
                    "phase3": "2",
                    "phase2": "3",
                    "phase1": "2",
                    "discovery": "0",
                    "company_count": "8",
                    "crowding_index": "75",
                },
            ],
        )
        _write_csv(
            str(raw_dir / "opportunity_matrix.csv"),
            [
                {
                    "mechanism": "GLP-1 Agonist",
                    "status": "Crowded Pipeline",
                    "total": "10",
                    "companies": "8",
                    "opportunity_score": "0.1200",
                },
            ],
        )
        with open(str(raw_dir / "freshness.json"), "w") as f:
            json.dump({"staleness_level": "ok", "computed_at_utc": "2026-04-07T00:00:00Z"}, f)

        open(str(raw_dir / "deals.csv"), "w").close()

        _write_csv(
            str(raw_dir / "launched.csv"),
            [
                {
                    "name": "DrugA",
                    "id": "123",
                    "phase": "Launched",
                    "indication": "Test Ind",
                    "mechanism": "GLP-1 Agonist",
                    "company": "Alpha Pharma",
                    "source": "cortellis",
                }
            ],
        )
        if extra_drug:
            _write_csv(
                str(raw_dir / "phase3.csv"),
                [
                    {
                        "name": "DrugB",
                        "id": "456",
                        "phase": "Phase 3",
                        "indication": "Test Ind",
                        "mechanism": "GLP-1 Agonist",
                        "company": "Beta Bio",
                        "source": "cortellis",
                    }
                ],
            )

        return str(raw_dir)

    def test_diff_with_previous_snapshot(self, tmp_path, monkeypatch, capsys):
        """Compile twice with different data, verify diff shows deltas."""
        from cli_anything.cortellis.skills.landscape.recipes.compile_dossier import main as compile_main
        from cli_anything.cortellis.skills.landscape.recipes.diff_landscape import main as diff_main

        wiki_base = str(tmp_path)

        # 1. First compile — minimal data
        raw_dir = self._build_raw_dir(tmp_path, slug="test-ind", extra_drug=False)
        monkeypatch.setattr(
            sys, "argv",
            ["compile_dossier.py", raw_dir, "Test Ind", "--wiki-dir", wiki_base],
        )
        compile_main()

        # 2. Second compile — more data (triggers previous_snapshot capture)
        raw_dir2 = self._build_raw_dir(tmp_path, slug="test-ind", extra_drug=True)
        monkeypatch.setattr(
            sys, "argv",
            ["compile_dossier.py", raw_dir2, "Test Ind", "--wiki-dir", wiki_base],
        )
        compile_main()

        # 3. Run diff
        capsys.readouterr()  # clear compile output
        monkeypatch.setattr(
            sys, "argv",
            ["diff_landscape.py", "test-ind", "--wiki-dir", wiki_base],
        )
        diff_main()

        output = capsys.readouterr().out
        assert "Landscape Changes" in output
        assert "Drug Pipeline" in output

    def test_diff_no_previous_snapshot(self, tmp_path, monkeypatch, capsys):
        """First compile has no previous snapshot — diff should say so."""
        from cli_anything.cortellis.skills.landscape.recipes.compile_dossier import main as compile_main
        from cli_anything.cortellis.skills.landscape.recipes.diff_landscape import main as diff_main

        wiki_base = str(tmp_path)
        raw_dir = self._build_raw_dir(tmp_path, slug="test-ind", extra_drug=False)

        monkeypatch.setattr(
            sys, "argv",
            ["compile_dossier.py", raw_dir, "Test Ind", "--wiki-dir", wiki_base],
        )
        compile_main()

        capsys.readouterr()  # clear compile output
        monkeypatch.setattr(
            sys, "argv",
            ["diff_landscape.py", "test-ind", "--wiki-dir", wiki_base],
        )
        with pytest.raises(SystemExit) as exc_info:
            diff_main()
        assert exc_info.value.code == 0

        output = capsys.readouterr().out
        assert "No previous snapshot" in output


class TestPortfolioReport:
    def test_multiple_indications(self, tmp_path, monkeypatch, capsys):
        """Create 3 indication articles, verify comparison table has all 3."""
        wiki_dir = tmp_path / "wiki" / "indications"
        wiki_dir.mkdir(parents=True)

        for name, drugs, top in [
            ("Obesity", 772, "Novo Nordisk (95.0)"),
            ("Asthma", 563, "GSK (89.3)"),
            ("ALS", 372, "Ionis (61.9)"),
        ]:
            slug = slugify(name)
            path = str(wiki_dir / f"{slug}.md")
            write_article(
                path,
                {
                    "title": name,
                    "type": "indication",
                    "slug": slug,
                    "compiled_at": "2026-04-07T18:00:00Z",
                    "total_drugs": drugs,
                    "total_deals": 200,
                    "freshness_level": "ok",
                    "top_company": top,
                    "phase_counts": {
                        "launched": 10,
                        "phase3": 20,
                        "phase2": 30,
                        "phase1": 40,
                        "discovery": 50,
                        "other": drugs - 150,
                    },
                    "company_rankings": [
                        {
                            "company": top.split(" (")[0],
                            "cpi_score": 80.0,
                            "tier": "A",
                        }
                    ],
                },
                f"## Executive Summary\n\n{name} overview.\n",
            )

        monkeypatch.setattr(
            sys, "argv",
            ["portfolio_report.py", "--wiki-dir", str(tmp_path)],
        )
        from cli_anything.cortellis.skills.landscape.recipes.portfolio_report import main as portfolio_main
        portfolio_main()

        output = capsys.readouterr().out
        assert "Obesity" in output
        assert "Asthma" in output
        assert "ALS" in output
        assert "Cross-Indication Portfolio View" in output

    def test_empty_wiki(self, tmp_path, monkeypatch, capsys):
        """No articles — should produce a message, not crash."""
        (tmp_path / "wiki").mkdir()
        monkeypatch.setattr(
            sys, "argv",
            ["portfolio_report.py", "--wiki-dir", str(tmp_path)],
        )
        from cli_anything.cortellis.skills.landscape.recipes.portfolio_report import main as portfolio_main
        with pytest.raises(SystemExit) as exc_info:
            portfolio_main()
        assert exc_info.value.code == 0

        output = capsys.readouterr().out
        assert "No compiled" in output or "0" in output


class TestWikiFastPathIntegration:
    def test_fresh_article_produces_context(self, tmp_path, monkeypatch):
        """When a fresh article exists, check_wiki_fast_path returns path and article is readable."""
        from cli_anything.cortellis.core.skill_router import check_wiki_fast_path

        # Create a fresh wiki article
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        ind_path = os.path.join(str(tmp_path), "wiki", "indications", "obesity.md")
        write_article(
            ind_path,
            {
                "title": "Obesity",
                "slug": "obesity",
                "compiled_at": now,
                "freshness_level": "ok",
                "source_dir": "raw/obesity",
            },
            "## Executive Summary\n\nObesity landscape.\n",
        )

        # Monkeypatch article_path and check_freshness in skill_router to use tmp_path
        monkeypatch.setattr(
            "cli_anything.cortellis.core.skill_router.article_path",
            lambda t, s, base=None: os.path.join(str(tmp_path), "wiki", t, f"{s}.md"),
        )
        monkeypatch.setattr(
            "cli_anything.cortellis.core.skill_router.check_freshness",
            lambda slug, **kw: "fresh" if slug == "obesity" else "missing",
        )

        result = check_wiki_fast_path("what is the obesity landscape?")
        assert result is not None

        art = read_article(result)
        assert art is not None
        assert "Executive Summary" in art["body"]

    def test_non_landscape_returns_none(self):
        """Non-landscape questions should not trigger fast path."""
        from cli_anything.cortellis.core.skill_router import check_wiki_fast_path

        assert check_wiki_fast_path("show me Pfizer's pipeline") is None
        assert check_wiki_fast_path("drug profile for semaglutide") is None
