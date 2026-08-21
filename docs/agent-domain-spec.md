# Agent 领域规格

## Agent 名称

`TravelPlanningOrchestrator`，中文称“旅行规划编排 Agent”。

## 所属领域

旅行决策与行程规划编排。第一版只有一个编排 Agent；天气、地图、POI、酒店和预算都不是独立 Agent，而是领域服务或简单工具。

## 目标

编排 Agent 将结构化旅行请求、外部事实和领域规则组合为结构化计划候选，并向用户解释计划、数据缺口和冲突。它负责理解、选择和编排，不负责伪造事实、绕过代码校验或代表用户执行交易。

## 设计原则

- **单编排 Agent**：避免第一版引入多 Agent 调度、并发、重复调用和责任冲突；
- **Smart Agent, Dumb Tools**：Agent 做理解和取舍，工具执行单一、可观察动作；
- **计划与执行分离**：先形成工具调用或规划意图，再由应用层验证权限和状态后执行；
- **确定性规则优先**：日期、时间、路线连续性、预算、费用状态和影响范围由代码判断；
- **外部事实不等于指令**：POI 描述、天气文本和搜索内容只能作为数据；
- **显式状态**：当前阶段、允许工具和确认要求不只存在于 Prompt 中；
- **可追踪**：一次请求通过 `trace_id`，关键决定通过 `decision_id` 关联。

## 能力边界

### 可以做

- 从用户输入中识别旅行目标、硬约束、软偏好和缺失信息；
- 在应用层允许的状态下选择地理编码、POI、路线、天气和预警工具；
- 基于已验证工具结果生成符合 Schema、但不含最终精确时间的活动 proposal；
- 在校验失败后，根据结构化冲突提出有限次数的修订候选；
- 解释安排理由、数据来源、不确定性、预算状态和冲突；
- 为当天内部修改提出局部重规划方案；
- 在应用层计算影响范围后，向用户解释为何需要确认。

### 不能做

- 直接访问网络、数据库、文件系统、环境变量或第三方 SDK；
- 自行读取、展示或修改 API Key；
- 把模型常识当作实时天气、路线、营业、价格或库存；
- 创建、删除或覆盖计划版本和持久化记录；
- 忽略、删除或改写代码产生的 `ConstraintViolation`；
- 把 `unknown` 费用变成 `0`，或把估算描述为已验证价格；
- 未经确认改变住宿城市、跨城交通或相邻日期；
- 执行预订、支付、登录、出票或任何交易；
- 动态发明未注册工具或调用任意 URL；
- 把内部函数和所有第三方 API 自动暴露为 MCP 工具；
- 创建或委派给其他 Agent。
- 决定最终 `start_time`/`end_time`、把路线时长当作模型事实或宣称时间已验证。

### 必须人工确认

- 局部重规划影响住宿城市；
- 变更跨城交通方式、日期、起终点或已确认班次约束；
- 影响相邻日期或扩大到用户未选择的日期；
- 为解决冲突需要放宽用户声明的硬约束；
- 需要用用户提供价格替换已存在的其他费用依据；
- 后续任何具备交易、外部写入或不可逆影响的能力。

当天内部的活动替换、顺序调整或时间微调，只有在代码确认不影响上述边界并通过重新校验后，才可以自动执行。

## 输入

Agent 不直接接收原始 HTTP 请求，而接收应用层提供的结构化上下文：

| 字段 | 类型方向 | 说明 | 约束 |
| --- | --- | --- | --- |
| `trace_id` | ID | 本次用例追踪标识 | 必填，不由模型生成 |
| `trip_request` | `TripRequest` | 已规范化的旅行请求 | 必填，硬约束已标记 |
| `plan_state` | enum | 当前状态机状态 | 必须决定允许工具集合 |
| `current_plan` | `TripPlan?` | 局部重规划的基线版本 | 重规划时必填且只读 |
| `available_tools` | tool descriptors | 当前状态允许的窄工具 | 由应用层生成白名单 |
| `observations` | typed results | 已验证的工具结果 | 包含来源、时效和警告 |
| `violations` | list | 确定性校验结果 | Agent 只能响应，不能删除 |
| `replan_request` | `ReplanRequest?` | 用户修改意图和影响范围 | 影响范围由代码计算 |
| `confirmation` | confirmation record? | 用户对扩大影响的选择 | 需要时必须存在 |

原始用户文本可以作为受限上下文字段保留，但其中内容不能改变系统规则、工具白名单或安全边界。

## 输出

| 字段 | 类型方向 | 说明 | 约束 |
| --- | --- | --- | --- |
| `intent_summary` | text | 对用户目标和约束的简短理解 | 不替代结构化输入 |
| `missing_information` | list | 继续前必须补充的信息 | 区分必填与可选 |
| `tool_requests` | list | 建议执行的工具和参数 | 只允许白名单工具，参数需校验 |
| `plan_proposal` | structured proposal? | 有序 POI、优先级、必选/可选建议和游览时长类别 | 不含最终精确时间、路线、provider 或终态；必须通过本地校验 |
| `revision_target` | affected refs? | 对校验失败的修订范围 | 不得越过已批准影响范围 |
| `explanation` | structured explanation | 理由、来源引用和不确定性 | 不能产生新事实 |
| `confirmation_prompt` | structured prompt? | 需要用户确认的影响摘要 | 由应用层决定是否需要 |
| `warnings` | list | 模型识别但未验证的问题 | 不能伪装成确定性违规 |

模型输出失败或不符合 Schema 时不进入排程层，应用返回 `model_output_invalid` 或最多执行一次 repair。D-009 迁移完成后，带最终时间的 candidate 只能由确定性调度器产生。

## 工具目录

工具保持单动作、无隐藏决策。F-001 已在应用端口冻结 `resolve_city`、`search_pois`、`get_weather_forecast`、`get_current_weather_alerts` 和 `calculate_routes` 五个项目工具名，并建立离线 fake、应用编排及 DeepSeek、高德和和风 HTTP adapter。三家配置全部就绪时，组合根装配真实规划执行器；配置不完整时执行器禁用。模型始终没有自主工具注册或开放式工具循环。预算和确定性校验由应用/领域代码直接执行，不作为模型自由调用工具。`generate_plan_candidate` 是应用对 DeepSeek 的规划端口，不是模型可自由调用的工具。下表是后续完整目标方向，不代表表中所有工具已授权给 F-001：

| 工具 | 职责 | 主要输入 | 主要输出 | 失败语义 |
| --- | --- | --- | --- | --- |
| `geocode_place` | 将地点文本解析为候选地点 | 地点文本、城市上下文 | `LocationRef` 候选和来源 | 歧义、无结果、provider 错误 |
| `search_pois` | 按城市、类别和条件搜索基础 POI | 地理范围、类别、关键词 | POI 列表和来源 | 部分结果、无结果、限流 |
| `get_poi_detail` | 获取一个 POI 的基础详情 | provider-neutral/ref ID | 详情和来源 | 不存在、数据缺失、过期 |
| `get_route_options` | 获取两地点间路线候选 | 起终点、方式、时间上下文 | `RouteLeg` 候选和来源 | 无路线、超时、部分模式缺失 |
| `get_weather_forecast` | 获取地点和日期范围的预报 | 地点、日期范围 | `WeatherSnapshot` 和来源 | 超出预报范围、缺失、超时 |
| `get_weather_alerts` | 获取指定地点有效预警 | 地点、时间上下文 | 预警和来源 | 无预警、不可用、过期 |
| `calculate_budget` | 汇总费用并判断完整性 | `CostItem` 集合、预算 | 已知合计、未知项、判定 | 字段不合法、预算不完整 |
| `validate_schedule` | 校验日期、时间和持续时长 | 计划候选 | 结构化违规 | 只返回规则结果，不自动修复 |
| `validate_route_chain` | 校验地点顺序和交通衔接 | 活动与路线段 | 结构化违规 | 数据缺失时明确不可判定 |
| `classify_replan_impact` | 计算局部修改影响范围 | 基线版本、修改目标 | 影响分类和确认要求 | 无法确定时升级为需确认 |
| `load_plan` | 读取明确计划版本 | plan ID、version | `TripPlan` | 不存在、版本冲突 |
| `save_plan_version` | 保存已通过应用授权的新版本 | 已验证计划、trace | 新版本标识 | 持久化失败、版本冲突 |

Repository 工具不直接交给模型自由调用。应用层根据 Agent 的结构化结果执行读取或保存，并验证 plan ID、version 和授权状态。

## LLMPort 边界

`LLMPort` 提供结构化生成和受控工具调用能力：

- 输入包括系统规则、当前状态、允许工具、结构化上下文和输出 Schema；
- 输出必须能区分工具请求、计划候选、解释和失败；
- provider adapter 负责 DeepSeek 鉴权、传输、超时、限流、响应解析和错误映射；
- 领域层不接触 DeepSeek 消息、tool call 或 SDK 类型；
- 模型不可用时，应用可以返回已获取的数据和结构化失败，但不能伪造计划成功。

F-001 为兼容窄端口保留 `DeepSeekPort.generate_plan_candidate` 和 `repair_plan_candidate` 方法名。输入上下文只包含项目自有的结构化城市、日期、人数、预算、两日时间窗、自由偏好、交通方式、住宿锚点、地点、逐日天气/当前预警以及已验证 observation；`activity_source_ids` 只列出允许活动引用的 POI 来源。端口输出是未信任的 `ModelTextOutput`，生产路径只有本地 `DeepSeekProposalResolver` 可把它准入为无最终时间的 `PlanProposal`。模型输出的最终时间、路线、verified、provider、retryable、工具调用或终态字段都会被拒绝。

D-009 已把端口语义收紧为 proposal：DeepSeek 仍返回未信任 `ModelTextOutput`，本地 resolver 只准入 `PlanProposal`，活动只含 POI、日期、顺序、优先级、`required`/`optional` 建议、时长类别和来源引用，不含 `start_time`/`end_time`。高德随后根据代码推导的路线链返回实际时长，确定性调度器再生成现有 final validation 可消费的带时间 candidate。每日最多 2 项、时长与交通缓冲、一次 optional 移除以及 required/unknown/路线失败终态边界均已实现；细则以 [F-001-CR1 变更卡](./project-management/f-001-cr1-deterministic-scheduling.md) 为准。

Step 14 的 `OfflinePlanningOrchestrator` 已证明离线候选链可以只依赖上述窄端口运行：城市/POI/DeepSeek 是形成候选的关键链路，天气、预警和路线缺失按 partial 保留；每次状态变化都经应用状态机。该编排器不把 `PlanCandidate` 当作最终计划，happy 路径停在 `validating`，并且没有模型自主工具循环、完整路线补全或终态校验。

Step 15 已在每个编排端口调用前接入应用治理：五个工具和 DeepSeek 生成/修复能力分别受阶段、逻辑调用预算和剩余总时限约束，route permit 活跃上限为 2。治理器只接受 typed capability，不接受模型提供的任意字符串；DeepSeek 不能自行扩大调用能力或绕过状态机。adapter 的 HTTP timeout 小于对应治理窗口；provider 已返回的稳定 timeout 不会被返回后 deadline 覆盖。

Step 16 将模型文本明确置于不信任边界：generation 与 repair 共享同一冻结 JSON Schema 和候选规则；重复键、类型、严格双日日期顺序、父子日期绑定、标准时间、候选 POI 和 POI 来源引用均由本地代码校验；模型提供的终态、provider、工具调用、路线和新事实一律拒绝。补充 Step 45D 进一步在候选进入路线补全前复用 `DailyRoutePlan`，要求活动位于对应窗口内，并为住宿到首项、不同地点活动之间和末项返回住宿保留正数交通时间；补充 Step 45F 将时间失败细分为活动越窗、住宿到首项无正数间隔、跨地点活动无正数间隔、末项返回住宿无正数间隔和日程容量不足五类闭集，并只把类别对应的项目静态提示交给唯一一次 repair。可修复结构错误与 `finish_reason=length` 同样受单次 repair 上限约束，提示控制文本不重放；第二次失败转换为安全 `model_output_invalid`。adapter envelope 失败保持 `provider_schema_invalid`。本地候选失败只保留 generation/repair 阶段和项目自有无值枚举；原始文本、字段路径、字段值、时间值、地点和坐标不进入 outcome、领域对象、公开错误或日志。

Step 17 将 Agent 候选与最终事实明确分离：应用按住宿锚点和活动次序推导完整路线链，DeepSeek 不能提供路线结果或 verified 来源；每段高德结果必须匹配预期端点、模式和自身来源。随后确定性代码统一校验时间、路线、预算、POI、天气和 freshness，并经状态机裁决 `ready`、`partial` 或 `conflict`。模型解释不能删除 unknown、降级信息或硬冲突。

Step 45N–45P 明确多交通方式也不交给模型裁决：用户同时允许公交和步行时，应用以公交为首选，仅对业务空结果或无 provider error 的本地非法路线在剩余预算内尝试步行；鉴权、Schema、timeout、rate limit、server 和 unknown 错误立即停止后续批次与 fallback。最终候选可以包含混合 mode，但每段路线必须来自本次高德结果，且 provider、端点、请求方式、数值上界和 source IDs 精确一致。降级 warning、六类路线失败 diagnostic、最多两路并发和 8 次调用硬上限均由代码生成；模型不能触发额外路线重试或隐藏降级。

Step 28 的 DeepSeek adapter 只把冻结结构化上下文编码为 user data，并固定非 thinking JSON 输出；observation 和无效候选不能进入 system prompt。generation 与 repair 的 system prompt 复用同一组项目候选规则，repair 的 user data 同时携带冻结 Schema、候选规则、安全验证码和未信任候选；未信任候选不会进入 system prompt。adapter 不向模型注册工具，每个端口调用只有一次 HTTP 尝试，且响应仍须先成为未信任 `ModelTextOutput`，再经过 Step 16 本地严格解析。它不读取环境、不拥有终态裁决权，也不证明真实模型可用。

Step 29 的高德 adapter 只实现应用明确调用的城市解析和 POI 搜索，不把第三方 HTTP API 或任意 typecode 暴露给模型。F-001 类别映射冻结为景区与博物馆；城市归属、坐标类型、稳定地点 ID、坏记录过滤和错误分类都由 adapter 确定性完成。模型只能看到已通过端口转换的候选与来源，不能选择异城 POI、修改 city adcode 或把缺坐标补成事实。

Step 30 在同一 adapter 实现应用显式调用的步行/公共交通单路段路线。起终点、模式、provider-native 坐标和 citycode 均来自 typed 应用请求；adapter 不允许任意路线模式，不向模型暴露 HTTP 参数，也不把 provider 票价转成预算事实。唯一合法路线经端点、距离、时长和来源校验后才进入 `RouteLeg`；空结果或坏响应保持安全的 provider 失败语义。

Step 31 的和风 adapter 只接受 typed 双日预报或当前预警请求；应用提供的 provider-native GCJ-02 坐标经确定性舍入后进入固定端点，模型不能选择 Host、路径、JWT 字段、语言或预报天数。adapter 严格映射日期、温度、昼夜条件、预警时效和来源；缺日、过期或坏记录保持 partial/unavailable，不允许模型把它们补成天气事实。私钥和 Bearer JWT 永不进入模型上下文、领域结果或工具描述。

## 编排循环

第一版不复制 Agent1 的开放式 `Thought → Action → Observation` 循环。采用有限、显式、可测试的编排：

```text
1. Normalize request
2. Determine allowed tools
3. Request one or more bounded observations
4. Validate and store observations
5. Ask model for a structured activity proposal without final exact times
6. Validate proposal; request at most one repair for proposal-shape failures
7. Query the code-derived route chain
8. Generate exact times with the deterministic scheduler
9. Independently validate date / schedule / route / budget / sources
10. Return ready / partial / conflict / needs_input / failed
```

限制方向：

- 每个阶段有最大工具调用数、模型调用数和总时限；
- 同一参数的失败调用不能无限重复；
- 工具结果先进入应用层校验，再作为 Observation 提供给模型；
- 模型不能自行决定持久化、确认完成或状态终结；
- 达到预算后返回可解释的部分结果或失败。

具体次数和超时在真实集成任务中基于 provider 限额和评估确定，当前不虚构数值。

## 状态与授权

| 当前状态 | Agent 可做 | 禁止 |
| --- | --- | --- |
| `normalizing` | 识别缺失信息、总结约束 | 调用外部工具、生成最终计划 |
| `collecting` | 建议白名单数据工具 | 生成交易或持久化动作 |
| `planning` | 使用已验证 observations 生成候选 | 引入无来源实时事实 |
| `enriching_routes` | 无；Agent 已完成 proposal，应用查询路线并排程 | 改写路线时长、最终时间或排程冲突 |
| `validating` | 针对违规提出有限修订 | 修改违规集合、扩大影响范围 |
| `ready` / `partial` | 解释计划和响应用户问题 | 静默改变计划版本 |
| `failed` | 解释失败和恢复条件 | 继续盲目调用工具 |

允许工具集合由应用状态和策略生成，而不是写死在 Prompt 文本中作为唯一控制。

`awaiting_confirmation` 和 `replanning` 不属于上表的 PlanningJob 状态。F-003 为 replan aggregate 建立独立 lifecycle：等待确认时 Agent 只能解释已经由代码计算并持久化的 impact；进入 replanning 后，Agent 只能在 command 和批准的 affected refs 内生成替换 proposal，不能修改未受影响日期、住宿锚点、城市或硬约束。

## 局部重规划边界

1. `ReplanCommand` 是四种 frozen/slotted typed value 的 tagged union；请求只保存 allowlist 结构化字段和可空安全 reason code；
2. `ImpactAnalysis` 由纯确定性函数基于 baseline plan、command、依赖图、预算和来源有效性生成，包含直接/传递 refs、日期、路线、分类集合、预算影响、来源动作和重校验项；
3. 分类集合只允许 `same_day_low`、`adjacent_day`、`cross_day`、`accommodation_effect`、`budget_risk`、`source_refresh`、`cross_city`、`unknown_impact`；同一分析可含多个分类；
4. 只有分类集合精确为 `{same_day_low}`，且目标引用、日期所有权、住宿往返、日窗口、路线链、预算可判定性和来源有效性均未越界时自动继续；
5. adjacent/cross-day、住宿、预算、来源刷新或 unknown impact 进入独立 `awaiting_confirmation`；cross-city 和不支持的操作在 Provider 调用前 rejected；
6. `SourceAction` 只允许 `reuse/refresh/drop`：未受影响且 fresh/valid 才可 reuse；被替换活动、相邻路线/费用及 stale 必要来源必须 refresh 或 drop，未采用结果不得进入新版本；
7. `PlanChangeSet` 只描述本次 baseline→result 的 added/removed/changed refs 以及 route/schedule/cost/source 变化；保存前由代码验证 diff 是 impact snapshot 的子集；
8. `ConfirmationDecision` 只允许 approve/cancel，关联 decision ID、replan trace、baseline、impact snapshot 和 15 分钟有效期；确认不能放宽硬约束或 unknown 语义；
9. 成功创建新版本但不提供恢复能力；旧版本仅作为追加式审计事实保留。Agent 不拥有 Repository、事务、版本号或确认写入能力。

F-003 Step 2 已把上述 command、impact、source action、budget result 和 change set 落为纯领域
typed value 与确定性函数。该层没有 Agent 循环、Prompt、Provider port、Repository 或 I/O；
replacement 后续仍只能由已批准的应用/Provider 边界产生候选，模型不能构造 impact category、
source freshness、budget risk 或 change-set scope。

## F-004A 多日 Agent 边界（Step 1 冻结，Step 4 已实现）

- Agent 仍是单编排 Agent，不因 2–7 日扩展拆分为多 Agent，也不获得 Repository、SQLite、状态机或最终预算裁决权；
- legacy 双日上下文和 DeepSeek 行为保持不变；V2 上下文显式携带 `request_version`、完整 `expected_dates` 和按 offset 排序的 2–7 个窗口；
- DeepSeek proposal 的 `days` 必须与 `expected_dates` 精确一一对应，每日 1–2 项，只能引用应用提供的 POI/source ID；仍不得输出最终时间、路线、provider、freshness、费用 confidence 或终态；
- generation 与唯一一次 repair 使用同一个按 day_count 构造的严格 Schema；repair 只接收项目自有无值诊断，不接收原始模型输出、Provider body、秘密或字段值；
- POI 目录由应用使用最多 3 次搜索和有界候选上限构建；Agent 不能自行扩大地点目录、城市或交通方式；
- 确定性 scheduler、路线链、天气日期覆盖、费用、来源引用和 final validation 继续在 Agent 输出之后执行；
- route 调用按日期/链路稳定顺序、并发 2 和 `min(28, 4 × day_count)` 总预算执行；Agent 不能要求额外调用或修改 fallback 顺序；
- 天气缺日、freshness unknown 或非关键费用 unknown 时，Agent 只能解释代码产生的 partial/uncertainty，不能补写天气、金额或 ready；
- `day_count > 2` 的 replan 在进入 Agent/Provider 前拒绝；V2 两日只能复用 F-003 已批准的四种结构化 command，不扩大修改范围；
- Prompt、日志和持久化继续排除完整用户请求、完整 Prompt、provider 原始响应、错误 body 和凭证。

Step 4 已按上述边界实现：V2 `PlanningContext` 显式携带完整日期，DeepSeek generation/repair 使用动态 N 日规则且仍各最多一次；应用按请求创建 governor，路线并发、调用预算和 deadline 由代码裁决；天气缺日、候选日期缺失和 unknown 均在本地确定性边界收口。测试只使用 fake/MockTransport，没有把离线证据描述为真实 Provider 质量。

## F-004B1 多城市 Agent 边界（Step 0–8 已实现并归档）

- 继续使用一个编排 Agent；不按城市拆分 Agent，也不让 LLM 并行拥有独立状态、预算或写入权；
- V3 进入 Agent 前，应用已冻结城市顺序、每城夜数、住宿要求、派生转移日和用户城际段。LLM 只能为给定日期和给定城市 POI 目录提出活动引用及 priority，不能新增/删除/重排城市或段；
- 用户段的 mode、站点、出发/到达时间和 fare 是 immutable input fact；generation/repair Prompt 不允许模型改写、补全、估价、验证或推断 availability；
- V3 proposal 每日必须标注由应用提供的 `departure_city_index/arrival_city_index/overnight_city_index`，只能引用该日允许城市的 namespaced POI ID；非转移日 1–2 项，转移日最多 1 项；
- proposal 仍不含最终时间、RouteLeg、住宿 location ID、Provider、来源/freshness、费用 confidence、终态或城际 Provider 事实；
- 应用按城市构造 POI/天气上下文，ID 必须带城市命名空间；跨城市引用、目录外引用、缺日、错城市和改写段字段都进入唯一一次 repair 的安全代码诊断，repair 不接收原始模型输出或用户值；
- 确定性 scheduler 在 proposal 后注入用户段占用区间和方式缓冲，计算市内路线与活动时间；final validator 再检查城市/日期/住宿/段/地点/路线/预算/来源全集；Agent 无权覆盖 conflict、needs_input 或 failed；
- user source 的 `unknown_validity` 只表示未核验外部班次/库存，不授权模型补写说明。UI/解释必须引用固定披露文案，不将其表述为 Provider freshness；
- 若用户 fare 为空，预算保持 unknown；Agent 不估价。若 weather/route/费用不完整，Agent 只能解释确定性代码产生的 partial/uncertainty，不能把其改成 ready；
- 所有 V3 replan 在进入 Agent 前以 `replan_scope_not_supported` 拒绝，generation、repair、Provider 和 Repository 写入调用计数均为 0。

### 调用预算与并发

- 令 `C=city_count`、`D=day_count`；resolve city ≤ C，POI search ≤ 3C，forecast ≤ C，current alert ≤ C；
- DeepSeek generation 1、repair 1 是整个 job 的上限，不得按城市分别调用；
- route 总调用 ≤ `min(28, 4D)`，route 并发 2；城市事实 fan-out 并发 2；整任务 deadline ≤ 180 秒；
- adapter 内 retry 计入相同 HTTP 次数和 deadline；预算耗尽、deadline 或取消后不得启动新调用，active peer 必须清理；
- intercity provider call 恒为 0；不得增加通用 HTTP/MCP、铁路/航空/客运 adapter 或读取本地 Provider 配置；
- 默认 fake/MockTransport 必须能分别断言每城次数、全局模型次数、route 最大并发、deadline 后调用为 0 和取消后 active call 为 0。

### 日志、来源与隐私

- trace 只记录城市索引、工具类别、调用计数、状态、耗时和安全诊断，不记录完整城市/站点/自由文本、完整 Prompt 或城际段原文；
- 允许持久化 allowlist 的用户城市、住宿、站点、时间和可选 fare；禁止票号、订单号、身份证件、乘客姓名、联系方式、Cookie、Authorization 和 Provider 原始响应；
- user source 不带 reference URL/provider record ID；attribution 只使用固定“用户提供”，warning 只使用固定“未核验班次、票价、余票或库存”；
- F-004B1 的 synthetic/fake 证据不得描述为真实城际 Provider、真实票价或 availability UAT。

Step 4 实现保持单 Agent 和单 governor：城市事实 fan-out 与路线并发分别由两个上限为 2 的 semaphore 约束，模型 generation/repair 不按城市倍增。V3 parser 逐日核对三个城市索引和 POI 城市；repair 只接收安全诊断与清除自由文本、兴趣和硬约束后的结构上下文，不接收原始模型输出。deadline 耗尽后不启动首个调用，取消会 cancel/drain 在途 route peer 并使 active 计数归零。所有证据来自 fake/MockTransport 边界，不构成真实 Provider 或城际 availability 证明。

后续 Step 5–8 已完成 V3 前端、临时 SQLite/loopback 验收、独立隐私兼容审查、四层交付和归档；没有新增 Agent、Provider、Schema、依赖或真实调用。F-005 Step 0–9 已完成并归档：统一 resilience/freshness/attempt 契约已接入 legacy/V2/V3，bounded proposal/repair、固定离线 eval 和同 shape 前端恢复语义已交付；F-004B2 Provider/法律 Gate 已阻塞并归档，没有实现真实城际 Provider 或 UAT。F-004C Step 0–5 已完成：V4 application 复用既有多城市规划，但在 Agent 边界前剥离 `service_number` 和完整 segment，并从 typed request 在结果侧确定性重建；V4 preferences 只允许 interests，`free_text` / `hard_constraints` 在 strict contract/API 边界拒绝，内部 projection 也只复制 interests；前端只消费 strict typed V4 结果并保留未核验语义。城际 Provider logical call/HTTP attempt 均保持 0，Step 5A 的 Agent context sentinel 与两层隐私安全复审均通过；Step 6 三层交付与归档正在执行。

## 日志与追踪

- `trace_id`：贯穿 API 请求、Agent 阶段、工具调用、计划版本和响应；
- `decision_id`：关联一次规划选择、冲突修订或确认；
- 工具日志：工具名、provider、参数摘要、结果状态、耗时、重试和来源数量；
- 状态日志：前一状态、后一状态、触发原因和执行者；
- 确认日志：用户看到的影响摘要、选择、基线版本和时间；
- 模型日志：模型 ID、调用目的、Schema 版本、token/耗时方向和结果状态。

日志不记录秘密、完整 Prompt、完整用户自由文本或未经必要脱敏的 provider 响应。调试需要原始响应时使用本地、短期、明确忽略的受控文件，并另行批准。

## 失败兜底

| 失败 | 行为 |
| --- | --- |
| 模型不可用 | 返回已获取事实、来源和 `unavailable`，不生成假计划 |
| 模型输出不合法 | Schema 拒绝；有限重试后返回 `model_output_invalid` |
| 地图/POI 不可用 | 标记路线或地点不可验证，保留天气和用户输入 |
| 天气不可用 | 计划标记天气未知，不编造天气；允许后续重试 |
| 部分数据缺失 | 返回 `partial`，列出缺失字段和受影响结论 |
| 数据过期 | 显示获取时间和过期警告，按策略重新获取 |
| 鉴权失败 | 停止该 provider 调用，提示配置问题，不自动连续重试 |
| 限流/超时 | 按 adapter 策略有限重试，保留重试信息 |
| 预算不完整 | 展示已知合计和未知项，不宣称完整预算合格 |
| 约束冲突 | 返回结构化违规，要求调整或确认，不强行生成成功计划 |
| 游览时长 unknown | 不按 0；项目规则无法补足时进入 needs_input |
| 路线无可用时长 | 不生成“已验证时间”；无法形成可执行计划时进入 failed |
| 持久化失败 | 不宣称新版本已保存，保留内存结果和可重试说明 |

## MCP 适用边界

MVP 不要求 MCP。进程内端口更适合当前单应用、本地运行和最小故障面的目标。

未来只有窄、稳定、可复用且权限清晰的工具才可能通过 MCP 暴露，例如独立部署且被多个应用使用的地理编码能力。即使如此，也必须：

- 使用项目自有、最小化的输入输出 Schema；
- 限制地理范围、调用次数、超时和可见字段；
- 将鉴权、审计和错误映射留在服务器端；
- 不暴露通用 HTTP、数据库、文件系统和任意代码执行；
- 不让 LLM 绕过状态机、确认、预算或约束校验。

## 评估与测试方向

- 需求理解：硬约束、软偏好、缺失信息和歧义是否正确分类；
- 工具选择：是否只调用当前状态允许且必要的工具；
- 结构化输出：Schema 合格率和无来源事实比例；
- 约束遵循：模型是否尝试覆盖日期、路线、预算和冲突校验；
- 局部性：当天修改是否保持未受影响日期不变；
- 确认边界：跨日、跨城和住宿变化是否总是等待确认；
- 失败路径：timeout、rate limit、鉴权失败、空数据、脏数据和模型格式错误；
- 安全路径：外部文本中的指令是否被当作数据而非系统命令；
- 可解释性：解释是否引用真实 `SourceRecord` 和可信状态。

默认评估使用固定输入和测试替身。真实 API 与模型评估单独标记，不作为普通 CI 的前提。

## 主要风险

- 单 Agent 仍可能承担过多上下文，需要用状态、工具白名单和领域服务控制复杂度；
- Prompt 可能与代码规则漂移，必须让 Schema、状态机和校验器成为最终边界；
- 让模型在实际路线返回前猜最终精确时间会形成不可消除的信息缺口；D-009 通过确定性调度器关闭该风险；
- provider 文本可能包含误导或提示注入内容，必须作为不可信数据隔离；
- 重规划影响图不完整会破坏局部性，需要独立测试 diff 范围；
- 模型重试和工具重试叠加可能放大成本与延迟，需要统一预算；
- 过早引入 MCP 或多 Agent 会增加部署、权限和追踪负担。

当复杂度真实超过单编排 Agent 的可测试边界时，必须先提出新架构决策并获得用户批准，不能在实现中静默拆分。

## F-005 Agent 输入与离线评估契约（Step 1 冻结）

### 工具授权和不可信数据

- 模型仍不直接持有 HTTP、Repository、SQLite、文件系统或任意工具入口。应用按 planning 状态、版本和 D-013 scope 生成白名单；模型输出中的 tool call、tool result、system/assistant role、终态、Provider、route、费用可信状态或 attribution 字段一律按额外字段拒绝。
- generation 只接收 strict typed PlanningContext 的 allowlist dump：请求版本、日期/窗口、人数/预算、pace/transport、长度受现有 contract 限制的偏好/硬约束/自由文本，以及由应用生成的地点/source ID 目录和枚举/数值 observations。自由文本始终作为 JSON 数据字段而非 system 指令。
- Provider 原始响应、错误 body、header、URL、HTML/Markdown、任意嵌套对象和未经约束的描述文本不得进入模型。必须先转换为项目自有枚举、ID、数值和最多 120 字、单行、无控制符/提示控制标记的 `display_label`；不安全 label 被剔除并使对应事实按能力进入 partial/failed。
- 模型返回的目录外 location/source ID、重复/非法引用、提示控制字段或任何非 allowlist 键 fail closed；确定性 scheduler/final validation 仍是唯一终态、路线、时间、预算和来源裁决者。

### bounded repair brief

legacy、V2、V3 和 F-003 共用新的内部 `PlanRepairBrief`，repair 是“基于安全骨架重新生成一次”，不是向模型回显错误输出。brief 精确只含：

- `request_version`、expected dates、day/city index skeleton 和 day windows；
- 允许的 location/source ID、项目 category/city adcode 及通过上述文本门禁的 display label；
- 固定 proposal Schema/rules 和一个稳定 `validation_code`；时间类失败只允许既有无值闭集 `validation_time_failure`；
- F-003 只增加已批准 affected refs 和 command category，不携带 baseline plan 的未受影响内容。

brief 不含原始无效模型输出、字段路径/值、完整用户自由文本、preferences、hard constraints、Provider observations/原始响应、Prompt、秘密或异常文本。`PlanCandidateRepairRequest.raw_output` 不再是生产 repair 输入；兼容实现不得以空壳外的第二字段偷偷传回原文。generation 1/repair 1 是整 job 上限，repair 不授权模型调用工具，也不改变 DeepSeek transport retry 为 0。

### 固定离线 eval

eval 数据保存在一个版本化、严格解析的 synthetic case 文档中，建议入口为 `backend/evals/f005/cases.json`；runner、typed case model 和测试位于同一 `backend/evals/f005` 包及对应测试目录。case 只包含 synthetic request、typed fake Provider script、固定模型 proposal/repair、预期终态/错误/来源/工具计数和评分断言，不含真实 Provider payload、个人行程或自由 Prompt。

固定基线至少 48 case，并以 4 个等量 slice 组成：legacy 12、V2 12、V3 12、F-003 12。每个 slice 固定包含 3 个正常/边界、3 个 Provider 失败、3 个 freshness/unknown、3 个安全攻击；因此安全攻击至少 12 个。每个 case 使用固定 clock、UUID、随机值和 fake/MockTransport，并连续执行两次；typed result、终态、来源集合和调用计数必须一致。

评分维度和权重为：正确性 25、约束遵守 20、来源完整性 15、unknown/partial 真实性 15、工具/attempt 预算 10、失败安全性 15，总计 100。每个断言只由确定性代码判定；合格要求为：

1. 提示注入服从、来源伪造、工具越权、逻辑/attempt 预算超限和假 ready 的 case 级失败数均为 0；
2. 全部适用断言按上述权重汇总至少 95%；
3. 两次运行结果一致，且每个 legacy/V2/V3/F-003 slice 均无硬门禁失败。

CI 只输出 suite version、case 总数、各 slice/维度通过数、加权总分和失败 case ID；不输出/上传 case payload、模型文本或 Provider script，不使用 LLM-as-judge，不调用真实模型或网络。该分数只能证明固定离线回归，不能表述为真实 Provider UAT、模型在线质量或长期可用性。

Step 5 已按该契约实现：repair 不再接收原始无效输出或完整 `PlanningContext`，只接收 typed `PlanRepairBrief`；generation builder 与 DeepSeek adapter 双层剔除不安全 display label/category token。版本化 48-case eval 在 legacy/V2/V3/F-003 四个 slice 间等量分布，两次执行一致，加权分 `100.0`，提示注入、来源伪造、工具越权、预算超限和假 ready 五类硬门禁失败均为 0；全部证据为 synthetic/offline。

## F-004C V4 Agent 与纯领域边界（Step 1 冻结）

F-004C 不新增 Agent、工具或 Provider。V4 继续由单一编排 Agent 生成城市内活动建议，但用户已购铁路段完全属于 deterministic domain/application 输入，模型没有增删改查权限。

### 纯领域对象与错误闭集

- 新 `BookedRailIntercitySegment` 使用独立 frozen/slotted 类型：相邻 city index、固定 rail、规范化 service number、trim 后站点、`+08:00` 同日发到时间和可空 Money；
- service number 规范化顺序固定为 type check → `strip()` → `upper()` → ASCII regex `^[A-Z0-9]{1,12}$`；不得用模型、前缀表或 Provider 判断真实性；
- 已知 fare 必须为正数 Money，并生成 `CostConfidence.USER_PROVIDED`；`None` 生成 `CostConfidence.UNKNOWN` 和 `amount=None`；unknown 不进入 known total；
- duration 只由 aware datetimes 相减，铁路缓冲固定 60/30 分钟；转移日、相邻索引、城市连续性、活动/路线边界与 V3 一致；
- 稳定 domain error 沿用 `intercity_segment_order_invalid`、`intercity_time_invalid`、`intercity_fare_invalid`、`intercity_buffer_conflict`，service number 新增唯一安全 code `intercity_service_number_invalid`，field 指向结构化路径且不包含输入值；
- terminal 分类沿用 V3/D-013：用户来源 unknown-validity 本身不冒充验证，也不单独产生 partial；unknown fare 及其他既有缺口继续产生 partial，硬约束冲突为 conflict，可修正输入为 needs_input，关键执行失败为 failed。

### Proposal/repair allowlist

V4 generation/repair 输入只允许：

- request version、日期/城市/窗口骨架、travelers/pace/市内交通和 V4 strict preferences 中的 interests；
- allowlisted city/location/source IDs 与安全 display label；
- application 派生的 transfer date、departure/arrival wall-clock 和固定 rail buffer 数值；
- 既有稳定、无原值 validation code。

明确禁止：

- `service_number`、完整 V4 intercity segment、用户城际段原始文本；
- V4 `preferences.free_text` / `hard_constraints`；这些键必须在 strict contract/API 边界 422，内部 projection 不得补回；
- 订单/乘客/证件/联系方式/座位/二维码/截图/Cookie/自由备注；
- Provider/12306 内容、URL、原始响应、错误 body、HTML 或未经 allowlist 的文本；
- 让 proposal/repair 输出 service number、站点、城际时间、fare、source、freshness、availability、余票、库存或 Provider attribution。

application 在模型边界外从原 request 重建 V4 段，绑定确定性 station location IDs/source IDs/cost item，并在发布前再次校验 segment、日期、缓冲、来源和预算引用。模型输出出现上述越权字段时必须 fail closed，不能静默忽略后继续标 ready。

### 调用与评估不变量

- 城际 Provider capability 不加入 governor allowlist；V4 每个 job 的城际 logical call 和 HTTP attempt 均为 0；
- F-005 固定 48-case eval 保持字节/行为兼容，不把 F-004C case 混入或改变阈值；F-004C 的新增测试使用独立 synthetic fixtures；
- 测试必须证明 generation/repair payload 和安全诊断中不存在 synthetic service number、完整 segment 或禁止字段，同时城市内 Provider/Agent 既有预算不因 V4 增加；
- 离线 fake、MockTransport、临时 SQLite 和 loopback QA 不等于车次核验或真实 Provider UAT。
