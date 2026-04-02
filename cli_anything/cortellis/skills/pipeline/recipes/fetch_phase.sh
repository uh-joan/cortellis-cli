#!/bin/bash
# Fetch all drugs for a company+phase with automatic pagination.
# Handles the 50-hit limit by fetching multiple pages.
# Includes rate limit protection (1s delay between pages).
#
# Usage: ./fetch_phase.sh <company_id> <phase_code> <output_csv> <recipes_dir>
# Example: ./fetch_phase.sh 18614 L /tmp/pipeline/launched.csv ./recipes

CID="$1"
PHASE="$2"
OUTPUT="$3"
RECIPES="$4"
HEADER="name,id,phase,indication,mechanism,company,source"

echo "$HEADER" > "$OUTPUT"

OFFSET=0
HITS=50
TOTAL=999
PAGE=0

while [ $OFFSET -lt $TOTAL ]; do
    # Rate limit: wait between pages (skip first page)
    if [ $PAGE -gt 0 ]; then
        sleep 1
    fi

    RESULT=$(cortellis --json drugs search --company "$CID" --phase "$PHASE" --hits $HITS --offset $OFFSET 2>/dev/null)

    # Check for rate limit (match only structured error messages, not drug content)
    if echo "$RESULT" | head -5 | grep -qi "rate limit\|too many requests"; then
        echo "Rate limited — waiting 10s..." >&2
        sleep 10
        continue
    fi

    # Extract totalResults
    TOTAL=$(echo "$RESULT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('drugResultsOutput',{}).get('@totalResults','0'))" 2>/dev/null)

    # Convert to CSV and append
    echo "$RESULT" | python3 "$RECIPES/ci_drugs_to_csv.py" >> "$OUTPUT"

    OFFSET=$((OFFSET + HITS))
    PAGE=$((PAGE + 1))

    # Safety: max 3 pages (150 drugs per phase)
    if [ $PAGE -ge 3 ]; then
        break
    fi
done

COUNT=$(($(wc -l < "$OUTPUT") - 1))
echo "$COUNT" >&2
