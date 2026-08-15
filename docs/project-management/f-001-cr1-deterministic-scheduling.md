# F-001-CR1：确定性时间排程责任调整

## 变更元数据

- 所属任务：`F-001 单城市双日旅行计划垂直切片`
- 变更类型：架构变更控制
- 任务等级：`L` 级任务内的高风险跨层变更
- 当前状态：`IMPLEMENTED / REVIEWED / READY_FOR_REVIEW`
- 关联决策：`D-009`
- 当前分支：`feat/f-001-cr1-deterministic-scheduling`
- 当前 stacked PR：[#5](https://github.com/wcnm8888/intelligent-travel-assistant/pull/5)，base 为 `feat/f-001-single-city-two-day-plan`；上层 PR：[#4](https://github.com/wcnm8888/intelligent-travel-assistant/pull/4)
- 设计 Step：补充 `Step 45G`
- 实施 Step：补充 `Step 45H`，已完成实现；Step 45I–45X 已完成 QA、修复、提交、远程 CI、UAT 和文档收口；等待 stacked 合并

本变更卡的获批详细设计已经由 Step 45H 实现。实现没有破坏公开 API 端点或 DTO 字段形状，但记录了路线数值安全上界和 `planning → needs_input` 的兼容性语义调整。PR #5 已完成提交、推送、Windows CI 和独立远程 review；Step 45T 真实 UAT 为 PASS（完整双日 partial，非关键 unknown 未按 0），当前等待按 stacked 顺序合并。

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

用户已批准方案二，以及 Step 45H 影响 24–34 个文件的范围例外；Step 45J 为测试和文档 findings 把新增行上限调整为 2600。D-008 的 120 文件例外仍不自动覆盖其他新增范围；超过本次新上界必须立即停止并重新确认。

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
- 总计：约 24–34 个文件；Step 45J 批准后的新增行上限为 2600。

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
9. Step 45H 获批 24–34 个文件范围例外；Step 45J 将新增行上限调整为 2600。

上述设计、策略和范围已经批准并由 Step 45H 完成离线实现。模型正常路径只生成无最终时刻 proposal，确定性 scheduler 生成现有带时间 candidate；旧时间候选解析仅用于迁移回归。新的 live UAT、独立 QA、提交、推送、stacked PR 创建、ready-for-review 和合并均不在本 Step 授权内。

## Step 45H 实施结果

- 新增严格 `PlanProposal`、`ProposalDay`、`ActivitySelection` 及 required/optional、short/standard/long/unknown 闭集；
- DeepSeek generation 与唯一一次 repair 共享 proposal Schema，精确禁止最终时间、路线、verified、provider 和终态字段；
- 新增纯确定性 scheduler，先推导路线要求并取得合法 `RouteLeg`，再用冻结时长、方式缓冲和日窗口生成 `PlanCandidate`；
- 每天最多一次 optional 移除，桥接路线仍受 8 次总预算限制；required 溢出、unknown、路线 unavailable 与 partial-with-data 均按批准终态发布；
- `planning → needs_input` 已成为允许状态边，公开五种终态 enum 不变；
- 现有 `DailyRoutePlan` 和 final validation 继续独立复验，未放宽日期、重叠、路线、预算或来源规则；
- 默认测试保持 `APP_ENV=test`、dotenv 禁用和非 loopback 网络阻断；没有读取 `.env.local` 或仓库外私钥；
- 统一离线门禁通过：后端 818 项、前端 64 项、文档检查器 23 项，以及格式、lint、strict typecheck、build、锁文件和文档契约全部绿色；
- Step 45H 没有执行 live UAT、暂存、提交、推送、PR 写入或合并。最新 live 结论仍是 Step 45E `FAIL`。

## Step 45I 独立审查结果

- 审查开始时完整工作区范围为 27 文件、`+2158/-281`，与批准的 24–34 文件、1200–2200 新增行例外一致；同步本 Step 允许的五份脱敏结论文档后仍为 27 文件，当前总差异为 `+2188/-286`。暂存区为空、无 upstream、无新增依赖或范围外文件；
- D-009 的生产职责迁移已完成：DeepSeek 正常路径只产生无最终时刻 proposal，代码依据实际路线和冻结规则排程，现有 `DailyRoutePlan` 与 final validation 独立复验；未发现 P0/P1 生产缺陷；
- P2 测试缺口包括 proposal 重复键/日期/POI/来源负例、五终态纵向 API 投影、被移除 optional 路线错误不污染最终结果，以及完整时长/类别缺省直接断言；
- `api-contract.md`、`testing-strategy.md`、`docs/README.md` 仍有 D-009 实施前后的语义漂移，需要与测试缺口一起在待批准 Step 45J 收口；
- 专项 127 项与统一离线门禁通过，统一入口包含后端 818 项、前端 64 项、文档检查器 23 项；provider 配置为空且非 loopback 网络被阻断，没有读取本地凭证或调用真实 API；
- 审查结论为 `REVIEW_COMPLETE_WITH_FINDINGS`。在 Step 45J 修复并复验前，不得精确暂存、提交、推送或创建 stacked PR；Step 46 和新的 live UAT 仍未授权。

## Step 45J findings 关闭结果

- Proposal 三层重复键、未知字段、日期、POI/来源负例与 repair 脱敏，60/120/180 和两类 120 分钟缺省均已直接锁定；
- 真实纵向链覆盖当前可达的 partial、conflict、needs_input、failed；门票 unknown 不按 0，ready 由零 unknown 冻结契约覆盖；
- optional 历史路线错误不污染最终结果，route partial 的 retryable/source/uncertainty 与 omission warning 均通过 GET API 复验；
- 专项 125 项与统一门禁通过：后端 838、前端 64、文档检查器 23；最终 27 文件、`+2559/-297`，低于批准上限。Step 45J 未修改生产代码、调用 provider、暂存、提交、推送或修改 PR；下一动作是待批准 Step 45K。

## Step 45K–45L 交付与独立 review

- 27 文件形成提交 `bb52adea871c6cadc21ceaa5ef4255b79c3904cb` 并由 stacked Draft PR #5 交付；base 为 `feat/f-001-single-city-two-day-plan`，Windows offline verification run `31867996619` 通过；
- Step 45L 独立 review 复核 D-009 职责、proposal/scheduler、五终态、8 次路线预算、Step 45J 测试和秘密边界；专项 147 项与文档检查器 23 项通过，当时未发现阻塞真实 UAT 的生产缺陷；
- PR #4/#5 均保持 Draft，尚未 ready 或合并。

## Step 45M 真实 UAT 结果

- 唯一真实任务取得 DeepSeek proposal、和风数据及部分高德路线事实，但必要路线未全部可用，最终以高德 `data_missing`、`retryable=false`、无计划进入 `failed`；真实 UAT 为 `FAIL`；
- 来源计数为 user 1、system 1、高德 7、和风 2、DeepSeek 1；无 provider 原始响应，因此不推测具体路线或地点，也不从来源数虚构精确 HTTP 次数；
- 桌面/窄屏、归因、freshness、AI 披露、安全错误、控制台和秘密扫描符合边界；只有 1 次 POST，无 retry 或第二个任务，临时产物和本地服务已清理；
- 发现三个待修契约：同时允许步行/公交时当前只选公交且没有 fallback；路线不可用的公开 `data_missing` 缺少 `route_data_unavailable` diagnostic；前端状态图缺少后端已允许的 `planning → needs_input`。在纯离线修复和复验前不得再次 live 或进入 Step 46。

## Step 45N 多交通方式与安全诊断收口

- 同时允许公交和步行时，确定性执行器以公交为首选，仅对首选不可用或未通过本地路线校验的路段尝试步行；单方式请求不变；
- 全部必要首选路段先按稳定顺序查询，降级只使用剩余路线预算，首选、降级和 optional 桥接共同受最多 8 次硬上限；
- 每段最终路线必须匹配高德 provider、端点、请求 mode 和本次 source IDs；scheduler 按实际 mode 使用对应缓冲，费用只统计实际公交段；
- 成功降级追加安全 warning，未采用结果不污染最终来源、错误或 retryable；失败诊断闭集为 primary unavailable、fallback exhausted、coordinates missing、result invalid 和 call budget exhausted；
- 前端状态图已与后端 `planning → needs_input` 对齐。专项 479 项、前端 65 项通过，冻结运行时统一门禁包含后端 842 项、前端 65 项和文档检查器 23 项且完整绿色；以上仍只有 synthetic/fake 纵向证据，不改变 Step 45M 的 UAT `FAIL`，也不授权再次 live。

## Step 45O–45P 路线可靠性复审与修复

- Step 45O 证明 provider-wide 错误盲目降级、路线 deadline 被发布为 `internal_error`、超大路线数值以及非法来源/错误归属仍阻塞 live；
- Step 45P 将降级白名单收紧为业务空结果和无 provider error 的本地非法路线；AUTH、Schema、timeout、rate limit、server、unknown 不再切换 mode。路线按稳定顺序最多两路并发分批，总调用仍受 8 次硬预算；
- 新增 `route_deadline_exhausted`，冻结单段距离 `2147483647` 米和时长 `1440` 分钟；只有 provider、端点、mode、数值和来源引用精确一致的结果能进入 scheduler/公开投影；
- POI 与路线错误保持 operation 归属，wrong-provider、非法或额外来源不公开。专项 157 项及统一门禁通过，包含后端 859 项、前端 65 项和文档检查器 23 项。以上只有离线证据，Step 45M UAT `FAIL` 不变，提交、远程 CI 和新 live 均待后续单独批准。

## Step 45Q–45R 并发停止语义复审与修复

- Step 45Q 纯离线证明 Step 45P 的停止语义仍只停在批次内部：同批 terminal 与可降级结果混合时仍会启动 fallback；裸 `asyncio.gather` 的一路异常也不会取消和等待同批 peer。两项均阻塞真实 UAT；
- Step 45R 将 terminal 提升为显式 batch-level 状态。当前已在途批次允许收口，但任一 terminal 均阻止后续首选批次与所有 fallback；业务空结果和无 Provider error 的本地非法路线仅在无 terminal 时降级；
- 并发异常路径先取消并 drain 所有未完成 peer，再传播原异常。纵向测试证明终态发布前 governor 的活动路线调用数为 0，且没有后续批次或 fallback；
- 定向 10 项、路线专项 182 项及统一门禁通过，统一入口包含后端 869 项、前端 65 项和文档检查器 23 项。以上仍只有离线证据，Step 45M UAT `FAIL` 不变；Step 45N–45R 尚未提交、推送或远程复验。

## Step 45S 独立离线复审与 live 准入

- 独立复核 26 个工作区文件、`+1574/-98`、stacked PR 关系、batch-level terminal、并发异常清理、governor、错误优先级、retryable 与来源投影，未发现 P0/P1 生产缺陷；
- 专项 233 项和统一门禁再次通过，统一入口包含后端 869 项、前端 65 项和文档检查器 23 项；外部任务取消的只读运行时探针也证明 peer 被清理、活动路线调用归零且无遗留任务；
- 仓库仍应在最终提交前补入外部任务取消和 fallback 批次 terminal 的持久回归，并把 `architecture.md` 中路线批次语义的 Step 归属更新到 Step 45R。这些是非阻塞收口项，不阻塞用户另行批准一次受控 live；
- Step 45M UAT `FAIL` 保持不变，Step 45N–45S 仍未提交、推送或远程复验。本 Step 未读取凭证、调用 Provider、执行 live、暂存、提交、推送或修改 PR。

## Step 45T 受控真实数据 UAT

- 唯一真实任务形成完整双日 `partial` 计划，真实 UAT 为 `PASS`；每天 2 项活动和 3 段合法公交路线，确定性时间窗口、无重叠、住宿往返、路线时长及固定缓冲全部通过；
- 3 项费用保持 unknown，已知合计 520 元，预算为 `budget_indeterminate`；公开来源计数为 user 1、system 1、高德 9、和风 2、DeepSeek 1；
- 所有必要公交路线本次直接可用，因此未触发步行 fallback。该结果验证主路线成功链，不替代混合 mode fallback 的离线纵向证据；
- 桌面/窄屏、来源、freshness、AI 披露、unknown、安全日志和秘密扫描通过；只有一个任务，无 retry、截图、原始响应、持久缓存或真实路线证据文件。Step 45N–45T 尚未提交、推送或远程复验，Step 46 继续阻塞。

## Step 45U 提交前离线收口

- 六类 provider-wide terminal 首次出现在 fallback 两路并发批次的行为已进入持久纵向测试：当前在途批次完成后不启动后续 fallback，公开 code、`route_primary_unavailable` 与 retryable 保持冻结语义，无效路线不进入来源、warning 或路线 uncertainty；
- 外部取消测试由 `asyncio.Event` 确认两路 peer 均进入等待后取消外层规划 task；两路 peer 均 cancel/drain，`CancelledError` 原样传播，governor 活动路线调用归零，没有后续批次或遗留 task；
- `architecture.md` 已明确 Step 45N–45P 建立基础降级/信任边界，Step 45R 最终闭合 batch-level terminal 与 peer 清理。两份核心测试 115 项、路线/调度/executor/Repository/API 专项 292 项通过；统一门禁通过后端 876 项、前端 65 项和文档检查器 23 项。Step 45T 的 live `PASS` 和未自然触发 walking fallback 的边界保持不变；本 Step 没有真实 Provider 调用、生产代码修改、暂存、提交、推送或 PR 修改。
