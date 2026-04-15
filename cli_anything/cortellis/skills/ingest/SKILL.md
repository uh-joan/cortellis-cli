# /ingest — Internal Document Ingestion

Reads a document (markdown or text file), extracts mentions of known wiki entities, and writes a `wiki/internal/<slug>.md` article with wikilinks. Internal documents become first-class wiki nodes that surface in `/signals` and `/insights` alongside Cortellis data.

---

## When to use

- You have a deal memo, expert call note, or prior assessment you want to connect to the wiki
- You want internal analysis to surface in future `/signals` runs alongside pipeline data
- You need to track what internal documents reference which drugs, companies, or indications

---

## Workflow

```bash
# Step 1: Extract entities from the document
ENTITIES=$(python3 cli_anything/cortellis/skills/ingest/recipes/extract_entities.py <file>)

# Step 2: Compile to wiki/internal/<slug>.md with wikilinks
python3 cli_anything/cortellis/skills/ingest/recipes/compile_internal.py \
  "<document title>" \
  "$(cat <file>)" \
  --source-file "<original filename>" \
  --entities "$ENTITIES"
```

---

## Supported file types

- `.md` — Markdown (preferred)
- `.txt` — Plain text
- `.markdown`, `.rst` — Other text formats

PDF and PPTX are not yet supported. Convert to markdown first with Pandoc:
```bash
pandoc deal_memo.pdf -o deal_memo.md
```

---

## Entity matching

`extract_entities.py` scans the wiki `INDEX.md` for known entity names (drugs, companies, targets, indications, conferences). It matches names case-insensitively with whole-word boundaries. Longer names take precedence over shorter ones to avoid partial matches.

- Matched entities appear in frontmatter as `entities: [slug-1, slug-2, ...]`
- The first mention of each entity in the body is replaced with `[[slug|Name]]` wikilink
- Entity detection works entirely offline — no API calls required

---

## Output

```
wiki/internal/<slug>.md
```

```yaml
---
title: <document title>
type: internal
slug: <slug>
ingested_at: <iso>
source_file: <original filename>
entities:
  - novo-nordisk
  - tirzepatide
  - obesity
---
```

Body text with wikilinks:
```
[[novo-nordisk|Novo Nordisk]] has achieved dominant market position in [[obesity|Obesity]]...
```

---

## Example

```bash
python3 cli_anything/cortellis/skills/ingest/recipes/extract_entities.py raw/internal/deal_memo.md

ENTITIES=$(python3 cli_anything/cortellis/skills/ingest/recipes/extract_entities.py raw/internal/deal_memo.md 2>/dev/null)
python3 cli_anything/cortellis/skills/ingest/recipes/compile_internal.py \
  "Deal Memo: Novo Nordisk Q1 2026" \
  "$(cat raw/internal/deal_memo.md)" \
  --source-file "deal_memo.md" \
  --entities "$ENTITIES"

# Result: wiki/internal/deal-memo-novo-nordisk-q1-2026.md
# with wikilinks to all mentioned drugs, companies, indications
```
