# Agent Memory

`agent-memory` — 2 loop prompts.

### 1. Agent-Loop Prompt — Memory: Consolidate & Dedupe

- **When:** Use when an agent's memory store (facts, notes, MEMORY.md-style entries, vector-DB records, etc.) has accumulated duplicate, contradictory, or stale entries and needs to be consolidated into a minimal, lossless set — without an LLM grading its own cleanup.
- **Loop:** assess (list current entry count + a sample of near-duplicates) -> one action (merge or delete exactly one duplicate cluster, or rewrite exactly one entry) -> verify (run the independent diff/consistency checker against the frozen source-of-truth fact list) -> decide (SUCCESS / BUDGET / NO-PROGRESS / BLOCKED)
- **Stop:** SUCCESS: Independent verifier reports, in one run: (a) fact_count_after equals unique_fact_count_in_baseline; (b) lost_fact_count is 0 (every baseline fact is reachable in the consolidated store); (c) duplicate_count is 0 (no entries remain above the dedupe similarity threshold); (d) contradiction_count is 0. All four must hold simultaneously in the same verifier run, not accumulated across runs. · BUDGET: Max MAX_ITERATIONS turns (default 20) OR max MAX_WALLCLOCK_MINUTES, whichever hits first. · NO-PROGRESS: If (duplicate_count + lost_fact_count + contradiction_count) does not strictly decrease for NOPROGRESS_K consecutive turns (default 3), halt as NO-PROGRESS — do not keep retrying the same merge strategy. · BLOCKED: Halt as BLOCKED if: two entries assert genuinely conflicting facts and source data doesn't indicate which is current (needs human disambiguation); the memory store is locked or uneditable; or the frozen baseline snapshot can't be produced (source files missing or unreadable).
- **Model:** Sonnet 5

```text
GOAL (frozen before the loop, do not redefine mid-run):
Consolidate and dedupe the memory store at MEMORY_STORE_PATH (e.g. a MEMORY.md file, a set of note files, or a vector-DB collection) so every distinct fact currently present appears exactly once, in a clear canonical form, with zero facts lost and zero contradictions introduced -- as measured by an INDEPENDENT verifier script that never touches the same reasoning path used to do the merging.

STEP 0, BEFORE THE LOOP (one-time setup, not repeated per turn):
1. Freeze a baseline: extract every atomic fact/entry currently in MEMORY_STORE_PATH into a flat, timestamped snapshot file BASELINE_SNAPSHOT_PATH (one fact per line/record, with a stable ID). This snapshot is ground truth for "was anything lost" and is never edited after this point.
2. Build or confirm the independent verifier: a script at VERIFIER_SCRIPT_PATH (diff/consistency checker) that takes (a) the current memory store and (b) BASELINE_SNAPSHOT_PATH, and deterministically outputs:
   - fact_count_after
   - unique_fact_count_in_baseline
   - lost_fact_count (baseline facts with no matching entry in current store, via exact match or embedding similarity >= MATCH_THRESHOLD)
   - duplicate_count (current entries with pairwise similarity >= DEDUPE_SIM_THRESHOLD)
   - contradiction_count (pairs flagged by rule-based or NLI-based contradiction check -- NOT the same LLM call doing the merge)
   This script/rubric must be authored or approved BEFORE any consolidation edit is made. The agent doing the merging must never be the one scoring its own merge -- use a separate script invocation, or a separate model call with no visibility into the merge's reasoning, only its output.
3. Record starting values of all five metrics above as turn-0 state.

PER-TURN SHAPE (repeat until Stop fires):
1. ASSESS: Run the verifier to get current metrics. From duplicate_count, pick ONE cluster of near-duplicate/contradictory entries (highest-similarity or highest-severity cluster not yet attempted this run). State which cluster and why.
2. ONE ACTION (reversible): Perform exactly one consolidation edit -- merge that one cluster into a single canonical entry, OR delete one confirmed exact duplicate, OR split one overloaded entry that conflates two distinct facts. Make the edit as a tracked change (git commit, or versioned file write) so it can be reverted. Do not batch multiple clusters in one turn.
3. VERIFY: Re-run VERIFIER_SCRIPT_PATH against BASELINE_SNAPSHOT_PATH. Record the five metrics.
4. DECIDE: Compare metrics to the previous turn and to the Stop conditions below. Emit exactly one of SUCCESS / BUDGET / NO-PROGRESS / BLOCKED / CONTINUE.

CARRY-FORWARD STATE (pass to next turn, keep compact):
- turn_number
- last 3 turns' metrics tuple: (fact_count_after, lost_fact_count, duplicate_count, contradiction_count)
- cluster_ids_already_merged (never re-attempt the same merge verbatim; never oscillate merge -> split -> merge on the same pair -- ban A->B->A)
- open_blocked_items (conflicting-fact pairs parked for human review, with both source snippets)

RULES:
- One reversible action per turn, then one verification call to the independent script -- never skip verification, never let the merging agent self-certify.
- Never re-attempt an identical merge/delete that a prior turn already tried and that didn't move the metrics (ban verbatim retries).
- Never oscillate: if cluster X was merged into entry E, do not later re-split E back toward X's original entries in a later turn without new information -- that is A->B->A.
- Any deletion of an entry that VERIFIER_SCRIPT_PATH cannot 100% confirm is a pure duplicate (any ambiguity about information loss) requires a human approval gate before the delete is committed -- treat it as irreversible until approved.
- No paid/external API calls beyond what's needed to run the verifier's similarity/NLI check; if that check requires a paid embedding/LLM call, confirm budget with the user once at Step 0, not per turn.

STOP -- halt on the FIRST that fires, checked in this order each turn:
1. SUCCESS: fact_count_after == unique_fact_count_in_baseline AND lost_fact_count == 0 AND duplicate_count == 0 AND contradiction_count == 0, all in the same verifier run.
2. BUDGET: turn_number >= MAX_ITERATIONS (default 20), or elapsed time >= MAX_WALLCLOCK_MINUTES.
3. NO-PROGRESS: (lost_fact_count + duplicate_count + contradiction_count) has not strictly decreased for NOPROGRESS_K consecutive turns (default 3).
4. BLOCKED: an unresolved genuine contradiction needs human disambiguation, the store is uneditable, or the baseline snapshot is unreadable/corrupted.

On halt, report: final metrics tuple, list of merges/deletes performed (with cluster IDs), and (if BLOCKED or NO-PROGRESS) the specific open items requiring human decision.

Placeholders to fill in before running: <MEMORY_STORE_PATH>, <BASELINE_SNAPSHOT_PATH>, <VERIFIER_SCRIPT_PATH>, <MATCH_THRESHOLD>, <DEDUPE_SIM_THRESHOLD>, <MAX_ITERATIONS>, <MAX_WALLCLOCK_MINUTES>, <NOPROGRESS_K>.
```

### 2. Agent Memory — Expire Stale Memory Safely

- **When:** A long-lived agent memory store (notes, facts, entity graph, conversation summaries) has accumulated entries that may be stale — superseded by newer entries, past an explicit TTL, or tied to a completed/expired context — and you want them expired according to explicit, pre-declared rules rather than the memory-writing agent's own judgment about what "feels" outdated.
- **Loop:** assess the frozen candidate list against the ONE frozen staleness rule-set, using a rule-checker that is a separate process from the agent -> archive (never hard-delete) exactly ONE candidate entry whose rule-match the checker confirmed -> re-run the independent rule-checker against the post-action store state as verifier -> commit the archive move + append one line to the removal log, or restore-and-skip if verification disagrees -> decide continue/stop, carrying forward only {remaining candidate count, last entry id, last verifier verdict, log line count}
- **Stop:** SUCCESS: every candidate on the frozen list is either archived-with-a-logged-matching-rule or excluded-with-a-logged-reason, AND a full independent re-scan of the (now-reduced) active store reports zero entries matching the staleness rule-set, AND the removal log has one line per action taken with entry id + rule id + timestamp · BUDGET: 15 turns, or however many turns equal the frozen candidate-list length, whichever is smaller · NO-PROGRESS: remaining-candidate count unchanged for 3 consecutive turns (the checker keeps rejecting the agent's proposed match — stop guessing and re-examine the rule text, don't retry the identical entry) · BLOCKED: an entry matches no rule and no exclusion cleanly — ambiguous phrasing, missing timestamp/provenance metadata needed to evaluate a rule, or a rule itself is ambiguous and needs a human to disambiguate it; OR the rule-checker process is unavailable/erroring (do not fall back to self-judged staleness); OR an entry the rules mark stale is still referenced by an in-flight session/process; OR the FINAL step — permanently purging the archive (as opposed to soft-deleting into it) — is reached, since that step is irreversible and requires an explicit human go-ahead before it runs
- **Model:** Mechanical once the rule-set is frozen and the checker is written — a good fit for a cheaper model (Sonnet/Haiku-class) running the bulk expiry loop, since the independent rule-checker (not the model) carries the actual verification weight. Use a strong model (Opus-class xhigh) up front to author the staleness rule-set and the rule-checker script, and to handle any BLOCKED escalation (ambiguous rule text, missing metadata) — never let the cheap loop invent or loosen a rule to make progress.

```text
Goal: expire stale entries from <MEMORY_STORE_PATH_OR_SYSTEM> according to ONE frozen, explicit staleness rule-set — and nothing else. Before looping:

1. Write down the staleness rule-set as a numbered list of mechanically-checkable rules over entry metadata (e.g. "R1: entry.type=='session-note' AND now - entry.last_referenced_at > <TTL_DAYS> days"; "R2: entry.superseded_by is set and the superseding entry still exists and is active"; "R3: entry.explicit_expiry_date < now"). Do not include any rule that requires subjective judgment ("looks outdated," "probably not needed"). This rule-set is frozen for the whole loop — do not add, loosen, or reinterpret a rule mid-run just to keep an entry moving.
2. Implement or point to an independent rule-checker — a separate script/tool call, NOT the same reasoning pass that decides to remove an entry — that takes one entry + the rule-set and returns {match: bool, rule_id, reason} or {match: false, reason}. This checker is the verifier for every turn; your own read of "this looks stale" never counts.
3. Run the checker once over the full store to produce a FROZEN candidate list (entry ids the checker currently flags). This list is the scope for the loop — it does not grow mid-run even if you notice other stale-looking entries; log those separately for a future pass instead.

Each turn:
(1) Assess: pick the next candidate id from the frozen list (or, near the end, sample a few already-processed entries plus a few never-flagged entries for the final full re-scan).
(2) Act — ONE reversible step: archive (soft-delete / move to a tombstone location that supports restore) that single entry, tagging it with the matching rule_id from step (2)'s original checker run. Never hard-delete inside the loop.
(3) Verify independently: re-run the rule-checker against the entry's prior state to confirm the match still holds, AND confirm the entry is now absent from the active store and present in the archive with its rule_id intact. The checker's verdict is authoritative, not your own recollection of why you picked it.
(4) Decide: if the checker confirms the match and archival succeeded, append one line to the removal log (entry id, rule_id, timestamp, one-line reason) and drop the id from the remaining-candidate count; if the checker disagrees (false positive) or archival fails, restore the entry immediately and mark it "excluded — checker disagreed" in the log instead of retrying the identical action. Carry forward only the compact state: {remaining candidate count, last entry id acted on, last verifier verdict, log line count} — not the full entry contents or full log history.

Never remove an entry the checker did not independently confirm. Never batch-remove more than one entry per turn. Never perform a permanent purge (irreversible deletion from the archive) inside this loop — that is a separate, explicitly human-approved step outside this loop's stop conditions.

Stop the instant one of these trips:
- SUCCESS — every id on the frozen candidate list is archived-and-logged or excluded-and-logged, AND a fresh full run of the independent rule-checker over the reduced active store returns zero matches, AND the removal log has exactly one line per action taken.
- BUDGET — 15 turns, or the frozen candidate-list length, whichever is smaller.
- NO-PROGRESS — remaining-candidate count unchanged for 3 consecutive turns (the checker keeps rejecting your proposed match — stop and re-read the rule text instead of retrying the same entry).
- BLOCKED — an entry can't be cleanly matched or excluded because of missing metadata or ambiguous rule wording (needs a human to clarify the rule); the rule-checker process itself is unavailable or erroring (do not fall back to judging staleness yourself); an entry the rules flag is still actively referenced by a live session; or you reach the point of proposing a permanent purge of the archive, which requires explicit human approval before it happens.

Report, at halt: which arm tripped, the full removal log, the remaining active-store count, and (if BLOCKED) the exact entry id and rule id that couldn't be resolved.
```
