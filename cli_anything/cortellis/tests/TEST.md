# Testing Guide

## Overview

Tests are split into two suites:

| Suite | File | Requires credentials | Hits real API |
|-------|------|----------------------|---------------|
| Unit tests | `test_core.py` | No | No (HTTP mocked) |
| E2E tests | `test_e2e.py` | Yes | Yes |

**88 tests pass** across the full suite (unit + E2E).

## Running Unit Tests

No credentials or network access required. HTTP calls are intercepted by the `responses` library.

```bash
# From the project root:
pytest tests/test_core.py

# With verbose output:
pytest -v tests/test_core.py

# Run a specific test:
pytest tests/test_core.py::test_build_drug_query_with_linked
```

## Running E2E Tests

E2E tests call the live Cortellis API. Set credentials before running:

```bash
CORTELLIS_USERNAME=your_username CORTELLIS_PASSWORD=your_password pytest tests/test_e2e.py
```

Or with a `.env` file in the project root:

```bash
pytest tests/test_e2e.py
```

E2E tests are automatically skipped when `CORTELLIS_USERNAME` is not set:

```bash
pytest tests/test_e2e.py  # skips all tests if no credentials
```

## What's Tested

### Unit Tests (`test_core.py`)

- **`query_builder`**: `build_drug_query`, `build_company_query`, `build_deals_query`, `build_trials_query`, `build_regulatory_query` — verifies correct LINKED(), RANGE(), and AND combinations
- **`client`**: `CortellisClient.get()` — verifies Digest auth is applied, correct URLs are constructed, HTTP errors are raised
- **Domain modules** (`drugs`, `companies`, `deals`, `trials`, `regulatory`): verifies `search()` and `get()` pass correct params to the client

HTTP responses are mocked using the `responses` library — no network calls are made.

### E2E Tests (`test_e2e.py`)

- Live API calls for each domain: `drugs search`, `companies search`, `deals search`, `trials search`, `regulations search`
- Verifies response shape (top-level keys present, non-empty results for common queries)
- Tests `get()` by ID using known stable Cortellis record IDs
- Also covers the newer domains: `company-analytics`, `deals-intelligence`, `drug-design`, and `targets`

## Test Dependencies

```bash
pip install -e ".[dev]"
```

Dev dependencies: `pytest>=7.0`, `pytest-mock>=3.0`, `responses>=0.23`

## What's Mocked vs Real

| Concern | Unit tests | E2E tests |
|---------|-----------|-----------|
| HTTP calls | Mocked via `responses` library | Real HTTPS to `api.cortellis.com` |
| Digest auth | Verified headers present | Real Digest auth handshake |
| Query building | Asserted on exact strings | Used as-is |
| Response parsing | Fixture JSON | Live API JSON |
| Credentials | Not needed | `CORTELLIS_USERNAME` / `CORTELLIS_PASSWORD` |
