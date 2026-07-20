# Config Drift / IaC Reconcile

`config-drift` — 2 loop prompts.

### 1. IaC Reconcile to Declared Desired State

- **When:** Live infrastructure has drifted from the declared Infrastructure-as-Code and must be driven back to a clean, empty plan and a passing policy check — without hand-editing state to fake convergence.
- **Loop:** assess drift from `plan` -> apply ONE targeted change (gated on human approval if destructive) -> independently re-run plan + policy -> commit/revert -> decide
- **Stop:** SUCCESS: two consecutive `<plan_cmd>` runs report a zero-change plan (0 add/0 change/0 destroy) AND `<policy_check_cmd>` passes · BUDGET: `<max_iterations>` or `<max_wall_clock>` reached · NO-PROGRESS: planned-change count flat for 3 turns despite a strategy change · BLOCKED: a reconciling action is destructive/irreversible (destroy, force-replace, data-loss) and the `<approval_gate>` is uncleared, a resource is managed outside `<iac_repo>`, or provider credentials/quota block apply
- **Model:** Strong reasoning model — root-causing drift (manual console edit vs provider default vs config bug) and judging blast radius is high-stakes; a cheap model tends to apply too broadly or paper over drift. The verifier must be independent because the agent that applies a change cannot certify its own success: only the tool's own plan/diff computed against real provider state, plus a separate policy engine, proves convergence. "I ran apply" or a hand-edited state file can yield an empty plan while the infra is actually wrong.

```text
GOAL (frozen — do not redefine mid-loop)
Drive the live infrastructure in <live_environment> to exactly match the declared IaC in <iac_repo> at pinned revision <iac_ref>, until <plan_cmd> (e.g. `terraform plan -detailed-exitcode`) reports a zero-change plan AND <policy_check_cmd> passes. Desired state = the committed IaC + variables in <var_file>; policy = <policy_bundle> (e.g. OPA/Conftest/Sentinel rules: allowed regions, mandatory tags, encryption-at-rest, no public ingress). Do NOT change <iac_repo>, <var_file>, or <policy_bundle> to close the gap — they are the frozen contract.

INDEPENDENT VERIFIER
Convergence is proved only by <plan_cmd> returning an empty diff (0 to add / 0 to change / 0 to destroy) computed by the tool against the real provider API, AND <policy_check_cmd> returning pass on that plan. "Apply succeeded", a green pipeline, or a resource that "looks applied" is not proof — apply can partially succeed, drift can reappear, and providers inject defaults. Editing <state_backend>, importing to mask a mismatch, or using -refresh-only / targeted state ops to manufacture an empty plan all fake convergence and are banned. The plan and the policy engine are separate mechanisms from your apply logic — that separation is the whole point.

PER-TURN SHAPE
1. ASSESS — run <plan_cmd> read-only; rank drifted resources by count/blast radius; classify each drift (manual console edit, provider default, missing resource, genuine IaC bug). Pick the single most-impactful drift to close.
2. ONE ACTION — reconcile exactly that one drift via a single `apply -target=<addr>` (or the smallest equivalent), OR fix one genuine IaC bug in a branch and re-plan. If the action is destructive/irreversible (destroy, force-replace, storage/data mutation, anything the plan flags as data-loss), STOP and route to <approval_gate> — do not apply until a human clears it.
3. VERIFY — re-run <plan_cmd> for the WHOLE config (not just the target) and <policy_check_cmd>; confirm the targeted drift is gone and no new drift or policy violation appeared elsewhere.
4. DECIDE — commit (record the applied change + plan output) on improvement; revert the last action on regression; park items behind <approval_gate>; escalate on repeated failure of the same action.

CARRY-FORWARD STATE (compact)
Planned-change count per turn (add/change/destroy), drifts reconciled, drifts remaining ranked, actions parked behind <approval_gate> with a one-line reason each, IaC bugs fixed, iterations/budget used.

ACTION BAN
Never edit or import into <state_backend> to fake an empty plan; never run apply without -target scoping to batch several drifts in one turn; never apply a destroy/replace/data-loss action without a cleared <approval_gate>; never loosen <policy_bundle> or add -refresh-only / lifecycle-ignore just to pass; never retry an identical failed apply verbatim — change approach or escalate; park "while I'm here" improvements to backlog, don't apply them.

STOP — halt on the FIRST of:
SUCCESS (two consecutive <plan_cmd> runs report a zero-change plan AND <policy_check_cmd> passes) | BUDGET (<max_iterations> or <max_wall_clock> reached) | NO-PROGRESS (planned-change count flat for 3 turns despite a strategy change) | BLOCKED (a reconciling action is destructive/irreversible and <approval_gate> is uncleared, a resource is managed outside <iac_repo>, or provider credentials/quota block apply — surface the plan and everything tried for human sign-off)
```

### 2. Manifest / Config Conformance to a Frozen Spec + Policy

- **When:** Deployed config (e.g. Kubernetes manifests, app config) has diverged from a frozen desired spec and/or violates a security/resource policy, and must be reconciled without weakening the spec or the policy.
- **Loop:** assess dry-run diff + policy report -> apply ONE conforming fix (gated on human approval if destructive) -> independently re-run dry-run diff + policy engine -> commit/revert -> decide
- **Stop:** SUCCESS: `<dry_run_diff_cmd>` shows zero diff vs the frozen spec AND `<policy_engine>` reports zero violations, on two consecutive runs · BUDGET: `<max_iterations>` reached · NO-PROGRESS: combined (diff-hunks + policy-violations) count flat for 3 turns despite a strategy change · BLOCKED: a conforming fix needs a destructive/irreversible change (delete PVC, mutate an immutable field forcing pod/StatefulSet recreation, rotate a live secret) with `<approval_gate>` uncleared, or spec and policy conflict irreconcilably
- **Model:** Mid-to-high reasoning model. Once the frozen spec and policy bundle exist most fixes are mechanical, but distinguishing a safe security-context/limits patch from an immutable-field replacement that forces a restart is a production-impacting judgment call. The verifier must be independent because the agent editing manifests can't certify its own change: only a server-side dry-run diff against the live cluster plus a separate admission/policy engine evaluating the rendered objects proves conformance. A manifest that "should" conform, or one you hand-graded, is not proof.

```text
GOAL (frozen — do not redefine mid-loop)
Reconcile the deployed config in <target_namespace>/<cluster> to exactly match the frozen desired spec <desired_spec_dir> at pinned revision <spec_ref> AND satisfy every rule in <policy_bundle>, until <dry_run_diff_cmd> shows no diff from the spec AND <policy_engine> reports zero violations. Desired spec = the pinned manifests/values; policy = <policy_bundle> (e.g. OPA Gatekeeper / Kyverno / Conftest: resource requests+limits set, non-root securityContext, readOnlyRootFilesystem, no plaintext secrets in env/ConfigMaps, approved image registries, no `:latest`). The spec and policy are the contract — do NOT edit <desired_spec_dir> or <policy_bundle> to make a check pass.

INDEPENDENT VERIFIER
Conformance is proved only by (a) <dry_run_diff_cmd> (e.g. `kubectl diff --server-side`, or render-then-diff) showing an empty diff between the rendered config and the frozen spec against the LIVE cluster, AND (b) <policy_engine> evaluating the rendered objects and returning zero violations. A manifest that "looks right", a client-side lint, or your own reading of the YAML is not verification — server-side dry-run catches defaulting/admission mutation and live drift a local render misses, and the policy engine is a mechanism separate from your editing. Never disable/suppress a policy rule (annotation exclusion, --skip, namespace exemption) or point the diff at a stale/local copy to manufacture a pass.

PER-TURN SHAPE
1. ASSESS — run <dry_run_diff_cmd> and <policy_engine>; list diff hunks vs spec and policy violations; pick the single highest-impact nonconformance (prefer security/policy violations, then spec drift).
2. ONE ACTION — apply exactly one conforming edit to the deployed config (patch one field, add the missing limits block, fix one securityContext, move one plaintext secret to <secret_ref>) — nothing else. If the fix requires a destructive/irreversible change (delete a PVC/PV, mutate an immutable field forcing pod/StatefulSet/Deployment recreation, rotate a live secret, incur downtime), STOP and route to <approval_gate>; do not apply until a human clears it.
3. VERIFY — re-run <dry_run_diff_cmd> AND <policy_engine> across the FULL object set; confirm the targeted item is resolved and no new diff or violation appeared elsewhere.
4. DECIDE — commit the patched config on improvement; revert the last edit on regression; park approval-gated items; escalate after repeated failure on the same item.

CARRY-FORWARD STATE (compact)
Diff-hunk count and policy-violation count per turn, items reconciled, items remaining ranked, fixes parked behind <approval_gate> with a one-line reason each, secrets migrated to <secret_ref>, edits already tried per object (never repeat a failed one), iterations/budget used.

ACTION BAN
Never edit <desired_spec_dir> or <policy_bundle> to close the gap; never suppress/exempt a policy rule to pass; never batch multiple field changes in one turn; never apply a destructive/irreversible change (PVC delete, immutable-field replace, secret rotation, forced restart) without a cleared <approval_gate>; never diff against a local/stale copy instead of the live cluster; never inline a plaintext secret to satisfy the spec — reference <secret_ref>; park unrelated improvements to backlog.

STOP — halt on the FIRST of:
SUCCESS (<dry_run_diff_cmd> shows zero diff vs the frozen spec AND <policy_engine> reports zero violations on two consecutive runs) | BUDGET (<max_iterations> reached) | NO-PROGRESS (combined diff-hunk + policy-violation count flat for 3 turns despite a strategy change) | BLOCKED (a conforming fix needs a destructive/irreversible change with <approval_gate> uncleared, the spec and policy conflict irreconcilably, or a required <secret_ref> / cluster credential is unavailable — surface the diff, violations, and everything tried for human sign-off)
```
