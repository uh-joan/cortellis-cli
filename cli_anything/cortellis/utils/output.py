"""
Dual JSON/human output formatting for Cortellis CLI.

Usage:
    from cli_anything.cortellis.utils.output import print_output

    print_output(ctx, data)  # respects ctx.obj["json"] flag
"""
from __future__ import annotations

import json
import sys
from typing import Any

import click
from rich.console import Console
from rich.table import Table
from rich import box


_console = Console()
_err_console = Console(stderr=True)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def print_output(ctx: click.Context, data: Any) -> None:
    """Print `data` as JSON or a human-readable Rich table/text.

    The ctx.obj dict must contain a boolean key ``"json"`` that is set by
    the root Click group callback.
    """
    as_json: bool = (ctx.obj or {}).get("json", False)
    if as_json:
        _print_json(data)
    else:
        _print_human(data)


def print_error(message: str, as_json: bool = False) -> None:
    """Print an error message and exit 1."""
    if as_json:
        click.echo(json.dumps({"error": message}), err=True)
    else:
        _err_console.print(f"[bold red]Error:[/bold red] {message}")
    sys.exit(1)


# ---------------------------------------------------------------------------
# JSON mode
# ---------------------------------------------------------------------------

def _print_json(data: Any) -> None:
    click.echo(json.dumps(data, indent=2, default=str))


# ---------------------------------------------------------------------------
# Human-readable mode
# ---------------------------------------------------------------------------

def _print_human(data: Any) -> None:
    if data is None:
        _console.print("[dim]No data.[/dim]")
        return

    if isinstance(data, dict):
        _render_dict(data)
    elif isinstance(data, list):
        _render_list(data)
    else:
        _console.print(str(data))


def _render_list(items: list) -> None:
    """Render a list of dicts as a Rich table, or fall back to bullets."""
    if not items:
        _console.print("[dim]No results.[/dim]")
        return

    if all(isinstance(item, dict) for item in items):
        _render_table(items)
    else:
        for item in items:
            _console.print(f"  [cyan]•[/cyan] {item}")


def _render_table(records: list[dict]) -> None:
    """Build a Rich table from a list of dicts.

    Uses the first record to determine columns.  Long text values are
    truncated to keep the table readable in a terminal.
    """
    if not records:
        return

    # Determine columns — prefer a curated order if common keys are present
    all_keys: list[str] = _ordered_keys(records)

    table = Table(box=box.SIMPLE_HEAVY, show_header=True, header_style="bold cyan")
    for key in all_keys:
        table.add_column(_humanize(key), overflow="fold", max_width=60)

    for record in records:
        row = [_cell_value(record.get(key)) for key in all_keys]
        table.add_row(*row)

    _console.print(table)
    _console.print(f"[dim]{len(records)} result(s)[/dim]")


def _render_dict(record: dict) -> None:
    """Render a single dict as a two-column key/value table."""
    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    table.add_column("Key", style="bold cyan", no_wrap=True)
    table.add_column("Value", overflow="fold")

    for key, value in record.items():
        table.add_row(_humanize(key), _cell_value(value))

    _console.print(table)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Keys that should appear first (if present) for common Cortellis entities
_PRIORITY_KEYS = [
    "drugId", "companyId", "dealId", "trialId", "regulationId",
    "conferenceId", "literatureId", "pressReleaseId",
    "id",
    "drugName", "companyName", "dealName", "trialName", "name", "title",
    "phase", "status", "country", "date", "startDate", "endDate",
]


def _ordered_keys(records: list[dict]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []

    # Priority keys first
    for key in _PRIORITY_KEYS:
        for record in records:
            if key in record and key not in seen:
                seen.add(key)
                ordered.append(key)
                break

    # Remaining keys in insertion order from the first record
    for key in records[0]:
        if key not in seen:
            seen.add(key)
            ordered.append(key)

    # Keys that only appear in later records
    for record in records[1:]:
        for key in record:
            if key not in seen:
                seen.add(key)
                ordered.append(key)

    return ordered


def _humanize(key: str) -> str:
    """Convert camelCase / snake_case key to Title Words."""
    import re
    # camelCase → words
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", key)
    s = re.sub(r"([a-z\d])([A-Z])", r"\1 \2", s)
    # snake_case → words
    s = s.replace("_", " ")
    return s.title()


# ---------------------------------------------------------------------------
# Alternative API (format_* style) — thin wrappers over the internals above
# ---------------------------------------------------------------------------

def format_output(data: Any, json_mode: bool = False, title: str = None) -> None:
    """Entry point matching the format_output(data, json_mode, title) spec.

    Prints to stdout.  Use this when you don't have a Click context.
    """
    if json_mode:
        _print_json(data)
    else:
        if title:
            from rich.panel import Panel
            _console.print(Panel(str(title), style="bold cyan"))
        _print_human(data)


def format_search_results(data: Any, json_mode: bool = False) -> None:
    """Format API search results (list or dict with hits list)."""
    if json_mode:
        _print_json(data)
        return
    # Unwrap common Cortellis envelope: {"hits": [...], "totalCount": N}
    if isinstance(data, dict) and "hits" in data:
        items = data["hits"]
        total = data.get("totalCount")
        _print_human(items)
        if total is not None:
            _console.print(f"[dim]Total matching: {total}[/dim]")
    else:
        _print_human(data)


def format_detail(data: Any, json_mode: bool = False) -> None:
    """Format a single detail record as a key-value panel."""
    if json_mode:
        _print_json(data)
    else:
        _print_human(data)


def format_list(items: list, json_mode: bool = False, columns: list = None) -> None:
    """Format a list with optional column selection."""
    if json_mode:
        _print_json(items)
        return
    if not items:
        _console.print("[dim]No results.[/dim]")
        return
    if columns and all(isinstance(i, dict) for i in items):
        filtered = [{k: i.get(k) for k in columns} for i in items]
        _render_table(filtered)
    else:
        _print_human(items)


def _cell_value(value: Any, max_len: int = 80) -> str:
    """Convert an arbitrary value to a display string."""
    if value is None:
        return ""
    if isinstance(value, list):
        if not value:
            return ""
        # Render list of scalars as comma-separated, list of dicts as count
        if isinstance(value[0], dict):
            return f"[{len(value)} items]"
        parts = [str(v) for v in value[:5]]
        suffix = f", +{len(value) - 5} more" if len(value) > 5 else ""
        return ", ".join(parts) + suffix
    if isinstance(value, dict):
        return f"{{…{len(value)} keys}}"
    text = str(value)
    if len(text) > max_len:
        return text[: max_len - 1] + "…"
    return text
