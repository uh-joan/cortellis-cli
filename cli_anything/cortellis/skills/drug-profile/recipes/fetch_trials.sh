#!/bin/bash
# Fetch active clinical trials for a drug with pagination.
# Active = Recruiting + Active, not recruiting.
# Merges all pages into a single JSON file for the report generator.
#
# Usage: ./fetch_trials.sh "<drug_name>" <output_json>
# Example: ./fetch_trials.sh "semaglutide" raw/drugs/semaglutide/trials.json

DRUG_NAME="$1"
OUTPUT="$2"
TMPDIR_LOCAL=$(mktemp -d)
trap "rm -rf $TMPDIR_LOCAL" EXIT

HITS=100
ACTUAL_TOTAL=0

for STATUS in "Recruiting" "Active, not recruiting"; do
    OFFSET=0
    TOTAL=999
    PAGE=0

    while [ $OFFSET -lt $TOTAL ]; do
        if [ $PAGE -gt 0 ]; then
            sleep 1
        fi

        RESULT=$(cortellis --json trials search \
            --query "trialInterventionsPrimaryAloneNameDisplay:$DRUG_NAME" \
            --recruitment-status "$STATUS" \
            --hits $HITS --offset $OFFSET \
            --sort-by "-trialDateStart" 2>/dev/null)

        if echo "$RESULT" | grep -qi "rate limit\|too many requests\|retry_error"; then
            echo "Rate limited or error — waiting 10s..." >&2
            sleep 10
            continue
        fi

        TOTAL=$(echo "$RESULT" | python3 -c "
import json,sys
d=json.load(sys.stdin)
print(d.get('trialResultsOutput',{}).get('@totalResults','0'))
" 2>/dev/null)

        ACTUAL_TOTAL=$((ACTUAL_TOTAL + 0))  # accumulate below

        echo "$RESULT" | python3 -c "
import json,sys
d=json.load(sys.stdin)
trials=d.get('trialResultsOutput',{}).get('SearchResults',{}).get('Trial',[])
if isinstance(trials,dict): trials=[trials]
for t in trials:
    print(json.dumps(t))
" 2>/dev/null >> "$TMPDIR_LOCAL/trials.ndjson"

        OFFSET=$((OFFSET + HITS))
        PAGE=$((PAGE + 1))
    done
done

# Merge all trials into final JSON, dedup by trial ID
python3 -c "
import json

trials = []
seen = set()
with open('$TMPDIR_LOCAL/trials.ndjson') as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        t = json.loads(line)
        tid = t.get('@id', t.get('Id', str(len(trials))))
        if tid not in seen:
            seen.add(tid)
            trials.append(t)

out = {
    'trialResultsOutput': {
        '@totalResults': str(len(trials)),
        'SearchResults': {
            'Trial': trials
        }
    }
}
print(json.dumps(out))
" > "$OUTPUT"

COUNT=$(python3 -c "
import json
d=json.load(open('$OUTPUT'))
t=d.get('trialResultsOutput',{}).get('SearchResults',{}).get('Trial',[])
print(len(t))
" 2>/dev/null)
echo "Fetched $COUNT active trials for '$DRUG_NAME'" >&2
