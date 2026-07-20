# Flaky Test Stabilization

`flaky-test-stabilization` — 2 loop prompts.

### 1. Reproduce-and-Fix a Single Flaky Test

- **When:** One named test fails intermittently and you must make it deterministic by fixing the single source of nondeterminism — without neutering what the test actually checks.
- **Loop:** ASSESS failure rate + name one nondeterminism source -> ONE reversible action that removes it -> VERIFY via the repeated-run stability harness -> commit/revert -> decide continue/stop.
- **Stop:** SUCCESS: `0/<N>` failures across `<N>` consecutive unmodified runs AND the assertion still fails when the real bug it guards is reintroduced · BUDGET: `<max_iters>` iterations · NO-PROGRESS: 3 straight hypotheses leave the failure rate unchanged · BLOCKED: repro needs an environment/data/timing you can't provision
- **Model:** Run-observe-compare once the nondeterminism source is narrow — a cheaper model drives the mechanical repeated-run turns fine; escalate to a stronger model when the source is deep concurrency, async scheduling, or clock/GC-timing, where generating the right hypothesis is the hard part. The verifier MUST be independent because the same reasoning that "fixed" the test will happily rationalize one lucky green run — or a quietly deleted assertion — as success; only an out-of-band harness that runs the unmodified test `<N>` times, plus a mutation check that the assertion still fires on the real bug, can tell a real fix apart from a masked or gutted one.

```text
GOAL (frozen — do not redefine mid-loop)
Test `<test_id>`, run by `<test_cmd>`, fails intermittently (~X% of runs). Find the ONE
source of nondeterminism and land a fix so the UNMODIFIED `<test_cmd>` passes 0/<N> across
<N> consecutive runs. Stability bar = <N> back-to-back clean runs of the exact command, not
a hand-picked seed or order. "Passing" achieved by weakening the assertion is a FAILURE.

INDEPENDENT VERIFIER
A stability harness that runs the unmodified `<test_cmd>` <N> times back-to-back and reports
the failure count/rate — external to your edit, never your read of the diff. One green run
proves nothing (the failure is rare by definition) and self-inspection proves nothing (you'd
be grading your own patch). Add the STILL-CATCHES-THE-BUG guard: reintroduce the actual
defect the test guards (or mutate the code under test) and confirm the assertion FAILS. A
test that stays green with the bug present has been neutered — that is a FAILURE, not a fix.

PER-TURN SHAPE
1. ASSESS — run the harness to measure the current failure rate; name ONE concrete source of
   nondeterminism (unmocked clock/timer, real network/IO, unseeded RNG, order-dependent
   shared state, unawaited async, wall-clock timeout).
2. ONE ACTION — make exactly one reversible change that removes that source (inject/mock the
   clock, stub the network, pin the seed, await the promise, isolate the state) — never a
   sleep, retry, or tolerance bump.
3. VERIFY — run the repeated-run harness (<N> runs), record the new failure rate; if it hits
   zero, run the still-catches-the-bug guard before believing it.
4. DECIDE — commit if the rate improved AND the guard still fires; revert if unchanged or the
   guard went silent; park unrelated flakiness to a backlog; escalate on a stop arm.

CARRY-FORWARD STATE (compact)
Failure-rate trend (baseline X/<N> -> current), nondeterminism hypotheses tried/killed,
whether the mutation guard still fires, iterations remaining.

ACTION BAN
Never delete/weaken/loosen the assertion or widen a tolerance to pass. Never add a blind
sleep, retry, or @flaky/retries=k wrapper to mask a race. Never skip/xfail the test. Never
declare fixed from one green run — only the full <N>-run harness counts. Touch no test other
than `<test_id>`; never re-run the same killed probe hoping for a different result.

STOP — halt on the FIRST of:
SUCCESS (0/<N> across <N> consecutive unmodified runs AND assertion still fails when the
guarded bug is reintroduced) | BUDGET (<max_iters> iterations) | NO-PROGRESS (3 straight
hypotheses with unchanged failure rate) | BLOCKED (repro needs env/data/timing you can't
provision — escalate with the failure-rate trend and hypotheses killed)
```

### 2. De-Flake a Suite Under Randomized Order and Parallel Execution

- **When:** A suite that is green in isolation goes red under randomized run order or parallel workers, and you must fix the test-isolation defects one at a time.
- **Loop:** ASSESS the failing set + pin ONE isolation defect -> ONE reversible fix at its source -> VERIFY via the randomized-seed + parallel-worker repeated-run harness -> commit/revert -> decide continue/stop.
- **Stop:** SUCCESS: `<M>` consecutive full-suite runs under fresh random `<seed>` + `<W>` parallel workers all green AND each fixed test still fails on its own reintroduced defect · BUDGET: `<max_iters>` iterations · NO-PROGRESS: 3 fixes land with no reduction in the failing-test set · BLOCKED: the leak lives in an external shared resource you can't isolate
- **Model:** Mostly mechanical isolate-one-variable turns once the leaking pair is found — a cheaper model handles the run/observe cycles; escalate to a stronger model to reason about which two tests share state, or which global mutation orders them, when the coupling is non-obvious. The verifier MUST be independent because a suite "passing" under a single fixed order is exactly the Goodhart trap: you must verify against fresh random seeds and real parallelism you did NOT tune to, and confirm each de-flaked test still catches its own bug — otherwise you've merely reordered or hidden the leak, not fixed it.

```text
GOAL (frozen — do not redefine mid-loop)
Suite `<suite_cmd>` passes in isolation but fails under randomized order and/or parallelism.
Land test-isolation fixes so the FULL suite passes <M> consecutive runs, each with a NEW
random order seed (`<seed_flag>`) and <W> parallel workers, zero failures. Stability bar =
<M> green runs under fresh seeds + <W> workers — not one lucky ordering. Pinning a fixed
order, forcing serial execution, or skipping a test to go green is a FAILURE, not a fix.

INDEPENDENT VERIFIER
A harness that runs the FULL suite <M> times, each run using a fresh random order seed and
<W> parallel workers, reporting per-run pass/fail and exactly which tests failed. A single
green pass in the default order is not proof — order dependence and shared-state leaks only
surface under varied interleavings, and self-inspection can't enumerate all orderings. Add
the guard: for each test you touched, confirm it STILL FAILS when its own guarded defect is
reintroduced, so an isolation fix never silently weakens what the test verifies.

PER-TURN SHAPE
1. ASSESS — run the harness; from the failing set, identify ONE isolation defect (module/
   global/singleton mutated without reset, DB/file/tmp not cleaned, cached connection,
   monkeypatch not undone, dependence on another test's side effect). Minimize to pin the
   culprit: bisect the ordering or run the failing pair alone.
2. ONE ACTION — fix exactly one defect at its source (add teardown/fixture reset, isolate the
   resource, make the test set up its own state) — not a global "run these serially" escape
   hatch unless the coupling is proven irreducible.
3. VERIFY — run the randomized + parallel harness (<M> runs); record which tests still fail.
4. DECIDE — commit if the failing set shrank with no new failures; revert if it didn't shrink
   or regressed; park unrelated defects to a backlog; escalate on a stop arm.

CARRY-FORWARD STATE (compact)
Failing-test set per turn (shrinking?), isolation defects fixed/remaining, seeds and worker
counts already exercised, iterations remaining.

ACTION BAN
Never pin the suite to one fixed order or force everything serial to pass — that hides the
leak (FAILURE). Never delete/xfail/skip a flaky test or weaken its assertions. Never bump
global retries. Never declare done from one green randomized run — only <M> consecutive
fresh-seed parallel runs count. Fix ONE defect per turn so attribution stays clean.

STOP — halt on the FIRST of:
SUCCESS (<M> consecutive full-suite runs under fresh random seeds + <W> workers all green AND
each fixed test still fails on its own reintroduced defect) | BUDGET (<max_iters> iterations)
| NO-PROGRESS (3 fixes with no reduction in the failing-test set) | BLOCKED (leak lives in an
external shared resource — shared DB/broker/port — you can't isolate; escalate with the
failing-set trend and defects fixed)
```
