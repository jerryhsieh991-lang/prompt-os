# Review by Dimensions

`review-dimensions` — 8 loop prompts.

### 1. General PR Review — Bugs / Security / Perf / Clarity

- **When:** A pull request or diff needs a full-spectrum review before merge and there's no specialized loop (security, perf, a11y, etc.) available yet — this is the default review-dimensions loop.
- **Loop:** assess which hunk x dimension pairs are unchecked -> pick ONE pair -> raise at most one candidate finding -> verify independently (test/scanner/profiler/fresh read) -> log CONFIRMED/REJECTED -> fix+recheck if confirmed -> reassess remaining coverage
- **Stop:** SUCCESS: all changed hunks checked against all 4 dimensions and zero unverified findings remain · BUDGET: turn or wall-clock cap reached · NO-PROGRESS: 2 consecutive turns with no new confirmed finding · BLOCKED: needs author clarification on intent or verification requires an unavailable env/credential
- **Model:** Opus-class model at high effort is the right default for mixed-dimension judgment calls. Escalate to a stronger/deeper-reasoning tier only when the diff touches security-critical or compliance-sensitive paths. A cheaper mid-tier model is fine for low-stakes internal tooling PRs.

```text
Review the attached diff against exactly four dimensions: bugs, security, performance, clarity. Freeze this as the goal: every changed hunk has been checked against all four dimensions, and every finding you raise has been independently verified (reproduced with a failing test, a security scanner, a profiler trace, or a fresh-frame second read) — not just asserted. Each turn: assess which hunk/dimension pairs are still unchecked, pick exactly ONE, produce at most one candidate finding, verify it independently, then log it as CONFIRMED or REJECTED with evidence. Fix only what's CONFIRMED, one fix per turn, and re-verify before moving on. Carry forward a compact state block: dimensions covered, open findings, budget remaining. Stop at whichever trips first: (1) SUCCESS — full coverage, no unverified findings remain; (2) BUDGET — turn/time cap hit; (3) NO-PROGRESS — 2 turns with no new confirmed finding; (4) BLOCKED — needs human input. Do not expand scope beyond the diff.
```

### 2. Security Vulnerability Review with PoC/Exploit-Chain Verification

- **When:** A dedicated security audit of code or config where every reported finding must survive exploit verification, not just static pattern matching, before it's written up.
- **Loop:** assess unchecked entry points/vuln classes -> pick ONE -> attempt PoC or exploit-chain reasoning -> classify EXPLOITABLE/THEORETICAL/FALSE-POSITIVE -> fresh-frame verification confirms before reporting -> log -> next
- **Stop:** SUCCESS: full attack surface covered and every reported finding carries a PoC or explicit exploit-chain evidence · BUDGET: iteration or time cap reached · NO-PROGRESS: 2 turns with no new confirmed finding or surface reduction · BLOCKED: needs a sandbox, credentials, or human sign-off on testing scope (e.g., production)
- **Model:** Use the strongest available reasoning tier at high effort — exploit-chain construction is where weaker models produce false positives/negatives. Reserve the most capable frontier model for novel, high-value targets (auth bypass, crypto); do not downgrade to a lightweight model for this loop.

```text
Frozen goal: every entry point in the attack surface listed below has been checked for injection, authz/authn, secrets exposure, and unsafe deserialization, and every reported finding is backed by a working proof-of-concept or an explicit, step-by-step exploit chain — never a bare pattern match. Each turn: assess which entry points/vuln classes remain unchecked, pick exactly ONE, attempt to build a PoC or exploit-reasoning chain against it, and classify the result EXPLOITABLE, THEORETICAL (needs conditions you can't create here), or FALSE-POSITIVE. A separate verification pass, run in a fresh frame rather than your authoring context, must confirm EXPLOITABLE before it is reported. Log one line of state per turn: surface remaining, confirmed count, budget left. Never retry an identical exploit attempt verbatim — change technique or move on. Stop on: SUCCESS (full surface covered, all findings verified), BUDGET (cap reached), NO-PROGRESS (2 turns, nothing new confirmed), or BLOCKED (need sandbox/creds/scope approval) — whichever comes first.
```

### 3. Performance Review with Benchmark-Verified Findings

- **When:** Reviewing a diff or module for perf regressions or opportunities where every claim must be backed by a measured benchmark number, not intuition about what 'should' be faster.
- **Loop:** assess profiler/flamegraph for current bottleneck -> pick ONE candidate optimization -> baseline -> apply single reversible change -> rerun same benchmark -> keep+commit if improved and tests pass, else revert -> log
- **Stop:** SUCCESS: target metric meets/beats the frozen threshold and the existing test suite is green · BUDGET: benchmark-run or wall-clock cap reached · NO-PROGRESS: metric hasn't moved beyond the noise floor for 3 consecutive turns · BLOCKED: needs profiling access, representative data, or a benchmark harness that doesn't exist yet
- **Model:** A mid-tier or cheaper fast model handles the mechanical benchmark-and-revert cycle well and keeps iteration cost low. Escalate to a top reasoning tier only when cheap-model attempts plateau and a non-obvious algorithmic change is needed.

```text
Frozen goal: [metric, e.g., p95 request latency] reaches <= [threshold] on the fixed benchmark harness below, with the existing test suite still green. Each turn: assess the profiler/flamegraph for the current bottleneck, pick exactly ONE candidate optimization, record the baseline benchmark number, apply that single reversible change, rerun the SAME benchmark (an independent signal from your own reasoning), and compare. Keep the change and commit only if the metric improved AND tests pass; otherwise git-revert immediately. Never batch multiple optimizations in one turn — you must be able to attribute any regression to exactly one change. Carry forward: current metric, best-so-far commit, changes already tried including failed ones, budget remaining. Stop at the first of: SUCCESS (threshold met, tests green), BUDGET (run/time cap), NO-PROGRESS (metric flat within noise for 3 turns — try a different bottleneck or halt), BLOCKED (missing profiler/harness/data).
```

### 4. API Design / Contract Review

- **When:** Reviewing REST or GraphQL API changes for convention drift and breaking changes, where compliance must be verified against a schema-diff or contract-test tool rather than eyeballed.
- **Loop:** assess unchecked endpoints -> pick ONE -> check convention + backward-compat -> run contract-diff/schema tool as verifier -> log CLEAN/FIXED/BREAKING-VERSIONED -> fix at most one issue and rerun tool -> next
- **Stop:** SUCCESS: every changed endpoint is CLEAN or has breaking changes explicitly versioned, with zero unresolved breaks · BUDGET: endpoint or turn cap reached · NO-PROGRESS: 2 turns with no endpoint resolved · BLOCKED: a breaking change needs a product/API-owner decision outside the reviewer's authority
- **Model:** A top-tier model at high effort earns its keep on ambiguous compatibility tradeoffs (is this actually breaking?). Once the style guide and contract tool make checks mostly mechanical, a mid-tier model can run the loop at lower cost.

```text
Frozen goal: every endpoint touched in this diff passes an independent schema-diff/contract-test tool, not your own read, with no unresolved breaking changes — any breaking change must be either reverted or explicitly versioned per the project's API style guide. Loop, one endpoint per turn: assess remaining unchecked endpoints, pick ONE, check naming/pagination/error-shape convention plus backward compatibility, then run the actual contract-diff tool as the verifier. Log CLEAN, FIXED, or BREAKING-VERSIONED with the tool's output as evidence. Apply at most one fix per turn and rerun the tool before moving on — never bundle fixes across endpoints. Maintain compact state: endpoints checked/remaining, open breaking changes, budget left. Stop on whichever hits first: SUCCESS (all endpoints clean or properly versioned), BUDGET (endpoint/turn cap), NO-PROGRESS (2 turns, no endpoint resolved), BLOCKED (a breaking change needs a product/API-owner judgment call you can't make). Do not redesign endpoints beyond fixing the flagged issue.
```

### 5. Technical Documentation / Content Clarity Review

- **When:** Reviewing docs, READMEs, or long-form content for clarity and accuracy — a non-code review dimension verified by fact-checking and a fresh-reader pass rather than the author's own re-reading.
- **Loop:** assess unchecked/FLAGGED sections -> pick ONE -> identify one clarity or accuracy issue -> verify claim against real source -> rewrite only that section -> fresh-frame comprehension recheck -> mark PASSED -> next
- **Stop:** SUCCESS: every section PASSED a fresh-reader comprehension check and every factual claim is source-verified · BUDGET: section or turn cap reached · NO-PROGRESS: 2 turns without a section moving from FLAGGED to PASSED · BLOCKED: a factual claim can't be verified without an unavailable source or subject-matter expert
- **Model:** A mid-tier model handles clarity passes well at volume and low cost. Escalate to a top reasoning tier for high-stakes public-facing docs (security advisories, breaking-change notices) where nuance and precision matter more than throughput.

```text
Frozen goal: every section of this document passes two independent checks — a fresh-reader comprehension check (can someone with no context restate the section's point correctly?) and a source-verification check (every factual claim traces to a citation or the actual codebase, not memory). Loop one section per turn: assess which sections are still FLAGGED or unchecked, pick ONE, identify at most one clarity or accuracy issue, verify it against the real source rather than your own re-reading, rewrite only that section, then have a fresh frame re-check comprehension before marking PASSED. Never let the author of a section also be its sole verifier. Track compact state: sections PASSED/FLAGGED/unchecked, unresolved claims, budget left. Stop at the first of: SUCCESS (all sections PASSED, all claims sourced), BUDGET (turn/section cap), NO-PROGRESS (2 turns, no section advances), BLOCKED (a claim needs an SME or source you don't have). Do not add new content or restructure beyond fixing flagged issues.
```

### 6. Database Schema / Migration Review

- **When:** Reviewing a schema change or migration PR for correctness, indexing, and safety, where claims must be verified via EXPLAIN plans and a dry-run migration rather than inspection alone.
- **Loop:** assess unverified migration steps -> pick ONE -> apply to dry-run env -> verify via EXPLAIN/ANALYZE output -> log VERIFIED/REVERTED, revert on failure -> next
- **Stop:** SUCCESS: dry-run migration completes cleanly on prod-like data, target queries hit expected indexes, no locking issue flagged · BUDGET: migration-step or time cap reached · NO-PROGRESS: 2 turns without a step moving from unverified to VERIFIED · BLOCKED: needs a prod-like data snapshot or DBA sign-off on a locking migration
- **Model:** A mid-tier model is sufficient for mechanically reading EXPLAIN-plan output. Escalate to a top reasoning tier when weighing lock-contention or replication-lag tradeoffs on large, high-traffic tables.

```text
Frozen goal: the migration applies cleanly to a prod-like data snapshot in a dry run, every query it's meant to speed up hits the expected index per EXPLAIN/ANALYZE output, and no step causes table-locking beyond the agreed maintenance window. Loop one migration step per turn: assess which steps are unverified, pick ONE — one index, one column change — apply it to the dry-run environment, verify with the database's own EXPLAIN/ANALYZE output rather than your prediction of the plan, and log VERIFIED or REVERTED. Revert immediately on any failure or unexpected lock; never carry a broken step forward. State to carry: steps verified/remaining, current dry-run schema hash, budget left. Stop at the first of: SUCCESS (full migration verified end-to-end), BUDGET (cap reached), NO-PROGRESS (2 turns, no step verified), BLOCKED (no prod-like snapshot, or a locking step needs DBA approval). Do not add unrelated schema improvements.
```

### 7. Accessibility (a11y / WCAG) Review

- **When:** Reviewing UI code or markup for WCAG 2.2 AA compliance, where each finding must be confirmed by an automated scanner plus a manual keyboard/contrast check rather than visual inspection.
- **Loop:** assess unchecked components -> pick ONE -> run scanner + manual keyboard/contrast check -> log VIOLATIONS-FOUND/CLEAN -> fix one violation, rerun scanner -> next
- **Stop:** SUCCESS: scanner reports zero violations on all changed components and manual keyboard/contrast checks pass on each interactive element · BUDGET: component or turn cap reached · NO-PROGRESS: 2 turns without the violation count decreasing · BLOCKED: a violation requires a design-system/color-token decision outside the reviewer's authority
- **Model:** A mid-tier model is sufficient since the scanner supplies the ground truth. Reserve a top reasoning tier for ambiguous ARIA-pattern judgment calls on custom widgets that the scanner can't fully evaluate.

```text
Frozen goal: an automated accessibility scanner such as axe-core reports zero violations on every component touched in this diff, and each interactive element passes a manual keyboard-only navigation check and a contrast check — self-assessment doesn't count. Loop one component per turn: assess remaining unchecked components, pick ONE, run the scanner as the independent verifier, and separately tab through it by keyboard to confirm focus order and visible focus states. Log VIOLATIONS-FOUND or CLEAN with the scanner's raw output. Fix at most one violation per turn, then rerun the scanner on that component before moving on — never fix multiple issues blind. Carry forward: violation-count trend, components CLEAN/remaining, budget left. Stop at the first of: SUCCESS (zero violations, manual checks pass), BUDGET (cap reached), NO-PROGRESS (2 turns, violation count unchanged), BLOCKED (fix needs a design-system/color-token decision outside your authority). Do not redesign components beyond the flagged violations.
```

### 8. Infrastructure-as-Code / Cloud Config Review

- **When:** Reviewing Terraform, Kubernetes, or CloudFormation changes for security misconfiguration and drift, where findings must be verified by a policy-as-code scanner and a plan diff rather than manual reading of HCL/YAML.
- **Loop:** assess current scanner output -> pick ONE finding -> smallest reversible fix -> rerun scanner + fresh plan/diff -> log FIXED/ACCEPTED-RISK -> next
- **Stop:** SUCCESS: scanner reports zero HIGH/CRITICAL findings and plan/diff shows only intended resource changes · BUDGET: resource or turn cap reached · NO-PROGRESS: 2 turns without the finding count decreasing · BLOCKED: a finding needs infra-owner risk acceptance or cost-tradeoff approval outside the reviewer's authority
- **Model:** Given the blast radius of cloud misconfiguration, use a top-tier model at high effort by default. A mid-tier model is acceptable for routine low-risk changes such as tag additions to save cost.

```text
Frozen goal: a policy-as-code scanner such as tfsec, checkov, or OPA reports zero HIGH/CRITICAL findings against this infra change's plan output, and plan/diff shows only the intended resource changes with no incidental drift. Loop one resource or finding per turn: assess the current scanner output, pick ONE finding, fix it with the smallest reversible edit, then rerun the scanner AND a fresh plan/diff as the independent verifier — never trust your own read of the HCL/YAML. Log FIXED or ACCEPTED-RISK, the latter only with explicit sign-off, per finding. Never apply to a real environment mid-loop; work against plan/dry-run output only. Carry forward: findings fixed/remaining by severity, plan-diff summary, budget left. Stop at the first of: SUCCESS (zero HIGH/CRITICAL, diff matches intent), BUDGET (cap reached), NO-PROGRESS (2 turns, finding count unchanged), BLOCKED (a finding needs infra-owner risk acceptance or cost approval). Do not refactor unrelated modules while in this loop.
```
