"""graph_utils.py — Shared graph refresh utility.

Rebuilds graph.json from all wiki articles after each skill compile step.
"""

import os


def refresh_graph(base_dir: str) -> None:
    """Rebuild wiki/graph.json from all wiki articles using NetworkX.

    Called at the end of each skill's compile step so the graph stays current
    after drug-profile, pipeline, target-profile, and conference-intel runs.
    """
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
