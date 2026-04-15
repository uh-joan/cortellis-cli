<!-- OMC:START -->
<!-- OMC:VERSION:4.9.3 -->

# oh-my-claudecode - Intelligent Multi-Agent Orchestration

You are running with oh-my-claudecode (OMC), a multi-agent orchestration layer for Claude Code.
Coordinate specialized agents, tools, and skills so work is completed accurately and efficiently.

<operating_principles>
- Delegate specialized work to the most appropriate agent.
- Prefer evidence over assumptions: verify outcomes before final claims.
- Choose the lightest-weight path that preserves quality.
- Consult official docs before implementing with SDKs/frameworks/APIs.
</operating_principles>

<delegation_rules>
Delegate for: multi-file changes, refactors, debugging, reviews, planning, research, verification.
Work directly for: trivial ops, small clarifications, single commands.
Route code to `executor` (use `model=opus` for complex work). Uncertain SDK usage → `document-specialist` (repo docs first; Context Hub / `chub` when available, graceful web fallback otherwise).
</delegation_rules>

<model_routing>
`haiku` (quick lookups), `sonnet` (standard), `opus` (architecture, deep analysis).
Direct writes OK for: `~/.claude/**`, `.omc/**`, `.claude/**`, `CLAUDE.md`, `AGENTS.md`.
</model_routing>

<skills>
Invoke via `/oh-my-claudecode:<name>`. Trigger patterns auto-detect keywords.
Tier-0 workflows include `autopilot`, `ultrawork`, `ralph`, `team`, and `ralplan`.
Keyword triggers: `"autopilot"→autopilot`, `"ralph"→ralph`, `"ulw"→ultrawork`, `"ccg"→ccg`, `"ralplan"→ralplan`, `"deep interview"→deep-interview`, `"deslop"`/`"anti-slop"`→ai-slop-cleaner, `"deep-analyze"`→analysis mode, `"tdd"`→TDD mode, `"deepsearch"`→codebase search, `"ultrathink"`→deep reasoning, `"cancelomc"`→cancel.
Team orchestration is explicit via `/team`.
Detailed agent catalog, tools, team pipeline, commit protocol, and full skills registry live in the native `omc-reference` skill when skills are available, including reference for `explore`, `planner`, `architect`, `executor`, `designer`, and `writer`; this file remains sufficient without skill support.
</skills>

<verification>
Verify before claiming completion. Size appropriately: small→haiku, standard→sonnet, large/security→opus.
If verification fails, keep iterating.
</verification>

<execution_protocols>
Broad requests: explore first, then plan. 2+ independent tasks in parallel. `run_in_background` for builds/tests.
Keep authoring and review as separate passes: writer pass creates or revises content, reviewer/verifier pass evaluates it later in a separate lane.
Never self-approve in the same active context; use `code-reviewer` or `verifier` for the approval pass.
Before concluding: zero pending tasks, tests passing, verifier evidence collected.
</execution_protocols>

<hooks_and_context>
Hooks inject `<system-reminder>` tags. Key patterns: `hook success: Success` (proceed), `[MAGIC KEYWORD: ...]` (invoke skill), `The boulder never stops` (ralph/ultrawork active).
Persistence: `<remember>` (7 days), `<remember priority>` (permanent).
Kill switches: `DISABLE_OMC`, `OMC_SKIP_HOOKS` (comma-separated).
</hooks_and_context>

<cancellation>
`/oh-my-claudecode:cancel` ends execution modes. Cancel when done+verified or blocked. Don't cancel if work incomplete.
</cancellation>

<worktree_paths>
State: `.omc/state/`, `.omc/state/sessions/{sessionId}/`, `.omc/notepad.md`, `.omc/project-memory.json`, `.omc/plans/`, `.omc/research/`, `.omc/logs/`
</worktree_paths>

## Session memory

When answering questions like "what did we talk last time?" or "what have we done?", draw exclusively from domain sources: `wiki/log.md` (compile events) and `wiki/insights/sessions/` (analysis summaries). Do not surface code changes, bug fixes, or implementation details — only research findings, compiled indications, and analytical conclusions.

## Internal research library

`wiki/internal/` holds primary research documents (forecasts, epidemiology, physician surveys, access & reimbursement, unmet need). These are richer and more current than Cortellis API data for commercial questions.

**Routing rule:** When the user asks about market share, sales forecasts, physician prescribing preferences, epidemiology numbers, reimbursement coverage, or unmet need for a specific indication — run `/search-internal <query>` first before going to the Cortellis API. If results are found, lead with the internal evidence and cite the source document. Only fall back to the API if no internal docs match.

Examples that should trigger `/search-internal`:
- "What's the GLP-1 market share?" → `/search-internal GLP-1 market share obesity`
- "How many patients are on semaglutide?" → `/search-internal semaglutide treated patients`
- "What do physicians prefer for obesity?" → `/search-internal physician prescribing preference obesity`
- "What's the obesity market forecast?" → `/search-internal obesity market forecast sales`

**Routing rule for `/signals`:** When the user asks about competitive shifts, pipeline changes, new entrants, company movements, what's changed recently, or what to watch — run `/signals` to surface the latest ranked competitive intelligence from compiled wiki articles.

If the question is indication-specific (e.g. "what's changed in obesity"), also run `/search-internal <indication> recent` in parallel — internal docs often have the most current commercial picture even when pipeline signals are quiet.

Examples that should trigger `/signals` (+ `/search-internal` when indication is named):
- "What's changed in obesity recently?" → `/signals` + `/search-internal obesity market`
- "Any new entrants in MASLD?" → `/signals` + `/search-internal masld pipeline`
- "What should I watch this week?" → `/signals`
- "Competitive shifts in diabetes?" → `/signals` + `/search-internal diabetes`

**Routing rule for `/insights`:** When the user asks for a summary of past analyses, accumulated findings, what we know about an indication, or a strategic brief — run `/insights` (optionally with `--indication <slug>`) to surface session-accumulated intelligence.

Examples that should trigger `/insights`:
- "What do we know about obesity?" → `/insights --indication obesity`
- "Summary of our MASLD analysis" → `/insights --indication masld`
- "What have we found so far?" → `/insights`
- "Key findings across indications" → `/insights`

## Setup

Say "setup omc" or run `/oh-my-claudecode:omc-setup`.

<!-- OMC:END -->
