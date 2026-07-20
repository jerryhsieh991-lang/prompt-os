# Documentation Verification

`doc-verification` — 2 loop prompts.

### 1. Runnable-Docs Doctest Loop

- **When:** Your documentation is full of code examples that may have silently gone stale against the current code — imports moved, APIs renamed, printed output changed — and you need every fenced snippet to actually execute green, fixing one at a time.
- **Loop:** assess runner's failing-example list -> fix ONE example (doc snippet, or the code if code is the contract) -> re-run the example-runner over all snippets -> commit on improvement / git reset on regression -> decide
- **Stop:** SUCCESS: every extracted example executes clean with matching output · BUDGET: `<MAX_ITERATIONS>` reached · NO-PROGRESS: failing-example count unchanged for 3 straight turns · BLOCKED: an example needs the doc author's intent or an unavailable runtime dependency
- **Model:** Extract-and-run is mechanical — a cheaper model drives most snippet fixes fine since the runner's exit code is ground truth. Escalate to a top-tier model when a failing example reveals the code itself is the contract and genuinely wrong, so deciding "fix doc vs fix code" needs real intent reasoning. The verifier MUST be the example-runner, never the model's read of the snippet: a snippet that "looks correct" can still import a renamed module or print stale output — only executing it against live code proves it runs, which is why self-inspection cannot close this loop.

```text
GOAL (frozen — do not redefine mid-loop)
Every code example/snippet in <DOCS_GLOB> executes successfully against the current codebase at <REPO>, verified by <EXAMPLE_RUNNER_CMD> (a doctest-style / tested-examples tool that EXTRACTS each fenced snippet, runs it, and compares actual output + exit code to the documented/expected output). "Passing" for one example = the runner parses it, executes it with exit 0, and its real output matches what the docs claim it prints — not "it reads plausibly". Fix exactly ONE failing or stale example per turn: correct the DOC snippet to match how the code actually behaves (the code is ground truth), UNLESS the code is itself the documented contract and is genuinely broken — only then fix the code. Do not add new examples or expand scope.

INDEPENDENT VERIFIER
<EXAMPLE_RUNNER_CMD> is the sole arbiter of "done" — it extracts every snippet from <DOCS_GLOB> and runs them against <REPO>. A human read-through, or the model re-reading its own edit, is NOT proof: a snippet can look perfectly idiomatic and still import a moved module, call a removed method, or assert stale output. Only extracting and executing the snippet against the live code detects that. Never grade with the same text you're editing — read the runner's pass/fail, not your own confidence.

PER-TURN SHAPE
1. ASSESS — run <EXAMPLE_RUNNER_CMD>, read the list of failing/stale examples, pick the ONE cheapest to fix in isolation (note whether the fault is a stale doc or genuinely broken contract code).
2. ONE ACTION — make the smallest reversible change to that ONE example: update the snippet to match real behavior, OR (only if the code is the published contract and wrong) fix the code. Never touch a second example this turn.
3. VERIFY — run <EXAMPLE_RUNNER_CMD> over ALL snippets (not just the one) so a fix that breaks a sibling example is caught immediately.
4. DECIDE — if the failing count dropped and nothing regressed, commit; if it rose or held, git reset and try a materially different fix next turn; if the example needs author intent or a missing runtime, park it and mark BLOCKED; escalate after 3 stalled turns.

CARRY-FORWARD STATE (compact)
Failing/stale example count, the specific example in focus, whether each is a doc-fix or code-fix, approaches already ruled out on it, and iterations left of <MAX_ITERATIONS>.

ACTION BAN
Never mark an example "verified" without actually running it through <EXAMPLE_RUNNER_CMD>. Never delete, comment out, or `# doctest: +SKIP` a hard example just to make the runner pass. Never loosen the expected-output assertion to force a match. Never edit product code to satisfy a wrong doc when the code is NOT the contract — fix the doc. Never batch multiple example fixes into one turn. Never retry the exact failed edit verbatim.

STOP — halt on the FIRST of:
SUCCESS (every extracted example runs clean, output matches, zero skips) | BUDGET (<MAX_ITERATIONS> reached) | NO-PROGRESS (failing-example count unchanged for 3 straight turns — escalate with what's been tried, don't grind) | BLOCKED (an example needs the doc author's intent, or an unavailable runtime/dependency the runner can't satisfy — surface it and wait)
```

### 2. API-Reference Drift-Diff Loop

- **When:** Your API reference (docstrings, README option tables, OpenAPI spec, CLI docs) has drifted from the code — renamed params, removed endpoints, changed defaults, wrong types — and you need every documented symbol to match the real signature, one entry per turn.
- **Loop:** assess the doc-vs-code drift report -> fix ONE drifted entry (doc to match code, or code if code is the published contract) -> re-run the introspection diff -> commit on improvement / git reset on regression -> decide
- **Stop:** SUCCESS: zero drift — every documented symbol matches the live signature/behavior · BUDGET: `<MAX_ITERATIONS>` reached · NO-PROGRESS: drift-entry count unchanged for 3 straight turns · BLOCKED: a mismatch needs a product decision on which side is canonical
- **Model:** Mechanical entry-by-entry reconciliation suits a cheaper, high-volume model — the diff report names each mismatch. Escalate to a top-tier model when a drift reveals a genuine contract breach (served behavior violates the published spec) where deciding "fix doc vs fix code" is a backward-compat judgment, not a substitution. The verifier MUST be a mechanical introspection diff, never side-by-side reading: reading doc and code together is exactly the human process that let the drift accumulate — only reflecting the actual symbol table / parsing real `--help` / diffing generated-vs-served OpenAPI is immune to plausible-but-stale prose, so self-inspection cannot certify truthfulness.

```text
GOAL (frozen — do not redefine mid-loop)
Every documented symbol/endpoint/flag/option in <API_REFERENCE> exists in the code at <CODEBASE> with the documented signature and behavior — no renamed/removed params, no wrong defaults, no phantom endpoints, no type mismatches — verified by <DOC_VS_CODE_CHECKER> (signature introspection via reflection, OpenAPI-spec-vs-implementation diff against <OPENAPI_SPEC>, and/or CLI `--help` diff). "Truthful" for one entry = the checker finds the symbol in code and its real signature/default/type/route matches what the doc claims. Fix exactly ONE drift entry per turn: correct the DOC to match the code (the code is ground truth), UNLESS the code is the published/versioned contract and its behavior violates that contract — only then fix the code. Do not document new symbols or expand scope.

INDEPENDENT VERIFIER
<DOC_VS_CODE_CHECKER> is the sole arbiter — it introspects the live code (reflects the actual function signatures, parses the real `--help`, generates OpenAPI from the running app and diffs it against <API_REFERENCE>/<OPENAPI_SPEC>) and emits a mechanical drift list. A human, or the model, reading the doc beside the code is NOT proof: that side-by-side read is the very process that let the drift accumulate, and a stale default or dropped param reads as plausible. Only introspecting the real symbol table catches it. Grade with the checker's diff, not your own re-reading.

PER-TURN SHAPE
1. ASSESS — run <DOC_VS_CODE_CHECKER>, read the drift list, pick the ONE entry cheapest to reconcile (classify it: stale doc vs genuine contract breach in code).
2. ONE ACTION — make the smallest reversible change to that ONE entry: update the doc/spec to match the real signature, OR (only if the code is the versioned contract and is breaking it) fix the code. Never touch a second entry this turn.
3. VERIFY — run <DOC_VS_CODE_CHECKER> across ALL documented symbols so a fix that introduces a new mismatch is caught immediately.
4. DECIDE — if the drift count dropped and nothing regressed, commit; if it rose or held, git reset and try a different reconciliation next turn; if which side is canonical needs a product owner, park it and mark BLOCKED; escalate after 3 stalled turns.

CARRY-FORWARD STATE (compact)
Drift-entry count, the specific entry in focus, its classification (doc-fix vs code-fix), reconciliations already ruled out, and iterations left of <MAX_ITERATIONS>.

ACTION BAN
Never mark an entry reconciled without re-running <DOC_VS_CODE_CHECKER>. Never delete a documented symbol from <API_REFERENCE> just to clear a drift when the symbol still exists in code (that hides real API, it doesn't fix drift). Never edit code to match a wrong doc when the code is NOT the contract — fix the doc. Never edit the checker/introspection config to suppress a mismatch. Never batch multiple entries into one turn. Never retry the same failed reconciliation verbatim.

STOP — halt on the FIRST of:
SUCCESS (checker reports zero drift — every documented symbol matches the live signature/behavior) | BUDGET (<MAX_ITERATIONS> reached) | NO-PROGRESS (drift-entry count unchanged for 3 straight turns — escalate with what's been tried, don't grind) | BLOCKED (a mismatch needs a product decision on which side is canonical, or the symbol lives in an un-introspectable external dependency — surface it and wait)
```
