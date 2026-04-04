# LLM Council Transcript — Landscape Skill Completeness
**Date:** April 4, 2026

---

## Original Question
> Is the cli_anything/cortellis/skills/landscape complete enough? Do we have gaps?

## Framed Question
**Question:** Is the `cli_anything/cortellis/skills/landscape/` skill complete enough for production use, or does it have meaningful gaps?

**Context:** This is a competitive landscape analysis skill for a pharmaceutical intelligence CLI (Cortellis). It generates reports across 3 modes: indication (disease), target (biological target), and technology (modality like ADC, mRNA). It has 11 recipe scripts covering: entity resolution (indication, target, technology), paginated drug fetching, mechanism enrichment via Drug Design API, biosimilar grouping, company deduplication with phase-weighted scoring, trial phase summaries, missing drug detection, and ASCII report generation. The CLI wraps the Cortellis API (17 data domains, 80+ commands). There are 20 other specialized skills that handle adjacent use cases. The skill router gives priority to more specific skills (clinical-landscape, combination-landscape) before falling back to the generic landscape skill.

**What's at stake:** This is the flagship analytical skill — competitive landscape is the #1 use case in pharma intelligence. If it has gaps, users will get incomplete or misleading competitive pictures, which directly impacts business decisions (M&A, licensing, portfolio strategy).

---

## Advisor Responses

### 1. The Contrarian

The fatal flaw is the 300-drug hard ceiling. Six pages of 50 is an arbitrary architectural limit masquerading as a feature. For major indications like oncology or diabetes, there are hundreds of active programs. You will silently truncate competitive landscapes. The "truncation warnings from metadata" mention suggests the system knows this happens — which means it's a known data loss problem, not an edge case.

The "missing drug detection" mechanism is also circular. It fetches ALL drugs without phase filter and diffs against phase CSVs — but if that unfiltered fetch is also paginated, you're just comparing two incomplete datasets. The diff will appear clean while both sides are truncated.

Mechanism enrichment filling "50-60% of empty mechanisms" means 40-50% of drugs in the output have no mechanism annotation. For a competitive landscape, mechanism clustering is fundamental — you cannot assess competitive overlap without it. That's not a gap, that's a core function that half-fails.

The company scoring uses a hardcoded list of ~20 major pharma companies. That list will be stale within months. Acquisitions, spinouts, name changes — your "major pharma" classifier will misclassify companies constantly, and nobody will notice because the output looks authoritative.

Three-second rate limiting between pages means fetching 300 drugs across 6 phases takes minutes per run. If a user queries oncology across three modes, they're waiting a long time for an incomplete answer.

The biosimilar detection is text-matching on drug names. This will miss biosimilars with brand names and will false-positive on drugs with "follow-on" in their clinical description.

This skill will produce confident-looking reports with systematic blind spots. That's worse than no skill at all.

### 2. The First Principles Thinker

The question presupposes "completeness" is the right lens. It isn't. The real question is: what decisions break if this skill is wrong, and does the skill surface that risk to the user?

Strip it back. A competitive landscape in pharma serves one purpose: tell someone whether a space is crowded, who the credible threats are, and where the white space is. Everything else is decoration.

Three structural problems, not feature gaps:

1. **The 300-drug ceiling is invisible to the user.** 6 pages × 50 hits is an engineering constraint presented as a complete picture. In a crowded indication like oncology, you're silently dropping drugs. The "truncation warning" in metadata is not enough — the user needs to know the floor before they trust the ceiling.

2. **Company scoring rewards activity, not capability.** Phase-weighted scoring (Launched=5 down to Discovery=1) measures who has the most programs. It says nothing about who has the best program. A single Roche Phase 3 asset outweighs ten Discovery-stage startups, but the algorithm doesn't know that.

3. **The skill cannot distinguish "no data" from "no activity."** If the Cortellis API returns nothing for a target, is the space empty or is the data coverage poor? The skill has no mechanism to flag low-confidence results. Users will treat silence as a clean competitive signal.

The actual question you should be asking: does this skill tell users what it doesn't know? Right now, the answer is no. That's the production gap — not the feature list.

### 3. The Expansionist

The gaps are real, but the bigger story is what this skill could become with modest investment.

Right now it caps at 300 drugs per phase. That's not a constraint, that's a hidden insight generator waiting to happen. The long tail of phase 1 and discovery compounds is where you spot emerging mechanisms before competitors do. Raise the cap or make it configurable — the users who need this most are exactly the ones doing early-stage BD scouting.

The major pharma list of ~20 companies is the most undervalued piece here. That classification logic is the seed of a company-tier taxonomy. Extend it: tier 1 majors, tier 2 specialty pharma, tier 3 biotech, tier 4 academia/spinouts. Suddenly the competitive landscape isn't just "who's in the race" but "what stage of industry maturation is this indication at." That's a $200M M&A decision framing, not just a report.

Mechanism enrichment at 50-60% fill rate sounds like a gap. Flip it: that 40-50% unknown is a signal. Unknown mechanisms cluster around novel programs. Surface that explicitly in the report — "X drugs with uncharacterized mechanisms" is a competitive intelligence finding, not missing data.

The deals section (up to 20) is criminally underused. Deal flow tied to a landscape is the connective tissue between pipeline position and commercial validation. Twenty is a floor, not a ceiling. Cross-reference deal timing against phase transitions and you have a partnership velocity metric no competitor intelligence tool currently offers.

This skill isn't missing completeness. It's missing ambition in how it frames what it already has. The infrastructure is there. The ceiling is narrative, not technical.

### 4. The Outsider

I can't evaluate this skill because I can't see it. Everything above is a description of what the builder believes they built. That's not the same as what exists.

Three things stand out from reading this description cold:

**The 300-drug cap is a business decision disguised as a technical detail.** "50 hits/page, max 6 pages" — who decided 300 drugs per phase is enough? In a crowded oncology indication, you can blow past that. The description says "show truncation warnings from metadata" but doesn't say whether the report flags which phases were truncated or what percentage of the actual landscape is missing. A decision-maker reading a competitive landscape doesn't know what they're not seeing.

**The major pharma list of ~20 companies is a maintenance trap.** Pharma M&A moves fast. A hardcoded list goes stale. Who updates it? When was it last updated? Is Gilead on there? Is AstraZeneca's biologics arm separated from its small molecule arm? This classification drives the company rankings, which drive strategic conclusions.

**"50-60% enrichment fills empty mechanisms" means 40-50% stay empty.** The description frames this as a win. I'd frame it as: nearly half of drugs in the landscape report have no mechanism of action listed. That's a significant gap for users trying to understand competitive differentiation.

I can't tell you if the code actually does what the description claims, whether error handling is real or aspirational, or whether the output is legible to a non-technical pharma analyst. Those require reading the actual files.

### 5. The Executor

The skill has execution gaps that will bite users in production.

**What's actually broken or risky:**

1. **300 drug hard cap is a real problem.** Oncology indications like NSCLC or breast cancer have 500+ drugs in pipeline. You're silently dropping drugs. The "truncation warning" in metadata only helps if the report surfaces it prominently — does it? If not, users get a confident-looking incomplete picture.

2. **20 mechanism enrichment lookups per phase file is arbitrary and too low.** If 50-60% of mechanisms are empty and you're capping enrichment at 20, a phase with 100 drugs still has ~30 unenriched entries. Users see blank mechanism columns and can't do modality analysis.

3. **The major pharma list of ~20 companies needs validation.** Is Novo Nordisk on it? AbbVie? BioNTech? If a major player is missing, their drugs get mis-classified as "emerging biotech" and the company rankings mislead M&A decisions.

4. **No error surfacing in the report itself.** If entity resolution falls through all 4 strategies and lands on a fallback, does the report say "WARNING: indication resolved via suffix strip"? If not, users don't know they might be looking at the wrong disease area.

**What Monday morning looks like:**

- Run the skill on NSCLC, PD-1, and ADC. Check if drug counts match a manual Cortellis web query.
- Count blank mechanism entries in a large phase file.
- Audit the major pharma list against top 20 by revenue.
- Grep the report generator for any warning/caveat output on resolution failures.

The bones are solid. The gaps are in silent failures and arbitrary caps that erode trust without the user knowing it.

---

## Peer Reviews

### Anonymization Mapping
- Response A = The Contrarian
- Response B = The First Principles Thinker
- Response C = The Expansionist
- Response D = The Outsider
- Response E = The Executor

### Peer Review 1

**Strongest: Response E (Executor)** — specific, actionable gaps with concrete validation steps. The "Monday morning" audit list is practically useful. Correctly distinguishes between silent failures (the real danger) and feature gaps.

**Biggest blind spot: Response C (Expansionist)** — reframes every flaw as opportunity without acknowledging production risk. Calling 40-50% missing mechanism data "a signal" is wishful framing. Provides no actionable path and would give a stakeholder false confidence.

**All missed:** Output consumer fidelity — who reads these ASCII reports, and do they have the pharma domain context to recognize when something looks wrong? No human-readable caveats embedded in the report indicating confidence level, data coverage percentage, or resolution method used.

### Peer Review 2

**Strongest: Response E (Executor)** — combines specific, actionable critique (20-lookup enrichment cap, entity resolution fallback warnings) with a concrete verification plan. Gives the developer a Monday-morning checklist with falsifiable tests.

**Biggest blind spot: Response C (Expansionist)** — reframes every deficiency as opportunity and never acknowledges that the skill can actively mislead users. Reads like a product pitch, not an evaluation.

**All missed:** The output format itself. None questioned whether ASCII reports are appropriate for a flagship pharma intelligence tool. Pharma analysts export to decks, share with executives, paste into models. ASCII is a dead end for adoption. No JSON export, no CSV alongside narrative. Production use requires usable output, not just accurate output.

### Peer Review 3

**Strongest: Response E (Executor)** — only one that proposes concrete validation steps. Names actual indications (NSCLC, breast cancer). Asks verifiable questions about warning surfacing.

**Biggest blind spot: Response C (Expansionist)** — reframes every flaw as opportunity and never answers the question. Motivated reasoning throughout.

**All missed:** The output consumer. Who reads these ASCII reports, and what do they do next? If a BD analyst pastes a truncated competitive landscape into a board deck, the downstream harm is a bad strategic decision made with false confidence. No response asked whether the visual design signals limitations.

---

## Chairman Synthesis

### Where the Council Agrees

Four of five advisors independently flagged the same three production failures:

**The 300-drug ceiling is silent truncation.** Not a warning, not a caveat in the report — just a confident-looking competitive landscape that stops counting at an arbitrary number. For oncology, NSCLC, diabetes, or any major indication, this produces a structurally incomplete picture that looks complete. Every advisor who engaged with this issue called it a critical flaw.

**Mechanism enrichment fails roughly half the time.** "50-60% fill rate" is a pleasant way of saying the core annotation function leaves 40-50% of drugs without mechanism data. That is not a partial feature — it is a feature that half-fails on its primary task.

**The hardcoded pharma list is a maintenance trap.** It will go stale. It already may be stale. The scoring algorithm built on top of it is therefore unreliable from the moment it shipped.

### Where the Council Clashes

**The Expansionist argues the gaps are feature seeds. The rest of the council says that's motivated reasoning.**

The Expansionist reframes every flaw — the drug cap, the unknown mechanisms, the underused deals section — as an opportunity for future intelligence. The peer reviews uniformly identified this as the weakest position on the council: it never answers the question, it reads like a product pitch, and it treats production risk as an aesthetics problem.

The genuine tension here is real but asymmetric. Yes, the long tail of unknown mechanisms might cluster around novel programs. Yes, the deals section could support a partnership velocity metric. These are legitimate future directions. But the question is production readiness, and a skill that confidently truncates oncology landscapes and silently fails on half its mechanism annotations is not production-ready regardless of its upside.

The Expansionist loses this clash. The gaps are not opportunities — they are silent failure modes in a tool used for M&A and licensing decisions.

### Blind Spots the Council Caught

**The output consumer is invisible in every advisor response, and the peer reviews caught it.**

All three peer reviews flagged the same omission: no advisor asked what happens when a BD analyst pastes a truncated competitive landscape into a board deck. The ASCII report format has no embedded confidence signals, no coverage percentage, no indication of whether entity resolution used a fallback strategy. A non-technical pharma analyst reading the output has no way to know they are looking at an incomplete picture.

This is the most consequential gap the council missed individually. The 300-drug ceiling is bad. The ceiling with no warning label in the output is catastrophic. The harm is not the truncation — it is that the truncation is invisible to the person making the strategic decision.

**Output format is a production blocker the advisors also missed.** Two peer reviews flagged that ASCII-only output with no JSON or CSV export is a dead end for pharma analyst adoption. Accurate output that cannot be used downstream is not production output.

### The Recommendation

**This skill is not production-ready. Ship it as a beta with explicit limitations surfaced in the output, or do not ship it as a flagship.**

The reasoning is direct: the #1 pharma intel use case should not produce confident-looking reports with invisible truncation and 40-50% annotation failure. The combination of silent failures and high-stakes downstream decisions (M&A, licensing, portfolio strategy) is a liability, not an acceptable tradeoff. The bones are solid — the architecture is coherent, the modes are well-designed, the recipe structure is sane. The production gap is not in what the skill does. It is in what the skill does not say about what it is not doing.

A skill that surfaces its own limitations — hard caps with explicit counts, mechanism fill rates in the report footer, resolution method used, fallback warnings inline — is a production skill. A skill that hides those limitations behind confident-looking output is a liability.

### The One Thing to Do First

Add an output footer to every generated report that shows: total drugs fetched vs. the cap, mechanism annotation fill rate for that run, entity resolution method used (NER/fallback/hardcoded), and a one-line data coverage warning if any of these metrics fall below a defined threshold.

This single change does not fix the underlying gaps. It makes every gap visible to the person reading the report, which is what separates a tool that informs decisions from a tool that misleads them.

---

*LLM Council — 5 advisors, 3 peer reviews, 1 chairman synthesis — April 4, 2026*
