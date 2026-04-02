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

echo "$HEADER" > "$OUTPUT"

OFFSET=0
HITS=50
TOTAL=999
PAGE=0

while [ $OFFSET -lt $TOTAL ]; do
    # Rate limit: wait between pages
    if [ $PAGE -gt 0 ]; then
        sleep 1
    fi

    RESULT=$(cortellis --json drugs search --indication "$IND_ID" --phase "$PHASE" --hits $HITS --offset $OFFSET 2>/dev/null)

    # Check for rate limit
    if echo "$RESULT" | grep -qi "rate limit\|429\|too many"; then
        echo "Rate limited — waiting 5s..." >&2
        sleep 5
        continue
    fi

    # Extract totalResults
    TOTAL=$(echo "$RESULT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('drugResultsOutput',{}).get('@totalResults','0'))" 2>/dev/null)

    # Convert to CSV
    echo "$RESULT" | python3 "$PIPELINE_RECIPES/ci_drugs_to_csv.py" >> "$OUTPUT"

    OFFSET=$((OFFSET + HITS))
    PAGE=$((PAGE + 1))

    # Safety: max 4 pages (200 drugs per phase)
    if [ $PAGE -ge 4 ]; then
        break
    fi
done

COUNT=$(($(wc -l < "$OUTPUT") - 1))
echo "$COUNT" >&2
