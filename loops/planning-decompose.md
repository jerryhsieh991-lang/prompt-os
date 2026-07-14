# Planning / Decompose

`planning-decompose` — 8 loop prompts.

### 1. Feature Request → Atomic Engineering Task Plan

- **When:** A PM/stakeholder hands you a fuzzy feature description before any code is written; you need a build-ready task list a team can pick up without further clarification.
- **Loop:** assess all leaf tasks against an atomicity+testability checklist -> split or annotate the ONE worst-offending task -> re-run the checklist as an independent pass -> report leaves total/passing and decide continue/stop
- **Stop:** SUCCESS: 100% of leaves pass the checklist on two consecutive turns · BUDGET: 10 decomposition passes used · NO-PROGRESS: the same task fails the checklist 2 turns running · BLOCKED: a task's scope depends on a product/design decision only a human can make
- **Model:** Opus 4.8 at xhigh is the sensible default — spotting implicit scope inside a fuzzy feature request needs real judgment. Sonnet 5 is fine for small, well-scoped features (CRUD, simple UI tweaks). Escalate to Fable 5 only when the feature spans many unfamiliar subsystems and atomicity boundaries are genuinely unclear.

```text
Freeze this goal for the whole session: decompose the fuzzy request below into an ordered task plan where every leaf task is ATOMIC (one engineer, one sitting, one PR) and TESTABLE (has a stated pass/fail check — a test, a build step, or an acceptance criterion someone else can verify). Goal: [paste feature request].

Each turn: (1) list current leaf tasks and run them against the atomicity+testability checklist — size, single owner, concrete verification step. (2) Pick the ONE worst-offending task and split it into 2-4 sub-tasks, or add the missing test/acceptance criterion if size is fine but verifiability is missing. (3) Re-run the checklist as an independent pass — do not just declare it fixed. (4) Report: leaves total, leaves passing, what changed, budget remaining.

Stop the moment one of these trips: SUCCESS — 100% of leaves pass the checklist twice in a row. BUDGET — 10 decomposition passes used. NO-PROGRESS — the same task fails the checklist 2 turns running. BLOCKED — a task's scope depends on a product/design decision only a human can make. Do not add tasks beyond the stated request; park extra ideas in a backlog note instead.
```

### 2. Vague Bug Report → Ordered Diagnostic Plan

- **When:** Someone reports "it's slow" or "something's broken" with no root cause identified yet; you need a decomposed investigation plan before touching any code.
- **Loop:** assess plan vs artifact-producing checklist -> split or clarify the ONE step still too broad or missing an output artifact -> independent re-pass confirms tool+action+output are named -> decide
- **Stop:** SUCCESS: every leaf names a tool, an action, and an output artifact, verified two turns running · BUDGET: 8 passes · NO-PROGRESS: leaf count and pass-rate unchanged for 3 turns · BLOCKED: a step requires access or logs you don't have
- **Model:** This is mechanical triage planning, not the diagnosis itself — Haiku 4.5 or Sonnet 5 is usually sufficient and cheap. Escalate to Opus 4.8 xhigh only if the system architecture is unfamiliar and picking the right split requires real domain judgment.

```text
Freeze the goal: turn this vague report into an ordered diagnostic task plan where every leaf step is ATOMIC (one check, one tool run, under 30 minutes) and TESTABLE (produces a concrete artifact — a log line, a metric, a reproduced error — that proves it was done). Report: [paste symptom].

Each turn: assess the current plan against that checklist, pick the ONE step that is still too broad (e.g. "investigate performance") or has no defined output artifact, split or clarify it, then run a second pass — not the same reasoning that wrote it — to confirm the revised step names its tool and its output. Carry forward only: current leaf list, pass/fail count, last change. Do not start executing the diagnosis; this loop only produces the plan.

Stop on whichever trips first: SUCCESS — every leaf names a tool, an action, and an output artifact, verified two turns running. BUDGET — 8 passes. NO-PROGRESS — leaf count and pass-rate unchanged for 3 turns. BLOCKED — a step requires access or logs you don't have. Never let "looks reasonable" substitute for the artifact check.
```

### 3. Fuzzy Research Question → Structured Research Plan

- **When:** Before running a literature review or deep-research loop, turn a broad question into an ordered set of atomic sub-questions each tagged with its own evidence bar.
- **Loop:** check every leaf sub-question against the evidence-bar rubric -> split a compound sub-question OR add a missing evidence bar (ONE action) -> fresh independent read confirms each leaf states its own success criterion -> decide
- **Stop:** SUCCESS: every leaf has a clear scope and evidence bar, confirmed on independent re-check · BUDGET: 8 turns · NO-PROGRESS: same leaf still failing after 2 consecutive differently-attempted fixes · BLOCKED: the question's scope itself is ambiguous and needs the requester's input
- **Model:** Opus 4.8 xhigh is the right default — cleanly splitting compound claims and setting a correct evidence bar needs judgment. Reserve Fable 5 for novel or highly technical domains where even defining the right evidence bar is hard; drop to Sonnet 5 once the domain is familiar and templated.

```text
Freeze this research question as the goal: [paste question]. Produce an ordered plan of leaf sub-questions, each ATOMIC (answerable from one class of source in one research pass) and TESTABLE (states what would count as sufficient corroborating evidence — e.g. two independent sources agreeing). This loop plans the research; it does not answer the question.

Per turn: check every leaf sub-question against that bar. Take ONE action — split a sub-question that bundles two claims, or add a missing evidence bar to one that lacks it. Then verify with a fresh read of the plan, not the reasoning that just wrote it: does each leaf state its own success criterion? Carry forward only the current leaf list and what changed last turn.

Stop the instant one arm trips: SUCCESS — every leaf has a clear scope and evidence bar, confirmed on independent re-check. BUDGET — 8 turns. NO-PROGRESS — same leaf still failing after 2 consecutive differently-attempted fixes. BLOCKED — the question's scope itself is ambiguous and needs the requester's input. Do not add tangential sub-questions; park them separately.
```

### 4. Fuzzy Launch Goal → Cross-Functional Task Plan

- **When:** A "launch X by Q3" business/GTM initiative spanning marketing, eng, and sales with no mechanical test available — verification must run against an explicit human rubric instead of a compiler.
- **Loop:** score every leaf task against a pre-written 4-line rubric -> split the least-compliant task OR assign a missing owner/date/done-criterion (ONE action) -> re-apply the rubric as if reviewing a colleague's plan -> decide
- **Stop:** SUCCESS: 100% of leaves pass the rubric, confirmed on a second independent pass · BUDGET: 8 passes or 45 minutes · NO-PROGRESS: compliant-leaf count unchanged for 2 turns · BLOCKED: a task needs a budget, headcount, or priority call only a stakeholder can make
- **Model:** The hard part here is writing a tight rubric, not raw model IQ — Sonnet 5 is often enough. Use Opus 4.8 xhigh when the initiative is complex enough that spotting missing owners or vague deliverables benefits from stronger reasoning.

```text
Freeze the goal: [paste launch/initiative goal and deadline]. Before this loop starts, write a 4-line rubric defining "atomic" (one owner, one deliverable, completable within one work session) and "testable" (a named person can say done/not-done by a stated date — no self-assessment). Then loop.

Each turn: score every leaf task against the rubric. Take ONE action: split the least-compliant task, or assign it a missing owner/date/done-criterion. Verify by applying the rubric fresh — if you wrote the task, check it as if reviewing a colleague's plan, not your own. State: leaves total, leaves compliant, budget left.

Stop on the first tripped arm: SUCCESS — 100% of leaves pass the rubric, confirmed on a second independent pass. BUDGET — 8 passes or 45 minutes. NO-PROGRESS — compliant-leaf count unchanged for 2 turns. BLOCKED — a task needs a budget, headcount, or priority call only a stakeholder can make — name it and stop. Freeze scope to the stated goal; new ideas go to a backlog, not into this plan.
```

### 5. Migration Goal → Reversible-Step Task Plan

- **When:** Turning "migrate service A off legacy system B" (with a hard constraint like zero-downtime) into an ordered plan of individually reversible, checkable steps, before any migration work starts.
- **Loop:** assess whether every leaf names its verification check and rollback action -> split a bundled step OR add the missing rollback/verification note (ONE action) -> fresh pass checks a third party could execute and verify it unaided -> decide
- **Stop:** SUCCESS: every leaf has a check and a rollback, confirmed twice · BUDGET: 8 decomposition turns · NO-PROGRESS: same step fails for 2 consecutive turns despite differently-attempted fixes · BLOCKED: a step depends on a resource or approval (e.g. prod access, security sign-off) you don't have
- **Model:** High-stakes and expensive to get wrong — default to Opus 4.8 xhigh. Escalate to Fable 5 for large distributed-systems migrations where rollback boundaries are subtle and a missed edge case is costly.

```text
Freeze the goal: [paste migration target and constraint, e.g. zero-downtime]. Build an ordered plan where every leaf step is ATOMIC (one reversible change), TESTABLE (a named check confirms it landed safely — health check, smoke test, metric threshold), and independently ROLLBACKABLE.

Per turn: assess the plan — does every leaf name its verification check and its rollback action? Take ONE action: split a step that bundles multiple changes, or add the missing rollback/verification note to one step. Re-check with a fresh pass: could someone else execute this step and know if it succeeded, without asking you? Carry forward: leaf list, compliant count, last edit, budget.

Stop the moment one arm trips: SUCCESS — every leaf has a check and a rollback, confirmed twice. BUDGET — 8 decomposition turns. NO-PROGRESS — same step fails for 2 consecutive turns despite differently-attempted fixes. BLOCKED — a step depends on a resource or approval (e.g. prod access, security sign-off) you don't have. This loop plans only — do not execute migration steps, and do not add steps beyond the stated scope.
```

### 6. Fuzzy Personal Goal → Weekly Atomic Action Plan

- **When:** An individual's "get good at X" or "ship Y" personal/learning goal with a deadline, needing decomposition into checkable weekly actions, self-verified against an explicit rubric.
- **Loop:** review the weekly task list against a pre-written done-rubric -> split an oversized task OR attach a missing artifact-check (ONE action) -> re-read as a skeptic, not the planner -> decide
- **Stop:** SUCCESS: every leaf task is atomic and has a checkable artifact, confirmed on re-read · BUDGET: 6 planning turns · NO-PROGRESS: same task un-fixed after 2 differently-attempted fixes · BLOCKED: the goal is too vague to decompose further without a scope/timeline decision only you can make
- **Model:** Low-stakes, single-user planning — Haiku 4.5 or Sonnet 5 is plenty. No need to spend Opus or Fable budget on this pattern.

```text
Freeze the goal and a deadline: [paste personal/learning goal, e.g. "ship a working side project in 6 weeks"]. Before looping, write an explicit done-rubric per task type (e.g. "atomic" = fits in one sitting under 2 hours; "testable" = produces a checkable artifact — code that runs, a page written, a rep count logged).

Each turn: review the current weekly task list against the rubric. Take ONE action — split a task that's really multiple sessions' worth, or attach a missing artifact-check to a vague one ("study X" becomes "complete exercises 1-5, paste output"). Verify by re-reading as a skeptic, not the planner: would a stranger know if this task got done? Log: tasks total, tasks compliant, budget left.

Stop on whichever trips first: SUCCESS — every leaf task is atomic and has a checkable artifact, confirmed on re-read. BUDGET — 6 planning turns. NO-PROGRESS — same task un-fixed after 2 differently-attempted fixes. BLOCKED — the goal itself is too vague to decompose further without a scope or timeline decision only you can make. Resist adding stretch goals — park them, don't plan them now.
```

### 7. Audit-Readiness Goal → Checklist-Verified Task Plan

- **When:** Preparing for a compliance certification or audit (SOC2, ISO, etc.) where the deliverable is a plan mapping every required control to an atomic, evidence-producing task.
- **Loop:** map leaf tasks to the standard's actual control list -> split an oversized task OR attach the missing control-ID/evidence-type (ONE action) -> verify against the control checklist itself, not prior reasoning -> decide
- **Stop:** SUCCESS: every control has a mapped, atomic, evidence-producing leaf task, cross-checked against the checklist twice · BUDGET: 10 turns · NO-PROGRESS: coverage percentage unchanged for 3 turns · BLOCKED: a control requires a policy decision or resource only compliance/legal can authorize
- **Model:** Misreading a control is costly, so precision matters — use Opus 4.8 xhigh by default. Escalate to Fable 5 for unusual or very new regulatory frameworks where standard training data is thin.

```text
Freeze the goal: prepare for [paste audit/certification] by [date]. Pull the actual control list or checklist for that standard as the independent verification source — the plan is graded against those controls, not against your own judgment of readiness.

Each turn: map current leaf tasks to controls; flag any leaf that isn't ATOMIC (single evidence artifact to produce) or TESTABLE (maps to one named control, has a stated evidence deliverable). Take ONE action: split an oversized task, or attach the missing control-ID/evidence-type to an under-specified one. Verify against the control checklist itself, not your prior reasoning. Carry forward: leaf list, controls covered/total, last change, budget.

Stop on the first arm to trip: SUCCESS — every control has a mapped, atomic, evidence-producing leaf task, cross-checked against the checklist twice. BUDGET — 10 turns. NO-PROGRESS — coverage percentage unchanged for 3 turns. BLOCKED — a control requires a policy decision or resource only compliance/legal can authorize. Do not plan remediation work beyond what the named controls require — no gold-plating the audit scope.
```

### 8. Fuzzy Automation Ask → Agent-Ready Task Plan

- **When:** Turning a fuzzy "automate this process" request into a plan of discrete, independently-executable subagent/tool-call tasks — the design step before building a multi-agent pipeline.
- **Loop:** scan for the least-compliant leaf (bundled tool calls or missing contract) -> split or specify it (ONE action) -> role-swap verify by reading it cold as the executing agent would -> decide
- **Stop:** SUCCESS: every leaf has a single responsibility and a checkable contract, confirmed on a cold re-read · BUDGET: 8 turns · NO-PROGRESS: same leaf unresolved after 2 differently-attempted fixes · BLOCKED: a leaf's contract depends on an API/tool that doesn't exist yet or needs human provisioning
- **Model:** This is meta-level agent design — Opus 4.8 xhigh is the right default. Use Fable 5 for genuinely novel multi-agent architectures where tool-call boundaries aren't obvious; a cheaper model (Sonnet/Haiku) can execute the loop mechanically once a human has sanity-checked the first pass.

```text
Freeze the goal: automate [paste process] end-to-end. Decompose into an ordered plan where every leaf task is ATOMIC (maps to one agent call or one tool invocation, no hidden multi-step reasoning inside a single "task") and TESTABLE (has an explicit input/output contract that a harness or a second agent can check without asking the author).

Per turn: scan the plan for the least-compliant leaf — one that bundles multiple tool calls, or lacks a defined input/output contract. Take ONE action to split or specify it. Verify with a role-swap: read it as the executing agent would, cold — is the contract unambiguous? Report leaves total/compliant, budget left.

Stop the instant one arm trips: SUCCESS — every leaf has a single responsibility and a checkable contract, confirmed on a cold re-read. BUDGET — 8 turns. NO-PROGRESS — same leaf unresolved after 2 differently-attempted fixes. BLOCKED — a leaf's contract depends on an API/tool that doesn't exist yet or needs human provisioning. Keep scope to the named process — do not design extra agents "while you're in there".
```
