#!/usr/bin/env python3
"""
ingest_internal.py — Ingest a raw file into wiki/internal/<slug>.md.

Extracts text, entity-links against the wiki index, compiles a wiki/internal
article, and prints a JSON summary for the calling skill to use.

Usage:
    python3 ingest_internal.py <file_path> [--title TITLE] [--wiki-dir DIR]

Output (stdout): JSON with slug, wiki_path, entities, doc_type_hint
"""

import json
import os
import re
import sys

# Allow running as standalone script
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))

from cli_anything.cortellis.skills.ingest.recipes.extract_entities import (
    extract_text_from_file,
    load_wiki_entities,
    scan_text,
    cortellis_ner_entities,
)
from cli_anything.cortellis.skills.ingest.recipes.compile_internal import (
    compile_internal_article,
)
from cli_anything.cortellis.utils.wiki import (
    wiki_root,
    write_article,
    update_index,
    log_activity,
)


# ---------------------------------------------------------------------------
# Doc type detection
# ---------------------------------------------------------------------------

_DOC_TYPE_PATTERNS = [
    (r"CurrentTreatment|Current.Treatment|Physician.Insight", "current_treatment"),
    (r"Epidemiology|Epi.Dashboard|Epi.Overview", "epidemiology"),
    (r"Landscape.and.Forecast|Landscape.*Forecast|Forecast.*Dashboard|Forecast.Data", "forecast"),
    (r"Access|Reimbursement", "access_reimbursement"),
    (r"UnmetNeed|Unmet.Need", "unmet_need"),
    (r"Executive.Summary", "executive_summary"),
    (r"Patient.Share", "forecast"),
    (r"Price.Per.Treated", "forecast"),
    (r"Sales", "forecast"),
]


def detect_doc_type(filename: str) -> str:
    """Infer document type from filename. Returns one of the schema keys or 'unknown'."""
    for pattern, doc_type in _DOC_TYPE_PATTERNS:
        if re.search(pattern, filename, re.IGNORECASE):
            return doc_type
    return "unknown"


def title_from_filename(filename: str) -> str:
    """Derive a human-readable title from the filename."""
    base = os.path.splitext(os.path.basename(filename))[0]
    # Replace underscores, hyphens, and camelCase boundaries with spaces
    base = re.sub(r"[-_]+", " ", base)
    base = re.sub(r"([a-z])([A-Z])", r"\1 \2", base)
    # Collapse multiple spaces
    base = re.sub(r"\s+", " ", base).strip()
    return base.title()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Ingest a raw file into wiki/internal/")
    parser.add_argument("file_path", help="Path to the file to ingest")
    parser.add_argument("--indication", help="Indication slug (e.g. obesity) — triggers synonym fetch if not yet done")
    parser.add_argument("--source-file", help="Original filename for slug/frontmatter (use when file_path is a tmp path)")
    parser.add_argument("--title", help="Override auto-detected title")
    parser.add_argument("--wiki-dir", default=None, help="Wiki root directory (defaults to CWD)")
    args = parser.parse_args()

    file_path = args.file_path
    if not os.path.exists(file_path):
        print(json.dumps({"error": f"File not found: {file_path}"}))
        sys.exit(1)

    wiki_dir = args.wiki_dir or wiki_root(os.getcwd())
    source_file_name = args.source_file or os.path.basename(file_path)
    title = args.title or title_from_filename(source_file_name)
    doc_type = detect_doc_type(source_file_name)
    base_dir = os.path.dirname(wiki_dir) if os.path.basename(wiki_dir) == "wiki" else os.getcwd()

    # Step 0: Fetch synonyms for the indication (if raw dir exists and synonyms not yet fetched)
    if args.indication:
        ind_raw_dir = os.path.join(base_dir, "raw", args.indication)
        synonyms_path = os.path.join(ind_raw_dir, "synonyms.json")
        if os.path.isdir(ind_raw_dir) and not os.path.exists(synonyms_path):
            try:
                from cli_anything.cortellis.skills.landscape.recipes.fetch_synonyms import fetch_and_save
                ind_name = args.indication.replace("-", " ").title()
                fetch_and_save(ind_raw_dir, ind_name, "indication")
                print(f"[synonyms] Fetched for {ind_name}", file=sys.stderr)
            except Exception as e:
                print(f"[synonyms] Skipped ({e.__class__.__name__})", file=sys.stderr)

    # Step 1: Extract text
    try:
        text = extract_text_from_file(file_path)
    except Exception as e:
        print(json.dumps({"error": f"Text extraction failed: {e}"}))
        sys.exit(1)

    if not text.strip():
        print(json.dumps({"error": "Extracted text is empty"}))
        sys.exit(1)

    # Step 2: Entity extraction (NER with wiki-index fallback)
    base_dir = os.path.dirname(wiki_dir) if os.path.basename(wiki_dir) == "wiki" else os.getcwd()
    entities = cortellis_ner_entities(text, base_dir)
    if not entities:
        wiki_entities = load_wiki_entities(base_dir)
        entities = scan_text(text, wiki_entities)

    # Step 3: Compile and write wiki/internal article
    slug, meta, body = compile_internal_article(
        title=title,
        body_text=text,
        source_file=source_file_name,
        entities=entities,
    )

    out_path = os.path.join(wiki_dir, "internal", f"{slug}.md")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    write_article(out_path, meta, body)

    # Step 4: Update INDEX.md (reload all entries so the new article is picked up)
    try:
        from cli_anything.cortellis.utils.wiki import load_index_entries
        entries = load_index_entries(wiki_dir)
        update_index(wiki_dir, entries)
    except Exception:
        pass  # INDEX update is best-effort

    log_activity(wiki_dir, "ingest-internal", f"{title} → {slug}")

    # Step 5: Archive original file to raw/internal/<slug>.<ext>
    import shutil as _shutil
    from datetime import datetime, timezone
    raw_internal_dir = os.path.join(base_dir, "raw", "internal")
    os.makedirs(raw_internal_dir, exist_ok=True)
    src_ext = os.path.splitext(file_path)[1]
    archive_path = os.path.join(raw_internal_dir, f"{slug}{src_ext}")

    # Step 5a: Delta — if a previous version exists AND content differs, compute and log changes
    def _md5(path):
        import hashlib
        h = hashlib.md5()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    if os.path.exists(archive_path) and _md5(archive_path) != _md5(file_path):
        try:
            import importlib.util as _ilu
            _spec = _ilu.spec_from_file_location(
                "compute_delta",
                os.path.join(os.path.dirname(__file__), "compute_delta.py"),
            )
            _mod = _ilu.module_from_spec(_spec)
            _spec.loader.exec_module(_mod)
            compute_delta = _mod.compute_delta
            format_changelog_entry = _mod.format_changelog_entry
            from cli_anything.cortellis.skills.ingest.recipes.extract_entities import (
                extract_text_from_file as _etf,
            )
            old_text = _etf(archive_path)
            # Read previous entity list from existing wiki article frontmatter
            old_wiki_path = os.path.join(wiki_dir, "internal", f"{slug}.md")
            old_entity_slugs: list[str] = []
            if os.path.exists(old_wiki_path):
                import re as _re
                _fm = open(old_wiki_path).read()
                _m = _re.search(r"^entities:\s*\n((?:  - .+\n)*)", _fm, _re.MULTILINE)
                if _m:
                    old_entity_slugs = _re.findall(r"  - (.+)", _m.group(1))
            new_entity_slugs = [e["slug"] for e in entities]
            delta = compute_delta(
                old_path=archive_path,
                new_path=file_path,
                old_text=old_text,
                new_text=text,
                old_entity_slugs=old_entity_slugs,
                new_entity_slugs=new_entity_slugs,
            )
            ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            entry = format_changelog_entry(delta, ts)
            changelog_path = os.path.join(wiki_dir, "internal", f"{slug}-changelog.md")
            if not os.path.exists(changelog_path):
                header = f"---\ntitle: {title} Changelog\ntype: internal-changelog\nslug: {slug}-changelog\n---\n\n"
                open(changelog_path, "w").write(header)
            with open(changelog_path, "a") as _f:
                _f.write(entry + "\n")
            print(f"[delta] Changelog updated: {changelog_path}", file=sys.stderr)
        except Exception as _e:
            print(f"[delta] Skipped ({_e.__class__.__name__}: {_e})", file=sys.stderr)

    try:
        _shutil.copy2(file_path, archive_path)
    except Exception as e:
        print(f"[archive] Could not copy source file: {e}", file=sys.stderr)
        archive_path = None

    # Output JSON summary for the calling skill
    result = {
        "slug": slug,
        "wiki_path": out_path,
        "archive_path": archive_path,
        "title": title,
        "doc_type": doc_type,
        "entities": [e["slug"] for e in entities],
        "text_chars": len(text),
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
