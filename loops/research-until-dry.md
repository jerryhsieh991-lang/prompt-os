# Research Until Dry

`research-until-dry` — 8 loop prompts.

### 1. Competitive Landscape Mapping

- **When:** Before a pricing, positioning, or GTM decision, when you need an evidence-backed list of every real competitor in a market rather than the five names everyone already knows.
- **Loop:** assess competitor table + angles tried -> run one new-angle search -> corroborate any new hit against a second independent source -> update table and zero-new-round counter -> decide
- **Stop:** SUCCESS: 3 consecutive rounds add zero new corroborated competitors · BUDGET: 15 search rounds used · NO-PROGRESS: 3 rounds yield raw hits but none survive corroboration · BLOCKED: 2 consecutive planned angles hit a paywall/login wall
- **Model:** Mid-tier/cheap model is fine — this is high-volume, low-reasoning search-and-corroborate work. Reserve a stronger model (Opus xhigh or Fable 5) only for synthesizing the final positioning narrative from the table.

```text
GOAL (frozen): List every real competitor in [MARKET/CATEGORY] as of [DATE], each with a one-line differentiator and source. A competitor counts only once independently corroborated.

Maintain this state across turns: competitor table (name | diff | source | corroborated Y/N), search angles already tried, current zero-new-round counter, round number.

Each turn: (1) ASSESS the state — which angles are untried (review sites, funding/VC databases, 'X vs Y' comparison queries, app-store category browse, HN/Reddit threads, industry newsletters)? (2) ACT — run exactly ONE search using an untried angle; never repeat a prior query verbatim. (3) VERIFY — for any new name, confirm it via a second, unrelated source before adding it; a single blog mention doesn't count. (4) DECIDE — append verified entries; if none were added this round, increment the zero-new-round counter, else reset to 0.

STOP on the first that trips: SUCCESS — counter hits 3 consecutive dry rounds. BUDGET — 15 rounds used. NO-PROGRESS — 3 rounds where hits appear but none survive verification (treat as blocked judgment, not success). BLOCKED — 2 consecutive angles hit a paywall.

Report the final table, which arm fired, and angles exhausted.
```

### 2. Production Incident Root-Cause Sweep

- **When:** During or just after a production incident, when you need to exhaust plausible causal leads across logs, code history, and prior postmortems before writing the root-cause section, rather than stopping at the first plausible story.
- **Loop:** assess hypothesis list + evidence log -> pull one new evidence source -> attempt to falsify (not just support) the leading hypothesis -> update evidence log and stale-hypothesis counter -> decide
- **Stop:** SUCCESS: leading hypothesis survives an explicit falsification attempt AND 2 consecutive rounds add no new causal candidate · BUDGET: 12 rounds or 90 minutes wall-clock · NO-PROGRESS: 3 rounds with no change to the leading hypothesis's confidence in either direction · BLOCKED: a needed log/system access is unavailable
- **Model:** Use a strong reasoning model (Opus 4.8 xhigh or Fable 5) for the falsification step — distinguishing correlation from causation in incident data is exactly where weaker models rationalize a plausible-sounding but wrong story.

```text
GOAL (frozen): Identify the root cause of [INCIDENT] as a specific mechanism, not a vague label like 'flaky network.' A cause counts as established only after surviving an explicit attempt to disprove it.

Carry forward: ranked hypothesis list with confidence, evidence log (source, timestamp, supports/refutes), sources already checked, stale-hypothesis counter.

Each turn: (1) ASSESS the leading hypothesis and pick one unchecked source — error tracker, git blame on the suspect path, vendor status page, runbooks, prior postmortems for the same subsystem. (2) ACT — pull evidence from that ONE source; never re-query an exhausted one. (3) VERIFY by trying to falsify the leading hypothesis, not just confirm it — correlate timestamps and error signatures, don't accept a plausible story alone. (4) DECIDE — update confidences; if rank/confidence didn't move, increment the stale counter.

STOP on first trip: SUCCESS — hypothesis survives falsification and 2 consecutive dry rounds. BUDGET — 12 rounds or 90 minutes. NO-PROGRESS — 3 rounds with zero confidence movement; force a new angle or escalate. BLOCKED — required log/system access unavailable; halt and request it.

Report: root cause, falsifying evidence, which arm fired.
```

### 3. Literature Review Saturation Sweep

- **When:** When answering a research question that needs grounding in existing literature before writing a survey section, choosing a method, or claiming a gap is novel — not after skimming the first five search hits.
- **Loop:** assess claim map + papers checked -> pull one new paper via an untried discovery method -> corroborate or flag conflict against a second paper -> update claim map and dry-round counter -> decide
- **Stop:** SUCCESS: 3 consecutive rounds add no new claim or paper · BUDGET: 20 papers reviewed or 2 hours · NO-PROGRESS: 4 rounds returning only papers already in the claim map · BLOCKED: a load-bearing paper is paywalled with no accessible preprint/summary
- **Model:** Mid-tier model handles the search/corroborate mechanics fine. Escalate to a stronger model (Opus xhigh or Fable 5) only for the final synthesis step where conflicting claims across papers must be reconciled into a coherent narrative.

```text
GOAL (frozen): Build a claim map answering [RESEARCH QUESTION] — each claim tagged with supporting/refuting papers. A claim counts as established only when corroborated by 2+ independent papers, or logged as contested if papers conflict.

Carry forward: claim map (claim | papers for | papers against | status), papers already reviewed, discovery methods tried, dry-round counter.

Each turn: (1) ASSESS which discovery method is untried — keyword search, forward/backward citation chasing from a key paper, a review article's reference list, preprint servers, conference proceedings. (2) ACT — pull ONE new paper via that method; don't repeat an exhausted method. (3) VERIFY — check whether its claims corroborate or conflict with existing map entries; a claim from one paper alone stays 'unconfirmed.' (4) DECIDE — update the map; if nothing new was added, increment the dry-round counter.

STOP on first trip: SUCCESS — 3 consecutive dry rounds. BUDGET — 20 papers or 2 hours. NO-PROGRESS — 4 rounds returning only already-seen papers via different queries; change strategy or stop. BLOCKED — a load-bearing paper is inaccessible; flag and continue only if it doesn't change conclusions.

Report: claim map, contested claims, arm fired.
```

### 4. Vendor & Tool Shortlist Builder

- **When:** Before a buy/build decision or contract signature, when you need a complete, verified shortlist of viable tools/vendors in a category rather than the two everyone already mentioned informally.
- **Loop:** assess candidate matrix -> search one new discovery channel -> verify each claimed capability against vendor docs AND an independent user report -> update matrix and dry counter -> decide
- **Stop:** SUCCESS: 3 consecutive rounds add no new candidate or capability change · BUDGET: 10 rounds · NO-PROGRESS: 3 rounds where new names surface but fail capability verification · BLOCKED: pricing/capability info requires a sales call not yet scheduled
- **Model:** Cheap/fast model is sufficient — mostly high-volume lookup and matrix-filling. Reserve a stronger model for the final buy recommendation that weighs the matrix against your specific constraints.

```text
GOAL (frozen): Produce a feature/pricing matrix of every viable vendor for [NEED] against [MUST-HAVE CRITERIA]. A capability claim counts only if verified against two independent sources.

Carry forward: candidate matrix (vendor | capabilities | pricing | source), channels already searched, dry-round counter.

Each turn: (1) ASSESS which discovery channel is untried — vendor docs/pricing pages, review sites (G2/Capterra), community forums, analyst comparisons, a direct trial/sandbox. (2) ACT — search ONE untried channel; don't repeat a channel already mined. (3) VERIFY — confirm any new capability claim against the vendor's own docs AND one independent user report (review, forum post, case study); vendor marketing copy alone doesn't count. (4) DECIDE — update the matrix; if nothing changed, increment the dry-round counter, else reset it.

STOP on first trip: SUCCESS — 3 consecutive dry rounds with the matrix unchanged. BUDGET — 10 rounds. NO-PROGRESS — 3 rounds surfacing new vendor names that never pass verification; reconsider search terms rather than retry. BLOCKED — key pricing/capability data is gated behind a sales call; flag and pause for a human to schedule it.

Report: final matrix, gaps still unverified, arm fired.
```

### 5. Dependency Vulnerability Enumeration

- **When:** Before a security sign-off or release, when you need an exhaustive, version-matched list of known vulnerabilities across a full dependency tree rather than a scan of only direct dependencies.
- **Loop:** assess dependency coverage checklist + findings list -> pull one unchecked dependency's advisories -> verify the CVE applies to the installed version range -> update findings and dry counter -> decide
- **Stop:** SUCCESS: full tree traversed at least once AND 2 consecutive rounds add no new applicable CVE · BUDGET: full tree traversal complete or 3 hours elapsed, whichever first · NO-PROGRESS: 3 rounds where CVE IDs surface but none apply to the installed version range · BLOCKED: a private/vendored dependency has no public advisory feed
- **Model:** Cheap model is fine for the mechanical NVD/OSV lookups and version-matching — this is a good candidate for a scripted/tool-augmented loop rather than pure LLM judgment where feasible.

```text
GOAL (frozen): Enumerate every CVE applicable to the ACTUALLY INSTALLED versions of [PROJECT]'s dependency tree (direct + transitive). A CVE counts only if its affected-version range includes the installed version.

Carry forward: coverage checklist (package | version | checked Y/N), findings list (CVE | package | severity | verified Y/N), dry-round counter.

Each turn: (1) ASSESS which dependency is still unchecked. (2) ACT — pull advisories for ONE unchecked package from NVD/OSV.dev/GitHub advisories; don't re-scan a cleared package. (3) VERIFY each hit against the package's changelog or lockfile-pinned version — a CVE for a different major version doesn't count. (4) DECIDE — log verified findings; if none applied, increment the dry-round counter, else reset it.

STOP on first trip: SUCCESS — full tree checked at least once AND 2 consecutive dry rounds. BUDGET — full traversal complete or 3 hours elapsed. NO-PROGRESS — 3 rounds of hits that all fail version-match; recheck your version-resolution method. BLOCKED — a vendored/private package has no advisory feed; flag for manual audit.

Report: verified CVE list by severity, coverage %, arm fired.
```

### 6. Adversarial Fact-Check Sweep

- **When:** Before publishing a piece with factual claims — journalism, a research summary, a public blog post — when each claim needs independent corroboration and an active attempt to find disconfirming evidence, not just a supporting citation.
- **Loop:** assess claim ledger -> pick one unresolved claim and search for BOTH corroboration and disconfirmation -> log verdict with sources -> update ledger and dry counter -> decide
- **Stop:** SUCCESS: every claim has 2+ independent corroborating sources AND a documented disconfirmation attempt, stable for 2 consecutive rounds · BUDGET: max 3 rounds per claim · NO-PROGRESS: same claim fails corroboration 3 times running with different queries · BLOCKED: a claim rests on a primary source that is inaccessible (paywalled, offline, no public record)
- **Model:** Use a stronger model (Opus xhigh or Fable 5) for claims with real reputational/legal stakes — deliberately searching for disconfirming evidence is an adversarial-reasoning task weaker models tend to skip or fake.

```text
GOAL (frozen): For every factual claim in [DRAFT], reach a verdict of CORROBORATED, CONTESTED, or UNVERIFIABLE, each backed by sources. A claim only counts as CORROBORATED if 2+ independent sources support it AND a genuine attempt was made to find sources that contradict it.

Carry forward: claim ledger (claim | verdict | supporting sources | disconfirming sources tried), per-claim round count, global dry-round counter.

Each turn: (1) ASSESS which claim is still unresolved. (2) ACT — for that ONE claim, run one search explicitly aimed at finding a source that would DISPROVE it, not just confirm it; vary phrasing each attempt, never repeat a query verbatim. (3) VERIFY — a single supporting source is not enough; primary sources outrank secondary commentary. (4) DECIDE — set the verdict; if the ledger is unchanged this round, increment the dry counter.

STOP on first trip: SUCCESS — all claims resolved, stable 2 rounds. BUDGET — 3 rounds per claim used. NO-PROGRESS — same claim stuck 3 rounds; mark UNVERIFIABLE rather than grind. BLOCKED — primary source inaccessible; flag for editor review.

Report: full ledger with verdicts and sources, arm fired.
```

### 7. Regulatory Requirement Mapping

- **When:** When scoping compliance obligations for a product or launch across one or more jurisdictions, and you need a complete, primary-source-backed list of applicable requirements before compliance work begins — not a partial list from the first blog post found.
- **Loop:** assess requirement register -> pull one unchecked jurisdiction/topic from a primary legal source -> trace each requirement to statute/reg text -> update register and dry counter -> decide
- **Stop:** SUCCESS: 3 consecutive rounds add no new applicable requirement, and every entry traces to a primary source · BUDGET: 12 rounds or all listed jurisdictions covered · NO-PROGRESS: 3 rounds citing only secondary commentary with no primary-source confirmation · BLOCKED: applicability turns on facts only counsel can determine
- **Model:** Use a stronger model (Opus xhigh or Fable 5) for jurisdictions with genuinely ambiguous applicability; cheaper models suffice for well-documented single-jurisdiction sweeps but should still route ambiguity to the BLOCKED arm rather than guess.

```text
GOAL (frozen): Map every regulatory requirement applicable to [PRODUCT/ACTIVITY] in [JURISDICTIONS]. This is a research map for counsel, NOT legal advice. A requirement counts only when traced to primary statute/regulation text, not secondary summary alone.

Carry forward: requirement register (requirement | jurisdiction | primary-source citation | status), areas covered, dry-round counter.

Each turn: (1) ASSESS which jurisdiction or topic is uncovered. (2) ACT — search ONE uncovered area; use law-firm alerts and industry summaries only to discover candidates, never repeat a covered area. (3) VERIFY — trace every candidate to the actual statute or regulator guidance text before logging; a secondary source alone doesn't qualify. (4) DECIDE — update the register; if nothing new was traced, increment the dry counter.

STOP on first trip: SUCCESS — 3 consecutive dry rounds, all entries primary-sourced. BUDGET — 12 rounds or full jurisdiction list covered. NO-PROGRESS — 3 rounds of secondary-only hits with no primary confirmation; broaden the query. BLOCKED — applicability hinges on facts only counsel can judge; halt and escalate, do not guess.

Report: requirement register, unresolved ambiguities, arm fired.
```

### 8. Patent Prior-Art Search

- **When:** Before filing a patent or assessing freedom-to-operate, when you need an exhaustive prior-art search with dated public disclosures across patent databases, literature, and product history — not a five-minute skim of the obvious database.
- **Loop:** assess coverage checklist (classification codes/keyword variants) + prior-art log -> search one uncovered code/keyword combination -> verify each hit's public disclosure date predates the priority date -> update log and dry counter -> decide
- **Stop:** SUCCESS: full coverage checklist exhausted AND 3 consecutive rounds add no new dated reference · BUDGET: 20 rounds or checklist complete, whichever first · NO-PROGRESS: 3 rounds surfacing references that fail the disclosure-date test · BLOCKED: a candidate disclosure's date cannot be independently confirmed
- **Model:** Use a strong reasoning model (Opus 4.8 xhigh or Fable 5) — judging whether a reference actually anticipates a claim (vs. is merely related) is a nuanced comparison task where weaker models both over- and under-count matches.

```text
GOAL (frozen): Find every prior-art reference disclosing [CLAIMED FEATURE] with a public date before [PRIORITY DATE]. A reference counts only with an independently verifiable disclosure date.

Carry forward: coverage checklist (classification codes/keyword variants, checked Y/N), prior-art log (reference | date | source | date-verified Y/N), dry-round counter.

Each turn: (1) ASSESS which checklist item is unchecked. (2) ACT — search ONE unchecked item across patent databases (USPTO, Google Patents, Espacenet), academic literature, and dated product/web archives; never repeat a checked item. (3) VERIFY — confirm the disclosure date via an independent source (archive timestamp, publication date, filing date); an undated page doesn't count. (4) DECIDE — log verified references; if nothing new was added, increment the dry counter.

STOP on first trip: SUCCESS — checklist fully covered AND 3 consecutive dry rounds. BUDGET — 20 rounds or checklist complete, whichever first. NO-PROGRESS — 3 rounds of hits that all fail the date test; broaden keyword variants. BLOCKED — a promising reference's date can't be pinned down; flag for attorney judgment.

Report: prior-art log, checklist coverage %, arm fired.
```
