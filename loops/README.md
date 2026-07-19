# Loop-prompt library

**154 reusable agent-loop prompts** across 26 loop families. Each is a copy-pasteable, model-agnostic prompt with an explicit stop condition so an agent iterates to a goal without looping forever.

Start with [loop-engineering principles](00-loop-engineering-principles.md), then browse a family:

- **[Build → Verify](build-verify.md)** — 8 prompts
- **[Debug / Root-Cause](debug-rootcause.md)** — 8 prompts
- **[Red-Team / Adversarial Verify](redteam-verify.md)** — 8 prompts
- **[Safe Refactor](refactor-safe.md)** — 8 prompts
- **[Research Until Dry](research-until-dry.md)** — 8 prompts
- **[Planning / Decompose](planning-decompose.md)** — 8 prompts
- **[Test Generation](test-generation.md)** — 8 prompts
- **[Review by Dimensions](review-dimensions.md)** — 8 prompts
- **[Self-Critique (Draft → Critique → Revise)](self-critique.md)** — 8 prompts
- **[Migration / Codemod](migration-codemod.md)** — 8 prompts
- **[Eval / Benchmark](eval-benchmark.md)** — 8 prompts
- **[Orchestration Harness (Fan-out / Pipeline)](orchestration-harness.md)** — 8 prompts
- **[Prompt Optimization](prompt-optimization.md)** — 8 prompts
- **[Data Pipeline / ETL](data-pipeline.md)** — 8 prompts

## Starter set

The most broadly useful prompts to try first (from curation):

- [build-verify] TDD Red-to-Green Loop (fix a failing test suite)
- [build-verify] Regression-First Bug Fix Loop
- [build-verify] Performance-Budget Optimization Loop
- [debug-rootcause] Production Crash / Stack-Trace Postmortem
- [debug-rootcause] Performance Regression Bisection
- [debug-rootcause] Flaky/Intermittent Test Root-Cause Hunt
- [refactor-safe] Baseline small-step refactor loop (existing test suite)
- [refactor-safe] Characterization-first refactor loop for untested legacy code
- [test-generation] Coverage-Gap Closer
- [migration-codemod] Deprecated API / Function-Signature Codemod
- [migration-codemod] Gradual Type Migration (JS -> TS strict-mode ratchet)
- [review-dimensions] General PR Review — Bugs / Security / Perf / Clarity
- [redteam-verify] Agent-Claim Red Team: Task-Completion Grounding
- [research-until-dry] Competitive Landscape Mapping
- [planning-decompose] Feature Request → Atomic Engineering Task Plan
- [eval-benchmark] Code-Gen Functional Correctness Loop (pass@1)
- [eval-benchmark] RAG Retrieval & Faithfulness Loop
- [prompt-optimization] Classification Prompt vs. Frozen Gold-Label Set
- [data-pipeline] Batch Schema Conformance & Quarantine
- [编排框架] Fan-Out Research Synthesis

## Curation notes

STRUCTURE: 154 prompts across 26 families, all sharing one meta-shape (frozen goal -> assess -> ONE reversible action -> independent verifier -> commit/revert -> 4-arm stop: SUCCESS/BUDGET/NO-PROGRESS/BLOCKED). That consistency is the library's main strength and makes prompts composable; the cost is heavy cross-family redundancy where the same loop reappears under a new framing.

TOP REDUNDANCY (structural, not just the 15 pairs above): the entire eval-benchmark family is a near-mirror of the entire prompt-optimization family. eval-benchmark = 'change ONE lever, re-run frozen eval, commit/revert'; prompt-optimization = the special case where the lever is restricted to prompt text. Four clean 1:1 dup pairs (Classification, Code-Gen, RAG, Safety). Recommendation: keep eval-benchmark as the general form and demote prompt-optimization to a documented 'lever = prompt' variant rather than a full parallel family.

SECOND: refactor-safe and migration-codemod overlap on mechanical migrations (API signatures, type ratchet, DB rename, framework/version upgrade). refactor-safe frames it as 'safe refactor under a metric'; migration-codemod frames it as 'codemod a frozen worklist' - same loop.

THIRD: the orchestration family (编排框架 Fan-out/Pipeline) is mostly a fan-out/subagent WRAPPER around single-thread loops that already exist elsewhere (Coverage-Driven Test-Gen ~ Coverage-Gap Closer; Codebase Migration Fan-Out ~ Deprecated API Codemod; Backlog Bug-Bash ~ Regression-First Bug Fix; Bulk Extraction ~ Extraction Validation). Legitimate as a distinct pattern, but a newcomer should learn the single-thread loop first, then reach for the fan-out only when parallelism pays. I kept exactly one orchestration prompt (Fan-Out Research Synthesis) in the starter set as the representative.

VERIFIER QUALITY is the sharpest quality axis. Strongest = mechanical, execution-based verifiers (test suite, schema validator, benchmark harness, scanner, EXPLAIN/ANALYZE, back-translation). Weakest = same-model-re-reads-its-own-output-with-a-persona (most of planning-decompose and 自我批判). Prefer/rewrite toward the former.

STARTER SET rationale: one representative per major mode (build / debug / refactor / test-gen / migrate / review / redteam / research / plan / LLM-eval / prompt-opt / data-pipeline / orchestration), biased toward everyday tasks and mechanical verifiers; deliberately excludes the redundant twins of items already included (e.g. picked eval Code-Gen over its prompt-opt twin, one type-migration over two). 20 items - trim to ~15 by dropping Performance-Budget (keep the debug bisection), one of the two eval entries, and the Feature->Task planner if a tighter intro is wanted.

METADATA SMELL (not a prompt-quality issue): the two Chinese-authored families carry an entire multi-sentence spec paragraph as their 'category title', repeated 8x. That belongs in one family-level header field, not duplicated per prompt.

(Note: user standing instruction is Chinese-only replies; wrote these curation notes in English because the deliverable is an English prompt library and every title/array entry must stay verbatim-English to be matchable by the orchestrator.)

### Known near-duplicates (kept, but be aware)

- eval-benchmark 'Classifier/Extraction Accuracy Gate (Dev/Held-Out Split)' ≈ prompt-optimization 'Classification Prompt vs. Frozen Gold-Label Set' — identical loop; only difference is 'change one lever' vs 'change the prompt'.
- eval-benchmark 'Code-Gen Functional Correctness Loop (pass@1)' ≈ prompt-optimization 'Code-Gen Instruction Prompt vs. Frozen Test Suite' — generate code, run frozen suite, commit only if pass-count improves.
- eval-benchmark 'Safety Refusal-Accuracy Loop (Independent Adversarial Verifier)' ≈ prompt-optimization 'Safety Refusal-Calibration Prompt vs. Dual Adversarial/Benign Sets' — same over/under-refusal loop.
- eval-benchmark 'RAG Retrieval & Faithfulness Loop' ≈ prompt-optimization 'RAG Answer Prompt vs. Accuracy + Grounding Checker' — run QA set, score accuracy+grounding, commit if neither regresses.
- refactor-safe 'Type-system migration with ratcheting strictness' ≈ migration-codemod 'Gradual Type Migration (JS -> TS strict-mode ratchet)' — same per-file error-count ratchet, typecheck + tests, commit/revert.
- refactor-safe 'Mechanical API/symbol migration across many call sites' ≈ migration-codemod 'Deprecated API / Function-Signature Codemod' ≈ 编排框架 'Codebase Migration Fan-Out' (the last is just the fan-out/subagent wrapper of the same worklist loop).
- build-verify 'Regression-First Bug Fix Loop' ≈ test-generation 'Bug Regression Test Loop' ≈ 编排框架 'Backlog Bug-Bash Fan-Out' (multi-issue wrapper) — all: reproduce → frozen regression test → minimal fix → full suite → commit/revert.
- 自我批判 'Ad Copy Rubric + Compliance Loop' ≈ prompt-optimization 'Ad Copy Prompt vs. Frozen Rubric (No Ground Truth)' — draft copy → rubric/compliance judge → one change.
- 自我批判 'Support Reply Policy + Tone Loop' ≈ prompt-optimization 'Support-Reply Prompt vs. Rubric Judge' — policy checklist + tone score → single revision.
- 自我批判 'Extraction Validation Loop' ≈ prompt-optimization 'Structured-Extraction Prompt vs. Schema + Field F1' ≈ 编排框架 'Bulk Document Extraction Fan-Out' — extract → schema validate + field-accuracy → single change (fan-out version just parallelizes).
- redteam-verify 'Claim-to-Publish: Adversarial Fact Check' ≈ research-until-dry 'Adversarial Fact-Check Sweep' ≈ 自我批判 'Research Synthesis Fact-Check Loop' — three framings of: pick a claim → challenge → verify against an independent source → log verdict.
- 自我批判 'Technical Documentation Revision Loop' ≈ review-dimensions 'Technical Documentation / Content Clarity Review' — assess sections → fresh-reader critique → fix one section → recheck.
- refactor-safe 'Database/schema refactor via expand-migrate-contract with shadow-read verification' ≈ migration-codemod 'Database Column/Field Rename Propagation' — overlapping DB-change-with-dry-run/shadow-verify (also adjacent to review-dimensions 'Database Schema / Migration Review').
- build-verify 'Performance-Budget Optimization Loop' ≈ review-dimensions 'Performance Review with Benchmark-Verified Findings' — apply one reversible change → rerun same benchmark → keep if improved & tests pass else revert.
- test-generation 'Coverage-Gap Closer' ≈ 编排框架 'Coverage-Driven Test Generation Fan-Out' — pick uncovered function → write one test → coverage tool + full suite as judge (fan-out just adds subagents).
