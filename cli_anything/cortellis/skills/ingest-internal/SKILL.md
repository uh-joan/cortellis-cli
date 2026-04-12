# /ingest-internal — Unified Internal Document Ingestion

Drop a raw file from `raw/internal/` into the wiki in one command:
1. Extracts text (PDF, PPTX, CSV, XLSX, MD, TXT)
2. Entity-links against wiki index → `wiki/internal/<slug>.md`
3. Detects document type from filename
4. Extracts structured commercial tables (Claude-powered)
5. Merges into `wiki/indications/<slug>.md` — no approval gate
6. Prints a summary of what was added

---

## Usage

```
/ingest-internal <file_path> <indication_slug>
```

Examples:
```
/ingest-internal raw/internal/obesity/Obesity_Forecast.csv obesity
/ingest-internal raw/internal/masld/Clarivate_MASLD_Epidemiology.pdf masld
/ingest-internal raw/internal/obesity/GLP1_Physician_Insights.pptx obesity
```

---

## Workflow

### Step 1: Run the ingest recipe

```bash
.venv/bin/python3 cli_anything/cortellis/skills/ingest-internal/recipes/ingest_internal.py \
  <file_path> \
  --indication <indication_slug> \
  --wiki-dir wiki
```

`--indication` triggers an automatic synonym fetch for `raw/<indication>/synonyms.json` if not already present, so entity detection includes all ontology synonyms on the first run.

Outputs JSON:
```json
{
  "slug": "clarivate-obesity-forecast-data",
  "wiki_path": "wiki/internal/clarivate-obesity-forecast-data.md",
  "title": "Clarivate Obesity Forecast Data",
  "doc_type": "forecast",
  "entities": ["obesity", "semaglutide", "novo-nordisk"],
  "text_chars": 12400
}
```

### Step 2: Read the extracted text

Read the body of `wiki/internal/<slug>.md` — the text is already there from step 1.
(Skip the frontmatter/wikilinks noise; focus on numerical data and prose.)

### Step 3: Extract commercial sections

Apply the schema for the detected `doc_type`. Use the same schemas as `/commercial-intel`:

- `forecast` → Revenue Forecast by Drug Class table + Key Forecast Assumptions
- `epidemiology` → Prevalent Cases table + Population Trend table
- `current_treatment` → Physician Prescribing Preference + Prescribing Trends + Market Dynamics
- `unmet_need` → Key Gaps table + Patient Perspective
- `access_reimbursement` → Coverage by Country table + Reimbursement Trends
- `executive_summary` → extract all sections that apply

**Extraction rules (same as /commercial-intel):**
- Only include data explicitly stated in the document — do NOT infer or extrapolate
- Use `-` for any missing figures
- Preserve exact percentages and figures
- If a table cannot be constructed (insufficient data), write brief prose instead
- Flag surprising data with `⚠️`

Section format:
```markdown
## <Type> — <Indication> (<Source filename>, <Date>)

[tables / bullets]

> Source: <filename> | Extracted: <today>
```

### Step 4: Merge into indication article

```bash
.venv/bin/python3 cli_anything/cortellis/skills/commercial-intel/recipes/append_commercial_section.py \
  wiki/indications/<indication_slug>.md \
  "<extracted_markdown>"
```

The recipe:
- Inserts before `## Data Sources` (or appends at end)
- Adds `## Commercial Intelligence` anchor on first merge
- Skips silently if the same section header already exists (safe to re-run)

### Step 5: Print summary

```
✓ Ingested:   wiki/internal/<slug>.md  (17 entities linked)
✓ Merged:     wiki/indications/<indication>.md
              Added: ## Market Forecast — Obesity (Clarivate, Nov 2025)
```

If the document had no extractable data (PDF TOC, empty chart slides):
```
✓ Ingested:   wiki/internal/<slug>.md
⚠ No commercial data extracted — document appears to be a product catalog or TOC-only PDF
```

---

## Data quality rules

- **Never hallucinate numbers.** If a figure is not in the source text, omit it.
- **Cite the source.** Every section ends with `> Source: <filename> | Extracted: <date>`.
- **No approval gate.** Merge directly — the user can review `wiki/indications/<slug>.md` afterward.
- **Idempotent.** Re-running on the same file skips the wiki/internal step (slug collision is overwrite) and skips the indication merge (duplicate header detection).

---

## PPTX note

python-pptx only extracts text frames. Chart values (bar/pie percentages) are locked in image objects. For PPTX files, extract what is available in prose/text frames and note chart data is unavailable. Prefer CSV exports when available.
