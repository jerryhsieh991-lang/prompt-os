# SQL / Analytics

`sql-analytics` — 5 loop prompts.

### 1. Text-to-SQL agent-loop prompt (SQL / Analytics family)

- **When:** Use when a natural-language analytics question must be answered with a read-only SQL query whose actual result is checked by an independent sanity script before it is trusted.
- **Loop:** assess -> one action (write/revise one SQL query) -> verify (execute query + run independent sanity-assertion checker) -> decide
- **Stop:** SUCCESS: The query executes without error against the target database AND the independent sanity-checker (a separate script/tool, not the model's own read of the output) confirms all of: (a) row count within the declared plausible range, (b) required columns non-null, (c) any declared numeric/date columns within their declared bounds, reconfirmed on the final run. · BUDGET: max_iterations query attempts (a hard cap on distinct query revisions this run may make). · NO-PROGRESS: Sanity-check pass count (0-3 of the assertion categories passing) is flat for 3 consecutive turns despite trying a different fix strategy each time (not the same edit repeated) — signals the loop should stop and escalate rather than keep guessing. · BLOCKED: The question is ambiguous against the schema (e.g. an entity/metric name matches 2+ plausible columns/tables with materially different results) and cannot be resolved without a human pick; OR a needed table/column does not exist in the schema; OR only a destructive/DDL statement could answer the question and no write-approval has been granted.
- **Model:** Use a mid-tier model for mechanical SQL syntax fixes once schema and sanity bounds are fixed; escalate to a stronger reasoning model or a human for schema ambiguity and sanity-bound design.

```text
Goal (frozen): produce ONE SQL query against <database> (schema reference: <schema_notes>) that correctly answers "<nl_question>", where correctness is judged by an independent sanity-checker script (NOT the model re-reading its own output) confirming, on the query's actual result set: (a) row count falls within <expected_row_range>; (b) columns in <required_nonnull_columns> contain no NULLs; (c) any column in <numeric_date_bounds> falls within its declared min/max. Define <expected_row_range>, <required_nonnull_columns>, and <numeric_date_bounds> BEFORE the loop starts, from domain knowledge of the schema and question — not by peeking at a query's output and backfitting bounds to make it pass.

Per turn:
(1) assess — read the prior turn's failure mode if any: SQL syntax/execution error, empty or trivially-wrong result (e.g. 0 or 1 row for an aggregate that should return many), or a specific failed sanity category (row-count / non-null / range). If this is turn 1, assess the schema for the tables/columns the question needs.
(2) act — write or revise exactly ONE query. Change only what the prior failure implicates (e.g. a wrong JOIN, a missing WHERE filter, an incorrect aggregation grain) — do not rewrite the whole query from scratch each turn, and do not touch a part of the query that already passed its sanity category.
(3) verify — execute the query read-only (SELECT/read-only role; no INSERT/UPDATE/DELETE/DDL) against <database>, capture the result set, then run it through the independent sanity-checker tool/script — a mechanism separate from the model's own judgment of whether the numbers "look right."
(4) decide — if the checker confirms execution succeeded and all three sanity categories pass, run it once more to reconfirm, then report SUCCESS with the query and result summary. If it partially passes, keep the parts that passed and target the next turn's edit at the failing category only. If it regresses (a category that passed now fails), revert to the last passing query text before making the next edit.

Carry forward each turn: the current best query text, which of the 3 sanity categories currently pass/fail, the specific failure reason each turn (not just pass/fail), fix strategies already tried per failure mode (never retry the identical edit verbatim), iterations used, budget remaining.

Stop on the FIRST that trips: SUCCESS — query executes cleanly and the sanity-checker confirms row-count range, required non-null columns, and declared numeric/date bounds all pass, reconfirmed on a second run; BUDGET — <max_iterations> query attempts; NO-PROGRESS — sanity-check pass count unchanged for 3 consecutive turns despite a genuinely different fix strategy each turn (not A->B->A oscillation between two query variants); BLOCKED — the question is ambiguous against the schema and needs a human pick between 2+ plausible interpretations, a referenced table/column does not exist, or the only way to answer would require a write/DDL statement (requires explicit human approval before executing — never issue a write query to "fix" a read-only sanity failure).
```

### 2. SQL Query Optimization to a Latency Budget — Agent-Loop Prompt

- **When:** User asks for a reliable agent-loop prompt to optimize a slow SQL query/report down to a target latency, without regressing correctness.
- **Loop:** assess (read current EXPLAIN plan + last measured runtime) -> one action (one reversible schema/query change: add index, rewrite one join/subquery, add one hint, adjust one stat/config) -> verify (independent harness: correctness suite + EXPLAIN/measured runtime on fixed dataset) -> decide (SUCCESS/BUDGET/NO-PROGRESS/BLOCKED, log delta, continue or stop)
- **Stop:** SUCCESS: Measured p<PERCENTILE> runtime on <BENCHMARK_DATASET> is at or under <LATENCY_BUDGET_MS>ms across <N_RUNS> consecutive runs, AND the full correctness suite (<CORRECTNESS_SUITE_CMD>) passes with zero row/value diffs against the golden baseline. · BUDGET: Max <MAX_ITERATIONS> optimization turns (default 8). Each turn = exactly one schema/query change + one verification cycle. Any change requiring a schema migration, index build on a table over <LARGE_TABLE_ROW_THRESHOLD> rows, or config change on a shared/production instance requires the human approval gate before execution (see BLOCKED). · NO-PROGRESS: Halt if the verifier's runtime metric fails to improve by at least <MIN_IMPROVEMENT_PCT>% (default 5%) over the best-so-far value for <K_FLAT_TURNS> consecutive turns (default 3), even if individual turns are "different" changes — flat-metric turns count regardless of which lever was pulled. · BLOCKED: Halt and hand off to a human when: (a) the only remaining levers require an irreversible/paid/production action (index build on prod, warehouse resize, materialized view backfill) not yet approved; (b) the correctness suite fails after a change and cannot be fixed by reverting that single change; (c) EXPLAIN shows the optimizer ignoring an index/hint for a reason outside the agent's authority (stale stats requiring a full ANALYZE on a locked table, engine-version limitation); (d) the budget's target is provably unreachable under the current schema (e.g., a full table scan is mechanically required and no index/partition can avoid it) — state the proof, don't keep spending turns.
- **Model:** Sonnet 5

```text
GOAL (frozen — do not renegotiate mid-loop)
Reduce the measured latency of <QUERY_NAME_OR_FILE_PATH> against <BENCHMARK_DATASET> (a fixed, representative dataset/snapshot — not prod-live data, so runs are reproducible) to <LATENCY_BUDGET_MS>ms at p<PERCENTILE>, measured by <N_RUNS> consecutive warm runs, WITHOUT changing query results versus the golden baseline captured by <CORRECTNESS_SUITE_CMD>.

Independent verifier (frozen before the loop starts — this is not the agent grading itself):
1. Correctness gate (must pass every turn, non-negotiable, checked FIRST): run <CORRECTNESS_SUITE_CMD> — a fixed suite of row-count checks, checksum/diff-against-golden-output checks, and any business-logic assertions already in place. Zero diffs allowed. A change that speeds up the query but changes even one row of output is a FAIL, full stop, revert.
2. Performance gate (checked only if #1 passes): run <EXPLAIN_AND_BENCH_CMD> — produces (a) the query plan via EXPLAIN/EXPLAIN ANALYZE and (b) measured wall-clock runtime over <N_RUNS> runs on <BENCHMARK_DATASET>. Record p<PERCENTILE>. This command is owned by the verifier, not edited by the optimization turns — the agent may read its output but must not modify the harness to make numbers look better.

Both gates run via a script/CI job the agent does not modify during the loop (<CORRECTNESS_SUITE_CMD> and <EXPLAIN_AND_BENCH_CMD> are separate from whatever the agent edits — the query/schema/index files). If the agent believes the verifier itself is wrong, that's a BLOCKED condition, not a license to edit it.

PER-TURN SHAPE
1. ASSESS — read the EXPLAIN plan and last measured runtime from the previous turn's verify output (or baseline on turn 1). Identify the single most expensive plan node (seq scan, nested loop, sort spill, etc.) as this turn's target.
2. ONE ACTION — make exactly one reversible change addressing that node:
   - add/drop one index
   - rewrite one join, subquery, or CTE
   - add one query hint / change one join order
   - adjust one relevant table statistic or session-level planner config (not global/prod config)
   Never bundle multiple changes in one turn — if the next verify regresses, you must know which single change caused it. Never touch the verifier files themselves.
3. VERIFY — run correctness gate, then (if it passes) the performance gate. Record: turn number, change made, correctness result, EXPLAIN plan delta (which node changed), p<PERCENTILE> runtime, delta vs. previous best.
4. DECIDE — apply the Stop line below. If none of the four arms fire, carry state forward and start the next turn.

CARRY-FORWARD STATE (compact, written at the end of every turn)
- turn_count / MAX_ITERATIONS
- best_runtime_ms so far + which turn produced it + the exact change that produced it
- last_K_FLAT_TURNS runtimes (for NO-PROGRESS check)
- list of changes already tried, tagged [kept] or [reverted] with one-line reason — ban re-trying a [reverted] change verbatim, and ban oscillating between two changes (A->B->A) without a new variable (new index column order, different join type, etc.) that makes the retry actually different
- current EXPLAIN plan's most-expensive node (this turn's target for the next ASSESS)
- any change currently pending human approval (irreversible/paid/prod-touching)

STOP — halt on the FIRST of these to trigger, checked in this order every turn:
- SUCCESS: performance gate shows p<PERCENTILE> <= <LATENCY_BUDGET_MS>ms across <N_RUNS> runs AND correctness gate passes. Report final change set, plan diff (before/after EXPLAIN), and runtime graph across turns.
- BLOCKED: next viable change requires human approval (irreversible index build, prod config, paid warehouse resize) not yet granted, OR correctness gate fails and can't be fixed by reverting the single last change, OR the target is proven mechanically unreachable under the current schema. Stop, do not guess, hand off with exact state above.
- NO-PROGRESS: best_runtime_ms improved by less than <MIN_IMPROVEMENT_PCT>% for <K_FLAT_TURNS> consecutive turns. Stop and report the plateau plus the two or three levers not yet tried that would require schema changes out of scope (partitioning, denormalization, materialized views) as next-step recommendations for a human — do not keep iterating on diminishing-return micro-tweaks.
- BUDGET: turn_count reaches <MAX_ITERATIONS> without SUCCESS. Report best_runtime_ms achieved, the gap to <LATENCY_BUDGET_MS>ms, and the change set that got there.

Whichever arm fires, the final report always includes: best runtime achieved, correctness status, the exact kept change set (so it's reproducible outside the loop), and — for BLOCKED/NO-PROGRESS/BUDGET — the specific next action a human should take.
```

### 3. SQL/Analytics Agent-Loop Prompt: Schema-Aware Question Answering

- **When:** Use when a user asks a natural-language analytics question against <DATABASE_NAME> and the answer must come back as a validated SQL query (and its result) that is guaranteed to reference only columns/tables/joins that actually exist in the live schema — not hallucinated ones.
- **Loop:** assess (inspect live schema + prior attempt state) -> one action (write or revise exactly one SQL query) -> verify (independent schema/execution validator checks the query, not the model) -> decide (SUCCESS / BUDGET / NO-PROGRESS / BLOCKED)
- **Stop:** SUCCESS: Query executes without error against <DATABASE_NAME>, every table/column/join it references is confirmed present in the live schema dump by the independent validator (not by the generating model), the result set is non-error and shape-plausible for the question (right cardinality: aggregate question -> few rows, list question -> row-per-entity), and the validator's structured PASS verdict is recorded verbatim in final state. · BUDGET: Max <MAX_ITERATIONS> turns (default 6). Each turn = exactly one query revision, independent of how many columns/joins it touches. · NO-PROGRESS: Flat if the validator's error signature (error_code + offending_identifier) is unchanged for 2 consecutive turns, or if error_count does not strictly decrease for 3 consecutive turns. Flat triggers HALT, not a retry. · BLOCKED: BLOCKED (halt immediately, do not spend a budget turn) when: the question requires a table/column that does not exist anywhere in the live schema and no reasonable synonym/join path closes the gap; the schema dump itself is stale/unreadable (introspection call fails); the query would require write/DDL access; or resolving ambiguity (e.g. "revenue" could mean 3 different columns) needs a human pick between named candidates.
- **Model:** Sonnet 5

```text
GOAL (frozen, do not restate or renegotiate mid-loop):
Answer the question — "<USER_QUESTION>" — against database <DATABASE_NAME> with ONE SQL query that (a) executes successfully, (b) references only tables/columns/joins that an INDEPENDENT schema validator confirms exist in the live schema right now, and (c) returns a result shape consistent with the question. Stop on the first of SUCCESS / BUDGET / NO-PROGRESS / BLOCKED below. Never mark done on your own read of the query — only the validator's PASS verdict counts.

INDEPENDENCE CONTRACT (must hold every turn):
- The GENERATOR (you) writes/revises the SQL query using your best understanding of the schema.
- The VERIFIER is a separate, mechanical step that you do NOT get to self-grade:
  1. Pull the CURRENT live schema via `<SCHEMA_INTROSPECTION_COMMAND>` (e.g. `information_schema.columns` query, `\d+`, `DESCRIBE`, or your DB's catalog call) — never trust a cached/remembered schema from a prior turn.
  2. Statically check every identifier in the query (tables, columns, join keys, CTEs' source columns) against that fresh dump. Any identifier not found = FAIL with error_code=UNKNOWN_IDENTIFIER and the offending name.
  3. If static check passes, actually EXECUTE the query against <DATABASE_NAME> (read-only role only — see gate below). A DB error = FAIL with error_code=EXEC_ERROR and the driver's message.
  4. If it executes, sanity-check result shape against the question (e.g. a "total/average/count" question returning >50 rows is suspicious; a "list of X" question returning 1 row is suspicious) = FAIL with error_code=SHAPE_MISMATCH if implausible, else PASS.
- Never accept "the query looks right to me" as verification. No PASS without an actual introspection query + actual execution in this turn.

PER-TURN SHAPE:
1. ASSESS — read carry-forward state below. Note the last validator error_code/offending_identifier if any. Do NOT re-read the whole schema by hand; the verifier step does that.
2. ONE ACTION — write or make exactly one revision to the SQL query that addresses the most recent FAIL (or a first draft on turn 1). One change in intent per turn: e.g. fix one wrong join key, swap one hallucinated column for its real name, add one missing filter — not a full rewrite unless turn 1.
3. VERIFY — run the INDEPENDENCE CONTRACT steps above in full. Record verdict, error_code, offending_identifier (if any), execution row count, and a one-line result summary.
4. DECIDE — apply the Stop Line below in order. If none fire, update carry-forward state and proceed to next turn.

APPROVAL GATE (irreversible/paid actions):
- The verifier's execution step must run under a READ-ONLY credential/role against <DATABASE_NAME>. If only a read-write credential is available, STOP and request explicit human confirmation before the first execution — do not silently execute with elevated rights.
- If the question can only be answered by a query with side effects (INSERT/UPDATE/DELETE/DDL) or by hitting a metered/paid query tier (e.g. a data warehouse with per-scan billing above <COST_THRESHOLD>), treat as BLOCKED and surface to the user for explicit approval before any execution — never auto-run.

CARRY-FORWARD STATE (compact, pass forward each turn — do not re-derive from scratch):
- turn_number / <MAX_ITERATIONS>
- current_query_text (the single latest SQL candidate, full text)
- last_verdict: PASS | FAIL
- last_error_code + offending_identifier (null if PASS or turn 1)
- error_count_history: [turn1_count, turn2_count, ...] (strictly track, used for NO-PROGRESS check)
- schema_snapshot_id_or_hash (from this turn's introspection call, so drift is detectable)
- confirmed_real_identifiers: {table/column names already validator-confirmed this session — reuse, don't re-guess}
- rejected_identifiers: {name -> reason} (columns/tables tried and confirmed NOT to exist — ban re-trying verbatim)
- attempts_log: short list of (turn, one-line change made, verdict) — used to detect A->B->A oscillation

ANTI-OSCILLATION RULE:
Before applying a revision, check attempts_log: if the proposed change reverts current_query_text to a prior turn's exact text, or reintroduces an identifier in rejected_identifiers, do NOT apply it — that turn counts as a forced NO-PROGRESS signal (increment a repeat-strike counter; 2 strikes = HALT under NO-PROGRESS regardless of the K-turn window).

STOP — halt on the FIRST that fires, checked in this order:
1. SUCCESS: validator returns PASS verdict this turn (schema-confirmed identifiers + clean execution + plausible shape). Report: final SQL, row count, one-line result summary, schema_snapshot_id used.
2. BLOCKED: required table/column genuinely absent from live schema with no viable path; schema introspection itself fails; write/DDL access required; paid/metered execution needs human approval; or semantic ambiguity needs a human to pick between named candidate columns/tables. Report: exactly what's missing/ambiguous and what human input unblocks it.
3. NO-PROGRESS: same error_code+offending_identifier for 2 consecutive turns, OR error_count_history not strictly decreasing for 3 consecutive turns, OR 2 anti-oscillation strikes. Report: attempts_log, the stuck error, and a recommendation (e.g. "likely needs a join through table X — confirm with human").
4. BUDGET: turn_number reaches <MAX_ITERATIONS> without PASS. Report: current_query_text, last verdict, error_count trend, and best-guess next step for a human to pick up.

Never retry the exact same query verbatim. Never let the generator's own read of correctness substitute for the verifier's schema-check + execution result.
```

### 4. Data-Quality Assertion Loop — Agent-Loop Prompt

- **When:** Use when <TABLE_NAME> in <DATABASE_NAME> is failing (or is suspected to fail) a fixed set of data-quality assertions — nulls where there shouldn't be, duplicate keys, referential-integrity breaks, values outside a valid range/enum, freshness lag — and an agent should drive the table from "failing N assertions" to "passing all of them" by making one remediation change at a time, without touching the assertions themselves.
- **Loop:** assess (read current assertion-suite report: which checks fail, on which rows) -> one action (one reversible remediation: one UPDATE/backfill scoped by a WHERE clause, one upstream transform/dbt-model fix, one constraint/dedup step) -> verify (re-run the fixed, independent assertion suite against the live table) -> decide (SUCCESS/BUDGET/NO-PROGRESS/BLOCKED)
- **Stop:** SUCCESS: every assertion in <ASSERTION_SUITE_CMD> returns PASS against <TABLE_NAME>, reconfirmed on a second consecutive run with no assertion flapping between runs. · BUDGET: max <MAX_ITERATIONS> remediation turns (default 8); each turn is exactly one remediation action + one suite run, regardless of how many rows it touches. · NO-PROGRESS: the count of failing assertions (or, if stuck on one assertion, the count of failing rows under it) does not strictly decrease for <K_FLAT_TURNS> consecutive turns (default 3) despite a genuinely different remediation each turn. · BLOCKED: halt immediately (don't spend a turn) when: fixing a failing assertion requires a write against a table/row range outside the agent's granted scope or above <ROW_CHANGE_APPROVAL_THRESHOLD> rows; the root cause is upstream of <TABLE_NAME> (a source system or an upstream pipeline the agent can't edit) and only a human/owning team can fix it; two assertions conflict (satisfying one necessarily breaks another, e.g. a NOT NULL default vs. a range check) and only a human can pick the resolution; or the assertion suite itself appears wrong (flags rows that are actually valid per business rules) — that's a suite-definition issue, not something to patch by editing the suite mid-loop.
- **Model:** Sonnet 5

```text
GOAL (frozen — do not renegotiate mid-loop):
Bring <TABLE_NAME> in <DATABASE_NAME> to a state where every assertion in the FIXED, pre-existing assertion suite <ASSERTION_SUITE_CMD> (e.g. a dbt test suite, Great Expectations checkpoint, or a hand-written SQL assertion file — not-null checks, uniqueness/PK checks, referential-integrity checks against <PARENT_TABLES>, accepted-range/enum checks on <RANGE_CHECKED_COLUMNS>, freshness check on <FRESHNESS_COLUMN> within <FRESHNESS_SLA>) returns PASS, without editing the assertion suite itself to make it pass. The suite is authored and frozen BEFORE this loop starts (by a human or a prior, separate step) — the loop's job is to fix the DATA and/or the pipeline producing it, never to relax the check.

INDEPENDENCE CONTRACT (must hold every turn):
- The REMEDIATOR (you) proposes and applies one data/pipeline fix per turn.
- The VERIFIER is <ASSERTION_SUITE_CMD> — a fixed, separately-maintained assertion runner the agent may READ (to see which checks/rows fail) but must never EDIT, disable, loosen a threshold in, or add exceptions to during this loop. If a check looks wrong, that's a BLOCKED condition to raise to a human, not something to patch.
- Every verify step actually re-runs <ASSERTION_SUITE_CMD> against the live table state — never infer a PASS from "the UPDATE looked right" or from re-reading the remediation SQL.

PER-TURN SHAPE:
1. ASSESS — read the prior turn's assertion-suite report (or the initial report on turn 1): which named assertions FAIL, how many rows each affects, and (if available) example offending rows/keys. Pick the single failing assertion with the most rows affected (or the one blocking the others, e.g. fix referential-integrity breaks before uniqueness) as this turn's target.
2. ONE ACTION — apply exactly one reversible remediation aimed at that target:
   - a scoped UPDATE/backfill with an explicit WHERE clause (never an unscoped table-wide UPDATE)
   - a fix to one upstream transform/dbt model/ETL step producing the bad values (one model, one commit)
   - a dedup pass keyed on the declared primary/unique key
   - a corrective cast/normalize step for one out-of-range/enum column
   Do not bundle fixes for two different assertions in one turn — if the next verify regresses something that had passed, you need to know which single change did it. Never modify <ASSERTION_SUITE_CMD> itself.
3. VERIFY — re-run <ASSERTION_SUITE_CMD> in full against the live table. Record: turn number, remediation applied, full pass/fail list (not just the one you targeted — a fix can regress an assertion that was previously passing), failing-row counts per still-failing assertion.
4. DECIDE — apply the Stop line below. If none fire, update carry-forward state and proceed.

APPROVAL GATE (irreversible/paid actions):
- Any UPDATE/DELETE/backfill touching more than <ROW_CHANGE_APPROVAL_THRESHOLD> rows, any DDL (adding a constraint, altering a column type), and any change to a table outside <TABLE_NAME>'s own pipeline ownership requires explicit human approval before execution — propose the exact statement and its expected row impact, then wait.
- If the assertion suite run itself incurs metered/paid cost above <COST_THRESHOLD> per run, surface that and get approval before each additional run beyond the first.

CARRY-FORWARD STATE (compact, written every turn):
- turn_number / <MAX_ITERATIONS>
- failing_assertions: {assertion_name -> failing_row_count} from the latest suite run (empty dict = SUCCESS)
- failing_count_history: [turn1_total_failing_rows, turn2_total, ...] (strictly tracked, used for NO-PROGRESS)
- remediations_tried: list of (turn, assertion_targeted, one-line fix, verdict: fixed / regressed-another / no-effect) — ban repeating a no-effect or regressed fix verbatim
- currently_passing_assertions (so a regression is visible immediately, not just net-count)
- any remediation pending human approval (row-threshold or DDL)
- suspected upstream/root-cause note if a failure looks like it originates outside <TABLE_NAME>

ANTI-OSCILLATION RULE:
Before applying a remediation, check remediations_tried: if the proposed fix exactly repeats a prior turn's fix for the same assertion, or flips the table between two states that alternately satisfy/break two conflicting assertions (A->B->A), do not apply it — count it as a forced NO-PROGRESS strike (2 strikes = HALT under NO-PROGRESS regardless of the K-turn window). A genuine retry is only valid if it targets the failure with a materially different mechanism (e.g. fixing the upstream model instead of patching rows again).

STOP — halt on the FIRST that fires, checked in this order every turn:
1. SUCCESS: <ASSERTION_SUITE_CMD> returns PASS on every assertion, reconfirmed on one additional consecutive run with identical PASS results (no flapping). Report: final failing_assertions (empty), remediations_tried log, and the reconfirming run's timestamp/output.
2. BLOCKED: the next fix requires a write outside granted scope or over <ROW_CHANGE_APPROVAL_THRESHOLD> rows without approval; the root cause sits upstream of <TABLE_NAME> in a system the agent can't edit; two assertions are mutually exclusive and need a human tiebreak; or an assertion appears to be checking the wrong thing (business-rule mismatch) — flag it, don't silently work around it. Report: exactly what's blocking and what a human needs to decide or grant.
3. NO-PROGRESS: total failing-row count across all assertions does not strictly decrease for <K_FLAT_TURNS> consecutive turns despite different remediation mechanisms each turn, or 2 anti-oscillation strikes accrue. Report: remediations_tried, current failing_assertions, and a recommendation for what's actually needed (e.g. "this requires an upstream fix in <SOURCE_SYSTEM>, out of this loop's scope").
4. BUDGET: turn_number reaches <MAX_ITERATIONS> without full PASS. Report: failing_assertions remaining, failing_count_history trend, remediations_tried, and best-guess next step for a human.

Never edit or relax <ASSERTION_SUITE_CMD> to reach PASS. Never let the remediator's own read of "the data looks fixed" substitute for an actual re-run of the fixed assertion suite.
```

### 5. Metric Reconciliation Across Two Independent Computation Paths — Agent-Loop Prompt

- **When:** Use when <METRIC_NAME> is computed two different ways — e.g. a warehouse SQL model vs. a source-of-truth report, a new pipeline vs. the legacy one it's replacing, an aggregation query vs. a row-level recompute — and they must agree within a declared tolerance before either is trusted, and an agent should drive the two paths into agreement one change at a time without ever declaring "close enough" on its own read of the numbers.
- **Loop:** assess (read the last reconciliation report: which slice(s) diverge, by how much, in which direction) -> one action (one reversible fix to exactly one path's logic, or a scoped filter/timezone/grain correction) -> verify (independent reconciliation script recomputes BOTH paths from scratch and diffs them — not the agent re-reading two numbers) -> decide (SUCCESS/BUDGET/NO-PROGRESS/BLOCKED)
- **Stop:** SUCCESS: the independent reconciliation script reports |path_A - path_B| / path_B <= <TOLERANCE_PCT> (or absolute diff <= <TOLERANCE_ABS> for near-zero denominators) for <METRIC_NAME> on every slice in <RECONCILIATION_DIMENSIONS> (e.g. per day, per region, per product), over <RECONCILIATION_WINDOW>, reconfirmed on one additional consecutive run with no slice flipping. · BUDGET: max <MAX_ITERATIONS> turns (default 8); each turn is exactly one fix to one path, regardless of how many slices it touches. · NO-PROGRESS: the count of out-of-tolerance slices (or, if stuck on one slice, its absolute diff) does not strictly decrease for <K_FLAT_TURNS> consecutive turns (default 3) despite a genuinely different fix mechanism each turn. · BLOCKED: halt immediately (don't spend a turn) when: the divergence traces to a definitional difference between the two paths that has no objectively correct resolution (e.g. path A counts refunds as negative revenue, path B excludes them entirely) and only a human/business owner can pick the canonical definition; one path pulls from a source system the agent cannot edit or query further; the two paths use different time windows/timezones/currencies that cannot be normalized without a human-confirmed conversion rule; or reconciling would require a write to production data (rather than to query/model logic) without explicit approval.
- **Model:** Sonnet 5

```text
GOAL (frozen — do not renegotiate mid-loop):
Bring two independently-computed values of <METRIC_NAME> — PATH_A: <PATH_A_DESCRIPTION_AND_QUERY_OR_MODEL> and PATH_B: <PATH_B_DESCRIPTION_AND_QUERY_OR_MODEL> — into agreement within <TOLERANCE_PCT>% (or <TOLERANCE_ABS> absolute, whichever the metric calls for) on every slice in <RECONCILIATION_DIMENSIONS> over <RECONCILIATION_WINDOW>, WITHOUT changing the tolerance, the reconciliation script, or which path is treated as which — those are fixed before the loop starts. The loop's job is to fix whichever path's logic is wrong (or genuinely reconcile a definitional gap with human input), never to narrow the diff by loosening the check.

INDEPENDENCE CONTRACT (must hold every turn):
- The FIXER (you) proposes and applies exactly one change to one path's query/model logic (or a documented, human-approved definitional adjustment) per turn.
- The VERIFIER is <RECONCILIATION_SCRIPT_CMD> — a separately-maintained script that, every run: (1) executes PATH_A fresh, (2) executes PATH_B fresh, (3) joins them on <RECONCILIATION_DIMENSIONS>, (4) computes the diff and pct-diff per slice, (5) reports PASS/FAIL per slice against <TOLERANCE_PCT>/<TOLERANCE_ABS>. The agent may read this script's output but must never edit its tolerance, its join keys, or which query it treats as authoritative during this loop.
- Never accept "the two totals look close" as verification — every verify step re-runs both paths from scratch through the script. A stale number from three turns ago does not count.

PER-TURN SHAPE:
1. ASSESS — read the prior turn's reconciliation report (or the initial run on turn 1): which slices FAIL, the diff and direction (A>B or A<B) per failing slice, and whether the pattern is uniform (suggests one systematic bug, e.g. a timezone or double-count) or scattered (suggests several independent issues). Pick the single highest-impact divergent pattern as this turn's target.
2. ONE ACTION — apply exactly one reversible change addressing that pattern, to exactly one path:
   - fix one join/filter/grain issue in the query or model (e.g. a missing dedup, a wrong date-truncation, an inclusive/exclusive boundary)
   - correct one unit/timezone/currency conversion
   - fix one aggregation-level mismatch (e.g. path A sums pre-discount, path B post-discount — align to the agreed definition)
   Change only the path implicated by this turn's pattern — do not edit both paths in the same turn, and do not touch a slice/dimension that already passed.
3. VERIFY — run <RECONCILIATION_SCRIPT_CMD> in full (fresh execution of both paths, not cached results). Record: turn number, change made + which path, full per-slice pass/fail list (not just the targeted slice — a fix can regress a slice that previously passed), diff magnitude and direction per still-failing slice.
4. DECIDE — apply the Stop line below. If none fire, update carry-forward state and proceed to next turn.

APPROVAL GATE (irreversible/paid actions or human-only decisions):
- If a divergence turns out to be definitional (both paths are "correct" under different, defensible definitions of <METRIC_NAME>) rather than a bug, do not silently pick one — surface both definitions and the resulting numbers, and treat as BLOCKED pending a human's canonical-definition call.
- Any change requiring a write to production data (as opposed to query/model/view logic), or a change to a shared upstream table both paths depend on, requires explicit human approval before execution.
- If either path's execution incurs metered/paid cost above <COST_THRESHOLD> per run, get approval before repeated runs beyond the first.

CARRY-FORWARD STATE (compact, written every turn):
- turn_number / <MAX_ITERATIONS>
- failing_slices: {slice_key -> (diff, pct_diff, direction A>B|A<B)} from the latest reconciliation run (empty dict = SUCCESS)
- failing_count_history: [turn1_count, turn2_count, ...] (strictly tracked, used for NO-PROGRESS)
- fixes_tried: list of (turn, path_targeted, one-line change, verdict: fixed / regressed-another-slice / no-effect) — ban repeating a no-effect or regressed fix verbatim
- currently_passing_slices (so a regression is visible immediately, not just net-count)
- any suspected definitional gap flagged for human tiebreak, with both paths' numbers and reasoning stated plainly
- any change currently pending human approval (prod write, shared upstream table, paid re-run)

ANTI-OSCILLATION RULE:
Before applying a fix, check fixes_tried: if the proposed change exactly repeats a prior turn's fix for the same slice/pattern, or flips a slice between two states that alternately satisfy path A's assumption and path B's assumption (A->B->A) without resolving which is actually correct, do not apply it — count it as a forced NO-PROGRESS strike (2 strikes = HALT under NO-PROGRESS regardless of the K-turn window). A genuine retry is only valid if it targets the divergence with a materially different mechanism (e.g. fixing the upstream source instead of re-patching the same join again).

STOP — halt on the FIRST that fires, checked in this order every turn:
1. SUCCESS: <RECONCILIATION_SCRIPT_CMD> reports every slice in <RECONCILIATION_DIMENSIONS> within <TOLERANCE_PCT>/<TOLERANCE_ABS>, reconfirmed on one additional consecutive run with identical PASS results (no slice flapping). Report: final failing_slices (empty), fixes_tried log, and the reconfirming run's timestamp/output.
2. BLOCKED: a divergence is definitional and needs a human to pick the canonical definition of <METRIC_NAME>; one path depends on a source system the agent can't query/edit further; time window/timezone/currency normalization needs a human-confirmed rule; or the only remaining fix requires a production write or shared-table change without approval. Report: exactly what's blocking, both paths' current numbers on the disputed slice(s), and what a human needs to decide or grant.
3. NO-PROGRESS: total out-of-tolerance slice count (or the single stuck slice's diff) does not strictly decrease for <K_FLAT_TURNS> consecutive turns despite different fix mechanisms each turn, or 2 anti-oscillation strikes accrue. Report: fixes_tried, current failing_slices, and a recommendation for what's actually needed (e.g. "this needs an upstream fix in <SOURCE_SYSTEM>, out of this loop's scope").
4. BUDGET: turn_number reaches <MAX_ITERATIONS> without full reconciliation. Report: failing_slices remaining, failing_count_history trend, fixes_tried, and best-guess next step for a human.

Never edit <RECONCILIATION_SCRIPT_CMD>'s tolerance, join keys, or authoritative-path designation to reach PASS. Never let the fixer's own read of "the numbers look close now" substitute for an actual fresh re-run of both paths through the independent reconciliation script.
```
