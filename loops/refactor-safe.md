# Safe Refactor

`refactor-safe` — 8 loop prompts.

### 1. Baseline small-step refactor loop (existing test suite)

- **When:** Any codebase with an existing, trustworthy test suite where you want to improve internal structure (complexity, duplication, readability) of a bounded file/module without changing behavior. The default refactor-safe pattern; use this when nothing more specialized applies.
- **Loop:** assess diff vs. the frozen metric -> make ONE small reversible edit (extract/rename/inline) -> run build + full test suite as verifier -> commit if green and metric improved, git reset if not -> decide continue/stop
- **Stop:** SUCCESS: target metric threshold met (e.g., function <=50 lines) AND full test suite green · BUDGET: 15 turns (or a fixed token/wall-clock cap) reached · NO-PROGRESS: target metric unchanged for 3 consecutive turns · BLOCKED: a step needs human judgment (ambiguous behavior, missing coverage on the path being touched)
- **Model:** Good fit for a default daily-driver model (e.g., Opus-class at high effort) since extraction-boundary judgment still matters. Once the pattern is established on 1-2 steps, the remaining mechanical steps can often be handed to a cheaper model (Sonnet/Haiku-class) since the test suite, not the model, is doing the real judgment.

```text
You are refactoring [TARGET: file/module/directory] to [GOAL: e.g., reduce cyclomatic complexity, remove duplication, improve readability] without changing external behavior. Before starting, run the full test suite and record the baseline: pass/fail count and runtime. Freeze this as your goal: all tests that passed before must still pass, and the specific improvement (state it numerically, e.g., "function X under 50 lines") must be met.

Each turn: (1) assess the current diff vs. the frozen goal, (2) make exactly ONE small, reversible refactor step (extract one function, rename one symbol, inline one variable), (3) run the build and full test suite as the verifier, (4) decide: if tests pass and the diff improved the target metric, commit and continue; if tests fail, git reset and try a different approach next turn (never repeat the identical failed edit).

Stop and report the moment ANY of these trips: SUCCESS — goal metric met and tests green; BUDGET — 15 turns reached; NO-PROGRESS — metric unchanged for 3 consecutive turns; BLOCKED — a step requires a decision only a human can make. Do not add features, fix unrelated bugs, or restyle code outside the target while looping.
```

### 2. Characterization-first refactor loop for untested legacy code

- **When:** Legacy code with little or no test coverage that must be restructured — you need to build a behavioral safety net before touching structure, otherwise 'passing tests' is not a real gate.
- **Loop:** Phase A (once, outside the loop): write characterization tests pinning down CURRENT behavior. Phase B (loop): assess vs. frozen structural goal -> one small reversible step -> run characterization+real tests -> commit/revert -> decide
- **Stop:** SUCCESS: structural goal met AND all characterization tests still green · BUDGET: 20 turns reached · NO-PROGRESS: no metric movement for 3 consecutive turns · BLOCKED: behavior discovered that can't be characterized without a human decision (e.g., possible latent bug of uncertain load-bearing status)
- **Model:** Keep on a strong reasoning model throughout (e.g., Opus-class xhigh, or Fable-class for unusually tangled/undocumented legacy code) — spotting which quirks are load-bearing behavior vs. accidental bugs is the hard, judgment-heavy part and is exactly where a cheaper model under-verifies.

```text
Target: [MODULE/FILE] has little or no test coverage and needs [structural goal, e.g., split into 3 cohesive units]. Do NOT refactor yet. First, write characterization tests that pin down CURRENT observed behavior (inputs to outputs, including quirks) until every code path you intend to touch is covered. Treat these tests as ground truth for "behavior preserved," not a judgment of whether the behavior is correct.

Once characterization tests pass against the untouched code, freeze the structural goal and enter the loop: each turn, assess progress vs. the goal, make ONE small reversible refactor step, run the characterization tests plus any real tests as the independent verifier, then commit on green or git reset on red (never repeat an identical failed edit — vary the approach).

Stop on whichever trips first: SUCCESS — structural goal met, all characterization tests still green; BUDGET — 20 turns; NO-PROGRESS — no metric movement for 3 turns; BLOCKED — you find behavior you cannot characterize without a human decision. Do not fix bugs found along the way; log them and continue.
```

### 3. Mechanical API/symbol migration across many call sites

- **When:** A large-scale but mechanical refactor — renaming a symbol, or migrating every call of a deprecated API to its replacement — across many files/call sites in one scope.
- **Loop:** assess remaining-count against the frozen call-site list -> migrate ONE file/call-site (smallest reversible unit) -> compile + test -> commit or revert -> decide, carrying forward only {remaining count, last site, last verifier result}
- **Stop:** SUCCESS: remaining count is 0 AND the full suite is green · BUDGET: 25 turns, or N turns (call-site count), whichever is smaller · NO-PROGRESS: remaining count unchanged for 3 consecutive turns · BLOCKED: a call site's correct migration is behaviorally ambiguous and needs a human call
- **Model:** This is the classic cheap-model / high-volume subagent case: once the migration pattern is confirmed on the first 1-2 sites, hand the bulk loop to a Sonnet/Haiku-class model since each step is low-judgment and the compiler+tests carry the verification load. Reserve a stronger model for building the initial frozen list and for any BLOCKED escalations.

```text
Goal: migrate every call site of [OLD_API/SYMBOL] to [NEW_API/SYMBOL] across [SCOPE], with identical runtime behavior. Before starting, search and freeze the exact list of call sites (count = N) — this list is the goal; it must not grow or shrink except by migration.

Each turn: assess how many sites remain from the frozen list, pick the SMALLEST reversible unit (one file, or one call site if a file is large), migrate it, then run the build and full test suite as the independent verifier. Commit if green and the remaining-count dropped; git reset if red. Carry forward only compact state — remaining count, last site migrated, last verifier result — not the whole diff history.

Stop the instant one of these trips: SUCCESS — remaining count is 0 and the full suite is green; BUDGET — 25 turns or N turns, whichever is smaller; NO-PROGRESS — remaining count unchanged for 3 turns; BLOCKED — a site's correct migration is ambiguous and needs a human call. Do not migrate sites outside the frozen list, even if you spot more.
```

### 4. God-object/god-function decomposition guarded by complexity metric

- **When:** A single function or class has grown too large or too coupled ('god object') and needs extraction into smaller units, where you want a metric gate (not just tests) so the loop can't just shuffle code around without real improvement.
- **Loop:** assess complexity/LOC metric + tests vs. frozen threshold -> extract ONE cohesive piece -> run linter/complexity tool AND test suite -> commit if metric improved-or-held and tests green, else revert -> decide
- **Stop:** SUCCESS: metric at or below threshold AND tests green · BUDGET: 15 turns reached · NO-PROGRESS: metric flat for 3 consecutive turns (signals shuffling, not shrinking) · BLOCKED: an extraction would require a public API change needing sign-off
- **Model:** Extraction-boundary choice is real judgment — keep on a strong default model (Opus-class xhigh); escalate to a top-tier model (Fable-class) only if this is a high-stakes core module where a wrong boundary is expensive to unwind.

```text
Target: [FUNCTION/CLASS] currently measures [baseline, e.g., 400 lines, cyclomatic complexity 35]. Frozen goal: reduce to at or below [threshold] on that SAME metric via extraction, with the full test suite staying green throughout — this is the only definition of done.

Each turn: run the complexity/lint tool to get the current metric, extract exactly ONE cohesive piece (a method, a class, a helper) into its own named unit, then run the linter/metric tool AND the test suite as two independent verifiers — the metric isn't your own read of the diff, and tests aren't your own read of correctness. Commit only if both improved-or-held and passed; otherwise git reset and choose a different extraction boundary next turn, never re-attempting the identical extraction.

Halt on the first: SUCCESS — metric at or below threshold, tests green; BUDGET — 15 turns; NO-PROGRESS — metric flat for 3 turns straight (force a different decomposition strategy); BLOCKED — extraction would require a public API change needing sign-off. Do not rename unrelated symbols or "clean up while here."
```

### 5. Framework/library major-version upgrade, module by module

- **When:** A major framework or library upgrade (class components to hooks, sync to async client, deprecated SDK v1 to v2) that must roll out module-by-module behind CI so main stays shippable, rather than as one big-bang change.
- **Loop:** assess frozen inventory of modules still on OLD pattern -> migrate ONE module (fewest downstream dependents first) -> run full build + CI (unit+integration) -> commit or revert -> decide, shrinking the inventory each turn
- **Stop:** SUCCESS: inventory empty AND CI green on main · BUDGET: [N] turns or [T] wall-clock reached · NO-PROGRESS: inventory count unchanged for 3 consecutive turns · BLOCKED: the same module fails migration 3 times running, or the new API has no equivalent for existing behavior
- **Model:** Mixed workload: use a strong model to triage the inventory and handle the first couple of modules to establish the migration idiom, then delegate the repetitive remaining modules to a cheaper model (Sonnet/Haiku-class) — CI is the real gate. Route BLOCKED escalations back to the strong model.

```text
Goal: migrate [SCOPE] from [OLD_PATTERN/LIBRARY_VERSION] to [NEW_PATTERN/LIBRARY_VERSION] one module at a time, keeping main always shippable. Before looping, freeze the inventory of modules still on the old pattern — this list only shrinks, never grows mid-loop.

Per turn: assess the inventory, pick the module with the fewest downstream dependents, migrate ONLY that module's usage, then run the full build and CI suite (unit and integration, not just unit) as the independent verifier. If green, commit and remove it from the inventory; if red, git reset that module's change, note the failure mode, and try a genuinely different migration approach next attempt on that module (not a verbatim retry).

Stop on the first tripped arm: SUCCESS — inventory empty, CI green on main; BUDGET — [N] turns or [T] wall-clock; NO-PROGRESS — inventory count unchanged for 3 turns; BLOCKED — the same module fails migration 3 times running (stop, report the concrete error and attempts, ask for guidance) or the new API lacks an equivalent for existing behavior. Do not upgrade unrelated dependencies opportunistically.
```

### 6. Type-system migration with ratcheting strictness

- **When:** Incrementally adding or tightening types across an untyped or loosely-typed codebase (Python to mypy strict, JS to TS, eliminating 'any') where the type checker's own error/looseness count is the measurable gate.
- **Loop:** assess type-error/'any' count vs. frozen target (0) -> tighten types in ONE file/module -> run type checker AND test suite -> commit if count dropped and both gates pass, else revert -> decide
- **Stop:** SUCCESS: count is 0 AND tests green · BUDGET: 20 turns reached · NO-PROGRESS: count flat for 3 consecutive turns · BLOCKED: a type error reveals what looks like a real runtime bug requiring a human decision
- **Model:** Mostly mechanical pattern-matching once initial idioms are set — a good candidate for a cheaper model (Sonnet/Haiku-class) running the bulk loop; escalate any turn flagged as 'looks like a real bug' to a stronger model rather than letting the cheap loop guess.

```text
Goal: bring [SCOPE] from [baseline type-checker error/"any" count, e.g., 240 errors under strict mode] to 0, without changing runtime behavior. Freeze that count as the metric; the test suite is the behavior guard — both must hold at the end.

Each turn: run the type checker for the current count, pick the file with the most errors or most dependents, add or fix types in that ONE file, then run the type checker AND the full test suite as two independent verifiers — a clean type check doesn't prove behavior is unchanged, and vice versa. Commit if the count dropped and tests stayed green; otherwise git reset and try a different typing strategy next turn, not the same fix again.

Stop on the first trip: SUCCESS — count is 0, tests green; BUDGET — 20 turns; NO-PROGRESS — count flat for 3 turns; BLOCKED — a type error reveals what looks like a real runtime bug (stop, report it, don't silently "fix" behavior mid-refactor). Never use blanket suppressions just to move the count — that's Goodhart, not progress.
```

### 7. Database/schema refactor via expand-migrate-contract with shadow-read verification

- **When:** Refactoring a data layer or schema (splitting a table, renaming a column, changing storage format) where correctness must be verified against real/production-shaped data, not just unit tests, and every step needs to be reversible.
- **Loop:** assess which step of the frozen expand-migrate-contract plan you're on -> execute ONLY that one reversible step -> verify with the step-specific independent gate (migration test, checksum, shadow-read diff) -> commit or run DOWN migration -> decide
- **Stop:** SUCCESS: final step complete AND shadow-read diff shows zero mismatches over the sampled window · BUDGET: [N] turns reached · NO-PROGRESS: the same step fails verification 2 turns running with no diagnosis · BLOCKED: needs a maintenance window/sign-off, or the diff reveals pre-existing data corruption
- **Model:** High blast-radius, keep on the strongest available model throughout (Opus-class xhigh, or Fable-class for designing the initial migration plan) — do not delegate this loop to a cheaper model given the cost of an undetected data-integrity regression.

```text
Goal: refactor [TABLE/SCHEMA] from [OLD shape] to [NEW shape] with zero data loss and no behavior change, via the expand-migrate-contract pattern. Freeze the plan as an ordered list of reversible steps (add new column/table, dual-write, backfill, shadow-read compare, cut reads over, drop old). Each step must have a corresponding DOWN migration.

Per turn: assess which step you're on, execute ONLY that one step, then verify with the independent gate for that step — migration tests, a backfill row-count/checksum comparison, or a shadow-read diff against production-shaped data, never your own assertion that "it looks right." If verification passes, commit and advance; if it fails, run the DOWN migration to roll back and diagnose before retrying with a different approach.

Halt on the first trip: SUCCESS — final step complete, shadow-read diff shows zero mismatches over the sampled window; BUDGET — [N] turns; NO-PROGRESS — the same step failing verification 2 turns running with no diagnosis; BLOCKED — you need a maintenance window, sign-off, or the diff reveals pre-existing data corruption. Never skip the dual-write/shadow-read step to save time.
```

### 8. Dead-code and duplication removal guarded by coverage-not-decreasing

- **When:** Removing dead code, unused exports, or duplicated logic across a codebase where the risk is deleting something that's actually load-bearing but poorly tested — coverage regression is the tell.
- **Loop:** assess frozen candidate list (from one static-analysis pass) -> remove/consolidate ONE candidate -> run build + full test suite + coverage report -> commit if green and coverage did not drop, else revert -> decide
- **Stop:** SUCCESS: candidate list empty, tests green, coverage at or above baseline · BUDGET: 20 turns reached · NO-PROGRESS: 3 consecutive turns with no successful removal · BLOCKED: a candidate is referenced only via reflection/dynamic dispatch/string lookup and static analysis can't confirm safety
- **Model:** Mostly mechanical — a Sonnet/Haiku-class model can run the bulk deletion loop cheaply since the build+test+coverage triple is the real verifier; route anything hitting the BLOCKED arm (dynamic-dispatch ambiguity) to a stronger model for the human-confirmation writeup.

```text
Goal: remove dead code and duplicated logic in [SCOPE]. Before looping, run static analysis (an unused-export/dead-code tool) once to produce a frozen candidate list — this run's list is the scope; do not re-scan and expand it mid-loop.

Each turn: assess remaining candidates, pick ONE (start with the one touching the fewest files), delete or consolidate it, then run the build, full test suite, and a coverage report as independent verifiers. Commit only if the build is green, all tests pass, AND coverage did not decrease (a drop means you deleted something a test was silently relying on, not truly dead code). If any check fails, git reset that candidate, mark it "needs human confirmation" instead of retrying blindly, and move to the next candidate.

Stop on the first tripped arm: SUCCESS — candidate list empty, tests green, coverage at or above baseline; BUDGET — 20 turns; NO-PROGRESS — 3 consecutive turns with no successful removal; BLOCKED — a candidate is referenced only via reflection/dynamic dispatch/string lookup and static analysis can't confirm it's safe. Do not refactor surrounding code while removing — deletion only.
```
