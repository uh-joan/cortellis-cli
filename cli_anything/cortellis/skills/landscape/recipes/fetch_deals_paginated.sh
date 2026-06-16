#!/bin/bash
# Fetch deals with pagination (50/page), last 2 years only, up to 1000 deals.
# Sorted by newest first. Date filtering is done client-side since the API
# does not support date range queries on dealDateStart.
#
# Usage: ./fetch_deals_paginated.sh "<search_args>" <output_csv> <pipeline_recipes_dir>
# Example: ./fetch_deals_paginated.sh '--indication "alzheimer"' deals.csv ./pipeline/recipes
#
# The first argument is passed directly to `cortellis deals search`.
# Outputs deals.meta.json alongside the CSV with totalResults.

SEARCH_ARGS="$1"
OUTPUT="$2"
PIPELINE_RECIPES="$3"
MAX_PAGES=20
HITS=50
DATE_FROM=$(python3 -c "from datetime import date; d=date.today(); print(d.replace(year=d.year-2).isoformat())")

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

    # Convert to CSV, filter to last 2 years, append (skip header)
    PAGE_ROWS=$(echo "$RESULT" | python3 "$PIPELINE_RECIPES/deals_to_csv.py" | tail -n +2)
    FILTERED=$(echo "$PAGE_ROWS" | python3 -c "
import sys, csv
date_from = '$DATE_FROM'
reader = csv.reader(sys.stdin)
writer = csv.writer(sys.stdout)
count = 0
for row in reader:
    if row and row[-1][:10] >= date_from:
        writer.writerow(row)
        count += 1
sys.stderr.write(str(count) + '\n')
" 2>/dev/null)

    if [ -n "$FILTERED" ]; then
        echo "$FILTERED" >> "$OUTPUT"
    else
        # All deals on this page are older than cutoff — stop early
        break
    fi

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
echo "{\"totalResults\": \"$TOTAL\", \"fetched\": $COUNT, \"date_from\": \"$DATE_FROM\"}" > "$DIR/deals.meta.json"

echo "$COUNT deals fetched (of $TOTAL total, from $DATE_FROM)" >&2
