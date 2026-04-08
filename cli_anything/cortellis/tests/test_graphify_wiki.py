"""Tests for graphify_wiki.py — knowledge graph builder from wiki frontmatter."""

import json
import os
import sys

import pytest

# Allow imports from project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

try:
    import networkx as nx
    _NX_AVAILABLE = True
except ImportError:
    _NX_AVAILABLE = False

pytestmark = pytest.mark.skipif(not _NX_AVAILABLE, reason="networkx not installed")

from cli_anything.cortellis.utils.wiki import write_article, article_path
from cli_anything.cortellis.skills.landscape.recipes.graphify_wiki import (
    build_graph_from_wiki,
    find_god_nodes,
    find_clusters,
    find_bridges,
    compute_stats,
    generate_graph_report,
    write_graph_json,
    main,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_indication(tmp_path, slug, title, company_rankings=None, related=None):
    """Write a minimal indication article to tmp_path/wiki/indications/<slug>.md."""
    meta = {
        "title": title,
        "type": "indication",
        "slug": slug,
        "compiled_at": "2026-01-01T00:00:00Z",
        "total_drugs": 10,
        "company_rankings": company_rankings or [],
        "related": related or [],
    }
    path = article_path("indications", slug, str(tmp_path))
    write_article(path, meta, f"## {title}\n")


def make_company(tmp_path, slug, title, indications=None, related=None):
    """Write a minimal company article to tmp_path/wiki/companies/<slug>.md."""
    meta = {
        "title": title,
        "type": "company",
        "slug": slug,
        "compiled_at": "2026-01-01T00:00:00Z",
        "indications": indications or {},
        "best_cpi": "50.0",
        "related": related or [],
    }
    path = article_path("companies", slug, str(tmp_path))
    write_article(path, meta, f"## {title}\n")


def make_drug(tmp_path, slug, title, originator="", indications=None, phase="Phase 3"):
    """Write a minimal drug article to tmp_path/wiki/drugs/<slug>.md."""
    meta = {
        "title": title,
        "type": "drug",
        "slug": slug,
        "compiled_at": "2026-01-01T00:00:00Z",
        "phase": phase,
        "originator": originator,
        "indications": indications or [],
    }
    path = article_path("drugs", slug, str(tmp_path))
    write_article(path, meta, f"## {title}\n")


# ---------------------------------------------------------------------------
# TestBuildGraph
# ---------------------------------------------------------------------------

class TestBuildGraph:
    def test_creates_nodes_from_articles(self, tmp_path):
        """Create 2 indication + 2 company articles, verify 4 nodes."""
        make_indication(tmp_path, "obesity", "Obesity")
        make_indication(tmp_path, "diabetes", "Diabetes")
        make_company(tmp_path, "novo-nordisk", "Novo Nordisk")
        make_company(tmp_path, "eli-lilly", "Eli Lilly")

        wiki_dir = os.path.join(str(tmp_path), "wiki")
        G = build_graph_from_wiki(wiki_dir)

        assert G.number_of_nodes() == 4
        assert "obesity" in G.nodes
        assert "diabetes" in G.nodes
        assert "novo-nordisk" in G.nodes
        assert "eli-lilly" in G.nodes

    def test_creates_edges_from_rankings(self, tmp_path):
        """Indication with company_rankings → edges to matching company nodes."""
        make_indication(
            tmp_path,
            "obesity",
            "Obesity",
            company_rankings=[
                {"company": "Novo Nordisk", "cpi_score": 95.0, "tier": "A"},
                {"company": "Eli Lilly", "cpi_score": 70.0, "tier": "A"},
            ],
        )
        make_company(tmp_path, "novo-nordisk", "Novo Nordisk")
        make_company(tmp_path, "eli-lilly", "Eli Lilly")

        wiki_dir = os.path.join(str(tmp_path), "wiki")
        G = build_graph_from_wiki(wiki_dir)

        assert G.has_edge("obesity", "novo-nordisk")
        assert G.has_edge("obesity", "eli-lilly")
        assert G["obesity"]["novo-nordisk"]["weight"] == 95.0
        assert G["obesity"]["eli-lilly"]["weight"] == 70.0

    def test_creates_edges_from_related(self, tmp_path):
        """Indication with related list → edges to matching nodes."""
        make_indication(
            tmp_path,
            "obesity",
            "Obesity",
            related=["novo-nordisk"],
        )
        make_company(tmp_path, "novo-nordisk", "Novo Nordisk")

        wiki_dir = os.path.join(str(tmp_path), "wiki")
        G = build_graph_from_wiki(wiki_dir)

        assert G.has_edge("obesity", "novo-nordisk")

    def test_creates_edges_from_company_indications(self, tmp_path):
        """Company.indications dict → edges to indication nodes."""
        make_indication(tmp_path, "obesity", "Obesity")
        make_company(
            tmp_path,
            "novo-nordisk",
            "Novo Nordisk",
            indications={"obesity": {"cpi_score": 95.0, "cpi_tier": "A"}},
        )

        wiki_dir = os.path.join(str(tmp_path), "wiki")
        G = build_graph_from_wiki(wiki_dir)

        assert G.has_edge("novo-nordisk", "obesity")

    def test_creates_edges_from_drug_originator(self, tmp_path):
        """Drug with originator matching a company node → edge created."""
        make_company(tmp_path, "novo-nordisk", "Novo Nordisk")
        make_drug(tmp_path, "semaglutide", "Semaglutide", originator="Novo Nordisk")

        wiki_dir = os.path.join(str(tmp_path), "wiki")
        G = build_graph_from_wiki(wiki_dir)

        assert G.has_edge("semaglutide", "novo-nordisk")

    def test_handles_empty_wiki(self, tmp_path):
        """Empty wiki → empty graph, no crash."""
        wiki_dir = os.path.join(str(tmp_path), "wiki")
        os.makedirs(wiki_dir, exist_ok=True)

        G = build_graph_from_wiki(wiki_dir)

        assert G.number_of_nodes() == 0
        assert G.number_of_edges() == 0

    def test_node_attributes_set(self, tmp_path):
        """Node attributes (type, title, slug) are populated correctly."""
        make_indication(tmp_path, "obesity", "Obesity")
        make_company(tmp_path, "novo-nordisk", "Novo Nordisk")

        wiki_dir = os.path.join(str(tmp_path), "wiki")
        G = build_graph_from_wiki(wiki_dir)

        assert G.nodes["obesity"]["type"] == "indication"
        assert G.nodes["obesity"]["title"] == "Obesity"
        assert G.nodes["novo-nordisk"]["type"] == "company"
        assert G.nodes["novo-nordisk"]["title"] == "Novo Nordisk"

    def test_no_self_loops(self, tmp_path):
        """Articles with self-referencing related entries do not produce self-loops."""
        make_indication(tmp_path, "obesity", "Obesity", related=["obesity"])

        wiki_dir = os.path.join(str(tmp_path), "wiki")
        G = build_graph_from_wiki(wiki_dir)

        assert not G.has_edge("obesity", "obesity")


# ---------------------------------------------------------------------------
# TestGodNodes
# ---------------------------------------------------------------------------

class TestGodNodes:
    def test_finds_highest_degree(self):
        """Build simple star graph, verify god node detection returns hub first."""
        G = nx.Graph()
        G.add_node("hub", type="indication", title="Hub", slug="hub")
        for i in range(5):
            node = f"company-{i}"
            G.add_node(node, type="company", title=f"Company {i}", slug=node)
            G.add_edge("hub", node)

        result = find_god_nodes(G, top_n=3)

        assert len(result) == 3
        assert result[0]["node"] == "hub"
        assert result[0]["degree"] == 5

    def test_returns_empty_for_empty_graph(self):
        """Empty graph returns empty list."""
        G = nx.Graph()
        assert find_god_nodes(G) == []

    def test_top_n_respected(self):
        """top_n parameter limits results."""
        G = nx.Graph()
        for i in range(10):
            G.add_node(f"node-{i}", type="company", title=f"Node {i}", slug=f"node-{i}")
        G.add_edge("node-0", "node-1")
        G.add_edge("node-0", "node-2")

        result = find_god_nodes(G, top_n=2)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# TestClusters
# ---------------------------------------------------------------------------

class TestClusters:
    def test_connected_components_fallback(self):
        """Without graspologic, uses connected_components — two disconnected subgraphs."""
        G = nx.Graph()
        G.add_node("a", type="indication", title="A", slug="a")
        G.add_node("b", type="company", title="B", slug="b")
        G.add_node("c", type="indication", title="C", slug="c")
        G.add_node("d", type="company", title="D", slug="d")
        G.add_edge("a", "b")
        G.add_edge("c", "d")
        # a-b and c-d are disconnected

        clusters = find_clusters(G)

        assert len(clusters) == 2
        all_nodes = {e["node"] for cl in clusters for e in cl["nodes"]}
        assert all_nodes == {"a", "b", "c", "d"}

    def test_single_component(self):
        """Fully connected graph returns one cluster."""
        G = nx.Graph()
        for n in ("a", "b", "c"):
            G.add_node(n, type="indication", title=n.upper(), slug=n)
        G.add_edge("a", "b")
        G.add_edge("b", "c")

        clusters = find_clusters(G)

        assert len(clusters) == 1
        assert len(clusters[0]["nodes"]) == 3

    def test_empty_graph(self):
        """Empty graph returns empty clusters."""
        G = nx.Graph()
        assert find_clusters(G) == []

    def test_cluster_has_label(self):
        """Each cluster entry has a non-empty label."""
        G = nx.Graph()
        G.add_node("obesity", type="indication", title="Obesity", slug="obesity")
        G.add_node("novo-nordisk", type="company", title="Novo Nordisk", slug="novo-nordisk")
        G.add_edge("obesity", "novo-nordisk")

        clusters = find_clusters(G)

        assert len(clusters) == 1
        assert clusters[0]["label"]


# ---------------------------------------------------------------------------
# TestBridges
# ---------------------------------------------------------------------------

class TestBridges:
    def test_finds_bridge_between_clusters(self):
        """Node connecting two separate clusters is identified as a bridge."""
        G = nx.Graph()
        # Cluster A: obesity - novo-nordisk
        G.add_node("obesity", type="indication", title="Obesity", slug="obesity")
        G.add_node("novo-nordisk", type="company", title="Novo Nordisk", slug="novo-nordisk")
        G.add_edge("obesity", "novo-nordisk")
        # Cluster B: cancer - pfizer
        G.add_node("cancer", type="indication", title="Cancer", slug="cancer")
        G.add_node("pfizer", type="company", title="Pfizer", slug="pfizer")
        G.add_edge("cancer", "pfizer")
        # Bridge: connector links both clusters
        G.add_node("connector", type="company", title="Big Pharma", slug="connector")
        G.add_edge("connector", "obesity")
        G.add_edge("connector", "cancer")

        clusters = find_clusters(G)
        bridges = find_bridges(G, clusters)

        bridge_nodes = {b["node"] for b in bridges}
        assert "connector" in bridge_nodes

    def test_no_bridges_single_component(self):
        """Single fully connected component → all nodes touch same cluster, no bridges."""
        G = nx.Graph()
        for n in ("a", "b", "c"):
            G.add_node(n, type="indication", title=n.upper(), slug=n)
        G.add_edge("a", "b")
        G.add_edge("b", "c")
        G.add_edge("a", "c")

        clusters = find_clusters(G)
        bridges = find_bridges(G, clusters)

        # All in one cluster, no cross-cluster connections
        assert bridges == []

    def test_empty_graph_no_bridges(self):
        """Empty graph returns no bridges."""
        G = nx.Graph()
        assert find_bridges(G, []) == []


# ---------------------------------------------------------------------------
# TestComputeStats
# ---------------------------------------------------------------------------

class TestComputeStats:
    def test_basic_stats(self):
        """Verify node_count, edge_count, and components are correct."""
        G = nx.Graph()
        G.add_node("a", type="indication", title="A", slug="a")
        G.add_node("b", type="company", title="B", slug="b")
        G.add_node("c", type="indication", title="C", slug="c")
        G.add_edge("a", "b")

        stats = compute_stats(G)

        assert stats["node_count"] == 3
        assert stats["edge_count"] == 1
        assert stats["components"] == 2  # a-b connected, c isolated

    def test_empty_graph(self):
        """Empty graph returns zero stats."""
        G = nx.Graph()
        stats = compute_stats(G)
        assert stats["node_count"] == 0
        assert stats["edge_count"] == 0
        assert stats["components"] == 0

    def test_by_type(self):
        """Type breakdown counts are correct."""
        G = nx.Graph()
        G.add_node("ind1", type="indication", title="Ind1", slug="ind1")
        G.add_node("comp1", type="company", title="Comp1", slug="comp1")
        G.add_node("comp2", type="company", title="Comp2", slug="comp2")

        stats = compute_stats(G)
        assert stats["by_type"]["indication"] == 1
        assert stats["by_type"]["company"] == 2


# ---------------------------------------------------------------------------
# TestGraphReport
# ---------------------------------------------------------------------------

class TestGraphReport:
    def _make_test_graph(self):
        G = nx.Graph()
        G.add_node("obesity", type="indication", title="Obesity", slug="obesity")
        G.add_node("novo-nordisk", type="company", title="Novo Nordisk", slug="novo-nordisk")
        G.add_node("eli-lilly", type="company", title="Eli Lilly", slug="eli-lilly")
        G.add_edge("obesity", "novo-nordisk", weight=95.0)
        G.add_edge("obesity", "eli-lilly", weight=70.0)
        return G

    def test_report_has_sections(self):
        """Verify report contains God Nodes, Clusters, Bridge Nodes, Network Statistics."""
        G = self._make_test_graph()
        god_nodes = find_god_nodes(G)
        clusters = find_clusters(G)
        bridges = find_bridges(G, clusters)
        stats = compute_stats(G)

        report = generate_graph_report(G, god_nodes, clusters, bridges, stats)

        assert "God Nodes" in report
        assert "Clusters" in report
        assert "Bridge Nodes" in report
        assert "Network Statistics" in report

    def test_report_contains_god_node_title(self):
        """Report lists the highest-degree node by title."""
        G = self._make_test_graph()
        god_nodes = find_god_nodes(G)
        clusters = find_clusters(G)
        bridges = find_bridges(G, clusters)
        stats = compute_stats(G)

        report = generate_graph_report(G, god_nodes, clusters, bridges, stats)

        assert "Obesity" in report

    def test_report_shows_node_edge_counts(self):
        """Network Statistics section includes node and edge counts."""
        G = self._make_test_graph()
        god_nodes = find_god_nodes(G)
        clusters = find_clusters(G)
        bridges = find_bridges(G, clusters)
        stats = compute_stats(G)

        report = generate_graph_report(G, god_nodes, clusters, bridges, stats)

        assert "Nodes: 3" in report
        assert "Edges: 2" in report


# ---------------------------------------------------------------------------
# TestMainOutput
# ---------------------------------------------------------------------------

class TestMainOutput:
    def test_writes_graph_json(self, tmp_path, monkeypatch):
        """Verify graph.json is created by main()."""
        make_indication(tmp_path, "obesity", "Obesity", related=["novo-nordisk"])
        make_company(tmp_path, "novo-nordisk", "Novo Nordisk")

        monkeypatch.setattr(
            sys, "argv", ["graphify_wiki.py", "--wiki-dir", str(tmp_path)]
        )
        main()

        graph_path = os.path.join(str(tmp_path), "wiki", "graph.json")
        assert os.path.exists(graph_path)

        with open(graph_path, encoding="utf-8") as f:
            data = json.load(f)
        assert "nodes" in data
        assert len(data["nodes"]) == 2

    def test_writes_report(self, tmp_path, monkeypatch):
        """Verify GRAPH_REPORT.md is created by main()."""
        make_indication(tmp_path, "obesity", "Obesity")
        make_company(tmp_path, "novo-nordisk", "Novo Nordisk")

        monkeypatch.setattr(
            sys, "argv", ["graphify_wiki.py", "--wiki-dir", str(tmp_path)]
        )
        main()

        report_path = os.path.join(str(tmp_path), "wiki", "GRAPH_REPORT.md")
        assert os.path.exists(report_path)

        with open(report_path, encoding="utf-8") as f:
            content = f.read()
        assert "Knowledge Graph Report" in content

    def test_custom_output_dir(self, tmp_path, monkeypatch):
        """--output-dir writes graph.json and GRAPH_REPORT.md to custom directory."""
        make_indication(tmp_path, "obesity", "Obesity")
        out_dir = tmp_path / "custom_output"
        out_dir.mkdir()

        monkeypatch.setattr(
            sys,
            "argv",
            [
                "graphify_wiki.py",
                "--wiki-dir",
                str(tmp_path),
                "--output-dir",
                str(out_dir),
            ],
        )
        main()

        assert os.path.exists(os.path.join(str(out_dir), "graph.json"))
        assert os.path.exists(os.path.join(str(out_dir), "GRAPH_REPORT.md"))


# ---------------------------------------------------------------------------
# TestWriteGraphJson
# ---------------------------------------------------------------------------

class TestWriteGraphJson:
    def test_valid_node_link_format(self, tmp_path):
        """write_graph_json produces valid node-link JSON loadable by networkx."""
        G = nx.Graph()
        G.add_node("obesity", type="indication", title="Obesity", slug="obesity")
        G.add_node("novo-nordisk", type="company", title="Novo Nordisk", slug="novo-nordisk")
        G.add_edge("obesity", "novo-nordisk", weight=95.0)

        out_path = os.path.join(str(tmp_path), "wiki", "graph.json")
        write_graph_json(G, out_path)

        assert os.path.exists(out_path)
        with open(out_path, encoding="utf-8") as f:
            data = json.load(f)

        G2 = nx.node_link_graph(data)
        assert G2.number_of_nodes() == 2
        assert G2.has_edge("obesity", "novo-nordisk")
