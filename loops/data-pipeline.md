# Data Pipeline / ETL

`data-pipeline` — 8 loop prompts.

### 1. Batch Schema Conformance & Quarantine

- **When:** Ingesting a raw tabular/CSV/JSON extract that must conform to a known schema (columns, dtypes, non-null rules) before it's usable downstream.
- **Loop:** assess unprocessed-row count -> pull one fixed-size batch -> validate against schema.json -> route rows to clean.csv or quarantine.csv with reason code -> run independent validator script on clean.csv -> decide
- **Stop:** SUCCESS: 0 unprocessed rows AND validator reports 0 schema violations in clean.csv · BUDGET: max_batches processed · NO-PROGRESS: pass rate unchanged within 1% for 3 consecutive batches · BLOCKED: schema is ambiguous or a required reference file is missing
- **Model:** Mostly mechanical rule-checking with a scripted verifier — a cheap/fast model (Haiku-tier) handles this fine once schema.json exists. Escalate to a stronger model only to author the schema and reason-code taxonomy up front.

```text
Goal (frozen): every row in <dataset> either passes schema validation against <schema.json> (exact column set, correct dtypes, non-null required fields) or is written to quarantine.csv with a reason code, until 100% of rows are accounted for in clean.csv + quarantine.csv, or a stop condition below trips.

Per turn: (1) assess — count rows still unprocessed; (2) pull exactly ONE batch of <batch_size> rows; (3) validate each row against the schema, coercing types where the schema permits but never silently dropping fields; (4) write passing rows to clean.csv and failing rows to quarantine.csv with a reason code; (5) run the independent validator script against clean.csv — a separate tool from your own validation logic — and report the pass rate.

Carry forward each turn: batches processed, cumulative pass rate, top 3 recurring reason codes, iterations used, budget remaining.

Stop on the FIRST that trips: SUCCESS — 0 unprocessed rows and the validator reports 0 schema violations in clean.csv; BUDGET — <max_batches> batches processed; NO-PROGRESS — pass rate unchanged within 1% for 3 consecutive batches; BLOCKED — the schema is ambiguous or a required reference file is missing. Do not edit schema.json mid-run or add validation rules beyond it.
```

### 2. Entity Deduplication / Fuzzy-Match Merge

- **When:** A customer/product/entity table has exact and near-duplicate records from multiple ingestion sources that need consolidating before analytics or CRM use.
- **Loop:** assess duplicate count via auditor -> pick single highest-count cluster -> merge or quarantine that one cluster -> re-run auditor on full table -> decide
- **Stop:** SUCCESS: 0 exact duplicates and <=threshold% fuzzy duplicates, reconfirmed · BUDGET: max_iterations reached · NO-PROGRESS: duplicate count flat for 3 turns despite a strategy change · BLOCKED: a merge decision needs a business rule not yet defined
- **Model:** Canonical-record selection and ambiguous-merge calls require real judgment; use a mid-to-high reasoning model (Sonnet/Opus-tier). A cheap model tends to over-merge distinct entities or under-merge true dupes.

```text
Goal (frozen): the entity table <table> has zero exact-key duplicates and no more than <threshold>% residual fuzzy duplicates, as measured by <dedup_audit_tool> — a script independent of your matching logic. Freeze the matching key and similarity threshold before the loop starts; do not retune them mid-run.

Per turn: (1) assess — run the auditor for the current duplicate count and pick the single highest-count duplicate cluster; (2) act — merge that one cluster (canonical record chosen by <rule>, e.g. most-complete or most-recent) or, if merge criteria aren't clearly met, quarantine it to needs-review.csv instead of guessing; (3) verify — rerun the auditor on the FULL table, not just the touched cluster; (4) decide, committing the table on improvement.

Carry forward: duplicate-count trend across the last 5 turns, clusters merged, clusters quarantined, iterations used. If the count hasn't dropped for 3 turns, change strategy (different matching field, one threshold adjustment) rather than repeat the same merge attempt.

Stop on FIRST: SUCCESS — 0 exact and ≤threshold% fuzzy duplicates, reconfirmed; BUDGET — <max_iterations>; NO-PROGRESS — count flat for 3 turns despite a strategy change; BLOCKED — a merge needs a business rule not yet defined.
```

### 3. PII/PHI Redaction Compliance Sweep

- **When:** A dataset must be scrubbed of regulated personal/health identifiers before it can be shared, published, or used for training, per a defined policy of categories.
- **Loop:** assess scanner hit counts by category -> apply one redaction rule to the highest-volume category -> rescan whole file -> commit or revert -> decide
- **Stop:** SUCCESS: 0 hits across all policy categories on two consecutive scans · BUDGET: max_iterations reached · NO-PROGRESS: total hit count unchanged for 3 turns · BLOCKED: a category needs a legal/policy call that can't be made unilaterally
- **Model:** Compliance-sensitive: a false 'clean' verdict has legal exposure. Use a stronger reasoning model (Opus-tier) and route any BLOCKED category to an actual human sign-off rather than letting the loop decide.

```text
Goal (frozen): <dataset> contains zero unredacted instances of the PII/PHI categories listed in <policy.yaml> (e.g. SSN, email, phone, MRN), confirmed by an independent scanner (regex+NER tool) that is a different mechanism from whatever redaction method you apply — grading your own regex with itself does not count as verification.

Per turn: (1) assess — run the scanner on the CURRENT working file and rank categories by hit count; (2) act — apply exactly ONE redaction rule to fix the single highest-volume leaking category (mask, tokenize, or drop per policy) and nothing else this turn; (3) verify — rerun the scanner on the whole file; (4) decide — commit the file if total hits dropped, revert if they rose (a regression means the rule was wrong).

Carry forward: per-category hit counts by turn, rules already applied, iterations used, remaining budget.

Stop on FIRST: SUCCESS — 0 hits across all policy categories on two consecutive scans; BUDGET — <max_iterations>; NO-PROGRESS — total hits unchanged for 3 turns; BLOCKED — a category needs a legal/policy call you can't make unilaterally. Never add redaction categories beyond policy.yaml — log ideas to backlog.md instead of acting on them.
```

### 4. Required-Field Completeness Remediation

- **When:** A dataset has missing values in fields required by downstream consumers, and each field needs a deliberate fill/backfill/quarantine decision rather than blanket imputation.
- **Loop:** assess per-field fill rates -> pick lowest-fill required field -> apply one remediation (impute/backfill/quarantine) -> re-run checker on full field set -> commit or revert -> decide
- **Stop:** SUCCESS: checker confirms >=threshold% completeness on every required field · BUDGET: max_iterations reached · NO-PROGRESS: overall completeness flat for 3 consecutive turns · BLOCKED: a field has no safe imputation source and quarantining would breach a minimum-row-count constraint
- **Model:** Execution is mechanical once remediation rules are documented — a mid-tier model (Sonnet) is sufficient. Use a stronger model upfront to design the per-field imputation rule set, since a bad default silently propagates.

```text
Goal (frozen): <dataset> reaches ≥<threshold>% completeness (non-null rate) on every field listed in <required_fields.txt>, verified each turn by an independent completeness-check script — not by inspecting the dataframe yourself.

Per turn: (1) assess — run the checker and identify the ONE required field with the lowest fill rate; (2) act — apply exactly one remediation to that field only: rule-based imputation with a documented default, cross-source backfill from <secondary_source>, or quarantine the row to incomplete.csv if no safe fill exists — never invent a value; (3) verify — rerun the checker across the FULL required-field set to confirm the target field improved and no other field regressed; (4) decide, committing the snapshot on improvement and reverting on regression.

Carry forward: per-field fill rates over time, which remediation was already tried per field (don't repeat a failed one), quarantined-row count, iterations used.

Stop on FIRST: SUCCESS — checker confirms ≥threshold% on every required field; BUDGET — <max_iterations>; NO-PROGRESS — overall completeness flat for 3 consecutive turns; BLOCKED — a field has no safe imputation source and quarantining it would breach a minimum-row-count constraint. Optional fields are out of scope — do not impute them.
```

### 5. Cross-Table Referential Integrity Reconciliation

- **When:** A fact table has foreign keys into one or more dimension tables (e.g. a warehouse star schema) and orphaned keys are breaking joins or reports.
- **Loop:** assess orphan counts per FK relationship -> fix or quarantine the single largest orphan set -> re-run full integrity checker across all relationships -> decide
- **Stop:** SUCCESS: 0 orphan rows across all FK relationships, reconfirmed twice · BUDGET: max_iterations reached · NO-PROGRESS: total orphan count unchanged for 3 turns · BLOCKED: a dimension table is missing entirely or its ownership is unclear
- **Model:** Root-causing orphan sets (ID drift vs encoding mismatch vs genuinely missing dimension row) needs multi-hop schema reasoning — favor a stronger reasoning model. A cheap model tends to default to quarantining everything instead of fixing the root cause.

```text
Goal (frozen): every foreign key in <fact_table> resolves to an existing row in its parent dimension table (<dim_tables>), with zero orphan rows, confirmed by an independent referential-integrity checker (a SQL constraint check or script separate from your fix logic).

Per turn: (1) assess — run the checker and rank broken FK relationships by orphan-row count; (2) act — fix only the single largest orphan set, using exactly one strategy: backfill the missing dimension row from <source_of_truth>, correct a specific key-mapping bug (ID drift, encoding mismatch), or quarantine the orphan fact rows to orphans.csv if the dimension record genuinely does not exist; (3) verify — rerun the FULL integrity checker across every FK relationship, not just the one touched, to catch newly introduced orphans; (4) decide.

Carry forward: orphan counts per relationship by turn, fixes already attempted (never retry a failed one verbatim), quarantine total, budget remaining.

Stop on FIRST: SUCCESS — 0 orphan rows across all relationships, reconfirmed twice; BUDGET — <max_iterations>; NO-PROGRESS — total orphans unchanged for 3 turns; BLOCKED — a dimension table is missing or ownership is unclear. Fix the data — never relax the constraint to force a pass.
```

### 6. Numeric Outlier / Range-Violation Quarantine

- **When:** A dataset's numeric columns (prices, ages, measurements) contain implausible values from unit errors, decimal shifts, or bad sensor/entry data that need correcting or isolating.
- **Loop:** assess violation counts per column via range checker -> fix or quarantine the worst column's violations -> re-run checker across ALL columns -> commit or revert -> decide
- **Stop:** SUCCESS: 0 violations across all columns per range_spec.yaml, reconfirmed · BUDGET: max_iterations reached · NO-PROGRESS: violation count unchanged for 3 turns · BLOCKED: a range bound itself looks wrong and needs a domain-expert call
- **Model:** Distinguishing a real data-entry bug from a legitimate extreme value is a judgment call with cost if wrong — use a mid-to-high tier model. A cheap model risks over-clipping legitimate long-tail data to hit the metric.

```text
Goal (frozen): the numeric columns in <dataset> defined by <range_spec.yaml> (plausible min/max or a z-score bound) contain zero out-of-range values in the clean set — each violation is either corrected via a documented, source-traceable fix or quarantined — verified each turn by an independent range-check script reading range_spec.yaml, not by your own judgment that a value "looks reasonable."

Per turn: (1) assess — run the checker and pick the column with the most violations; (2) act — apply ONE fix to that column only: correct a specific traceable bug (e.g. cents-vs-dollars, unit mismatch) or quarantine the offending rows to outliers.csv with the triggering value logged — never silently clip or delete; (3) verify — rerun the checker across ALL columns to catch regressions the fix introduced elsewhere; (4) decide, commit on improvement, revert on regression.

Carry forward: violation counts per column by turn, fixes already tried, quarantine count, iterations left.

Stop on FIRST: SUCCESS — 0 violations across all columns, reconfirmed; BUDGET — <max_iterations>; NO-PROGRESS — violation count unchanged for 3 turns; BLOCKED — a range bound itself looks wrong and needs a domain-expert call. Never widen range_spec.yaml to manufacture a pass.
```

### 7. LLM Pretraining Corpus Quality Filtering

- **When:** Preparing a raw text corpus for tokenizer/LLM pretraining that needs deduplication, language filtering, and quality-classifier filtering before it's clean enough to train on.
- **Loop:** assess largest failure category (dupes/language/quality) via fixed eval harness -> apply one filter to current batch -> re-run harness on clean/ -> decide
- **Stop:** SUCCESS: all three thresholds (dup, language, quality) met on two consecutive harness runs · BUDGET: max_batches reached · NO-PROGRESS: combined failure rate flat for 3 turns · BLOCKED: quality_classifier is flagging clearly good text and needs human recalibration
- **Model:** High-volume, mostly mechanical once thresholds are set — a cheap/fast model works fine for the loop itself. Use a stronger model (or a human) to calibrate quality_classifier and dup_threshold before the loop starts, since those choices are Goodhart-prone.

```text
Goal (frozen): <corpus_dir> reaches, on a fixed eval harness run fresh each turn (independent of your filtering code): (a) 0% exact/near-duplicate documents above <dup_threshold> similarity, (b) 0 documents failing language-ID for <target_lang>, (c) 0 documents scoring below <quality_threshold> on <quality_classifier>.

Per turn: (1) assess — run the harness and identify the single largest-volume failure category (dupes, language, or quality); (2) act — apply exactly ONE filter targeting that category to the current batch of <batch_size> documents only (e.g. one dedup shard, one classifier cutoff, one bad-language shard dropped) — move failing docs to quarantine/, never edit document text; (3) verify — rerun the full harness on clean/, confirming the target category improved and no other category regressed; (4) decide.

Carry forward: per-category failure counts by turn, batches processed, filters already applied (don't reapply an ineffective one), remaining budget.

Stop on FIRST: SUCCESS — all three thresholds met on two consecutive harness runs; BUDGET — <max_batches>; NO-PROGRESS — combined failure rate flat for 3 turns; BLOCKED — the quality classifier is flagging clearly good text and needs human recalibration. Never hand-tune thresholds just to force a pass.
```

### 8. Streaming Ingestion with Backpressure & Quarantine Sink

- **When:** A production ETL pipeline is consuming from a live queue/stream and must validate and route records batch-by-batch without blocking indefinitely or corrupting the clean sink.
- **Loop:** check queue depth and running error rate -> process one bounded batch -> verify via downstream check + recompute running error rate -> quarantine whole batch on spike -> decide
- **Stop:** SUCCESS: queue drained AND running error rate <= threshold for the full run · BUDGET: max_wall_clock or max_batches reached · NO-PROGRESS: error rate flat-or-rising for 3 consecutive batches under unchanged rules · BLOCKED: source stream unavailable or an upstream schema change breaks validation_rules.json
- **Model:** Time-sensitive, per-batch mechanical decisions running frequently under a hard budget — a cheap/fast model (Haiku-tier) is ideal so the loop stays cheap at high batch frequency. Escalate to a stronger model only when BLOCKED fires on an upstream schema change requiring diagnosis.

```text
Goal (frozen): every record from <source_stream> is routed to clean_sink (passes <validation_rules.json>) or quarantine_sink (with an error code) during this run, with clean_sink's running error rate ≤<threshold>%, measured by the pipeline's downstream consumer/lint check — a process independent of your ingestion code.

Per turn: (1) assess — check queue depth and the running error rate from the last window; (2) act — pull and process exactly ONE batch of ≤<batch_size> records (validate, transform, route) — nothing else this turn; (3) verify — run the downstream check against the newly written batch and recompute the running error rate for the whole run, not just this batch; if this batch's error rate spikes, quarantine the entire batch rather than partially committing; (4) decide.

Carry forward: cumulative records processed, running error rate, quarantine volume, last 3 batches' error trend, budget remaining.

Stop on FIRST: SUCCESS — queue drained and running error rate ≤threshold for the full run; BUDGET — <max_wall_clock or max_batches>; NO-PROGRESS — error rate flat-or-rising for 3 consecutive batches under unchanged rules; BLOCKED — the source is unavailable or an upstream schema change breaks validation_rules.json. Never suppress a validation rule to unblock — quarantine instead.
```
