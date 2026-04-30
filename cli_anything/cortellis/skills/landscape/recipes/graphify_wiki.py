#!/usr/bin/env python3
"""
graphify_wiki.py — Build knowledge graph from compiled wiki articles.

Constructs a NetworkX graph from wiki article frontmatter metadata,
runs community detection, and produces graph.json + GRAPH_REPORT.md.

Usage: python3 graphify_wiki.py [--wiki-dir DIR] [--output-dir DIR]

Dependencies: networkx (required), graspologic (optional, for Leiden clustering)
"""

import json
import os
import sys

# Allow running as standalone script
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))

try:
    import networkx as nx
    _NX_AVAILABLE = True
except ImportError:
    _NX_AVAILABLE = False

try:
    from graspologic.partition import leiden
    _LEIDEN_AVAILABLE = True
except ImportError:
    _LEIDEN_AVAILABLE = False

from cli_anything.cortellis.utils.wiki import list_articles, wiki_root, log_activity


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def build_graph_from_wiki(wiki_dir: str) -> "nx.Graph":
    """Parse all wiki articles and build a NetworkX graph.

    Nodes: Each article becomes a node (type=indication/company/drug/target)
    Node attributes: title, type, slug, + type-specific (cpi_score, phase, etc.)

    Edges derived from:
    - indication.company_rankings → indication↔company edges (weight=cpi_score)
    - indication.related → indication↔company edges
    - company.indications → company↔indication edges (bidirectional verification)
    - drug.originator → drug↔company edge
    - drug.indications → drug↔indication edges
    - target.related → target↔drug/company edges
    """
    G = nx.Graph()

    articles = list_articles(wiki_dir)

    # --- Pass 1: add all nodes ---
    for art in articles:
        meta = art["meta"]
        if not meta:
            continue
        slug = meta.get("slug", "")
        if not slug:
            continue
        atype = meta.get("type", "")
        title = meta.get("title", slug)

        node_attrs = {
            "title": title,
            "type": atype,
            "slug": slug,
        }

        # Type-specific attributes
        if atype == "indication":
            node_attrs["total_drugs"] = meta.get("total_drugs", 0)
            node_attrs["phase_counts"] = meta.get("phase_counts", {})
            node_attrs["top_company"] = meta.get("top_company", "")
        elif atype == "company":
            node_attrs["best_cpi"] = meta.get("best_cpi", "")
        elif atype == "drug":
            node_attrs["phase"] = meta.get("phase", "")
            node_attrs["originator"] = meta.get("originator", "")
        elif atype == "target":
            node_attrs["gene_symbol"] = meta.get("gene_symbol", "")

        G.add_node(slug, **node_attrs)

    # Build a set of known slugs for edge validation
    known_slugs = set(G.nodes())

    # --- Pass 2: add edges ---
    for art in articles:
        meta = art["meta"]
        if not meta:
            continue
        slug = meta.get("slug", "")
        if not slug or slug not in known_slugs:
            continue
        atype = meta.get("type", "")

        if atype == "indication":
            # indication.company_rankings → indication↔company edges (weight=cpi_score)
            for ranking in meta.get("company_rankings", []):
                company_name = ranking.get("company", "")
                cpi_score = ranking.get("cpi_score", 1.0)
                # Try to find matching company node by title
                company_slug = _find_company_slug(G, company_name)
                if company_slug and company_slug in known_slugs:
                    if G.has_edge(slug, company_slug):
                        # Keep highest weight
                        if cpi_score > G[slug][company_slug].get("weight", 0):
                            G[slug][company_slug]["weight"] = cpi_score
                    else:
                        G.add_edge(slug, company_slug, weight=cpi_score, source="company_rankings")

            # indication.related → indication↔entity edges
            for related_slug in meta.get("related", []):
                if related_slug != slug and related_slug in known_slugs and not G.has_edge(slug, related_slug):
                    G.add_edge(slug, related_slug, weight=1.0, source="related")

        elif atype == "company":
            # company.indications → company↔indication edges
            indications_dict = meta.get("indications", {})
            for ind_slug, ind_data in indications_dict.items():
                if ind_slug in known_slugs:
                    cpi_score = float(ind_data.get("cpi_score", 1.0)) if isinstance(ind_data, dict) else 1.0
                    if G.has_edge(slug, ind_slug):
                        if cpi_score > G[slug][ind_slug].get("weight", 0):
                            G[slug][ind_slug]["weight"] = cpi_score
                    else:
                        G.add_edge(slug, ind_slug, weight=cpi_score, source="company_indications")

            # company.related → additional edges
            for related_slug in meta.get("related", []):
                if related_slug != slug and related_slug in known_slugs and not G.has_edge(slug, related_slug):
                    G.add_edge(slug, related_slug, weight=1.0, source="related")

        elif atype == "drug":
            # drug.originator → drug↔company edge
            originator = meta.get("originator", "")
            if originator:
                orig_slug = _find_company_slug(G, originator)
                if orig_slug and orig_slug in known_slugs and not G.has_edge(slug, orig_slug):
                    G.add_edge(slug, orig_slug, weight=1.0, source="originator")

            # drug.indications → drug↔indication edges
            for ind_slug in meta.get("indications", []):
                if isinstance(ind_slug, str) and ind_slug in known_slugs:
                    if not G.has_edge(slug, ind_slug):
                        G.add_edge(slug, ind_slug, weight=1.0, source="drug_indications")

        elif atype == "target":
            # target.related → target↔drug/company edges
            for related_slug in meta.get("related", []):
                if related_slug != slug and related_slug in known_slugs and not G.has_edge(slug, related_slug):
                    G.add_edge(slug, related_slug, weight=1.0, source="related")

        elif atype == "conference":
            # conference.related → conference↔drug/company/indication/target edges
            for related_slug in meta.get("related", []):
                if related_slug != slug and related_slug in known_slugs and not G.has_edge(slug, related_slug):
                    G.add_edge(slug, related_slug, weight=1.0, source="related")

        elif atype == "internal":
            # internal.entities → internal↔drug/company/indication/target edges
            for entity_slug in meta.get("entities", []):
                if entity_slug != slug and entity_slug in known_slugs and not G.has_edge(slug, entity_slug):
                    G.add_edge(slug, entity_slug, weight=1.0, source="internal_entities")

    return G


def _find_company_slug(G: "nx.Graph", company_name: str) -> str:
    """Find a node slug whose title matches company_name (case-insensitive)."""
    if not company_name:
        return ""
    name_lower = company_name.lower().strip()
    for node, attrs in G.nodes(data=True):
        if attrs.get("title", "").lower().strip() == name_lower:
            return node
    return ""


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def find_god_nodes(G: "nx.Graph", top_n: int = 10) -> list:
    """Find nodes with highest degree centrality.

    Returns [{node, type, degree, title}] sorted by degree desc.
    """
    if G.number_of_nodes() == 0:
        return []

    degree_map = dict(G.degree())
    sorted_nodes = sorted(degree_map.items(), key=lambda x: x[1], reverse=True)

    result = []
    for node, degree in sorted_nodes[:top_n]:
        attrs = G.nodes[node]
        result.append({
            "node": node,
            "type": attrs.get("type", ""),
            "degree": degree,
            "title": attrs.get("title", node),
        })
    return result


def find_clusters(G: "nx.Graph") -> list:
    """Detect communities using connected components or Leiden if available.

    Try graspologic.partition.leiden first (pip install graspologic).
    Fall back to networkx connected_components if not installed.

    Returns [{cluster_id, nodes: [{node, type, title}], label: str}].
    Label is derived from the most common node type or highest-degree node.
    """
    if G.number_of_nodes() == 0:
        return []

    clusters = []

    if _LEIDEN_AVAILABLE and G.number_of_edges() > 0:
        # Use Leiden algorithm for community detection
        try:
            partition = leiden(G)
            # partition is a dict: {node: community_id}
            community_map: dict = {}
            for node, comm_id in partition.items():
                community_map.setdefault(comm_id, []).append(node)

            for cluster_id, nodes in sorted(community_map.items()):
                node_entries = []
                for node in nodes:
                    attrs = G.nodes[node]
                    node_entries.append({
                        "node": node,
                        "type": attrs.get("type", ""),
                        "title": attrs.get("title", node),
                    })
                label = _cluster_label(G, node_entries)
                clusters.append({
                    "cluster_id": cluster_id,
                    "nodes": node_entries,
                    "label": label,
                })
            return clusters
        except Exception:
            pass  # fall back to connected_components

    # Fallback: connected components
    for cluster_id, component in enumerate(nx.connected_components(G)):
        node_entries = []
        for node in sorted(component):
            attrs = G.nodes[node]
            node_entries.append({
                "node": node,
                "type": attrs.get("type", ""),
                "title": attrs.get("title", node),
            })
        label = _cluster_label(G, node_entries)
        clusters.append({
            "cluster_id": cluster_id,
            "nodes": node_entries,
            "label": label,
        })
    return clusters


def _cluster_label(G: "nx.Graph", node_entries: list) -> str:
    """Derive a human-readable label for a cluster."""
    if not node_entries:
        return "unknown"

    # Find highest-degree node in cluster as label anchor
    max(node_entries, key=lambda e: G.degree(e["node"]))
    # Count types
    type_counts: dict = {}
    for e in node_entries:
        t = e.get("type", "unknown")
        type_counts[t] = type_counts.get(t, 0) + 1
    dominant_type = max(type_counts, key=lambda t: type_counts[t])
    # Collect up to 3 titles for the label
    titles = [e["title"] for e in node_entries[:3]]
    return f"{dominant_type}: {', '.join(titles)}"


def find_bridges(G: "nx.Graph", clusters: list) -> list:
    """Find nodes that connect different clusters (bridge nodes).

    Uses NetworkX articulation points: nodes whose removal increases the number
    of connected components. These are the true structural bridges in the graph.

    Falls back to cluster-membership cross-checking when clusters come from
    Leiden (non-component-based) partitioning.

    Returns [{node, type, title, clusters: [int]}].
    """
    if G.number_of_nodes() == 0:
        return []

    bridges = []

    # Primary: use articulation points (nodes whose removal disconnects the graph)
    if G.number_of_edges() > 0:
        art_points = set(nx.articulation_points(G))
    else:
        art_points = set()

    # Build node→cluster_id mapping for cluster annotation
    node_to_clusters: dict = {}
    for cluster in clusters:
        cid = cluster["cluster_id"]
        for entry in cluster["nodes"]:
            node_to_clusters.setdefault(entry["node"], set()).add(cid)

    if art_points:
        for node in art_points:
            attrs = G.nodes[node]
            # Find which clusters the node's neighbors belong to
            neighbor_clusters: set = set()
            for neighbor in G.neighbors(node):
                for cid in node_to_clusters.get(neighbor, set()):
                    neighbor_clusters.add(cid)
            own_clusters = node_to_clusters.get(node, set())
            all_touched = neighbor_clusters | own_clusters
            bridges.append({
                "node": node,
                "type": attrs.get("type", ""),
                "title": attrs.get("title", node),
                "clusters": sorted(all_touched),
            })
    elif len(clusters) > 1:
        # Leiden partitioning: fall back to cross-cluster neighbor check
        for node in G.nodes():
            neighbor_clusters = set()
            for neighbor in G.neighbors(node):
                for cid in node_to_clusters.get(neighbor, set()):
                    neighbor_clusters.add(cid)
            own_clusters = node_to_clusters.get(node, set())
            all_touched = neighbor_clusters | own_clusters
            if len(all_touched) >= 2:
                attrs = G.nodes[node]
                bridges.append({
                    "node": node,
                    "type": attrs.get("type", ""),
                    "title": attrs.get("title", node),
                    "clusters": sorted(all_touched),
                })

    # Sort by degree descending
    bridges.sort(key=lambda b: -G.degree(b["node"]))
    return bridges


def compute_stats(G: "nx.Graph") -> dict:
    """Basic graph statistics: node_count, edge_count, density, components."""
    node_count = G.number_of_nodes()
    edge_count = G.number_of_edges()
    density = nx.density(G) if node_count > 1 else 0.0
    components = nx.number_connected_components(G) if node_count > 0 else 0

    # Count by type
    type_counts: dict = {}
    for _, attrs in G.nodes(data=True):
        t = attrs.get("type", "unknown")
        type_counts[t] = type_counts.get(t, 0) + 1

    return {
        "node_count": node_count,
        "edge_count": edge_count,
        "density": round(density, 4),
        "components": components,
        "by_type": type_counts,
    }


# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------

def write_graph_json(G: "nx.Graph", output_path: str) -> None:
    """Write NetworkX graph as node-link JSON for later querying."""
    data = nx.node_link_data(G)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def generate_graph_report(
    G: "nx.Graph",
    god_nodes: list,
    clusters: list,
    bridges: list,
    stats: dict,
) -> str:
    """Generate GRAPH_REPORT.md with graph analysis results."""
    by_type = stats.get("by_type", {})
    type_summary_parts = []
    for t in ("indications", "companies", "drugs", "targets"):
        count = by_type.get(t, 0)
        if count:
            type_summary_parts.append(f"{count} {t}")
    # Also include "indication" / "company" etc. (singular forms from frontmatter)
    _plural = {"indication": "indications", "company": "companies", "drug": "drugs", "target": "targets"}
    for t in ("indication", "company", "drug", "target"):
        count = by_type.get(t, 0)
        if count:
            type_summary_parts.append(f"{count} {_plural[t]}")

    type_summary = ", ".join(type_summary_parts) if type_summary_parts else "0 articles"

    lines = [
        "## Knowledge Graph Report\n",
        f"\n> {type_summary} | {stats['node_count']} nodes, {stats['edge_count']} edges\n",
        "\n",
        "### God Nodes (highest connectivity)\n",
        "\n",
    ]

    if god_nodes:
        for i, entry in enumerate(god_nodes, 1):
            lines.append(
                f"{i}. **{entry['title']}** ({entry['type']}) — degree {entry['degree']}\n"
            )
    else:
        lines.append("_No nodes found._\n")

    lines.append("\n### Clusters\n\n")

    if clusters:
        for cluster in clusters:
            node_count = len(cluster["nodes"])
            titles = [e["title"] for e in cluster["nodes"][:5]]
            preview = ", ".join(titles)
            if node_count > 5:
                preview += f", ... (+{node_count - 5} more)"
            lines.append(
                f"{cluster['cluster_id'] + 1}. **Cluster {cluster['cluster_id'] + 1}**"
                f" ({node_count} nodes) — {preview}\n"
            )
    else:
        lines.append("_No clusters found._\n")

    lines.append("\n### Bridge Nodes\n\n")

    if bridges:
        for entry in bridges[:10]:
            cluster_ids = [str(c + 1) for c in entry["clusters"]]
            lines.append(
                f"- **{entry['title']}** ({entry['type']}) — connects Cluster "
                f"{' and Cluster '.join(cluster_ids)}\n"
            )
    else:
        lines.append("_No bridge nodes found (graph may be a single component)._\n")

    lines.append("\n### Network Statistics\n\n")
    lines.append(
        f"- Nodes: {stats['node_count']}"
        f" | Edges: {stats['edge_count']}"
        f" | Density: {stats['density']}"
        f" | Components: {stats['components']}\n"
    )
    if by_type:
        type_breakdown = ", ".join(f"{v} {k}" for k, v in sorted(by_type.items()))
        lines.append(f"- Node types: {type_breakdown}\n")

    return "".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if not _NX_AVAILABLE:
        print(
            "ERROR: networkx is not installed.\n"
            "Install it with: pip install networkx\n"
            "Or: pip install cortellis-cli[graph]",
            file=sys.stderr,
        )
        sys.exit(1)

    # Parse args
    wiki_dir_override = None
    output_dir_override = None
    i = 1
    while i < len(sys.argv):
        if sys.argv[i] == "--wiki-dir" and i + 1 < len(sys.argv):
            wiki_dir_override = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--output-dir" and i + 1 < len(sys.argv):
            output_dir_override = sys.argv[i + 1]
            i += 2
        else:
            i += 1

    base_dir = wiki_dir_override or os.getcwd()
    w_dir = wiki_root(base_dir)
    output_dir = output_dir_override or w_dir

    print(f"Building knowledge graph from {w_dir} ...")

    G = build_graph_from_wiki(w_dir)
    god_nodes = find_god_nodes(G)
    clusters = find_clusters(G)
    bridges = find_bridges(G, clusters)
    stats = compute_stats(G)

    clustering_method = "Leiden" if _LEIDEN_AVAILABLE else "connected_components"
    print(
        f"Graph: {stats['node_count']} nodes, {stats['edge_count']} edges, "
        f"{stats['components']} component(s) | clustering: {clustering_method}"
    )

    # Write graph.json
    graph_json_path = os.path.join(output_dir, "graph.json")
    write_graph_json(G, graph_json_path)
    print(f"Written: {graph_json_path}")

    # Write GRAPH_REPORT.md
    report = generate_graph_report(G, god_nodes, clusters, bridges, stats)
    report_path = os.path.join(output_dir, "GRAPH_REPORT.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"Written: {report_path}")

    log_activity(w_dir, "compile", f"Knowledge graph: {stats['node_count']} nodes, {stats['edge_count']} edges")

    # Print summary
    print(report)


if __name__ == "__main__":
    main()
