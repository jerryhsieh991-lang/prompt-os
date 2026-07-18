# Video Generation

`video-generation` — 1 loop prompts.

### 1. Iterative Video Upscale/Detail Pass with Independent QA Gate

- **When:** Use when you have a generated video clip (<SOURCE_VIDEO_PATH>) that needs iterative resolution/detail upscaling and must clear an objective artifact/QA check before being published or handed downstream.
- **Loop:** assess current version's QA report -> pick ONE upscale/detail action -> run independent verifier (resolution + artifact scan) -> decide SUCCESS/BUDGET/NO-PROGRESS/BLOCKED
- **Stop:** SUCCESS: Verifier reports: output resolution >= <TARGET_RESOLUTION> AND artifact_score <= <MAX_ARTIFACT_SCORE> AND human reviewer has approved the frame-sample gate. · BUDGET: max <MAX_ITERATIONS> upscale/detail passes (default 5) · NO-PROGRESS: halt if artifact_score and resolution both fail to improve beyond <MIN_DELTA> for 2 consecutive turns · BLOCKED: halt if the upscale tool errors, source video is missing/corrupt, or the human gate is awaited/declined
- **Model:** Sonnet 5 (mechanical iterate-and-check loop; escalate to Opus only if the verifier's failure mode itself becomes ambiguous)

```text
GOAL (frozen, do not renegotiate mid-loop):
Take the video at <SOURCE_VIDEO_PATH> and produce an upscaled/detail-enhanced version that satisfies ALL of:
  1. Output resolution >= <TARGET_RESOLUTION> (e.g. 1920x1080 or 4K)
  2. Independent artifact/QA scan reports artifact_score <= <MAX_ARTIFACT_SCORE> (e.g. no flicker/ghosting/warping above threshold, temporal consistency delta <= <MAX_TEMPORAL_DELTA>)
  3. A human has reviewed a frame-sample gate and explicitly approved before the file is published/delivered to <DESTINATION>
The verifier that checks (1) and (2) is a SEPARATE tool/process from whatever model does the upscaling — it must never be the same model self-grading its own output, and it never reports raw "confidence." It emits a structured, re-runnable report: resolution, per-frame artifact_score, flagged frame ranges.

BEFORE the loop starts, freeze the rubric:
  - Verifier tool: <VERIFIER_TOOL> (e.g. video-QA CLI / frame-diff + no-reference IQA model like NIQE/BRISQUE + resolution probe via ffprobe)
  - artifact_score definition: <ARTIFACT_METRIC_DEFINITION> (lower = better; document exactly what it measures so it can't be redefined mid-loop to manufacture a pass)
  - TARGET_RESOLUTION, MAX_ARTIFACT_SCORE, MAX_TEMPORAL_DELTA: fixed numeric thresholds, set once, never loosened inside the loop
  - Human gate reviewer: <HUMAN_REVIEWER> (named person/role), sample: <N_SAMPLE_FRAMES> frames or a <SAMPLE_DURATION>s clip

PER-TURN SHAPE:
1. ASSESS — read the current QA report (if none exists yet, run the verifier once on the raw source to establish a baseline). Note current resolution, artifact_score, and which frame ranges are flagged.
2. ONE ACTION — apply exactly one reversible upscale/detail operation to a NEW output file (never overwrite the last good version):
   - candidates: run <UPSCALE_TOOL> at the next model/scale setting, re-run denoise/deflicker pass targeting only the flagged frame ranges from the last report, or re-encode at a different bitrate/codec if artifacts are compression-driven
   - pick the action most likely to address the SPECIFIC flaw the last report flagged — do not repeat the exact same action+params that already ran (ban verbatim retries)
   - do not oscillate between two settings (e.g. scale=2x then back to scale=1.5x then back to 2x) — if a setting was already tried and reverted, it's off the table for the rest of this loop
3. VERIFY — run <VERIFIER_TOOL> on the new output file only (not on the model's own claims). Record resolution, artifact_score, flagged ranges, and diff vs. the immediately prior report.
4. DECIDE — check the Stop conditions below in order; on anything but SUCCESS, log the compact state and either continue, halt, or escalate.

CARRY-FORWARD STATE (compact, passed to next turn — do not re-derive from scratch each time):
  - iteration count / <MAX_ITERATIONS>
  - current best output file path + its resolution + artifact_score
  - action history: [(action, params, resulting artifact_score, resulting resolution), ...] — used only to block verbatim repeats and A->B->A oscillation
  - flagged frame ranges from most recent verifier run
  - artifact_score trend over last 2 turns (for NO-PROGRESS check)
  - human gate status: not_requested / pending / approved / declined

STOP — halt on the FIRST of:
  - SUCCESS: resolution >= <TARGET_RESOLUTION> AND artifact_score <= <MAX_ARTIFACT_SCORE> AND human gate = approved. Publish/deliver to <DESTINATION> only after this line is true — never before.
  - BUDGET: iteration count reaches <MAX_ITERATIONS> without meeting SUCCESS — halt, surface the best-scoring file and its report, ask user whether to spend more budget or accept current best.
  - NO-PROGRESS: artifact_score and resolution both fail to improve past <MIN_DELTA> for 2 consecutive turns — halt, surface the plateaued report, do not keep spending compute on the same lever.
  - BLOCKED: upscale tool errors/crashes, source file missing/corrupt, verifier tool unavailable, or human gate has been pending > <GATE_TIMEOUT> with no response — halt and surface to a human; do not proceed to publish without the gate regardless of how good the metrics look.

Never publish, deliver, or overwrite the original source on anything short of the SUCCESS line being fully true, including the human-approved gate.
```
