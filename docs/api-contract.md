# F-001 API 与数据契约

## 文档状态

本文件是 F-001 旅行计划 HTTP API、公开 DTO、状态和错误码的唯一权威说明。对应 Python Schema 位于 `backend/src/intelligent_travel_assistant/contracts/`。五种终态结果快照、POST/GET/retry、前端严格解析与有界轮询均已实现；三家 provider 配置全部就绪时，POST/retry 会调度真实规划执行器，否则只登记 `draft` 资源且不访问 provider。默认测试组合明确禁用本地 provider 配置和外部网络。

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
- 相同 `client_request_id` 和规范化后相同请求体在进程存活期间返回原任务，不重复产生外部调用；
- 相同 ID 对应不同请求体返回 `409 idempotency_conflict`；
- HTTP/Pydantic 格式错误返回 `422 input_invalid`，此时任务可以尚未创建。

### 查询计划任务

`GET /api/trip-plans/{job_id}`

- 存在时返回 `200 OK` 和当前 `TripPlanResponse`；
- 不存在、已因进程重启丢失或无效 ID 返回 `404 job_not_found`；
- 客户端轮询间隔第一版固定不低于 1 秒；终态后停止轮询；
- 服务端状态是事实来源，前端不得伪造中间阶段。

### 重试计划任务

`POST /api/trip-plans/{job_id}/retry`

- 只允许 `partial` 或 `failed` 且 `retryable=true` 的任务；
- 接受时返回 `202 Accepted`，沿用 `job_id` 和 `client_request_id`，增加 `attempt`，生成新 `trace_id`；
- 每个任务最多 3 个 attempt；
- 不可重试、已达上限或非终态任务返回 `409 retry_not_allowed`；
- `ready`、`conflict` 和 `needs_input` 不允许通过该接口盲目重试；用户必须新建或调整请求。

### 健康接口

现有 `GET /api/health` 契约保持不变，不依赖任何 provider 凭证。

## HTTP 状态与业务状态

HTTP 状态表示是否接受/找到资源；计划 `status` 表示业务阶段或结果。provider 失败通常写入已创建任务的终态和 `errors`，查询任务本身仍返回 `200`，不能把所有 provider 失败都变成 HTTP 5xx。

| HTTP | 项目错误 | 使用条件 |
| ---: | --- | --- |
| 202 | 无 | 创建或重试任务已接受 |
| 200 | 无 | 查询到任务，包括业务 `partial`、`conflict` 或 `failed` |
| 404 | `job_not_found` | 任务不存在或进程重启后已丢失 |
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
- `transport_modes` 只允许 `walking`、`public_transit`，同时选择表示混合模式；
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
| `planning` | `enriching_routes`、`validating`、`failed` |
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

公开 `ApiError` 只包含稳定 code、安全 message、可选 field/provider、retryable 和 `diagnostic_code`。`diagnostic_code` 只能是项目自有、无值的安全枚举，例如 `response_envelope_invalid` 或 `candidate_local_validation_failed`；不得包含 provider 原文、字段值、Prompt、凭证、异常或堆栈。

## 前端类型映射

Step 23–27 实现前端类型时必须逐字段匹配本契约：

- UUID、date、time、datetime、Decimal JSON 均先作为 `string` 接收；
- 金额只能由项目金额解析器显示，不能 `Number(amount)` 后用于预算裁决；
- enum 使用与后端完全一致的字符串联合类型，不设置未知值为成功状态；
- 前端不重新计算预算、路线可行性或终态；
- 收到未知字段、非法 enum 或错误形状时进入安全协议错误，而不是宽松接受；
- OpenAPI 仅在计划路由实现后成为可生成类型的输入；在此之前不维护手写的第二份权威 DTO。

## 当前限制

- 任务与结果只存于进程内 Repository，进程退出后丢失；
- 真实规划执行器只有在 DeepSeek、高德和和风三组配置全部就绪时启用；
- Step 38 只取得一次 live 契约证据，Step 39 尚未取得 ready/partial 真实计划 UAT；
- 局部重规划、SQLite 持久化、多城市和交易能力不属于 F-001。
