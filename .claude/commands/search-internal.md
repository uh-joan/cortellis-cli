Search wiki/internal/ articles for documents that discuss a topic or keyword.

Run:

```
.venv/bin/python3 cli_anything/cortellis/skills/ingest-internal/recipes/search_internal.py $ARGUMENTS
```

Pass the user's search query as `$ARGUMENTS`. Examples:
- `/search-internal GLP-1 market share`
- `/search-internal physician prescribing preference`
- `/search-internal reimbursement coverage`

Print the results directly. If no results, say so and suggest `/ingest-internal` to add more documents.

Usage: /search-internal <query terms>

Arguments: $ARGUMENTS
