# Compliance Audit (Policy-as-Code)

`compliance-audit` — 2 loop prompts.

### 1. Policy-as-Code Control Remediation (Frozen Ruleset)

- **When:** A system, config, or IaC bundle must be brought into conformance with a compliance policy set that is already encoded as executable rules (OPA/Rego, Conftest, Cloud Custodian), fixing one failing control at a time under an unchanging ruleset.
- **Loop:** assess engine output for failing controls -> apply ONE smallest reversible fix to the target -> re-run the frozen policy engine -> commit if that control now PASSES with no new violation, else revert -> decide continue/stop
- **Stop:** SUCCESS: the frozen `<POLICY_BUNDLE>` reports zero failing controls against `<TARGET_SYSTEM>` and the automated-floor caveat is recorded · BUDGET: control or turn cap `<BUDGET>` reached · NO-PROGRESS: `<K>` consecutive turns with the failing-control count unchanged (or an A->B->A pass/fail oscillation on one control) · BLOCKED: the only way to clear a control is to weaken the rule, OR the control depends on human/process attestation the engine cannot mechanically test (e.g. "management reviews access quarterly")
- **Model:** Mid-tier model runs the mechanical fix-and-rerun cycle cheaply; escalate to a top reasoning tier when a remediation touches auth, encryption, network exposure, or data-residency where a wrong fix has real blast radius. The verifier MUST be the frozen policy engine, not the model's own read — the agent that wrote the fix cannot also be the thing that certifies it passes, or it will rationalize green. Honest scope: a fully-green engine run is a NECESSARY floor, not proof of compliance — it proves the encoded controls hold at this instant on this snapshot; it says nothing about controls that live in process, evidence, or human judgment.

```text
GOAL (frozen — do not redefine mid-loop)
Bring <TARGET_SYSTEM> (config / IaC / cluster manifests) into conformance with <POLICY_BUNDLE> — the frozen policy-as-code ruleset for <FRAMEWORK> (e.g. CIS / SOC 2 / PCI-DSS), evaluated by <POLICY_ENGINE> (opa eval / conftest test / cloud-custodian run). Acceptance criterion: <POLICY_ENGINE> reports zero failing controls, every fix is attributable to one control, and no rule in <POLICY_BUNDLE> was edited, skipped, or exempted to get there. The ruleset and its severities are LOCKED at loop start: you remediate the system to satisfy the policy, never the policy to excuse the system.

INDEPENDENT VERIFIER
<POLICY_ENGINE> executing the unmodified <POLICY_BUNDLE> is the sole arbiter of pass/fail — it is independent because it is a separate, deterministic ruleset you did not author this turn and cannot re-interpret. It cannot rubber-stamp itself: a control counts as fixed only when the engine's own exit status / result JSON flips that control to PASS. Honest note: passing every automated control does NOT mean "compliant" — the engine only checks what was encodable as code against a point-in-time snapshot; process controls, evidence retention, and attestations sit outside its reach and are tracked separately as attestation-required.

PER-TURN SHAPE
1. ASSESS — read the latest <POLICY_ENGINE> output; pick exactly ONE failing control (highest severity first) as this turn's target: <FAILING_CONTROL_ID>.
2. ONE ACTION — make the smallest reversible edit to <TARGET_SYSTEM> that should satisfy <FAILING_CONTROL_ID>; touch nothing unrelated.
3. VERIFY — re-run <POLICY_ENGINE> over the WHOLE bundle (not just the one rule) and diff results: did <FAILING_CONTROL_ID> flip to PASS, and did the total failing set shrink with zero NEW failures introduced?
4. DECIDE — commit if the control passes and no new violation appeared; git-revert immediately if it still fails or any other control regressed; park to attestation-required if the control can only be met by human/process evidence; escalate if clearing it would require weakening a rule.

CARRY-FORWARD STATE (compact)
Controls: passing count, failing list by severity, this-turn target. Fixes committed (control -> one-line change). Attestation-required list (controls parked for human/process evidence). Regressions seen and reverted. Budget: turns / engine-runs remaining.

ACTION BAN
Never edit, disable, add an exception/waiver to, or lower the severity of any rule in <POLICY_BUNDLE> to force a pass. Never batch fixes for multiple controls in one turn — one control, one rerun, so any regression is attributable. Never retry the identical failed edit verbatim; change approach or park it. Never mark the system "compliant" or "audit-ready" from a green engine run — the truthful claim is "all encoded controls pass on this snapshot; attestation-required items remain open." Never apply changes to a live/production environment mid-loop; work against dry-run / plan / a copy only.

STOP — halt on the FIRST of:
SUCCESS (<POLICY_ENGINE> reports zero failing controls on unmodified <POLICY_BUNDLE>, attestation-required items listed, automated-floor caveat recorded) | BUDGET (<BUDGET> turns / engine-runs reached) | NO-PROGRESS (<K> turns with failing count unchanged, or one control oscillating pass/fail) | BLOCKED (clearing a control needs a rule weakened, or the control requires human/process attestation the engine cannot test)
```

### 2. Evidence-Backed Control Verification (One Control per Turn)

- **When:** Each required control in a frozen control set must be proven ACTUALLY satisfied by attaching mechanical evidence an independent checker validates against acceptance criteria — never accepted on assertion — one control at a time.
- **Loop:** assess unproven/FLAGGED controls -> collect ONE control's mechanical evidence (config snapshot / log query / scan output / access-review export) -> independent checker validates evidence against that control's acceptance criteria -> record MET (evidence attached) / NOT-MET / ATTESTATION-REQUIRED -> decide continue/stop
- **Stop:** SUCCESS: every control in `<CONTROL_SET>` is either MET with passing evidence stored, or explicitly ATTESTATION-REQUIRED with the human owner named — zero controls resting on assertion · BUDGET: control or turn cap `<BUDGET>` reached · NO-PROGRESS: `<K>` turns with no control moving from unproven to MET (and none newly parked as ATTESTATION-REQUIRED) · BLOCKED: a control's evidence source is unavailable (no log retention, no scan/export access, missing export) so it can be neither evidenced-MET nor cleanly parked — note that a control satisfiable only by human/process attestation is NOT blocked, it is recorded ATTESTATION-REQUIRED (a normal per-control terminal) and the loop continues
- **Model:** Mid-tier model suffices when evidence is machine-parseable (JSON scan output, query row counts, config diffs); escalate to a top reasoning tier for controls whose acceptance criteria are ambiguous or require judging whether the evidence genuinely covers the control's intent. The checker MUST be independent of the collector and of the agent's narration — an assertion that "encryption is on" is not evidence; the stored artifact plus the checker's pass verdict against the criteria is. Honest scope: mechanical evidence proves the controls that CAN be evidenced mechanically; the ATTESTATION-REQUIRED bucket is not a failure but the honest boundary where compliance depends on human/process attestation — a green mechanical sweep is a floor, and reporting it as "compliant" while attestations are open is the exact overstatement this loop exists to prevent.

```text
GOAL (frozen — do not redefine mid-loop)
For every control <CONTROL_ID> in <CONTROL_SET> — the frozen control set for <FRAMEWORK> (e.g. SOC 2 CC-series, ISO 27001 Annex A, NIST 800-53), each with a written <ACCEPTANCE_CRITERIA> — establish that it is ACTUALLY satisfied by attaching mechanical evidence that <CRITERIA_CHECKER> validates against that control's acceptance criteria. Acceptance criterion for the loop: no control is marked MET without a stored, passing evidence artifact; controls that only a human/process can satisfy are marked ATTESTATION-REQUIRED with a named owner, never silently passed. The control set and its acceptance criteria are LOCKED at loop start.

INDEPENDENT VERIFIER
The verifier is the pairing of <EVIDENCE_COLLECTOR> (produces the artifact — config snapshot, log query result, scan output, access-review export, IAM policy dump) and <CRITERIA_CHECKER> (validates that artifact against <ACCEPTANCE_CRITERIA> and emits pass/fail). It is independent because the artifact is ground truth pulled from the system, not the agent's summary of it, and the checker's verdict is separate from the collection step. It cannot rubber-stamp itself: "MET" requires an artifact on file AND the checker's pass verdict — an assertion with no artifact is auto NOT-MET. Honest note: passing every mechanically-checkable control is NECESSARY but NOT SUFFICIENT for compliance — controls resolved only by human sign-off, process observation, or third-party attestation cannot be closed here and are surfaced as ATTESTATION-REQUIRED, not counted toward "compliant."

PER-TURN SHAPE
1. ASSESS — pick exactly ONE control <CONTROL_ID> that is still unproven or FLAGGED; restate its <ACCEPTANCE_CRITERIA> verbatim.
2. ONE ACTION — run <EVIDENCE_COLLECTOR> to gather the single artifact that would prove this control (one query, one snapshot, one export); do not collect for other controls this turn.
3. VERIFY — run <CRITERIA_CHECKER> to validate that artifact against <ACCEPTANCE_CRITERIA>; the artifact, its timestamp/source, and the verdict are the evidence of record.
4. DECIDE — record MET only if a passing artifact is stored in <EVIDENCE_STORE>; record NOT-MET and leave the control open if evidence fails or is missing; record ATTESTATION-REQUIRED with a named human owner if no mechanical collector can satisfy it; escalate if the evidence source itself is unavailable.

CARRY-FORWARD STATE (compact)
Controls: MET (with evidence-artifact ref), NOT-MET / open, ATTESTATION-REQUIRED (with owner), unproven remaining. Evidence store index (control -> artifact id + timestamp + source). This-turn target and its criteria. Budget: turns / collection-runs remaining.

ACTION BAN
Never mark a control MET on assertion, inference, or "it should be configured that way" — no stored passing artifact means NOT-MET. Never reuse a stale artifact whose timestamp predates the control's evidence window, and never edit an artifact to make it pass. Never batch evidence collection across controls in one turn — one control, one artifact, one verdict, so provenance is clean. Never fold ATTESTATION-REQUIRED items into the MET count, and never report "compliant" or "controls satisfied" while any attestation is open — the truthful claim is "N controls evidenced-MET, M attestation-required and open." Never weaken or reinterpret a control's acceptance criteria to fit the evidence you happened to collect.

STOP — halt on the FIRST of:
SUCCESS (every control in <CONTROL_SET> is evidence-MET with a stored passing artifact or explicitly ATTESTATION-REQUIRED with a named owner, and the floor-not-ceiling caveat is recorded) | BUDGET (<BUDGET> turns / collection-runs reached) | NO-PROGRESS (<K> turns with no control moving to MET and none newly parked as ATTESTATION-REQUIRED) | BLOCKED (an evidence source is unavailable — no log retention, no scan/export access — so a control can be neither evidenced nor parked; a control satisfiable only by human/process attestation is NOT blocked, it is recorded ATTESTATION-REQUIRED and the loop continues)
```
