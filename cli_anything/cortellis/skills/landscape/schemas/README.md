# Landscape Output Schema

`landscape_output.schema.json` is a JSON Schema (draft-07) contract for all files
produced by `recipes/strategic_scoring.py`. Downstream skills that consume landscape
output should validate against these definitions before processing.

## Files covered

| File | Schema definition | Description |
|------|-------------------|-------------|
| `strategic_scores.csv` | `#/definitions/strategic_scores_row` | Per-company CPI scores and position |
| `mechanism_scores.csv` | `#/definitions/mechanism_scores_row` | Per-mechanism crowding analysis |
| `opportunity_matrix.csv` | `#/definitions/opportunity_matrix_row` | Mechanism opportunity scoring |
| `deals.meta.json` | `#/definitions/deals_meta` | Deal fetch metadata |
| `<phase>.meta.json` | `#/definitions/phase_meta` | Per-phase drug fetch metadata |

## Key column notes

### strategic_scores.csv

- `cpi_tier` — bucket A/B/C/D (A=>=75, B=>=50, C=>=25, D=<25) based on raw `cpi_score`
- `cpi_score` — weighted float 0-100; weights vary by therapeutic area preset
- `position` — Leader (top 20%), Challenger (next 30%), Emerging (rest)

### mechanism_scores.csv

- `crowding_index` = `active_count * company_count`; use to rank competitive intensity

### opportunity_matrix.csv

- `opportunity_score` is inverted from crowding — higher means less competition

## Therapeutic area presets

Weights applied to CPI dimensions are controlled by preset JSON files in
`config/presets/`. The active preset is printed in the markdown report header.
Pass the preset name as the second CLI argument:

```bash
python3 recipes/strategic_scoring.py raw/obesity/ oncology
```

Available presets: `default`, `oncology`, `rare_disease`, `neuro`, `metabolic`.
