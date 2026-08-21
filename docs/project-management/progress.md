# 项目进度

## 当前状态

- 当前任务：`F-005 外部服务韧性、数据时效与 Agent 评估`
- 任务状态：`ACTIVE`
- 最近完成：`Step 8 - 全量门禁与 stacked PR`，状态 `DONE`
- 当前 Step：`Step 9 - 依序合并与归档`，状态 `TODO`；尚未批准、尚未进入
- 当前分支：`feat/f-005-ui-delivery`
- 当前交付动作：五层 Draft stacked PR 与逐层 CI 已完成；停止在 merge、clean-restack、最终 main CI 与归档之前

## Step 0 完成摘要

- 2026-08-21 复核本地 `HEAD/main/origin/main` 与 GitHub remote main 均为 `c5f07e12abdc37f977ee0f7181a5f2800f015066`，修改前工作区干净；
- PR #19/#23/#24/#25/#26 均为 `MERGED`，PR #26 merge commit 为 `c5f07e1`，当前无开放 PR；
- main CI run `32386260285` 在 `c5f07e1` 上 `completed/success`；
- 激活前 current-task 明确没有活动任务；F-005 现为 roadmap 唯一 ACTIVE，后续顺序保持 F-005 → F-004B2；
- 完整已批准任务卡、D-014、Step 0–9、核心文件清单、受控相邻扩展、四层 stacked PR 和规模阈值已写入当前权威文档；
- F-004B1 当前状态已收口为 Step 0–8 完成归档、PR #26 已合并、最终 main/CI 为 `c5f07e1` / `32386260285`；历史 evidence 和归档任务卡未改写；
- 已从干净 main 创建本地首层分支 `feat/f-005-resilience-domain-contracts`；
- 本 Step 未修改生产源码、测试、fixture、Schema、migration、依赖、lockfile 或数据库；未读取 `.env.local`、秘密或本地 Provider 配置，未调用 DeepSeek、高德、和风或城际 Provider；
- 未 commit、push、创建 PR、触发远程 CI 或进入 Step 1。

## Step 1 完成摘要

- 逐能力冻结失败终态：Provider failure 不产生 needs_input/conflict；城市/地点/路线/天气/模型按关键性在 retry 耗尽后进入 failed 或 partial，ready 不容纳 stale/参与决策的未验证事实；
- freshness 冻结为 attempt 评估快照，GET 不按墙钟重写；stale 最终路线被拒绝，天气/预警被剔除，unknown-validity 保持披露且最高 partial；
- attempt runtime 冻结为每个 planning attempt 显式创建，额外预算为 Amap 3/QWeather 1/任务 4，timeout/5xx 使用 0–200ms jitter，受控 429 delay 最多 2 秒；terminal/cancel/deadline 后零新调用并 drain peers；
- generation/repair 输入、Provider 文本隔离、48-case 四 slice、两次确定性运行、五类硬门禁和 95% 加权门禁已冻结；
- API/UI 复用既有 URI、shape、`data_stale` 和 `diagnostic_code`；Stack 3 负责后端投影和 Agent 输入安全，Step 8 新增 Stack 4 只负责真实离线 application eval 集成，Stack 5 只消费既有 shape；五层核心文件和分层测试入口已对齐；
- 本 Step 只修改批准文档，没有修改生产源码、测试、fixture、Schema、migration、依赖、lockfile 或数据库；没有秘密读取、Provider/外部调用、commit、push、PR、CI 或进入 Step 2。

## Step 2 完成摘要

- RED 首次定向运行在 collection 阶段因新的 F-005 领域符号不存在失败；最小 GREEN 后定向 `108 passed`；
- `ProviderError` 只接受 rate-limit 的 `0..2s` 安全 Retry-After；纯 schedule 锁定 Amap/QWeather 2 attempts、额外预算 3/1/任务 4、6 秒 timeout，DeepSeek 1 attempt/35 秒/0 retry；
- retry 决策覆盖 timeout/server/受控 429、0–200ms jitter、budget、remaining deadline、terminal/cancelled；不可重试类别和 Provider/operation mismatch fail closed；
- freshness 决策覆盖 route stale reject、weather/alert stale omit、location stale partial-use、unknown-validity partial-use；Provider failure 只产生 failed/partial；安全诊断保持 8 项闭集；
- domain + contracts/golden `342 passed`，全 backend Ruff format/lint 与 strict mypy 134 files 通过；unknown/null、legacy/V2/V3 shape 和 domain dependency boundary 保持；
- 生产/测试只涉及 5 个批准文件、净新增 856 行且无未预期文件；没有 adapter/application/API/Repository/SQLite/前端、Schema/migration、依赖/lockfile、数据库、秘密、Provider/外部调用、commit、push、PR、CI 或 Step 3 实现。

## Step 3 完成摘要

- RED 首次定向运行因 `ProviderAttemptRuntime` 尚不存在而在 collection 失败；最小 GREEN 后 runtime + Amap/QWeather 定向 `121 passed`；
- 显式 task-scoped runtime 独立持有 attempt 记录、Amap/QWeather/任务额外预算、deadline、active peers 与 closed 状态；覆盖单 attempt timeout、注入式 jitter/sleeper、budget/deadline 停止、取消/异常 close、peer drain 和 closed 后零新调用；
- Amap/QWeather adapter 仍只执行一次 HTTP exchange，无内部 sleep/retry；timeout/request/HTTP/Schema 错误和 Retry-After 只投影为闭集安全错误与 `0..2s` 数值，不保留原始 header/body；DeepSeek 生产代码未修改，0 transport retry 回归通过；
- Provider/DeepSeek/治理/既有编排兼容回归 `378 passed`，domain/contracts `164 passed`；全 backend Ruff format/lint 与 strict mypy 136 files 通过；
- 生产/测试范围为 8 个批准核心或受控相邻文件、净新增 859 行、未预期文件 0；没有接入 application planning service，没有 API/Repository/SQLite/前端、Schema/migration、依赖/lockfile、数据库、秘密、Provider/外部调用、commit、push、PR、CI 或 Step 4 实现。

## Step 4 完成摘要

- RED 首次以 4 个接线测试证明 legacy/V2/V3 orchestrator/executor 不接受显式 runtime；第二个 RED 证明 stale weather 仍会进入 plan；随后完成最小 application 接线和同 shape 投影；
- executor 为每次 planning attempt 创建并持有一个 runtime，终态写 Repository 前 close；同一 runtime 覆盖 Amap/QWeather/DeepSeek、城市、路线与天气调用，logical call 与 HTTP attempt 计数保持分离；
- deadline 前置拒绝不启动 HTTP，timeout/retry budget 只输出既有错误 shape 和安全 diagnostic；城市/路线并发异常或取消均 cancel/drain peers，终态 active execution 为 0；
- retry 先于 deterministic route fallback；Provider-wide failure 与 stale route 均不 fallback。stale route failed，stale weather/alert 剔除并 partial，unknown-validity 不提升 ready；
- legacy/V2/V3 API URI/JSON keys、Repository typed union、SQLite schema v2、migration、F-003 replan 和 F-004B1 城际 Provider 调用 0 均未改变；
- 定向 runtime/application `60 passed`，全 backend `1264 passed`；Ruff format/lint、strict mypy 136 files 通过；任务累计生产/测试 22 文件、净新增 2713 行，低于任务阈值，Step 4 无未预期文件；
- 没有读取秘密、调用真实 Provider、访问外部网络、创建数据库、修改前端/依赖/lockfile、commit、push、PR、CI 或进入 Step 5。

## Step 5 完成摘要

- RED 在 collection 因 `PlanRepairBrief` 不存在失败；GREEN 后 repair 不再携带原始无效模型输出或完整 `PlanningContext`，只使用日期/城市/窗口骨架、允许 ID 目录与稳定诊断；
- generation/repair 在 builder 和 DeepSeek adapter 两层过滤 Provider label：最多 120 字、单行、无控制符/提示控制标记；category/kind 仅允许项目 token，unsafe 文本不会进入模型 payload；
- `f005-v1` 固定 48 case 按 legacy/V2/V3/F-003 各 12、每 slice 正常/Provider/freshness/security 各 3 分布；重复两次结果一致，六维加权 100.0%，提示注入、来源伪造、工具越权、预算超限和假 ready 零失败；
- 定向 `127 passed`、完整 backend `1270 passed`；Ruff、strict mypy（137 source + eval 4 files）通过；任务累计 36 文件/3421 净新增行，Stack 3 估算 1706 净新增行，未触发阈值；
- 没有前端、Schema/migration、依赖/lockfile、数据库、秘密、Provider/外部调用、commit、push、PR、CI 或 Step 6 实现；eval 只证明固定离线回归，不代表真实 Provider/模型 UAT。

## Step 6 完成摘要

- RED 定向 30 项中 4 项按预期失败，证明鉴权配置、错误排序、stale 恢复和 unknown-validity 披露缺口；最小 GREEN 后 30 项全部通过；
- 前端只按现有同 shape 字段展示服务端裁决：鉴权无 retry，暂时失败受 `retryable/attempt` 控制，stale 显示重新获取，unknown-validity 不暗示 fresh，也不单独创造 retry；
- 固定错误排序、safe Provider 名称和安全文案已覆盖 legacy/V2/V3；exact parser、unknown/null、attempt 3、F-003 replan 与 V3 用户城际语义保持；
- 前端全量 `99 passed`，Prettier、ESLint、TypeScript、Vite build 和无 SQLite API/contracts `98 passed`；6 个批准文件净新增 230 行，任务累计 42 文件/3651 行，未触发阈值；
- 未进入临时 SQLite、browser、Step 7、Schema/migration、依赖/lockfile、秘密、Provider/网络、数据库或交付操作。

## Step 7 完成摘要

- 临时 schema v2 SQLite 纵向最终 `31 passed`；冻结 V3 browser 日期在当日成为 D+0 后，先新增测试取得精确 RED，再仅在 browser 支撑中允许显式平移冻结日期；生产 contracts、Repository、Schema/migration 未变；
- Edge desktop/390px 覆盖 V3 partial、键盘/skip link、retry、reload 恢复、unknown/null 与时效披露；浏览器 57 条请求全为 loopback，overflow、DOM/ARIA、console error/warning 均为 0；
- 临时数据库只含 migration 1/2 和既有表，敏感/原始 payload/运行诊断模式扫描为 0；三份精确数据库文件已移入可恢复的回收站；
- 独立 Codex Security scan `c0d1100d-227b-4572-aa5a-769cb0689541` 覆盖 8 个信任面、coverage complete、0 finding；安全/韧性 `365 passed`，SQLite `31 passed`，Ruff 与 strict mypy 137 files 通过；
- Step 7 仅受控修改 2 个测试文件、净新增 59 行；任务累计 44 文件/3710 净新增行，未触发阈值；未进入 stacked PR 或任何 Git/远程交付操作；
- 首次 Playwright CLI `npx` 探测可能查询 npm registry，随后全部改为 offline。该严格非 loopback 过程偏差已披露并阻止无条件 PASS；用户已明确接受该偏差。

## 当前产品与技术边界

- F-001 产品状态保持 `PARTIAL`；Step 45M 真实 UAT `FAIL`、Step 45T 真实 UAT `PASS` 均保留；
- unknown 金额保持 `null`，混合交通 fallback 只有离线证据；
- F-004A/F-004B1 均无真实 Provider UAT，F-004B1 城际 Provider 调用为 0；
- SQLite schema 保持 version 2，无 migration v3；legacy/V2/V3、F-003 replan 和现有 API shape 必须兼容；
- F-005 不新增 Provider、真实调用、依赖、账号、遥测、公网服务、交易或生产高可用能力。

## 阻塞与下一入口

Step 7 技术验收已完成，首次 `npx` 探测可能访问 npm registry 的已披露过程偏差已由用户明确接受。Step 8 也已完成；不得自动 merge、clean-restack、运行最终 main CI、归档或进入 Step 9。

## Step 8 完成摘要

- 用户接受已披露的 Codex CLI 全局插件外连失败偏差；该失败未访问真实 Provider、未形成 Provider UAT，也未改变项目代码或数据边界；
- 用户批准把交付拓扑改为五层，并在 application/Agent 与 UI 之间新增 `feat/f-005-agent-eval-integration`；
- 新层的 RED 是 eval 测试在收集阶段因 `evals.f005.application` 不存在失败；最小 GREEN 通过真实 `ProviderPlanningJobExecutor`、legacy/V2/V3 orchestrator 与 `ReplanApplicationService` 的离线入口观测终态、来源、unknown/partial 和调用预算；
- case schema 已拒绝 `published_source_ids` 与 `unknown_amount` 等自报观测字段；DeepSeek 使用 `MockTransport`，Amap/QWeather 使用 fake，F-004B1 城际 Provider 调用保持 0；
- 最终本地门禁通过 backend format/lint、strict mypy 139 files、backend `1309 passed`、frontend format/lint/typecheck、`99 passed`、build、文档测试 `24 passed` 与文档检查器；
- 三轮独立 review 的所有 P1/P2 均以对应 RED/GREEN 关闭，五层最终复审均为 NO FINDINGS；
- 五层分支已普通 push；Draft PR #27/#28/#29/#30/#31 依次以 main/前层分支为 base，首轮 CI runs `32450657207`、`32450661429`、`32450664838`、`32450668170`、`32450671589` 全部 success；
- 未 merge、clean-restack、运行最终 main CI、归档或进入 Step 9；未修改 Schema/migration、依赖/lockfile，未读取秘密或调用真实 Provider。

## 权威入口

- 完整任务卡：[current-task.md](./current-task.md)
- Step 0–9：[implementation-plan.md](./implementation-plan.md)
- 路线与优先级：[roadmap.md](./roadmap.md)
- 长期决策：[D-014](../decisions.md#d-014f-005-统一外部服务韧性数据时效与离线-agent-评估)
- Step 0–7 证据：[evidence.md](./evidence.md)
