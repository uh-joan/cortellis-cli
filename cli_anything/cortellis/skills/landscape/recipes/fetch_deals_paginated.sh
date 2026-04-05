#!/bin/bash
# Fetch deals with pagination (50/page, up to 200 deals).
# Sorted by newest first.
#
# Usage: ./fetch_deals_paginated.sh "<search_args>" <output_csv> <pipeline_recipes_dir>
# Example: ./fetch_deals_paginated.sh '--indication "alzheimer"' deals.csv ./pipeline/recipes
#
# The first argument is passed directly to `cortellis deals search`.
# Outputs deals.meta.json alongside the CSV with totalResults.

SEARCH_ARGS="$1"
OUTPUT="$2"
PIPELINE_RECIPES="$3"
MAX_PAGES=4
HITS=50

# Write header
echo "title,id,principal,partner,type,date" > "$OUTPUT"

OFFSET=0
TOTAL=999
PAGE=0

while [ $OFFSET -lt $TOTAL ]; do
    # Rate limit: wait between pages (skip first)
    if [ $PAGE -gt 0 ]; then
        sleep 1
    fi

    RESULT=$(eval cortellis --json deals search $SEARCH_ARGS --hits $HITS --offset $OFFSET --sort-by '"-dealDateStart"' 2>/dev/null)

    # Extract totalResults
    TOTAL=$(echo "$RESULT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('dealResultsOutput',{}).get('@totalResults','0'))" 2>/dev/null)

    # Convert to CSV and append (skip header from deals_to_csv.py)
    echo "$RESULT" | python3 "$PIPELINE_RECIPES/deals_to_csv.py" | tail -n +2 >> "$OUTPUT"

    OFFSET=$((OFFSET + HITS))
    PAGE=$((PAGE + 1))

    # Safety: max pages
    if [ $PAGE -ge $MAX_PAGES ]; then
        break
    fi
done

COUNT=$(($(wc -l < "$OUTPUT") - 1))

# Write metadata
DIR=$(dirname "$OUTPUT")
echo "{\"totalResults\": \"$TOTAL\", \"fetched\": $COUNT}" > "$DIR/deals.meta.json"

echo "$COUNT deals fetched (of $TOTAL total)" >&2
