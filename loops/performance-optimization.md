# Performance Optimization

`performance-optimization` — 2 loop prompts.

### 1. Hotspot Speed Optimization Loop

- **When:** A program is too slow and you must speed up its top runtime hotspot on a fixed representative workload, one reversible change at a time, without breaking correctness or gaming the benchmark.
- **Loop:** assess profile + benchmark baseline -> ONE reversible change to the current top hotspot -> re-run the same benchmark harness (warmup + N runs + significance) and the test suite -> commit if faster beyond noise and tests pass / git-revert otherwise -> decide
- **Stop:** SUCCESS: benchmark median improves past `<TARGET_SPEEDUP>` beyond the noise band AND test suite green · BUDGET: `<MAX_ITERATIONS>` reached · NO-PROGRESS: no change lands outside the noise band for 3 straight turns (or profile hotspot oscillates) · BLOCKED: hotspot is in a frozen dependency / needs an architectural or spec decision
- **Model:** Start mid-tier — obvious algorithmic and allocation wins are near-mechanical off profiler output. Escalate to a top-tier model exactly when NO-PROGRESS is about to trip and the remaining gain needs creative restructuring. The verifier MUST be an independent, fixed benchmark harness (not the model's read of the diff) because a model optimizing for speed will happily rationalize an unmeasured "this should be faster"; and it must be distinct from the change so the loop can't be won by tuning the harness/workload and then citing that same number as proof (Goodhart).

```text
GOAL (frozen — do not redefine mid-loop)
Reduce runtime of <PROGRAM/FUNCTION> on the FROZEN workload <FROZEN_WORKLOAD> so that <BENCHMARK_HARNESS> reports its median wall-time improved by at least <TARGET_SPEEDUP> versus the recorded baseline, while <TEST_COMMAND> stays fully green. The workload, the harness config (<WARMUP> warmup iters, <RUNS> measured runs, <SIGNIFICANCE> test / noise band), and the test suite are frozen inputs — do not edit, shrink, reorder, or re-tune any of them to move the number.

INDEPENDENT VERIFIER
Two mechanical checks the change cannot rubber-stamp itself with: (1) <BENCHMARK_HARNESS> run on the untouched <FROZEN_WORKLOAD> — <WARMUP> warmup then <RUNS> timed runs, compared by median with a <SIGNIFICANCE> significance / noise-band rule so a delta only counts if it clears run-to-run jitter; (2) <TEST_COMMAND> for correctness. A win requires BOTH: median faster beyond the noise band AND tests green. "Faster" is never decided by reasoning about the code — only by the harness on the frozen workload. Because the harness and workload are frozen and separate from the edit, you cannot Goodhart the metric by hand-tuning inputs, warmup, or environment; if you touch the harness, the run is void.

PER-TURN SHAPE
1. ASSESS — run <PROFILER> on <FROZEN_WORKLOAD>, read the current single top hotspot vs the carried baseline; pick that ONE hotspot only.
2. ONE ACTION — make the smallest reversible change (algorithm, caching, batching, allocation removal, hot-path inlining) targeting that hotspot — no batching of edits, no drive-by refactors elsewhere.
3. VERIFY — run the INDEPENDENT VERIFIER: <BENCHMARK_HARNESS> (<WARMUP>+<RUNS>, median + <SIGNIFICANCE>) then <TEST_COMMAND>. Never accept a speedup you did not measure.
4. DECIDE — commit only if median improved beyond the noise band AND tests pass; otherwise `git revert`/`git reset` to last known-good and try a materially different approach next turn. Re-profile — the hotspot may have moved.

CARRY-FORWARD STATE (compact)
Baseline median + current best median (with noise band), current top hotspot from last profile, changes tried and their measured delta (kept/reverted), correctness status, iterations left of <MAX_ITERATIONS>.

ACTION BAN
Never accept an unmeasured "should be faster" — the harness decides, not the diff. Never edit/shrink/reorder <FROZEN_WORKLOAD>, tune warmup/runs/env, or otherwise game <BENCHMARK_HARNESS> then cite its number (Goodhart) — that voids the turn. Never batch multiple changes before benchmarking (kills attribution + clean revert). Never keep a change that is within the noise band. Never touch <TEST_COMMAND> to make a change "pass." Never re-run the exact reverted change hoping for a different number.

STOP — halt on the FIRST of:
SUCCESS (median improved >= <TARGET_SPEEDUP> beyond the noise band AND <TEST_COMMAND> green) | BUDGET (<MAX_ITERATIONS> reached) | NO-PROGRESS (no change lands outside the noise band for 3 straight turns, or the top hotspot oscillates A->B->A) | BLOCKED (hotspot lives in a frozen dependency, or the next gain needs an architecture/spec decision only a human can make — surface it with everything tried)
```

### 2. Memory / Allocation Reduction Loop

- **When:** A program's peak memory or allocation count/rate is too high on a fixed representative scenario and you must bring it down one reversible change at a time, proven by a profiler, with zero correctness regression.
- **Loop:** assess allocation/peak profile -> ONE reversible change to the top allocation site -> re-run the same profiler on the frozen scenario + the test suite -> commit if measured lower and tests pass / git-revert otherwise -> decide
- **Stop:** SUCCESS: profiler shows `<MEMORY_METRIC>` reduced by >= `<TARGET_REDUCTION>` AND test suite green · BUDGET: `<MAX_ITERATIONS>` reached · NO-PROGRESS: `<MEMORY_METRIC>` flat within measurement error for 3 straight turns (or top alloc site oscillates) · BLOCKED: dominant allocation is in a frozen dependency / needs a design decision
- **Model:** Mid-tier handles the common wins (pooling, reuse, streaming, dropping copies, right-sizing buffers) off profiler output. Escalate to a top-tier model when the remaining footprint needs a data-structure or ownership redesign rather than a local edit. The verifier MUST be an independent memory profiler on the frozen scenario plus the test suite, kept separate from the change: a model reasoning "this should use less memory" is routinely wrong (allocations move, get deferred, or reappear under GC), so only a measured before/after on the same scenario counts; keeping it separate from the edit stops the loop being won by trimming the scenario instead of the code.

```text
GOAL (frozen — do not redefine mid-loop)
Reduce <MEMORY_METRIC> (choose one and hold it: peak RSS / peak heap / total allocation count / allocation rate) of <PROGRAM/SERVICE> on the FROZEN scenario <FROZEN_SCENARIO>, as measured by <MEMORY_PROFILER>, by at least <TARGET_REDUCTION> versus the recorded baseline — while <TEST_COMMAND> stays fully green. The scenario, the profiler config, and the test suite are frozen inputs; do not shrink the scenario, relax the profiler, or change the metric definition to make the number move.

INDEPENDENT VERIFIER
Two mechanical checks the change cannot rubber-stamp itself with: (1) <MEMORY_PROFILER> run on the untouched <FROZEN_SCENARIO>, reporting <MEMORY_METRIC>, compared to the carried baseline with a <MEASUREMENT_MARGIN> margin so a drop only counts if it clears run-to-run measurement noise (average <RUNS> runs where the profiler is noisy); (2) <TEST_COMMAND> for correctness. A win requires BOTH: metric measurably lower beyond the margin AND tests green. Memory usage is NEVER decided by reasoning about the code — allocations get deferred, moved, or hidden behind the allocator/GC — only the profiler on the frozen scenario is ground truth. Because the scenario and profiler are frozen and separate from the edit, you cannot pass by trimming inputs and citing the result.

PER-TURN SHAPE
1. ASSESS — run <MEMORY_PROFILER> on <FROZEN_SCENARIO>, read the single top allocation site / peak contributor vs the carried baseline; pick that ONE only.
2. ONE ACTION — make the smallest reversible change (reuse/pool a buffer, stream instead of buffering, drop a redundant copy, right-size a collection, release earlier) targeting that site — no batching, no unrelated cleanup.
3. VERIFY — run the INDEPENDENT VERIFIER: <MEMORY_PROFILER> on the frozen scenario (average <RUNS>, apply <MEASUREMENT_MARGIN>) then <TEST_COMMAND>. Never trust "should allocate less" — measure it.
4. DECIDE — commit only if <MEMORY_METRIC> dropped beyond the margin AND tests pass; otherwise `git revert`/`git reset` to last known-good and try a materially different approach next turn. Re-profile — the top site may have shifted, and watch for a speed/memory trade you didn't intend.

CARRY-FORWARD STATE (compact)
Baseline + current best <MEMORY_METRIC> (with margin), current top allocation site from last profile, changes tried and their measured delta (kept/reverted), correctness status, iterations left of <MAX_ITERATIONS>.

ACTION BAN
Never accept "should use less memory" reasoning — the profiler decides, not the diff. Never shrink/relax <FROZEN_SCENARIO>, weaken the profiler, or redefine <MEMORY_METRIC> mid-loop to force a drop (voids the turn). Never batch multiple changes before profiling (kills attribution + clean revert). Never keep a change whose delta is inside the measurement margin. Never touch <TEST_COMMAND> to paper over a correctness regression. Never re-run the exact reverted change expecting a different profile.

STOP — halt on the FIRST of:
SUCCESS (<MEMORY_METRIC> reduced >= <TARGET_REDUCTION> beyond the margin AND <TEST_COMMAND> green) | BUDGET (<MAX_ITERATIONS> reached) | NO-PROGRESS (<MEMORY_METRIC> flat within measurement error for 3 straight turns, or the top allocation site oscillates A->B->A) | BLOCKED (dominant allocation is inside a frozen dependency, or the next reduction needs a data-structure/ownership redesign only a human can approve — surface it with everything tried)
```
