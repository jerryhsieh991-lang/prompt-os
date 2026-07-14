# Test Generation

`test-generation` — 8 loop prompts.

### 1. Coverage-Gap Closer

- **When:** General-purpose loop for a module/service with a coverage tool already wired up (Istanbul, coverage.py, JaCoCo, etc.) and a numeric target. Best default when the ask is simply 'raise coverage on X'.
- **Loop:** assess coverage report -> pick single largest uncovered region -> write ONE test -> run, confirm red-for-right-reason -> minimal code fix if needed -> full suite green + recheck coverage % -> commit or revert
- **Stop:** SUCCESS: coverage >= frozen threshold per the coverage tool · BUDGET: N turns or T minutes reached · NO-PROGRESS: coverage delta < 0.5% for 3 consecutive turns · BLOCKED: uncovered region needs an unavailable fixture/credential/human decision
- **Model:** Mechanical enumeration — a cheaper model (Sonnet/Haiku) handles this fine on small-to-medium codebases. Escalate to Opus/Fable only if the uncovered branches involve tangled conditional logic where 'minimal fix' is ambiguous.

```text
GOAL (frozen): raise this module's line+branch coverage to >= {THRESHOLD}% per the coverage tool's report at loop start; that report, not your judgment, defines 'uncovered.' VERIFIER: the coverage tool + full test suite — a test only counts if it fails before your fix/target code exists and passes after. LOOP (each turn): (1) run coverage report, pick the single largest uncovered region not yet attempted; (2) write ONE test for it — nothing else; (3) run it, confirm it fails for the right reason; (4) if needed, make the minimal code change to satisfy it; (5) rerun full suite green, rerun coverage, record new %; (6) commit if coverage rose, else `git reset` and note the dead end. Carry forward: threshold, current %, last 3 deltas, symbols already attempted. STOP on first: SUCCESS coverage>=threshold; BUDGET {N} turns/{T} minutes hit; NO-PROGRESS coverage delta <0.5% for 3 consecutive turns — change strategy or halt; BLOCKED region needs an unavailable fixture/credential/human call — surface it, don't guess.
```

### 2. Bug Regression Test Loop

- **When:** You have a fixed backlog of reported bugs (ticket IDs) and want a test-first fix pass: each bug proven reproducible, then closed with a permanent regression guard.
- **Loop:** pick next un-ticked bug -> write ONE reproducing test -> run, confirm red matches the reported symptom -> minimal fix -> full suite green -> commit + check off ticket
- **Stop:** SUCCESS: all M tickets have passing regression tests · BUDGET: turns/tokens exhausted · NO-PROGRESS: same ticket fails 3 distinct fix approaches · BLOCKED: bug not reproducible from ticket as written
- **Model:** Root-cause diagnosis quality matters here more than mechanics. Sonnet is fine for well-specified, shallow bugs; route gnarly/intermittent tickets to Opus or Fable 5 at higher effort so the '3 distinct approaches' arm actually explores different hypotheses instead of superficial variants.

```text
GOAL (frozen): every bug in this fixed list of {M} ticket IDs gets exactly one regression test that reproduces the reported failure and then passes after a minimal fix — the ticket list is frozen at turn 1, no new bugs added mid-run. VERIFIER: the test itself, run in CI/local runner — 'reproduces' means it fails BEFORE the fix in a way matching the ticket's described symptom, not just any red. LOOP: (1) pick the next un-ticked bug; (2) write one test that reproduces it exactly as described; (3) run, confirm red matches the reported symptom (not a typo in your test); (4) apply the smallest code change that turns it green; (5) rerun full suite to confirm no regressions; (6) commit, check off the ticket. Carry forward: ticket list with status, current ticket's failed-attempt count. STOP on first: SUCCESS all {M} tickets have passing regression tests; BUDGET turns/tokens exhausted; NO-PROGRESS same ticket fails 3 distinct fix approaches (not 3 retries of one approach); BLOCKED bug isn't reproducible from the ticket as written — escalate to human for repro steps.
```

### 3. Public API Contract Loop

- **When:** A library, SDK, or service has a defined public surface (exports, routes) with weak or missing behavioral tests. Use to guarantee every exposed symbol has at least a happy-path + error-path contract test.
- **Loop:** diff public surface vs existing tests -> pick first uncovered symbol -> write ONE contract test -> confirm it fails against a broken/stubbed impl -> confirm it passes against real impl -> commit
- **Stop:** SUCCESS: 100% of frozen surface list has contract tests · BUDGET: exhausted · NO-PROGRESS: same symbol untestable after 3 turns · BLOCKED: symbol's intended contract is undocumented/ambiguous
- **Model:** Mostly enumeration + boilerplate assertions — cheaper models handle the bulk fine. Use a stronger model only to pre-generate the frozen surface list and adjudicate ambiguous contracts before the loop starts.

```text
GOAL (frozen): every symbol in this module's public surface — exports/routes as enumerated by {tool, e.g. `__all__` diff or OpenAPI paths} at loop start — has >=1 contract test covering its documented happy path and its documented error case. The surface list is frozen; symbols added after turn 1 go to a backlog, not this run. VERIFIER: test runner only — a passing test that asserts nothing (e.g., no assertion, or asserts `true`) does not count; the verifier step must confirm the test fails if you comment out the implementation. LOOP: (1) diff surface list against existing tests, pick first uncovered symbol; (2) write ONE test (happy path OR error case, whichever is missing); (3) confirm it fails against a stubbed/broken implementation to prove it's real; (4) confirm it passes against actual code; (5) commit. Carry forward: surface checklist, per-symbol attempt count. STOP: SUCCESS 100% surface covered; BUDGET exhausted; NO-PROGRESS same symbol untestable after 3 turns; BLOCKED symbol's intended contract is undocumented/ambiguous — ask, don't invent behavior.
```

### 4. Mutation-Testing Strengthening Loop

- **When:** Coverage is already high but you suspect tests are weak (assertion-free, over-mocked). Use when a mutation-testing tool (Stryker, mutmut, PIT) is available and you need to prove tests actually catch bugs, not just execute lines.
- **Loop:** run mutation tool -> pick one surviving mutant -> strengthen/add ONE assertion -> rerun scoped mutation check -> confirm mutant dies + suite stays green -> commit or revert
- **Stop:** SUCCESS: mutation score >= frozen threshold · BUDGET: exhausted · NO-PROGRESS: same mutant survives 3 distinct assertion strategies -> flag as likely equivalent · BLOCKED: mutation tool crashes or needs config only a human can supply
- **Model:** Classifying equivalent vs. killable mutants requires real semantic judgment — this is where a weaker model will either loop forever chasing an equivalent mutant or wrongly declare victory. Prefer Opus/Fable 5 at higher effort for this one.

```text
GOAL (frozen): drive the mutation score for {target file/module} from its loop-start baseline up to >= {threshold}%, per the mutation-testing tool's own report — do NOT verify against the coverage number you were optimizing against test-by-test; mutation score is the independent signal precisely because it differs from line coverage (Goodhart guard). LOOP: (1) run the mutation tool, pick ONE surviving mutant not yet attempted; (2) write or strengthen exactly one assertion to kill it; (3) rerun the mutation tool scoped to that mutant, confirm it now dies while the rest of the suite stays green; (4) commit if it died and nothing broke, else revert and try a different assertion strategy (never the identical one twice). Carry forward: mutation score history, list of confirmed-equivalent mutants (skip these, don't re-attempt). STOP on first: SUCCESS score>=threshold; BUDGET exhausted; NO-PROGRESS same mutant survives 3 distinct assertion strategies — flag as likely equivalent and move on; BLOCKED tool crashes or needs config only a human can supply.
```

### 5. Property-Based Invariant Loop

- **When:** Pure functions or data transforms with real mathematical/structural invariants (parsers, serializers, sorters, codecs). Use when example-based tests already exist but haven't caught edge cases a generator would find.
- **Loop:** pick next function -> state ONE real invariant -> write property test -> run across K seeds, treat any counterexample as the fail signal -> fix function (or correct a wrong invariant, logged) -> rerun clean -> commit
- **Stop:** SUCCESS: every function has a property test stable across K seeds · BUDGET: exhausted · NO-PROGRESS: 3 turns with no new invariant found or fixed · BLOCKED: invariant requires a product/spec decision
- **Model:** Picking a real, non-vacuous invariant is the hard part — this is a judgment task, not mechanical enumeration. Favor a stronger model (Opus/Fable 5); a cheap model tends to write invariants that are trivially true and pass without ever testing anything.

```text
GOAL (frozen): every function in this fixed target list gets >=1 property-based test encoding a real documented invariant (round-trip, idempotence, commutativity, monotonicity — pick what actually holds, don't invent a fake one to pad coverage). VERIFIER: the property-test framework's own shrinker/runner across a fixed seed count {K}, not your read of the output — a property that passes because it's vacuous (e.g., trivially true for all inputs) doesn't count. LOOP: (1) pick next function without a property test; (2) state the invariant in one sentence before coding it; (3) write the property test; (4) run it — if it finds a counterexample, that IS your fail signal: either fix the function's minimal bug or, if the invariant itself was wrong, restate it (log this, don't silently redefine success); (5) rerun clean across {K} seeds; (6) commit. Carry forward: function list, invariant-per-function log, seeds run. STOP: SUCCESS all functions covered and stable across {K} seeds; BUDGET; NO-PROGRESS 3 turns with no new invariant found or fixed; BLOCKED invariant needs a product/spec decision.
```

### 6. Golden-Master Characterization Loop

- **When:** Pre-refactor safety net for legacy code with no/weak tests and unclear intended behavior. Use BEFORE a refactor-loop starts, never mixed with production-code changes in the same run.
- **Loop:** pick next uncovered entry point -> capture actual output as fixture -> assert against a deliberately wrong placeholder first (proves the test executes) -> swap in real fixture, confirm green -> commit fixture+test together
- **Stop:** SUCCESS: every frozen entry point has a passing characterization test · BUDGET: exhausted · NO-PROGRESS: same entry point yields different output on 3 consecutive captures · BLOCKED: nondeterminism needs a human decision on seeding/mocking
- **Model:** Low reasoning burden per turn (mostly capture-and-lock) — a cheap model runs this well at volume. Escalate only to triage the nondeterministic cases the loop flags as BLOCKED, where a human or stronger model decides how to seed/mock.

```text
GOAL (frozen): before any refactor begins, every public entry point of {legacy module}, per the entry-point list frozen at turn 1, has a passing characterization test locking in its CURRENT observed behavior — this loop changes zero production code. VERIFIER: the test suite, with a discipline substitute for red-green since there's no bug to fix: (a) capture actual output as a fixture, (b) first assert against a deliberately wrong placeholder to prove the test actually executes and would fail on drift, (c) then swap in the real captured fixture and confirm green. LOOP: (1) pick next uncovered entry point; (2) run it once, capture output as a golden fixture; (3) write the test with a wrong placeholder, confirm it fails; (4) swap in the real fixture, confirm it passes; (5) commit fixture+test together. Carry forward: entry-point checklist, flagged-nondeterministic list. STOP: SUCCESS all entry points captured; BUDGET; NO-PROGRESS same entry point produces different output on 3 consecutive captures (nondeterministic); BLOCKED nondeterminism needs a human decision on seeding/mocking before it can be characterized.
```

### 7. Negative-Path / Error-Contract Loop

- **When:** APIs or services with a spec (OpenAPI, documented exceptions, validation rules) where happy-path tests exist but error handling is under-tested or leaks internals (stack traces, wrong status codes).
- **Loop:** diff spec's declared error cases vs existing negative tests -> pick first uncovered case -> write ONE test triggering it -> confirm current failure (wrong status/leak/silent success) -> minimal handling fix -> confirm exact contract now met -> commit
- **Stop:** SUCCESS: every declared error case has a matching test · BUDGET: exhausted · NO-PROGRESS: same case unresolved after 3 distinct handling attempts · BLOCKED: spec ambiguous on expected error shape
- **Model:** Mostly mechanical against a well-formed spec — Sonnet-class handles it. If the spec itself is inconsistent or missing error shapes, escalate to a stronger model to resolve ambiguity before it becomes a BLOCKED-arm bottleneck.

```text
GOAL (frozen): every declared error case in {spec — OpenAPI error responses, documented exceptions, validation rules} as enumerated at loop start has exactly one negative test asserting the precise contract (status code, exception type, error body shape) — new error cases discovered mid-run go to a backlog, not this run. VERIFIER: the test suite hitting the real handler, not a mock of it. LOOP: (1) diff spec's declared error cases against existing negative tests, pick the first uncovered one; (2) write one test that triggers exactly that condition (bad input, missing auth, etc.); (3) run it, confirm it currently fails — wrong status, leaked stack trace, or silent 200 all count as a legitimate red; (4) add the minimal validation/handling to match the spec, nothing more; (5) confirm it now passes with the exact contract; (6) commit. Carry forward: error-case checklist, attempt count per case. STOP: SUCCESS all declared cases covered; BUDGET; NO-PROGRESS same case unresolved after 3 distinct handling attempts; BLOCKED spec is ambiguous about the expected error shape — ask, don't guess.
```

### 8. Concurrency & Flakiness Stress Loop

- **When:** Shared-state or concurrent code paths (counters, caches, queues, locks) where race conditions are suspected but not proven. Use when 'passes once' is not an acceptable bar and stability under repetition is the real requirement.
- **Loop:** pick next un-stressed path -> write ONE stress test (M-way parallel, K reps) -> run now, confirm nonzero failure rate proves the race -> minimal synchronization fix -> rerun K reps, confirm 0 failures -> commit
- **Stop:** SUCCESS: all frozen paths at 0/K failures over K reps · BUDGET: exhausted · NO-PROGRESS: same path still flaky after 3 distinct synchronization strategies · BLOCKED: fix requires infrastructure unavailable in this environment
- **Model:** Highest reasoning difficulty in this set — races require correct mental modeling of interleavings, not pattern matching. Use the strongest available model (Opus/Fable 5 at xhigh) per this environment's own escalation policy for hardest-unsolved-problem classes; a cheap model will likely apply a fix that masks rather than eliminates the race.

```text
GOAL (frozen): every path in this fixed list of shared-state/concurrent code has a stress test that runs {M} parallel invocations, repeated {K} consecutive times, with 0 invariant violations (e.g., no double-write, exact counter) — a single green run does NOT count as done; the exit metric is 0/{K} failures. VERIFIER: the stress harness's own pass/fail count across all {K} reps, run fresh each time — never trust a single run. LOOP: (1) pick next un-stressed path; (2) write the stress test asserting the invariant under {M}-way concurrency; (3) run {K} reps now, confirm it currently fails at some nonzero rate — that's your proof the race is real, not imagined; (4) apply the minimal synchronization fix (lock, atomic op, single-writer); (5) rerun {K} reps, confirm 0 failures; (6) commit. Carry forward: path list, failure-rate history per path, synchronization strategies already tried. STOP: SUCCESS all paths at 0/{K}; BUDGET; NO-PROGRESS same path still flaky after 3 distinct synchronization strategies; BLOCKED fix requires infrastructure (e.g., distributed lock) unavailable in this environment.
```
