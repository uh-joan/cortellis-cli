#!/bin/bash
# Fetch ALL drugs for a given mechanism/action with pagination.
# Merges all pages into a single JSON file for the report generator.
#
# Usage: ./fetch_drugs_by_action.sh "<action_name>" <output_json>
# Example: ./fetch_drugs_by_action.sh "Glucagon-like peptide 1 receptor agonist" raw/targets/glp1r/drugs_pipeline.json

ACTION="$1"
OUTPUT="$2"
TMPDIR_LOCAL=$(mktemp -d)
trap "rm -rf $TMPDIR_LOCAL" EXIT

OFFSET=0
HITS=50
TOTAL=999
PAGE=0
ACTUAL_TOTAL=0

while [ $OFFSET -lt $TOTAL ]; do
    if [ $PAGE -gt 0 ]; then
        sleep 1
    fi

    RESULT=$(cortellis --json drugs search --action "$ACTION" --hits $HITS --offset $OFFSET 2>/dev/null)

    if echo "$RESULT" | head -5 | grep -qi "rate limit\|too many requests"; then
        echo "Rate limited — waiting 10s..." >&2
        sleep 10
        continue
    fi

    TOTAL=$(echo "$RESULT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('drugResultsOutput',{}).get('@totalResults','0'))" 2>/dev/null)
    ACTUAL_TOTAL=$TOTAL

    # Extract Drug array from this page, write to numbered file
    echo "$RESULT" | python3 -c "
import json, sys
d = json.load(sys.stdin)
drugs = d.get('drugResultsOutput', {}).get('SearchResults', {}).get('Drug', [])
if isinstance(drugs, dict):
    drugs = [drugs]
for drug in drugs:
    print(json.dumps(drug))
" 2>/dev/null >> "$TMPDIR_LOCAL/drugs.ndjson"

    OFFSET=$((OFFSET + HITS))
    PAGE=$((PAGE + 1))
done

# Merge all drugs into final JSON
python3 -c "
import json, sys

drugs = []
with open('$TMPDIR_LOCAL/drugs.ndjson') as f:
    for line in f:
        line = line.strip()
        if line:
            drugs.append(json.loads(line))

out = {
    'drugResultsOutput': {
        '@totalResults': '$ACTUAL_TOTAL',
        'SearchResults': {
            'Drug': drugs
        }
    }
}
print(json.dumps(out))
" > "$OUTPUT"

COUNT=$(python3 -c "import json; d=json.load(open('$OUTPUT')); drugs=d.get('drugResultsOutput',{}).get('SearchResults',{}).get('Drug',[]); print(len(drugs))" 2>/dev/null)
echo "Fetched $COUNT / $ACTUAL_TOTAL drugs" >&2
