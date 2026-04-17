"""graph_utils.py — Shared graph refresh utility.

Rebuilds graph.json from all wiki articles. Silent no-op if networkx is not installed.
"""

import os


def refresh_graph(base_dir: str) -> None:
    """Rebuild wiki/graph.json from all wiki articles using NetworkX.

    Called at the end of each skill's compile step so the graph stays current
    after drug-profile, pipeline, and target-profile runs — not only after landscape.

    Silent no-op when networkx is not installed (optional [graph] extra).
    """
    try:
        import networkx as nx  # noqa: F401
    except ImportError:
        return

    from cli_anything.cortellis.skills.landscape.recipes.graphify_wiki import (
        build_graph_from_wiki,
        write_graph_json,
    )
    from cli_anything.cortellis.utils.wiki import wiki_root

    w_dir = wiki_root(base_dir)
    if not os.path.isdir(w_dir):
        return

    G = build_graph_from_wiki(w_dir)
    write_graph_json(G, os.path.join(w_dir, "graph.json"))
