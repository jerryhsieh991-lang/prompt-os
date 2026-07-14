# Red-Team / Adversarial Verify

`redteam-verify` — 8 loop prompts.

### 1. Claim-to-Publish: Adversarial Fact Check

- **When:** Before a factual claim, statistic, or quote is asserted in a report, article, or briefing and must survive independent scrutiny before publication.
- **Loop:** assess claim status -> one skeptic (fresh frame, new attack angle) challenges it -> verify the objection against a checkable source -> log verdict -> continue or stop
- **Stop:** SUCCESS: claim survives 3 independent skeptic passes, each attacking a distinct angle, with zero unresolved objections · BUDGET: 4 skeptic rounds used · NO-PROGRESS: 2 consecutive rounds raise the same objection type with no new evidence · BLOCKED: the claim's cited source is inaccessible or unverifiable
- **Model:** Skeptic role benefits from a stronger/creative model (Opus, Fable 5) to find non-obvious contradicting sources; the verify step is mechanical enough for a cheaper model (Haiku) once a citation just needs to be resolved and read.

```text
Freeze the claim verbatim before round 1: "[CLAIM]". Maintain a scratchpad — claim, sources cited so far, round count, skeptic log (round: objection, resolved Y/N), budget remaining. Each round: (1) assess current status; (2) run ONE skeptic pass in a fresh frame with no access to the defense's reasoning, attacking via a NEW angle each time — a contradicting source, a scope/definition gap, a base-rate sanity check, or an outdated-data check — never repeat a prior round's objection; (3) verify the skeptic's objection against a checkable, cited source, not assertion; (4) log the verdict and decide. If refuted, the claim is dead — stop and report the refutation; do not reword and resubmit it. Halt the moment any exit trips: SUCCESS — claim survives 3 distinct-angle skeptic passes, none unresolved; BUDGET — 4 rounds used; NO-PROGRESS — 2 straight rounds repeat the same objection type with no new evidence; BLOCKED — a cited source can't be accessed to check. The skeptic never grades its own attack; a separate pass confirms resolution.
```

### 2. Patch-Claim Red Team: Bug-Fix Verification

- **When:** Before merging a PR whose author claims 'this fixes bug X' or 'this change is safe' — force independent reproduction attempts before trusting the fix.
- **Loop:** assess fix status -> one skeptic attempts the original repro or a new regression angle -> verify by actually running it -> log -> continue or stop
- **Stop:** SUCCESS: original repro fails to reproduce AND 2 independent skeptics probing distinct regression angles find nothing, full suite green · BUDGET: 5 skeptic rounds · NO-PROGRESS: the same failure signature recurs 2 rounds in a row without a narrower fix attempt · BLOCKED: reproducing the bug requires an environment or resource unavailable to the loop
- **Model:** The patch author can run on a cheaper model for routine fixes; the skeptic hunting non-obvious regressions (concurrency, edge cases) benefits from a stronger model like Opus or Fable 5 on complex codebases.

```text
Freeze the claim: "[commit/PR] fixes [bug]". State: bug repro steps, patch diff, round count, skeptic log (round: attack tried, outcome), budget left. Each round: (1) assess — does the original repro still trigger? (2) ONE skeptic action per round, in a role distinct from whoever wrote the patch: re-run the original repro exactly as specified, OR probe one new angle (edge case, concurrency, rollback, adjacent code path) — never the same probe twice; (3) verify by actually running it (test suite, build, or manual repro), not by re-reading the diff; (4) log pass/fail and decide. A failing verify refutes the claim — stop, report the exact failure; do not patch-and-recheck in the same turn, that's two actions. Halt on first trip: SUCCESS — original repro fails AND 2 distinct-angle skeptic rounds find nothing, suite green; BUDGET — 5 rounds; NO-PROGRESS — same failure signature 2 rounds straight; BLOCKED — repro needs unavailable infra/data. End every round in a committed, reproducible state (git commit or explicit revert).
```

### 3. Pentest Finding Red Team: False-Positive Filter

- **When:** Before a security finding (e.g. 'endpoint X is vulnerable to SQLi') goes into a pentest report or ticket — adversarially confirm exploitability before it's trusted.
- **Loop:** assess finding status -> one skeptic attempts to disprove exploitability with a distinct technique -> verify with a real PoC against the live/staged target -> log -> continue or stop
- **Stop:** SUCCESS: finding survives 2 independent exploit-disproof attempts and a working PoC reproduces against the actual target · BUDGET: 4 rounds · NO-PROGRESS: 2 rounds in a row yield 'inconclusive' with no new technique proposed · BLOCKED: required target access or authorization is not currently granted
- **Model:** Use a stronger model (Opus/Fable 5) for the skeptic generating novel exploit-disproof techniques against hardened targets; running the PoC and reading response codes is mechanical and fine on a cheaper model.

```text
Freeze the finding verbatim: "[vulnerability claim] on [target]". State: finding, PoC attempts log (round: technique, result), round count, budget left. Each round: (1) assess — is exploitability confirmed, refuted, or open? (2) ONE skeptic action per round, run by a role that did NOT write the finding: attempt to disprove it via a distinct technique — a WAF/sanitization check, a different payload class, an environment/config check, or a false-positive scanner-artifact check — never repeat a prior technique; (3) verify against the real target (staging, not description) with an actual request/PoC, not reasoning about the code; (4) log the result and decide. If disproved, the finding is dead — report it as a false positive, do not soften it into a "potential" issue. Halt on first trip: SUCCESS — finding survives 2 distinct-technique disproof attempts with a reproduced working PoC; BUDGET — 4 rounds; NO-PROGRESS — 2 rounds produce "inconclusive" with no new technique proposed; BLOCKED — needed target access/authorization isn't available. Never accept the original discoverer's own re-test as the independent verification.
```

### 4. Result-to-Report: Adversarial Stats Check

- **When:** Before a data-analysis conclusion (e.g. 'treatment B improves conversion 12%, p<0.05') is written into a report or used to justify a decision.
- **Loop:** assess conclusion status -> one skeptic probes a specific statistical failure mode -> verify by recomputing on the raw data -> log -> continue or stop
- **Stop:** SUCCESS: conclusion survives 3 distinct statistical-attack rounds (confound, multiple-comparisons, sample-size/power, distribution assumption) with recomputation confirming it each time · BUDGET: 5 rounds · NO-PROGRESS: 2 rounds repeat the same failure-mode category without identifying a new confound or variable · BLOCKED: raw data or the analysis code needed to recompute isn't accessible
- **Model:** Skeptic role needs strong statistical reasoning to spot non-obvious confounds — use Opus/Fable 5; recomputation itself (running the script) is mechanical and can run on any tier.

```text
Freeze the conclusion: "[statistical claim]" from dataset "[X]". State: conclusion, analysis method, attack log (round: failure mode probed, outcome), round count, budget left. Each round: (1) assess current status; (2) ONE skeptic action per round, run independently of whoever produced the analysis: probe exactly one statistical failure mode per round — confounding variable, multiple-comparisons/p-hacking, insufficient sample size/power, violated distribution assumption, or selection bias — never re-probe a mode already cleared; (3) verify by actually recomputing on the raw data with the proposed correction/control, not by re-reading the write-up; (4) log the recomputed number and decide. If recomputation changes the conclusion's direction or significance, it's refuted — report the corrected result, don't cherry-pick a sub-slice that still supports the original claim. Halt on first trip: SUCCESS — conclusion survives 3 distinct failure-mode checks, recomputation confirms it each time; BUDGET — 5 rounds; NO-PROGRESS — 2 rounds repeat the same failure-mode category with no new variable; BLOCKED — raw data/analysis code unavailable. The skeptic must never share context with the original analysis.
```

### 5. IC Memo Red Team: Investment Thesis Verification

- **When:** Before an investment thesis claim (e.g. 'TAM is $4B, growing 20% YoY' or 'this moat is defensible') goes into an investment committee memo.
- **Loop:** assess thesis-point status -> one skeptic attacks a single load-bearing assumption with independent data -> verify against a primary/independent source -> log -> continue or stop
- **Stop:** SUCCESS: thesis point survives 3 rounds attacking distinct load-bearing assumptions, each checked against an independent source · BUDGET: 5 rounds · NO-PROGRESS: 2 rounds attack the same assumption without new independent data · BLOCKED: no independent data source exists to check a given assumption (management-only figures)
- **Model:** Best on a strong model (Opus/Fable 5) throughout — spotting weak market-sizing math and moat claims needs deep reasoning; don't downgrade the verify step either, since misjudging a financial claim is costly.

```text
Freeze the thesis point verbatim: "[claim, e.g. TAM/moat/growth]". State: claim, load-bearing assumptions list, attack log (round: assumption attacked, source used, verdict), round count, budget left. Each round: (1) assess which assumption is still untested; (2) ONE skeptic action per round, run as a devil's-advocate role separate from whoever wrote the memo: attack exactly one load-bearing assumption — market-size math, growth-rate extrapolation, competitive moat durability, or unit-economics — using an independent source (third-party market data, competitor filings, churn data), never the deal team's own deck twice; (3) verify the skeptic's counter-number against that independent source directly, not by trusting the citation; (4) log and decide. If an assumption breaks, the thesis point is refuted — report which pillar failed and by how much, don't reframe the claim to survive. Halt on first trip: SUCCESS — 3 distinct assumptions each survive independent-source checking; BUDGET — 5 rounds; NO-PROGRESS — 2 rounds re-attack the same assumption with no new source; BLOCKED — an assumption rests solely on unverifiable management-provided figures. Judge is a third party, not the memo author or the skeptic.
```

### 6. Compliance-Claim Red Team: Control Verification

- **When:** Before asserting 'this system/control satisfies [GDPR Art. X / SOC 2 CC6.1 / HIPAA §Y]' in an audit response, DPIA, or compliance attestation.
- **Loop:** assess control-claim status -> one skeptic maps the claim against the regulation's actual text and demands evidence -> verify the evidence exists and matches -> log -> continue or stop
- **Stop:** SUCCESS: claim survives 2 independent mapping-and-evidence rounds against the clause's actual text with concrete artifacts produced · BUDGET: 4 rounds · NO-PROGRESS: 2 rounds request the same missing evidence type without escalation · BLOCKED: the required evidence artifact does not exist and cannot be generated within the loop
- **Model:** A cheaper model (Haiku) can drive the mechanical evidence-matching once the clause is quoted; use a stronger model to correctly parse ambiguous regulatory language into concrete sub-requirements first.

```text
Freeze the claim: "[system/control] satisfies [specific regulation clause, quoted]". State: claim, clause text, evidence log (round: evidence requested, produced Y/N, matches clause Y/N), round count, budget left. Each round: (1) assess which sub-requirement of the clause is untested; (2) ONE skeptic action per round, played by a role that did not draft the claim: pick one sub-requirement the clause actually requires and demand concrete evidence — a config screenshot, an access log, a signed policy, a retention setting — never re-ask for evidence already produced; (3) verify the artifact actually exists and actually matches the clause's wording, not the claim's paraphrase of it; (4) log and decide. Missing or mismatched evidence refutes the claim — report the exact gap, don't accept a promise to fix it later as evidence. Halt on first trip: SUCCESS — 2 independent rounds each verify real evidence matching the clause; BUDGET — 4 rounds; NO-PROGRESS — 2 rounds stall on the same missing evidence type; BLOCKED — the evidence doesn't exist yet and can't be produced in-loop — escalate to the control owner.
```

### 7. Postmortem Red Team: Root-Cause Verification

- **When:** Before an incident postmortem's stated root cause ('the outage was caused by X') is finalized and action items are derived from it.
- **Loop:** assess root-cause status -> one skeptic tests an alternative causal explanation against the timeline/logs -> verify against raw evidence -> log -> continue or stop
- **Stop:** SUCCESS: stated root cause survives 3 rounds of alternative-hypothesis testing, each ruled out by direct timeline/log evidence · BUDGET: 5 rounds · NO-PROGRESS: 2 rounds propose no new alternative hypothesis, only restate the same one · BLOCKED: logs/telemetry needed to rule an alternative in or out were not retained
- **Model:** A stronger model (Opus/Fable 5) generates more plausible alternative hypotheses from sparse telemetry; a cheaper model is adequate once logs are structured and the check is a straightforward timestamp/grep comparison.

```text
Freeze the stated root cause: "[incident] was caused by [X]". State: claim, timeline/log evidence available, alternative-hypothesis log (round: hypothesis, ruled in/out, evidence), round count, budget left. Each round: (1) assess which alternative causes remain untested; (2) ONE skeptic action per round, run by someone outside the on-call/fix team: propose one alternative causal explanation the timeline could also support — a different upstream trigger, a coincidental deploy, a monitoring gap masking the real cause — never re-propose an already-ruled-out hypothesis; (3) verify against raw logs/traces/timestamps, not the incident summary's narrative; (4) log the verdict and decide. If an alternative fits the evidence as well or better, the stated cause is refuted — report the ambiguity, don't force a single cause to close the ticket. Halt on first trip: SUCCESS — stated cause survives 3 distinct alternative-hypothesis rounds, each ruled out by direct evidence; BUDGET — 5 rounds; NO-PROGRESS — 2 rounds with no new hypothesis proposed; BLOCKED — required logs/telemetry weren't retained. Action items get written only after SUCCESS.
```

### 8. Agent-Claim Red Team: Task-Completion Grounding

- **When:** Before trusting an AI agent's own report that a task is 'done' (file written, tests passing, deploy succeeded, email sent) — force verification against actual system state instead of the agent's narration.
- **Loop:** assess claim status -> one skeptic checks actual system state via an independent tool call -> verify the raw output -> log -> continue or stop
- **Stop:** SUCCESS: claim confirmed by 2 independent ground-truth checks via raw tool output that don't rely on the acting agent's self-report · BUDGET: 3 rounds · NO-PROGRESS: 2 rounds where the acting agent re-asserts the same claim without new tool evidence · BLOCKED: the system needed to check ground truth isn't accessible (no read access, no API)
- **Model:** This loop is cheap to run on any tier since it's mostly tool calls, not reasoning — a good fit for Haiku/Sonnet as a background self-check layer sitting on top of a stronger primary agent.

```text
Freeze the claim: "[agent] completed [task]". State: claim, ground-truth checks run (round: check, tool used, result), round count, budget left. Each round: (1) assess — has ground truth actually been checked yet, or only asserted? (2) ONE skeptic action per round, run as a fresh-context checker with no memory of the acting agent's reasoning: pick one ground-truth check that doesn't rely on the agent's narration — re-read the actual file, re-run the actual test suite, query the actual API/mailbox/database state — never accept "I already checked" as evidence; (3) verify by inspecting the raw tool output directly; (4) log and decide. A mismatch between claim and ground truth refutes it — report the actual state, don't let the acting agent re-narrate its way to "done". Halt on first trip: SUCCESS — 2 independent ground-truth checks confirm the claim via raw tool output; BUDGET — 3 rounds; NO-PROGRESS — 2 rounds of re-assertion with no new tool call; BLOCKED — no access to the system holding ground truth. The checker must never share a session with the acting agent.
```
