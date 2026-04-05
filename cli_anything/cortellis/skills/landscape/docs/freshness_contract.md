# Freshness Contract — `/landscape` Data Staleness Warnings

## Purpose

Cortellis is a lagging snapshot: data is pulled once, stored under `raw/`, and consumed by every downstream scoring script. BD decisions, however, are forward bets placed on the state of competition today — not at the moment data was last fetched. Reviewer 3 of the LLM council audit (2026-04-05) identified this gap: every silent rerun rewrites history without surfacing to the reader how old the underlying data is.

The freshness contract closes that gap. It ensures every `/landscape` output carries a user-visible staleness signal when warranted, and writes a machine-readable `freshness.json` that tooling and reviewers can inspect.

## Thresholds

| Level | Default | Env var override |
|-------|---------|-----------------|
| Warn | 30 days | `LANDSCAPE_FRESHNESS_WARN_DAYS` |
| Hard | 90 days | `LANDSCAPE_FRESHNESS_HARD_DAYS` |

Age is measured as the mtime of the oldest `*.meta.json` file in the landscape_dir. Meta files are written by the fetch pipeline; their mtime is the proxy for when data was last pulled from Cortellis.

On fresh data (oldest meta < 30 days) nothing is printed — no noise on healthy runs.

## Placement

The warning appears immediately after the orientation blockquote ("Reading this output: CPI...") and before the first `##` section of every report. Read order: title → data-as-of line → orientation blockquote → **freshness warning (if stale)** → first content section.

Scripts with an orientation blockquote (all except `opportunity_matrix.py`) insert the warning there. `opportunity_matrix.py` has no blockquote; the warning appears at the top of the markdown output before the heatmap table.

When data is fresh the function returns an empty string and nothing is printed.

## Schema (freshness/v1)

| Field | Type | Description |
|-------|------|-------------|
| `schema_version` | string | Always `"freshness/v1"` |
| `landscape_dir` | string | Path to the landscape data directory |
| `computed_at_utc` | string | ISO 8601 UTC timestamp of this computation |
| `oldest_meta_age_days` | int or null | Age in days of the oldest `*.meta.json` |
| `newest_meta_age_days` | int or null | Age in days of the newest `*.meta.json` |
| `warn_threshold_days` | int | Warn threshold used (default 30) |
| `hard_threshold_days` | int | Hard threshold used (default 90) |
| `staleness_level` | string | `"ok"`, `"warn"`, `"hard"`, or `"unknown"` |
| `sources` | object | Per-file dict with `mtime_utc` and `age_days` |
| `history_note` | string | Present only when severity was elevated by the rerun rule |
| `error` | string | Present only when computation partially or fully failed |

The file is written as `<landscape_dir>/freshness.json`, a sibling to `audit_trail.json`.

## The "No Silent History Rewrite" Rule

Every rerun of a scoring script on the same landscape_dir reads the previous `freshness.json` if it exists. If the new `oldest_meta_age_days` is at least one day greater than the previous value, it means the user ran scoring again without fetching fresh data — the data is aging under them.

In that case, the staleness level is elevated one step: `ok` becomes `warn`, `warn` becomes `hard`. A `history_note` field is added to `freshness.json` explaining the elevation. If the new oldest age is equal to or less than the previous value (meaning a fresh pull happened), the file is overwritten normally with no elevation.

This prevents a common failure mode: a user fetches data once, runs scoring repeatedly over weeks, and the output silently becomes stale without any signal.

## Relationship to Audit Trail

The audit trail (T5, `docs/governance/audit_trail_spec.md`) is an HTML comment at the **bottom** of every output file, hidden from rendered markdown. Its audience is tooling, reviewers, and automated pipelines checking provenance.

The freshness warning (T6, this document) is a visible blockquote at the **top** of every output file, rendered in every markdown viewer. Its audience is human readers — BD analysts, executives, and reviewers — who need to know whether the data is current before citing the output externally.

Two layers, two audiences, one contract.

## What This Does NOT Do

- Does not fetch fresh data. That is the user's responsibility (run the fetch pipeline steps).
- Does not block scoring on stale data. Scoring always completes; the warning is advisory.
- Does not track Cortellis API version drift or schema changes between pulls.
- Does not sign timestamps cryptographically. Mtime is a best-effort proxy, not a tamper-proof record.
