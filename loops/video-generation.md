# Video Generation

`video-generation` — 5 loop prompts.

### 1. Iterative Video Upscale/Detail Pass with Independent QA + Detail-Gain Gate

- **When:** Use when you have a generated video clip (<SOURCE_VIDEO_PATH>) that needs iterative resolution/detail upscaling and must clear an objective artifact/QA check AND an objective reference-based detail-gain check before being published or handed downstream.
- **Loop:** assess current version's QA + detail-gain report -> pick ONE upscale/detail action -> run independent verifier (resolution + no-reference artifact scan + reference-based detail_gain vs. a fixed bicubic/Lanczos baseline) -> once all three numeric gates pass, request the human frame-sample gate that same turn -> decide SUCCESS/BUDGET/NO-PROGRESS/BLOCKED
- **Stop:** SUCCESS: resolution >= <TARGET_RESOLUTION> AND artifact_score <= <MAX_ARTIFACT_SCORE> AND detail_gain >= <MIN_DETAIL_GAIN> AND human reviewer has approved the frame-sample gate. · BUDGET: max <MAX_ITERATIONS> upscale/detail passes (default 5 for a short, single-artifact-type clip; raise it up front for long clips or clips with multiple distinct artifact types, since each turn spends exactly one action) · NO-PROGRESS: halt if artifact_score and detail_gain both fail to improve beyond <MIN_DELTA> for 2 consecutive turns · BLOCKED: halt if the upscale tool errors, source video is missing/corrupt, the verifier tool is unavailable, or the human gate has been pending > <GATE_TIMEOUT> with no response
- **Model:** Sonnet 5 (mechanical iterate-and-check loop; escalate to Opus only if the verifier's failure mode itself becomes ambiguous)

```text
GOAL (frozen, do not renegotiate mid-loop):
Take the video at <SOURCE_VIDEO_PATH> and produce an upscaled AND detail-enhanced version that satisfies ALL of:
  1. Output resolution >= <TARGET_RESOLUTION> (e.g. 1920x1080 or 4K)
  2. Independent no-reference artifact/QA scan reports artifact_score <= <MAX_ARTIFACT_SCORE> (e.g. no flicker/ghosting/warping above threshold, temporal consistency delta <= <MAX_TEMPORAL_DELTA>)
  3. Independent REFERENCE-based detail scan reports detail_gain >= <MIN_DETAIL_GAIN>, where detail_gain is the candidate's detail/sharpness score MINUS (or divided by, per <DETAIL_METRIC_DEFINITION>) the same score measured on a fixed <BASELINE_UPSCALE_METHOD> (bicubic or Lanczos, chosen once, never changed) applied to the source at the same TARGET_RESOLUTION
  4. A human has reviewed a frame-sample gate and explicitly approved before the file is published/delivered to <DESTINATION>
The verifier that checks (1), (2), and (3) is a SEPARATE tool/process from whatever model does the upscaling — it must never be the same model self-grading its own output, and it never reports raw "confidence." It emits a structured, re-runnable report: resolution, per-frame artifact_score, detail_gain vs. baseline, flagged frame ranges.

Why gate (3) exists and is load-bearing, not optional: no-reference IQA metrics like NIQE/BRISQUE (used for artifact_score) systematically reward smoothness and penalize high-frequency signal — a denoise/deflicker pass tuned purely to drive artifact_score down can suppress the metric while destroying real detail. Likewise a trivial bicubic/Lanczos resize satisfies gate (1) on resolution alone with zero added detail. Gates (1)+(2) together can therefore be maximized by "resize + smooth," which is exactly the failure mode this loop must NOT reward — it directly contradicts the stated goal of detail enhancement. Gate (3) closes that gap: it is reference-based (compares candidate vs. source-derived baseline, not a free-floating no-reference score) and specifically requires the candidate to beat a naive baseline upscale of the SAME source to the SAME resolution — so a naive resize scores ~0 on this gate by construction, and only genuine added detail clears it.

BEFORE the loop starts, freeze the rubric:
  - Verifier tool: <VERIFIER_TOOL> (e.g. video-QA CLI / frame-diff + no-reference IQA model like NIQE/BRISQUE + resolution probe via ffprobe + reference-based detail comparator)
  - artifact_score definition: <ARTIFACT_METRIC_DEFINITION> (lower = better; document exactly what it measures so it can't be redefined mid-loop to manufacture a pass)
  - detail_gain definition: <DETAIL_METRIC_DEFINITION> (higher = better; must be reference-based, comparing candidate vs. baseline on the SAME frames — e.g. high-frequency energy / Laplacian-variance ratio, edge-density delta, or a blinded paired-comparison judge scoring "which of these two frames shows more real detail, not more noise" — never a bare no-reference sharpness score, since those can't distinguish detail from noise)
  - <BASELINE_UPSCALE_METHOD>: the naive reference upscale (bicubic or Lanczos), picked once before the loop starts, never changed mid-loop, never itself eligible as the delivered output
  - TARGET_RESOLUTION, MAX_ARTIFACT_SCORE, MAX_TEMPORAL_DELTA, MIN_DETAIL_GAIN: fixed numeric thresholds, set once, never loosened inside the loop
  - Human gate reviewer: <HUMAN_REVIEWER> (named person/role), sample: <N_SAMPLE_FRAMES> frames or a <SAMPLE_DURATION>s clip
  - GATE_TIMEOUT: fixed duration after which an unanswered pending gate becomes BLOCKED

PER-TURN SHAPE:
1. ASSESS — read the current QA + detail-gain report (if none exists yet, run the verifier once on the raw source AND once on the <BASELINE_UPSCALE_METHOD> baseline, to establish the raw starting point and the fixed detail_gain reference score). Note current resolution, artifact_score, detail_gain, and which frame ranges are flagged.
2. ONE ACTION — apply exactly one reversible upscale/detail operation to a NEW output file (never overwrite the last good version):
   - candidates: run <UPSCALE_TOOL> at the next model/scale setting, re-run denoise/deflicker pass targeting only the flagged frame ranges from the last report, or re-encode at a different bitrate/codec if artifacts are compression-driven
   - pick the action most likely to address the SPECIFIC flaw the last report flagged — do not repeat the exact same action+params that already ran (ban verbatim retries)
   - do not oscillate between two settings (e.g. scale=2x then back to scale=1.5x then back to 2x) — if a setting was already tried and reverted, it's off the table for the rest of this loop
   - do not pick an action purely to chase artifact_score down (e.g. extra smoothing/denoise) unless it is also expected to hold or improve detail_gain — suppressing artifacts by destroying detail defeats the loop's actual goal and gate (3) will catch it anyway
3. VERIFY — run <VERIFIER_TOOL> on the new output file only (not on the model's own claims). Record resolution, artifact_score, detail_gain vs. baseline, flagged ranges, and diff vs. the immediately prior report.
4. DECIDE:
   a. Gate trigger (do this before checking Stop conditions): if resolution, artifact_score, AND detail_gain ALL pass their thresholds for the first time this loop and human gate status is still not_requested, request the frame-sample gate from <HUMAN_REVIEWER> now, in this same turn, and set gate status -> pending. Do not defer this to a later turn and do not let the loop keep spending iterations with the numeric gates green and the gate still not_requested.
   b. Check the Stop conditions below in order; on anything but SUCCESS, log the compact state and either continue, halt, or escalate.

CARRY-FORWARD STATE (compact, passed to next turn — do not re-derive from scratch each time):
  - iteration count / <MAX_ITERATIONS>
  - current best output file path + its resolution + artifact_score + detail_gain
  - baseline upscale's detail score (fixed reference point, computed once at ASSESS turn 1)
  - action history: [(action, params, resulting artifact_score, resulting resolution, resulting detail_gain), ...] — used only to block verbatim repeats and A->B->A oscillation
  - flagged frame ranges from most recent verifier run
  - artifact_score and detail_gain trend over last 2 turns (for NO-PROGRESS check)
  - human gate status: not_requested / pending / approved / declined — must flip to pending the instant all three numeric gates first pass (see DECIDE step 4a); never left at not_requested once gates clear

STOP — halt on the FIRST of:
  - SUCCESS: resolution >= <TARGET_RESOLUTION> AND artifact_score <= <MAX_ARTIFACT_SCORE> AND detail_gain >= <MIN_DETAIL_GAIN> AND human gate = approved. Publish/deliver to <DESTINATION> only after this line is true — never before.
  - BUDGET: iteration count reaches <MAX_ITERATIONS> without meeting SUCCESS — halt, surface the best-scoring file and its report, ask user whether to spend more budget or accept current best. Tuning note: default <MAX_ITERATIONS>=5 assumes a short clip with one dominant artifact type and one action spent per turn; for long clips, clips with multiple distinct artifact types (e.g. banding + ghosting + softness), or whenever a codec/bitrate remediation path hasn't even been tried by turn 3-4, raise <MAX_ITERATIONS> before starting rather than letting BUDGET fire before the right lever gets a turn.
  - NO-PROGRESS: artifact_score and detail_gain both fail to improve past <MIN_DELTA> for 2 consecutive turns (resolution is normally a one-time step-change from a single upscale pass, so it is not part of this stall check) — halt, surface the plateaued report, do not keep spending compute on the same lever.
  - BLOCKED: upscale tool errors/crashes, source file missing/corrupt, verifier tool unavailable, or human gate has been pending > <GATE_TIMEOUT> with no response — halt and surface to a human; do not proceed to publish without the gate regardless of how good the metrics look.

Never publish, deliver, or overwrite the original source on anything short of the SUCCESS line being fully true, including the human-approved gate.
```

### 2. Short Clip → Shot Brief with Rubric Judge (fixed)

- **When:** Use when producing one short video clip against a frozen shot brief, scored by an independent LLM-with-vision judge, and you need a bounded generate→verify→revise loop rather than one-shotting the clip.
- **Loop:** ASSESS (read last judge report + attempt/spend) -> ONE ACTION (single reversible edit tied to lowest-scoring dimension) -> VERIFY (independent judge scores new clip; calibration double-judge on any near-threshold or periodic-interval clip) -> DECIDE (apply STOP arms in fixed order: SUCCESS -> BUDGET -> NO-PROGRESS -> BLOCKED)
- **Stop:** SUCCESS: Judge total >= PASS_THRESHOLD (against the fixed /15 denominator) AND no single dimension <= MIN_DIMENSION_SCORE, AND — new in this fix — a same-clip calibration re-score (fresh judge session) of the winning candidate diverges from the first score by <= JUDGE_TOLERANCE, with the conservative (lower) of the two totals used for the threshold check. Report winning version, both score breakdowns, attempt count, spend; still requires the human sign-off gate before external delivery. · BUDGET: Attempt count reaches MAX_ITERATIONS OR spend reaches MAX_SPEND. Report best-scoring version so far and its gap to PASS_THRESHOLD on the /15 scale. · NO-PROGRESS: Judge total flat (gain < MIN_DELTA, where MIN_DELTA is constitutionally set > JUDGE_TOLERANCE so a "flat" reading can't just be judge noise) for K consecutive turns, OR the same lowest-scoring dimension unmoved for K turns, OR an A->B->A oscillation appears in action_log — oscillation is exclusively a NO-PROGRESS trigger now (no longer double-classified as BLOCKED). Report the stuck dimension/oscillating pair and recommend a brief or rubric revision (new loop) rather than continuing to cycle. · BLOCKED: Fires only on: (a) the calibration double-judge step (now a concrete, mechanically-triggered step inside VERIFY) shows two independent scorings of the identical clip diverging by more than JUDGE_TOLERANCE; (b) generation tool errors/refuses; (c) required reference assets missing; (d) next needed action requires unauthorized spend or human creative input. Report exactly what's missing/ambiguous/divergent and what decision or asset unblocks it. Oscillation is explicitly excluded from this arm (see NO-PROGRESS).
- **Model:** Generation: <VIDEO_GEN_TOOL/MODEL> (per user's task). Judge: an LLM-with-vision from a different model family/provider than whatever powers the generation tool's steering/prompt-following (not just a different session or checkpoint of the same family) — e.g. if generation is steered by a Family-X model, the judge must be Family-Y or Family-Z, to avoid correlated blind spots to that family's characteristic artifacts.

```text
GOAL (frozen, mechanically checkable — define BEFORE the loop starts):
Produce one short video clip that satisfies the SHOT BRIEF below, as measured by the RUBRIC below, scored by a judge that never generated or edited the clip and is drawn from a different model family than the one steering generation.

SHOT BRIEF (frozen — do not edit mid-loop; if it needs to change, that's a new loop):
  - Subject/action: <SUBJECT_AND_ACTION>
  - Setting/style: <SETTING_AND_VISUAL_STYLE>
  - Duration: <TARGET_DURATION_SECONDS>s (+/- <DURATION_TOLERANCE>s)
  - Camera: <CAMERA_MOVEMENT_AND_FRAMING>
  - Mood/lighting: <MOOD_AND_LIGHTING>
  - Must include: <REQUIRED_ELEMENTS_LIST>
  - Must avoid: <FORBIDDEN_ELEMENTS_LIST>
  - Reference assets (if any): <REF_ASSET_PATHS_OR_IDS>

RUBRIC (frozen, written before first generation — each dimension scored 0-3 by the judge):
  1. Brief fidelity — subject, action, setting, required elements all present, forbidden elements absent.
  2. Camera/framing match — matches specified camera movement and shot type.
  3. Visual quality — no major artifacts (warping, flicker, morphing, broken anatomy/objects), sufficient resolution.
  4. Mood/lighting/style match — tone and look match brief.
  5. Duration/pacing — within tolerance, motion reads as intentional not rushed/frozen.
  RUBRIC_MAX is FIXED at 15 (5 dimensions x 0-3 pts each) — this is not a free parameter; do not restate it on a different scale (e.g. "/10") anywhere in the filled-out loop.
  PASS = total >= PASS_THRESHOLD AND no single dimension <= MIN_DIMENSION_SCORE.
  Example of a correctly-scaled instantiation (illustrative only, replace with real values): PASS_THRESHOLD = 12 (of 15), MIN_DIMENSION_SCORE = 1. Do NOT instantiate PASS_THRESHOLD against any denominator other than 15 — a value like "8.5/10" is invalid because it doesn't match the fixed 5x0-3 rubric structure above.

PARAMETER RECONCILIATION (frozen, set together before first generation — these four numbers must be chosen jointly, not independently):
  - RUBRIC_MAX = 15 (fixed, derived — see RUBRIC above).
  - PASS_THRESHOLD, MIN_DIMENSION_SCORE — set against the /15 scale.
  - JUDGE_TOLERANCE — the judge's own admitted run-to-run noise floor on a repeat scoring of the identical clip (e.g. 1.0 pt of total). This must be measured/estimated before the loop starts (e.g. via one throwaway calibration pair) rather than guessed.
  - MIN_DELTA — the minimum total-score gain across turns that counts as "progress." MIN_DELTA MUST be set strictly greater than JUDGE_TOLERANCE (e.g. if JUDGE_TOLERANCE = 1.0 pt, MIN_DELTA >= 1.5 pt). If a candidate MIN_DELTA <= JUDGE_TOLERANCE, widen MIN_DELTA before starting — otherwise NO-PROGRESS would fire (or fail to fire) based on measurement noise instead of real quality change.

INDEPENDENT VERIFIER (must be separate from the generation call/model, and from a different model family):
  <JUDGE_SPEC> — a separate LLM-with-vision call, drawn from a different model family/provider than whatever model steers generation (not merely a different session or checkpoint of the same family — a same-family judge can share the generator's blind spots to its own characteristic artifact types). Given only the frozen SHOT BRIEF + RUBRIC + the candidate clip's extracted frames (no generation prompt history, no self-report), it returns per-dimension scores + total + one-line justification per dimension. Judge must not see prior scores or the generation prompt used, to avoid anchoring.

PER-TURN SHAPE:
  1. ASSESS — read last judge report (or none, on turn 1): total score, per-dimension scores, lowest-scoring dimension, its justification text. Read current attempt count and spend.
  2. ONE ACTION — take exactly one reversible step, chosen by the single lowest-scoring dimension:
       - Turn 1: generate clip v1 from the frozen brief via <VIDEO_GEN_TOOL/MODEL>.
       - Later turns: one targeted change only — e.g. edit ONE prompt clause tied to the weak dimension, OR adjust ONE generation parameter (seed, motion strength, duration, camera-control weight), OR regenerate with the same prompt at a different seed if the issue looks stochastic (artifacts) rather than systematic (wrong content).
       - Never change multiple dimensions' inputs in the same turn — isolates which edit caused which score movement.
       - Save the previous clip/version before overwriting (reversible: keep v(n-1) alongside v(n)).
  3. VERIFY — send the new clip + frozen brief + rubric to the independent judge. Record full per-dimension breakdown, not just total.
       - CALIBRATION CHECK (makes judge-inconsistency mechanically observable, not just declared): run a second independent judge scoring of the SAME clip (fresh session, same judge spec) whenever EITHER (a) this turn's total is within JUDGE_TOLERANCE of PASS_THRESHOLD (i.e. it's a plausible SUCCESS candidate), OR (b) it has been <CALIBRATION_INTERVAL> turns (e.g. every 3rd turn) since the last calibration check. Record both totals and their divergence.
       - If the two scorings of the identical clip diverge by more than JUDGE_TOLERANCE, do not treat either score as authoritative this turn — this is the BLOCKED judge-inconsistency condition (see STOP).
  4. DECIDE — apply the Stop line below, in order.

CARRY-FORWARD STATE (compact, pass to next turn only):
  attempt: <n>/<MAX_ITERATIONS> | spend: <$x>/<MAX_SPEND>
  last_total: <score>/15 | best_total_so_far: <score> (+ which version)
  per_dim: [fidelity:_, camera:_, quality:_, mood:_, pacing:_]
  lowest_dim_history: [last <K> turns' lowest-scoring dimension, to detect oscillation/staleness]
  last_calibration_check: <turn #, divergence observed, pass/fail vs JUDGE_TOLERANCE>
  last_action_taken: <one-line description of the single edit made>
  action_log: [list of every past action, to ban verbatim repeats and detect A->B->A oscillation]

ANTI-PATTERNS (banned):
  - Re-running the exact same prompt/seed/params combo twice (verbatim retry) — if it already failed, it fails again; either change the targeted clause or change the sampling seed explicitly, not both blindly.
  - Oscillating between two prompt variants A and B chasing two dimensions that trade off against each other (A->B->A) — if that pattern appears in action_log, that's a NO-PROGRESS condition (see STOP: NO-PROGRESS) — it means the brief likely has an internal conflict (e.g. "slow dreamy pacing" + "fits in 4s"); surface it and recommend a brief revision, don't keep cycling. (This is a NO-PROGRESS trigger only — it is not separately classified as BLOCKED, to avoid the two arms disagreeing on the same event.)
  - Trusting the generation model's own confidence/description of its output ("this looks great") as verification — only the independent judge's score counts.
  - Silently loosening the rubric, threshold, JUDGE_TOLERANCE, or MIN_DELTA mid-loop to force SUCCESS or dodge NO-PROGRESS/BLOCKED.

HUMAN/APPROVAL GATE:
  - Before the FIRST generation call if it is paid/metered: confirm estimated cost per attempt (including the extra cost of calibration double-judge calls) and the budget cap with the user.
  - Before any regeneration attempt once MAX_SPEND*0.8 has been spent: surface remaining budget and get explicit continue/stop confirmation.
  - Before publishing/delivering the final clip anywhere external (client, social, production pipeline): human sign-off on the winning version, even after judge SUCCESS — the judge gates iteration, not final release.
  - If BLOCKED fires on judge-inconsistency: surface both scorings and divergence to the user; they decide whether to raise JUDGE_TOLERANCE (if the noise looks acceptable), swap judge model, or treat the brief as ambiguous and pause for a new loop.

STOP — halt on the FIRST that triggers, checked in this order each turn:
  SUCCESS   — judge total >= PASS_THRESHOLD and no dimension <= MIN_DIMENSION_SCORE, AND the calibration re-score of this same winning clip is within JUDGE_TOLERANCE of the first score (use the lower/conservative of the two totals against PASS_THRESHOLD). Report winning version, full score breakdown from both judge runs, attempt count, spend.
  BUDGET    — attempt count reaches MAX_ITERATIONS OR spend reaches MAX_SPEND. Report best-scoring version so far + gap to PASS_THRESHOLD.
  NO-PROGRESS — judge total flat (< MIN_DELTA gain, and MIN_DELTA is constitutionally > JUDGE_TOLERANCE per PARAMETER RECONCILIATION, so "flat" can't just be noise) for K consecutive turns, or same lowest-scoring dimension unmoved for K turns, or an A->B->A oscillation detected in action_log. Report the stuck dimension/oscillating pair and recommend a brief/rubric revision (new loop) rather than continuing.
  BLOCKED   — the calibration double-judge check (run inside VERIFY, per PER-TURN SHAPE step 3) shows two scorings of the identical clip diverging by more than JUDGE_TOLERANCE, OR generation tool errors/refuses, OR required reference assets missing, OR next needed action requires unauthorized spend/human creative input. Report exactly what's missing/divergent and what decision or asset is needed to unblock. (Oscillation never fires this arm — see NO-PROGRESS.)

Return the full corrected prompt object.
```

### 3. Video Generation loop prompt: legible on-screen caption via independent OCR verifier

- **When:** Use when generated video must contain a specific on-screen caption that only counts as correct if an external OCR verifier can read it across sampled frames.
- **Loop:** assess (read prior state + last verifier output, pick single likely failure cause) -> one action (single reversible generation-config change, new output path) -> verify (run frozen external verify_caption.py OCR script) -> decide (SUCCESS/BUDGET/NO-PROGRESS/BLOCKED)
- **Stop:** SUCCESS: verify_caption.py prints PASS with match_fraction >= MIN_PASS_FRACTION across sampled frames between START_TS and END_TS · BUDGET: MAX_ITERATIONS turns (placeholder, e.g. 8) · NO-PROGRESS: match_fraction flat within PROGRESS_EPSILON for K consecutive turns despite trying distinct action types · BLOCKED: missing OCR engine/video-gen credentials, unrenderable glyphs in target string, or awaiting human approval on a cost/credit gate
- **Model:** Use a mid-tier model for mechanical caption/config iterations; escalate only when OCR failures point to ambiguous typography, timing, or generation-tool constraints.

```text
Goal (frozen, mechanically-checkable): Produce a video clip at <OUTPUT_PATH> in which the on-screen text overlay, sampled at <SAMPLE_FPS> fps between <START_TS> and <END_TS>, OCRs to exactly <TARGET_CAPTION_STRING> (normalized per <NORMALIZATION_RULES>) on at least <MIN_PASS_FRACTION> of sampled frames, using <OCR_ENGINE> run as a standalone script never touched by the generation step.

Independent verifier (frozen before loop starts, off-limits to edit): `verify_caption.py <video_path> <target_string>` — extracts frames at <SAMPLE_FPS>, crops to <TEXT_REGION_BBOX> if given, runs OCR, applies <NORMALIZATION_RULES>, prints `PASS <fraction>` or `FAIL <fraction> <misread_sample>`, exits 0/1.

Per-turn shape:
1. Assess — read prior state + last verifier output; identify single most likely failure cause (size/contrast, off-frame timing, typo/paraphrase, unsupported glyph).
2. One action — exactly one reversible change to generation config/prompt (font size/stroke/shadow, fix literal caption typo, adjust overlay timing, switch font), regenerate via <VIDEO_GEN_TOOL> to a NEW output path.
3. Verify — run verify_caption.py on the new output; record fraction, exit code, misread sample.
4. Decide — apply stop rule.

Carry-forward state (compact, per turn):
turn: <n>
last_action: <one-line change description>
match_fraction: <float>
delta_vs_prev: <+/-float>
misreads_sample: <e.g. "CAPTIN" vs "CAPTION">
actions_tried: [distinct change-types attempted — ban verbatim retries]

Anti-oscillation: never alternate the same two settings back and forth (A->B->A banned); if the next natural fix repeats an action-type from the last 2 turns, pick a different lever.

Human/approval gate: stop and get explicit confirmation before any turn that would exceed <PER_TURN_BUDGET> in generation cost/credits, or before using a paid/premium tier of <VIDEO_GEN_TOOL>. Never edit verify_caption.py.

Stop on the FIRST of:
- SUCCESS: verifier prints PASS with fraction >= <MIN_PASS_FRACTION>. Report final video path, fraction, winning config diff.
- BUDGET: <MAX_ITERATIONS> turns reached without SUCCESS. Report best-fraction attempt as fallback.
- NO-PROGRESS: match_fraction flat within <PROGRESS_EPSILON> for <K> consecutive turns despite distinct action types tried. Report plateau + misread pattern for human diagnosis.
- BLOCKED: missing OCR engine, missing <VIDEO_GEN_TOOL> credentials, target string has unrenderable glyphs, or cost gate awaiting approval. Report exact blocker.

Placeholders: <OUTPUT_PATH> <SAMPLE_FPS> <START_TS> <END_TS> <TARGET_CAPTION_STRING> <NORMALIZATION_RULES> <MIN_PASS_FRACTION> <OCR_ENGINE> <TEXT_REGION_BBOX> <VIDEO_GEN_TOOL> <GENERATION_COST_OR_CREDIT> <PER_TURN_BUDGET> <MAX_ITERATIONS> <PROGRESS_EPSILON> <K>
```

### 4. Iterative Motion-Match Generation with Independent Pose-Judge Gate

- **When:** Use when you need a generated video clip of a subject to match the motion of a reference clip, verified by an independent pose/motion judge (not the gen model, not the agent's own eyes), before it's accepted.
- **Loop:** ASSESS last judge flags -> pick ONE generation knob to change (from a pre-approved, frozen list) -> re-run generation -> VERIFY via independent pose judge against a frozen reference window -> DECIDE against SUCCESS/BUDGET/NO-PROGRESS/BLOCKED
- **Stop:** SUCCESS: Latest run's similarity >= TARGET_SCORE AND zero flags from MUST_NOT_FLAG_LIST = {missing_limb, flicker, wrong_bone_length, off_by_N_frames_lag} (low_confidence_frames is advisory-only, reported but non-blocking). Report best_run_path, final score, knob history; any follow-on paid step (upscale/render/delivery) needs human approval first. · BUDGET: Turn count reaches MAX_ITERATIONS OR cumulative_spend_usd (a carry-forward state field updated every turn from the generation invocation's own reported cost) reaches MAX_SPEND_USD. Report best_score_so_far, best_run_path, cumulative_spend_usd; stop spending. · NO-PROGRESS: score_history over the last K turns has moved by less than EPSILON in either direction (flat or noisy-flat). Stop, report, flag for human review of the allowed-knob list or reference clip quality — this usually signals a model/reference-format ceiling, not a tuning problem. · BLOCKED: Judge script errors or can't extract a confident pose on either clip; the needed next knob falls outside the pre-approved list; or the reference clip is missing/corrupt. Stop immediately, state exactly what's broken, request human input — never substitute a reference or guess a workaround.
- **Model:** Sonnet 5 for the mechanical iterate-and-verify loop itself; escalate only if the judge's failure mode or a knob's ambiguity requires deeper judgment than one-knob-at-a-time tuning.

```text
GOAL (frozen, do not renegotiate mid-loop):
Generate a video clip of <SUBJECT_DESCRIPTION> performing the motion shown in <REFERENCE_MOTION_CLIP_PATH_OR_URL> using <VIDEO_GEN_TOOL/MODEL>, such that an independent motion/pose judge scores the generated clip's motion similarity to the reference at or above <TARGET_SCORE, e.g. 0.85 mean per-joint PCK / DTW-aligned pose-correlation> across <MIN_FRAMES_OR_SECONDS_COVERED>, with zero flags from MUST_NOT_FLAG_LIST (defined below — covers missing-limb, flicker, wrong-bone-length, and frame-lag failure modes using the judge's exact flag strings).

Before the loop starts, fix and do not change:
- Reference clip: exact file/URL, frame range and fps to compare against (<REF_START>–<REF_END> @ <REF_FPS>). This window/fps is the judge's frozen verification target for the entire loop — no generation knob, including the sampling-stride knob below, may alter it.
- Judge = <POSE_ESTIMATION_TOOL, e.g. MediaPipe Pose / OpenPose / VideoPose3D> run as a separate script/service — NOT the video-gen model, NOT this agent's own visual read of the output. It must:
    1. Extract pose keypoints per frame from reference and from candidate.
    2. Temporally align (DTW or fixed-fps resample) reference vs candidate, always against the frozen <REF_START>–<REF_END> @ <REF_FPS> window — never a window the agent selects per-turn.
    3. Output a single scalar similarity score + a flags list drawn from exactly these flag strings: missing_limb, flicker, wrong_bone_length, off_by_N_frames_lag, low_confidence_frames.
  Judge lives at <JUDGE_SCRIPT_PATH>, invoked as: <JUDGE_INVOCATION_COMMAND>.
- MUST_NOT_FLAG_LIST (exact judge flag strings, blocking SUCCESS if any are present): {missing_limb, flicker, wrong_bone_length, off_by_N_frames_lag}. low_confidence_frames is advisory-only — it does not by itself block SUCCESS, but if it appears on the run that otherwise meets SUCCESS, the agent must report it alongside the passing score rather than silently drop it, since it signals the judge itself had low confidence on part of the comparison.
- Rubric for SUCCESS: similarity >= <TARGET_SCORE> AND zero flags in MUST_NOT_FLAG_LIST (as defined above).
- Generation knobs the agent is allowed to touch this loop: <e.g. motion-strength weight, reference-frame sampling stride, seed, motion-control adapter/LoRA choice, prompt text for appearance (not motion)>.
    - Clarification on reference-frame sampling stride: this knob controls only how densely the motion-control adapter samples the reference clip when building the generation-conditioning signal (i.e. an input to the generator). It never changes the frozen <REF_START>–<REF_END> @ <REF_FPS> window or fps that the judge uses to score the candidate — that window is fixed above and is off-limits to every knob in this list. Tuning this knob affects what the generator sees; it must never be used, or appear to be used, to make the judge's comparison easier.
  Anything outside this knob list (e.g. swapping the base model entirely, changing output resolution/duration) requires a human decision — flag BLOCKED, don't do it unilaterally.
- MAX_SPEND_USD: fixed dollar cap on cumulative generation spend for this loop, set once before turn 1, never raised mid-loop.

PER-TURN SHAPE:
1. ASSESS — read carry-forward state below. Identify the single highest-leverage knob to change this turn based on the judge's flags from the last run (e.g. flicker -> raise temporal-consistency weight; off_by_N_frames_lag -> adjust frame-sync offset; missing_limb -> increase motion-strength / switch reference-pose extractor).
2. ONE ACTION — change exactly that one knob to one new value. Do not change two knobs at once (can't attribute the delta). Re-run generation: <VIDEO_GEN_INVOCATION_COMMAND> -> writes <CANDIDATE_OUTPUT_PATH>/run_<N>.mp4. Capture the invocation's reported cost in USD from its response/billing metadata for this run.
3. VERIFY (independent) — run <JUDGE_INVOCATION_COMMAND> on run_<N>.mp4 against the frozen reference window. Record: similarity score, flags list (exact strings), wall-clock gen time, reported generation cost in USD, any generation-side errors/warnings.
4. DECIDE — apply the Stop line below. If none fire, update carry-forward state — including adding this turn's reported cost to cumulative_spend_usd, and appending this turn's (knob, value, score) to knobs_tried_this_direction — and begin the next turn.

CARRY-FORWARD STATE (compact, overwrite each turn — do not accumulate full logs):
- turn: <N>
- best_score_so_far: <score> (from run_<K>)
- best_run_path: <CANDIDATE_OUTPUT_PATH>/run_<K>.mp4
- cumulative_spend_usd: <running total of reported generation cost across every run this loop, updated every turn from the generation invocation's own reported cost — this is what BUDGET's spend check reads>
- last_knob_changed: <name> <old_value> -> <new_value>
- last_score: <score>, last_flags: [<flag>, ...]
- score_history (last 4 turns only): [<s1>, <s2>, <s3>, <s4>]
- knobs_tried_this_direction: [<(knob, value, resulting_score) triples already attempted — the score is required, not optional, so BAN's oscillation rule and verbatim-repeat rule are both mechanically checkable from this field alone>]

BAN:
- Do not re-run with an identical knob/value combo already in knobs_tried_this_direction (check the (knob, value) pair regardless of what score it produced).
- Do not oscillate a knob back to a value already scored lower two turns ago (A->B->A): before changing a knob, look up its distinct previously-tried values in knobs_tried_this_direction with their recorded scores — if the last two distinct values tried for that knob both scored below best_score_so_far, that knob is exhausted; pick a different knob next turn instead of returning to any of its tried values.
- Do not let the agent itself eyeball the video and declare success — score comes only from the judge script's output.

STOP — halt on the FIRST that fires, check in this order:
- SUCCESS: latest run's similarity >= <TARGET_SCORE> and flags list has zero entries from MUST_NOT_FLAG_LIST. Report best_run_path, final score, any advisory low_confidence_frames flag if present, knob history, and stop. This is an irreversible/paid step if <VIDEO_GEN_TOOL> bills per generation past this point (e.g. upscale, delivery render) — get human approval before any such follow-on spend.
- BUDGET: turn count reaches <MAX_ITERATIONS, e.g. 8> OR cumulative_spend_usd (read from carry-forward state, updated every turn per PER-TURN SHAPE step 2) reaches <MAX_SPEND_USD>. Report best_score_so_far, best_run_path, and cumulative_spend_usd, stop, do not keep spending.
- NO-PROGRESS: score_history over the last <K, e.g. 3> turns has moved by less than <EPSILON, e.g. 0.02> in either direction (flat or noisy-flat). Stop and report — this usually means the remaining gap is a model/reference-format limitation, not a knob-tuning problem; flag for human review of the allowed-knob list or reference clip quality.
- BLOCKED: judge script errors or can't extract a confident pose on either clip (e.g. low resolution, occlusion, wrong subject in frame) OR the needed next knob falls outside the pre-approved list OR the reference clip itself is missing/corrupt. Stop immediately, state exactly what's missing/broken, request human input. Do not substitute a different reference or guess a workaround.
```

### 5. Duration and Pacing to Spec (Frozen Cut-Alignment + Verifier-Integrity Lock)

- **When:** Use when you have a rendered or in-progress video at &lt;OUTPUT_PATH&gt; that must simultaneously hit an exact duration, an exact ordered list of cut timestamps, and a target frame rate, and you need a genuinely deterministic, non-gameable pass/fail loop instead of a human eyeballing the pacing.
- **Loop:** ASSESS (checksum-verify the verifier, run it fresh, order-preserving cut alignment, normalized error_score) -> ONE ACTION targeting the single largest normalized error term -> VERIFY (independent re-run, checksum re-checked) -> DECIDE (SUCCESS, then BLOCKED, then NO-PROGRESS, then BUDGET — fixed order, identical in both the per-turn shape and the top-level STOP block)
- **Stop:** SUCCESS: All three deterministic checks pass simultaneously on the latest verifier run against &lt;OUTPUT_PATH&gt;: |actual_duration_sec - TARGET_DURATION_SEC| &lt;= DURATION_TOLERANCE_SEC; the frozen cut-alignment routine (see prompt) reports missing_count == 0, extra_count == 0, and every matched pair's raw (non-normalized) delta &lt;= CUT_TOLERANCE_SEC; and the fps check passes (exact match against avg_frame_rate if the output is confirmed CFR, or within FPS_TOLERANCE of avg_frame_rate if confirmed VFR). Report final measured values (both r_frame_rate and avg_frame_rate, full matched cut list) alongside spec. · BUDGET: Iteration count reaches &lt;MAX_ITERATIONS&gt; (suggest 8) without SUCCESS. Report best normalized error_score achieved and the remaining per-term deltas. · NO-PROGRESS: Normalized error_score fails to improve by &gt;= &lt;MIN_IMPROVEMENT_PCT&gt; (suggest 5%) for &lt;K&gt; (suggest 3) consecutive turns, or a verbatim retry / A-&gt;B-&gt;A oscillation on the same target is detected. Report the plateaued state and everything already tried on that target. · BLOCKED: Verifier checksum mismatch (someone/something edited the verifier's script, config, or thresholds mid-loop); source too short/long for the target even at edit limits; a target cut fails the pre-loop detectability check (falls inside a dissolve/fade/whip-pan or near-identical-shot region the detector can't resolve); spec cut count exceeds detectable scene changes; &lt;EDIT_TOOL&gt; or &lt;VERIFIER_CMD&gt; errors or is missing; or the needed decision requires human judgment (e.g. picking among equally-valid takes). Report the exact blocking fact — do not guess or retry past it.
- **Model:** Sonnet 5 for the mechanical iterate-and-verify loop (the matching algorithm, error_score, and stop logic are now fully specified, so no judgment calls are needed to run a turn). Escalate to Opus only for the one-time pre-flight detectability judgment (step D) or if a BLOCKED verdict requires reasoning about whether the spec itself is salvageable.

```text
GOAL (frozen — do not redefine mid-loop):
Produce a rendered video file at <OUTPUT_PATH> that satisfies, simultaneously:
  - duration: <TARGET_DURATION_SEC> sec, tolerance ± <DURATION_TOLERANCE_SEC> sec
  - cuts: exactly <TARGET_CUT_COUNT> cuts, at timestamps <TARGET_CUT_TIMESTAMPS_SEC> (list, sec from start, ascending order), each within ± <CUT_TOLERANCE_SEC> sec of the target it is matched to (matching defined below — no other matching rule is permitted)
  - frame rate: <TARGET_FPS> fps, measured per the FROZEN MEASUREMENT RULES below (tolerance ± <FPS_TOLERANCE> fps applies only when the output is confirmed variable-frame-rate by that same rule)
Source material: <SOURCE_CLIP_PATHS_OR_GLOB>. Editing tool: <EDIT_TOOL> (e.g. ffmpeg CLI / a specific NLE script). Verifier tool: <VERIFIER_CMD> (e.g. `ffprobe -v error -show_entries format=duration:stream=r_frame_rate,avg_frame_rate -of json <file>` piped through a scene-detect script) — must be a DIFFERENT command/process than <EDIT_TOOL>, invoked fresh each turn, never asked "does this look right" of the editing model itself.

This goal does not change during the loop. If mid-loop you discover the spec itself is wrong or unsatisfiable, that is a BLOCKED condition — do not silently renegotiate the numbers.

BEFORE the loop starts — freeze the rubric in writing (do this once; nothing here may change during the loop):

A. Cut-matching algorithm (deterministic, order-preserving — replaces any ad hoc nearest-neighbor/positional guess):
   - Sort actual_cut_timestamps_sec and TARGET_CUT_TIMESTAMPS_SEC ascending (defensively; they should already be).
   - Align them with an order-preserving sequence-alignment DP (Needleman-Wunsch-style edit distance over the two ordered lists) — not nearest-neighbor, not index-position matching:
     - match(actual_i, target_j) is only a legal DP transition if |actual_i - target_j| / CUT_TOLERANCE_SEC <= 1.0; its cost is that ratio. Pairs further apart than tolerance can never be matched to each other.
     - skip-target (a target with no corresponding detected cut = "missing") costs <CUT_PENALTY_WEIGHT> (suggest 1.0).
     - skip-actual (a detected cut with no corresponding target = "extra"/spurious) costs <CUT_PENALTY_WEIGHT> (same constant).
     - the alignment is whichever legal path through the DP grid has minimum total cost, preserving the original temporal order of both lists (no reordering allowed). This is a mechanical optimization with a unique optimal total cost, so any correct implementation reproduces the same error_score for the same two lists.
     - Tie-break (for determinism of WHICH pair gets picked when several alignments share the minimum cost, since that choice feeds step 2 below): prefer matching each target to the earliest eligible actual cut (leftmost DP tie-break).
   - Output: matched_pairs = [(actual_i, target_j, normalized_cost), ...], missing_count, extra_count. Everywhere below, "matched cuts" and "missing/extra cut penalty" refer only to this routine's output.

B. Normalized error_score (every term is dimensionless — expressed as a multiple of its own tolerance — so they are comparable and summable regardless of underlying units):
   error_score =
       |actual_duration_sec - TARGET_DURATION_SEC| / DURATION_TOLERANCE_SEC
     + sum(normalized_cost for each pair in matched_pairs)          # already /CUT_TOLERANCE_SEC per (A)
     + (missing_count + extra_count) * <CUT_PENALTY_WEIGHT>
     + |actual_fps - TARGET_FPS| / FPS_TOLERANCE                    # actual_fps per (C) below
   "Target the single largest contributor" means: whichever individual term — the duration term, one specific matched-cut's normalized_cost, the missing/extra penalty as a whole, or the fps term — has the highest value among all of them. Because every term is on the same "1.0 = exactly at its tolerance boundary" scale, this comparison is now well-defined and reproducible, independent of the arbitrary original units (seconds vs. fps).

C. Frozen measurement rules (resolves the ffprobe r_frame_rate vs. avg_frame_rate ambiguity):
   - Authoritative fps field: avg_frame_rate (total frames ÷ total container duration). This is the value used everywhere above as actual_fps — never r_frame_rate.
   - CFR/VFR determination: record both r_frame_rate and avg_frame_rate every turn. If they're equal within 1e-3 fps, the output is constant-frame-rate (CFR) and actual_fps must equal TARGET_FPS exactly (no FPS_TOLERANCE). If they differ, the output is variable-frame-rate (VFR); apply FPS_TOLERANCE against avg_frame_rate, and record is_vfr = true in carry-forward state so this never gets re-litigated mid-loop.

D. Cut-detectability pre-flight (surfaces the hidden scene-detector assumption instead of leaving it implicit):
   - State the assumption explicitly, in writing, before turn 1: every timestamp in TARGET_CUT_TIMESTAMPS_SEC is assumed to be a hard cut or a transition visible to <VERIFIER_CMD>'s scene-detect stage at its tuned sensitivity — not a gradual dissolve/fade/whip-pan, and not a cut between two near-identical static shots that a content-detector could plausibly treat as continuity.
   - Validate this once, before turn 1: run <VERIFIER_CMD>'s scene-detect stage against the raw source material (or the first-pass render) and confirm it surfaces a candidate discontinuity within a wide pre-flight window (± 2×CUT_TOLERANCE_SEC) of every target timestamp.
   - Any target cut with no detector-visible discontinuity at pre-flight is BLOCKED immediately — do not enter the per-turn loop hoping a later edit fixes detectability. Report which timestamp(s) failed and why (e.g. "target cut at 12.4s falls inside a 1.5s cross-dissolve; the detector cannot resolve a discrete cut there").

E. Verifier integrity lock (closes the loophole where the agent "fixes" a failing render by loosening the verifier instead):
   - Before turn 1, compute a checksum (e.g. sha256) over every file that constitutes <VERIFIER_CMD> — its script(s), config, and all tunable thresholds (scene-detector sensitivity, CUT_TOLERANCE_SEC, DURATION_TOLERANCE_SEC, FPS_TOLERANCE, <CUT_PENALTY_WEIGHT>). Record it as verifier_checksum_frozen.
   - Re-check this checksum every turn, BEFORE trusting that turn's verifier output.
   - The agent may never edit the verifier's script, config, or thresholds for the duration of the loop, for any reason — including "the tolerance seems too strict." A checksum mismatch is an automatic BLOCKED: halt, report exactly which file(s) changed, and do not resume until a human confirms the change was intentional and re-freezes a new checksum.

PER-TURN SHAPE:
1. ASSESS — first re-check the verifier checksum against verifier_checksum_frozen (E); if it fails, stop right here and go to BLOCKED. Otherwise run <VERIFIER_CMD> against the current state of <OUTPUT_PATH> (or, on turn 1, a first-pass render): record actual_duration_sec, actual_cut_timestamps_sec, actual_r_fps, actual_avg_fps (C). Run the cut-matching routine (A) and compute error_score (B).
2. ONE ACTION — make exactly one reversible edit that targets the single largest normalized contributor to error_score, per (B) — e.g. trim/extend the matched cut with the highest normalized_cost, adjust speed/retime one segment, change the output fps flag, or fix a missing/extra cut. Do not batch multiple fixes in one turn. Save the previous render (or its edit-decision-list) before overwriting, so the action can be undone.
3. VERIFY — re-check the verifier checksum, then re-run <VERIFIER_CMD> (same independent command as step 1) against the new render only. Never accept the editing tool's own log/exit-code as proof of correctness — only the verifier's fresh, checksum-confirmed measurement counts.
4. DECIDE — compare new error_score to previous; update carry-forward state; check the four stop arms in this exact order — SUCCESS, then BLOCKED, then NO-PROGRESS, then BUDGET — and act on the first one that's true. (This order is identical to the STOP block below; the two must never be allowed to drift apart again.)

CARRY-FORWARD STATE (compact, pass forward each turn):
``​`
iteration: <n>
last_error_score: <float>                      # normalized per (B)
error_history: [<up to last 4 error_scores>]
actual_duration_sec: <float>
actual_cut_timestamps_sec: [<list>]
matched_pairs / missing_count / extra_count: <output of (A) this turn>
actual_avg_fps: <float>
actual_r_fps: <float>
is_vfr: <bool>                                  # r_frame_rate != avg_frame_rate, per (C)
verifier_checksum_ok: <bool>
last_action_taken: <one-line description>
last_action_target: <which cut/segment/param it touched>
actions_tried_this_target: [<list of prior fixes tried on the same cut/param, to ban verbatim repeats>]
``​`

RULES:
- One reversible action per turn, then verify. Never chain edit -> edit -> verify.
- Never repeat the exact same action verbatim (check actions_tried_this_target before acting).
- Never oscillate: if the last two actions on the same target moved the parameter in opposite directions with no net error_score improvement (A->B->A pattern), that counts toward NO-PROGRESS.
- Verifier independence is non-negotiable: the script/command that measures duration/cuts/fps must never be the render tool itself, must never accept "looks about right," must be re-invoked fresh (not cached) every turn, and — per (E) — must never be edited mid-loop. A checksum mismatch is an automatic BLOCKED no matter how good the reported numbers look.
- The cut-matching algorithm (A), the error_score formula (B), the fps authoritative-field/CFR rule (C), the detectability assumption (D), and every threshold are frozen before turn 1 and apply unmodified for the rest of the loop — see (E) for enforcement.
- Before any irreversible action — deleting source footage, overwriting the only copy of a prior good render, or triggering a paid render/API call — stop and get explicit human confirmation first, even mid-budget.

STOP — halt on the FIRST of, checked in this exact order (identical to PER-TURN SHAPE step 4):
- SUCCESS: all three deterministic checks pass simultaneously on the latest verifier run against <OUTPUT_PATH>: |actual_duration_sec - TARGET_DURATION_SEC| <= DURATION_TOLERANCE_SEC; the (A) alignment has missing_count == 0, extra_count == 0, and every matched pair's raw (non-normalized) delta <= CUT_TOLERANCE_SEC; and the (C) fps check passes (exact vs. avg_frame_rate if CFR, within FPS_TOLERANCE of avg_frame_rate if VFR). Report final measured values (both fps fields, full matched cut list) alongside spec.
- BLOCKED: verifier checksum mismatch (E); source too short/long for target even at edit limits; a target cut fails the (D) detectability pre-flight; spec cut count exceeds detectable scene changes; <EDIT_TOOL> or <VERIFIER_CMD> errors or is missing; or the needed decision requires human judgment (e.g. picking among equally-valid takes). Report the exact blocking fact — do not guess or retry past it.
- NO-PROGRESS: normalized error_score fails to improve by >= <MIN_IMPROVEMENT_PCT> (suggest 5%) for <K> (suggest 3) consecutive turns, or a verbatim retry / A->B->A oscillation is detected. Report the plateaued state and what was tried.
- BUDGET: iteration count reaches <MAX_ITERATIONS> (suggest 8) without SUCCESS. Report best error_score achieved and remaining per-term deltas.
```
