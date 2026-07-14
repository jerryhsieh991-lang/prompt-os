# Migration / Codemod

`migration-codemod` — 8 loop prompts.

### 1. Deprecated API / Function-Signature Codemod

- **When:** A library or internal API changed its name or signature (e.g. positional args -> options object, function renamed/removed) and every call site in the repo must be updated to the new form.
- **Loop:** assess (grep/AST search for remaining old-signature call sites against a frozen worklist) -> pick ONE site -> transform it -> verify (build + narrowest covering test) -> commit if green / git reset --hard if red -> update remaining-count -> decide continue/stop.
- **Stop:** SUCCESS: zero remaining matches for old API AND full build + test suite green · BUDGET: max_turns reached · NO-PROGRESS: remaining-site count unchanged for 3 consecutive turns · BLOCKED: the same site fails 3 distinct fix approaches
- **Model:** Mechanical AST/grep work well within a mid-tier model. For huge worklists (1000+ sites), a cheaper/faster model can drive the per-site loop to save cost, reserving a stronger model only for the handful of BLOCKED sites that need real judgment.

```text
You are migrating every call site of `<old_api>` to `<new_api>` in this repository. GOAL (frozen): a grep/AST search for `<old_api>` returns zero matches, and `<build_command>` plus `<test_command>` both pass. Before looping, list all call sites via `<discovery_command>` — this is your fixed worklist; do not add scope beyond it.

Each turn: (1) assess — pick exactly ONE unmigrated site from the worklist; (2) transform — rewrite only that site to `<new_api>`; (3) verify — run `<build_command>` and the narrowest test that covers that file; (4) decide — if green, `git commit`, mark the site done, and continue; if red, `git reset --hard` that change and try a different fix (never repeat the identical edit).

Maintain a one-line running state each turn: sites remaining / done / current failure (if any) / turns used of budget.

STOP the instant one of these is true: (a) SUCCESS — worklist empty and full verification passes; (b) BUDGET — `<max_turns>` reached; (c) NO-PROGRESS — remaining count unchanged 3 turns running; (d) BLOCKED — same site fails 3 distinct approaches. Report which arm tripped and the final state.
```

### 2. UI Framework Component Migration (class -> hooks / Options -> Composition API)

- **When:** Migrating a component library from one framework paradigm to another (React class -> function+hooks, Vue 2 Options -> Vue 3 Composition, Angular NgModule -> standalone) component by component while preserving behavior.
- **Loop:** assess (list components still on old pattern) -> pick ONE component -> rewrite it in isolation -> verify (unit test + snapshot/visual diff for that component only) -> commit/revert -> decide.
- **Stop:** SUCCESS: 0 components remain on old pattern AND full test suite + lint rule banning old pattern both pass · BUDGET: max turns / time reached · NO-PROGRESS: same component fails verification twice identically, or migrated-count flatlines 3 turns · BLOCKED: a component has no test coverage to verify behavior preservation
- **Model:** Use a stronger model (Opus xhigh, or Fable for the trickiest stateful components) when component logic is nontrivial — subtle effect/lifecycle regressions are easy to miss; simple presentational components can run on a cheaper model.

```text
Migrate every component from `<old_pattern>` to `<new_pattern>` (e.g., class components to function components with hooks). FROZEN GOAL: an ESLint/codemod rule flags zero `<old_pattern>` components, and the full test suite (`<test_command>`) plus any visual-snapshot check pass. Build the component worklist once, from `<discovery_command>`; do not touch components outside it, and do not refactor beyond what migration requires — new hooks-based helpers, prop renames, or style cleanups go to a backlog note, not this run.

Per turn: assess remaining worklist -> migrate exactly ONE component -> run that component's unit tests and snapshot diff -> if green, commit and remove it from the worklist; if red, revert and retry with a genuinely different approach (never resubmit the same diff).

Carry forward compact state: components done/remaining, last failure, turns used.

Stop on whichever trips first: SUCCESS (worklist empty + suite green); BUDGET (`<N>` turns); NO-PROGRESS (worklist count unchanged 3 turns, or same component fails twice identically); BLOCKED (component lacks tests to verify behavior preservation — escalate to human for a snapshot baseline before continuing).
```

### 3. Monorepo Import-Path / Package Rename Migration

- **When:** A package was renamed or moved in a monorepo and every importer across packages must be updated in dependency order without breaking the build graph or triggering cascading failures.
- **Loop:** assess (build import worklist in dependency order, leaves first) -> pick ONE importing file -> rewrite its import -> verify (that package's build/typecheck) -> commit/revert -> re-check for newly surfaced breaks -> decide.
- **Stop:** SUCCESS: 0 stale import references AND monorepo-wide build/typecheck green · BUDGET: max turns / wall-clock reached · NO-PROGRESS: stale-import count flat for 3 turns, or a file oscillates old->new->old · BLOCKED: a circular dependency surfaces that the rename can't resolve without an architecture decision
- **Model:** A large-context model (e.g. Opus with 1M context) helps hold the whole dependency graph in view; escalate to Fable-tier only if the rename triggers deep circular-dependency redesign questions.

```text
Migrate every import of `<old_package_path>` to `<new_package_path>` across this monorepo. FROZEN GOAL: `<grep_command>` for the old path returns zero hits, and `<monorepo_build_command>` (typecheck + build, all packages) is fully green. First, build the full worklist of importing files in dependency order, leaf packages first — this ordering matters because fixing a leaf can cascade upward.

Each turn: assess the worklist -> pick ONE file -> update its import(s) only -> verify by building/typechecking just that file's package -> commit if green, `git reset --hard` if red and pick a different fix (e.g., a re-export shim) rather than repeating the same edit. Never batch multiple files in one turn — cascading breaks must be attributable to exactly one change.

Track compact state: files done/remaining, packages still red, turns used, last blocker.

Halt on the first true condition: SUCCESS (zero stale imports, full graph builds); BUDGET (`<N>` turns/`<T>` minutes); NO-PROGRESS (remaining count unchanged 3 turns, or a file toggles old/new repeatedly); BLOCKED (a genuine circular-dependency or ownership question needs a human decision).
```

### 4. Gradual Type Migration (JS -> TS strict-mode ratchet)

- **When:** Converting files to TypeScript, or turning on strict/noImplicitAny file-by-file, where the exit criterion is a monotonically shrinking type-error count rather than a simple boolean pass/fail per file.
- **Loop:** assess (run type-checker for per-file/total error counts) -> pick ONE file (lowest error count first) -> add/fix types -> verify (scoped typecheck + full-repo typecheck for regressions) -> commit/revert -> update ratchet -> decide.
- **Stop:** SUCCESS: target scope has 0 typecheck errors AND the exemption/ratchet list is empty · BUDGET: max turns reached · NO-PROGRESS: total error count hasn't decreased for 3 consecutive turns · BLOCKED: errors stem from an untyped third-party dependency requiring a human decision on @types vs. local declarations
- **Model:** This scenario most needs top-tier reasoning (Opus xhigh or Fable): inferring correct types for genuinely dynamic JS requires judgment, and a weaker model tends to reach for `any`, which quietly defeats the goal via Goodhart.

```text
Migrate this codebase to strict TypeScript, one file at a time, using an error-count ratchet. FROZEN GOAL: `<typecheck_command>` reports 0 errors across `<target_scope>`, and the ratchet/exemption list is empty. Snapshot the current per-file error counts now — that snapshot is your worklist and must only shrink, never grow silently.

Each turn: assess the ratchet -> pick ONE file, lowest error count first to build momentum -> add types or fix violations for that file only -> verify by re-running the type-checker scoped to that file plus a full-repo typecheck to confirm no regressions elsewhere -> if total errors decreased, commit and update the ratchet; if flat or worse, revert and try a different typing approach (e.g., a narrower type vs. an assertion) rather than repeating the same fix.

Carry forward each turn: total errors remaining, files fully clean, last delta, turns used.

Stop on first trip: SUCCESS (0 errors, ratchet empty); BUDGET (`<N>` turns); NO-PROGRESS (total error count unchanged 3 turns straight); BLOCKED (errors trace to an untyped dependency needing a human call on adding `@types` vs. writing a local declaration).
```

### 5. Database Column/Field Rename Propagation

- **When:** A DB column or model field is being renamed and the change must propagate through ORM models, raw SQL, migrations, and serializers/API contracts, verified against a real shadow database rather than static search alone.
- **Loop:** assess (grep for old field across ORM/SQL/migrations/serializers) -> pick ONE reference site -> transform -> verify (narrow test + migration dry-run on shadow DB) -> commit/revert -> decide.
- **Stop:** SUCCESS: 0 references to old field outside an approved backward-compat alias AND migration dry-run + full integration suite pass on the shadow DB · BUDGET: max turns reached · NO-PROGRESS: reference count flat for 3 turns · BLOCKED: a reference lives in a third-party integration or external API contract that can't be unilaterally changed
- **Model:** Real blast radius: use the strongest available model (Opus xhigh, or Fable for irreversible production schemas) and never let the agent apply the migration to a live database without explicit human confirmation, per standing HITL policy.

```text
Rename the field `<old_field>` to `<new_field>` everywhere it's referenced: ORM models, raw SQL, migrations, serializers, API schemas. FROZEN GOAL: `<grep_command>` finds zero remaining references (excluding an explicitly approved backward-compat alias), the migration applies cleanly to a shadow/test database, and the full integration suite passes against it. Build the reference worklist once via `<discovery_command>`; do not rename unrelated fields you notice along the way — log those to a backlog instead.

Per turn: assess worklist -> transform exactly ONE reference site -> verify with the narrowest relevant test PLUS a migration dry-run on the shadow DB — never trust grep alone as your verifier here, data-layer changes need a real dry-run -> commit if green, revert if red and choose a different fix.

Carry state forward: sites done/remaining, shadow-DB status, turns used.

Stop at the first true arm: SUCCESS (worklist empty, dry-run + suite green); BUDGET (`<N>` turns); NO-PROGRESS (unchanged count 3 turns); BLOCKED (a reference sits in an external contract or integration you can't unilaterally change — surface it and stop; never apply an untested migration to a real database).
```

### 6. Infrastructure-as-Code Provider/Resource Syntax Migration

- **When:** An IaC provider (Terraform/Pulumi/CloudFormation) deprecates resource syntax or bumps a major version, and every resource block must be updated without triggering an unintended destroy/replace in the plan.
- **Loop:** assess (list resources still on deprecated syntax) -> pick ONE resource block -> rewrite it -> verify (validate + plan, inspect diff for destructive actions) -> commit/revert -> decide.
- **Stop:** SUCCESS: 0 resources on deprecated syntax AND plan shows zero unexpected create/destroy/replace actions · BUDGET: max turns reached · NO-PROGRESS: remaining-resource count flat for 3 turns · BLOCKED: plan shows an unavoidable destructive replace that needs human sign-off before any apply
- **Model:** Keep at daily-driver strength or above; plan diffs need careful reading against real infrastructure. Treat the BLOCKED destructive-plan arm as a hard stop requiring explicit human confirmation before any `apply`, consistent with irreversible-action safety rules.

```text
Migrate every `<resource_type>` block off the deprecated `<old_provider_syntax>` to `<new_provider_syntax>`. FROZEN GOAL: `<lint_or_grep_command>` finds no deprecated blocks, and `<plan_command>` (validate + plan) shows zero unexpected create/destroy/replace actions versus the pre-migration state — a clean plan is your independent verifier, not just "it validates." List every affected resource block now as your fixed worklist.

Each turn: assess worklist -> rewrite exactly ONE resource block -> run `<validate_command>` then `<plan_command>` and read the diff line by line -> if the plan shows only in-place updates (no replace/destroy), commit; if it shows anything destructive or fails validation, revert and try an alternate migration approach (e.g., a `moved` block or state import) rather than repeating the same edit.

State each turn: resources done/remaining, last plan diff summary, turns used.

Stop immediately on: SUCCESS (worklist empty, plan clean); BUDGET (`<N>` turns); NO-PROGRESS (count flat 3 turns); BLOCKED (a resource cannot be migrated without a destructive replace — do NOT apply; escalate for human approval before any `apply`).
```

### 7. Security Remediation Codemod (unsafe-pattern removal)

- **When:** A SAST/security scanner (semgrep, bandit, CodeQL, etc.) flags an unsafe pattern (raw string-built SQL, unsanitized innerHTML/eval, hardcoded secrets) across the codebase and each instance must be fixed and verified by an independent rescan, not the author's own read of the diff.
- **Loop:** assess (rerun scanner for current finding list) -> pick ONE finding -> fix it with the safe pattern -> verify (rescan that file + run relevant tests) -> commit/revert -> decide.
- **Stop:** SUCCESS: scanner reports 0 findings for the target rule(s) AND full test suite passes · BUDGET: max turns reached · NO-PROGRESS: open-finding count flat for 3 turns · BLOCKED: a finding looks like a false positive or needs an architectural fix beyond a local edit
- **Model:** Pair a strong model (Opus/Fable) with the fix while keeping the scanner as a separate, non-LLM verifier — this is the cleanest instance in the set of 'verify with an independent signal, not self-assessment.'

```text
Remediate every `<scanner_rule_id>` finding (e.g., unsafe string-built SQL, unsanitized `innerHTML`) reported by `<scanner_command>`. FROZEN GOAL: rerunning `<scanner_command>` reports zero findings for this rule, and the full test suite (`<test_command>`) still passes. Do NOT use your own read of the code as verification — the scanner rerun is the independent signal that decides done, since it is a different mechanism than the one making the fix. Snapshot the current finding list as your worklist now.

Per turn: assess remaining findings -> fix exactly ONE, using the safe pattern (parameterized query, sanitizer, escaping, etc.) -> verify by rerunning the scanner on that file AND the relevant tests -> commit if the finding is gone and tests pass; revert and try a different fix if not — never re-apply an identical patch that already failed.

Carry state: findings open/fixed, last scanner output, turns used.

Stop on first trip: SUCCESS (0 findings, suite green); BUDGET (`<N>` turns); NO-PROGRESS (open-finding count unchanged 3 turns); BLOCKED (finding looks like a false positive, or the fix needs an architectural change — do not suppress it yourself, escalate to a human).
```

### 8. Test-Framework Migration with Mutation-Check Verification

- **When:** Porting an existing test suite from one testing framework/API to another (e.g. Enzyme -> React Testing Library) file by file, where the hard part is verifying without using the very thing being rewritten as its own proof.
- **Loop:** assess (list test files still on old framework) -> pick ONE test file -> port it -> verify (passes clean + fails under a deliberate source break + coverage held) -> commit/revert -> decide.
- **Stop:** SUCCESS: 0 files remain on old framework AND full suite passes under new framework AND coverage >= baseline · BUDGET: max turns reached · NO-PROGRESS: files-remaining count flat for 3 turns · BLOCKED: a test relies on an old-framework-only capability (e.g. shallow-render internals) with no direct equivalent
- **Model:** Designing a meaningful mutation/source-break requires real judgment, so favor a stronger model (Opus xhigh) for the first several files; once the pattern is established, a cheaper model can handle high-volume, low-complexity remaining files.

```text
Port every test file from `<old_framework>` to `<new_framework>`. FROZEN GOAL: 0 files remain on `<old_framework>`, the full suite passes under `<new_framework>`, and coverage is >= the pre-migration baseline (`<baseline_pct>`). Beware Goodhart: a ported test passing is NOT sufficient proof — also confirm it still catches the bug it's meant to catch, e.g., by temporarily breaking the source and confirming the new test fails (a mutation check), then restoring the source.

Per turn: assess remaining worklist -> port exactly ONE test file -> verify: (a) it passes clean, (b) it fails under a deliberate one-line source break, then revert the break, (c) coverage hasn't dropped -> commit if all three hold, else revert and retry with a different porting approach.

Carry forward: files done/remaining, coverage delta, last mutation-check result, turns used.

Stop on first true arm: SUCCESS (worklist empty, suite green, coverage >= baseline); BUDGET (`<N>` turns); NO-PROGRESS (remaining count flat 3 turns); BLOCKED (old-framework-only capability with no equivalent — escalate for a test-redesign decision).
```
