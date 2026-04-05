#!/bin/bash
# Fetch all drugs for an indication+phase with automatic pagination.
# Handles the 50-hit limit by fetching multiple pages.
#
# Usage: ./fetch_indication_phase.sh <indication_id> <phase_code> <output_csv> <pipeline_recipes_dir>
# Example: ./fetch_indication_phase.sh 238 L /tmp/landscape/launched.csv ../pipeline/recipes

IND_ID="$1"
PHASE="$2"
OUTPUT="$3"
PIPELINE_RECIPES="$4"
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

    RESULT=$(cortellis --json drugs search --indication "$IND_ID" --phase "$PHASE" --hits $HITS --offset $OFFSET 2>/dev/null)

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
