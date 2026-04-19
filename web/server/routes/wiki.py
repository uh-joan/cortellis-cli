import os
import re
import subprocess
import threading
from pathlib import Path

import yaml
from fastapi import APIRouter, HTTPException

from web.server.jobs import create_job, finish_job, get_job

_WIKILINK_RE = re.compile(r"\[\[([^\]|\\]+?)(?:[|\\][^\]]+?)?\]\]")

router = APIRouter()

_ALLOWED_TYPES = {"indications", "companies", "drugs", "targets", "root", "internal", "conferences", "sessions"}
_TYPE_SINGULAR = {"indications": "indication", "companies": "company", "drugs": "drug", "targets": "target"}


def _parse_frontmatter(content: str) -> dict:
    if not content.startswith("---"):
        return {}
    end = content.find("\n---", 4)
    if end == -1:
        return {}
    try:
        return yaml.safe_load(content[4:end]) or {}
    except Exception:
        return {}


@router.get("/wiki")
def list_wiki(workspace_path: str):
    wiki_dir = os.path.join(workspace_path, "wiki")
    if not os.path.isdir(wiki_dir):
        return []

    articles = []
    for article_type in ("indications", "companies", "drugs", "targets"):
        type_dir = os.path.join(wiki_dir, article_type)
        if not os.path.isdir(type_dir):
            continue
        for fname in sorted(os.listdir(type_dir)):
            if fname.endswith(".md"):
                slug = fname[:-3]
                path = os.path.join(type_dir, fname)
                try:
                    meta = _parse_frontmatter(Path(path).read_text(encoding="utf-8"))
                    title = meta.get("title") or slug.replace("-", " ").title()
                except Exception:
                    title = slug.replace("-", " ").title()
                articles.append({"type": article_type, "slug": slug, "title": title})

    # root: wiki/INDEX.md
    index_path = os.path.join(wiki_dir, "INDEX.md")
    if os.path.isfile(index_path):
        articles.append({"type": "root", "slug": "INDEX", "title": "Index"})

    # internal, conferences, sessions
    flat_dirs = {
        "internal": os.path.join(wiki_dir, "internal"),
        "conferences": os.path.join(wiki_dir, "conferences"),
        "sessions": os.path.join(wiki_dir, "insights", "sessions"),
    }
    for article_type, type_dir in flat_dirs.items():
        if not os.path.isdir(type_dir):
            continue
        for fname in sorted(os.listdir(type_dir)):
            if not fname.endswith(".md"):
                continue
            slug = fname[:-3]
            path = os.path.join(type_dir, fname)
            try:
                meta = _parse_frontmatter(Path(path).read_text(encoding="utf-8"))
                title = meta.get("title") or slug.replace("-", " ").title()
            except Exception:
                title = slug.replace("-", " ").title()
            articles.append({"type": article_type, "slug": slug, "title": title})

    return articles


@router.get("/wiki/graph")
def get_wiki_graph(workspace_path: str):
    """Return nodes + links for the wiki knowledge graph."""
    wiki_dir = os.path.join(workspace_path, "wiki")
    if not os.path.isdir(wiki_dir):
        return {"nodes": [], "links": []}

    nodes = {}
    body_links = {}  # slug -> set of target slugs from wikilinks in body

    # Pass 1: collect all nodes and extract body wikilinks
    for article_type in ("indications", "companies", "drugs", "targets"):
        type_dir = os.path.join(wiki_dir, article_type)
        if not os.path.isdir(type_dir):
            continue
        singular = _TYPE_SINGULAR[article_type]
        for fname in os.listdir(type_dir):
            if not fname.endswith(".md"):
                continue
            slug = fname[:-3]
            try:
                content = Path(os.path.join(type_dir, fname)).read_text(encoding="utf-8")
                meta = _parse_frontmatter(content)
                title = meta.get("title") or slug.replace("-", " ").title()
                nodes[slug] = {"id": slug, "type": singular, "slug": slug, "title": title}
                # Strip frontmatter, extract all [[slug|...]] wikilinks from body
                end = content.find("\n---", 4) if content.startswith("---") else -1
                body = content[end + 4:] if end != -1 else content
                body_links[slug] = set(_WIKILINK_RE.findall(body))
            except Exception:
                continue

    # Pass 2: build deduplicated edge list from body wikilinks
    link_set = set()
    links = []
    for source_slug, targets in body_links.items():
        for target_slug in targets:
            target_slug = target_slug.strip()
            if target_slug not in nodes or target_slug == source_slug:
                continue
            pair = tuple(sorted([source_slug, target_slug]))
            if pair not in link_set:
                link_set.add(pair)
                links.append({"source": source_slug, "target": target_slug})

    return {"nodes": list(nodes.values()), "links": links}


@router.get("/wiki/jobs/{job_id}")
def get_wiki_job(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job


@router.post("/wiki/refresh")
def wiki_refresh(workspace_path: str):
    job_id = create_job()

    def _run():
        proc = subprocess.run(
            ["cortellis", "wiki", "refresh"],
            capture_output=True, text=True, cwd=workspace_path,
        )
        finish_job(job_id, proc.returncode, proc.stdout + proc.stderr)

    threading.Thread(target=_run, daemon=True).start()
    return {"job_id": job_id}


@router.post("/wiki/{slug}/changelog")
def run_changelog(slug: str, workspace_path: str):
    md_path = Path(workspace_path) / "wiki" / "indications" / f"{slug}.md"
    raw_dir = Path(workspace_path) / "raw" / slug
    if not md_path.exists():
        return {"prereq_missing": True, "message": "Run /landscape first to generate data for this indication."}
    if not raw_dir.is_dir() or not (raw_dir / "historical_snapshots.csv").exists():
        return {"prereq_missing": True, "message": f"No historical data for '{slug}'. Run /landscape {slug} first."}

    import sys
    job_id = create_job()
    script = str(Path(__file__).resolve().parents[3] / "cli_anything" / "cortellis" / "skills" / "changelog" / "recipes" / "extract_changes.py")

    def _run():
        proc = subprocess.run(
            [sys.executable, script, str(md_path), str(raw_dir), slug],
            capture_output=True, text=True, cwd=workspace_path,
        )
        finish_job(job_id, proc.returncode, proc.stdout + proc.stderr)

    threading.Thread(target=_run, daemon=True).start()
    return {"job_id": job_id, "prereq_missing": False}


@router.get("/wiki/{article_type}/{slug}")
def get_wiki_article(article_type: str, slug: str, workspace_path: str):
    if article_type not in _ALLOWED_TYPES:
        raise HTTPException(400, "Invalid article type")
    if ".." in slug or "/" in slug:
        raise HTTPException(400, "Invalid slug")

    wiki_dir = os.path.join(workspace_path, "wiki")

    # Resolve path for new flat types
    if article_type == "root":
        path = os.path.join(wiki_dir, "INDEX.md")
    elif article_type == "internal":
        path = os.path.join(wiki_dir, "internal", f"{slug}.md")
    elif article_type == "conferences":
        path = os.path.join(wiki_dir, "conferences", f"{slug}.md")
    elif article_type == "sessions":
        path = os.path.join(wiki_dir, "insights", "sessions", f"{slug}.md")
    else:
        path = os.path.join(wiki_dir, article_type, f"{slug}.md")

    if not os.path.exists(path):
        raise HTTPException(404, "Article not found")

    content = Path(path).read_text(encoding="utf-8")

    # New flat types: no related links needed
    if article_type in ("root", "internal", "conferences", "sessions"):
        return {"type": article_type, "slug": slug, "content": content, "related": []}

    meta = _parse_frontmatter(content)

    # Build related list: from 'related' (indication) or 'indications' keys (company)
    related = []
    if article_type == "indications":
        related = [{"slug": s, "type": "companies"} for s in meta.get("related", [])[:12]]
    elif article_type == "companies":
        related = [{"slug": s, "type": "indications"} for s in list(meta.get("indications", {}).keys())[:8]]

    return {"type": article_type, "slug": slug, "content": content, "related": related}
