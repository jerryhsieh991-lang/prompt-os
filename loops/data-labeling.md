# Data Labeling

`data-labeling` — 1 loop prompts.

### 1. Low-Agreement Label Resolution via Frozen Adjudication Ruleset

- **When:** Annotator agreement on a batch of labeled items falls below threshold (e.g. Krippendorff's alpha, pairwise %, or a fixed vote-margin rule) and the disagreements need resolving — but resolution must come from a deterministic rule/decision tree plus a gold-labeled reference set, not from having the same disagreeing labelers re-vote or "talk it out."
- **Loop:** assess the largest same-root-cause cluster in the unresolved disagreement queue -> take ONE reversible action (edit exactly one clause in the adjudication ruleset, OR route exactly one cluster to a designated third-party senior adjudicator — never back to the original disagreeing labelers) -> verify by mechanically re-running the updated ruleset against the frozen gold set (script/rule engine, not model or labeler judgment) -> commit ruleset version + newly-resolved items if gold accuracy holds and unresolved count dropped, else revert -> decide
- **Stop:** SUCCESS: unresolved-item count in the disagreement queue = 0 AND a fresh full run of the current adjudication ruleset against the frozen gold set scores >= the gold-accuracy target (no cherry-picked partial run counts) · BUDGET: <MAX_TURNS> turns or <MAX_HOURS> wall-clock elapsed · NO-PROGRESS: unresolved-item count is unchanged for <K> consecutive turns despite trying different root-cause levers (ruleset edit vs. senior-adjudicator escalation) — force a lever-category switch or escalate rather than keep tweaking the same clause · BLOCKED: the frozen gold set itself contains two cases with the same root cause adjudicated inconsistently (policy contradiction), or the designated senior adjudicator resource is unavailable — surface to a human; never fall back to majority vote of the same disagreeing labeler pool as a substitute verifier
- **Model:** The verifier (ruleset-vs-gold-set check) should run as a deterministic script/rule engine wherever the ruleset is expressible as rules — trust doesn't scale with model tier there. Where the senior adjudicator's ruling itself must be elicited via a model call (e.g. simulating/drafting a proposed ruling for a human to approve), use a distinct, ideally stronger model or a fresh context with no memory of which labelers disagreed, so it isn't anchored on either original label. Never let the model that drafted a ruleset edit also grade its own edit against gold — the gold check must be a separate, fixed pass.

```text
Goal: on the frozen low-agreement queue [<DISAGREEMENT_QUEUE> — items where annotator agreement < <AGREEMENT_THRESHOLD> per <AGREEMENT_METRIC>, e.g. Krippendorff's alpha or vote-margin], drive the unresolved-item count to 0, where EVERY resolution is produced by applying the current version of <ADJUDICATION_RULESET> (a versioned, deterministic tie-break/decision-tree document) — never by asking the original disagreeing labelers to re-vote or reach informal consensus. The ruleset must score >= <GOLD_ACCURACY_TARGET> (e.g. 100%) against the frozen <GOLD_SET> (<N> already-adjudicated cases with documented rationale, covering the known hard root-causes) before any queue resolution it produces counts as final. Freeze the queue, the gold set, and the agreement metric before turn 1 — no new items enter either set mid-loop.

Per turn:
1. Assess: pull the current unresolved count and identify the single largest cluster of disagreement items sharing one root cause (e.g. same category pair confused, same rubric clause read two ways, same edge-case type).
2. Act — ONE reversible change only:
   (a) add or edit exactly one clause/branch in <ADJUDICATION_RULESET> to cover that root cause, or
   (b) route that one cluster to <SENIOR_ADJUDICATOR> (a designated third party distinct from the original disagreeing labelers) for a binding ruling, then encode that ruling back into the ruleset as a new rule or worked example.
   Never bundle a ruleset edit and an escalation in the same turn.
3. Verify independently: re-run the updated ruleset mechanically (script/rule engine) against the frozen <GOLD_SET> — this is the verifier, and it is separate from whoever proposed the edit. Accept the change only if gold accuracy stays >= <GOLD_ACCURACY_TARGET>. If it holds, re-apply the ruleset across the full disagreement queue and record how many items now resolve unambiguously (hit a defined rule branch) vs. still fall through.
4. Decide: commit the new ruleset version + the newly-resolved queue items if unresolved count dropped AND gold accuracy held; otherwise git-revert/roll back the ruleset edit and mark that lever as tried-and-failed for this root cause.

Carry forward each turn (compact, not the full transcript): goal + both thresholds, ruleset version number, unresolved-count trend over the last 3 turns, last gold-accuracy check result, root-cause clusters already addressed (don't re-target the same one), which lever type was last tried, budget remaining.

Ban: re-editing a rubric clause you already reverted for the same root cause (no A -> B -> A oscillation — if a clause change already failed the gold check once, the next attempt on that root cause must be the senior-adjudicator escalation, not a re-wording of the same clause); treating "labelers re-voted and now agree" as resolution under any circumstance — only ruleset-driven or senior-adjudicator-driven resolutions that pass the gold check count; applying a ruleset change to the queue before it has passed the gold-set check.

Stop on whichever trips first:
- SUCCESS — unresolved count = 0 AND a fresh full run of the ruleset against the gold set scores >= <GOLD_ACCURACY_TARGET>.
- BUDGET — <MAX_TURNS> turns or <MAX_HOURS> elapsed.
- NO-PROGRESS — unresolved count unchanged for <K> consecutive turns despite alternating lever types (ruleset edit vs. escalation) — then halt ruleset tweaking and escalate the whole stalled cluster to a human policy owner rather than keep iterating.
- BLOCKED — the gold set contains contradictory adjudications for the same root cause, or <SENIOR_ADJUDICATOR> is unavailable — surface to a human; do not substitute a vote among the same disagreeing labelers as a stand-in verifier.
```
