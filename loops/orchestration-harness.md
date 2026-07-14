# Orchestration Harness (Fan-out / Pipeline)

`orchestration-harness` — 8 loop prompts.

### 1. 扇出式研究综合(Fan-Out Research Synthesis)

- **When:** 需要就一个开放性研究问题从多个独立信源收集、交叉核实并综合出一份有据可查的报告时使用;适合竞品情报、文献综述、事实核查类任务。研究类循环把'停滞'定义为证据饱和('dry'),而不是固定轮数。
- **Loop:** 扇出(fan-out):主控拆出待研究子问题清单 → 每回合派1个子智能体研究1个子问题,或把1条已产出的论断单独提交给独立核实者 → 只有通过核实的论断才进入综合报告。
- **Stop:** SUCCESS — 所有子问题闭环、所有论断通过独立核实,综合体产出报告 · BUDGET — 达到子智能体派发次数(如25次)或墙钟时间上限(如60分钟) · NO-PROGRESS('枯竭')— 连续3轮未新增被接受的论断或新信源 · BLOCKED — 某子问题依赖付费墙/不可获取的数据源,停止并说明缺口
- **Model:** 研究子智能体(搜索/摘要)可用较便宜的模型(如 Sonnet/Haiku)大批量跑;独立核实者与最终综合体建议升级到更强模型(Opus 或 Fable 5),因为跨信源交叉核验和识别隐含矛盾更依赖推理深度,弱模型容易被表面一致的信源蒙混过关。

```text
GOAL (frozen): answer the research question [QUESTION]. Success = a synthesis where every load-bearing claim is corroborated by 2+ independent sources and zero verifier-flagged claims remain. Fix this bar now; do not loosen it later.

Maintain a compact scratchpad: claims table (claim / sources / status), open sub-questions, last verifier verdict, turns used.

Each turn: (1) Assess the scratchpad against the goal. (2) Act — dispatch ONE sub-agent to research exactly one open sub-question, OR send ONE existing claim to the verifier. Never both. (3) Verify — a separate verifier agent (not the researcher) checks the claim against sources it independently pulls, returning ACCEPT / REJECT / UNCERTAIN only. (4) Decide — update the scratchpad, pick the next single action.

STOP on whichever trips first:
SUCCESS — no open sub-questions, all claims ACCEPT, synthesizer emits the report.
BUDGET — 25 sub-agent dispatches or 60 min reached.
NO-PROGRESS ("dry") — 3 straight turns add zero newly-accepted claims or new sources.
BLOCKED — a sub-question needs paywalled/inaccessible data; halt and name exactly what's missing.
Never verify a claim with the same source that produced it.
```

### 2. 代码库级 API 迁移扇出(Codebase Migration Fan-Out)

- **When:** 需要把整个代码库中匹配某模式的所有文件从旧 API/框架迁移到新 API,且每一步都必须可编译、可独立回滚时使用。
- **Loop:** 扇出+归并:冻结待迁移文件清单 → 每回合派1个子智能体只改1个文件 → 独立构建+测试作裁判 → 通过则提交,失败则 git revert 并换策略重试 → 全部完成后合并为单个 PR。
- **Stop:** SUCCESS — 清单清空、全量测试绿、产出单个 PR · BUDGET — 尝试次数达到文件数的2倍 · NO-PROGRESS — 同一文件连续失败3次 · BLOCKED — 某文件依赖尚未发布的新 API,需人工排期
- **Model:** 单文件迁移多是机械替换,Sonnet 级别足够且成本更低;当'同一文件连续失败3次'触发 NO-PROGRESS 后若需要人工判断更换迁移策略,可把那一次的策略决策升级给更强模型(Opus/Fable 5)处理,而不是整条流水线都用强模型。

```text
GOAL (frozen): migrate every file matching [PATTERN] from [OLD_API] to [NEW_API]. Success = repo builds clean, full test suite green, zero remaining references to [OLD_API].

Split the file list into a fixed worklist up front; freeze it — no files added mid-run beyond that list.

Each turn: (1) Assess worklist state (done / failing / untouched) and remaining budget. (2) Act — dispatch ONE fresh sub-agent to migrate exactly ONE untouched or previously-failing file; it edits only that file. (3) Verify — an independent step (not the migrating agent) runs the build + that file's tests; pass/fail only, no self-report. (4) Decide — on pass, commit and mark file done; on fail, git-revert that file's change and log the failure reason, then choose a different approach next turn — never retry the identical diff.

STOP on first trip: SUCCESS — worklist empty, full suite green, synthesizer opens one PR. BUDGET — worklist length x2 attempts exhausted. NO-PROGRESS — same file fails 3 times running. BLOCKED — a file needs an API not yet released; halt and list it for a human.
```

### 3. 多阶段内容生产流水线(Draft→Fact-check→Edit→Format Pipeline)

- **When:** 内容需要经过起草、事实核查、编辑、排版等多个严格顺序阶段,且每个阶段必须由独立角色把关时使用,适合长文、报告、发布物的生产。
- **Loop:** 流水线(pipeline):四阶段严格接力,每阶段只接收上一阶段的产出与冻结的评分标准 → 每回合推进1个阶段的1次动作,由该阶段专属的独立检查者验收 → 未过则打回上一阶段并携带具体缺陷。
- **Stop:** SUCCESS — 同一轮内四阶段全部通过评分标准 · BUDGET — 累计阶段推进次数达到12次 · NO-PROGRESS — 同一缺陷在2次修复后仍复现 · BLOCKED — 事实核查需要无法访问的信源
- **Model:** 起草阶段可用较有创意/较便宜的模型;事实核查与编辑阶段建议用更强、指令遵循更严格的模型(Opus/Fable 5),因为这两阶段的漏检成本最高,而排版阶段基本机械化,便宜模型即可。

```text
GOAL (frozen): produce a publish-ready piece on [TOPIC] meeting the fixed rubric: factually accurate, matches style guide, passes plagiarism/originality check, reading level in range. Freeze the rubric before turn 1.

Pipeline stages run in strict order, one active hand-off at a time: Draft -> Fact-check -> Edit -> Format. Each stage is a distinct agent that receives ONLY the prior stage's output plus the frozen rubric — never the full history.

Each turn: (1) Assess which stage is active and its last verifier result. (2) Act — advance exactly one stage's work (one draft pass, one fact-check pass, etc.), one reversible edit. (3) Verify — a checker distinct from the stage's author role scores against the rubric (fact-check uses source lookup, not the drafter's confidence). (4) Decide — advance on pass, bounce back one stage on fail with the concrete defect, log it in the scratchpad.

STOP: SUCCESS — all four stages pass their checks in the same run. BUDGET — 12 stage-passes total. NO-PROGRESS — same defect recurs after 2 fix attempts (force a different fix strategy or stop). BLOCKED — fact-check needs a source outside your access.
```

### 4. 批量文档结构化抽取扇出(Bulk Document Extraction Fan-Out)

- **When:** 需要从大批量文档(合同、财报、PDF等)中按固定 schema 抽取结构化数据并生成可信数据集时使用。
- **Loop:** 扇出:冻结文件清单与 schema → 每回合派1个子智能体只抽取1份文档 → 独立校验器对照 schema 与原文核验 → 通过入库,拒绝则换策略重抽。
- **Stop:** SUCCESS — 清单中每份文档均已核验入库或记录为例外,零静默跳过 · BUDGET — 子智能体调用次数达文件数的1.5倍 · NO-PROGRESS — 同一文件连续2次被拒 · BLOCKED — 单文件不可读记为例外继续;若同时≥3份文件不可读视为系统性问题,整体暂停
- **Model:** 高吞吐、低复杂度的抽取任务,子智能体用 Haiku/Sonnet 即可大幅降低成本;仅当 schema 存在歧义(如自由文本条款、跨字段推断)时,把独立校验器升级到更强模型以减少漏判。

```text
GOAL (frozen): extract [SCHEMA] from every document in [DOCUMENT_SET] (N files) into one validated dataset. Success = 100% of files have a schema-valid record or an explicit documented exception; zero silent skips.

Freeze the schema and the file list before starting. Carry a compact ledger: file -> {pending, extracted, verified, exception}.

Each turn: (1) Assess the ledger and budget left. (2) Act — dispatch ONE sub-agent to extract structured fields from exactly ONE pending file. (3) Verify — an independent validator agent checks the extraction against the frozen schema (types, required fields, cross-field consistency) and against the source text; ACCEPT / REJECT-with-reason / UNPARSEABLE. (4) Decide — on ACCEPT, mark verified and append to the dataset; on REJECT, re-extract with a different strategy (different prompt framing or a targeted re-read), never the identical attempt.

STOP on first: SUCCESS — ledger has zero pending, every file verified or a logged exception. BUDGET — 1.5x N sub-agent calls. NO-PROGRESS — same file REJECTs twice running. BLOCKED — a file is corrupt/unreadable; log as exception and continue, but halt the whole run if 3+ files are simultaneously unreadable (systemic issue).
```

### 5. 覆盖率驱动的测试生成扇出(Coverage-Driven Test Generation Fan-Out)

- **When:** 需要把某模块的测试覆盖率从当前基线提升到目标阈值以上,且必须保持全量测试常绿时使用。
- **Loop:** 扇出:冻结未覆盖函数清单与覆盖率目标 → 每回合派1个子智能体只为1个函数写测试 → 独立运行覆盖率工具与全量测试作裁判 → 提升且绿灯则提交,回归则 revert。
- **Stop:** SUCCESS — 覆盖率≥目标且全量测试绿 · BUDGET — 清单耗尽或40轮 · NO-PROGRESS — 连续4轮覆盖率增量<0.5% · BLOCKED — 某函数缺少必要的 mock/fixture,标记后跳过
- **Model:** 写常规单测的子智能体用便宜模型即可;当覆盖率连续4轮停滞触发 NO-PROGRESS、需要换成 property-based 测试或重新设计可测性(如引入依赖注入)时,把'换策略'这一步升级给更强模型判断。

```text
GOAL (frozen): raise test coverage on [MODULE] from its current baseline to >= [TARGET]% as measured by [COVERAGE TOOL], with the full suite green. Freeze the target and tool now — don't switch coverage tools mid-run to chase a better number.

Scratchpad: coverage %, list of untested functions (frozen worklist), last 3 coverage deltas, budget used.

Each turn: (1) Assess current coverage % vs target and the delta trend. (2) Act — one sub-agent writes tests for exactly ONE untested function from the worklist; nothing else touched. (3) Verify — run the coverage tool + full suite as an independent process; record the new %. (4) Decide — if % rose and suite is green, commit; if suite broke, git-revert and log why; if % is flat, the function's tests were likely trivial — try a different function or a property-based approach next turn, not the same test again.

STOP: SUCCESS — coverage >= target and suite green. BUDGET — worklist exhausted or 40 turns. NO-PROGRESS — coverage delta <0.5% for 4 consecutive turns. BLOCKED — a function is untestable without a mock/fixture you don't have; flag it and move to the next.
```

### 6. 多语言本地化流水线(Localization Pipeline with Bilingual QA)

- **When:** 需要把内容翻译成多个语言版本,并要求每个语种都经过独立双语审校确认术语与语义忠实度时使用。
- **Loop:** 流水线+扇出混合:冻结语种清单与术语表 → 每回合派1个译者只译1个语种分片 → 独立双语审校核对忠实度与术语一致性 → 通过则锁定,未通过则针对被标记片段换措辞重译。
- **Stop:** SUCCESS — 所有语种均锁定/通过 · BUDGET — 审校轮次达语种数的2倍 · NO-PROGRESS — 同一语种同一片段连续3轮被标记 · BLOCKED — 术语表缺失必要术语,该语种暂停待补充,其余语种继续
- **Model:** 译者子智能体可用较快模型;双语审校建议用在该语种对上语感更强的模型,尤其是低资源语言对,可考虑升级到 Opus/Fable 5 或专门的翻译评测模型,弱模型容易漏判'流畅但走样'的翻译。

```text
GOAL (frozen): produce a QA-passing localization of [SOURCE CONTENT] into locales [LIST]. Success = every locale's translation passes the bilingual reviewer's fidelity + terminology check with zero open flags.

Freeze the locale list and the terminology glossary before turn 1; glossary changes mid-run are out of scope (park them).

Each turn: (1) Assess the per-locale status table (untranslated / translated / flagged / passed) and budget. (2) Act — dispatch ONE translator agent to fully translate exactly ONE locale chunk, using only the frozen glossary. (3) Verify — a separate bilingual reviewer agent (never the translator) checks fidelity, tone, and glossary adherence against the source; PASS or FLAG-with-specifics. (4) Decide — on PASS, lock that locale; on FLAG, re-translate only the flagged segments with a different phrasing approach, not a verbatim resubmission.

STOP: SUCCESS — every locale locked/PASS. BUDGET — 2x locale-count review rounds. NO-PROGRESS — same locale flagged 3 rounds running on the same segment. BLOCKED — glossary lacks a term needed for a locale; halt that locale and request the term, continue others.
```

### 7. 积压问题批量修复扇出(Backlog Bug-Bash Fan-Out)

- **When:** 需要在一个固定的 issue 清单上推进修复,且必须避免多个修复相互踩踏共享代码时使用,适合冲刺前的缺陷清理。
- **Loop:** 扇出:冻结 issue 清单 → 每回合派1个子智能体只处理1个 issue(复现→写回归测试→修复) → 独立重跑该测试+全量回归套件作裁判 → 通过提交关闭,失败 revert 换思路。
- **Stop:** SUCCESS — 清单中每个 issue 均已关闭或分诊 · BUDGET — 尝试次数达 issue 数的2倍 · NO-PROGRESS — 同一 issue 连续3次修复失败 · BLOCKED — 某 issue 需要产品/人工决策,记为 needs-human 并继续处理其余 issue
- **Model:** 常规缺陷修复用 Sonnet 级别足够;若某 issue 连续3次失败触发 NO-PROGRESS,往往意味着架构层面纠缠更深,把那个 issue 单独升级给更强模型(Opus/Fable 5)重新诊断,而不是提高整批的模型档位。

```text
GOAL (frozen): close backlog issues [ISSUE_LIST] (a fixed set, frozen now — no new issues admitted mid-run) such that each has either a merged fix with its regression test passing, or an explicit triage note (won't-fix / needs-human).

Scratchpad: per-issue status, shared-code touch log (to catch collisions), budget used.

Each turn: (1) Assess backlog status and which issues remain open. (2) Act — one sub-agent takes exactly ONE issue: reproduce it, write a failing test, then fix it — one issue's diff only, never bundled with another issue's fix. (3) Verify — independently rerun that issue's new test plus the full existing suite (regression check on shared code); pass/fail, not the fixing agent's opinion. (4) Decide — pass: commit and close; fail: git-revert, log the failure, next attempt must use a different fix approach.

STOP: SUCCESS — every issue closed or triaged. BUDGET — issue-count x2 attempts. NO-PROGRESS — same issue fails fix 3 times. BLOCKED — an issue needs a product/UX decision only a human can make; triage it as needs-human and continue the rest — don't stall the whole loop on one issue.
```

### 8. 多方案裁判团合成(Best-of-N Judge-Panel Synthesis)

- **When:** 需要针对同一任务并行生成多个差异化解法,再由独立裁判团按固定评分标准挑选或合并出最优解时使用,适合方案设计、架构选型、创意产出等有多解空间的任务。
- **Loop:** 扇出+裁判:一次性并行生成 K 个互不可见、策略各异的候选方案 → 每回合把1个未评分候选提交给独立裁判团评分 → 分数相近的候选可合并出新候选再评分。
- **Stop:** SUCCESS — 某候选(或合并候选)达标且无裁判重度异议 · BUDGET — K + 3 轮合并/追加评分 · NO-PROGRESS — 连续3轮最高分未提升 · BLOCKED — 裁判持续分裂且合并无法收敛,升级人工裁决
- **Model:** K 个方案生成体可以刻意混用不同模型/人设/温度以拉开策略差异(便宜模型也可参与,增加多样性);裁判团是整个循环的质量瓶颈,务必用可用的最强模型(Opus/Fable 5),弱模型当裁判会让整套选优机制失效。

```text
GOAL (frozen): produce the best solution to [TASK] from [K] independently-generated candidates, selected or merged against a rubric fixed before generation starts. Success = a candidate (or merge) that a separate judge panel scores >= [THRESHOLD] with no dissent below [MIN].

Fan out once: K solver agents each produce ONE full candidate independently (no cross-visibility) using genuinely different approaches — assign each a distinct strategy so this isn't K copies of the same idea.

Each subsequent turn: (1) Assess which candidates are scored vs unscored. (2) Act — send exactly ONE unscored candidate to the judge panel (2-3 judges distinct from every solver). (3) Verify — judges score independently against the frozen rubric, no averaging away a hard fail; report per-judge scores. (4) Decide — record scores in the scratchpad; if two candidates are close, spawn ONE merge attempt combining their strongest parts as a new candidate, then judge that.

STOP: SUCCESS — a candidate clears threshold with no judge dissent below min. BUDGET — K + 3 merge/extra rounds. NO-PROGRESS — best score hasn't improved across 3 judged rounds. BLOCKED — judges split irreconcilably (persistent tie with no merge improving it) — escalate to human for tiebreak.
```
