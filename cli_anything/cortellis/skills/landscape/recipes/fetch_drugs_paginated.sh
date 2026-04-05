#!/bin/bash
# Fetch all drugs with automatic pagination for ANY search parameter.
# Replaces fetch_indication_phase.sh with a generic version.
#
# Usage: ./fetch_drugs_paginated.sh <phase_code> <output_csv> <pipeline_recipes_dir> [--phase-highest] [search_params...]
# Example:
#   ./fetch_drugs_paginated.sh L /tmp/launched.csv ../pipeline/recipes --indication 238
#   ./fetch_drugs_paginated.sh C3 /tmp/phase3.csv ../pipeline/recipes --phase-highest --technology 1164
#   ./fetch_drugs_paginated.sh L /tmp/launched.csv ../pipeline/recipes --action "GLP-1 receptor agonist"
#   ./fetch_drugs_paginated.sh DR /tmp/discovery.csv ../pipeline/recipes --phase-highest --technology 1164 --indication 88

PHASE="$1"
OUTPUT="$2"
PIPELINE_RECIPES="$3"
shift 3

# Check for --phase-highest flag
USE_PHASE_HIGHEST=false
REMAINING=()
for arg in "$@"; do
    if [ "$arg" = "--phase-highest" ]; then
        USE_PHASE_HIGHEST=true
    else
        REMAINING+=("$arg")
    fi
done
SEARCH_PARAMS=("${REMAINING[@]}")
HEADER="name,id,phase,indication,mechanism,company,source"

# Auto-detect venv if cortellis not on PATH
if ! command -v cortellis >/dev/null 2>&1; then
    SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
    VENV_BIN="$(cd "$SCRIPT_DIR/../../../../.." && pwd)/.venv/bin"
    if [ -x "$VENV_BIN/cortellis" ]; then
        export PATH="$VENV_BIN:$PATH"
    else
        echo "ERROR: cortellis not found on PATH or in .venv" >&2
        exit 1
    fi
fi

echo "$HEADER" > "$OUTPUT"

OFFSET=0
HITS=50
TOTAL=999
PAGE=0
METADATA_FILE="${OUTPUT%.csv}.meta.json"

while [ $OFFSET -lt $TOTAL ]; do
    # Rate limit: wait between pages (3s for safety with parallel workers)
    if [ $PAGE -gt 0 ]; then
        sleep 3
    fi

    if [ "$USE_PHASE_HIGHEST" = true ]; then
        RESULT=$(cortellis --json drugs search "${SEARCH_PARAMS[@]}" --phase "$PHASE" --phase-highest --hits $HITS --offset $OFFSET 2>/dev/null)
    else
        RESULT=$(cortellis --json drugs search "${SEARCH_PARAMS[@]}" --phase "$PHASE" --hits $HITS --offset $OFFSET 2>/dev/null)
    fi

    # Guard: empty result means command failed
    if [ -z "$RESULT" ]; then
        echo "ERROR: empty response from cortellis (page $PAGE)" >&2
        break
    fi

    # Check for rate limit (match only structured error messages, not drug content)
    if echo "$RESULT" | head -5 | grep -qi "rate limit\|too many requests"; then
        echo "Rate limited — waiting 10s..." >&2
        sleep 10
        continue
    fi

    # Extract totalResults
    TOTAL=$(echo "$RESULT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('drugResultsOutput',{}).get('@totalResults','0'))" 2>/dev/null)

    # Convert to CSV
    echo "$RESULT" | python3 "$PIPELINE_RECIPES/ci_drugs_to_csv.py" >> "$OUTPUT"

    OFFSET=$((OFFSET + HITS))
    PAGE=$((PAGE + 1))

    # Safety: max 200 pages (10000 drugs) — prevents infinite loops
    if [ $PAGE -ge 200 ]; then
        echo "WARN: hit safety limit at $((PAGE * HITS)) drugs" >&2
        break
    fi
done

COUNT=$(($(wc -l < "$OUTPUT") - 1))

# Save metadata for report generator (totalResults vs fetched)
echo "{\"phase\": \"$PHASE\", \"totalResults\": $TOTAL, \"fetched\": $COUNT}" > "$METADATA_FILE"

echo "$COUNT" >&2
