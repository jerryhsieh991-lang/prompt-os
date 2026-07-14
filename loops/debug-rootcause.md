# Debug / Root-Cause

`debug-rootcause` — 8 loop prompts.

### 1. Flaky/Intermittent Test Root-Cause Hunt

- **When:** A test fails nondeterministically (passes sometimes, fails sometimes) with no clear trigger — ordering, timing, shared state, or an external dependency is suspected.
- **Loop:** Baseline the failure rate over N runs -> each turn: state ONE nondeterminism hypothesis -> add ONE probe (log/assert/seed pin) -> re-run N times -> compare failure rate to baseline -> narrow or discard -> decide continue/stop.
- **Stop:** SUCCESS: N/N consecutive clean runs AND removing the fix reproduces the original failure (causal proof, not correlation) · BUDGET: 12 iterations exhausted · NO-PROGRESS: 3 consecutive hypotheses produce zero change in failure rate · BLOCKED: repro requires environment/data access that isn't available
- **Model:** Mostly mechanical run-observe-compare cycles — a cheaper model (e.g. Sonnet/Haiku-class) handles this well once the hypothesis space is narrow. Escalate to a stronger model (Claude Fable 5) only if the codebase involves deep concurrency, async scheduling, or JIT/GC-timing effects where hypothesis generation itself is the hard part.

```text
GOAL (frozen): Test `<test_name>` fails intermittently (~X% of Y runs). Find the root cause and land a fix that makes it pass N/N consecutive runs, confirmed by re-running the SAME test command unmodified — that command is your verifier, not your own read of the code.

Baseline first: run the test N times, record the failure rate as your reference metric.

Each turn: state one concrete hypothesis for the nondeterminism (ordering, timing, shared state, uninitialized value, external dependency). Add exactly ONE probe — a log line, assertion, or seed pin — that would confirm or kill it. Re-run N times. Compare failure rate to baseline; if unchanged, discard the hypothesis and pick a genuinely different one, never the same probe again. Commit anything that leaves the suite green; revert regressions.

STOP on first: SUCCESS — N/N clean runs, and removing the fix reproduces the original failure (causal proof); BUDGET — 12 iterations; NO-PROGRESS — 3 straight hypotheses with zero change in failure rate; BLOCKED — repro needs an environment/data you don't have — escalate with findings so far.
```

### 2. Production Crash / Stack-Trace Postmortem

- **When:** A production incident produced a stack trace or error report but has no local reproduction yet; you need to go from symptom to root cause to a locked-in regression test.
- **Loop:** Freeze evidence read (trace/logs/timing) as starting state -> each turn: ONE hypothesis for the failing invariant -> ONE reversible action (probe or minimal repro attempt) -> run -> check against the same signature -> update confirmed/killed/open list -> decide.
- **Stop:** SUCCESS: local repro reproduces the exact signature, fix removes it, and a new regression test locks it in · BUDGET: 15 iterations exhausted · NO-PROGRESS: 4 turns pass with no hypothesis eliminated or confirmed · BLOCKED: repro requires production data/traffic that isn't accessible
- **Model:** Going from a raw stack trace to a good first hypothesis is the hard part — favor a stronger model (Claude Fable 5) for the initial evidence read and hypothesis generation on unfamiliar codebases; once narrowed to 2-3 candidate sites, a cheaper model can drive the mechanical probe/run/observe turns.

```text
GOAL (frozen): Root-cause the crash in `<error signature / stack trace>` seen in production and land a fix verified by a NEW regression test that fails on main and passes with your patch — that test is the verifier, not your explanation of the trace.

Start by writing down what the evidence (stack trace, logs, timing) rules in and out — freeze this as your starting state, don't re-litigate it each turn.

Each turn: pick ONE hypothesis for the failing invariant, take ONE reversible action (add a log/assert at the suspected boundary, or attempt a minimal local repro), run it, and check the result against the SAME signature you started with. Track confirmed / killed / open hypotheses; never repeat a killed one. Keep the branch running after every turn — commit probes that stick, revert ones that don't.

STOP on first: SUCCESS — local repro reproduces the exact signature, fix removes it, regression test locks it in; BUDGET — 15 iterations; NO-PROGRESS — 4 turns with no hypothesis eliminated or confirmed; BLOCKED — repro needs production data/traffic you can't access — escalate with everything ruled out.
```

### 3. Performance Regression Bisection

- **When:** A latency/throughput/memory metric regressed between a known-good and known-bad reference point (commit, release, config) and you need to localize the exact change.
- **Loop:** Each turn = one bisection step: pick midpoint ref between current good/bad bounds -> run the FIXED benchmark harness once (twice at any candidate boundary to rule out noise) -> record in a ref->metric table -> narrow the range -> decide.
- **Stop:** SUCCESS: culprit commit isolated, fix applied, benchmark back within threshold on two consecutive runs · BUDGET: log2(range)+5 bisection steps exhausted · NO-PROGRESS: identical measurements from different refs for 3 turns running (noise dominates signal) · BLOCKED: regression doesn't reproduce outside production traffic
- **Model:** This is a search algorithm more than a reasoning task — a cheaper model (Haiku/Sonnet-class) is sufficient and cost-efficient for the bisection turns themselves. Reserve a stronger model for the final step: reading the isolated diff and explaining *why* it caused the regression before writing the fix.

```text
GOAL (frozen): `<metric>` regressed from `<baseline value>` to `<current value>` between `<good ref>` and `<bad ref>`. Find the single change responsible and land a fix that brings the metric back within `<threshold>` of baseline, measured by running the FIXED benchmark harness `<command>` — not by reasoning about what "should" be faster.

Each turn is one bisection step: pick the midpoint commit/config between your current good and bad bounds, run the benchmark exactly as specified, record the number, and narrow the range from that single measurement — don't skip points or eyeball multiple commits at once. Run any candidate boundary twice to rule out noise before trusting it. Keep a running ref->metric table so you never re-measure a point you already have.

STOP on first: SUCCESS — culprit commit isolated, fix applied, benchmark back within threshold on two consecutive runs; BUDGET — log2(range)+5 steps; NO-PROGRESS — two identical measurements from different refs for 3 turns running (noise dominates) — escalate for a cleaner harness; BLOCKED — regression doesn't reproduce outside production traffic.
```

### 4. Silent Data Corruption / Wrong Output Localization

- **When:** Code runs without crashing but produces incorrect output or values — a silent bug somewhere in a multi-stage pipeline, transform, or computation.
- **Loop:** Model pipeline as ordered stages -> each turn: pick most-suspect stage -> add ONE assertion/dump at its boundary -> re-run the SAME fixture -> diff actual vs expected at that boundary -> narrow before/after -> decide.
- **Stop:** SUCCESS: automated diff shows exact match between actual and expected output on the fixture, confirmed twice · BUDGET: 10 stage-probes exhausted · NO-PROGRESS: no new stage eliminated for 3 turns · BLOCKED (also covers oscillation as forced escalation): a stage gets re-implicated after being cleared, or no ground-truth expected value exists to diff against
- **Model:** Straightforward pipelines (few stages, simple transforms) are fine for a cheaper model driving the diff-and-narrow loop. Long or domain-specific pipelines (numerical, ML preprocessing, financial calculations) benefit from a stronger model (Claude Fable 5) to correctly reason about which stage is 'most likely at fault' before spending a probe.

```text
GOAL (frozen): Given input `<fixture>`, the pipeline produces `<wrong output>` instead of `<expected output>`. Find which stage introduces the divergence and fix it so output matches expected EXACTLY, verified by an automated diff against the fixture — not by eyeballing the result.

Model the pipeline as an ordered list of stages. Each turn: pick the stage most likely at fault, add ONE assertion or intermediate-value dump at its boundary, re-run the SAME fixture, and diff the actual value against what it should be. Narrow to before/after that stage. If a stage gets re-implicated after already being cleared, that's oscillation — stop guessing stage-by-stage and dump ALL intermediate values in one pass instead. Keep the fixture and expected output frozen; don't "fix" the test data.

STOP on first: SUCCESS — exact diff match on the fixture, confirmed twice; BUDGET — 10 stage-probes; NO-PROGRESS — no new stage eliminated for 3 turns, or oscillation detected; BLOCKED — no ground-truth value exists to diff against — escalate to get one defined before continuing.
```

### 5. Distributed / Race-Condition Bug Isolation

- **When:** A bug manifests intermittently under concurrency or across services/threads/network boundaries, and reproduction requires load or timing conditions, not a single deterministic input.
- **Loop:** Each turn: ONE interleaving hypothesis -> ONE probe (timestamp log, sequence assert, or forced-delay) -> run the stress harness once -> record occurrence count -> narrow or discard -> decide; strip forced delays before shipping.
- **Stop:** SUCCESS: 0/N occurrences across two independent post-fix stress runs, AND reapplying the delay probe forces the old failure (causal proof) · BUDGET: 10 iterations exhausted · NO-PROGRESS: 3 hypotheses in a row with unchanged occurrence rate · BLOCKED: can't provision the multi-node/concurrent environment needed to reproduce
- **Model:** Highest-difficulty hypothesis space in this set — concurrency/ordering reasoning is where weaker models thrash and repeat disguised variants of the same guess. Use the strongest available model (Claude Fable 5 at xhigh effort) throughout, not just for the first turn.

```text
GOAL (frozen): `<symptom>` occurs intermittently under concurrent/distributed conditions involving `<services/threads>`. Find the race/ordering bug and land a fix that survives a stress harness running `<N>` concurrent iterations with ZERO occurrences — that harness, run fresh each time, is your verifier.

Each turn: state one hypothesis about interleaving (which two operations race, which lock is missing, which message can arrive out of order). Add exactly ONE probe — a timestamp log, a sequence assertion, or an artificial delay forcing the suspected interleaving — then run the stress harness once and record the occurrence count. A hypothesis that doesn't move the rate is dead; pick a structurally different one next, not a variant of the same guess. Strip any artificial delay from the final fix — probes only, never shipped.

STOP on first: SUCCESS — 0/N occurrences across two independent post-fix runs, and reapplying the delay probe forces the old failure (causal proof); BUDGET — 10 iterations; NO-PROGRESS — 3 hypotheses with unchanged occurrence rate; BLOCKED — can't provision the multi-node/concurrent environment needed to reproduce.
```

### 6. Regression After Dependency/Environment Upgrade

- **When:** Something broke after upgrading a library, runtime, OS, or config, and it isn't obvious which of several simultaneous changes is responsible.
- **Loop:** List every changed dependency/config as candidates -> each turn: revert/pin exactly ONE candidate -> re-run the repro command -> record pass/fail -> once narrowed, verify the WHY via changelog/diff -> decide.
- **Stop:** SUCCESS: repro passes with only the culprit reverted/patched, and reintroducing it alone reproduces the failure · BUDGET: candidate list exhausted twice over (bisect pass + verify pass) · NO-PROGRESS: 3 candidates reverted with no change in repro outcome · BLOCKED: culprit is a confirmed upstream bug with no available patch or workaround
- **Model:** Largely mechanical one-variable-at-a-time isolation — a cheaper model handles the bisection turns fine. Swap in a stronger model for the final 'read the changelog and explain the breaking change' step, since that requires correctly parsing semver/migration notes rather than pattern-matching.

```text
GOAL (frozen): After upgrading `<dependency/env>` from `<old>` to `<new>`, `<symptom>` appeared. Isolate the exact change responsible and land a fix (patch, pin, or workaround) that makes `<repro command / failing test>` pass again, verified by running that exact command unmodified.

List every changed dependency/config between old and new as your candidate set. Each turn: revert or pin exactly ONE candidate to its old value, re-run the repro command, record pass/fail — never revert more than one variable per turn, or you lose attribution. Once narrowed to a single culprit, verify WHY by reading its changelog/diff, not by guessing. Keep the working branch runnable after every turn; revert anything you can't explain.

STOP on first: SUCCESS — repro passes with only the culprit reverted/patched, and reintroducing it alone reproduces the failure; BUDGET — candidate list exhausted twice (bisect + verify pass); NO-PROGRESS — 3 candidates reverted with no change in outcome; BLOCKED — culprit is a confirmed upstream bug with no available patch — escalate for a version-pin decision.
```

### 7. Frontend/UI Visual or Interaction Bug

- **When:** A browser-observable bug (visual glitch, broken interaction, wrong rendered state) is reproducible via a fixed sequence of UI steps.
- **Loop:** Turn 1: automate the repro into a re-runnable script -> each turn after: ONE hypothesis (CSS/state/render-race/event) -> ONE probe (log, breakpoint note, component isolation) -> re-run automated repro -> check DOM/screenshot assertion -> decide.
- **Stop:** SUCCESS: automated repro asserts expected DOM state/screenshot on two consecutive runs, root component/line identified and fixed · BUDGET: 10 iterations exhausted · NO-PROGRESS: 3 probes in a row with no narrowing of the suspect component · BLOCKED: bug only reproduces on a browser/OS/device combination that isn't accessible locally
- **Model:** Fine for a mid-tier model once repro automation exists (e.g. via Playwright), since the assertion is mechanical DOM/screenshot comparison, not self-judgment. Escalate to a stronger model when the hypothesis involves an async render/fetch race, where timing reasoning is easy to get subtly wrong.

```text
GOAL (frozen): Following steps `<repro steps>` in `<browser/environment>` produces `<observed bug>` instead of `<expected behavior>`. Find the root cause and land a fix verified by an automated repro that asserts the EXPECTED DOM state/screenshot — not by eyeballing it once manually.

First turn: automate the repro steps into a re-runnable script so every later check is identical and mechanical. Each turn after: form one hypothesis (wrong CSS rule, stale state, a render/fetch race, event mis-binding), add ONE probe — a console log, a breakpoint note, or isolating the suspect component — then re-run the automated repro and check the assertion. Narrow to the exact component/line. Don't touch unrelated styling or add "while I'm here" cleanup.

STOP on first: SUCCESS — automated repro asserts expected state on two consecutive runs, root line identified and fixed; BUDGET — 10 iterations; NO-PROGRESS — 3 probes with no narrowing of the suspect component; BLOCKED — bug only reproduces on a browser/OS/device you can't access — escalate with what's ruled out.
```

### 8. Memory Leak / Resource Exhaustion in a Long-Running Process

- **When:** A long-running process's memory, handle, or connection count grows unboundedly over time under sustained load, and the leaking allocation site is unknown.
- **Loop:** Baseline growth slope -> each turn: ONE suspect (allocation site/handle/cache) -> snapshot before/after a short run -> diff retained objects -> confirm or discard -> on confirmation, fix and re-run FULL soak test to re-check slope -> decide.
- **Stop:** SUCCESS: soak-test growth slope within threshold on two consecutive full-length runs · BUDGET: 10 suspects investigated · NO-PROGRESS: 3 consecutive suspects show no disproportionate retained-object growth · BLOCKED: leak only manifests at a production-scale duration/load that can't be reproduced locally
- **Model:** Heap-diff mechanics are fine for a cheaper model, but choosing which allocation site is 'most likely' among many candidates benefits from a stronger model (Claude Fable 5) — weak hypothesis selection here wastes the whole 10-suspect budget on low-probability candidates before reaching the real leak.

```text
GOAL (frozen): `<process>` grows `<resource, e.g. RSS>` by `<rate>` over `<duration>` under `<load profile>` and should stay flat within `<threshold>`. Find the leak and land a fix, verified by a fixed-length soak test showing bounded growth on two independent runs — not a single spot-check.

Establish the baseline growth slope first as your reference metric. Each turn: pick ONE suspect (an allocation site, an unclosed handle/connection, an unbounded cache), snapshot the resource before and after a short run, and diff retained objects — that diff is your evidence, not intuition. If the suspect's retained size doesn't grow disproportionately, discard it and pick a structurally different suspect next turn. Apply a fix only once a suspect is confirmed, then re-run the full soak test to check the SLOPE, not peak memory.

STOP on first: SUCCESS — soak-test slope within threshold on two consecutive full-length runs; BUDGET — 10 suspects investigated; NO-PROGRESS — 3 consecutive suspects show no disproportionate growth; BLOCKED — leak needs production-scale duration/load unreproducible locally — escalate with snapshot diffs collected.
```
