import sys
import json as _json

import requests

from cli_anything.cortellis.cortellis_cli import cli


def main():
    try:
        cli()
    except requests.exceptions.HTTPError as exc:
        resp = exc.response
        status = resp.status_code if resp is not None else "?"
        body = resp.text[:300] if resp is not None else ""
        msg = f"API error {status}: {body}"
        sys.stderr.write(f"Error: {msg}\n")
        sys.exit(1)
    except requests.exceptions.ConnectionError as exc:
        sys.stderr.write(f"Error: Could not connect to Cortellis API: {exc}\n")
        sys.exit(1)
    except requests.exceptions.RequestException as exc:
        sys.stderr.write(f"Error: Request failed: {exc}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
