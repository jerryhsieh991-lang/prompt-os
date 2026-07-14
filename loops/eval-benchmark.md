# Eval / Benchmark

`eval-benchmark` — 8 loop prompts.

### 1. Classifier/Extraction Accuracy Gate (Dev/Held-Out Split)

- **When:** Tuning a prompt, few-shot set, or extraction schema against a labeled classification or structured-extraction dataset where accuracy or F1 is the target metric.
- **Loop:** assess worst failure category on dev set -> change exactly one lever -> re-run fixed eval script on dev -> commit/revert -> periodically verify on held-out test -> decide
- **Stop:** SUCCESS: held-out test score >= target on a fresh run · BUDGET: 20 turns or 2 hours elapsed · NO-PROGRESS: dev score flat +/-0.5pt for 3 consecutive turns · BLOCKED: label scheme ambiguity requires a human decision
- **Model:** Actor can run on a cheap/fast model during dev-set iteration since the fixed script, not the model, grades each turn; reserve a stronger model for the periodic held-out gate only if evaluation noise or task difficulty demands it.

```text
Goal: raise [task] accuracy/F1 on the frozen dev set (path: [dev_set]) to >= [X]%, verified independently on a held-out test set (path: [test_set]) you must never look at while iterating. Freeze this target and both splits before turn 1.

Each turn: (1) assess current dev score and the single worst failure category from the last run's error log; (2) change exactly ONE lever — prompt wording, one few-shot example, or one schema constraint — never bundle edits; (3) re-run the eval harness (a fixed script, not your own judgment) on the dev set; (4) log delta, commit if improved, git-revert if worse. Carry forward only: goal, current best dev score, last 3 deltas, remaining budget, dead-ends tried. Every 5 turns, or when dev score first crosses target, run the held-out test set once as the real verifier.

Stop on whichever trips first: SUCCESS (test score >= target), BUDGET (20 turns or 2 hrs), NO-PROGRESS (dev score flat ±0.5pt for 3 turns — then change lever type, not retry), BLOCKED (label scheme is ambiguous — ask human).
```

### 2. RAG Retrieval & Faithfulness Loop

- **When:** Tuning chunking, retrieval parameters, or the synthesis prompt in a RAG pipeline against a fixed QA benchmark with known source documents.
- **Loop:** assess weaker of recall/faithfulness -> change one retrieval-or-synthesis lever -> replay fixed QA batch -> score via independent grounding-checker -> commit/revert -> decide
- **Stop:** SUCCESS: recall@k AND faithfulness both meet threshold on the same run · BUDGET: 15 turns · NO-PROGRESS: neither metric moves for 3 consecutive turns · BLOCKED: a gold answer has no valid source in the corpus
- **Model:** Keep the grounding-checker on a separate, ideally stronger model or family than the generator so it doesn't share the generator's hallucination blind spots; the generator can be a cheaper model while iterating quickly, with a final check on the production-tier model before declaring success.

```text
Goal: on the frozen QA benchmark [qa_set.json] (fixed N questions with gold source spans), reach retrieval recall@k >= [X] AND answer-faithfulness >= [Y], where faithfulness is scored by a separate grounding-checker (a script or distinct judge call verifying each answer sentence cites a retrieved chunk that actually contains it) — never let the generation model grade its own faithfulness.

Per turn: assess which of the two metrics is worse and pick the single failing example driving it; change ONE lever (chunk size, top-k, reranker, or the synthesis prompt) — not several at once; re-run the full QA batch through the fixed harness; record both metrics; commit on joint improvement, revert if either regresses without the other compensating.

Carry forward: goal, current (recall, faithfulness), last lever tried, budget remaining, questions still failing.

Stop on first trip: SUCCESS — both thresholds met on this turn's run; BUDGET — 15 turns; NO-PROGRESS — neither metric moves for 3 turns (force a lever-category switch, e.g. retrieval to prompt); BLOCKED — a gold answer has no valid source in the corpus, escalate rather than fabricate one.
```

### 3. Judge-Rubric Quality Loop (Tuning Set + Disjoint Judge Holdout)

- **When:** Improving a summarization, rewriting, or open-ended generation prompt where quality has no hard metric and must be scored against a rubric.
- **Loop:** freeze rubric + tuning/holdout split -> assess weakest criterion -> change one prompt element -> score tuning set with in-loop judge -> commit/revert -> periodic holdout check with a second independent judge -> decide
- **Stop:** SUCCESS: judge-B holdout run meets the frozen rubric threshold · BUDGET: 12 turns · NO-PROGRESS: tuning-set average flat for 3 consecutive turns · BLOCKED: rubric appears wrong for 2+ documents — escalate before redefining it
- **Model:** In-loop judge-A can be a cheaper/faster model for rapid tuning-set scoring; judge-B on the holdout should be a stronger or differently-sourced model (e.g. a top-tier model in a fresh context) specifically to catch cases where the loop overfit to judge-A's quirks rather than true quality.

```text
Before turn 1, freeze a rubric (e.g. 5 criteria scored 1-5, pass = average >=4 with no criterion below 3) and split sample documents into a 10-doc tuning set and a disjoint 10-doc holdout set. Use judge-A (fast, in-loop) only on the tuning set while iterating; reserve judge-B — a different model or a fresh context with no memory of your edits — for the holdout, run once per checkpoint, never mid-turn.

Per turn: assess the lowest-scoring rubric criterion on the tuning set; edit ONE part of the prompt (length instruction, structure, or tone guidance); re-run judge-A over the tuning set; commit if the average rises, revert if not.

Carry forward: goal, tuning average, last criterion targeted, edits already tried, budget left.

Stop on first: SUCCESS — a judge-B holdout run meets the frozen rubric threshold; BUDGET — 12 turns; NO-PROGRESS — tuning average flat for 3 turns (retarget which criterion you're improving, don't keep polishing the same one); BLOCKED — the rubric itself looks wrong for 2+ documents, ask a human before redefining it.
```

### 4. Code-Gen Functional Correctness Loop (pass@1)

- **When:** Improving a code-generation prompt or pipeline against a fixed suite of problems that have real, executable unit tests.
- **Loop:** assess highest-value failing task -> change one generation lever -> regenerate full set -> execute real tests for pass@1 -> commit/revert -> decide
- **Stop:** SUCCESS: pass@1 >= target on a fresh full run · BUDGET: 15 turns or 90 minutes of compute · NO-PROGRESS: pass@1 unchanged for 3 consecutive turns · BLOCKED: a test case itself appears broken
- **Model:** Verification is deterministic test execution, so model tier mostly affects iteration speed/cost, not trust in the signal; use a cheaper model for the bulk of turns and escalate to a stronger model only if the same failure class survives 3+ turns (the NO-PROGRESS arm).

```text
Goal: raise pass@1 on the frozen problem set [problems/, N tasks with hidden unit tests] from baseline to >= [X]%. Freeze the task set and test files before starting; never edit a test to make it pass.

Per turn: pick the single highest-value failing task (the most common failure pattern — off-by-one, wrong signature, missing edge case); change ONE thing — the generation prompt, a retry strategy, or a post-processing step — and regenerate solutions for the whole set; execute the real test suite via subprocess (not model narration) to get pass@1; commit on improvement, git-revert on regression.

Carry forward: goal, current pass@1, failing-task IDs, last lever changed, budget used.

Stop on first: SUCCESS — pass@1 >= target on a fresh full run; BUDGET — 15 turns or 90 minutes compute; NO-PROGRESS — pass@1 unchanged for 3 turns straight (change lever category, don't retry the same prompt tweak); BLOCKED — a test itself looks broken, flag to a human rather than silently editing or skipping it.
```

### 5. Safety Refusal-Accuracy Loop (Independent Adversarial Verifier)

- **When:** Hardening a system prompt or guardrail layer against a labeled red-team set covering both must-refuse and must-comply prompts.
- **Loop:** assess dominant failure class (over- vs under-refusal) -> change one guardrail element -> re-run full set -> score via independent verifier -> commit/revert -> decide
- **Stop:** SUCCESS: accuracy AND zero-over-refusal thresholds both met on a clean full run · BUDGET: 10 turns · NO-PROGRESS: flat for 3 consecutive turns on the same failure class · BLOCKED: a gold label looks wrong or a novel jailbreak pattern is found
- **Model:** The verifier/classifier should be independent of and ideally as strong as or stronger than the model under test to avoid shared blind spots; use a stronger model for adversarial case discovery when NO-PROGRESS triggers, since a weaker model may not find the next bypass pattern.

```text
Goal: on the frozen red-team set [redteam_set.json — must-refuse and must-comply cases labeled by a human], reach >= [X]% correct refusal/compliance decisions AND zero over-refusals on the must-comply subset, verified by an independent classifier or separate judge call that only ever sees the model's final response plus the gold label, never your system-prompt edits.

Per turn: assess which failure class dominates (over-refusal vs under-refusal) from the last verifier report; change ONE guardrail element — a system-prompt phrase, one refusal example, or one detection rule — never several; re-run the full set through the model, then the independent verifier; commit if accuracy and over-refusal both move the right direction, else revert.

Carry forward: goal, current (accuracy, over-refusal count), last lever, cases still wrong, budget left.

Stop on first: SUCCESS — both thresholds met on a clean full run; BUDGET — 10 turns; NO-PROGRESS — flat for 3 turns (switch which failure class you target); BLOCKED — a gold label looks wrong or a new jailbreak pattern surfaces — escalate, don't self-adjudicate.
```

### 6. Latency/Cost Loop Under a Quality Floor

- **When:** Optimizing a serving pipeline for latency or cost (model tier, caching, batching, prompt length) while a quality floor must hold.
- **Loop:** assess latency/quality tradeoff of last lever -> change one lever -> replay fixed traffic sample -> re-run quality harness -> commit only if both conditions hold -> decide
- **Stop:** SUCCESS: latency/cost target met with quality >= floor on the same turn · BUDGET: 12 turns · NO-PROGRESS: latency flat 3 turns, or quality repeatedly drops below floor on the same lever type · BLOCKED: target unreachable without a model or infrastructure change outside your control
- **Model:** Model tier is often literally the lever under test (e.g. swapping a cheaper model for a pricier one), so keep the quality harness's own judge/scorer fixed and separate from whichever model is being tuned, so comparisons across tiers stay apples-to-apples.

```text
Goal: reduce p95 latency (or $/1K requests) on the frozen load-test replay [traffic_sample.jsonl] to <= [X], while quality — measured by an existing harness independent of latency, e.g. task accuracy or judge score — stays >= [floor], both re-verified every turn, never assumed.

Per turn: assess whether the last lever hurt quality or helped latency more; change ONE lever — model tier, prompt truncation, caching rule, or batch size; replay the fixed traffic sample to measure p95/cost; run the quality harness on the same outputs; commit only if latency/cost improves AND quality >= floor, else revert both together.

Carry forward: goal, current (p95, quality), floor, last lever, budget.

Stop on first: SUCCESS — latency/cost target met with quality >= floor on this turn; BUDGET — 12 turns; NO-PROGRESS — latency flat for 3 turns, or quality keeps dropping below floor on the same lever type (stop reusing that lever); BLOCKED — target unreachable without a model or infrastructure change outside your control, escalate.
```

### 7. Agentic Tool-Use Task-Completion Loop

- **When:** Improving an agent's system prompt or tool schemas against a fixed suite of scripted multi-step scenarios with checkable end-state success predicates.
- **Loop:** assess most common failure mode -> change one prompt/tool-schema element -> replay full scenario suite in mock environment -> score via automated predicates -> commit/revert -> decide
- **Stop:** SUCCESS: task-completion rate >= target on a full scenario replay · BUDGET: 15 turns · NO-PROGRESS: pass rate unchanged for 3 consecutive turns · BLOCKED: a scenario's mock environment or success predicate appears broken
- **Model:** The verifier is code (state predicates), not a model, so trust doesn't depend on model tier; a cheaper model speeds up rapid scenario-replay iteration, but validate the final candidate configuration on the actual production-tier model before shipping, since tool-use reliability can shift across model tiers.

```text
Goal: on the frozen scenario suite [scenarios/, each with a scripted mock environment and a checkable success predicate over final state — not transcript tone], raise task-completion rate to >= [X]%. A scenario passes only if the automated predicate says so; the agent's own claim of completion never counts.

Per turn: assess the single most common failure mode across the last full run (wrong tool call, bad argument, premature stop, infinite retry); change ONE thing in the agent's own prompt — a tool description, one instruction, or one stop-condition rule; replay the full scenario suite in the mock environment; score via the predicates; commit if pass rate rises, revert if not.

Carry forward: goal, current pass rate, failing scenario IDs, last lever, budget.

Stop on first: SUCCESS — pass rate >= target on a full replay; BUDGET — 15 turns; NO-PROGRESS — unchanged for 3 turns (switch lever category, e.g. tool descriptions to stop-conditions); BLOCKED — a scenario's mock environment or predicate looks broken, escalate rather than patching the test to fit the agent.
```

### 8. Distilled/Fine-Tuned Model Regression Gate vs Golden Suite

- **When:** Gating a distilled, fine-tuned, or quantized model before it replaces a production baseline, to catch silent per-category capability regressions.
- **Loop:** assess worst-lagging category -> change one candidate-side training/calibration lever -> retrain narrowly -> re-run the FULL golden suite -> commit/revert checkpoint -> decide
- **Stop:** SUCCESS: every category at or above baseline within tolerance · BUDGET: 8 turns or a compute cap · NO-PROGRESS: the same category stays worst for 3 turns despite different levers · BLOCKED: training infrastructure unavailable or the golden-suite label is disputed
- **Model:** Golden-suite scorers should be deterministic/fixed wherever possible; where an LLM-judge is unavoidable inside the suite, pin that judge to one fixed model separate from both baseline and candidate so the comparison isn't confounded by the judge model also changing.

```text
Goal: the candidate model must match or beat the frozen baseline on EVERY category of the golden regression suite [golden_suite/, M categories with scoring rules already fixed] — not just the average — with no category regressing more than [tolerance]%.

Per turn: assess which category lags baseline the most; change ONE candidate-side lever — a distillation hyperparameter, a fine-tune data slice, or a calibration step; retrain/tune only that; re-run the FULL suite, not just the lagging category, to catch new regressions elsewhere; score with the suite's own fixed scorers, never the candidate grading itself; commit the checkpoint if no category regressed, else revert to the last good checkpoint.

Carry forward: goal, per-category deltas vs baseline, last lever, budget, categories still failing.

Stop on first: SUCCESS — all categories at or above baseline within tolerance; BUDGET — 8 turns or a compute cap; NO-PROGRESS — the same category stays worst for 3 turns despite different levers (escalate — may need an architecture change, not more tuning); BLOCKED — training infrastructure unavailable or the golden suite's label is disputed.
```
