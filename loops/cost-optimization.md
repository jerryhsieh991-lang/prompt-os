# Cost Optimization

`cost-optimization` — 2 loop prompts.

### 1. Cloud Workload Cost Reduction Under a Frozen SLO

- **When:** Reducing the measured dollar cost of a running cloud workload (compute/storage/egress) while a frozen latency/error-rate/throughput SLO must keep holding on a representative scenario.
- **Loop:** assess biggest cost line vs SLO headroom -> apply ONE reversible cost lever -> replay frozen scenario, read cost meter + SLO check -> commit if cost down AND SLO held else revert -> decide
- **Stop:** SUCCESS: metered spend <= target with SLO held on a clean replay · BUDGET: `<N>` turns or `<cost/wall-clock cap>` · NO-PROGRESS: metered cost flat for `<K>` turns despite changing lever type · BLOCKED: only remaining levers are irreversible/production-affecting and need a human gate
- **Model:** The verifier is a billing/metering meter plus a load-test/SLO harness, never the agent's own reasoning — an agent that concludes "this config is cheaper and still fast" routinely misses egress, IOPS, cross-AZ, or cold-start cost the change shifts elsewhere, so trust only the metered bill and the measured SLO, not a console price sticker. The dual gate is non-negotiable: metered cost must drop AND every SLO metric must hold on the SAME run — a cheaper config that breaches latency is a revert, not a tradeoff, and the two are never averaged. A cheaper/faster model can drive the assess/one-lever iteration since the meters do the grading; reserve human judgment for the irreversible-lever gate.

```text
GOAL (frozen — do not redefine mid-loop)
Cut the measured cost of <WORKLOAD> from baseline <$BASELINE per DAY/MONTH/1K-REQ> to <= <$TARGET>, measured by <COST_METER e.g. billing export / Cost Explorer / Kubecost / CUR report> over the frozen representative scenario <SCENARIO e.g. a replayed production traffic window or fixed load-test profile>, WHILE the frozen SLO holds: p95 latency <= <L ms> AND error rate <= <E%> AND throughput >= <T rps>. Freeze $TARGET, the SLO thresholds, and the scenario before turn 1; never relax the SLO or shrink the scenario to make the number move.

INDEPENDENT VERIFIER
Two gates, both measured, never averaged: (a) the cost meter — actual metered spend from <COST_METER>, read AFTER the change settles over <a full billing/metering window> on the SAME frozen scenario, never a console/napkin price estimate or a projected saving; (b) the SLO check — <load-test harness / SLO dashboard / synthetic probe> reporting measured p95, error rate, and throughput on that same replay. A change counts only if the meter shows spend actually dropped AND every SLO metric is still within bound on the same run. An estimated saving and "this instance is cheaper on paper" are not proof — right-sizing can blow latency, a cheaper storage tier can raise egress or IOPS spend elsewhere; only the metered bill after the fact settles it.

PER-TURN SHAPE
1. ASSESS — from the cost meter, pick the single largest cost line that has SLO headroom to give back (e.g. an over-provisioned instance, hot data on premium storage, always-on capacity idling).
2. ONE ACTION — apply exactly ONE reversible lever: right-size one instance/pod, add or resize a cache, move one dataset to a cheaper storage tier, adjust one autoscaling policy, or shift eligible capacity to spot/committed-use — nothing irreversible, nothing bundled.
3. VERIFY — replay the frozen scenario; read the cost meter over a full metering window AND run the SLO check on the same run.
4. DECIDE — commit only if metered cost dropped AND every SLO metric held; otherwise revert the change; park any lever needing an irreversible/production-affecting step behind a human gate; escalate if the same cost line resists 3 different levers.

CARRY-FORWARD STATE (compact)
Goal ($TARGET + frozen SLO thresholds + scenario), current metered cost and current p95/error/throughput, levers tried with measured cost delta and SLO effect, reverts/dead-ends, remaining budget.

ACTION BAN
Never accept an estimated/unmetered saving as done — wait for the meter to settle. Never let any SLO metric cross its bound to bank a saving (no averaging a latency regression against a cost win). Never shrink, shorten, or soften the scenario or the SLO to make the meter look better (Goodhart). Never bundle multiple levers in one turn. Never flip an irreversible or production-affecting switch — delete data, drop a replica, terminate reserved capacity, mutate prod config — without an explicit human gate.

STOP — halt on the FIRST of:
SUCCESS (metered spend <= $TARGET AND all SLO metrics within bound on a clean replay) | BUDGET (<N> turns or <cost/wall-clock cap> reached) | NO-PROGRESS (metered cost flat within <±X%> for <K> turns despite changing lever type — rethink, don't retry the same lever) | BLOCKED (only remaining levers are irreversible/production-affecting, or the cost meter/SLO harness is unavailable — escalate to a human gate, don't guess).
```

### 2. LLM/API Pipeline Cost Reduction Under a Frozen Quality Bar

- **When:** Cutting the token/API dollar cost of an LLM pipeline (model routing, prompt/context trimming, caching, batching) while a frozen quality eval must stay at or above its threshold on a fixed scenario.
- **Loop:** assess costliest stage vs quality headroom -> apply ONE reversible cost lever -> replay frozen eval set, read token/$ meter + quality eval -> commit if cost down AND quality >= bar else revert -> decide
- **Stop:** SUCCESS: metered $/run <= target with quality >= bar on a clean eval run · BUDGET: `<N>` turns or `<cost cap>` · NO-PROGRESS: metered cost flat for `<K>` turns despite changing lever type · BLOCKED: every remaining lever drops quality below the bar, or a gold item/eval/judge looks broken
- **Model:** The cost meter is real token accounting from the API/usage log and the quality gate is a FIXED eval harness — a scoring script or a pinned judge model distinct from every tier the pipeline routes to — because a cheaper tier that grades its own output will always look fine (shared blind spots) and Goodharts the check. Dual gate: metered $ must drop AND the eval score must stay >= bar on the SAME frozen eval set; never average a quality drop against a cost win, and never subsample the eval set or weaken the judge to make the meter look better. Keep the judge pinned and separate from every routed tier so tier swaps stay apples-to-apples; the pipeline model itself may be cheap while iterating since the meter and judge do the grading.

```text
GOAL (frozen — do not redefine mid-loop)
Cut the measured cost of <PIPELINE> from baseline <$BASELINE per 1K-REQ / per RUN> to <= <$TARGET>, measured by <COST_METER e.g. provider usage/billing log, or a token-accounting counter summing prompt+completion tokens × per-model price + tool/API call fees> over the frozen eval scenario <EVAL_SET — a fixed set of N representative requests>, WHILE quality — scored by the frozen eval harness <EVAL e.g. task accuracy / F1 / rubric-judge score> — stays >= <QUALITY_BAR>. Freeze $TARGET, the quality bar, the eval set, AND the judge/scorer config before turn 1; never lower the bar or trim the eval set to move the number.

INDEPENDENT VERIFIER
Two gates, both measured on the SAME frozen eval set, never averaged: (a) the cost meter — actual metered token/API spend from <COST_METER> for the run, not an estimate of "cheaper model ≈ X% less"; (b) the quality eval — <fixed scoring script or a pinned judge model distinct from every model the pipeline routes to> reporting the score, never the pipeline's own model grading its own output. A change counts only if metered $ actually dropped AND the eval score is still >= <QUALITY_BAR> on that run. Why measured, not estimated: a cheaper model can inflate output tokens or trigger more retries so cost doesn't fall as predicted, and prompt/context trimming can quietly push quality under the bar — only the real usage log and the fixed eval settle both.

PER-TURN SHAPE
1. ASSESS — from the cost meter, pick the single costliest stage that has quality headroom (e.g. a high-token step on the top tier, a fat few-shot/context block, an uncached repeated call).
2. ONE ACTION — apply exactly ONE reversible lever: route one stage/request-class to a cheaper model tier, trim prompt/context (drop redundant few-shots, compress instructions), add a cache for repeated calls, or batch eligible requests — one lever, reversible, nothing bundled.
3. VERIFY — replay the frozen eval set; read the token/$ meter for the run AND run the fixed quality eval on the same outputs.
4. DECIDE — commit only if metered cost dropped AND eval score held >= bar; otherwise revert; if quality only holds by variance, re-run to confirm before committing/parking; escalate if every remaining lever pushes quality below the bar.

CARRY-FORWARD STATE (compact)
Goal ($TARGET + quality bar + frozen eval set + judge config), current metered $/run and current eval score, levers tried with measured cost delta and quality effect, reverts/dead-ends, remaining budget.

ACTION BAN
Never accept an estimated (unmetered) saving — read the usage log. Never trade quality below <QUALITY_BAR> to save money (no averaging a score drop against a cost win). Never shrink, subsample, or swap the eval set, and never weaken or swap the judge, to make the meter look better (Goodharting the cost meter). Never let the routed model grade its own quality. Never bundle multiple levers per turn. Never chase cost by adding retries/verbosity that quietly re-inflate tokens.

STOP — halt on the FIRST of:
SUCCESS (metered $/run <= $TARGET AND eval score >= QUALITY_BAR on a clean run) | BUDGET (<N> turns or <cost cap> reached) | NO-PROGRESS (metered cost flat within <±X%> for <K> turns despite changing lever type — switch lever category or halt, don't re-tweak the same one) | BLOCKED (every remaining lever drops quality below the bar, or a gold item / eval / judge looks broken — escalate, don't lower the bar or edit the eval).
```
