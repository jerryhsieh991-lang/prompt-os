# Tool Use

`tool-use` — 5 loop prompts.

### 1. Tool-Error Recovery Loop

- **When:** Use when an agent must complete a task by calling tools from a fixed, named tool set and needs disciplined, capped recovery from tool errors (transient failures, bad args, wrong tool, missing resource, auth failures, unclassifiable errors) instead of ad-hoc or unbounded retries.
- **Loop:** BOOTSTRAP (turn 1 only) -> ASSESS -> ONE ACTION -> VERIFY -> DECIDE
- **Stop:** SUCCESS: The independent state-check confirms <SUCCESS_CONDITION> on the final step, and every prior sub-step's <STEP_VERIFICATION_MAP> entry was already confirmed. · BUDGET: <MAX_ITERATIONS> total turns used for the run — and ONLY that. Per-category cap exhaustion (<MAX_ATTEMPTS_PER_CATEGORY>) never trips BUDGET directly: per DECIDE, exhausting a category's cap always escalates to the next category-appropriate action, terminating at · NO-PROGRESS: Same error category repeats on the same step with no new fix left to try; or 3 straight turns with plan_step unchanged and no new tool/arg combination tried; or A→B→A tool oscillation. · BLOCKED: AUTH/PERMISSION on any call; WRONG_TOOL or RESOURCE_MISSING with no untried fallback/create path; UNKNOWN surviving its one diagnostic retry; INVALID_ARGS cascaded into WRONG_TOOL with no fallback left; or an irreversible/paid/destructive action pending with no available human-approval gate. · BLOCKED: (never BUDGET) if no action remains.
- **Model:** Run every ordinary turn (ASSESS / ONE ACTION / VERIFY / DECIDE) on the run's standard model. Escalate to a stronger model for exactly one moment per step: the instant INVALID_ARGS's single replan attempt or UNKNOWN's single diagnostic attempt fails to verify — since each has cap 1, "first attempt" and "cap-exhausting attempt" are the same event, so this trigger is guaranteed to fire on that first failure, not a rare recurrence. Use the stronger model for whichever action DECIDE's cascade selects next (reasoning through the WRONG_TOOL fallback choice after INVALID_ARGS exhaustion, or composing the BLOCKED report after UNKNOWN exhaustion) — never for a second attempt inside the same category, which the cap forbids outright. Do not escalate for TRANSIENT (mechanical backoff-retry needs no extra reasoning) or for a category's initial attempt.

```text
GOAL (frozen — do not redefine mid-loop)
Complete <TASK_DESCRIPTION> by calling tools from <TOOL_SET> (the fixed, named set of tools available this run, each with its documented required-args schema), reaching a state where an INDEPENDENT check confirms <SUCCESS_CONDITION> — a specific, mechanically-verifiable fact about actual resulting state (e.g., "GET /orders/{id} returns status=confirmed", "the file exists at <PATH> with the expected content hash", "a follow-up list call shows the new record") — read via a call DIFFERENT from whichever write/action call attempted to produce it. A tool call returning HTTP 200 / no exception / "ok":true is NEVER sufficient for SUCCESS on its own; it only justifies attempting the independent check.

Freeze before turn 1: <TOOL_SET> (primary tools, each with its required-args schema); <FALLBACK_TOOLS> (an explicit ordered list of alternate tools/methods that can achieve the same sub-goal if the primary tool keeps failing — e.g., a REST call as fallback for a failed SDK method, or a different search provider as fallback for a failed one; if no fallback exists for a step, say so explicitly now, not mid-run); <SUCCESS_CONDITION> plus the exact independent read call that checks it; <STEP_VERIFICATION_MAP> (for every non-final sub-step of <TASK_DESCRIPTION>, the exact independent read call — distinct from the write/action call, same independence rule as <SUCCESS_CONDITION> — that confirms that sub-step actually landed; if no independent read exists for a given sub-step, say so now and name the explicit fallback check you'll use instead, e.g. "confirmed only indirectly, via the next sub-step's precondition succeeding" — never left to in-the-moment judgment); <MAX_ITERATIONS>; <MAX_ATTEMPTS_PER_CATEGORY> (default 2 for TRANSIENT, 1 for INVALID_ARGS-replan, 1 for UNKNOWN-diagnostic — a fixed small cap per category, not a shared pool); and whether any step in <TASK_DESCRIPTION> is irreversible/paid/destructive, in which case name the required human-approval gate now.

ERROR CLASSIFIER (the independent verifier for this loop — applied to every non-success tool result, mechanically, from the tool's own structured error code/type/message, never from the acting step's self-assessment of "why it probably failed"):
- TRANSIENT — timeout, rate-limit (429), connection reset, 5xx, "temporarily unavailable." Legal action: retry the SAME tool with the SAME args after a backoff, up to <MAX_ATTEMPTS_PER_CATEGORY> times for this step. This is the loop's ONE named, bounded exception to the verbatim-retry ban in ACTION BAN below — deliberate, not incidental: transport-level failures are the one class where the original args were never the problem, so replaying them after backoff is the correct recovery. No other category may ever repeat identical args.
- INVALID_ARGS — schema validation failure, 400 Bad Request, "missing required field," "malformed input," a parseable message pointing at a specific parameter. Legal action: replan-args — construct a corrected argument set that concretely addresses the message (not a guess-and-check retry), call the SAME tool once. Verbatim retry of the same args is banned outright in this category.
- WRONG_TOOL — 404/"not supported"/"method not allowed," or the tool's response indicates this operation isn't what that tool does. Legal action: fallback-tool — take the next untried entry in <FALLBACK_TOOLS> for this step. If <FALLBACK_TOOLS> has no untried entry left, this becomes BLOCKED.
- AUTH / PERMISSION — 401/403, "invalid token," "access denied," expired credentials. No legal in-loop action exists. Always BLOCKED — surface immediately, do not spend a retry.
- RESOURCE_MISSING — 404 on a read/reference to something that should exist (distinct from WRONG_TOOL: the tool is right, the target isn't there). Legal action: ONE replan attempt to locate/create the resource via a tool already in <TOOL_SET>/<FALLBACK_TOOLS> if the task allows it (e.g., create-if-missing is in scope); otherwise BLOCKED.
- UNKNOWN — error doesn't cleanly match the above. Legal action: ONE diagnostic retry with verbose/debug mode or a narrower probe call (not the original action) to try to reclassify it. If it's still UNKNOWN after that one diagnostic attempt, STOP: BLOCKED — do not keep guessing.

MODEL
Run every ordinary turn (ASSESS / ONE ACTION / VERIFY / DECIDE) on the run's standard model. Escalate to a stronger model for exactly one moment per step: the instant INVALID_ARGS's single replan attempt or UNKNOWN's single diagnostic attempt fails to verify — since each has cap 1, "first attempt" and "cap-exhausting attempt" are the same event, so this trigger is guaranteed to fire on that first failure, not a rare recurrence. Use the stronger model for whichever action DECIDE's cascade selects next (reasoning through the WRONG_TOOL fallback choice after INVALID_ARGS exhaustion, or composing the BLOCKED report after UNKNOWN exhaustion) — never for a second attempt inside the same category, which the cap forbids outright. Do not escalate for TRANSIENT (mechanical backoff-retry needs no extra reasoning) or for a category's initial attempt.

PER-TURN SHAPE
0. BOOTSTRAP (turn 1 only) — There is no prior tool result yet, so skip ASSESS's read-verbatim check this one time. Set plan_step to the first sub-step of <TASK_DESCRIPTION>, select the first entry in <TOOL_SET> for it, and go straight to ONE ACTION (make that call); then VERIFY and DECIDE run as normal. From turn 2 onward this step does not run — start at ASSESS.
1. ASSESS — Read the last tool call's raw result verbatim (full error code/type/message, not a paraphrase). If it was a success-looking return, do NOT treat that as done — proceed to Verify this same turn. If it was an error, run it through the ERROR CLASSIFIER above to get exactly one category.
2. ONE ACTION — Take exactly the single action the category licenses (retry-with-backoff / replan-args / fallback-tool / diagnostic-retry), never more than one tool call this turn, and never an action outside what the category legalized. If the category is AUTH/PERMISSION, or WRONG_TOOL with <FALLBACK_TOOLS> exhausted, or RESOURCE_MISSING with no create path, or UNKNOWN past its one diagnostic attempt — take no action; go straight to STOP: BLOCKED. If the next legal action is the task's irreversible/paid/destructive step, it may proceed ONLY once the human-approval gate named at freeze time is cleared for THIS specific call.
3. VERIFY — Make the independent state-check call named in <SUCCESS_CONDITION> for the final step, or the exact call named for the current sub-step in <STEP_VERIFICATION_MAP> for a non-final step — frozen before turn 1, never improvised in the moment — a call distinct from the one just attempted. Compare against the target fact. A tool's own "success" field is never treated as verification.
4. DECIDE — Update attempt_log and the per-category counter for this step. If verify confirms the target fact: for a non-final step, advance plan_step and reset category_counts_this_step to 0; for the final step, STOP: SUCCESS. If the category's cap for this step is now exhausted without success → escalate to the next category-appropriate action (TRANSIENT cap exhausted → treat as UNKNOWN, one diagnostic attempt, not endless backoff; INVALID_ARGS cap exhausted → WRONG_TOOL logic, try fallback; WRONG_TOOL/RESOURCE_MISSING/UNKNOWN exhausted → BLOCKED). Cap exhaustion never halts the loop by itself — it always cascades onward or resolves as BLOCKED; it never triggers BUDGET (see STOP). If turn_count reaches <MAX_ITERATIONS> → STOP: BUDGET. If a NO-PROGRESS condition is met → stop there. Otherwise continue to the next turn.

CARRY-FORWARD STATE (compact — do not let this balloon)
- plan_step: <which sub-step of <TASK_DESCRIPTION> is active>
- attempt_log: last 3 attempts only, as (turn#, tool, args-hash, error-category, outcome) triples
- category_counts_this_step: {TRANSIENT: n/<cap>, INVALID_ARGS: n/<cap>, UNKNOWN: n/<cap>} — resets to 0 when plan_step advances
- tools_tried_this_step: <set of tool names already attempted for the current sub-goal, so fallback selection never repeats one>
- turn_count: <int> / budget <MAX_ITERATIONS>
- human_gate_status: <cleared|not-cleared, for the NEXT pending irreversible action only — resets to not-cleared the instant that action resolves>
- last_verified_state: <the actual fact last confirmed by an independent read, for comparing against <SUCCESS_CONDITION> or the active <STEP_VERIFICATION_MAP> entry>

ACTION BAN
- The ONLY sanctioned repeat of a byte-identical tool call is a TRANSIENT retry (same tool, same args, after backoff, capped at <MAX_ATTEMPTS_PER_CATEGORY>) — a deliberate, bounded, explicitly-named exception, not a loophole. Every other category is banned outright from repeating identical args, with no exceptions.
- Never treat "the call returned without throwing" as SUCCESS — always run the independent check named in <SUCCESS_CONDITION> (final step) or <STEP_VERIFICATION_MAP> (non-final step) before declaring a step done.
- Never invent a fallback tool that isn't in <FALLBACK_TOOLS> — if none is listed for a failing step, that step's WRONG_TOOL/RESOURCE_MISSING failures go straight to BLOCKED, not to an improvised workaround.
- Never oscillate between two tools/arg-sets on the same step (A→B→A) — that's a NO-PROGRESS trigger, not a valid exploration strategy.
- Never take the irreversible/paid/destructive action without a fresh human-approval-gate clearance for that specific call, even if an earlier call in the same run was approved.
- Never silently downgrade AUTH/PERMISSION into a "retry later" — it is always an immediate BLOCKED, since no amount of retrying fixes bad credentials.

STOP — halt on the FIRST of:
SUCCESS (the independent state-check confirms <SUCCESS_CONDITION> on the final step, and every prior sub-step's <STEP_VERIFICATION_MAP> entry was already confirmed) | BUDGET (<MAX_ITERATIONS> total turns used for the run — and ONLY that; per-category cap exhaustion never trips BUDGET directly, it always cascades to the next category-appropriate action per DECIDE and, if nothing is left, resolves as BLOCKED) | NO-PROGRESS (same category repeats on the same step with no new fix left to try; or 3 straight turns with plan_step unchanged and no new tool/arg combination tried; or A→B→A tool oscillation) | BLOCKED (AUTH/PERMISSION; WRONG_TOOL or RESOURCE_MISSING with no untried fallback/create path; UNKNOWN surviving its one diagnostic retry; INVALID_ARGS cascaded into WRONG_TOOL with no fallback left; or an irreversible/paid/destructive action pending with no available human-approval gate). Report the exact category, tool/args last tried, and attempt_log at the point of halt.
```

### 2. Tool-Choice Routing with Outcome Check

- **When:** You have a task that requires invoking ONE of several available tools/APIs (from a fixed registry — search, file ops, calendar, email, DB query, calculator, etc.) to change or retrieve some real state, and 'the right tool ran without erroring' is not proof the task is actually done — you need to confirm the underlying goal state was achieved by a check independent of the tool's own return value.
- **Loop:** assess unmet requirement vs tool registry capabilities -> select the ONE tool + params whose declared capability best matches the unmet requirement -> execute that single tool call -> run an independent outcome check against the real target state (not the tool's own success flag/response) -> commit (mark requirement satisfied) if the check confirms it, else roll back any reversible side effect and log the tool as ruled out for this requirement -> decide continue/stop
- **Stop:** SUCCESS: the independent outcome check confirms the target state/requirement from <SUCCESS_CRITERION> is actually satisfied — not that a tool call returned success:true or 200 OK · BUDGET: <MAX_ITERATIONS> tool-call turns reached without all requirements satisfied · NO-PROGRESS: the outcome check result (pass/fail per requirement) is unchanged for 3 straight turns despite trying tools/params that differ from what was already tried — stop grinding, don't keep swapping tools blindly · BLOCKED: no tool in <TOOL_REGISTRY> has the capability the requirement needs (capability gap, not a bad call), OR the next-best action is irreversible or paid/costly (send, delete, purchase, publish, live trade) and lacks explicit human approval already given in this session
- **Model:** Capability-matching against a small, well-documented tool registry (pick file-write vs calendar-create vs web-search) is mechanical pattern matching a cheaper model handles fine. Escalate to a stronger model when: (a) the registry has overlapping/ambiguous tools (multiple search backends, multiple 'send message' channels) and picking the right one requires understanding subtle scope/side-effect differences; or (b) the outcome check itself is fuzzy (e.g. 'did the email read as intended' rather than 'does the file exist') and needs real judgment to grade, not just a status-code check.

```text
Goal (frozen): fulfill <TASK_REQUEST> using tools drawn only from <TOOL_REGISTRY> — success means <SUCCESS_CRITERION> is independently confirmed true, not that some tool call returned success:true, 200, or a plausible-looking response. The tool's own return value is a signal to log, never the verifier.

Independent verifier (define before looping): <OUTCOME_CHECK> — a check that queries the actual target state through a path DIFFERENT from the tool just invoked (e.g. re-fetch the file/record via a separate read call, re-query the calendar/DB, re-run the search and inspect real results, diff the file on disk) rather than trusting the acting tool's response. If no such independent check exists yet for this task, define it now, before the first turn, and freeze it.

Each turn:
1. Assess: which part of <TASK_REQUEST> is still unmet, and which tool(s) in <TOOL_REGISTRY> declare a capability matching it. Route by capability, not by habit or whichever tool was tried last.
2. Act: make exactly ONE tool call — one tool, one set of params — chosen as the best capability match. Do not chain multiple tool calls in a single turn; each call gets its own verification.
3. Verify: run <OUTCOME_CHECK> against real state, independent of what the tool itself reported. A tool saying "done" is not evidence; the outcome check is.
4. Decide: if the check confirms the requirement is now met, commit it (mark satisfied, move to the next unmet requirement). If the check still fails: if the tool call had a reversible side effect, roll it back; log this (tool, params, failure reason: wrong-capability-match / right-tool-wrong-params / tool-succeeded-but-didn't-achieve-goal) as ruled out, and next turn pick a materially different tool or materially different params — never repeat the identical call, and never oscillate between the same two tools without changing the approach.

Before ANY irreversible or paid/costly action (send, delete, publish, purchase, live trade, external notification) — even if a tool in the registry supports it — stop and get explicit human approval in this conversation before executing it. Treat unapproved irreversible actions as BLOCKED, not as a turn to take.

Carry forward each turn, compactly: which requirements are satisfied vs still open, the tool+params tried per open requirement and why each failed, the last outcome-check result, and iterations remaining out of <MAX_ITERATIONS>.

Stop and report on the FIRST of:
- SUCCESS — outcome check independently confirms <SUCCESS_CRITERION> for every part of <TASK_REQUEST>.
- BUDGET — <MAX_ITERATIONS> turns reached without full success.
- NO-PROGRESS — outcome-check pass/fail state unchanged for 3 straight turns despite genuinely different tools/params being tried (not verbatim retries) — halt and report what was tried rather than continuing to guess.
- BLOCKED — no registry tool has the needed capability (name the gap), or the only remaining path requires an irreversible/paid action without human approval already granted — surface it and wait.
```

### 3. Idempotent Side-Effecting Action with Confirmation Gate

- **When:** Use when a single turn must execute ONE irreversible-or-paid call (charge a card, create an order, provision a resource, send a payment, fire a one-time webhook) through a tool/API that supports an idempotency key, and an ambiguous response (timeout, dropped connection, 5xx with no body) must never be resolved by blindly retrying — because a blind retry on a side-effecting call risks a duplicate charge/resource/send if the original request actually landed server-side despite the client never seeing the reply.
- **Loop:** ASSESS (has the gate cleared? has a key been minted?) -> HUMAN APPROVAL GATE (once, before the first attempt) -> ONE ACTION (the single idempotent call, same key every attempt) -> VERIFY (independent read by key/resource-id, never the call's own response) -> DECIDE (commit / re-verify-only on ambiguous response / BLOCKED)
- **Stop:** SUCCESS: the independent read-by-idempotency-key (or read-by-resulting-resource-id) confirms the effect exists exactly once in the target system — never inferred from the write call's own 200/ok. · BUDGET: <MAX_ITERATIONS> turns used, where an ambiguous-response re-verify-only turn still counts against budget even though it makes no new call. · NO-PROGRESS: the independent read returns "not found yet" on 3 straight turns with no new information (no error code change, no propagation-delay justification left) — stop polling forever. · BLOCKED: the approval gate is not cleared for this specific key+payload; the tool has no idempotency-key support at all (so a retry can't be made safe — surface this and stop before the first attempt, don't attempt); or the independent read itself is unavailable/erroring, leaving no way to distinguish "didn't happen" from "happened but unconfirmable" — never resolve that ambiguity by guessing.
- **Model:** Route the gate check, the call, and the independent-read verify on the run's standard model — this is mechanical (mint key once, one call, one read, compare). Escalate to a stronger model for exactly one decision point: classifying an ambiguous response (timeout/5xx/dropped connection) as "safe to re-verify" vs "must treat as BLOCKED because even the independent read is inconclusive" — that judgment call, made once per ambiguous event, is where a wrong guess causes a duplicate side effect, so it's worth the stronger model; the mechanical retry-vs-stop mechanics around it stay on the standard model.

```text
GOAL (frozen — do not redefine mid-loop)
Execute <SIDE_EFFECTING_ACTION> (a single irreversible-or-paid call: <e.g. charge $X to card, create order #, provision <RESOURCE>, send payment to <RECIPIENT>>) through <TOOL/API> exactly once, such that an INDEPENDENT read — <INDEPENDENT_VERIFY_CALL>, a query by <IDEMPOTENCY_KEY> or by the resulting resource's own id, made through a path DIFFERENT from the call that attempted the action — confirms the effect exists in the target system exactly once. The write call's own return value (200 OK, "success":true, a resource payload in the response body) is NEVER sufficient for SUCCESS by itself — it only tells you the request was accepted, not that it was safely and singularly applied, and on an ambiguous response (timeout, connection reset, 5xx with no body) it tells you nothing at all.

Freeze before turn 1:
- <SIDE_EFFECTING_ACTION> and <TOOL/API> — the exact call, its required params, and confirmation the API supports client-supplied idempotency keys (if it does not, this task cannot be made safe for retry — say so now and route to BLOCKED before the first attempt, not after a failure).
- <IDEMPOTENCY_KEY> — minted ONCE, before turn 1 (e.g. a UUID scoped to this task instance), and reused byte-identical on every attempt of THIS action for the life of the loop. This is the loop's one deliberate, named exception to the verbatim-retry ban below: repeating the identical key+payload is what makes a retry safe, and swapping the key mid-loop is banned outright because it defeats the entire mechanism.
- <INDEPENDENT_VERIFY_CALL> — the exact read (by idempotency key, or by the resource id the action is expected to produce) that confirms the effect landed, distinct from the write call itself.
- <HUMAN_APPROVAL_GATE> — who/what must explicitly approve THIS specific key+payload before the first attempt (not a standing approval from an earlier run or an earlier different payload).
- <MAX_ITERATIONS>.
- <PROPAGATION_WINDOW> — how long an independent read may legitimately lag the write (e.g. "up to 10s eventual consistency") before "not found yet" stops being a normal wait and starts being a real signal.

INDEPENDENT VERIFIER (defined before the loop, applied every turn, never the acting call's own response):
<INDEPENDENT_VERIFY_CALL> — re-query the target system for a record matching <IDEMPOTENCY_KEY> or the expected resource id, through a call that did not just attempt the write. Three possible outcomes, each handled differently:
- FOUND, exactly one record, matching expected payload → SUCCESS.
- FOUND, but more than one record for supposedly the same key, or a record that doesn't match expected payload → do NOT treat as success; this is a duplicate/mismatch signal — STOP: BLOCKED, surface for human reconciliation, never auto-remediate a live duplicate.
- NOT FOUND → if within <PROPAGATION_WINDOW> and this is the first check after the call, this may be normal lag — one re-verify-only turn (no new write) is allowed. If NOT FOUND persists past <PROPAGATION_WINDOW> or across 3 straight verify-only turns → treat as NO-PROGRESS.

PER-TURN SHAPE
1. ASSESS — Has <HUMAN_APPROVAL_GATE> been explicitly cleared for this exact <IDEMPOTENCY_KEY>+payload? If not, and no attempt has been made yet, go straight to the gate — do not call the tool first and ask permission after the fact. If the gate was already cleared and one attempt already made, check whether the last turn's result was a clean success/failure or an ambiguous response (timeout/reset/5xx-no-body).
2. HUMAN APPROVAL GATE (once, before the first attempt only) — Present the exact action, payload, and <IDEMPOTENCY_KEY> to the human/approval mechanism named at freeze time. Do not proceed to ONE ACTION without an explicit, specific-to-this-payload clearance. A prior clearance for a different payload or a different run never carries over.
3. ONE ACTION — Make the single call to <TOOL/API> with <SIDE_EFFECTING_ACTION>'s payload and <IDEMPOTENCY_KEY> attached. If the previous turn's result was ambiguous (timeout/reset/5xx-no-body), this turn is NOT a fresh action turn — skip straight to VERIFY-only using <INDEPENDENT_VERIFY_CALL>; do not re-call the write endpoint again until the independent read has first ruled out "it already landed."
4. VERIFY — Run <INDEPENDENT_VERIFY_CALL>. Classify the result per the three outcomes above (FOUND-matching / FOUND-duplicate-or-mismatch / NOT FOUND). Never accept the write call's own response as verification, clean-looking or not.
5. DECIDE — FOUND-matching → STOP: SUCCESS. FOUND-duplicate-or-mismatch → STOP: BLOCKED, do not attempt cleanup unattended. NOT FOUND within <PROPAGATION_WINDOW> on the first check → next turn is a VERIFY-only re-check (no new write, no new key). NOT FOUND past the window, or the original write call itself errored with a non-ambiguous, clearly-failed status (e.g. 400 invalid payload, 403 denied) → this is a genuine failure, not ambiguity: if the error is fixable (bad payload field), fix the payload, keep the SAME <IDEMPOTENCY_KEY>, and return to the HUMAN APPROVAL GATE step again before the corrected attempt (a changed payload under the same key needs fresh eyes, since idempotency keys are meant to guard one exact payload). If unfixable or the gate is unavailable to re-clear → STOP: BLOCKED. If turn_count reaches <MAX_ITERATIONS> → STOP: BUDGET. If NOT FOUND repeats 3 straight verify-only turns past the window with nothing new to try → STOP: NO-PROGRESS.

CARRY-FORWARD STATE (compact)
- idempotency_key: <the single frozen key, never regenerated>
- gate_status: <not-cleared | cleared-for-current-payload> — resets to not-cleared if the payload changes
- last_call_outcome: <clean-success | clean-failure(code) | ambiguous(timeout/reset/5xx-no-body)>
- verify_result_log: last 3 VERIFY outcomes only, as (turn#, FOUND-matching/FOUND-duplicate/NOT-FOUND, seconds-since-write)
- attempts_made: <count of actual write calls fired — distinct from verify-only turns, which don't increment this>
- turn_count: <int> / budget <MAX_ITERATIONS>

ACTION BAN
- Never re-fire the write call while the last result is ambiguous (timeout/reset/5xx-no-body) — always VERIFY-only first. Firing again before checking is exactly the duplicate-side-effect risk this loop exists to prevent.
- Never mint a second idempotency key for the same logical action because the first attempt seemed to fail — a new key defeats the server's dedup and can cause the exact duplicate this pattern guards against. One key per logical action, for the life of the loop.
- Never treat the write call's own 200/ok/success-looking body as SUCCESS — only <INDEPENDENT_VERIFY_CALL> can confirm it.
- Never proceed past the HUMAN APPROVAL GATE on a prior or generic approval — every distinct payload change requires fresh, specific clearance.
- Never auto-remediate a FOUND-duplicate-or-mismatch result (e.g. by issuing a refund/delete/second corrective call) — that is itself a new side-effecting action requiring its own gate; STOP: BLOCKED and surface it instead.
- Never poll NOT FOUND past <PROPAGATION_WINDOW> indefinitely — 3 straight unchanged verify-only turns past the window is NO-PROGRESS, not "give it a bit longer."

STOP — halt on the FIRST of:
SUCCESS (<INDEPENDENT_VERIFY_CALL> finds exactly one matching record for <IDEMPOTENCY_KEY>/resource id) | BUDGET (<MAX_ITERATIONS> total turns used, ambiguous-response re-verify-only turns included) | NO-PROGRESS (NOT FOUND persists 3 straight verify-only turns past <PROPAGATION_WINDOW> with nothing new to try) | BLOCKED (approval gate not cleared for the current key+payload; tool has no idempotency-key support; independent read itself unavailable/erroring so the ambiguity can't be resolved; or a FOUND-duplicate-or-mismatch surfaced). Report idempotency_key, attempts_made, last_call_outcome, and verify_result_log at the point of halt.
```

### 4. Multi-Tool Plan Execution with Per-Call Verification

- **When:** You have a fixed, ordered plan of N tool calls across different tools (e.g. create-record → attach-file → send-notification → update-status) that must land in sequence because a later call depends on an earlier one's real effect, not just its return value — and a wrong or unconfirmed earlier step must never be built on.
- **Loop:** assess next unexecuted plan step and its declared precondition -> issue exactly that ONE tool call -> run the independent post-condition check for that step (a read distinct from the call just made) -> commit and advance if confirmed, else roll back (if reversible) and repair the step, never proceeding to step N+1 on unconfirmed step N -> decide continue/stop
- **Stop:** SUCCESS: every step in <PLAN> has been executed AND its independent post-condition check passed, in order, with no step skipped or assumed. · BUDGET: <MAX_ITERATIONS> total tool-call turns used across the whole plan. · NO-PROGRESS: the SAME plan step fails its post-condition check on 3 consecutive attempts with no new fix left to try (not counting the one sanctioned identical retry for a TRANSIENT failure), or the plan oscillates between two steps (advance to N+1, roll back to N, advance again with no changed input). · BLOCKED: the current step's precondition can never be satisfied with tools in <TOOL_SET> (capability gap), or the current step is irreversible/paid/destructive and the human-approval gate named at freeze time has not been cleared for that specific call, or a prior step's rollback itself fails (leaving state inconsistent) with no repair path.
- **Model:** Run ordinary steps (data-moving calls with a clean, mechanical post-condition — record created, file attached, row updated) on the run's standard model; this is capability-matching plus a status check, not judgment. Escalate to a stronger model only for: (a) a step whose post-condition check is ambiguous or requires interpreting content rather than checking a status/existence fact (e.g. "the notification text reads as intended," "the attached file is the correct version"), or (b) composing the repair plan after a step fails its post-condition check the first time — deciding whether to retry, replan args, roll back and re-order, or escalate to BLOCKED requires more reasoning than the routine calls do.

```text
GOAL (frozen — do not redefine mid-loop)
Execute <PLAN> — a fixed, ordered list of N tool calls, each naming its tool (from <TOOL_SET>), its arguments, and the real-world state it is supposed to produce — such that after the run, an INDEPENDENT check confirms every step's post-condition holds, in order, with no step's success assumed from its own return value and no later step ever issued while an earlier step's post-condition is still unconfirmed.

Freeze before turn 1: <PLAN> (the ordered step list: for each step, tool + args + one-line description of the real state it should produce); <TOOL_SET> (the fixed tools available, each with required-args schema); for EVERY step, its <POST_CONDITION_CHECK> — the exact independent read call, distinct from the step's own action call, that confirms that step's real effect landed (e.g. step = "create ticket via API" -> check = "GET the ticket by returned ID and confirm status=open"; step = "send Slack message" -> check = "list recent channel messages and confirm the new one is present with matching text" — never the send call's own 200 OK); which steps, if any, are reversible and by what specific undo action; which steps are irreversible/paid/destructive and therefore need a human-approval gate before execution (name the gate now, not mid-run); <MAX_ITERATIONS>.

PER-TURN SHAPE
1. ASSESS — Identify plan_step: the first step in <PLAN> whose post-condition is not yet confirmed. Read its tool, args, and precondition (does it depend on a fact confirmed by a prior step's <POST_CONDITION_CHECK>? if that prior confirmation is missing, STOP here — do not proceed on an assumption). Confirm the step is not irreversible/paid/destructive without its gate cleared.
2. ONE ACTION — Issue exactly ONE tool call: the call named by plan_step, using its frozen args (or a repaired arg set if this is a retry after a prior failed post-condition check — never a byte-identical repeat of args that already failed, except the one sanctioned TRANSIENT backoff-retry). If plan_step is gated and the gate is not cleared this turn, take no action and go straight to STOP: BLOCKED.
3. VERIFY — Run plan_step's frozen <POST_CONDITION_CHECK> — a read distinct from the call just made — and compare the result against the real state that step was supposed to produce. The tool call's own return value (200 OK, "success":true, no exception) is never treated as the check; it only justifies attempting the check.
4. DECIDE — If the check confirms the post-condition: commit (mark plan_step done), append it to confirmed_steps, and advance to the next unconfirmed step. If it does not confirm: classify the failure (transient / bad-args / step assumption wrong / tool incapable) — for a transient failure, retry the SAME call once after backoff (the loop's one sanctioned identical-args exception); for anything else, roll back plan_step's side effect if it is reversible, log the failure with cause, and repair (corrected args, or — if the step's own precondition was wrong — flag that an earlier step needs re-examination, never silently push forward). If plan_step has now failed 3 consecutive times with no new fix left to try, or rollback itself fails leaving state inconsistent with no repair path, STOP there rather than continuing to grind. If turn_count reaches <MAX_ITERATIONS>, STOP: BUDGET. Otherwise continue to the next turn.

CARRY-FORWARD STATE (compact — do not let this balloon)
- plan_step: <index/name of the current unconfirmed step in <PLAN>>
- confirmed_steps: <ordered list of step indices whose post-condition has already passed — never re-verified, never re-run>
- last_failure: <(step, tool, args-hash, failure-cause, rollback-outcome) for the most recent failed attempt only>
- attempts_this_step: <n>, reset to 0 whenever plan_step advances
- human_gate_status: <cleared|not-cleared, scoped to the one pending gated step only — resets to not-cleared once that step resolves>
- turn_count: <int> / budget <MAX_ITERATIONS>

ACTION BAN
- Never issue step K+1's call before step K's <POST_CONDITION_CHECK> has independently confirmed — a plan step's own "ok" response is not permission to advance.
- Never repeat a byte-identical call after a non-transient failure — repair the args or roll back; verbatim retry is reserved solely for the one sanctioned transient-backoff case.
- Never re-verify or re-run a step already in confirmed_steps — that's wasted turns, not diligence.
- Never oscillate a step between "advance" and "roll back" with no new input between attempts — that's NO-PROGRESS, not exploration.
- Never take a gated (irreversible/paid/destructive) step's call without a fresh human-approval clearance for that specific call, even if an earlier gated step in the same plan was already approved.
- Never let a failed rollback go unreported — an inconsistent post-rollback state with no repair path is BLOCKED, not a reason to push on to the next step anyway.

STOP — halt on the FIRST of:
SUCCESS (every step in <PLAN> executed and independently confirmed via its <POST_CONDITION_CHECK>, in order) | BUDGET (<MAX_ITERATIONS> total tool-call turns used across the whole plan) | NO-PROGRESS (the same plan step fails its post-condition check 3 consecutive times with no new fix left, excluding the one sanctioned transient retry; or advance/rollback oscillation on the same step with no changed input) | BLOCKED (current step's precondition unsatisfiable with <TOOL_SET> — capability gap; or an irreversible/paid/destructive step pending with no cleared human-approval gate; or a failed rollback leaving inconsistent state with no repair path). Report confirmed_steps, plan_step, and last_failure at the point of halt.
```

### 5. Tool-Argument Repair Before Calling

- **When:** Use whenever an agent has selected a tool but the argument object it wants to send has not yet been checked against that tool's schema — required fields, types, enums, ranges, formats, cross-field constraints — and calling it wrong would either error, no-op, or (worse) execute with silently-wrong parameters.
- **Loop:** assess (diff proposed args vs schema) -> one repair action (fix exactly the violations the verifier reported, nothing else) -> verify (independent schema validator re-checks the repaired args) -> decide (SUCCESS / retry / BUDGET / NO-PROGRESS / BLOCKED)
- **Stop:** SUCCESS: validator returns zero schema violations AND zero required-field gaps for <TOOL_NAME> against <TOOL_SCHEMA> — call is placed only after this exact state is reached · BUDGET: max <MAX_REPAIR_ATTEMPTS> repair attempts (default 4) before forced BLOCKED · NO-PROGRESS: violation_count (from the validator) does not strictly decrease for 2 consecutive attempts, OR the same field is repaired and re-flagged with the same error code twice · BLOCKED: a violation requires information not derivable from context (missing required value with no source, an enum value none of the allowed options match, a value that would need user judgment/credentials/scope the agent doesn't have) — surface the exact field + error + attempted repairs and stop for a human
- **Model:** Sonnet 5

```text
GOAL (frozen — do not renegotiate mid-loop):
Produce a call to <TOOL_NAME> whose argument object satisfies <TOOL_SCHEMA> in full (required fields present, types correct, enums matched, ranges/formats respected, cross-field constraints satisfied), as certified by an INDEPENDENT schema validator — never by your own read of the schema. Do not call <TOOL_NAME> until that validator reports zero violations. This prompt governs argument repair only; it does not authorize the call's downstream side effects — if <TOOL_NAME> itself is irreversible or paid (send, delete, purchase, deploy, broadcast), get explicit human confirmation of the FINAL validated args before the call fires, separate from this loop's schema pass.

INDEPENDENCE REQUIREMENT:
The verifier is a schema-validation function/library (e.g. jsonschema.validate, ajv, pydantic, or the tool platform's own pre-flight validator) invoked as a separate step — not the same model call that drafted the args re-reading the schema and declaring it fine. If no programmatic validator is wired up, construct one mechanically (parse <TOOL_SCHEMA>, check each field's presence/type/enum/range/pattern in code) rather than eyeballing it. The validator's output (a list of violations with field path + error code) is the only thing that can mark a field "fixed."

CARRY-FORWARD STATE (compact, update every turn):
- attempt: N (of <MAX_REPAIR_ATTEMPTS>)
- current_args: {the full argument object as of this turn}
- violations: [{field, error_code, expected, got}, ...] — from the LAST validator run, not a guess
- violation_count: integer (for NO-PROGRESS comparison)
- fields_touched_this_attempt: [field, ...] — must be a subset of violations from the prior turn; touching an already-clean field without cause is scope creep, flag and skip it
- repair_log: [{attempt, field, error_code, fix_applied}, ...] — append-only, used to ban verbatim retries (same field + same fix twice is a repeat, not a repair — pick a different fix or escalate to BLOCKED)

PER-TURN SHAPE:
1. ASSESS — read violations from the last validator run (or, on attempt 1, run the validator once against the initial draft args to get a baseline; do not skip straight to repairing on a guess).
2. ONE ACTION — for each violation, apply exactly one concrete, reversible repair to current_args (coerce a type, supply a required field from context, map a near-miss string to the correct enum value, clamp/reformat a value to the stated pattern/range). Do not touch fields the validator did not flag. Do not add speculative fields "just in case." Log each repair in repair_log before re-validating.
3. VERIFY — re-run the independent validator against the full repaired current_args. Record the new violations list and violation_count.
4. DECIDE:
   - SUCCESS: violation_count == 0 -> present the final args once, then place the call to <TOOL_NAME> (pausing first for human confirmation if the call is irreversible/paid per the goal note above).
   - BUDGET: attempt == <MAX_REPAIR_ATTEMPTS> and violation_count > 0 -> stop, report current_args, remaining violations, and full repair_log.
   - NO-PROGRESS: violation_count did not strictly decrease for 2 consecutive attempts, or repair_log shows the same {field, error_code, fix_applied} twice -> stop, do not retry the same fix a third way blindly; name a genuinely different repair strategy or fall through to BLOCKED.
   - BLOCKED: any remaining violation requires info/judgment/access not available in context (unresolvable required field, no matching enum value, needed credential/scope absent) -> stop, name the exact field + error + what's missing, request human input.
   - Otherwise: increment attempt, loop to step 1 with the new violations list.

ANTI-PATTERNS (banned):
- Re-submitting identical args hoping the validator "was wrong" the first time.
- Oscillating a field between two prior values (A -> B -> A) without a new rationale in repair_log.
- Fixing a flagged field by deleting/omitting it instead of correcting it (unless the schema marks it optional and the value is genuinely unknowable — then that's a BLOCKED case, not a silent drop).
- Calling <TOOL_NAME> "close enough" with violations still open, or self-certifying the schema is satisfied without running the validator.

STOP: halt on the first of SUCCESS (validator: zero violations, call placed) / BUDGET (<MAX_REPAIR_ATTEMPTS> attempts exhausted, violations remain) / NO-PROGRESS (violation_count flat 2 turns or a repair repeated) / BLOCKED (a violation needs human-supplied info, judgment, or access this loop doesn't have).
```
