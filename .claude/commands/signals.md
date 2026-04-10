Run the Cortellis strategic signals report by executing:

```
.venv/bin/python3 cli_anything/cortellis/skills/landscape/recipes/signals_report.py
```

This scans all compiled indication articles in wiki/indications/, compares current metadata against previous_snapshot, and ranks competitive shifts by severity (HIGH/MEDIUM/LOW). Writes output to wiki/SIGNALS_REPORT.md.

Print the report contents to the user after running.

Usage: /signals

Arguments: $ARGUMENTS
