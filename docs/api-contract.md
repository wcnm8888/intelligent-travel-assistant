# F-001 API 与数据契约

## 文档状态

本文件是 F-001 旅行计划 HTTP API、公开 DTO、状态和错误码的唯一权威说明。对应 Python Schema 位于 `backend/src/intelligent_travel_assistant/contracts/`。五种终态结果快照、POST/GET/retry、前端严格解析与有界轮询均已实现；F-002 保持这些公开契约不变，并在本地应用模式默认使用 SQLite Repository。三家 provider 配置全部就绪时，POST/retry 会调度真实规划执行器，否则只登记 `draft` 资源且不访问 provider。默认测试组合明确禁用本地 provider 配置和外部网络。

## 契约原则

- HTTP Schema、应用、Agent 和 adapter 只交换项目自有模型，不泄露 provider SDK 类型；
- 所有对象拒绝未知字段，ID 使用 UUID，时间戳必须带时区；
- 当地旅行日期和日内时间分开表达，F-001 的目的地时区固定按 `Asia/Shanghai` 解释；
- JSON 金额是十进制字符串，例如 `"100.00"`，不接受 JSON number；
- `unknown` 费用的金额必须为 `null`，不能使用 `0`；
- 计划和 provider 事实只引用已存在的 `source_id`；
- 原始 provider 错误、堆栈、Prompt、Key、JWT 和私钥不得进入公开响应；
- 前端可以做即时提示，但服务端 Schema 和确定性校验仍是权威边界。

## HTTP 资源

### 创建计划任务

`POST /api/trip-plans`

- 请求体：`TripPlanRequest`；
- 成功接收：`202 Accepted`，响应为 `TripPlanResponse`，初始可观察状态为 `draft` 或 `normalizing`；
- Header `Location` 指向 `/api/trip-plans/{job_id}`；
- 相同 `client_request_id` 和规范化后相同请求体返回原任务；使用同一本地 SQLite 数据库重启后仍保持该幂等语义，不重复产生外部调用；
- 相同 ID 对应不同请求体返回 `409 idempotency_conflict`；
- HTTP/Pydantic 格式错误返回 `422 input_invalid`，此时任务可以尚未创建。

### 查询计划任务

`GET /api/trip-plans/{job_id}`

- 存在时返回 `200 OK` 和当前 `TripPlanResponse`；
- 不存在或无效 ID 返回 `404 job_not_found`；使用同一本地 SQLite 数据库重启后，已保存任务仍可查询；
- 客户端轮询间隔第一版固定不低于 1 秒；终态后停止轮询；
- 服务端状态是事实来源，前端不得伪造中间阶段。

### 重试计划任务

`POST /api/trip-plans/{job_id}/retry`

- 只允许 `partial` 或 `failed` 且 `retryable=true` 的任务；
- 接受时返回 `202 Accepted`，沿用 `job_id` 和 `client_request_id`，增加 `attempt`，生成新 `trace_id`；
- 每个任务最多 3 个 attempt；
- 不可重试、已达上限或非终态任务返回 `409 retry_not_allowed`；
- `ready`、`conflict` 和 `needs_input` 不允许通过该接口盲目重试；用户必须新建或调整请求。

### 删除单个计划任务

`DELETE /api/trip-plans/{job_id}`

- 存在时原子删除该 job 及其 attempt、内部计划版本、来源关联、decision 和 acceptance 子记录，返回 `204 No Content`；
- 不存在或 ID 无效返回 `404 job_not_found`；
- 删除后相同 `client_request_id` 可创建新任务；
- 不提供批量删除、清空全部数据、历史列表、版本比较或恢复能力。

### 健康接口

现有 `GET /api/health` 契约保持不变，不依赖任何 provider 凭证。

## HTTP 状态与业务状态

HTTP 状态表示是否接受/找到资源；计划 `status` 表示业务阶段或结果。provider 失败通常写入已创建任务的终态和 `errors`，查询任务本身仍返回 `200`，不能把所有 provider 失败都变成 HTTP 5xx。

| HTTP | 项目错误 | 使用条件 |
| ---: | --- | --- |
| 202 | 无 | 创建或重试任务已接受 |
| 200 | 无 | 查询到任务，包括业务 `partial`、`conflict` 或 `failed` |
| 204 | 无 | 单个计划任务及其 job-owned 数据已删除 |
| 404 | `job_not_found` | 任务不存在或 ID 无效 |
| 409 | `idempotency_conflict` | 同一 client request ID 对应不同内容 |
| 409 | `retry_not_allowed` | 任务状态、次数或 retryable 不允许重试 |
| 422 | `input_invalid` | HTTP 请求无法通过公开 Schema |
| 500 | `internal_error` | 无法安全映射的本地缺陷；只返回安全摘要 |

## 创建请求

```json
{
  "client_request_id": "11111111-1111-4111-8111-111111111111",
  "city": "杭州",
  "start_date": "2026-08-15",
  "travelers": 2,
  "total_budget": { "amount": "4000.00", "currency": "CNY" },
  "preferences": {
    "interests": ["自然", "历史"],
    "free_text": "节奏不要太赶",
    "hard_constraints": []
  },
  "pace": "balanced",
  "transport_modes": ["walking", "public_transit"],
  "accommodation": {
    "area_or_poi": "西湖附近",
    "one_night_cost": { "amount": "700.00", "currency": "CNY" }
  },
  "day_windows": [
    { "day_offset": 0, "start_time": "09:00:00", "end_time": "20:00:00" },
    { "day_offset": 1, "start_time": "09:00:00", "end_time": "18:00:00" }
  ],
  "intercity_transport_cost": {
    "amount": "1000.00",
    "currency": "CNY"
  },
  "meal_budget_per_person_per_day": {
    "amount": "100.00",
    "currency": "CNY"
  }
}
```

规则：

- `start_date` 的动态 D+1 至 D+5 边界由注入时钟的领域校验器实现，不写死到静态 JSON Schema；
- 行程固定为 `start_date` 和次日，不接收可独立变化的 `end_date`；
- `transport_modes` 只允许 `walking`、`public_transit`；只选一种时所有路段使用该方式，同时选择时由确定性代码以公交为首选，并且只对首选结果不可用或未通过本地路线校验的路段尝试步行降级；
- 多方式降级仍受每任务最多 8 次路线调用约束；预算耗尽、两种方式均不可用、坐标缺失或路线端点/方式/来源不合法时停止为 `failed`，不得继续隐式调用；
- 餐饮默认 100 元/人/天，用户可修改；默认值和修改值都按明确规则标记为 `estimated`；
- `day_windows` 必须各包含 day 0 和 day 1，窗口顺序、重复和起止关系由后续确定性校验器验证；
- 住宿和城际费用缺失时进入领域后转换为 `unknown` 费用项，而不是零。

## 任务响应

所有 POST、GET 和 retry 成功响应使用同一个 `TripPlanResponse`：

```json
{
  "job_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
  "trace_id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
  "client_request_id": "11111111-1111-4111-8111-111111111111",
  "status": "collecting",
  "attempt": 1,
  "request_summary": {
    "city": "杭州",
    "start_date": "2026-08-15",
    "end_date": "2026-08-16",
    "travelers": 2,
    "budget": { "amount": "4000.00", "currency": "CNY" }
  },
  "resolved_destination": null,
  "plan": null,
  "violations": [],
  "warnings": [],
  "uncertainties": [],
  "sources": [],
  "errors": [],
  "retryable": false,
  "created_at": "2026-08-13T14:00:00+08:00",
  "updated_at": "2026-08-13T14:00:01+08:00"
}
```

终态响应保留同一 envelope，并按状态填充 `resolved_destination`、`plan`、`violations`、`uncertainties`、`sources` 和 `errors`。完整 happy/partial/conflict/failed 样例属于 Step 4。

`TripPlan.locations` 是计划内全部住宿锚点、POI、路线端点和天气地点的 provider-neutral 地点目录。`PlanDay`、`ItineraryItem`、`RouteLeg` 和 `WeatherSnapshot` 只能引用该目录中存在的 `location_id`；悬空地点引用必须被后续确定性校验拒绝。

## 状态机

F-001 当前可观察状态：

| 当前状态 | 允许的下一状态 |
| --- | --- |
| `draft` | `normalizing` |
| `normalizing` | `needs_input`、`collecting`、`failed` |
| `needs_input` | 无；用户修改输入后创建新任务 |
| `collecting` | `planning`、`partial`、`failed` |
| `planning` | `needs_input`、`enriching_routes`、`validating`、`failed` |
| `enriching_routes` | `validating`、`partial`、`failed` |
| `validating` | `ready`、`partial`、`conflict`、`planning`、`failed` |
| `ready` | 无 |
| `partial` | 仅经 retry 重新进入 `normalizing` |
| `conflict` | 无；用户需修改输入创建新任务 |
| `failed` | 仅在 `retryable=true` 时经 retry 重新进入 `normalizing` |

状态转换表由 `ALLOWED_PLANNING_TRANSITIONS` 冻结。应用状态机执行转换，Repository 以不可变 version 快照记录；模型、工具、HTTP adapter 和前端都不能直接改变状态。

## 最终状态

| 状态 | 必要语义 | plan |
| --- | --- | --- |
| `ready` | 硬校验通过，关键数据完整，预算可判定 | 必须存在 |
| `partial` | 存在可用计划，但数据、路线或预算不完整 | 必须存在 |
| `conflict` | 存在不可自动解决的硬冲突 | 可存在候选计划 |
| `needs_input` | 城市歧义、日期边界或必要输入需要用户修改 | 不存在 |
| `failed` | 关键链路无法形成安全计划 | 不存在 |

这些跨字段终态不变量由 `PlanningJobResult`、状态机和 Repository 的 `record_result` 共同执行；普通状态推进不能产生缺少结果载荷的终态。

## 金额与预算

`Money`：

```json
{ "amount": "100.00", "currency": "CNY" }
```

`CostItem` 规则：

- `verified`、`estimated`、`user_provided` 必须有非负金额；
- `unknown` 必须为 `amount: null`；
- 合法的零元必须有明确类别和依据，不能由缺失值转换；
- `known_total` 只累计非 unknown 项；
- 存在 unknown 且已知费用未超限时为 `budget_indeterminate`；已知费用已超限时仍为 `over_budget`。

## 来源、坐标和天气

- `SourceRecord.fetched_at` 必须带时区；`valid_until` 不知道时为空，并将 freshness 设为 `unknown_validity`；
- provider 为 `deepseek`、`amap`、`qweather`、`user` 或 `system`；
- 坐标系统当前只允许 `provider_native`、`wgs84`、`unknown`；在高德境内真实合同验证前，不把 provider 原生坐标误标为 WGS84；
- 和风当前预警作为抓取时正在生效的风险提示，不能描述为两日未来预警；
- `reference_url` 和 attribution 只保留可安全展示的 provider 元数据，不含凭证。

## 稳定错误码

| 错误码 | 默认重试 | 说明 |
| --- | --- | --- |
| `input_invalid` | 否 | 格式或请求级硬约束不合法 |
| `configuration_missing` | 否 | 本地缺少 provider 配置 |
| `provider_unauthorized` | 否 | provider 鉴权失败 |
| `provider_rate_limited` | 是 | provider 限流，仍受总预算约束 |
| `provider_timeout` | 是 | provider 超时 |
| `provider_unavailable` | 是 | provider 5xx 或暂时不可用 |
| `provider_schema_invalid` | 否 | provider HTTP/响应 envelope 无法通过 adapter Schema；不用于本地候选领域校验失败 |
| `data_missing` | 否 | 请求成功但关键数据缺失 |
| `data_stale` | 可按策略 | 数据已超过允许时效 |
| `model_output_invalid` | 最多一次修复 | 模型 JSON、日期、时间、POI/来源引用或字段不合法；修复后仍无效时对外发布该码 |
| `constraint_conflict` | 否 | 计划违反硬约束 |
| `budget_incomplete` | 否 | 未知费用导致预算不可完整判断 |
| `idempotency_conflict` | 否 | 同一请求 ID 对应不同内容 |
| `job_not_found` | 否 | 任务不存在或临时状态已丢失 |
| `retry_not_allowed` | 否 | 状态、次数或策略禁止重试 |
| `internal_error` | 否 | 未安全映射的本地缺陷 |

公开 `ApiError` 只包含稳定 code、安全 message、可选 field/provider、retryable 和 `diagnostic_code`。`diagnostic_code` 只能是项目自有、无值的安全枚举；不得包含 provider 原文、字段值、Prompt、凭证、异常或堆栈。

路线数据不能形成完整链时，安全诊断闭集为 `route_primary_unavailable`、`route_fallback_exhausted`、`route_coordinates_missing`、`route_result_invalid`、`route_call_budget_exhausted` 和 `route_deadline_exhausted`。诊断只描述失败类别，不包含日期、地点、坐标、路段端点或上游响应。`route_deadline_exhausted` 表示本地调用治理已无足够任务时限，公开为不可自动重试的高德 `data_missing`，不能降级为 `internal_error`。成功使用步行降级时通过现有 `warnings` 返回安全文案；每段最终 `RouteLeg.mode` 仍是实际采用方式。路线距离冻结为不超过 `2147483647` 米，单段时长冻结为不超过 `1440` 分钟；超界数据按 Schema/本地非法结果拒绝。

DeepSeek proposal 通过 adapter envelope 后仍不能通过本地校验时，公开错误保持 `model_output_invalid`、`retryable=false`。正常生产路径的诊断码由 generation/repair 阶段与 JSON、Schema、日期、POI/来源引用、安全文本或截断类别组成。旧精确时间 candidate 的 `time_invalid`、四类 gap 和 `day_schedule_capacity_exceeded` 诊断只保留 migration-only 回归，不再是 D-009 正常生产事实来源；只有内部结果缺少阶段或类别时才使用兼容兜底 `candidate_local_validation_failed`。诊断码不得包含模型原文、字段路径、字段值、时间值、地点或坐标。

## 前端类型映射

Step 23–27 实现前端类型时必须逐字段匹配本契约：

- UUID、date、time、datetime、Decimal JSON 均先作为 `string` 接收；
- 金额只能由项目金额解析器显示，不能 `Number(amount)` 后用于预算裁决；
- enum 使用与后端完全一致的字符串联合类型，不设置未知值为成功状态；
- 前端不重新计算预算、路线可行性或终态；
- 收到未知字段、非法 enum 或错误形状时进入安全协议错误，而不是宽松接受；
- OpenAPI 仅在计划路由实现后成为可生成类型的输入；在此之前不维护手写的第二份权威 DTO。

## D-009 兼容边界

D-009 及 F-001-CR1 已把最终精确时间交给确定性调度器，同时保持 HTTP Schema 不变。当前兼容边界为：

- `TripPlanRequest` 不增加逐活动时长字段；用户提供的逐活动时长语义只预留，不在本变更实现；
- `TripPlanResponse`、`ItineraryItem.start_time/end_time` 和五种终态保持不变；公开精确时间改由代码生成；
- 估算游览时长、交通缓冲和自动移除原因通过现有 `warnings`/`uncertainties`/`violations` 表达，不增加第二套 plan DTO；
- 路线 provider 的 `partial` 结果只有在仍携带合法 `RouteLeg` 时才能形成带计划的 `partial`；完全缺少路线时长不得把 unknown 当作 0，也不得宣称时间已验证；
- 混合方式计划允许各路段采用不同方式；scheduler 按每段实际 `RouteLeg.mode` 使用步行 10 分钟或公交 15 分钟缓冲，市内交通估算只计实际公交路段；
- 若游览时长无法由用户值、冻结时长类别或项目类别规则确定，使用现有 `needs_input`；`planning → needs_input` 已成为允许状态边；
- 已知路线、缓冲和游览时长超过日窗口时使用 `conflict`；不通过模型 repair 放宽容量。
- F-001 没有门票价格输入或可靠门票 provider，真实执行器必须保留 `ticket=unknown`，不得按 0 处理；因此完整可执行计划可合理收口为 `partial`，`ready` 继续由零 unknown 的冻结 API/Synthetic Executor 契约覆盖。

上述错误与终态语义已由 Step 45H 红绿测试、状态机和 executor → Repository → API 离线纵向回归锁定。公开字段和状态 enum 未增加；以后若需要扩展仍必须重新审批 API 变更。

## F-003 局部重规划 API（Step 1 冻结，Step 5 已实现）

F-003 保持既有 `POST/GET/retry/DELETE /api/trip-plans` 请求、响应和错误不变，尤其不向
`TripPlanResponse` 增加内部 job version 或 plan version。客户端以当前 `plan.plan_id` 作为
公开 baseline token；服务端在创建 replan 时内部捕获 job version 和 plan version。

### 创建 replan

`POST /api/trip-plans/{job_id}/replans`

- 请求体是 `ReplanRequest`，成功返回 `202 Accepted` 和 `ReplanResponse`；
- `Location` 指向 `/api/trip-plans/{job_id}/replans/{replan_id}`；
- 只允许当前计划为 `ready` 或具有可执行 plan 的 `partial`；
- 同一 job 下相同 `replan_request_id` 和同一规范化 command 返回原资源，不重复分析、确认或 Provider 调用；相同 ID 不同 command 返回 `409 replan_idempotency_conflict`；
- 影响分析在请求内同步完成且零 Provider 调用：仅 `same_day_low` 可直接进入 `replanning`，高影响返回 `awaiting_confirmation`，cross-city/越界操作返回 `422 replan_scope_not_supported`。

公共请求字段：

```json
{
  "replan_request_id": "11111111-1111-4111-8111-111111111111",
  "baseline_plan_id": "22222222-2222-4222-8222-222222222222",
  "command": {
    "operation": "adjust_activity_time",
    "target_activity_id": "33333333-3333-4333-8333-333333333333",
    "start_time": "10:00:00",
    "end_time": "12:00:00",
    "reason_code": "user_schedule_preference"
  }
}
```

`command` 是拒绝额外字段的 tagged union：

| operation | 必需字段 | 冻结约束 |
| --- | --- | --- |
| `replace_activity` | `target_activity_id`、`replacement_categories` | 1–3 个安全结构化类别；不接收 provider ID、完整自然语言或完整活动对象 |
| `delete_activity` | `target_activity_id` | 目标必须属于 baseline；删除后的计划仍须完整重校验住宿往返和其他硬边界 |
| `adjust_activity_time` | `target_activity_id`、`start_time`、`end_time` | 目的地当地 time，结束晚于开始，活动日期不可改变 |
| `reorder_activities` | `local_date`、`ordered_activity_ids` | 必须是该日完整、无重复、无新增的现有 activity ID 排列 |

`reason_code` 可空且只允许项目自有安全代码。服务端不接收或持久化完整自然语言修改请求。

### 查询与决定

- `GET /api/trip-plans/{job_id}/replans/{replan_id}`：存在时 `200 OK`；不存在或 job/replan 不匹配返回 `404 replan_not_found`。它是单资源查询，不构成历史列表；客户端只轮询 `analyzing` 或 `replanning`；
- `POST /api/trip-plans/{job_id}/replans/{replan_id}/decision`：请求只允许 `{ "choice": "approve" }` 或 `cancel`；新的 approve 返回 `202` 并进入 `replanning`，cancel 返回 `200` 和 `cancelled`；
- 相同决定重放返回当前资源且不重复执行；相反决定返回 `409 confirmation_conflict`；过期返回 `409 confirmation_expired` 并稳定收口为 `expired`；baseline 或 job version 漂移返回 `409 version_conflict`；
- 决定只对已展示且持久化的 impact snapshot 生效，不能改变 command 或扩大受影响集合。

### ReplanResponse

公开响应精确包含：

```text
job_id, replan_id, replan_request_id, trace_id, baseline_plan_id,
operation, status, impact, confirmation_expires_at, decision,
result, change_set, errors, created_at, updated_at
```

- `status` 只允许独立 replan lifecycle 的十个值，不复用 `PlanningStatus`；
- `impact` 在分析完成后非空，包含有序去重的 categories、direct_refs、transitive_refs、affected_dates、route_refs、budget_effect、source_actions、required_validations 和 `confirmation_required`；分析前可为空；
- `decision` 只包含可空 `decision_id/choice/decided_at`，不回显自由文本；
- `result` 仅在 `completed` 时为当前 `TripPlanResponse`，其他状态为空；
- `change_set` 仅在 completed 时非空，包含 baseline/result plan ID 和 added/removed/changed refs、route/schedule/cost/source change codes；只比较本次 baseline→result；
- `errors` 只含现有安全 `ApiError` 形状，不含 provider body、Prompt、异常、秘密或完整请求。

新增稳定 HTTP 错误边界：

| HTTP | 项目错误 | 使用条件 |
| ---: | --- | --- |
| 404 | `job_not_found` / `replan_not_found` | job 或指定 replan 不存在 |
| 409 | `replan_idempotency_conflict` | 同一 replan request ID 对应不同 command |
| 409 | `version_conflict` | baseline plan 或内部 job version 已漂移 |
| 409 | `confirmation_conflict` | 已记录相反决定或当前状态不允许决定 |
| 409 | `confirmation_expired` | 15 分钟确认窗口已过 |
| 409 | `replan_not_allowed` | 当前 job 没有 ready/可执行 partial baseline |
| 422 | `input_invalid` | tagged command 格式、引用或字段不合法 |
| 422 | `replan_scope_not_supported` | 跨城市、改日期/住宿、增加活动或其他越界操作 |
| 500 | `internal_error` | 无法安全映射的本地缺陷；原计划保持不变 |

业务 `needs_input/conflict/failed/rejected` 作为已创建 replan 的 `200 GET` 状态返回，不统一转换为 HTTP 5xx。任何失败都不能把原计划投影为 completed。

## 当前限制

- 本地应用模式的任务与结果保存于 SQLite；测试可显式注入内存 Repository，或在 `APP_ENV=test` 且未提供临时 SQLite 路径时使用内存替身；
- 已启动的后台规划不是持久化任务队列，应用退出时不会自动续跑进行中的外部调用；重启只恢复最后一次已提交的任务、attempt、结果和版本快照；
- 真实规划执行器只有在 DeepSeek、高德和和风三组配置全部就绪时启用；
- Step 38 只取得一次 live 契约证据；Step 39 和补充 Step 45A、45C、45E 均未取得 ready/partial 真实计划 UAT；Step 45H 已实现确定性调度器但只具备离线证据，不构成新的 live UAT 通过；
- SQLite 持久化由 F-002 接入；除新增单计划 DELETE 外，F-001 的 POST/GET/retry 形状保持不变。F-003 Step 5 已实现三个可注入的 replan 端点、严格 DTO 和安全错误映射；默认组合不自行启用 Provider 或后台恢复。F-004B1 Step 0–8 已实现并归档独立 V3 contracts、Repository/SQLite/API typed 集成、离线 planning/调用治理、前端严格 V3 交互/本机 job 指针恢复、临时 SQLite 纵向和 loopback desktop/390px；城际 Provider 调用为 0，且没有真实 Provider UAT。批量清空、历史列表、版本比较/恢复、真实城际 Provider 和交易能力仍不在范围内。

## F-004A version 2 多日契约（已实现并交付）

### 请求判别与 URI

现有 URI 全部保留。`POST /api/trip-plans` 的 body 是严格联合：

- 没有 `request_version`：只按现有 `TripPlanRequest` 校验；旧字段、默认值、额外字段拒绝和请求指纹完全不变；
- `request_version` 精确为字符串 `"2"`：只按 `TripPlanRequestV2` 校验；
- 其他版本、`null`、数字 2、同时满足不了对应模型或多余字段：422 `input_invalid`；不得回退尝试另一版本。

FastAPI/OpenAPI 使用 callable discriminator + tagged union 表达“缺失=legacy、`2`=V2”，不把 endpoint 降为未约束 `dict`，也不增加 envelope。若实现无法保持该 oneOf 和既有客户端请求，必须停止，不得自行新增 `/api/v2`。

### `TripPlanRequestV2`

| 字段 | 类型 | 规则 |
| --- | --- | --- |
| `request_version` | literal string | 必须为 `"2"` |
| `client_request_id` | UUID | 与 legacy 相同的幂等键 |
| `city` | string | 与 legacy 相同；一个中国大陆城市 |
| `start_date` | date | 目的地当地 D+1 至 D+5 |
| `end_date` | date | 含首尾共 2–7 日，必须连续且晚于开始日 |
| `travelers`、`total_budget` | legacy 类型 | 规则不变 |
| `preferences`、`pace`、`transport_modes` | legacy 类型 | 不新增模式或自由 Prompt |
| `accommodation` | legacy 类型 | 一个住宿区域/POI；一晚金额可空 |
| `day_windows` | 2–7 个 V2 window | offset 精确为 `0..day_count-1`，唯一、正时长、不跨夜 |
| `intercity_transport_cost` | Money/null | 保留用户聚合输入；不代表本任务支持跨城或实时票价 |
| `meal_budget_per_person_per_day` | Money | 默认和 legacy 相同 |

V2 window 的 `day_offset` 是严格整数 0–6；bool、字符串和越界值拒绝。字段顺序不影响指纹，但字段集合和数组顺序参与 canonical JSON；只排除 `client_request_id`。

### V2 任务响应

POST、GET 和 retry 对 V2 job 返回 `TripPlanResponseV2`：

- 保留 job/trace/client ID、status、attempt、retryable、resolved destination、violations、warnings、uncertainties、sources 和 errors 的现有语义；
- 新增顶层 `response_version="2"`；V2 request summary 含 `request_version="2"`、start/end date、travelers 和 budget；
- `plan` 为 `TripPlanV2 | null`；非空时含 `plan_format_version="2"`，days 长度为 2–7 且逐日覆盖请求日期；
- V2 `PlanDay` 每日最多 2 项活动、最多 3 条路线；来源、天气、费用和 unknown 形状复用现有类型；
- legacy response 不增加 `response_version`、`request_version`、`plan_format_version` 或其他字段。

GET/retry 的 response union 由持久化请求版本决定，不能由 Accept header、查询参数或客户端猜测切换。DELETE 继续返回 204；同 client ID/同版本同 body 复用，同 client ID/任何字段或版本不同返回既有 409 `idempotency_conflict`。

### Replan 兼容

- legacy 双日行为不变；
- V2 恰好 2 日可使用现有三个 replan URI，并返回与 job request version 对应的 typed plan；
- V2 3–7 日创建 replan 返回 422 `replan_scope_not_supported`；检查发生在 replan reserve、decision、executor 和 Provider 前；
- 拒绝路径不得创建 replan/decision/lineage/plan version，不修改 job/current plan/version，不调 Provider；
- 不新增多日 replan command、历史列表、版本比较或恢复 API。

### 稳定错误和兼容门禁

F-004A 不新增稳定错误码。日期跨度、窗口集合和版本字段错误使用 422 `input_invalid`；幂等冲突、Repository version 冲突、retry/delete/not-found 和安全 500 保持现有映射。legacy golden 必须逐字段、逐 JSON 形状保持不变；synthetic legacy 请求的 SHA-256 fingerprint 固定为 `f8e8a85d192745f703d968695945c2fa4200f224d4e8ae9162a69abd57bf7edd`。

## F-004B1 version 3 多城市契约（Step 0–8 已实现并归档）

### 版本判别与 URI

现有 POST/GET/retry/DELETE 和三个 replan URI 全部保留。`POST /api/trip-plans` 的严格联合扩为：

- 缺少 `request_version`：只校验 legacy；
- `request_version` 精确为字符串 `"2"`：只校验 V2；
- `request_version` 精确为字符串 `"3"`：只校验 V3；
- 其他值、数字/null、版本 tag 与字段集合冲突、额外字段或模糊形状：422 `input_invalid`，不得回退另一 model。

FastAPI/OpenAPI 继续使用 callable discriminator + tagged union，不接受无约束 `dict`，不新增 `/api/v3`、header 或 query version。legacy/V2 的 OpenAPI 分支、请求和响应键集合不变。

### `TripPlanRequestV3`

V3 是独立严格模型，不继承单城市字段集合：

| 字段 | 类型 | 冻结规则 |
| --- | --- | --- |
| `request_version` | literal string | 必须为 `"3"` |
| `client_request_id` | UUID | 现有幂等键 |
| `start_date/end_date` | date | 含首尾 3–7 日；开始日沿用 D+1 至 D+5 |
| `day_windows` | 3–7 个 V2 window | offset 精确为 `0..day_count-1`，唯一、正时长、不跨夜 |
| `travelers/total_budget` | 现有类型 | 1–8 人，CNY Decimal 规则不变 |
| `preferences/pace/transport_modes` | 现有类型 | 只允许现有步行/公交与 allowlist 文本 |
| `city_stays` | 2–3 个 `CityStayV3` | 有序、城市文本唯一；每项至少 1 夜 |
| `intercity_segments` | 1–2 个 `UserProvidedIntercitySegmentV3` | 精确为城市数减 1，按相邻索引排序 |
| `meal_budget_per_person_per_day` | Money | 规则和默认值不变 |

V3 不接受顶层 `city`、`accommodation` 或 `intercity_transport_cost`。`sum(city_stays[*].nights) == day_count - 1`；2 城最少 3 日，3 城最少 4 日。

`CityStayV3`：

| 字段 | 类型 | 冻结规则 |
| --- | --- | --- |
| `city` | CityText | 中国大陆城市；文本和解析后 adcode 均须唯一 |
| `nights` | strict int | 1–6；参与总夜数校验 |
| `accommodation` | AccommodationRequirement | 每城独立区域/POI与可空一晚金额 |

`UserProvidedIntercitySegmentV3`：

| 字段 | 类型 | 冻结规则 |
| --- | --- | --- |
| `from_city_index/to_city_index` | strict int | 第 i 段必须为 i → i+1 |
| `mode` | enum | `rail`、`air`、`coach` |
| `departure_station/arrival_station` | ShortText | 必填站点名称；不接受票号、证件或乘客信息 |
| `departure_at/arrival_at` | timezone-aware datetime | 必须为 `+08:00`、同一派生转移日且 arrival > departure |
| `fare` | Money/null | 非空即 `user_provided`；空值为 unknown，不代表 0 |

派生转移日为 `start_date + sum(city_stays[0..i].nights)`；跨夜、日期不符、同日第二次转移、第三城市、非相邻索引和重复首城闭环均在 422 前置校验中拒绝。

### V3 plan 与响应

`TripPlanV3` 为独立 plan shape：

- `plan_format_version="3"`、plan ID、start/end date；
- 按用户顺序排列的 2–3 个 `city_adcodes`；
- 最多 32 个 `locations`，覆盖每城住宿、活动和用户站点；
- 1–2 个 `PlanIntercitySegmentV3`；
- 3–7 个 `PlanDayV3` 和现有 `BudgetSummary`。

`PlanIntercitySegmentV3` 固定包含 segment ID、相邻城市索引、mode、出发/到达 station location ID、带时区时间、一个城际 `CostItem` 和非空 user source IDs。票价缺失仍创建 `confidence=unknown/amount=null` 的费用项；用户票价为 `confidence=user_provided`，不能标记 verified/estimated。

`PlanDayV3` 复用 local date、住宿 location、activities、local routes 和 weather，并新增 `departure_city_index/arrival_city_index/overnight_city_index/intercity_segment_id`：

- 非转移日三索引相同、segment ID 为空、1–2 项活动；
- 转移日索引必须为 i/i+1/i+1、segment ID 非空、最多 1 项活动；
- 活动只能位于当天出发/到达城市；local route 两端必须同城，每日最多 3 段；
- 站点与住宿/活动衔接只使用现有步行/公交 route，不把城际段投影为 `RouteLeg`。

POST、GET、retry 对 V3 job 返回独立 `TripPlanResponseV3`：顶层 `response_version="3"`，保留现有 job/status/attempt/warning/uncertainty/source/error 字段；使用 2–3 个 `resolved_destinations` 代替单数 `resolved_destination`；`request_summary` 为 `TripRequestSummaryV3`，字段精确为 `request_version="3"`、有序 `city_stays[{city,nights}]`、start/end date、travelers 和 budget；`plan` 只允许 `TripPlanV3|null`。legacy/V2 响应不新增复数字段。

### 缓冲、来源、状态和错误

- 铁路出发前/到达后 60/30 分钟，航空 120/60，长途客运 45/30；窗口或路线不能容纳时返回 terminal conflict，而不是改写用户时间；
- user source 使用 `provider=user`、`source_type=user_provided_intercity_segment`、本地记录时间、`valid_until=null`、`freshness=unknown_validity` 和安全 warning；不含外部 URL/record ID，不声称班次、票价、余票或库存已验证；
- 未核验 availability 本身不阻止 ready，因为它是明确排除的外部能力；但票价/天气/路线等参与预算或执行判断的 unknown 继续产生 partial；
- shape、城市数、夜数、段数、索引、时区和跨夜错误使用 422 `input_invalid`；城市解析歧义进入 `needs_input`；确定性连续性/缓冲冲突进入 `conflict`；必要编排失败进入 `failed`；
- F-004B1 不新增顶层 HTTP error code。稳定 violation/uncertainty code 冻结为 `multicity_city_order_invalid`、`multicity_nights_invalid`、`multicity_day_continuity_invalid`、`multicity_accommodation_invalid`、`intercity_segment_order_invalid`、`intercity_time_invalid`、`intercity_buffer_conflict`、`intercity_fare_unknown` 和 `intercity_user_provided_unverified`；不得包含原始字段值。

### Fingerprint、Repository、SQLite 与 replan

- V3 fingerprint 对原始 typed V3 dump 排除 `client_request_id` 后使用现有 sort-keys/compact UTF-8 canonical JSON + SHA-256；城市、夜数、数组顺序、时间、站点和 fare 均参与；
- 同 client ID/同 V3 body 复用；任何字段、顺序或版本不同返回既有 409 `idempotency_conflict`；legacy 固定 digest 和 V2 golden 不变；
- `PlanningJobRepository` 方法集合不变；legacy/V2 `PlanningJobResult` 保持原 shape，新增 `PlanningJobResultV3` 与内部 `PlanningResult` union，typed request/plan/result union 一致增加 V3；format mismatch、损坏 JSON、未知 tag 和跨 request plan/result 均 fail closed；
- SQLite schema 仍为 version 2，migration 表只能有 1/2；V3 只进入既有 request_json/plan_json/source/version 事务，不新增列、表、索引或 migration；
- 旧应用读取 V3 fail closed，不 down migration、不删除记录；
- 对任何 V3 job 创建 replan 都返回既有 422 `replan_scope_not_supported`。检查在 service 获取、reserve、decision、executor、Provider 和任何写入前；数据库新增 replan/decision/lineage/plan version 数均为 0，job/current plan/version 不变。

## F-005 同 shape 失败与时效投影（Step 1 冻结）

F-005 不增加 URI、HTTP envelope、公开顶层错误码或 JSON 键。legacy、V2、V3 各自现有 exact-key shape、discriminator、fingerprint 和 response model 保持不变；只在原有 `errors`、`warnings`、`uncertainties`、`sources`、`status` 与 `retryable` 字段中发布已存在的安全语义。

### 终态与公开错误矩阵

| 原因 | 关键链路 | 可选事实/仍有可执行计划 | 公开 retryable | 恢复语义 |
| --- | --- | --- | --- | --- |
| 用户可修正的缺失/歧义 | `needs_input` | 不适用 | false | 返回修改；必须有安全 `field` 才能归入该类 |
| 确定性硬冲突 | `conflict` | 不适用 | false | 修改约束；不能通过 retry 改变 |
| `provider_unauthorized` | `failed` | `partial` | false | 检查本机 Provider 配置 |
| `provider_timeout` / `provider_rate_limited` / `provider_unavailable`，内部 retry 已耗尽 | `failed` | `partial` | true | 稍后执行既有 job retry |
| `provider_schema_invalid` / 非用户原因的 `data_missing` | `failed` | `partial` | false | 服务数据当前不能安全使用；不盲目重试 |
| 最终采用路线 `data_stale` | 去除该路线；无合法替代时 `failed` | 未采用候选不投影 | true | 重新获取并重跑 |
| 天气/预警/地点 `data_stale` | 保留可执行计划为 `partial` | `partial` | true | 可查看已验证部分或重跑 |
| `model_output_invalid` | `failed` | 不存在模型降级 plan | false | 返回修改或稍后重新创建；不执行 transport retry |

`ready` 的 `errors` 必须为空，且不能靠 warning 隐藏 stale、unknown-validity 或参与决策的未验证事实。`partial` 必须有可执行 plan，并在现有 error/uncertainty/source 中指出缺口；`failed` 不得携带假计划。Provider failure 不投影成 `needs_input` 或 `conflict`。

### `data_stale`、validity unknown 与诊断

- stale 使用既有公开 `data_stale`。`provider` 取现有 Provider 枚举文本；`message` 使用项目固定安全文案；`field` 仅在现有契约允许且确有用户字段时填写；`retryable` 按上表。
- capability 只通过现有可空 `diagnostic_code` 的闭集发布：`route_source_stale`、`location_source_stale`、`weather_forecast_stale`、`weather_alert_stale`。不得带 location ID、日期、坐标、URL、原始 record ID 或字段值。
- `unknown_validity` 不是 `data_stale`，继续由 SourceRecord freshness 和既有 uncertainty 表达；它不得被改写为 fresh。retry 同一次调用不能创造不存在的 `valid_until`，因此该 uncertainty 本身不设置 retryable。
- retry runtime 可使用的安全诊断闭集为 `provider_attempt_timeout`、`retry_budget_exhausted`、`retry_deadline_exhausted` 和 `retry_after_invalid`；公开时仍必须搭配既有顶层错误码，不新增计数、delay、header 或 body 字段。
- response 顶层 `retryable` 表达“原因是否允许既有 planning job retry”，与 `attempt` 分开。attempt 3 即使原因可重试，前端也不再展示 retry，既有 retry endpoint 继续拒绝超过上限的请求。

### 兼容与持久化边界

- GET 返回任务完成时持久化的来源 freshness 快照；不得因读取时墙钟变化改写 plan、status、errors 或 fingerprint。retry/replan 新 attempt 才使用新的显式评估时刻。
- SQLite 仍只持久化现有 typed request/result/plan/source/error；HTTP attempt 记录、retry delay、active peer、Prompt、原始响应和安全运行诊断均不进入数据库。schema version 仍为 2，migration 集合仍为 1/2。
- F-003 replan 的独立 attempt/lifecycle、失败保持原计划、来源 reuse/refresh/drop 和确认边界不变；V3 replan 继续在 runtime、Provider 和写入前拒绝。
- legacy/V2/V3 golden 测试逐键比较正常、partial、failed、data_stale、unknown/null、retryable 和 attempt 3；任何新增键、缺失键、跨版本投影或旧 fingerprint 漂移都阻断交付。

## F-004C version 4 用户已购铁路段契约（Step 1 冻结）

F-004C 复用现有 `POST /api/trip-plans`、`GET /api/trip-plans/{job_id}`、`POST /api/trip-plans/{job_id}/retry` 和 `DELETE /api/trip-plans/{job_id}`。请求以字符串 `request_version="4"` 进入独立 strict model；缺少 version 仍只进入 legacy，`"2"`/`"3"` 仍只进入原模型，数字、`null`、未知版本、tag/字段冲突和任何额外键均返回既有 422 `input_invalid`，不得模糊回退。

### V4 request exact shape

`TripPlanRequestV4` 的顶层键精确为：

```text
request_version, client_request_id, start_date, end_date, travelers,
total_budget, preferences, pace, transport_modes, city_stays,
intercity_segments, day_windows, meal_budget_per_person_per_day
```

除 tag 外，通用字段沿用 V3 的类型和约束：总行程 3–7 日、2–3 个唯一有序中国大陆城市、总夜数等于 `day_count - 1`、窗口精确覆盖每天、段数精确为城市数减 1。V4 不接受单城市 `city/accommodation/intercity_transport_cost`，也不接受订单、乘客、证件、座位、二维码、截图、Cookie、自由备注、Provider 或 duration 字段。

V4 的 `preferences` 使用独立 strict allowlist，精确只含 `interests`（最多 5 个既有 `ShortText`）；`free_text`、`hard_constraints` 或其他额外键均返回既有 422 `input_invalid`，且拒绝发生在 planning job reserve/持久化/执行之前。legacy/V2/V3 继续使用各自既有 preferences shape，不因 V4 收窄而改变。

每个 `BookedRailIntercitySegmentV4` 的键精确为：

| 字段 | 类型 | 冻结规则 |
| --- | --- | --- |
| `from_city_index` / `to_city_index` | strict int | 第 i 段必须为 i → i+1 |
| `mode` | `Literal["rail"]` | 必填且只能为 rail；air/coach 拒绝 |
| `service_number` | strict string | 先 `strip()`，再 `upper()`；规范化后必须匹配 `^[A-Z0-9]{1,12}$` |
| `departure_station` / `arrival_station` | strict ShortText | trim 后 1–120 字符，控制字符拒绝；只表达站名 |
| `departure_at` / `arrival_at` | aware datetime | 必须为 `+08:00`、同一派生转移日且 arrival > departure |
| `fare` | Money / null | 已知时必须为正数 CNY；未知为 `null`，不得用 0 代替 |

`service_number` 接受如 `" g1234 " → "G1234"`；内部空格、连字符、斜杠、非 ASCII 字母数字、空串、超过 12 字符、数字 JSON 值或 `null` 均拒绝。不维护前缀 allowlist，不校验车次是否真实存在。单个 segment 结构本身表示“同日直达”：没有经停、换乘、分段、跨夜或 availability 字段；这不是 Provider 核验。

派生转移日继续为 `start_date + sum(city_stays[0..i].nights)`。铁路缓冲继续为出发前 60 分钟、到达后 30 分钟。历时只由规范化的发到时间在服务端确定性计算，用于排程/展示校验；不成为 request、plan 或 response 新键。

### V4 plan、response 与来源 exact shape

`TripPlanV4` 的键集合与 V3 多城市 plan 对应，唯一 version-specific 变化为 `plan_format_version="4"`，且 `intercity_segments` 元素使用 `PlanBookedRailSegmentV4`。每个计划段在 V3 段键集合上增加规范化 `service_number`，同时把 `mode` 收窄为字符串 `"rail"`；仍包含 segment ID、相邻索引、站点 location ID、发到时间、一个城际 `CostItem` 和非空 source IDs。不得增加 duration、订单、座位、票号、余票、库存或 Provider record 字段。

票价为 `null` 时，计划仍创建 `category=intercity_transport`、`confidence=unknown`、`amount=null` 的费用项并以既有 `intercity_fare_unknown` 披露；已知正数票价为 `confidence=user_provided`，不得标记 verified/estimated。

`TripPlanResponseV4` 的顶层键与 V3 plural-destination response 精确相同，唯一 tag 为 `response_version="4"`；`request_summary` 键集合也与 V3 相同，tag 为 `request_version="4"`，不回显 `service_number`。`plan` 只允许 `TripPlanV4|null`，`resolved_destinations` 为 0–3 个。tag 不匹配、V4 response 携带 V3 plan、V3 response/plan 携带 `service_number`、未知/额外/缺失键均 fail closed。

每个 V4 城际段只引用一个现有形状的用户来源：`provider=user`、`source_type=user_provided_intercity_segment`、`provider_record_id=null`、`valid_until=null`、`freshness=unknown_validity`、`reference_url=null`、attribution 为“用户提供”、warning 为“未核验班次、票价、余票或库存”。UI 合并展示“用户提供，未核验”。`fetched_at` 仅表示本地记录时刻，不证明车次当前有效。

与 D-013 一致，明确的用户输入及其排程校验通过本身不因 `unknown_validity` 强制降为 partial，但也绝不能表述为 Provider 验证；任何 unknown 票价、天气/路线缺口或其他既有 partial 事实继续阻止 ready。ready 文案只能是“代码校验通过”，不能是“班次已核验”。

### Fingerprint、Repository、SQLite 与 replan

- V4 fingerprint 使用规范化 typed V4 dump，排除 `client_request_id`，再执行现有 UTF-8、sort-keys、compact JSON、SHA-256；规范化相同的 `" g1234 "`/`"G1234"` digest 相同，车次、城市/夜数/数组顺序/站点/时间/fare/version 任一变化必须改变 digest；
- legacy 固定 digest、V2/V3 typed body 与 golden 必须逐字节不变；不得先把旧版本升级成 V4 再算指纹；
- 内部新增独立 `PlanningJobResultV4(resolved_destinations, TripPlanV4|null, terminal fields)`，并将 request/plan/result union 严格增加 V4；V3 result 类型不扩字段，跨版本 request/result/plan 一律拒绝；
- Repository Protocol、attempt、幂等、retry、DELETE、30 天 job 生命周期和事务不变。V4 只进入 schema v2 既有 typed `request_json/result_json/plan_json/source` 路径；Schema SQL 和 migration 文件字节不变，migration 表只能为 1/2；
- 旧应用读取 V4 必须 fail closed，不降级为 V3，不删除或改写旧记录；
- 创建 V3 或 V4 replan 均在 replan reserve、decision、executor、Provider/runtime、lineage 和 plan write 前返回既有 422 `replan_scope_not_supported`；拒绝路径相关写入和城际 Provider 调用均为 0。由于这些 job 不可能创建 replan 资源，后续伪造的 GET/decision ID 沿用既有 404/安全错误，不新增 URI 或错误码；
- V4 POST/GET/retry/DELETE 顶层 job/error envelope、HTTP status、Location、attempt 3、idempotency conflict 和 retry-not-allowed 行为与现有版本一致。
