# /commercial-intel — Commercial Intelligence Extraction

Reads a Clarivate (or similar) market research document, extracts structured commercial data, shows the proposed sections to the user for review, then merges approved sections into the corresponding indication wiki article.

This is a Claude-powered extraction skill — Claude reads the document and produces structured markdown tables. No external API calls.

---

## When to use

- You have a market research document (current treatment, epidemiology, forecast, access/reimbursement, unmet need) for a specific indication
- You want to enrich a wiki indication article with commercial intelligence alongside Cortellis pipeline data

---

## Usage

```
/commercial-intel <file_path> <indication_slug>
```

Examples:
```
/commercial-intel raw/internal/obesity/Obesity_Overweight-CurrentTreatment-Overview.pdf obesity
/commercial-intel raw/internal/obesity/Clarivate_Disease-Landscape-and-Forecast_Obesity_Executive-Summary_November-2025_0.pptx obesity
/commercial-intel raw/internal/obesity/Obesity_Overweight-Epidemiology-Overview.pdf obesity
```

---

## Workflow

### Step 1: Detect document type

Infer the document type from filename and content:
- `CurrentTreatment` / `Physician-Insights` → `current_treatment`
- `Epidemiology` → `epidemiology`
- `Landscape-and-Forecast` / `Forecast` → `forecast`
- `Access` / `Reimbursement` → `access_reimbursement`
- `UnmetNeed` → `unmet_need`
- `Executive-Summary` → may contain multiple types — extract all that apply

### Step 2: Extract text from document

```python
# Use extract_text_from_file from extract_entities.py
python3 cli_anything/cortellis/skills/ingest/recipes/extract_entities.py <file_path>
```

Or read directly:
```python
from cli_anything.cortellis.skills.ingest.recipes.extract_entities import extract_text_from_file
text = extract_text_from_file(file_path)
```

**Supported formats:** `.pdf` (pdftotext), `.pptx` (python-pptx text frames), `.xlsx`/`.xlsm` (openpyxl),
`.csv` (UTF-8-sig, handles Excel BOM), `.md`/`.txt`

**Note on PPTX chart data:** python-pptx only extracts text frames. Chart values (bar/pie chart percentages)
are locked in image objects and not extractable. Executive summary text usually contains key figures in prose.
Prefer CSV exports (from Excel dashboards) over PPTX/XLSM when available — they give direct numerical access.

### Step 3: Extract structured sections (Claude-powered)

Read the extracted text and produce structured markdown tables. Apply the schema for the detected document type:

#### `current_treatment` schema
```markdown
## Current Treatment — <Indication> (<Source>, <Date>)

### Physician Prescribing Preference
| Brand (INN) | 1st Line Share | 2nd Line Share | Key Driver |
|---|---|---|---|
| ... | ...% | ...% | ... |

### Prescribing Trends
| Period | Trend | Notable Shift |
|---|---|---|
| ... | ... | ... |

### Market Dynamics
- <Key insight 1>
- <Key insight 2>

> Source: <filename> | Extracted: <date>
```

#### `epidemiology` schema
```markdown
## Epidemiology — <Indication> (<Source>, <Date>)

### Prevalent Cases
| Country | Year | Total (M) | Drug-Treated (M) | Treatment Rate |
|---|---|---|---|---|
| ... | ... | ... | ... | ...% |

### Population Trend
| Year | Global Prevalent (M) | YoY Change |
|---|---|---|
| ... | ... | ...% |

> Source: <filename> | Extracted: <date>
```

#### `forecast` schema
```markdown
## Market Forecast — <Indication> (<Source>, <Date>)

### Revenue Forecast by Drug Class
| Drug Class | 2024 ($B) | 2027 ($B) | 2030 ($B) | 2034 ($B) | CAGR |
|---|---|---|---|---|---|
| ... | ... | ... | ... | ... | ...% |

### Key Forecast Assumptions
- <Assumption 1>
- <Assumption 2>

> Source: <filename> | Extracted: <date>
```

#### `access_reimbursement` schema
```markdown
## Access & Reimbursement — <Indication> (<Source>, <Date>)

### Coverage by Country
| Country | Coverage | Restrictions | Key Payer |
|---|---|---|---|
| ... | Broad/Limited/None | ... | ... |

### Reimbursement Trends
- <Key insight>

> Source: <filename> | Extracted: <date>
```

#### `unmet_need` schema
```markdown
## Unmet Need — <Indication> (<Source>, <Date>)

### Key Gaps
| Need Area | Current Status | Gap Level |
|---|---|---|
| ... | ... | High/Medium/Low |

### Patient Perspective
- <Key insight>

> Source: <filename> | Extracted: <date>
```

**Extraction rules:**
- Only include data that is explicitly stated in the document — do NOT infer or extrapolate
- If a number is not in the document, use `-` not a guess
- Preserve exact percentages and figures from the source
- If a table cannot be constructed (insufficient data), write a brief prose summary instead
- Flag any data that seems inconsistent or surprising with a `⚠️` note

### Step 4: Show proposed sections to user

Display the extracted sections clearly with a header:

```
─────────────────────────────────────────
PROPOSED COMMERCIAL SECTIONS
Target article: wiki/indications/<slug>.md
─────────────────────────────────────────

[extracted markdown sections]

─────────────────────────────────────────
Approve to merge into wiki/indications/<slug>.md? (yes / edit / skip)
```

### Step 5: Merge into indication article (on approval)

```bash
python3 cli_anything/cortellis/skills/commercial-intel/recipes/append_commercial_section.py \
  wiki/indications/<slug>.md \
  "<extracted_markdown>"
```

The recipe appends the commercial section before `## Data Sources` (or at end if no such marker).
Updates `wiki/INDEX.md` to reflect the enrichment.

---

## Data quality rules

- **Never hallucinate numbers.** If a figure is not in the source text, do not include it.
- **Cite the source.** Every section ends with `> Source: <filename> | Extracted: <date>`.
- **Flag conflicts.** If extracted data conflicts with what is already in the indication article, note it explicitly rather than silently overwriting.
- **Preserve provenance.** The source filename is stored in the section footer so the original document is always traceable.

---

## Output

The indication article (`wiki/indications/<slug>.md`) gains one or more `## Commercial Intelligence` subsections. These appear after the pipeline data (phases, companies, SWOT) and before `## Data Sources`.

The `wiki/internal/<slug>.md` archive entry remains as a raw extraction record — it is not the query surface.
