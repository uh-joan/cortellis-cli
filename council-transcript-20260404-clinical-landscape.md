# LLM Council Transcript — Clinical Landscape Skill Completeness
**Date:** April 4, 2026

---

## Original Question
> Is the cli_anything/cortellis/skills/clinical-landscape complete enough? Do we have gaps?

## Framed Question
**Question:** Is the `/clinical-landscape` skill complete enough for production use, or does it have meaningful gaps?

**Context:** Clinical trial landscape skill for a pharma CLI. 1 recipe (`clinical_landscape_report.py`), reuses landscape's `resolve_indication.py`. Workflow: resolve indication, 4 trial searches (Phase 3/2/1 + recruiting at hits=50 each), generate report. Key issues: bare `except`, hardcoded `limit=20` in trial tables, hits=50 cap vs 1542 total, sponsor analysis on sample not population, Python list repr for multi-sponsors, no Data Completeness footer.

**What's at stake:** Clinical trial landscape used by BD teams (competitive intensity), clinical ops (trial environment), and investors (development activity).

---

## Advisor Responses

### 1. The Contrarian
Not production-ready. Header says "1542" but table shows 20 rows — trust-destroying. Sponsor analysis from 50 fetched trials is actively misleading for competitive intelligence. Bare except compounds everything. Same problems landscape and drug-profile had and were fixed. Shipping this repeats a known failure.

### 2. The First Principles Thinker
Three structural problems: (1) Data contract broken — fetches 50 of 1542 without disclosure. (2) Aggregations built on wrong population — "Top Sponsors" from 50 is a different, wrong answer. (3) Silent failure incompatible with decision tools. Built to fetch and format, not to accurately represent.

### 3. The Expansionist
Issues are real but this could be genuinely differentiated. Clinical trial landscape is a high-value workflow teams do manually. The 50-trial cap limits utility. Geographic breakdown and enrollment analysis are major missing signals. Data Completeness footer builds trust. Build this right and it becomes a daily-use tool.

### 4. The Outsider
Third skill with same anti-patterns — that's a process problem. Need a SKILL_TEMPLATE.md. Two independent truncation points (hits=50, limit=20). Python list repr in sponsors signals output never reviewed by non-developer.

### 5. The Executor
Fix order: (1) header/table gap, (2) sponsor methodology, (3) Data Completeness footer, (4) bare except, (5) multi-sponsor formatting, (6) indication ID. Items 1-3 are blockers.

---

## Peer Reviews

### Review 1
**Strongest:** First Principles — precise diagnosis. **Weakest:** First Principles — no path forward. **All missed:** Sort order/relevance — the 50 trials may not be the most relevant.

### Review 2
**Strongest:** Outsider — systemic cause. **Weakest:** Outsider — no immediate fix. **All missed:** Trust lifecycle — one bad inference contaminates trust in all skills.

### Review 3
**Strongest:** Executor — ranked fix list with blockers. **Weakest:** Executor — items 1-2 share root cause (pagination). **All missed:** Testing requirements — no validation strategy.

---

## Chairman Synthesis

### Where the Council Agrees
Not production-ready. Header/content mismatch (1542 vs 20 rows), sponsor analysis on 3% of population, bare except hiding failures. Same anti-patterns as landscape and drug-profile (both already fixed).

### Where the Council Clashes
Pagination vs transparency (fetch all vs label as sample). Fix scope (punch list vs systemic template). Both valid on different timescales.

### Blind Spots the Council Caught
(1) Sort order — 50 trials may not be most relevant. (2) Trust contagion across all skills. (3) No testing strategy.

### The Recommendation
Do not ship until: (1) header matches content, (2) aggregations labeled or correct, (3) bare except replaced.

### The One Thing to Do First
Fix the header-to-content mismatch so the skill tells the user what it actually analyzed.

---

*LLM Council — 5 advisors, 3 peer reviews, 1 chairman synthesis — April 4, 2026*
