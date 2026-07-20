# Dependency Upgrade

`dependency-upgrade` — 2 loop prompts.

### 1. Single-Dependency Major-Version Upgrade Loop

- **When:** You need to move exactly ONE dependency across a major-version boundary and repair the breakages that bump alone causes — guided by its changelog/breaking-changes notes — keeping build, typecheck, and the full test suite green, one dependency at a time.
- **Loop:** assess post-bump break list -> fix ONE breakage per the changelog (root cause, not symptom) -> run build + typecheck + full suite -> commit on improvement / revert on regression -> decide (revert the whole bump if not all-green within budget)
- **Stop:** SUCCESS: `<DEP>` pinned at `<TARGET_VERSION>`, build + typecheck + full suite all green, no test weakened · BUDGET: `<MAX_ITERATIONS>` reached · NO-PROGRESS: combined break count flat for 3 turns · BLOCKED: a removed/redesigned API has no viable replacement, or a peer-dependency conflict needs a human call
- **Model:** Mostly mechanical call-site chasing across many breakages — a cheaper high-volume model is cost-effective; escalate to a top-tier model when the major version removes or redesigns a core API and the replacement needs architectural judgment. The verifier must be independent because a model that both writes the fix and grades it will rationalize a skipped or loosened test as "passing" — only the unmodified build/typecheck/test trio can prove the bump is behavior-preserving rather than merely compiling.

```text
GOAL (frozen — do not redefine mid-loop)
With ONLY <DEP> bumped from <CURRENT_VERSION> to <TARGET_VERSION> and every other dependency pinned unchanged, `<build command>`, `<typecheck command>`, and the full test suite `<test command>` all pass with zero new failures and zero behavior change. Fix breakages the bump causes using <DEP>'s changelog/migration guide as the map for WHAT changed — but the three green gates, not the changelog, decide done. Scope is this one upgrade only: do not bump other deps, adopt new <DEP> features, or refactor unrelated code — park those.

INDEPENDENT VERIFIER
The trio `<build command>` + `<typecheck command>` + `<test command>` — external to your edits, none authored to match this change. The test suite is frozen: fixing a breakage means updating call sites/config to the new API, never editing, skipping, xfail-ing, or loosening a test (or lowering typecheck strictness) to turn red green. If a test genuinely encodes old-version behavior that the major version legitimately changed, flag it BLOCKED for a human — do not silently rewrite it. Reading the changelog is not verification; only the three gates are.

PER-TURN SHAPE
1. ASSESS — read current failures from build/typecheck/test; map each to the changelog entry that explains it; pick the ONE highest in the dependency chain (a root-cause API change clears many downstream errors at once).
2. ONE ACTION — apply the smallest changelog-guided call-site or config fix for that one breakage.
3. VERIFY — run `<build command>`, `<typecheck command>`, then `<test command>`; count combined breakages against last known-good.
4. DECIDE — combined count dropped and nothing regressed -> commit; rose or held -> git reset and try a materially different fix next turn; if the whole bump can't reach all-green within remaining budget -> revert to <CURRENT_VERSION>, leave baseline green, and report BLOCKED with the blocking API.

CARRY-FORWARD STATE (compact)
<DEP> target version; combined break count (build+typecheck+test); the one breakage in focus + its changelog entry; fixes already tried and ruled out; iterations left of <MAX_ITERATIONS>.

ACTION BAN
Never edit/skip/xfail/loosen a test or lower typecheck strictness to force green. Never bump a second dependency to dodge a break (that is a new loop). Never batch multiple breakage fixes before verifying. Never retry a reverted fix verbatim. Never leave the bump half-applied at turn end — either all-green-and-committed, or reverted to the last known-good.

STOP — halt on the FIRST of:
SUCCESS (<DEP> at <TARGET_VERSION>; build + typecheck + full suite all green; no test weakened) | BUDGET (<MAX_ITERATIONS> reached — revert the bump, leave baseline green) | NO-PROGRESS (combined break count unchanged for 3 straight turns — halt, don't grind) | BLOCKED (a removed/redesigned API has no compatible replacement, or a peer-dep/transitive conflict needs a human decision — revert and hand off).
```

### 2. Security-Driven Dependency Remediation Loop

- **When:** An SCA/vulnerability scanner flags known-vulnerable dependencies and you must bump each to a patched version until an independent re-scan reports no known vulns remain AND the suite still passes — without pulling in a new vulnerable transitive dep or breaking the build.
- **Loop:** assess scanner report (ranked by severity) -> bump ONE flagged dep to its nearest patched version -> re-scan + build + full suite -> commit on improvement / revert on regression -> decide
- **Stop:** SUCCESS: fresh re-scan reports zero known vulns at/above `<SEVERITY_FLOOR>` AND build + full suite green AND no new flagged transitive · BUDGET: `<MAX_ITERATIONS>` reached · NO-PROGRESS: open-vuln count flat for 3 turns · BLOCKED: no patched version exists, or the only fix is a breaking major/transitive change a human must approve
- **Model:** Routine patch bumps are mechanical and fine on a cheaper model; escalate to a stronger model when the only fix is a breaking major bump whose fallout needs judgment, or when transitive conflicts require dependency-graph reasoning. The verifier must be independent because the agent choosing the bump cannot also certify safety — only a fresh scan against the live advisory DB catches a vuln that moved into a newly-pulled transitive, and only the unmodified build+suite proves the patch didn't break behavior; self-attestation ("this version looks patched") is exactly the Goodhart trap a re-scan defeats.

```text
GOAL (frozen — do not redefine mid-loop)
Every dependency flagged by `<SCA scan command>` at or above <SEVERITY_FLOOR> is bumped to its nearest non-vulnerable version such that a FRESH independent re-scan reports zero remaining known vulnerabilities at/above that floor, AND `<build command>` plus the full test suite `<test command>` stay green, AND no bump introduces a new flagged transitive dependency. Scope is remediation only: patch to the minimum version that clears the advisory — do not opportunistically major-upgrade, refactor, or add features; park those.

INDEPENDENT VERIFIER
Two separate ground-truth signals, neither of which you author: (1) a fresh re-run of `<SCA scan command>` against the live advisory database and the actual resolved lockfile/dependency tree — not your reasoning about which version is safe, and re-resolved so newly-pulled transitives are re-checked too; (2) `<build command>` + `<test command>`. A vuln counts as remediated only when the re-scan no longer lists it. Never edit the scanner config, allowlist/ignore an advisory, or pin around a CVE to make the report green — a residual vuln may be accepted only as an explicit, human-approved accepted-risk recorded in state, never silenced.

PER-TURN SHAPE
1. ASSESS — read the current scanner report; pick the ONE flagged dependency with the highest severity (break ties by smallest version delta to a patched release).
2. ONE ACTION — bump that single dep to the nearest version that clears its advisory, re-resolving the lockfile.
3. VERIFY — re-run `<SCA scan command>` on the new tree, then `<build command>` and `<test command>`; compare open-vuln count (including any NEW transitive vuln the bump pulled in) and build/test status against last known-good.
4. DECIDE — open-vuln count dropped, no new vuln introduced, build + suite green -> commit; count rose, a new vuln appeared, or the build/suite broke -> git reset and try the next patched version, or a different dep, next turn.

CARRY-FORWARD STATE (compact)
Open-vuln count by severity; the dep in focus + its target patched version; bumps that introduced a new transitive vuln or broke the build (ruled out); accepted-risk items awaiting human sign-off; iterations left of <MAX_ITERATIONS>.

ACTION BAN
Never silence a vuln by editing scanner config, adding it to an ignore/allowlist, or lowering <SEVERITY_FLOOR> instead of patching it. Never skip/xfail a test that breaks after a bump. Never trade one CVE for another — a bump that introduces a new flagged transitive is a regression; revert it. Never batch several dep bumps before re-scanning (you'd lose which bump caused a new vuln or break). Never leave the lockfile unresolved or the build broken at turn end.

STOP — halt on the FIRST of:
SUCCESS (fresh re-scan reports zero known vulns at/above <SEVERITY_FLOOR> AND build + full suite green AND no new flagged transitive) | BUDGET (<MAX_ITERATIONS> reached — report remaining open vulns and their blocking reasons) | NO-PROGRESS (open-vuln count unchanged for 3 straight turns — halt, don't guess) | BLOCKED (a flagged dep has no patched version, or the only fix is a breaking major/transitive change needing human approval or an explicit accepted-risk decision — surface it and wait).
```
