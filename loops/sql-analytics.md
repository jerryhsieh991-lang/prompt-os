# SQL / Analytics

`sql-analytics` — 3 loop prompts.

### 1. Text-to-SQL agent-loop prompt (SQL / Analytics family)

- **When:** User asks Claude to answer a natural-language analytics question against a database by generating and running SQL, in the style of the prompt-os loop library (e.g. /Users/jerryjerry/Projects/prompt-os/loops/*.md).
- **Loop:** assess -> one action (write/revise one SQL query) -> verify (execute query + run independent sanity-assertion checker) -> decide
- **Stop:** SUCCESS: The query executes without error against the target database AND the independent sanity-checker (a separate script/tool, not the model's own read of the output) confirms all of: (a) row count within the declared plausible range, (b) required columns non-null, (c) any declared numeric/date columns within their declared bounds, reconfirmed on the final run. · BUDGET: max_iterations query attempts (a hard cap on distinct query revisions this run may make). · NO-PROGRESS: Sanity-check pass count (0-3 of the assertion categories passing) is flat for 3 consecutive turns despite trying a different fix strategy each time (not the same edit repeated) — signals the loop should stop and escalate rather than keep guessing. · BLOCKED: The question is ambiguous against the schema (e.g. an entity/metric name matches 2+ plausible columns/tables with materially different results) and cannot be resolved without a human pick; OR a needed table/column does not exist in the schema; OR only a destructive/DDL statement could answer the question and no write-approval has been granted.
- **Model:** Sonnet/mid-tier is sufficient for mechanical SQL syntax fixes once schema and sanity bounds are fixed; escalate to a stronger reasoning model up front to interpret schema ambiguity and set the sanity-assertion bounds (row-count range, non-null columns, numeric/date ranges) before the loop starts — those choices are Goodhart-prone if left to the loop itself.

```text
### Text-to-SQL with Independent Sanity-Checked Result

- **When:** A natural-language analytics question must be answered by generating a SQL query against <database>, where "correct" isn't just "it ran" — the result also has to be plausible (right shape, right ranges) before it's trusted.
- **Loop:** assess prior attempt's failure mode (syntax error / empty result / sanity-check fail) -> write or revise exactly ONE SQL query -> execute it read-only, then run the independent sanity-checker against the result -> decide
- **Stop:** SUCCESS: query executes cleanly AND the sanity-checker confirms row-count range, non-null required columns, and declared numeric/date bounds all pass, reconfirmed on the final run · BUDGET: max_iterations query attempts reached · NO-PROGRESS: sanity-check pass count (0-3 categories) flat for 3 consecutive turns despite trying a different fix strategy each time · BLOCKED: the question is ambiguous against the schema (2+ plausible tables/columns with materially different results), a referenced table/column doesn't exist, or answering would require a write/DDL statement without approval
- **Model:** Sonnet/mid-tier handles syntax-fixing iterations fine once schema and sanity bounds are fixed up front. Use a stronger model (or a human) to write <schema_notes> disambiguation and set the sanity-assertion bounds before the loop starts — a wrong row-count range or missing non-null constraint lets a bad query pass silently.

``​`text
Goal (frozen): produce ONE SQL query against <database> (schema reference: <schema_notes>) that correctly answers "<nl_question>", where correctness is judged by an independent sanity-checker script (NOT the model re-reading its own output) confirming, on the query's actual result set: (a) row count falls within <expected_row_range>; (b) columns in <required_nonnull_columns> contain no NULLs; (c) any column in <numeric_date_bounds> falls within its declared min/max. Define <expected_row_range>, <required_nonnull_columns>, and <numeric_date_bounds> BEFORE the loop starts, from domain knowledge of the schema and question — not by peeking at a query's output and backfitting bounds to make it pass.

Per turn:
(1) assess — read the prior turn's failure mode if any: SQL syntax/execution error, empty or trivially-wrong result (e.g. 0 or 1 row for an aggregate that should return many), or a specific failed sanity category (row-count / non-null / range). If this is turn 1, assess the schema for the tables/columns the question needs.
(2) act — write or revise exactly ONE query. Change only what the prior failure implicates (e.g. a wrong JOIN, a missing WHERE filter, an incorrect aggregation grain) — do not rewrite the whole query from scratch each turn, and do not touch a part of the query that already passed its sanity category.
(3) verify — execute the query read-only (SELECT/read-only role; no INSERT/UPDATE/DELETE/DDL) against <database>, capture the result set, then run it through the independent sanity-checker tool/script — a mechanism separate from the model's own judgment of whether the numbers "look right."
(4) decide — if the checker confirms execution succeeded and all three sanity categories pass, run it once more to reconfirm, then report SUCCESS with the query and result summary. If it partially passes, keep the parts that passed and target the next turn's edit at the failing category only. If it regresses (a category that passed now fails), revert to the last passing query text before making the next edit.

Carry forward each turn: the current best query text, which of the 3 sanity categories currently pass/fail, the specific failure reason each turn (not just pass/fail), fix strategies already tried per failure mode (never retry the identical edit verbatim), iterations used, budget remaining.

Stop on the FIRST that trips: SUCCESS — query executes cleanly and the sanity-checker confirms row-count range, required non-null columns, and declared numeric/date bounds all pass, reconfirmed on a second run; BUDGET — <max_iterations> query attempts; NO-PROGRESS — sanity-check pass count unchanged for 3 consecutive turns despite a genuinely different fix strategy each turn (not A->B->A oscillation between two query variants); BLOCKED — the question is ambiguous against the schema and needs a human pick between 2+ plausible interpretations, a referenced table/column does not exist, or the only way to answer would require a write/DDL statement (requires explicit human approval before executing — never issue a write query to "fix" a read-only sanity failure).
``​`
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
