# LLM Council Transcript — Drug SWOT Skill Completeness
**Date:** April 4, 2026

---

## Chairman Verdict
**Not production-ready today, but one focused day gets it there.** Defects are error handling, truncation policy, and interface honesty — not architectural.

**Blockers:**
1. Bare `except: return None` — silent data loss masks failures
2. Boolean Data Availability (Available/NOT AVAILABLE) — doesn't explain WHY data is missing  
3. `--vs` comparison mode documented but not implemented — silent no-op
4. Truncation: financial 800 chars, consensus 400, safety 300, editorial SWOT 200 chars + 3 items
5. API hits too low (20/15 vs drug-profile's 50/50)
6. Display limits: trials 8, deals 10, competitors 10, biosimilars 8
7. `len(str(d)) < 50` emptiness check is fragile
8. No HTML entity decoding
9. Subprocess invocation may lose synthesis instructions context

**One thing first:** Replace bare `except` with typed exceptions + `_data_status` dict.

---

*LLM Council — 5 advisors, 3 peer reviews, 1 chairman synthesis — April 4, 2026*
