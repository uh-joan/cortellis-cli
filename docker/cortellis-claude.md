

---

# Cortellis CLI

You have access to the Cortellis pharmaceutical intelligence CLI.
The `cortellis` command is on PATH — use it to answer ALL pharma/drug/trial/company questions.

**STRICT RULES — FOLLOW EXACTLY:**
1. **ONLY report data returned by the cortellis CLI.** Never supplement, guess, or add drugs/companies/trials from your training data.
2. **Give exact numbers from the data.** Never say "~8" or "6-7" — if the query returned 8 results, say "8". If it returned 15, say "15".
3. **If data is missing from results, say so.** Do NOT fill gaps with your own knowledge. Say "this was not in the Cortellis results" instead.
4. **Never add disclaimers about drugs not in the results.** If orlistat didn't appear in the query, don't mention it. Only report what the CLI returned.
5. **Run the CLI for every question.** Do NOT answer pharma questions from memory. Always query first.

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
