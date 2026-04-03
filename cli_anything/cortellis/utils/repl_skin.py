"""
Interactive REPL skin for Cortellis CLI using prompt_toolkit.

The REPL accepts the same sub-commands as the Click CLI (without the program
name prefix), e.g.::

    cortellis> drugs search --phase L --hits 5
    cortellis> companies get 12345
    cortellis> --json drugs search --phase L

Type ``exit``, ``quit``, or press Ctrl-D / Ctrl-C to leave the REPL.

Usage (called from cortellis_cli.py)::

    from cli_anything.cortellis.utils.repl_skin import run_repl

    run_repl(cli_group, ctx)
"""
from __future__ import annotations

import shlex
from typing import TYPE_CHECKING

import click
from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import FileHistory, InMemoryHistory
from prompt_toolkit.styles import Style

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_repl(cli: click.Group, ctx: click.Context, banner: str = None) -> None:
    """Start an interactive REPL session.

    Parameters
    ----------
    cli:
        The root Click group (e.g. the ``cortellis`` group).
    ctx:
        The Click context from the caller.  Its ``obj`` dict is forwarded to
        every command executed inside the REPL so that ``--json`` and
        credential state are preserved.
    banner:
        Optional ASCII art banner string to display on startup.  If provided,
        it is printed before the interactive mode hint.  Typically passed from
        cortellis_cli._BANNER to avoid circular imports.
    """
    _print_banner(banner)

    session: PromptSession = _make_session(cli)

    while True:
        try:
            raw = session.prompt("cortellis> ")
        except KeyboardInterrupt:
            # Ctrl-C — clear line, keep running
            continue
        except EOFError:
            # Ctrl-D — exit
            click.echo("\nGoodbye.")
            break

        line = raw.strip()
        if not line:
            continue
        if line.lower() in {"exit", "quit", "q", ":q"}:
            click.echo("Goodbye.")
            break

        _dispatch(cli, ctx, line)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_PROMPT_STYLE = Style.from_dict(
    {
        "prompt": "bold #00aaff",
    }
)


def _print_banner(banner: str = None) -> None:
    if banner:
        click.echo(banner)

    # Auto-detect SKILL.md path for agent discoverability
    from pathlib import Path
    skills_dir = Path(__file__).resolve().parent.parent / "skills"
    skill_files = sorted(skills_dir.glob("*/SKILL.md")) if skills_dir.is_dir() else []

    click.echo(
        "  Interactive mode  —  type a command (e.g. drugs search --phase L)\n"
        "  Commands: drugs  companies  deals  trials  regulations  ontology\n"
        "            analytics  literature  press-releases  conferences  ner\n"
    )
    if skill_files:
        click.echo("  Skills:")
        for sf in skill_files:
            click.echo(f"    \u25c7 {sf}")
        click.echo()
    click.echo("  Type 'exit' or press Ctrl-D to quit.\n")


_HISTORY_FILE = "~/.cortellis_cli_history"


def _make_session(cli: click.Group) -> PromptSession:
    """Build a PromptSession with file history and basic tab-completion."""
    import os

    top_level_commands = list(cli.commands.keys()) if hasattr(cli, "commands") else []
    # Add common flags and exit words so they show up in completion
    words = top_level_commands + ["--json", "--help", "exit", "quit"]

    completer = WordCompleter(words, ignore_case=True, sentence=True)

    history_path = os.path.expanduser(_HISTORY_FILE)
    try:
        history = FileHistory(history_path)
    except Exception:
        # Fall back to in-memory if file is not writable
        history = InMemoryHistory()

    return PromptSession(
        history=history,
        auto_suggest=AutoSuggestFromHistory(),
        completer=completer,
        style=_PROMPT_STYLE,
        complete_while_typing=False,
    )


def _dispatch(cli: click.Group, parent_ctx: click.Context, line: str) -> None:
    """Parse and invoke a REPL line against the Click group."""
    try:
        args = shlex.split(line)
    except ValueError as exc:
        click.echo(f"Parse error: {exc}", err=True)
        return

    try:
        # standalone_mode=False so Click doesn't call sys.exit on --help or errors
        cli.main(
            args=args,
            prog_name="cortellis",
            standalone_mode=False,
            obj=parent_ctx.obj,
        )
    except click.exceptions.Exit:
        pass
    except click.exceptions.Abort:
        pass
    except click.UsageError as exc:
        click.echo(f"Usage error: {exc}", err=True)
    except click.ClickException as exc:
        exc.show()
    except SystemExit:
        # Some Click internals raise SystemExit even with standalone_mode=False
        pass
    except Exception as exc:  # noqa: BLE001
        click.echo(f"Error: {exc}", err=True)
