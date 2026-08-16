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

## 当前限制

- 本地应用模式的任务与结果保存于 SQLite；测试可显式注入内存 Repository，或在 `APP_ENV=test` 且未提供临时 SQLite 路径时使用内存替身；
- 已启动的后台规划不是持久化任务队列，应用退出时不会自动续跑进行中的外部调用；重启只恢复最后一次已提交的任务、attempt、结果和版本快照；
- 真实规划执行器只有在 DeepSeek、高德和和风三组配置全部就绪时启用；
- Step 38 只取得一次 live 契约证据；Step 39 和补充 Step 45A、45C、45E 均未取得 ready/partial 真实计划 UAT；Step 45H 已实现确定性调度器但只具备离线证据，不构成新的 live UAT 通过；
- SQLite 持久化由 F-002 接入；除新增单计划 DELETE 外，F-001 的 POST/GET/retry 形状保持不变。局部重规划、批量清空、历史列表、版本比较/恢复、多城市和交易能力仍不在当前范围内。
