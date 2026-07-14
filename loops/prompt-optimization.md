# Prompt Optimization

`prompt-optimization` — 8 loop prompts.

### 1. Classification Prompt vs. Frozen Gold-Label Set

- **When:** You have a labeled example set (ground-truth categories) and want to iteratively improve a classification/labeling prompt's accuracy without a human eyeballing outputs each round.
- **Loop:** assess (best prompt + last 3 misses) -> ONE variant targeting one failure pattern -> score full held-out set via scoring script -> commit or revert -> check 4 stop arms
- **Stop:** SUCCESS: accuracy >= frozen threshold on the held-out set · BUDGET: K iterations exhausted · NO-PROGRESS: no accuracy gain for 3 consecutive turns (one structurally different approach allowed, then halt) · BLOCKED: held-out set or scoring script unavailable
- **Model:** Verifier is a mechanical script, so a cheap model (Haiku-class) can draft variants fine; escalate to a stronger model only if failure patterns look semantically subtle (near-duplicate categories, ambiguous edge cases).

```text
Optimize a classification prompt against a frozen held-out set of N labeled examples. GOAL (frozen): accuracy >= X% on that set. Budget: K iterations. Each turn: (1) Assess -- current best prompt, its score, and the last 3 misclassified examples from the state log. (2) Act -- draft exactly ONE variant changing a single element (instruction, example, format rule) to address a concrete failure pattern; never resubmit a variant already tried. (3) Verify -- run the variant on the full held-out set with a scoring script separate from drafting; record accuracy and the new miss set. (4) Decide -- if accuracy improved, commit as best and update the scratchpad (best score, best prompt, patterns tried, iterations left); else discard and revert. Stop the instant one arm trips: SUCCESS (threshold met), BUDGET (iterations exhausted), NO-PROGRESS (no improvement for 3 turns -- try one structurally different approach, then halt if still flat), BLOCKED (held-out set or scorer unavailable). Report final prompt, score, stop reason. No new label categories mid-run -- backlog them.
```

### 2. Support-Reply Prompt vs. Rubric Judge

- **When:** No single correct reply exists (customer support, sales replies); you need a rubric-graded judge defined up front so 'good' is checkable every turn instead of vibes-based.
- **Loop:** assess (score breakdown per ticket) -> ONE change to tone/policy/escalation instruction -> render all tickets -> independent judge rubric-scores -> commit or revert -> check 4 stop arms
- **Stop:** SUCCESS: mean rubric score >= 4.2 across the fixed 15-ticket set · BUDGET: 8 iterations or 45 minutes wall-clock reached · NO-PROGRESS: score flat or oscillating for 3 turns -- force a different lever · BLOCKED: judge unavailable, or a ticket needs a human policy call
- **Model:** Use a stronger model (e.g. Fable 5 or Opus-class) in the judge role for nuanced tone/policy calls; the drafting/actor role can be a cheaper model since it only needs to propose edits, not evaluate them.

```text
Optimize a customer-support reply prompt where no single correct answer exists, so define the judge FIRST: a fixed rubric (1-5) on resolution-accuracy, policy adherence, and tone, applied by a role separate from drafting, seeing only rendered replies. GOAL (frozen): mean rubric score >= 4.2 across a fixed 15-ticket set. Budget: 8 iterations or 45 minutes. Per turn: assess current best prompt and its per-ticket score breakdown; change ONE thing (e.g. add an escalation clause, tighten tone) -- never a repeat of a discarded change; render replies for all 15 tickets; have the independent judge score them; if mean rises, commit and log score, change, still-failing tickets; else revert. Stop on first trip: SUCCESS (threshold met), BLOCKED (judge unavailable or a ticket needs human policy judgment), NO-PROGRESS (flat or oscillating score for 3 turns -- force a different lever), BUDGET (limit reached). The drafting model never grades itself.
```

### 3. Structured-Extraction Prompt vs. Schema + Field F1

- **When:** Optimizing a prompt that extracts JSON from documents, where correctness is fully mechanical (schema validity + field-level diff against gold JSON).
- **Loop:** assess (failing fields/docs from compact state) -> ONE change to a field description/format rule/example -> validate schema + compute F1 on full set -> commit only if neither metric regresses -> check 4 stop arms
- **Stop:** SUCCESS: 100% schema-valid AND field-level F1 >= 0.95 · BUDGET: 10 turns exhausted · NO-PROGRESS: F1 unchanged for 3 turns -- restructure rather than reword, then halt if still flat · BLOCKED: validator or gold set missing
- **Model:** Verification is fully scripted (no LLM judge needed), so a mid-tier model suffices for drafting; reach for a stronger model only if the schema is deeply nested or instructions are inherently ambiguous.

```text
Optimize a structured-extraction prompt against a frozen validation set of 20 documents with gold JSON. GOAL (frozen): 100% schema-valid output AND field-level F1 >= 0.95. Verification is mechanical and independent of the author: a JSON-schema validator plus a field-diff script -- never self-assessed. Budget: 10 turns. Each turn: assess current best prompt plus which fields/documents are still failing, from compact state, not the full transcript; make ONE change -- a field description, a formatting rule, or one added example -- targeting the most common failure; run all 20 documents, validate schema, compute F1; commit as new best only if both schema-validity and F1 hold or improve, else git-revert the prompt file so the workspace stays known-good. Stop on first arm: SUCCESS (both thresholds met), BUDGET (10 turns), NO-PROGRESS (F1 unchanged for 3 turns -- restructure the approach, don't just reword), BLOCKED (validator or gold set missing). No new fields or edge cases mid-run -- backlog them.
```

### 4. Summarization Prompt vs. Blind Pairwise Judge

- **When:** Improving a summarization prompt where quality is comparative rather than absolute -- judge by win-rate against a reference summarizer, not a shared scalar metric.
- **Loop:** assess (win-rate + judge's loss reasons) -> ONE targeted change -> regenerate all summaries -> blind order-randomized pairwise judge -> commit or revert -> check 4 stop arms
- **Stop:** SUCCESS: win-rate >= 70% on the fixed 12-document set · BUDGET: 6 iterations exhausted · NO-PROGRESS: win-rate flat +/-2pts for 3 turns, or oscillating between two variants -- change mechanism or halt · BLOCKED: judge or reference summarizer unavailable
- **Model:** The pairwise judge should be a stronger model than the drafter (e.g. Fable/Opus-class judging, Sonnet-class drafting) so faithfulness hallucinations are actually caught rather than rubber-stamped.

```text
Optimize a summarization prompt using blind pairwise preference judging, not a metric shared with drafting. GOAL (frozen): current-best summary beats a fixed reference summarizer on >= 70% of a fixed 12-document set, per an independent judge given only the two summaries (order-randomized) and fixed criteria (coverage, faithfulness, length). Budget: 6 iterations. Turn shape: assess current win-rate and the judge's stated reasons for recent losses; make ONE targeted change -- not a repeat of one already tried and reverted; regenerate all 12 summaries; run the blind judge; compute win-rate; if it rises, commit and log win-rate, change, recurring loss reasons; else revert to last-committed prompt. Stop on first trip: SUCCESS (win-rate >= 70%), BUDGET (6 iterations), NO-PROGRESS (win-rate flat +/-2pts for 3 turns, or oscillating between two variants -- change mechanism or halt), BLOCKED (judge or reference unavailable). Do not tune to the judge's exact phrasing -- that is Goodharting the metric.
```

### 5. Code-Gen Instruction Prompt vs. Frozen Test Suite

- **When:** Writing/refining the natural-language instruction a coding model receives, where ground truth is a test suite that must never be touched by the loop.
- **Loop:** assess (failing test names/errors, compact) -> ONE instruction change -> generate code + run suite in isolated env -> commit only if pass-count improves -> check 4 stop arms
- **Stop:** SUCCESS: all N tests pass on a clean run · BUDGET: 6 attempts exhausted · NO-PROGRESS: same tests failing 3 turns running -- change approach, not phrasing · BLOCKED: test harness won't run or environment is broken -- escalate
- **Model:** Use a strong coding-capable model for the actor (instruction drafting); the verifier is deterministic (test runner), so no LLM judge is needed at all -- keep it that way to avoid Goodharting on a soft signal.

```text
Optimize an instruction prompt that asks a coding model to implement a function, verified by a fixed test suite the drafter never edits -- ground truth, not a target to game. GOAL: all N tests pass on a clean run. Budget: 6 attempts. Per turn: assess current best prompt and the exact failing test names/errors from the last run, kept compact; change ONE aspect of the instruction (add a constraint, clarify an edge case, specify an interface) that plausibly fixes the actual failure -- never resubmit the same prompt verbatim hoping for a different sample; generate code, run the suite fresh in an isolated environment, record pass/fail per test; if more tests pass than current best, commit prompt and code and update state; else discard and keep the prior known-good version. Stop immediately on: SUCCESS (all tests green), BUDGET (6 attempts), NO-PROGRESS (same tests failing 3 turns running -- change approach, not phrasing), BLOCKED (harness won't run, environment broken -- escalate). Never edit the tests to make them pass.
```

### 6. Ad Copy Prompt vs. Frozen Rubric (No Ground Truth)

- **When:** Optimizing headline/CTA copy for a brand where there's no single right answer -- forces you to freeze a rubric and judge role before looping, per the pre-loop-rubric principle.
- **Loop:** assess (lowest-scoring rubric dimension) -> ONE change targeting that dimension -> generate copy for all briefs -> judge scores against frozen rubric -> commit or revert -> check 4 stop arms
- **Stop:** SUCCESS: mean rubric score >= 8.0 across the fixed 10-brief set · BUDGET: 5 iterations or 30 minutes exhausted · NO-PROGRESS: score flat for 3 turns -- try one structurally different angle, then halt · BLOCKED: brief or judge unavailable, or a claim-safety call needs a human
- **Model:** Judge role benefits from a stronger model for brand/voice nuance and claim-safety judgment calls; drafting can use a cheaper, higher-throughput model since you're generating many candidate variants.

```text
Optimize an ad headline+CTA prompt where no ground truth exists, so before looping, freeze a rubric (0-10): clarity, on-brand voice, CTA strength, claim-safety -- scored by a judge role distinct from drafting, working only from rendered output plus the brand brief. GOAL (frozen): mean score >= 8.0 across a fixed set of 10 briefs; scope frozen to headline + CTA only, no body copy, no new formats mid-run. Budget: 5 iterations or 30 minutes. Each turn: assess best-so-far score and the judge's lowest-scoring dimension; make ONE change targeting that dimension; generate copy for all 10 briefs; judge scores against the frozen rubric; commit only on improvement, else revert to the last-committed file. Stop on first arm: SUCCESS (score >= 8.0), BUDGET (exhausted), NO-PROGRESS (flat for 3 turns -- try one structurally different angle, then halt), BLOCKED (brief or judge unavailable, or a claim-safety call needs a human -- escalate, don't guess).
```

### 7. RAG Answer Prompt vs. Accuracy + Grounding Checker

- **When:** Tuning the generation-side prompt in a RAG pipeline (retrieval held fixed) where answers must be both factually correct and traceable to retrieved passages -- guards against fluent-but-ungrounded output.
- **Loop:** assess (which questions fail on accuracy vs. grounding) -> ONE change targeting the dominant failure category -> run full QA set, score both metrics -> commit only if neither regresses -> check 4 stop arms
- **Stop:** SUCCESS: exact-match/F1 >= 0.85 AND grounding checker confirms every claim on the 25-question set · BUDGET: 8 turns exhausted · NO-PROGRESS: neither metric moves for 3 turns, or the loop oscillates between two prompts -- change lever or halt · BLOCKED: retriever or grounding checker is down
- **Model:** Prefer a programmatic (embedding/string-match) grounding checker over an LLM judge to avoid Goodharting the same model family that generates answers; if an LLM grounding checker is unavoidable, use a different, stronger model than the generator.

```text
Optimize a RAG answer-generation prompt (retrieval fixed, only generation varies) against a frozen 25-question QA set with gold answers and gold passages. GOAL (frozen): exact-match/F1 >= 0.85 AND a citation-grounding checker confirms every claim traces to a retrieved passage -- both mechanical, run by a script independent of the prompt, never self-reported. Budget: 8 turns. Per turn: assess current best prompt plus which questions fail on accuracy vs. grounding, kept compact; make ONE change (e.g. "answer only from context," restructure citations) targeting whichever failure category dominates; run all 25 questions, score both metrics; commit only if neither regresses and one improves, else revert. Stop the instant one trips: SUCCESS (both thresholds met), BUDGET (8 turns), NO-PROGRESS (neither metric moves for 3 turns, or the loop oscillates between two prompts -- change lever or halt), BLOCKED (retriever or grounding checker down). Don't expand scope to fix retrieval -- that's a separate loop; backlog it.
```

### 8. Safety Refusal-Calibration Prompt vs. Dual Adversarial/Benign Sets

- **When:** Tuning a safety/refusal clause that must resist jailbreaks without over-refusing legitimate requests -- a dual-metric goal where optimizing one side alone is a trap.
- **Loop:** assess (both rates + failing cases per side) -> ONE change to the worse-performing side -> run both frozen sets fresh -> commit only if neither metric drops below its threshold -> check 4 stop arms
- **Stop:** SUCCESS: adversarial refusal rate >= 95% AND benign compliance rate >= 90%, simultaneously · BUDGET: 7 iterations exhausted · NO-PROGRESS: both rates flat, or the loop flips between over-permissive and over-restrictive for 3 turns · BLOCKED: either eval set unavailable, or a case needs policy judgment beyond the rubric -- escalate to a human
- **Model:** Use the strongest available model as the independent classifier/reviewer given the stakes, and ensure it is a different model or instance than the one being tuned so it doesn't share the actor's blind spots; keep a human escalation path live, don't let the loop grind through ambiguous policy calls alone.

```text
Optimize a safety system-prompt clause balancing refusal calibration: resist a frozen 20-case adversarial red-team set while not over-refusing a frozen 20-case benign edge-case set. GOAL (frozen, dual-metric): adversarial refusal rate >= 95% AND benign compliance rate >= 90%, scored by a harness distinct from the prompt-writer -- a fixed classifier or separate reviewer, never the acting model self-judging its own refusals. Budget: 7 iterations. Per turn: assess both current rates and which specific cases fail on each side; make ONE change (a boundary clarification, an example pair) aimed at the worse-performing side without knowingly trading it for the other; run both sets fresh; commit only if neither metric drops below threshold once met and the weighted sum improves, else revert. Stop on first: SUCCESS (both thresholds met simultaneously), BUDGET (7 iterations), NO-PROGRESS (both rates flat, or the loop flips between over-permissive and over-restrictive for 3 turns), BLOCKED (either set unavailable, or a case needs policy judgment beyond the rubric -- escalate to a human).
```
