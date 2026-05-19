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
- State assumptions explicitly before starting. Ask rather than guess. Push back when a simpler approach exists. Stop when confused — do not produce speculative output.
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
Define success criteria before starting non-trivial work. Loop until verified — strong criteria enable independent looping without check-ins.
Verify before claiming completion. Size appropriately: small→haiku, standard→sonnet, large/security→opus.
If verification fails, keep iterating. Partial completion must be reported as partial, never rounded up to done.
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

## Frontend development

When fixing or developing the web UI (`web/ui/`), use the **web browser tool** to verify changes visually before claiming completion. Workflow:
1. Start the dev server (`cortellis web --dev`) if not already running.
2. Make the code change.
3. Open the browser to `http://localhost:7337` and verify the fix visually.
4. Check for regressions on related UI areas before finishing.

Do not rely solely on type checking or build success — always confirm in the browser.

## Surgical Changes

Touch only what the task requires. For `cortellis_cli.py`, `harness_runner.py`, and `workflow.yaml` files specifically: do not improve adjacent code, update unrelated logic, or change style as side effects. Every changed line should trace directly to the request.

## Ambiguity Gate (Skills)

Before running `landscape`, `pipeline`, `drug-profile`, `target-profile`, `drug-comparison`, or `conference-intel`:
- If the drug/indication/company/conference name could match multiple entities, present options first.
- For `drug-comparison`: resolve brand names to INNs before fetching (e.g., "Ozempic" → "semaglutide", "Mounjaro" → "tirzepatide").
- If the task scope is unclear (one drug vs. full competitive landscape), ask.

API calls and wiki writes are not free to undo. Clarify before launching a multi-step workflow.

## Coding Rules

**Pre-flight on non-trivial changes.** Before writing, answer these four questions:
- Where does state live? (ownership, consistency, blast radius)
- Where does feedback live? (observability, error surfacing)
- What breaks if I delete this? (coupling, fragility)
- When does timing matter? (async, ordering, race conditions)
If any answer is unclear, ask before proceeding.

**Read before you write.** Before adding or modifying code, read the exports, immediate callers, and shared utilities it touches. If unsure why existing code is structured a certain way, ask.

**Surface conflicts, don't average them.** When two patterns contradict (formatting, error handling, naming), pick the more recent or more tested one and explain why. Flag the other for cleanup. Blending conflicting patterns hides both and fixes neither.

**Match conventions even if you disagree.** Conformance over taste inside the codebase. If a convention seems harmful, surface it explicitly. Don't fork it silently.

**Use the model only for judgment calls.** Claude for: classification, drafting, summarization, extraction. Not for: routing, retries, status-code handling, deterministic transforms. If code can answer, code answers.

**Checkpoint after significant steps.** On multi-step tasks (landscape, wiki refresh, pipeline runs): summarize what was done, what's verified, what's left before continuing. Don't proceed from a state you can't describe.

**Fail loud.** "Completed" is wrong if anything was skipped or failed silently. "Tests pass" is wrong if any were skipped. Surface uncertainty rather than hiding it. A partial result reported as done is a bug.

## Setup

Say "setup omc" or run `/oh-my-claudecode:omc-setup`.

<!-- OMC:END -->
