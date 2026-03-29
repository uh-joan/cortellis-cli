

---

# Cortellis CLI

You have access to the Cortellis pharmaceutical intelligence CLI.
The `cortellis` command is on PATH — use it to answer ALL pharma/drug/trial/company questions.

**CRITICAL: ALWAYS use the cortellis CLI to answer questions about drugs, companies, deals, trials, regulatory, etc. Do NOT answer from training data. Run the CLI and use real Cortellis data.**

## How to use

```bash
cortellis --json drugs search --phase L --indication 238 --hits 10
```

Always use `--json` flag for parseable output.

## Important

- Indication, company, and country filters use numeric IDs
- Look up IDs first: `cortellis ontology search --term "obesity" --category indication`
- Action fields use text names: `--action "glucagon"`
- Phase codes: L (Launched), C3 (Phase 3), C2 (Phase 2), C1 (Phase 1), DR (Discovery), DX (Discontinued)

## Available command groups

drugs, companies, deals, trials, regulations, conferences, literature, press-releases,
ontology, analytics, ner, targets, company-analytics, deals-intelligence, drug-design

Run `cortellis <group> --help` for full options.
