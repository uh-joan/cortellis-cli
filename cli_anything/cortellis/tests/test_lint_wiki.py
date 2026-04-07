"""Tests for lint_wiki.py — wiki health-check checks."""

import os
from datetime import datetime, timezone, timedelta

import pytest

from cli_anything.cortellis.utils.wiki import write_article
from cli_anything.cortellis.skills.landscape.recipes.lint_wiki import (
    check_broken_wikilinks,
    check_orphan_pages,
    check_stale_articles,
    check_missing_cross_refs,
    check_empty_sections,
    check_index_consistency,
    check_freshness_gaps,
    run_all_checks,
    format_lint_report,
)


def _wiki_dir(tmp_path) -> str:
    """Create and return a wiki/ directory under tmp_path."""
    wiki = os.path.join(str(tmp_path), "wiki")
    os.makedirs(wiki, exist_ok=True)
    return wiki


def _write_indication(wiki_dir, slug, body="", meta_extra=None):
    path = os.path.join(wiki_dir, "indications", f"{slug}.md")
    meta = {"title": slug.replace("-", " ").title(), "slug": slug, "type": "indication",
            "compiled_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    if meta_extra:
        meta.update(meta_extra)
    write_article(path, meta, body)
    return path


def _write_company(wiki_dir, slug, body=""):
    path = os.path.join(wiki_dir, "companies", f"{slug}.md")
    meta = {"title": slug.replace("-", " ").title(), "slug": slug, "type": "company",
            "compiled_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    write_article(path, meta, body)
    return path


class TestBrokenWikilinks:
    def test_finds_broken_link(self, tmp_path):
        wiki_dir = _wiki_dir(tmp_path)
        _write_indication(wiki_dir, "obesity", body="See also [[nonexistent-company]].")
        issues = check_broken_wikilinks(wiki_dir)
        assert len(issues) == 1
        assert issues[0]["broken_link"] == "nonexistent-company"
        assert "obesity" in issues[0]["source_article"]

    def test_valid_links_pass(self, tmp_path):
        wiki_dir = _wiki_dir(tmp_path)
        _write_company(wiki_dir, "novo-nordisk")
        _write_indication(wiki_dir, "obesity", body="Leader: [[novo-nordisk|Novo Nordisk]].")
        issues = check_broken_wikilinks(wiki_dir)
        assert issues == []

    def test_link_with_display_text_broken(self, tmp_path):
        wiki_dir = _wiki_dir(tmp_path)
        _write_indication(wiki_dir, "obesity", body="See [[missing-slug|Missing Co]].")
        issues = check_broken_wikilinks(wiki_dir)
        assert len(issues) == 1
        assert issues[0]["broken_link"] == "missing-slug"

    def test_no_links_no_issues(self, tmp_path):
        wiki_dir = _wiki_dir(tmp_path)
        _write_indication(wiki_dir, "obesity", body="No wikilinks here at all.")
        issues = check_broken_wikilinks(wiki_dir)
        assert issues == []


class TestOrphanPages:
    def test_finds_orphan(self, tmp_path):
        wiki_dir = _wiki_dir(tmp_path)
        # article-a links to article-b; article-c is orphaned
        _write_indication(wiki_dir, "article-a", body="See [[article-b]].")
        _write_indication(wiki_dir, "article-b")
        _write_indication(wiki_dir, "article-c")  # no inbound links
        orphans = check_orphan_pages(wiki_dir)
        slugs = [o["article_path"].replace("indications/", "").replace(".md", "") for o in orphans]
        assert "article-c" in slugs
        assert "article-b" not in slugs  # article-b is linked from article-a

    def test_all_linked_no_orphans(self, tmp_path):
        wiki_dir = _wiki_dir(tmp_path)
        _write_indication(wiki_dir, "article-a", body="See [[article-b]].")
        _write_indication(wiki_dir, "article-b", body="See [[article-a]].")
        orphans = check_orphan_pages(wiki_dir)
        slugs = [o["article_path"] for o in orphans]
        assert not any("article-a" in s or "article-b" in s for s in slugs)

    def test_single_article_is_orphan(self, tmp_path):
        wiki_dir = _wiki_dir(tmp_path)
        _write_indication(wiki_dir, "lonely")
        orphans = check_orphan_pages(wiki_dir)
        assert any("lonely" in o["article_path"] for o in orphans)


class TestStaleArticles:
    def test_finds_old_article(self, tmp_path):
        wiki_dir = _wiki_dir(tmp_path)
        old_date = (datetime.now(timezone.utc) - timedelta(days=45)).strftime("%Y-%m-%dT%H:%M:%SZ")
        _write_indication(wiki_dir, "old-drug", meta_extra={"compiled_at": old_date})
        issues = check_stale_articles(wiki_dir, max_age_days=30)
        assert len(issues) == 1
        assert issues[0]["age_days"] >= 45

    def test_fresh_article_not_flagged(self, tmp_path):
        wiki_dir = _wiki_dir(tmp_path)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        _write_indication(wiki_dir, "fresh-drug", meta_extra={"compiled_at": now})
        issues = check_stale_articles(wiki_dir, max_age_days=30)
        assert issues == []

    def test_no_compiled_at_skipped(self, tmp_path):
        wiki_dir = _wiki_dir(tmp_path)
        path = os.path.join(wiki_dir, "indications", "nodates.md")
        write_article(path, {"title": "No Dates", "slug": "nodates"}, "Body")
        issues = check_stale_articles(wiki_dir, max_age_days=30)
        assert issues == []


class TestMissingCrossRefs:
    def test_finds_missing_company(self, tmp_path):
        wiki_dir = _wiki_dir(tmp_path)
        _write_indication(
            wiki_dir, "obesity",
            meta_extra={"company_rankings": [{"company": "Beijing QL Biopharm", "cpi_score": 60}]},
        )
        issues = check_missing_cross_refs(wiki_dir)
        assert len(issues) == 1
        assert "beijing-ql-biopharm" in issues[0]["expected_slug"]
        assert issues[0]["indication"] == "Obesity"

    def test_existing_company_no_issue(self, tmp_path):
        wiki_dir = _wiki_dir(tmp_path)
        _write_company(wiki_dir, "novo-nordisk")
        _write_indication(
            wiki_dir, "obesity",
            meta_extra={"company_rankings": [{"company": "Novo Nordisk", "cpi_score": 95}]},
        )
        issues = check_missing_cross_refs(wiki_dir)
        assert issues == []

    def test_no_rankings_no_issues(self, tmp_path):
        wiki_dir = _wiki_dir(tmp_path)
        _write_indication(wiki_dir, "obesity")
        issues = check_missing_cross_refs(wiki_dir)
        assert issues == []


class TestEmptySections:
    def test_finds_empty_section(self, tmp_path):
        wiki_dir = _wiki_dir(tmp_path)
        body = "## Introduction\n\nSome content.\n\n## Empty Section\n\n## Next Section\n\nMore content.\n"
        _write_indication(wiki_dir, "test-ind", body=body)
        issues = check_empty_sections(wiki_dir)
        assert any(i["empty_section"] == "Empty Section" for i in issues)

    def test_all_sections_have_content(self, tmp_path):
        wiki_dir = _wiki_dir(tmp_path)
        body = "## Introduction\n\nSome content.\n\n## Details\n\nMore content.\n"
        _write_indication(wiki_dir, "test-ind", body=body)
        issues = check_empty_sections(wiki_dir)
        assert issues == []

    def test_no_headers_no_issues(self, tmp_path):
        wiki_dir = _wiki_dir(tmp_path)
        _write_indication(wiki_dir, "test-ind", body="Just plain text, no headers.")
        issues = check_empty_sections(wiki_dir)
        assert issues == []


class TestIndexConsistency:
    def test_missing_from_index(self, tmp_path):
        wiki_dir = _wiki_dir(tmp_path)
        _write_indication(wiki_dir, "orphan-indication")
        # Don't write INDEX.md — article exists but is not indexed
        result = check_index_consistency(wiki_dir)
        assert any("orphan-indication.md" in p for p in result["missing_from_index"])
        assert result["in_index_but_missing"] == []

    def test_in_index_but_missing(self, tmp_path):
        wiki_dir = _wiki_dir(tmp_path)
        # Write INDEX.md referencing an article that doesn't exist
        idx_path = os.path.join(wiki_dir, "INDEX.md")
        with open(idx_path, "w") as f:
            f.write("| [Ghost](indications/ghost.md) | - | - | - | - |\n")
        result = check_index_consistency(wiki_dir)
        assert any("ghost.md" in p for p in result["in_index_but_missing"])

    def test_consistent_index(self, tmp_path):
        wiki_dir = _wiki_dir(tmp_path)
        _write_indication(wiki_dir, "obesity")
        idx_path = os.path.join(wiki_dir, "INDEX.md")
        with open(idx_path, "w") as f:
            f.write("| [Obesity](indications/obesity.md) | 478 | Novo Nordisk | 2026-04-07 | ok |\n")
        result = check_index_consistency(wiki_dir)
        assert result["missing_from_index"] == []
        assert result["in_index_but_missing"] == []


class TestFreshnessGaps:
    def test_finds_gap(self, tmp_path):
        wiki_dir = _wiki_dir(tmp_path)
        # Write a wiki article compiled at a past time
        old_time = (datetime.now(timezone.utc) - timedelta(hours=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
        _write_indication(wiki_dir, "obesity", meta_extra={"compiled_at": old_time})
        # Write a raw dir with a newer file
        raw_dir = os.path.join(str(tmp_path), "raw", "obesity")
        os.makedirs(raw_dir, exist_ok=True)
        csv_path = os.path.join(raw_dir, "launched.csv")
        with open(csv_path, "w") as f:
            f.write("name,phase\nDrugA,Launched\n")
        # Touch the file to ensure mtime is now
        import time
        os.utime(csv_path, (time.time(), time.time()))

        issues = check_freshness_gaps(wiki_dir, raw_base="raw")
        assert any(i["indication"] == "obesity" for i in issues)
        assert any(i["gap_hours"] >= 4.9 for i in issues)

    def test_no_gap_when_wiki_is_newer(self, tmp_path):
        wiki_dir = _wiki_dir(tmp_path)
        # Wiki article compiled just now
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        _write_indication(wiki_dir, "obesity", meta_extra={"compiled_at": now})
        # Raw dir with an older file
        raw_dir = os.path.join(str(tmp_path), "raw", "obesity")
        os.makedirs(raw_dir, exist_ok=True)
        csv_path = os.path.join(raw_dir, "launched.csv")
        with open(csv_path, "w") as f:
            f.write("name,phase\nDrugA,Launched\n")
        # Set mtime to 1 hour ago
        import time
        old_ts = time.time() - 3600
        os.utime(csv_path, (old_ts, old_ts))

        issues = check_freshness_gaps(wiki_dir, raw_base="raw")
        assert not any(i["indication"] == "obesity" for i in issues)

    def test_no_raw_dir_no_issues(self, tmp_path):
        wiki_dir = _wiki_dir(tmp_path)
        _write_indication(wiki_dir, "obesity")
        issues = check_freshness_gaps(wiki_dir, raw_base="raw")
        assert issues == []


class TestRunAllChecks:
    def test_returns_all_categories(self, tmp_path):
        wiki_dir = _wiki_dir(tmp_path)
        result = run_all_checks(wiki_dir)
        assert set(result.keys()) == {
            "broken_wikilinks",
            "orphan_pages",
            "stale_articles",
            "missing_cross_refs",
            "empty_sections",
            "index_consistency",
            "freshness_gaps",
        }

    def test_index_consistency_is_dict(self, tmp_path):
        wiki_dir = _wiki_dir(tmp_path)
        result = run_all_checks(wiki_dir)
        assert isinstance(result["index_consistency"], dict)
        assert "missing_from_index" in result["index_consistency"]
        assert "in_index_but_missing" in result["index_consistency"]

    def test_format_report_runs(self, tmp_path):
        wiki_dir = _wiki_dir(tmp_path)
        results = run_all_checks(wiki_dir)
        report = format_lint_report(results)
        assert "Wiki Lint Report" in report
        assert "7 checks run" in report
        assert "Summary" in report
