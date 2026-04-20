import logging
import os
import sys
import json as _json


def _auto_venv() -> None:
    """Re-exec with the project-local cortellis if one exists.

    When the global cortellis binary runs inside a cloned project directory
    that has a .venv, transparently switch to the local binary so the correct
    dependencies and wiki path are used — no manual activation required.

    If this looks like a cortellis project but has no .venv yet, print a
    helpful first-run message and exit.
    """
    cwd = os.getcwd()
    local_bin = os.path.join(cwd, ".venv", "bin", "cortellis")
    is_project = os.path.isdir(os.path.join(cwd, "cli_anything", "cortellis"))

    is_setup = "setup" in sys.argv[1:]

    if os.path.isfile(local_bin):
        # Guard against infinite re-exec loop: check the running script, not the interpreter
        if os.path.abspath(sys.argv[0]) != os.path.abspath(local_bin):
            os.execv(local_bin, [local_bin] + sys.argv[1:])
    elif is_project and not is_setup:
        print(
            "No local environment found.\n"
            "Run `cortellis setup` to create the virtual environment and get started.",
            file=sys.stderr,
        )
        sys.exit(1)


_auto_venv()

import click
import requests
from urllib3.exceptions import MaxRetryError

from cli_anything.cortellis.cortellis_cli import cli


def _configure_logging() -> None:
    """Enable debug logging when --debug flag is present."""
    if "--debug" in sys.argv[1:]:
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(name)s %(levelname)s: %(message)s",
            stream=sys.stderr,
        )
    else:
        logging.basicConfig(
            level=logging.WARNING,
            format="%(name)s %(levelname)s: %(message)s",
            stream=sys.stderr,
        )


def _emit_error(message: str, error_type: str, details: dict | None = None) -> None:
    """Print error as structured JSON or plain text, then exit 1."""
    # Detect --json from sys.argv since Click context may not exist yet
    as_json = "--json" in sys.argv[1:]

    if as_json:
        payload = {"error": message, "type": error_type}
        if details:
            payload["details"] = details
        click.echo(_json.dumps(payload), err=True)
    else:
        click.echo(f"Error: {message}", err=True)

    sys.exit(1)


def main():
    _configure_logging()
    try:
        cli()
    except click.exceptions.Exit:
        raise
    except click.exceptions.Abort:
        raise
    except SystemExit:
        raise
    except requests.exceptions.HTTPError as exc:
        resp = exc.response
        status = resp.status_code if resp is not None else "unknown"
        body = resp.text[:300] if resp is not None else ""
        _emit_error(
            message=f"API error {status}: {body}",
            error_type="http_error",
            details={"status_code": status},
        )
    except requests.exceptions.RetryError as exc:
        _emit_error(
            message=f"API request failed after retries: {exc}",
            error_type="retry_error",
        )
    except (requests.exceptions.ConnectionError, MaxRetryError):
        _emit_error(
            message="Could not connect to Cortellis API",
            error_type="connection_error",
        )
    except requests.exceptions.RequestException as exc:
        _emit_error(
            message=f"Request failed: {exc}",
            error_type="request_error",
        )
    except Exception as exc:
        _emit_error(
            message=str(exc),
            error_type=type(exc).__name__,
        )


if __name__ == "__main__":
    main()
