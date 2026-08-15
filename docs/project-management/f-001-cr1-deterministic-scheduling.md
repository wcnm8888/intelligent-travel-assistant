# F-001-CR1：确定性时间排程责任调整

## 变更元数据

- 所属任务：`F-001 单城市双日旅行计划垂直切片`
- 变更类型：架构变更控制
- 任务等级：`L` 级任务内的高风险跨层变更
- 当前状态：`APPROVED / IMPLEMENTATION_NOT_STARTED`
- 关联决策：`D-009`
- 当前分支：`feat/f-001-single-city-two-day-plan`
- 当前 Draft PR：[#4](https://github.com/wcnm8888/intelligent-travel-assistant/pull/4)
- 设计 Step：补充 `Step 45G`
- 实施 Step：补充 `Step 45H`，设计、策略和范围已批准，实施仍需单独批准

本变更卡已冻结获批详细设计，但批准设计不等于授权实施。Step 45H 仍需单独批准；新的真实 provider 调用、live UAT、提交、推送和 PR 写入也必须分别获得授权。

## 用户目标和工程价值

用户需要的不是“格式正确但路线时间靠猜”的行程，而是由实际路线时长、明确游览时长和用户日窗口共同决定的可执行时间表。变更后的系统应让模型专注于偏好理解、POI 选择、优先级和解释，让代码生成并独立复验精确时间，从而消除相同 Prompt 在真实模型上反复产生时间不可行候选的结构性不稳定。

## 当前事实和变更原因

- Step 45A、45C、45E 三次受控真实 UAT 均未形成可验收的 `ready`/`partial` 计划；
- Step 45F 已证明 generation/repair 拥有完整日窗口、住宿锚点、POI 来源和正数交通窗口规则；
- 当前 `CandidateActivity` 要求 LLM 同时生成 POI、顺序和最终 `start_time`/`end_time`；
- 当前编排先生成精确时间候选，再调用高德路线，模型生成时间时没有实际路线时长；
- 当前确定性校验能正确拒绝不可行计划，但无法使模型稳定地产生可行时刻；
- 继续增加 Prompt 或 repair 次数只能改善概率，不能关闭信息缺口，还会增加成本和不确定性。

因此，D-009 已确认：精确活动时间骨架和排程由确定性代码负责，LLM 不再输出最终精确时刻。

## 范围

### 包含

- 冻结 LLM、路线 provider、确定性调度器和最终校验器的职责；
- 新增内部 `PlanProposal`/`ActivitySelection` 语义；
- 设计从有序活动建议到路线查询、确定性排程和最终计划的流水线；
- 定义分钟级、可复现、无复杂求解器的 MVP 调度算法；
- 定义游览时长可信状态、交通缓冲、溢出、unknown 和路线失败策略；
- 保持公开五种终态、现有最终计划 DTO、Repository 和 UI 主体不变；
- 设计 Step 45H 红绿测试和交付策略。

### 非目标

- 不引入多 Agent、优化求解器、路线矩阵、地图 UI、持久化或局部重规划；
- 不自动放宽日窗口、缩短必选活动、忽略路线时长或把 unknown 当作 0；
- 不让 LLM 生成路线事实、verified 时长或最终终态；
- 不在本变更中扩大 live 调用次数、费用或 UAT 授权；
- 不修改公开请求以增加逐景点时长编辑器；该能力可在后续产品任务单独设计。

## 冻结职责边界

### LLM

- 理解偏好、硬约束和节奏；
- 只从已验证 POI 目录中选择每日活动；
- 输出稳定的活动顺序、优先级、`required`/`optional` 建议和游览时长类别；
- 输出取舍理由、天气提示、解释和警告；
- 不输出 `start_time`、`end_time`、路线、路线时长、距离、费用可信升级或业务终态；
- `required` 只代表本次规划建议中的不可自动删除项，不能覆盖用户硬约束，也不能把模型判断升级为已验证事实。

### 高德

- 只接收代码确定的住宿和有序 POI 端点；
- 返回路线距离、分钟级时长、方式和来源；
- 不排序活动、不裁决可选项、不生成游览时长、不决定终态。

### 确定性代码

- 严格校验 proposal 的日期、POI、来源、优先级、必选/可选和时长类别；
- 从有序活动推导住宿往返及跨地点路线链；
- 使用实际路线时长、显式交通缓冲和游览时长生成精确时间；
- 处理一次受限的可选活动移除、unknown、硬冲突和 provider 失败；
- 独立执行日期、窗口、重叠、路线、预算、来源和最终终态校验。

## 推荐编排顺序

```text
TripPlanRequest
  → normalizing：请求、日期、窗口和费用校验
  → collecting：城市、住宿、POI、天气和预警
  → planning：DeepSeek 输出不含精确时刻的 PlanProposal
  → proposal validation：POI / 来源 / 日期 / 优先级 / 时长类别
  → enriching_routes：推导路线链并查询高德实际路线
  → deterministic scheduler：生成 start_time / end_time
  → validating：DailyRoutePlan + 日期 / 重叠 / 路线 / 预算 / 来源复验
  → Repository：ready / partial / conflict / needs_input / failed
  → Web UI：复用现有终态展示
```

不新增公开状态。`planning` 表示 proposal 生成与准入，`enriching_routes` 包含路线查询和时间骨架生成，`validating` 继续是独立复验。若 proposal 产生无法由项目规则补足的 unknown 时长，目标状态图需要增加 `planning → needs_input` 这一条已有状态之间的新边；不增加新 enum。

## DTO 方案比较

### 方案一：新增 proposal DTO，保留现有 scheduled candidate

模型输出：

```text
PlanProposal
  intent_summary
  days[2]
    local_date
    selections[1..N]
      location_id
      local_date
      title
      priority_rank
      selection_kind: required | optional
      duration_class: short | standard | long | unknown
      source_ids
  explanation
  warnings
```

调度器输出仍使用带 `start_time`/`end_time` 的现有 `PlanCandidate`/`CandidateActivity`，再进入当前 final validation 和公开计划映射。

优点：信任边界清楚；模型 DTO 和确定性结果 DTO 不混用；公开 API、前端和 Repository 可保持不变；现有最终校验可最大化复用。缺点：增加一个内部 DTO 层和 proposal 到 scheduled candidate 的映射。

### 方案二：修改现有 candidate，使时间字段可空或分阶段填充

优点：表面文件数较少。缺点：同一对象在排程前后拥有不同不变量；`None` 时间可能越过边界；解析、路线补全、最终校验和类型检查都需增加阶段判断；容易重新制造“半合法 candidate”。

### 推荐

采用方案一。`PlanProposal` 是 LLM 信任边界的唯一输出，现有 `PlanCandidate` 改为确定性调度后的内部结果。两者均为 frozen/slotted、provider-neutral dataclass。模型 Schema 必须精确拒绝 `start_time`、`end_time`、路线、状态、provider 和未知字段。

公开 `TripPlanRequest`、`TripPlanResponse`、`ItineraryItem`、前端类型和 Repository 快照不因本变更改变；估算时长和自动移除原因使用现有 `warnings`/`uncertainties` 表达。若实现发现必须新增公开字段，应触发停止条件并重新审批，不得在 Step 45H 静默扩展 API。

## Proposal 不变量

- 恰好两个按请求日期排序的 `ProposalDay`；
- 每日活动数量使用经用户确认的 MVP 上限；
- `location_id` 必须属于本次 POI 目录，`source_ids` 必须属于 POI 来源白名单；
- `priority_rank` 从 1 开始、日内唯一，数字越小优先级越高；
- 数组顺序是 LLM 的顺序建议；priority 只用于可选项取舍，不允许静默重排；
- `required` 活动不能被自动移除；`optional` 才可进入溢出策略；
- 时间类别只能来自冻结枚举，不能输出任意分钟、实际路线时长或 verified 声明；
- 同地点连续活动允许存在，后续路线链不生成自环路线；
- explanation/warnings 仍经过安全文本和长度限制。

## 游览时长与可信状态

内部引入独立的 `DurationBasis`，不复用金额 `CostConfidence`：

| 来源 | 内部状态 | 使用规则 |
| --- | --- | --- |
| 用户明确提供 | `user_provided` | 最高优先级；当前 F-001 公开请求尚不支持逐活动输入，只预留语义 |
| LLM 时长类别 | `estimated_model` | 只接受代码冻结的类别到分钟映射，不能标为 verified |
| 项目 POI 类别规则 | `estimated_rule` | LLM 给出 unknown 或缺少可用建议时使用，并产生 system 来源 uncertainty |
| 无任何可靠规则 | `unknown` | 分钟为空，禁止按 0 排程，进入 needs_input |

冻结优先级为 `user_provided → estimated_model → estimated_rule → unknown`。类别映射固定为 `short=60`、`standard=120`、`long=180` 分钟；F-001 当前 `scenic_area` 与 `museum` 的缺省规则均为 `standard=120` 分钟。所有估算必须在公开结果中形成现有 warning/uncertainty，不能宣称 verified。Step 45H 不得自行选择其他数值。

## 交通缓冲策略

对每个不同地点路线段使用固定、可解释、分钟级的系统规则：

- walking：实际路线时长 + 10 分钟；
- public transit：实际路线时长 + 15 分钟；
- 同地点连续活动：不查询路线，也不增加路线缓冲；
- 缓冲只影响时间骨架，不改写高德返回的 `RouteLeg.duration_minutes`；
- 结果通过现有 warning/uncertainty 说明缓冲是项目估算规则。

缓冲值已批准。不得为塞入更多活动而压缩缓冲或 provider 路线时长。

## 确定性调度算法

每个自然日独立执行，固定输入必须得到字节语义一致的活动顺序和分钟值：

1. 按 proposal 数组顺序读取活动；不按模型解释文本重新排序；
2. 解析每项游览时长；存在 unknown 且无类别规则时停止为 `needs_input`；
3. 从住宿到首项、活动之间、末项回住宿推导不同地点路线链；
4. 查询并严格验证所需实际路线，保留来源和时长；
5. 令游标为日窗口开始；首项开始时间为游标加首段路线时长和缓冲；
6. 每项结束时间为开始时间加游览时长；下一项按前一结束时间加实际路线和缓冲开始；
7. 末项结束后必须还能容纳返回住宿的实际路线和缓冲；
8. 所有计算使用整数分钟，不使用随机数、当前时间或浮点数；
9. 若完整 proposal 可容纳，形成现有 `PlanCandidate`；
10. 若不可容纳，按经批准的可选/必选策略处理一次；不得压缩游览时长、忽略路线、越过窗口或循环调用模型；
11. `DailyRoutePlan.validate()` 和 final validation 使用调度结果与 provider 路线独立复验，不能因调度器存在而删除。

### 路线调用预算

F-001 proposal 上限固定为每天最多 2 项。最坏情况下每日至多 3 个不同地点路线段，双日共 6 段；若每天各自动移除 1 项 optional，至多各增加 1 个新桥接路线，最坏共 8 段，仍符合现有高德路线逻辑预算。不得自行恢复每天 3 项或增加调用预算。

## 不可行与失败策略

### 可选活动溢出

每天最多自动移除一次最低优先级 `optional`：

- 不得移除最后一项活动，使某日变为空；
- 排序依据为较大的 `priority_rank`，相同时以 proposal 原顺序后的活动优先移除；
- 移除后只允许在剩余高德路线预算内补一个必要桥接路线；
- 公开计划必须保留 warning/uncertainty，说明存在未采用活动及稳定原因 `optional_activity_omitted_for_capacity`；
- 若一次移除后仍不可行，停止，不继续删第二项或再次调用 LLM。

### 必选活动溢出

进入 `conflict`，记录 `schedule_capacity_exceeded`；不得静默删除、缩短、越过窗口或变更用户日窗口。已知路线和时长已证明约束不可同时满足，因此不应伪装成 provider `failed`。

### 路线数据缺失

- `partial` provider 结果如果仍含通过 Schema 的可用 `RouteLeg`，可以排程，但最终任务必须保留 partial/uncertainty；
- 路线 `unavailable`、缺坐标或无可用 `RouteLeg` 时不能生成经过验证的精确时间；终态为 `failed`，retryable 跟随稳定 provider 错误；
- 不能继续沿用“没有路线数据但保留模型精确时间”的旧 partial 行为，因为 D-009 后模型不再提供时刻，且公开 `partial` 必须存在可用计划；
- 不能把缺失路线当作 0，也不能使用未批准的直线距离估算。

### 实际路线超过容量

按完整实际路线、缓冲和游览时长计算。存在 optional 时只执行上述一次受限移除；全部 required 或移除后仍超限则进入 `conflict`。final validation 仍必须能独立产生 `route_duration_exceeds_gap`/`route_conflict`，用于发现调度器或映射缺陷。

## Step 45F 诊断语义复审

当前代码把领域错误 `activity_visit_order_invalid` 映射为 `day_schedule_capacity_exceeded`，两者不等价：前者表示活动时间顺序或重叠不合法，后者应只表示“日窗口小于路线 + 缓冲 + 游览时长总需求”。该映射会把结构错误误报为容量不足。

目标闭集分层如下：

- proposal 阶段：JSON、Schema、日期、POI、来源、优先级、时长类别和安全文本；不再产生精确时间间隔诊断；
- scheduler 阶段：`activity_duration_unknown`、`route_data_unavailable`、`schedule_capacity_exceeded`、`optional_activity_omitted_for_capacity`；
- final validation 阶段：`activity_outside_day_window`、`activity_sequence_time_invalid`、`activity_overlap`、`route_chain_mismatch`、`route_duration_exceeds_gap`；
- Step 45F 的四类 `*_gap_not_positive` 仅作为迁移前旧 candidate 的回归诊断保留，迁移完成后不再由新 proposal 正常产生；
- `day_schedule_capacity_exceeded` 只在确定性容量计算有证据时使用，不再由 `activity_visit_order_invalid` 直接映射。

Step 45H 必须先用红测锁定这一语义，再删除或弃用不再可达的旧诊断；不得同时保留两套互相矛盾的“时间失败事实来源”。

## 状态机、API、Repository 和 UI 影响

- 状态 enum：不增加；继续复用 `planning`、`enriching_routes`、`validating` 和五种终态；
- 状态边：若 unknown 时长需要用户决定，增加 `planning → needs_input`；其余成功流不变；
- API Schema：推荐不变；现有 `warnings`、`uncertainties`、`violations` 和 `errors` 足以表达估算、移除、容量和路线失败；
- API 语义：路线完全缺失从“可形成 partial”收紧为“无法形成可执行计划时 failed”；需要更新契约和回归；
- Repository：仍只保存最终 `PlanningJobResult`，不持久化中间 proposal；端口和幂等语义不变；
- UI：不重设计，不新增页面；复用现有 partial/conflict/needs_input/failed 和 warning/uncertainty 展示；
- Public plan：继续输出带精确时间的现有 `ItineraryItem`，时间来源改为确定性调度器。

## PR 与范围策略

### 方案一：直接继续加入 PR #4

保持 D-008 单 PR 形式最直接，但 PR 已有约 120 文件范围例外，新 DTO、编排和调度测试会进一步放大 review、回滚和 CI 定位成本。

### 方案二：基于功能分支建立 stacked PR（已批准）

先按 Step 45H-0 独立授权把 Step 45B–45G 的既有修复和设计精确提交并推送到 PR #4；再从该功能分支创建 `feat/f-001-cr1-deterministic-scheduling`，实现 PR 以 `feat/f-001-single-city-two-day-plan` 为 base。该 stacked PR 只审查调度架构；合并回功能分支后，最终仍由 PR #4 作为面向 `main` 的完整 F-001 交付，兼顾 D-008 与可审查性。

### 方案三：关闭或重组 PR #4

回滚和历史整理成本最高，会丢失已经通过的远程 CI/审查上下文；除非 stacked PR 无法使用，不推荐。

用户已批准方案二，以及 Step 45H 影响 24–34 个文件、1200–2200 行的新范围例外。D-008 的 120 文件例外仍不自动覆盖其他新增范围；超过本次新上界必须立即停止并重新确认。

## Step 45H 红绿测试地图

```text
DeepSeek MockTransport
  → [RED] proposal 含 start_time/end_time 被拒绝
  → proposal parser
      ├─ [RED] 非法 POI/来源/日期/优先级/时长类别
      └─ [GREEN] 两日有序 PlanProposal
  → route-chain derivation
      ├─ 住宿→首项 / 活动间 / 末项→住宿
      ├─ 同地点无自环
      └─ 双日正常 ≤ 6 段，单次移除后总计 ≤ 8 段
  → deterministic scheduler
      ├─ 正常双日
      ├─ 窗口恰好容纳
      ├─ 超出 1 分钟
      ├─ walking/public-transit 缓冲
      ├─ unknown 时长
      ├─ optional 一次移除及 warning
      ├─ required 溢出 conflict
      └─ 固定输入重复运行完全一致
  → DailyRoutePlan + final validation
      ├─ 实际路线时长超限仍硬冲突
      ├─ 路线 partial-with-data
      ├─ 路线 unavailable 无 verified 时间
      └─ 调度器产物再次验证
  → executor → Repository → API
      ├─ ready / partial / conflict / needs_input / failed
      ├─ 公开 API Schema 不变
      ├─ warning/uncertainty/错误安全可见
      └─ 默认测试不读 .env.local、不访问 provider
```

必须先写失败测试，再写最小实现。LLM prompt/Schema 变化还需运行现有 Agent scorecard，并新增“模型不得输出最终精确时间”“相同 proposal 重复解析稳定”“模型选择顺序不覆盖代码冲突”评估。Step 45H 只运行离线门禁，不包含新的 live UAT。

## Step 45H 实施地图

1. 事实和范围预检：确认分支、工作区、批准文件清单、暂存区和离线隔离；
2. 红测冻结 `PlanProposal` 与精确拒绝时间字段；
3. 实现 proposal DTO、parser、DeepSeek generation/repair Schema；
4. 红测并实现时长类别、可信状态和 unknown 裁决；
5. 红测并实现不依赖精确时刻的住宿往返路线链推导；
6. 红测并实现纯确定性 scheduler；
7. 红测并实现一次 optional 移除、桥接路线预算和 required conflict；
8. 调整 orchestrator 顺序与状态边，保持 provider 端口不变；
9. 复用现有 `PlanCandidate`、`DailyRoutePlan` 和 final validation，删除旧时间猜测正常路径；
10. 更新 executor/API 失败语义和纵向测试；
11. 运行 Agent eval、专项测试、统一离线门禁、scope/secret/docs 检查；
12. 同步文档并停止，新的 live UAT、提交和 PR 写入分别等待单独授权。

## 文件影响范围估算

如果保持公开 API/前端不变，预计 Step 45H：

- 生产代码：8–12 个文件，新增 1 个纯调度模块，修改端口模型、candidate/proposal resolver、DeepSeek adapter、orchestrator、executor/状态边和导出；
- 测试：8–12 个文件，覆盖 proposal、scheduler、路线、终态、纵向链和离线隔离；
- 文档：8–10 个文件；
- 前端：预计 0 个生产文件，只有现有终态回归；
- 总计：约 24–34 个文件、约 1200–2200 行净变更。

该估算明显超出“小修复”，属于 D-008 之后的新架构范围；用户已批准该范围例外。若实施需要新增公开 DTO、前端交互或超过该上界，应立即停止并重新审批。

## 验收标准

1. LLM 输出 Schema 不含最终精确时间、路线或终态；
2. 代码以实际路线、明确缓冲和可追踪游览时长生成分钟级时间；
3. 相同输入、proposal、路线和固定时钟重复运行结果一致；
4. 住宿往返、活动间路线、同地点和路线时长边界通过独立校验；
5. unknown 不按 0，估算均产生可见 uncertainty；
6. optional/required 溢出严格遵循用户批准策略；
7. 路线无可用数据时不宣称已验证时间；
8. 公开 API、Repository 幂等和 UI 主体保持兼容；
9. 默认测试不读取 `.env.local`、不访问真实 provider；
10. 专项测试、Agent eval、统一离线门禁和文档检查通过。

## 风险、回滚和停止条件

主要风险：proposal 与 scheduled candidate 双模型漂移；自动移除导致未预期 POI 取舍；路线重查突破预算；估算时长被误解为 verified；新增状态边影响终态；PR 范围继续膨胀。

回滚边界：调度器位于独立 application 模块，provider 端口、公开 API 和 Repository 不变；可通过 `git revert` stacked PR 恢复到现有精确 candidate 流程，不使用破坏性重置。旧路径只在迁移期用于回归，不应长期通过 feature flag 双轨运行。

出现以下任一情况立即停止 Step 45H：

- 需要修改公开 API 或生产 UI 才能表达基础语义；
- 需要提高高德/DeepSeek/和风调用预算；
- 需要复杂求解器、路线矩阵或多轮模型重排；
- 预计超过 34 个文件或 2200 行净新增；
- 不能在不调用真实 provider 的情况下验证；
- 任何实现尝试放宽 `DailyRoutePlan`、日期、重叠、预算、来源或最终校验。

## 已批准实施决策

1. 每日活动上限从 3 收紧为 2，以保证正常双日路线不超过 6 段、每天一次 optional 调整后最坏不超过 8 段；
2. 时长类别固定为 `short=60`、`standard=120`、`long=180` 分钟；
3. `scenic_area` 和 `museum` 缺省使用 `standard=120` 分钟；
4. walking 每段增加 10 分钟缓冲，public transit 每段增加 15 分钟缓冲；
5. 每天最多自动移除一次最低优先级 optional，并公开 warning；
6. required 容量不足进入 conflict，unknown 时长进入 needs_input；
7. 无可用路线进入 failed；只有携带合法 `RouteLeg` 的 partial provider 结果才能形成 partial 计划；
8. 采用 stacked PR，实施分支为 `feat/f-001-cr1-deterministic-scheduling`，base 为 `feat/f-001-single-city-two-day-plan`；
9. Step 45H 获批 24–34 个文件、1200–2200 行的新范围例外。

上述设计、策略和范围已经批准。Step 45H 的生产实现仍必须由用户单独授权；新的 live UAT、提交、推送、stacked PR 创建、ready-for-review 和合并均不在本批准内。
