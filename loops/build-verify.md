# Build → Verify

`build-verify` — 8 loop prompts.

### 1. TDD Red-to-Green Loop (fix a failing test suite)

- **When:** You have a codebase with a test suite that's currently failing (broken build, half-finished feature, or tests written ahead of implementation) and need to drive it to fully green without touching the tests themselves.
- **Loop:** assess current fail list -> pick ONE cheapest-to-fix failing test -> make the smallest source change -> run the FULL suite as verifier -> commit on improvement / git reset on regression -> decide continue/stop
- **Stop:** SUCCESS: full suite passes, zero failures/skips · BUDGET: <MAX_ITERATIONS> reached · NO-PROGRESS: fail count unchanged for 3 straight turns · BLOCKED: a test appears wrong or the fix needs a human spec decision
- **Model:** Mechanical, high-volume error-chasing — a cheaper model (Sonnet/Haiku-class) handles most repos fine since the test output is the ground truth. Escalate to a top-tier model like Fable 5 only for large/legacy codebases where failures are tangled (one root cause manifesting as many symptoms) and picking the 'cheapest fix' requires real dependency-graph reasoning.

```text
Goal (frozen): the full test suite in this repo passes with zero failures and zero skips, verified by running <test command> — nothing else counts as done. Do not edit test files; if a test looks wrong, flag it as BLOCKED rather than changing it.

Each turn: (1) run the test suite, read the failure list, and pick the ONE failing test that is cheapest to fix without touching others; (2) make the smallest code change that addresses it; (3) re-run the full suite as your verifier — never trust your own read of the diff; (4) if failures dropped, commit; if failures rose or stayed equal, git reset the change and try a different approach next turn (never repeat the same fix verbatim).

Carry forward each turn: pass/fail count, the one test you're targeting, what you already tried on it, and iterations remaining out of <MAX_ITERATIONS>.

Stop and report on the FIRST of: all green (SUCCESS); <MAX_ITERATIONS> reached (BUDGET); fail count unchanged for 3 straight turns (NO-PROGRESS — halt, don't keep grinding); or a fix requires a decision only a human can make (BLOCKED).
```

### 2. Regression-First Bug Fix Loop

- **When:** A bug report with repro steps exists and you must first codify it as a failing test, then fix the root cause until that test and the pre-existing suite both pass — prevents 'fixed it' claims with no proof.
- **Loop:** reproduce -> write ONE frozen failing regression test -> ONE root-cause source change -> run regression test + full suite -> commit on improvement / revert on regression -> decide
- **Stop:** SUCCESS: new regression test AND full suite both green · BUDGET: <MAX_ITERATIONS> reached · NO-PROGRESS: same failure signature for 3 turns · BLOCKED: bug won't reproduce, or fix requires a design decision
- **Model:** Distinguishing root cause from symptom patch is a judgment call, not a mechanical one — worth a stronger model. Use a top-tier model (e.g. Fable 5) for concurrency/race-condition/heisenbugs where the repro itself is flaky; a mid-tier model is fine for deterministic, easily-reproduced bugs.

```text
Goal (frozen): reproduce bug <BUG_DESCRIPTION>, write ONE new regression test that fails because of it, then make that test pass AND keep the pre-existing suite green — verified by `<test command>`. Write the regression test first and freeze it before touching source; don't loosen its assertions later just to force a pass.

Turn shape: assess (current failure of the regression test, current state of the full suite) -> make ONE reversible source change aimed at the root cause, not a symptom patch -> run the regression test + full suite as the verifier -> if both improve, commit; if either regresses versus last known-good, git reset and try a materially different approach.

Carry forward: the regression test's current pass/fail, full-suite pass/fail count, root-cause hypotheses already ruled out, iterations left of <MAX_ITERATIONS>.

Stop on the first trip: SUCCESS — regression test and full suite both green; BUDGET — <MAX_ITERATIONS> hit; NO-PROGRESS — same failure signature 3 turns running (escalate with what's been tried, don't keep grinding); BLOCKED — bug won't reproduce or fix requires a design decision — surface it and wait for a human.
```

### 3. Embedded Firmware Compile-Flash-Verify Loop

- **When:** Iterating on microcontroller firmware (PlatformIO/Arduino/ESP32-class) where 'build' means compile+link within a flash/RAM budget and 'verify' means an actual flash plus a real serial-log or hardware-probe check — compiling alone is not proof it works.
- **Loop:** assess last build stats + serial capture -> ONE source/config change -> compile -> flash + capture real serial output -> commit on improvement / revert on regression -> decide
- **Stop:** SUCCESS: build in-budget AND serial log confirms expected behavior within timeout · BUDGET: <MAX_ITERATIONS> reached · NO-PROGRESS: identical serial output/error for 3 turns · BLOCKED: device won't enumerate/respond, or needs a hardware fix
- **Model:** Compile-error fixing is mechanical and fine on a cheaper/faster model. Escalate to a stronger model (Fable 5) when the loop stalls on timing bugs, ISR/interrupt interactions, or I2C/SPI protocol quirks — these need real hardware-semantics reasoning, not pattern matching on compiler output.

```text
Goal (frozen): `<build command, e.g. pio run>` compiles clean within flash/RAM budget (<X% flash, <Y% RAM), AND after flashing, the serial monitor shows <EXPECTED_SIGNAL> within <TIMEOUT>s — both required, compiling alone is not done. Freeze the wiring/pin assumptions; don't redesign the circuit mid-loop.

Each turn: assess the last build output and serial capture -> make ONE change (source, config, or wiring note) -> compile -> if compile fails, that's your verifier signal, stop there for the turn; if it compiles, flash the device and capture real serial output for <TIMEOUT>s as the independent check (not your prediction of what it'll print) -> commit on improvement, git reset on regression or ambiguous result.

Carry forward: last flash/RAM %, last serial excerpt, what's been tried, iterations left of <MAX_ITERATIONS>.

Stop on first trip: SUCCESS — compiles in-budget and serial confirms expected behavior; BUDGET — <MAX_ITERATIONS>; NO-PROGRESS — identical serial output/error 3 turns running; BLOCKED — device won't enumerate, no serial response, or a hardware fix is needed — halt and hand off.
```

### 4. Dependency / Runtime Upgrade Loop

- **When:** Bumping a library, framework, or language runtime version and needing the build and test suite to stay green with zero behavior change — explicitly not the moment to adopt new APIs or refactor.
- **Loop:** assess current break list from build+test -> fix ONE break (root cause, not downstream symptom) -> rebuild/retest -> commit on improvement / revert on regression -> decide
- **Stop:** SUCCESS: build succeeds and full suite passes on new version, no test edits · BUDGET: <MAX_ITERATIONS> reached · NO-PROGRESS: error count flat for 3 turns · BLOCKED: an API was removed with no compatible replacement
- **Model:** Mostly mechanical error-chasing across many small call sites — a cheaper, high-volume model is cost-effective here. Escalate to a stronger model only when a major-version bump removes/redesigns a core API and the workaround requires architectural judgment rather than a mechanical substitution.

```text
Goal (frozen): with dependency/runtime pinned to <NEW_VERSION>, `<build command>` succeeds and the full test suite passes with zero behavior changes — verified by build exit code + test suite, not by reading the changelog. Scope is upgrade-compatibility only: do not adopt new APIs, refactor, or fix unrelated warnings; park those ideas, don't act on them.

Turn shape: assess current compile/test errors -> pick the ONE error highest in the dependency chain (fixing root causes fixes downstream errors for free) -> apply the minimal compatibility shim or call-site update -> rebuild and rerun the full suite as verifier -> commit if error count dropped, git reset if it rose, and change approach rather than retry the same shim.

Carry forward: remaining error count, the one error being targeted, shims already tried, budget left of <MAX_ITERATIONS>.

Stop on first trip: SUCCESS — clean build, full suite green; BUDGET — <MAX_ITERATIONS> reached; NO-PROGRESS — error count flat for 3 turns; BLOCKED — the new version removed an API with no compatible replacement, needs a human call on the workaround.
```

### 5. API-Contract Implementation Loop

- **When:** Implementing a service/endpoint against a fixed contract (OpenAPI spec, Pact/contract tests, or a golden request-response fixture set), where the contract test suite is the independent verifier and must never be edited to match the code.
- **Loop:** assess failing contract cases -> ONE handler-behavior change -> run the full contract suite -> commit on improvement / revert on regression -> decide
- **Stop:** SUCCESS: 100% of contract test cases pass · BUDGET: <MAX_ITERATIONS> reached · NO-PROGRESS: pass count unchanged for 3 turns · BLOCKED: the contract itself looks ambiguous, contradictory, or unsatisfiable
- **Model:** Cheaper models handle CRUD-shaped contracts well. Escalate to a stronger model (Fable 5) when the spec has subtle semantics — conditional fields, versioning, auth edge cases — where misreading the contract produces a plausible-looking but wrong implementation.

```text
Goal (frozen): every case in the contract test suite `<contract test command>` against spec <SPEC_FILE/PACT_FILE> passes — that suite is the sole verifier and is off-limits for editing. If a contract case looks wrong, report it as BLOCKED rather than 'fixing' the contract to match your code.

Each turn: assess which contract cases fail and why -> implement the smallest server-side change that satisfies ONE failing case without breaking passing ones -> run the full contract suite (not just the case you targeted) -> commit if pass count rose and nothing regressed, else git reset and pick a different implementation strategy next turn.

Carry forward compactly: pass/fail count, the specific case in focus, approaches already tried on it, iterations remaining of <MAX_ITERATIONS>.

Stop on the first that trips: SUCCESS — 100% contract cases green; BUDGET — <MAX_ITERATIONS> exhausted; NO-PROGRESS — pass count unchanged 3 turns straight, don't keep guessing at the same case, escalate; BLOCKED — the spec itself is ambiguous, contradictory, or requires a backend/data dependency you don't have — stop and ask.
```

### 6. Performance-Budget Optimization Loop

- **When:** Optimizing code to meet a fixed, measurable performance target (latency, throughput, memory) where a benchmark harness distinct from the code being optimized is the verifier — guards explicitly against gaming the benchmark.
- **Loop:** assess current metric vs threshold + correctness status -> ONE optimization -> rerun benchmark (3x) + correctness suite -> commit on improvement / revert on regression -> decide
- **Stop:** SUCCESS: metric meets/beats threshold AND correctness suite passes · BUDGET: <MAX_ITERATIONS> reached · NO-PROGRESS: metric within noise band or oscillating for 3 turns · BLOCKED: threshold appears architecturally infeasible
- **Model:** This is where model strength matters most — once cheap wins (obvious algorithmic fixes) are exhausted, further gains need creative restructuring. Start on a mid-tier model; if the metric plateaus and NO-PROGRESS is about to trip, that's exactly the signal to hand the remaining budget to a top-tier model like Fable 5 for a fresh strategic angle.

```text
Goal (frozen): `<benchmark command>` reports <METRIC> at or better than <THRESHOLD> (e.g., p95 latency <= 150ms), AND the existing correctness test suite still passes — both required. The benchmark harness is fixed and off-limits for tuning; don't hand-tune inputs or environment just to game the number.

Turn shape: assess current metric and correctness status vs last-known-good -> make ONE optimization (algorithmic, caching, batching, etc.) -> re-run the benchmark 3x for stability and the correctness suite -> if the metric improved (median of 3) and correctness held, commit; otherwise git reset and try a structurally different approach, not a tweak of the same one.

Carry forward: current metric trend (last 3 turns), correctness pass/fail, optimizations already tried and their measured effect, budget left of <MAX_ITERATIONS>.

Stop on first trip: SUCCESS — threshold met and correctness green; BUDGET — <MAX_ITERATIONS>; NO-PROGRESS — metric within noise band for 3 turns or oscillating between two values; BLOCKED — threshold appears infeasible under current architecture, needs a human decision on scope or infra.
```

### 7. Infrastructure-as-Code Plan-Apply Loop

- **When:** Iterating on Terraform/CloudFormation/Pulumi config toward a target state, where verification is `plan`/`validate`/policy-check output — not a live `apply` each turn — to keep every step cheap and reversible.
- **Loop:** assess last plan diff + policy findings -> ONE resource/config change -> validate + plan -> commit change on shrinking diff / revert on growth -> apply only once converged -> decide
- **Stop:** SUCCESS: plan shows zero unexpected diff AND policy check is clean · BUDGET: <MAX_ITERATIONS> reached · NO-PROGRESS: diff count unchanged for 3 turns · BLOCKED: missing credentials, quota, or an approval gate
- **Model:** Routine drift-closing (tagging, sizing, naming conventions) is fine on a cheaper model. Escalate to a stronger model when policy violations touch security/compliance boundaries (IAM scope, network exposure) where a wrong-but-plausible fix is costly — that needs careful judgment, not pattern completion.

```text
Goal (frozen): `terraform plan` (or equivalent) against <TARGET_STATE_DESCRIPTION> shows zero unexpected diff and `<policy/validate command>` reports no violations — that's the independent verifier, not your read of the .tf files. Do not run `apply` except on the turn where plan+policy are already clean and you're asked to converge; every other turn is plan-only, keeping the loop reversible.

Each turn: assess the last plan diff and policy findings -> make ONE resource/config change targeting the highest-impact diff line -> run validate then plan as verification -> if the diff shrank and no new violations appeared, keep the change (commit to version control); if the diff grew or violations increased, revert the file change.

Carry forward: current diff line count, current policy violation count, changes already tried, budget left of <MAX_ITERATIONS>.

Stop on first trip: SUCCESS — clean plan and clean policy check; BUDGET — <MAX_ITERATIONS>; NO-PROGRESS — diff count unchanged 3 turns; BLOCKED — missing credentials, quota, or an approval gate you can't clear — halt and hand off rather than guessing at permissions.
```

### 8. Data Pipeline Schema-Conformance Loop

- **When:** Implementing or fixing an ETL/transformation step that must produce output conforming to a frozen schema and matching a golden reference dataset within tolerance — verifier is schema validation plus a diff tool, independent of the transform code.
- **Loop:** assess schema violations + golden-diff mismatches -> ONE transform change -> re-run pipeline + both checks -> commit on improvement / revert on regression -> decide
- **Stop:** SUCCESS: schema valid AND golden diff within tolerance · BUDGET: <MAX_ITERATIONS> reached · NO-PROGRESS: combined error count flat for 3 turns · BLOCKED: golden dataset/schema looks stale, or upstream source shape changed
- **Model:** Mechanical field-mapping and type-coercion fixes suit a cheaper model well. Escalate to a stronger model when mismatches trace back to ambiguous business rules encoded in the golden dataset (e.g. edge-case rounding, null-handling semantics) that require inferring intent, not just matching bytes.

```text
Goal (frozen): running `<pipeline command>` on <INPUT_DATASET> produces output that validates against `<schema file>` with zero violations, and differs from `<golden_output>` by no more than <TOLERANCE> — verified by the schema validator and a diff tool, not by eyeballing rows. The golden dataset and schema are frozen; if either looks wrong, report BLOCKED instead of editing them to match your output.

Each turn: assess the current list of schema violations and golden-diff mismatches -> change ONE transformation step targeting the most common violation type -> re-run the full pipeline and both checks -> if violations + diff count dropped, commit; if they rose or held flat, revert and try a different transform, not a re-tuned version of the same one.

Carry forward: violation count, diff-mismatch count, the mismatch category in focus, approaches ruled out, budget left of <MAX_ITERATIONS>.

Stop on first trip: SUCCESS — schema clean and diff within tolerance; BUDGET — <MAX_ITERATIONS>; NO-PROGRESS — combined error count flat for 3 turns; BLOCKED — golden output or schema appears stale/incorrect, or upstream source data changed shape — escalate rather than chase a moving target.
```
