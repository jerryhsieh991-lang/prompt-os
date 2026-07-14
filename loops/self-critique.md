# Self-Critique (Draft → Critique → Revise)

`self-critique` — 8 loop prompts.

### 1. 技术文档修订循环(Technical Documentation Revision Loop)

- **When:** 发布前对 README、API 文档或运维手册按固定的清晰度与完整性量表进行修订,尤其适合'写完就该定稿'但又怕遗漏读者视角的场景。
- **Loop:** 草稿 → 切换到全新的'首次读者'视角批判(独立于起草时的思路)→ 针对最低分项做单点修订 → 重新打分 → 决定继续/停止。
- **Stop:** SUCCESS — 全部量表项 ≥4 分且无项 <3 分 · BUDGET — 已用满 6 轮修订 · NO-PROGRESS — 连续 2 轮总分持平或下降(须换修订策略而非重复同一修法) · BLOCKED — 量表判分所需信息(如未文档化的系统行为)缺失
- **Model:** 判据机械、任务边界清晰,Sonnet 5 级别模型即可稳定跑完循环;只有当文档涉及深层架构取舍判断(该不该这样设计,而不只是有没有写清楚)时,才值得把'单次动作'那一步换成更强模型。

```text
You are revising [DOCUMENT] against this frozen rubric, scored 1-5 per item, threshold: every item scores >=4 and no item scores below 3: (1) a first-time reader completes the task without outside help, (2) every claim matches actual system behavior, (3) no required section is missing, (4) length is no more than 20% over the minimum needed. Freeze this rubric now; do not add criteria mid-loop.

Each turn: state current per-item scores and the single lowest one from your scratchpad, make ONE targeted edit addressing only that item, then switch to a fresh 'first-time reader' frame and re-score all items independently of your drafting reasoning. Log round number, scores, what changed, and rounds left. Keep the previous version as fallback if a round scores worse than the last kept-good one.

Stop on whichever trips first: SUCCESS - threshold met; BUDGET - 6 rounds used; NO-PROGRESS - total score flat or worse for 2 rounds running, then change edit strategy rather than repeating the fix; BLOCKED - the rubric needs information you don't have. Park other improvement ideas in a backlog, not this draft.
```

### 2. 代码实现正确性 + 风格自我批判循环(Code Correctness & Style Loop)

- **When:** 针对已有测试套件和团队风格规范,实现单个函数/模块或修一个明确范围的 bug,需要机器裁决而非模型自读。
- **Loop:** 草稿代码 → 运行测试套件(机械独立验证者)→ 独立视角风格审查 → 单点修订 → 通过则 commit,退步则 revert。
- **Stop:** SUCCESS — 测试全部通过且风格量表判定 clean · BUDGET — 已用满 8 轮 · NO-PROGRESS — 连续 3 轮出现完全相同的测试失败(下一次必须换思路,不能重试同一改法) · BLOCKED — 规格模糊,或缺少测试夹具/依赖
- **Model:** 验证信号是硬性的(测试套件),循环控制部分用便宜模型就够;真正需要更强模型(Opus/Fable)的是'单次动作'里对并发、边界条件等复杂改法的设计判断,而不是循环本身。

```text
Implement [FUNCTION/MODULE] against this frozen spec: every test in [TEST_FILE] passes, plus a style rubric (readability, no duplicated logic, error handling matches project convention) scored pass/fail per item. This target is fixed at loop start; do not redefine 'done' later.

Each turn: check the scratchpad for current pass count and open style items, make ONE coherent code change, then run the test suite - the independent verifier, not your own read of the code. In a separate fresh-frame pass, check the style rubric. Update the scratchpad (round, tests passing/failing, style items open, budget left); commit if this round is no worse than the last kept-good state, otherwise revert to it.

Stop on the first tripped arm: SUCCESS - all tests pass and style rubric is clean; BUDGET - 8 rounds; NO-PROGRESS - identical test failures 3 rounds straight, meaning the next attempt must change approach, not retry; BLOCKED - the spec is ambiguous or a fixture/dependency is missing. Do not add features beyond the spec.
```

### 3. 营销/广告文案批判循环(Ad Copy Rubric + Compliance Loop)

- **When:** 生成广告标题/文案变体,交付前必须同时满足品牌语气量表和硬性合规清单(如广告法、平台政策)。
- **Loop:** 草稿一个变体 → 独立'评委'视角(未见过起草思路)对量表+合规清单打分 → 单点修订。
- **Stop:** SUCCESS — 量表均分≥4 且合规清单零失败 · BUDGET — 已用满 5 轮 · NO-PROGRESS — 连续 2 轮得分持平或下降(须换角度而非改措辞) · BLOCKED — 某条声明是否合规需要人工法务/品牌拍板
- **Model:** 创意锐度对模型能力敏感,建议起草与评委两个角色都用较强模型(Opus/Fable)以获得真正有区分度的批判;合规清单那部分纯机械核对,可以外包给便宜模型跑,不必占用高价模型的预算。

```text
Draft copy for [ASSET] against this frozen rubric, scored 1-5 per item, threshold average >=4 with zero items below 3: on-brand voice per [BRAND_GUIDE], one clear CTA, no unverifiable claims, fits the character limit. Compliance is checked separately, pass/fail, against [CLAIMS_CHECKLIST]; any fail blocks success regardless of rubric score.

Each turn: read the scratchpad (round, last scores, compliance flags, budget left), write or revise ONE variant only, then hand it to a separate judge frame that has not seen your drafting rationale - it scores fresh against rubric and checklist. Log its verdict verbatim; the drafter does not overrule the judge. Keep the last version that met or beat the current best score as fallback if a revision scores worse.

Halt on the first tripped condition: SUCCESS - threshold met and compliance clean; BUDGET - 5 rounds spent; NO-PROGRESS - score unchanged or worse for 2 straight rounds, so switch angle rather than reword the same line; BLOCKED - a compliance question needs a human legal or brand call. Keep scope to the one asset; do not spin off extra variants.
```

### 4. 研究摘要对抗性事实核查循环(Research Synthesis Fact-Check Loop)

- **When:** 将多篇资料整理成摘要报告,要求每条论断都可追溯到原文且不失真,常见于文献综述、竞品调研报告。
- **Loop:** 草稿摘要 → 对抗性事实核查(独立视角,专门找一条无法验证的论断)→ 增/删/改单条论断。
- **Stop:** SUCCESS — 未解决论断数为零 · BUDGET — 已用满 6 轮 · NO-PROGRESS — 连续 2 轮未解决论断数不变(须删掉该论断而非继续辩护) · BLOCKED — 某条论断所需来源不在给定资料集内
- **Model:** 对抗性核查是防止'自我打分'的关键一步——务必换用与草稿不同的模型,或至少完全独立的新对话帧,避免共享同一套盲点;来源本身信息密度高、需要精细比对时,核查阶段用更强模型收益明显。

```text
Synthesize [SOURCES] into a summary of [TOPIC]. Frozen exit criterion: every factual claim in the summary traces to a specific source passage, and no claim contradicts a source. This is checked by an adversarial fact-checking pass - a separate frame that actively tries to find one claim it cannot verify - not a repeat read by the drafter.

Each turn: the scratchpad shows current claim count, unresolved-claim count, and budget left; make ONE change - add, cite, cut, or correct a single claim; run the adversarial check against the source set only, since outside knowledge does not count as corroboration; update the unresolved count; if it rises, revert to the prior version rather than keep the regression.

Stop at the first tripped arm: SUCCESS - zero unresolved claims; BUDGET - 6 rounds; NO-PROGRESS - unresolved count unchanged for 2 rounds, meaning the next round must cut the claim rather than re-argue it; BLOCKED - a claim needs a source outside [SOURCES]. Do not add claims beyond what the sources actually support.
```

### 5. 结构化数据抽取 / Schema 校验循环(Extraction Validation Loop)

- **When:** 从非结构化文本(简历、发票、合同)中抽取字段填入固定 JSON schema,要求可机械验证而非模型自我判断'看起来对'。
- **Loop:** 草稿抽取 → schema 校验器(机械独立裁决)+ 3 个随机字段抽样核对 → 单点修订。
- **Stop:** SUCCESS — 校验通过且抽样核对无误 · BUDGET — 已用满 5 轮 · NO-PROGRESS — 连续 2 轮出现同一条校验错误(须换解析思路而非重复同一修法) · BLOCKED — 源文本确实缺少必填字段且无默认值可用
- **Model:** 验证信号纯机械(schema validator),这个循环本身适合便宜/快速模型(Haiku 级别)批量跑;只有源文本本身书写混乱、需要语义消歧时,才值得把抽取那一步换成更强模型。

```text
Extract [DATA] from [SOURCE_TEXT] into the frozen schema at [SCHEMA]. Done means the output validates against the schema mechanically, not by your judgment, and a spot-check of 3 random fields matches the source text exactly.

Each turn: the scratchpad states current validator errors and which spot-checked fields failed last round; fix ONE field or structural issue; run the schema validator so the machine decides pass/fail, then spot-check 3 fields against source; log results and update the scratchpad. If a fix introduces a new validator error, revert to the prior extraction rather than layer fixes.

Stop on whichever trips first: SUCCESS - validator passes and spot-check is clean; BUDGET - 5 rounds; NO-PROGRESS - the same validator error appears 2 rounds running, so try a different parsing approach rather than the same fix again; BLOCKED - the source text genuinely lacks a required field and no default is specified, so surface it instead of inventing a value. Do not add optional fields the schema doesn't require.
```

### 6. 翻译/本地化保真度循环(Translation Fidelity via Back-Translation)

- **When:** 翻译任务需要同时保证'意思没变'和'读起来自然',通过回译作为独立验证信号,而非依赖模型自称'翻译准确'。
- **Loop:** 草稿翻译 → 独立回译(看不到原文对照)+ 双语评审视角打流畅度分 → 单段修订。
- **Stop:** SUCCESS — 回译无语义漂移且流畅度≥4/5 · BUDGET — 已用满 5 轮 · NO-PROGRESS — 连续 2 轮被标记同一处漂移(须换表达策略而非换同义词) · BLOCKED — 原文存在习语或歧义,需要人工裁定意图
- **Model:** 回译这一步必须是真正独立的视角——同一模型执行时也要清空上下文,否则等于自我打分;资源允许时,流畅度评审换更强模型能识别更细微的'翻译腔',小语种或专业术语密集的文本尤其值得升级。

```text
Translate [SOURCE] from [LANG_A] to [LANG_B]. Frozen exit target: back-translating the draft to [LANG_A] preserves the original meaning with no material drift, and a native-fluency rubric (natural phrasing, correct register, no literal-translation artifacts) scores >=4/5. The back-translation is the independent verifier, produced fresh without the original source text visible side by side.

Each turn: the scratchpad lists the last drift flags and fluency score; revise ONE passage; back-translate that passage independently and compare meaning; score fluency in a separate reviewer frame; log results and budget left. If drift increases, revert to the prior passage instead of layering edits.

Stop on the first tripped arm: SUCCESS - no meaning drift and fluency threshold met; BUDGET - 5 rounds; NO-PROGRESS - the same drift flagged 2 rounds straight, so choose a different phrasing strategy, not a synonym swap; BLOCKED - an idiom or ambiguity needs a human call on intended meaning. Do not embellish beyond the source's content.
```

### 7. 客服回复起草循环(Support Reply Policy + Tone Loop)

- **When:** 起草客诉/工单回复,发送前必须同时通过硬性政策清单和语气/完整性量表,常见于人工审核前的客服助理场景。
- **Loop:** 草稿回复 → 政策清单机械核对 + 独立视角语气/完整性打分 → 单点修订。
- **Stop:** SUCCESS — 政策清单全过且量表≥4/5 · BUDGET — 已用满 4 轮 · NO-PROGRESS — 连续 2 轮同一清单项失败(须改实际内容而非改措辞) · BLOCKED — 解决工单需要草稿者没有的审批权限或账户访问权
- **Model:** 政策合规部分是规则化任务,便宜模型即可机械核对;共情语气与完整性判断更依赖模型的社交判断力,预算允许时把评审角色换成更强模型能更早抓住'听起来敷衍'的回复。

```text
Draft a reply to [TICKET] against this frozen bar: every item on [POLICY_CHECKLIST] passes, pass/fail with no exceptions, and a tone/completeness rubric (empathetic opening, resolves or clearly next-steps the issue, no promises outside policy) scores >=4/5 from a fresh reviewer frame that did not write the draft.

Each turn: the scratchpad shows last checklist failures and rubric score; make ONE revision targeting the worst failure; re-run the policy checklist mechanically, then have the separate reviewer frame re-score tone and completeness; log results and rounds remaining. If the rubric score drops, revert to the last version that passed the checklist rather than compound edits.

Stop on the first arm that trips: SUCCESS - checklist clean and rubric met; BUDGET - 4 rounds; NO-PROGRESS - the same checklist item fails 2 rounds running, so change the actual offer or wording, not just phrasing; BLOCKED - resolving the ticket needs an approval or account access the drafter lacks, so escalate rather than guess. Do not add commitments beyond what the ticket requires.
```

### 8. 演示文稿叙事结构批判循环(Presentation Narrative Loop)

- **When:** 正式做幻灯片之前,先打磨演示大纲的叙事结构是否契合目标受众和时长,避免'内容都对但讲不通'。
- **Loop:** 草稿大纲 → 切换到'从未看过'的受众视角重新打分 → 单点重构一个章节或一处过渡。
- **Stop:** SUCCESS — 全部量表项≥4 · BUDGET — 已用满 5 轮 · NO-PROGRESS — 连续 2 轮最低分项分数不变(须重构该章节而非改措辞) · BLOCKED — 判断契合度所需的受众画像或时长信息尚未提供
- **Model:** 叙事结构好不好是高度主观的创意判断,建议评委视角用更强模型(Opus/Fable),它更擅长识别'看似逻辑通顺实则空洞'的论证结构——这正是弱模型容易漏判、反而给出虚高分数的地方。

```text
Outline [PRESENTATION] for [AUDIENCE] against this frozen rubric, scored 1-5 per item, threshold all items >=4: opens with the stakes or hook, carries one throughline argument rather than three, each section earns its slide time, ends with a specific ask. Freeze this list now.

Each turn: the scratchpad shows current per-item scores and the lowest one; revise ONE section or restructure ONE transition, not the whole outline; switch to an 'audience member who has never seen this' frame and re-score all items fresh; log scores, what changed, and budget left. If restructuring drops another item's score, revert that change rather than carry two regressions forward.

Stop at the first tripped condition: SUCCESS - every item >=4; BUDGET - 5 rounds; NO-PROGRESS - the lowest item's score unchanged for 2 rounds running, so restructure that section instead of rewording it; BLOCKED - judging fit needs audience or time-limit information not yet provided. Keep slide count and topic frozen; new content ideas go to a backlog, not this outline.
```
