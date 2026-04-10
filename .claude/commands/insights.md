Run the Cortellis accumulated insights report by executing:

```
.venv/bin/python3 cli_anything/cortellis/skills/landscape/recipes/insights_report.py
```

This scans wiki/insights/sessions/ for analysis sessions from the last 30 days and writes a summary to wiki/INSIGHTS_REPORT.md.

Optional flags:
- `--days N` — look back N days instead of 30
- `--indication <slug>` — filter to a specific indication

Print the report contents to the user after running. Do not invoke any OMC or Claude usage analytics skill.

Usage: /insights [--days N] [--indication slug]

Arguments: $ARGUMENTS
