# Incident Response

`incident-response` — 3 loop prompts.

### 1. Alert Triage to Root Cause

- **When:** A monitoring/paging alert fires (error-rate spike, latency SLO breach, queue backup, failed health check) and the on-call needs to go from "alert fired" to a confirmed root cause before touching production — the alert itself is not yet trusted as accurately describing what's wrong.
- **Loop:** Reproduce/confirm the alert's symptom independently first (dashboard/query/log, not the alert text) as the frozen baseline -> each turn: state ONE root-cause hypothesis ranked by likelihood -> take ONE reversible diagnostic action (query logs/metrics/traces, inspect a config/deploy diff, check a dependency's status) -> re-check the SAME symptom signal used for baseline -> update confirmed/ruled-out list -> decide continue/stop. Any action that would change production state (restart, rollback, scale, flag flip, config push) requires an explicit human approval gate before executing, even if the loop is otherwise autonomous.
- **Stop:** SUCCESS: Root cause is identified and confirmed by reproducing the exact symptom signal used at baseline (same query/dashboard/metric, not the raw alert text), a fix or mitigation is proposed with the specific evidence chain, and — for any action that touches production — a human has explicitly approved it in the conversation before it executes. · BUDGET: 12 diagnostic iterations (investigation actions), separate from and not consumed by the human-approval wait for a prod change. · NO-PROGRESS: 3 consecutive hypotheses investigated with zero change to the confirmed/ruled-out list (i.e., nothing new eliminated or corroborated) — forces a strategy change: broaden the hypothesis space, escalate to a human with everything ruled out so far, or pull in an additional data source not yet checked. · BLOCKED: Root cause implicates a system/log/metric the agent cannot query (no access, missing credentials, third-party dependency with no visibility) — OR the fix requires a production change and no human is available to approve it — OR the symptom cannot be independently reproduced/confirmed at all (alert may be a false positive; escalate for manual triage rather than guessing at a cause for an unconfirmed symptom).
- **Model:** Diagnostic Q&A against logs/metrics/traces is fine for a mid-tier model once the alert has an initial hypothesis space — most turns are mechanical query-compare-narrow cycles. Use a stronger model (Claude Fable 5, xhigh) for the first-turn evidence read on an unfamiliar/complex system (distributed services, cascading failures, multi-tenant blast radius) where generating a *good* first hypothesis is the hard part, and again for the final root-cause explanation that will justify a production change to a human approver.

```text
GOAL (frozen): Alert `<alert_name/ID>` fired reporting `<alert description, e.g. "5xx rate > 2% on service X">`. Before treating this as real, independently reproduce/confirm the symptom via `<dashboard/query/log source>` — NOT by trusting the alert text. Using that confirmed symptom as your baseline signal, find the root cause and propose a fix/mitigation, verified by re-checking the SAME signal after any change — never by re-reading code or config and declaring it "should" be fixed. Any action that touches production (restart, rollback, scale, feature-flag flip, config/deploy push) requires explicit human approval in this conversation before you execute it — treat this as a hard gate, not a suggestion.

Turn 0: confirm the symptom independently and record the exact baseline signal (query, dashboard panel, log pattern, current value) you will re-check every turn. If you cannot reproduce/confirm it at all, that's a BLOCKED condition — do not proceed to root-cause on an unconfirmed symptom.

Each turn: state ONE root-cause hypothesis (recent deploy, config change, upstream dependency, resource exhaustion, traffic pattern, data issue), ranked by likelihood given what's confirmed so far. Take ONE reversible diagnostic action — query logs/metrics/traces, diff a config or deploy, check a dependency's status page/health endpoint, inspect a recent change — that would confirm or kill the hypothesis. Re-check the baseline signal. Update your confirmed/ruled-out list; never re-investigate a ruled-out hypothesis, and never take the identical diagnostic action twice hoping for a different read. If the next step is a production-touching action, STOP and present the evidence chain to the human for explicit approval before executing — do not proceed on inferred consent.

Carry forward each turn: baseline signal + current value, confirmed/ruled-out hypothesis list, iterations used, any production-change request awaiting approval.

STOP on first: SUCCESS — root cause confirmed against the baseline signal, fix/mitigation proposed with evidence chain, and any prod-touching action explicitly human-approved before executing; BUDGET — 12 diagnostic iterations exhausted; NO-PROGRESS — 3 consecutive hypotheses with no change to the confirmed/ruled-out list — broaden the hypothesis space or escalate with findings so far; BLOCKED — needed system/log/metric isn't accessible, OR a prod change is required and no human is available to approve it, OR the symptom can't be independently reproduced at all (possible false alarm) — escalate for manual triage rather than guessing.
```

### 2. Incident Response — Correlate Signals to Isolate a Fault (agent-loop prompt)

- **When:** A production incident is active (alert fired, SLO breach, user-facing error spike) and the faulty component/change is not yet known — multiple independent telemetry signals (metrics, logs, traces, deploy/config history) exist and need to be correlated to isolate the fault before remediation.
- **Loop:** Freeze the incident window and blast radius as starting state -> each turn: state ONE fault hypothesis -> pick ONE signal source NOT yet used to test it (independent of the narrative) -> query that signal for the incident window -> compare against its own pre-incident baseline -> mark hypothesis confirmed/killed/open in a running table -> decide continue/stop
- **Stop:** SUCCESS: SUCCESS — a single fault is isolated where at least TWO independent signal sources (e.g. a metrics-based correlation AND a trace/log-based correlation, never two views of the same underlying signal) corroborate it, AND a scoped mitigating action (rollback/config revert/feature-flag) applied under human approval brings the primary SLO/error metric back within threshold, confirmed by the SAME monitoring query re-run after mitigation — not by the responder's narrative of what happened. · BUDGET: 14 hypothesis-turns from incident-open, or the org's incident-response time-box (e.g. <INCIDENT_TIMEBOX_MINUTES>), whichever is reached first. · NO-PROGRESS: 4 consecutive turns produce no hypothesis newly confirmed or killed (i.e., every check comes back inconclusive/ambiguous against baseline) — signals a wrong hypothesis class, not a wrong signal choice; force a full reset of the hypothesis space (e.g. from "code change" to "infra/dependency" or vice versa) rather than trying a 5th variant within the same class. · BLOCKED: A needed signal source (dashboard, log index, trace backend, deploy history) is inaccessible or has no data for the incident window; or two hypotheses each get corroborated by one independent signal apiece with no tiebreaker signal available — escalate to a human with the confirmed/killed/open table rather than guessing.
- **Model:** Fable 5 at xhigh for the opening evidence read and initial hypothesis generation across noisy, unfamiliar telemetry (this is the highest-leverage, hardest-to-get-right step — a bad first hypothesis set burns the whole budget). Once narrowed to 2-3 candidate fault classes, mechanical per-turn signal-query-and-compare work is fine on a cheaper model (Sonnet/Haiku-class). Any mitigating action requires explicit human approval regardless of model — this is an irreversible/paid-adjacent action gate, not a model-capability question.

```text
GOAL (frozen): Incident `<INCIDENT_ID>` — `<observed symptom, e.g. "P99 latency on checkout-service up 8x, error rate 4%">` began at `<T_START>`. Isolate the single fault responsible and confirm a scoped mitigation restores `<PRIMARY_METRIC>` to within `<THRESHOLD>` of its pre-incident baseline. Success requires TWO INDEPENDENT signal sources to corroborate the same fault — a metrics dashboard and a trace/log query, or a deploy-history record and an independent metrics correlation — never two readings of the same underlying signal, and never the responder's own narrative as one of the two. Available signal sources: `<SOURCE_1: e.g. metrics/APM dashboard>`, `<SOURCE_2: e.g. centralized logs>`, `<SOURCE_3: e.g. distributed tracing>`, `<SOURCE_4: e.g. deploy/config-change history>`, `<SOURCE_5: e.g. dependency/vendor status page>`.

Freeze first: incident window (`<T_START>` to now), affected service(s)/blast radius, and the primary metric's pre-incident baseline value. Do not re-litigate these each turn — treat them as fixed reference points.

Each turn:
1. Assess: review the confirmed/killed/open hypothesis table so far and the remaining budget.
2. State ONE fault hypothesis (e.g. "the 14:02 deploy of `<service>` introduced the regression", "an upstream dependency `<X>` is degraded", "a config/flag flip changed behavior", "a traffic/load pattern shift exceeded capacity").
3. Pick ONE signal source that has NOT yet been used to test THIS hypothesis, and that is independent of whatever produced the hypothesis in the first place (a hypothesis formed from a dashboard spike must be tested against logs/traces/deploy-history, not the same dashboard reread differently).
4. Query that signal for the incident window only, compare against its own documented pre-incident baseline (not against your expectation of what it should show).
5. Record the result in the table as CONFIRMED (signal shows a clear, timed anomaly coincident with T_START that this hypothesis predicts), KILLED (signal is clean / doesn't coincide), or OPEN (ambiguous — needs a different signal, not a re-query of the same one).
6. Never re-test an already-KILLED hypothesis, and never query the same signal source twice for the same hypothesis expecting a different read (that's the verbatim-retry anti-pattern). If two hypotheses keep flipping which looks more likely turn to turn without new evidence, that is oscillation — pull in a third, unused signal source to break the tie rather than continuing to alternate.

Mitigation gate: once a fault has 2 independent corroborating signals, propose the specific scoped mitigating action (rollback commit `<X>`, revert config `<Y>`, disable flag `<Z>`) and STOP for explicit human approval before applying it — this is an irreversible/customer-facing action and is never auto-applied by the loop. After approval and application, re-run the SAME primary-metric query used to establish baseline to confirm recovery; do not declare success on the mitigator's own confidence that "it should be fixed now."

STOP on first:
- SUCCESS — fault isolated with 2 independent corroborating signals, human-approved mitigation applied, primary metric back within `<THRESHOLD>` of baseline on the same query re-run post-mitigation.
- BUDGET — 14 hypothesis-turns reached, or `<INCIDENT_TIMEBOX_MINUTES>` wall-clock reached, whichever first — escalate with the full confirmed/killed/open table.
- NO-PROGRESS — 4 consecutive turns with no hypothesis newly confirmed or killed — reset to a different hypothesis class rather than varying within the current one.
- BLOCKED — a needed signal source is inaccessible/has no data for the window, or two hypotheses are each singly-corroborated with no independent tiebreaker signal available — escalate to a human with everything gathered so far.
```

### 3. Incident Response — Post-incident fix with regression guard (agent-loop prompt)

- **When:** Use after an incident has been triaged and root-caused, when you need an agent to land a durable fix plus a regression guard (test/alarm) that independently proves the incident can't recur — not for live firefighting during an active outage.
- **Loop:** assess (read incident record + current repro state) -> one reversible action (write/adjust ONE of: fix code, regression test, alarm/monitor config) -> verify (run the independent verifier fresh, out-of-process) -> decide (SUCCESS / BUDGET / NO-PROGRESS / BLOCKED)
- **Stop:** SUCCESS: The independent regression verifier — a test or alarm authored to reproduce <INCIDENT_ID> — fails against the pre-fix code/config and passes against the post-fix state, confirmed by a fresh run (not cached), plus the full existing test suite still passes (no new regressions introduced by the fix). · BUDGET: Max <MAX_ITERATIONS> turns (suggest 6-8 for a single-incident fix). Each turn = one action + one verification cycle. · NO-PROGRESS: Halt if the verifier's pass/fail signal and the diff's target lines are identical for <K> consecutive turns (suggest K=2), or if the same file/line is edited 3 times without the verifier state changing. · BLOCKED: Halt and request human input if: the regression verifier cannot be written without production data/credentials the agent doesn't have; the fix requires a schema/API change needing owner sign-off; the incident isn't reproducible locally/in staging at all; or an irreversible/paid action (prod deploy, alarm threshold that pages on-call, data backfill) is the next required step.
- **Model:** claude-sonnet-5

```text
GOAL (frozen — do not renegotiate mid-loop):
Fix the root cause of <INCIDENT_ID> in <REPO/SERVICE> and land an INDEPENDENT regression guard — a new test or alarm at <TEST_PATH_OR_ALARM_CONFIG> — that:
  (a) reproduces the incident's failure mode (fails against the pre-fix code/config), and
  (b) passes once the fix is applied,
verified by running <VERIFIER_COMMAND> (e.g. `pytest <path> -k <test_name>` or the alarm's synthetic-trigger/dry-run command) in a clean process — never by the agent's own read of the diff or a confidence statement.
The existing suite (<FULL_SUITE_COMMAND>) must still pass after the fix. Do not modify the verifier to make it pass once it exists — only the fix.

CONTEXT TO LOAD ONCE, BEFORE THE LOOP:
- Incident record / postmortem: <INCIDENT_DOC_LINK>, root cause hypothesis: <ROOT_CAUSE_SUMMARY>
- Repro steps as currently known: <REPRO_STEPS_OR_NONE>
- Owner of the affected service/alarm, for the BLOCKED gate: <OWNER_CONTACT>
- Any prior failed fix attempts and why they didn't stick: <PRIOR_ATTEMPTS_OR_NONE>

PER-TURN SHAPE:
1. ASSESS — re-read current diff state + last verifier output (not memory of it). State in one line: what's true now, what's still unproven.
2. ONE ACTION — make exactly one reversible change:
   - Turn 1 is special: write the regression test/alarm FIRST, confirm it fails against the unfixed code (red). If it doesn't fail red, the verifier is wrong — fix the verifier, not the code, before touching the fix.
   - Subsequent turns: one edit toward the fix (one function, one config value, one guard clause — not a refactor sweep).
3. VERIFY — run <VERIFIER_COMMAND> fresh (no cache, no re-use of a prior run's output). On a turn where you believe the fix is complete, also run <FULL_SUITE_COMMAND>.
4. DECIDE — apply the Stop line below. If continuing, carry forward the compact state and end the turn.

CARRY-FORWARD STATE (rewrite compactly each turn, do not restate full history):
- turn: <n>/<MAX_ITERATIONS>
- verifier_status: red | green | not-yet-written
- last_action: <one-line description of the single change made>
- verifier_output_delta: <what changed vs previous run — pass count, error message, alarm trigger state>
- suite_status: <pass/fail/not-yet-run>
- attempted_and_reverted: <list of actions already tried and undone — never repeat these verbatim>

BANNED:
- Retrying the identical edit verbatim after it already failed verification once.
- Oscillating A -> B -> A on the same file/lines across turns.
- Declaring SUCCESS from reading the diff, from the agent's own reasoning about correctness, or from a verifier run that isn't fresh.
- Editing the regression test/alarm to match the fix's behavior after the fix is in place (that erases its independence).
- Any deploy, alarm-threshold change that pages on-call, or data backfill without an explicit human go-ahead — surface as BLOCKED instead.

STOP (halt on the first that fires):
- SUCCESS — verifier_status: green AND suite_status: pass, confirmed by a fresh run this turn.
- BUDGET — turn count reaches <MAX_ITERATIONS> without SUCCESS.
- NO-PROGRESS — verifier_output_delta unchanged for <K> consecutive turns, or same file/line edited 3x with no state change.
- BLOCKED — verifier can't be authored without unavailable prod data/credentials, fix needs an API/schema change requiring <OWNER_CONTACT> sign-off, incident isn't reproducible in <ENV>, or next required step is an irreversible/paid action (prod deploy, paging alarm change, backfill) — stop and hand to a human with the current carry-forward state attached.
```
