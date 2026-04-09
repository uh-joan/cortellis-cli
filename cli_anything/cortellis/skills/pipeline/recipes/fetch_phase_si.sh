#!/bin/bash
# Fetch all SI (drug-design) drugs for a company+phase query with pagination.
# Handles the 50-hit limit by fetching multiple pages.
# Includes rate limit protection (1s delay between pages).
#
# Usage: ./fetch_phase_si.sh "<query>" <output_csv> <recipes_dir>
# Example: ./fetch_phase_si.sh \
#   "organizationsOriginator:\"Novo Nordisk\" AND developmentIsActive:Yes AND phaseHighest:\"Phase I\"" \
#   raw/pipeline/novo-nordisk/phase1_si.csv \
#   ./recipes

QUERY="$1"
OUTPUT="$2"
RECIPES="$3"
HEADER="name,id,phase,indication,mechanism,company,source"

echo "$HEADER" > "$OUTPUT"

OFFSET=0
HITS=50
TOTAL=999
PAGE=0

while [ $OFFSET -lt $TOTAL ]; do
    if [ $PAGE -gt 0 ]; then
        sleep 1
    fi

    RESULT=$(cortellis --json drug-design search-drugs --query "$QUERY" --hits $HITS --offset $OFFSET 2>/dev/null)

    if echo "$RESULT" | head -5 | grep -qi "rate limit\|too many requests"; then
        echo "Rate limited — waiting 10s..." >&2
        sleep 10
        continue
    fi

    TOTAL=$(echo "$RESULT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('drugDesignResultsOutput',{}).get('@totalResults','0'))" 2>/dev/null)

    echo "$RESULT" | python3 "$RECIPES/si_drugs_to_csv.py" >> "$OUTPUT"

    OFFSET=$((OFFSET + HITS))
    PAGE=$((PAGE + 1))

    if [ $PAGE -ge 3 ]; then
        break
    fi
done

COUNT=$(($(wc -l < "$OUTPUT") - 1))
echo "$COUNT" >&2
