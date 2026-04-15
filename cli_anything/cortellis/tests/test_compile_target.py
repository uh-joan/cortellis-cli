"""Tests for compile_target.py — target profile wiki compiler."""

import importlib.util
import json
import os
import sys


from cli_anything.cortellis.utils.wiki import (
    read_article,
    slugify,
)

# target-profile has a hyphen so we load the module directly from its file path
_COMPILE_TARGET_PATH = os.path.join(
    os.path.dirname(__file__),
    "..", "skills", "target-profile", "recipes", "compile_target.py",
)


def _load_compile_target():
    spec = importlib.util.spec_from_file_location("compile_target", _COMPILE_TARGET_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)


SAMPLE_RECORD = {
    "TargetRecordsOutput": {
        "Targets": {
            "Target": {
                "@namemain": "GLP-1 Receptor",
                "Synonyms": {
                    "Synonym": ["GLP1R", "Glucagon-like peptide 1 receptor"]
                },
                "Family": {"$": "GPCR"},
                "Description": "Receptor for glucagon-like peptide-1, mediates insulin secretion.",
                "Localizations": {"Localization": [{"$": "Plasma membrane"}]},
            }
        }
    }
}

SAMPLE_CONDITION_DRUGS = {
    "TargetRecordsOutput": {
        "Targets": {
            "Target": {
                "ConditionDrugAssociations": {
                    "Condition": [
                        {"@name": "Type 2 Diabetes", "DrugId": [{"@highestphase": "Launched", "@status": "Active"}]},
                        {"@name": "Obesity", "DrugId": [{"@highestphase": "Launched", "@status": "Active"}]},
                        {"@name": "NASH", "DrugId": [{"@highestphase": "Phase II"}]},
                    ]
                }
            }
        }
    }
}

SAMPLE_CONDITION_GENES = {
    "TargetRecordsOutput": {
        "Targets": {
            "Target": {
                "ConditionGeneAssociations": {
                    "Condition": [
                        {"@name": "Type 2 Diabetes", "Source": [{"$": "Clinical"}]},
                        {"@name": "Obesity", "Source": [{"$": "Genetic"}]},
                    ]
                }
            }
        }
    }
}

SAMPLE_INTERACTIONS = {
    "TargetRecordsOutput": {
        "Targets": {
            "Target": {
                "Interactions": {
                    "Interaction": [
                        {"CounterpartObject": {"$": "GLP-1"}, "Direction": "Upstream", "Effect": "Activation", "Mechanism": "Ligand-receptor"},
                        {"CounterpartObject": {"$": "Adenylyl cyclase"}, "Direction": "Downstream", "Effect": "Activation", "Mechanism": "Signal transduction"},
                    ]
                }
            }
        }
    }
}

SAMPLE_DRUGS_PIPELINE = {
    "drugResultsOutput": {
        "@totalResults": "3",
        "SearchResults": {
            "Drug": [
                {
                    "@name": "Semaglutide",
                    "@phaseHighest": "Launched",
                    "CompanyOriginator": {"@name": "Novo Nordisk"},
                    "IndicationsPrimary": {"Indication": [{"@name": "Type 2 Diabetes"}, {"@name": "Obesity"}]},
                },
                {
                    "@name": "Tirzepatide",
                    "@phaseHighest": "Launched",
                    "CompanyOriginator": {"@name": "Eli Lilly"},
                    "IndicationsPrimary": {"Indication": [{"@name": "Type 2 Diabetes"}]},
                },
                {
                    "@name": "Liraglutide",
                    "@phaseHighest": "Launched",
                    "CompanyOriginator": {"@name": "Novo Nordisk"},
                    "IndicationsPrimary": {"Indication": [{"@name": "Type 2 Diabetes"}, {"@name": "Obesity"}]},
                },
            ]
        },
    }
}

SAMPLE_PHARMACOLOGY = {
    "drugDesignResultsOutput": {
        "SearchResults": {
            "PharmacologyRecord": [
                {"@drugName": "Semaglutide", "@assayType": "Ki", "@value": "0.35", "@unit": "nM"},
                {"@drugName": "Liraglutide", "@assayType": "EC50", "@value": "2.1", "@unit": "nM"},
            ]
        }
    }
}


def _build_target_dir(tmp_path, target="GLP-1 Receptor"):
    """Create a minimal target profile directory for testing."""
    target_dir = os.path.join(str(tmp_path), "raw", slugify(target))
    os.makedirs(target_dir, exist_ok=True)

    _write_json(os.path.join(target_dir, "record.json"), SAMPLE_RECORD)
    _write_json(os.path.join(target_dir, "condition_drugs.json"), SAMPLE_CONDITION_DRUGS)
    _write_json(os.path.join(target_dir, "condition_genes.json"), SAMPLE_CONDITION_GENES)
    _write_json(os.path.join(target_dir, "interactions.json"), SAMPLE_INTERACTIONS)
    _write_json(os.path.join(target_dir, "drugs_pipeline.json"), SAMPLE_DRUGS_PIPELINE)
    _write_json(os.path.join(target_dir, "pharmacology.json"), SAMPLE_PHARMACOLOGY)

    return target_dir


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCompileTargetCreatesArticle:
    def test_compile_creates_target_article(self, tmp_path, monkeypatch):
        """Running compile_target.main() creates wiki/targets/<slug>.md."""
        target_dir = _build_target_dir(tmp_path, "GLP-1 Receptor")
        wiki_base = str(tmp_path)

        monkeypatch.setattr(
            sys, "argv",
            ["compile_target.py", target_dir, "GLP-1 Receptor", "--wiki-dir", wiki_base],
        )

        compile_target = _load_compile_target()
        compile_target.main()

        expected = os.path.join(wiki_base, "wiki", "targets", "glp-1-receptor.md")
        assert os.path.exists(expected), f"Expected {expected} to exist"

    def test_article_has_correct_type(self, tmp_path, monkeypatch):
        """Compiled article frontmatter has type: target."""
        target_dir = _build_target_dir(tmp_path)
        wiki_base = str(tmp_path)

        monkeypatch.setattr(
            sys, "argv",
            ["compile_target.py", target_dir, "GLP-1 Receptor", "--wiki-dir", wiki_base],
        )

        compile_target = _load_compile_target()
        compile_target.main()

        path = os.path.join(wiki_base, "wiki", "targets", "glp-1-receptor.md")
        art = read_article(path)
        assert art is not None
        assert art["meta"]["type"] == "target"
        assert art["meta"]["slug"] == "glp-1-receptor"
        assert art["meta"]["title"] == "GLP-1 Receptor"


class TestFrontmatterHasTargetFields:
    def test_gene_symbol_in_frontmatter(self, tmp_path, monkeypatch):
        """Frontmatter contains gene_symbol extracted from record.json."""
        target_dir = _build_target_dir(tmp_path)
        wiki_base = str(tmp_path)

        monkeypatch.setattr(
            sys, "argv",
            ["compile_target.py", target_dir, "GLP-1 Receptor", "--wiki-dir", wiki_base],
        )

        compile_target = _load_compile_target()
        compile_target.main()

        path = os.path.join(wiki_base, "wiki", "targets", "glp-1-receptor.md")
        art = read_article(path)
        assert art["meta"]["gene_symbol"] == "GLP1R"

    def test_family_in_frontmatter(self, tmp_path, monkeypatch):
        """Frontmatter contains family (protein family)."""
        target_dir = _build_target_dir(tmp_path)
        wiki_base = str(tmp_path)

        monkeypatch.setattr(
            sys, "argv",
            ["compile_target.py", target_dir, "GLP-1 Receptor", "--wiki-dir", wiki_base],
        )

        compile_target = _load_compile_target()
        compile_target.main()

        path = os.path.join(wiki_base, "wiki", "targets", "glp-1-receptor.md")
        art = read_article(path)
        assert art["meta"]["family"] == "GPCR"

    def test_disease_count_in_frontmatter(self, tmp_path, monkeypatch):
        """Frontmatter contains disease_count from condition_drugs.json."""
        target_dir = _build_target_dir(tmp_path)
        wiki_base = str(tmp_path)

        monkeypatch.setattr(
            sys, "argv",
            ["compile_target.py", target_dir, "GLP-1 Receptor", "--wiki-dir", wiki_base],
        )

        compile_target = _load_compile_target()
        compile_target.main()

        path = os.path.join(wiki_base, "wiki", "targets", "glp-1-receptor.md")
        art = read_article(path)
        # SAMPLE_CONDITION_DRUGS has 3 conditions
        assert art["meta"]["disease_count"] == 3

    def test_drug_count_in_frontmatter(self, tmp_path, monkeypatch):
        """Frontmatter contains drug_count from drugs_pipeline.json."""
        target_dir = _build_target_dir(tmp_path)
        wiki_base = str(tmp_path)

        monkeypatch.setattr(
            sys, "argv",
            ["compile_target.py", target_dir, "GLP-1 Receptor", "--wiki-dir", wiki_base],
        )

        compile_target = _load_compile_target()
        compile_target.main()

        path = os.path.join(wiki_base, "wiki", "targets", "glp-1-receptor.md")
        art = read_article(path)
        # SAMPLE_DRUGS_PIPELINE has 3 drugs
        assert art["meta"]["drug_count"] == 3

    def test_organism_in_frontmatter(self, tmp_path, monkeypatch):
        """Frontmatter contains organism field."""
        target_dir = _build_target_dir(tmp_path)
        wiki_base = str(tmp_path)

        monkeypatch.setattr(
            sys, "argv",
            ["compile_target.py", target_dir, "GLP-1 Receptor", "--wiki-dir", wiki_base],
        )

        compile_target = _load_compile_target()
        compile_target.main()

        path = os.path.join(wiki_base, "wiki", "targets", "glp-1-receptor.md")
        art = read_article(path)
        assert art["meta"]["organism"] == "Human"


class TestBodyHasSections:
    def _compile(self, tmp_path, monkeypatch):
        target_dir = _build_target_dir(tmp_path)
        wiki_base = str(tmp_path)

        monkeypatch.setattr(
            sys, "argv",
            ["compile_target.py", target_dir, "GLP-1 Receptor", "--wiki-dir", wiki_base],
        )

        compile_target = _load_compile_target()
        compile_target.main()

        path = os.path.join(wiki_base, "wiki", "targets", "glp-1-receptor.md")
        return read_article(path)

    def test_body_has_biology_section(self, tmp_path, monkeypatch):
        """Article body contains ## Biology section."""
        art = self._compile(tmp_path, monkeypatch)
        assert "## Biology" in art["body"]

    def test_body_has_disease_associations_section(self, tmp_path, monkeypatch):
        """Article body contains ## Disease Associations section."""
        art = self._compile(tmp_path, monkeypatch)
        assert "## Disease Associations" in art["body"]

    def test_body_has_drug_pipeline_section(self, tmp_path, monkeypatch):
        """Article body contains ## Drug Pipeline section."""
        art = self._compile(tmp_path, monkeypatch)
        assert "## Drug Pipeline" in art["body"]

    def test_biology_has_function(self, tmp_path, monkeypatch):
        """Biology section lists the function from record.json."""
        art = self._compile(tmp_path, monkeypatch)
        assert "insulin secretion" in art["body"]

    def test_disease_associations_list_diseases(self, tmp_path, monkeypatch):
        """Disease Associations section lists disease names."""
        art = self._compile(tmp_path, monkeypatch)
        assert "Type 2 Diabetes" in art["body"]
        assert "Obesity" in art["body"]

    def test_drug_pipeline_lists_drugs_with_wikilinks(self, tmp_path, monkeypatch):
        """Drug Pipeline uses [[wikilinks]] for drugs."""
        art = self._compile(tmp_path, monkeypatch)
        assert r"[[semaglutide\|Semaglutide]]" in art["body"]
        assert r"[[tirzepatide\|Tirzepatide]]" in art["body"]

    def test_drug_pipeline_uses_wikilinks_for_companies(self, tmp_path, monkeypatch):
        """Drug Pipeline uses [[wikilinks]] for companies."""
        art = self._compile(tmp_path, monkeypatch)
        assert r"[[novo-nordisk\|Novo Nordisk]]" in art["body"]

    def test_body_has_protein_interactions_section(self, tmp_path, monkeypatch):
        """Article body contains ## Protein Interactions section."""
        art = self._compile(tmp_path, monkeypatch)
        assert "## Protein Interactions" in art["body"]

    def test_body_has_pharmacology_section(self, tmp_path, monkeypatch):
        """Article body contains ## Pharmacology section."""
        art = self._compile(tmp_path, monkeypatch)
        assert "## Pharmacology" in art["body"]

    def test_body_has_data_sources_section(self, tmp_path, monkeypatch):
        """Article body contains ## Data Sources section."""
        art = self._compile(tmp_path, monkeypatch)
        assert "## Data Sources" in art["body"]

    def test_pharmacology_lists_compounds(self, tmp_path, monkeypatch):
        """Pharmacology section lists compound names."""
        art = self._compile(tmp_path, monkeypatch)
        assert "Semaglutide" in art["body"]
        assert "nM" in art["body"]


class TestTargetUpdatesIndex:
    def test_updates_index(self, tmp_path, monkeypatch):
        """compile_target updates wiki/INDEX.md with the target entry."""
        target_dir = _build_target_dir(tmp_path)
        wiki_base = str(tmp_path)

        monkeypatch.setattr(
            sys, "argv",
            ["compile_target.py", target_dir, "GLP-1 Receptor", "--wiki-dir", wiki_base],
        )

        compile_target = _load_compile_target()
        compile_target.main()

        index_path = os.path.join(wiki_base, "wiki", "INDEX.md")
        assert os.path.exists(index_path), "wiki/INDEX.md should be created"
        content = open(index_path).read()
        assert "GLP-1 Receptor" in content

    def test_index_has_targets_section(self, tmp_path, monkeypatch):
        """INDEX.md has a Targets section after compile."""
        target_dir = _build_target_dir(tmp_path)
        wiki_base = str(tmp_path)

        monkeypatch.setattr(
            sys, "argv",
            ["compile_target.py", target_dir, "GLP-1 Receptor", "--wiki-dir", wiki_base],
        )

        compile_target = _load_compile_target()
        compile_target.main()

        content = open(os.path.join(wiki_base, "wiki", "INDEX.md")).read()
        assert "## Targets" in content

    def test_index_has_gene_symbol(self, tmp_path, monkeypatch):
        """INDEX.md Targets section includes the gene symbol."""
        target_dir = _build_target_dir(tmp_path)
        wiki_base = str(tmp_path)

        monkeypatch.setattr(
            sys, "argv",
            ["compile_target.py", target_dir, "GLP-1 Receptor", "--wiki-dir", wiki_base],
        )

        compile_target = _load_compile_target()
        compile_target.main()

        content = open(os.path.join(wiki_base, "wiki", "INDEX.md")).read()
        assert "GLP1R" in content


class TestEmptyInputHandling:
    def test_empty_json_files_no_crash(self, tmp_path, monkeypatch):
        """Compiler handles missing/empty JSON files gracefully."""
        target_dir = os.path.join(str(tmp_path), "raw", "empty-target")
        os.makedirs(target_dir, exist_ok=True)
        # Write only empty dicts
        for fname in ["record.json", "condition_drugs.json", "condition_genes.json",
                      "interactions.json", "drugs_pipeline.json", "pharmacology.json"]:
            _write_json(os.path.join(target_dir, fname), {})

        wiki_base = str(tmp_path)
        monkeypatch.setattr(
            sys, "argv",
            ["compile_target.py", target_dir, "Empty Target", "--wiki-dir", wiki_base],
        )

        compile_target = _load_compile_target()
        compile_target.main()  # Should not raise

        path = os.path.join(wiki_base, "wiki", "targets", "empty-target.md")
        assert os.path.exists(path)
        art = read_article(path)
        assert art["meta"]["type"] == "target"

    def test_missing_json_files_no_crash(self, tmp_path, monkeypatch):
        """Compiler handles completely absent JSON files gracefully."""
        target_dir = os.path.join(str(tmp_path), "raw", "sparse-target")
        os.makedirs(target_dir, exist_ok=True)
        # No JSON files at all

        wiki_base = str(tmp_path)
        monkeypatch.setattr(
            sys, "argv",
            ["compile_target.py", target_dir, "Sparse Target", "--wiki-dir", wiki_base],
        )

        compile_target = _load_compile_target()
        compile_target.main()  # Should not raise

        path = os.path.join(wiki_base, "wiki", "targets", "sparse-target.md")
        assert os.path.exists(path)
