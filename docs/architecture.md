# 系统架构

## 文档状态

本文件定义 Intelligent Travel Assistant 当前批准的目标架构。B-000 建立了工程基线和健康检查；F-001 已冻结 provider-neutral 契约、领域校验和 provider 端口，并建立离线 fake、显式状态机、应用编排、调用治理、DeepSeek 本地严格解析/单次修复、最终确定性裁决、任务资源 API、React 旅行需求表单、受控轮询与 retry、五种终态界面，以及按完整本地配置条件装配的 DeepSeek、高德、和风 HTTP adapter 和真实规划执行器。F-002 Step 2–4 已在同一 Repository 端口后实现本地 SQLite 基础设施、持久化 adapter 和现有 API 装配。synthetic 五终态已通过真实本机浏览器闭环；Step 38 取得一次脱敏 live 契约证据，Step 45T 已取得完整双日 partial 的通过式真实 UAT。产品仍保留 PARTIAL 边界：unknown 费用不按 0 处理，混合交通 fallback 的真实质量未宣称覆盖。

## 系统目标

系统需要在本地把用户旅行需求、外部事实、大模型规划和确定性校验组合成可追溯的结构化计划，并在数据缺失或服务失败时保持可解释的部分结果。

架构优先保证：

- 核心业务不依赖 UI、数据库、第三方 SDK 或具体模型；
- 大模型提出计划，但不能覆盖代码校验和人工确认边界；
- 外部事实保留来源、获取时间、有效期和不确定性；
- 每次工具调用、计划版本和重规划决定可通过 `trace_id` 关联；
- 单日修改尽量局部化，跨日、跨城或住宿变更必须先确认；
- 默认测试离线，真实 API 验证独立且默认关闭。

## 运行与交付边界

- 架构形态：后端采用模块化单体，不拆分微服务；
- Agent 形态：单编排 Agent + 多个简单领域工具 + 显式状态机，不采用多 Agent；
- 运行位置：用户本机；
- 客户端：浏览器中的轻量 React Web UI；
- 服务端：绑定 `127.0.0.1` 的 FastAPI；
- 持久化方向：本地 SQLite，经 Repository 隔离；
- 外部网络：只在用户配置后由后端适配器访问 DeepSeek、高德和和风天气；
- 不包含公网部署、登录、多租户、队列、分布式锁或实时协作。

## 系统上下文

```text
┌──────────────┐       local HTTP       ┌──────────────────────────┐
│ React Web UI │ ─────────────────────> │ FastAPI Application API  │
└──────────────┘ <───────────────────── └────────────┬─────────────┘
                                                     │
                                                     v
                                      ┌──────────────────────────┐
                                      │ Travel Planning Core     │
                                      │ Orchestrator + State     │
                                      │ Domain + Validators      │
                                      └───────┬─────────┬────────┘
                                              │         │
                                  repository  │         │ provider ports
                                              v         v
                                        ┌────────┐  ┌─────────────────┐
                                        │ SQLite │  │ Provider Adapters│
                                        └────────┘  └────┬────┬───────┘
                                                        │    │
                                                DeepSeek│    │高德 / 和风天气
```

浏览器不直接持有或调用第三方 Key。所有外部访问、重试、限流处理、Schema 校验和脱敏日志都位于后端边界。

## 分层与依赖方向

```text
Presentation
  ↓
Application
  ↓
Domain
  ↑
Ports
  ↑
Adapters / Infrastructure
```

依赖规则：

- `domain` 只包含旅行计划概念、规则、值对象和确定性校验，不导入 FastAPI、SQLite、第三方 SDK 或 UI 类型；
- `application` 负责用例、状态转换、事务边界和人机确认流程，依赖领域和端口；
- `agent` 属于应用编排能力，调用领域服务和窄工具端口，不直接访问 SDK、数据库或全局变量；
- `ports` 定义应用需要的能力和项目自有结果模型；
- `adapters` 实现端口，负责第三方认证、传输、重试、Schema 转换和错误映射；
- `api` 把 HTTP Schema 转为应用命令，并把应用结果转为响应；
- `web` 只负责输入、展示、交互反馈和用户确认。

## 计划目录结构

```text
backend/
  pyproject.toml
  src/intelligent_travel_assistant/
    api/
      routes/
      schemas/
      dependencies/
    application/
      commands/
      ports/
        models.py
        providers.py
      services/
      state_machine/
    domain/
      trip/
      itinerary/
      budget/
      constraints/
      provenance/
    agent/
      orchestrator/
      prompts/
      tool_catalog/
    adapters/
      fakes/
      deepseek/
      amap/
      qweather/
      persistence/
    observability/
    config/
  tests/
frontend/
  src/
    app/
    features/trip-planning/
    components/
    services/
    types/
  tests/
scripts/
docs/
```

目录只在对应任务有真实内容时创建。公共抽象必须由重复或替换需求驱动，不为空想扩展预建框架。

## 模块边界

| 模块 | 职责 | 输入 | 输出 | 禁止依赖 |
| --- | --- | --- | --- | --- |
| Web UI | 表单、计划展示、来源、冲突和确认交互 | API view model、用户操作 | HTTP 请求、可见状态 | 第三方 Key、SDK、领域规则实现 |
| API | HTTP 校验、用例调用、错误到响应映射 | HTTP Schema | 应用命令与响应 | 第三方 SDK、预算计算 |
| Application | 用例编排、状态机、计划版本和确认流程 | 命令、端口结果 | 用例结果、事件、持久化请求 | UI 组件、具体数据库、第三方类型 |
| Agent Orchestrator | 需求解释、工具选择、POI/顺序提议和说明 | 结构化请求、领域状态、工具目录 | 不含最终精确时间的结构化 proposal、决策记录 | 直接网络、直接 SQL、最终精确时间、隐藏副作用 |
| Domain | 旅行请求、行程、费用、约束和来源规则 | 领域值 | 校验结果、派生值 | FastAPI、React、SDK、文件系统 |
| Ports | 外部能力与 Repository 契约 | 项目自有输入模型 | 项目自有结果模型 | provider SDK 类型 |
| Adapters | 第三方传输、鉴权、转换、错误映射 | 端口调用 | 标准结果 envelope | 业务规划决策 |
| Persistence | 计划、trace、来源和确认记录持久化 | Repository 命令 | 领域对象或持久化结果 | UI、模型 Prompt |
| Observability | 结构化日志、trace 关联、运行指标 | 安全事件数据 | 本地日志和诊断 | 秘密、完整 Prompt 或原始敏感响应 |

## 核心数据模型方向

以下领域概念已在 F-001 Step 3 冻结为 provider-neutral 契约方向，但不是数据库 Schema；动态规则和业务实现仍在后续 Step：

| 模型 | 关键内容 | 核心约束 |
| --- | --- | --- |
| `TripRequest` | 目的地、日期、人数、预算、偏好、交通和住宿要求 | 日期有效，必要输入明确，保留用户原始约束 |
| `TravelerPreferences` | 兴趣、节奏、无障碍、饮食和避免项 | 可区分硬约束与软偏好 |
| `TripPlan` | 版本、状态、日期范围、逐日计划、预算和警告 | 每个版本不可原地覆盖，关联 trace |
| `PlanDay` | 当地日期、住宿城市、活动和交通段 | 日期唯一，活动顺序可校验 |
| `ItineraryItem` | POI、活动、开始/结束时间、停留时长 | 时间为正，地点和来源可追踪 |
| `LocationRef` | provider-neutral 标识、名称、类别、坐标和地址 | 不把高德类型泄漏到领域模型 |
| `RouteLeg` | 起终点、方式、距离、预计时长和来源 | 起终点连续，时长非负，保留获取时间 |
| `WeatherSnapshot` | 地点、预测时段、天气、预警和有效期 | 匹配计划日期，过期必须标记 |
| `CostItem` | 类别、金额、币种、可信状态和依据 | `unknown` 金额为空，金额不可为负 |
| `SourceRecord` | provider、记录 ID、获取时间、有效期、用途和警告 | 可关联到使用它的计划字段 |
| `ConstraintViolation` | 规则、严重级别、影响对象和说明 | 由确定性规则产生，不能被 LLM 删除 |
| `ReplanRequest` | 基线版本、修改目标、用户意图和影响范围 | 必须引用现有版本，扩大影响需确认 |
| `DecisionRecord` | decision ID、提议、校验结果和确认状态 | 可解释且关联 trace |
| `PlanProposal` | LLM 提议的两日有序 POI、优先级、必选/可选和时长类别 | 不含最终精确时间、路线、provider 或终态 |
| `ScheduledPlanCandidate` | 代码根据实际路线和时长规则生成的分钟级活动时间 | 输入固定则结果稳定，必须再经领域校验 |

金额使用十进制定点语义；默认币种为人民币 `CNY`，但币种仍作为显式字段。日期和时间使用目的地当地上下文；需要绝对时间时使用带时区值。

### F-001 纯领域基础

Step 5 已在 `domain/foundation.py` 建立不依赖框架的最小领域基础：

- `Money` 和 `CostEntry`：非负 CNY、两位精度、unknown/known/verified 语义；
- `SourceRecord` 和 `SourceCatalog`：带时区获取时间、有效期顺序、来源 ID 唯一和引用存在性；
- `Coordinates` 和 `Location`：坐标范围、六位 adcode、非空来源；
- `RouteLeg`：不同起终点、非负距离、正时长和来源；
- `WeatherForecast`：最低温不高于最高温，并保留地点和来源；
- `PlanStructure`：单城市地点目录以及住宿、活动、路线和天气地点引用完整性。

该领域包只依赖 Python 标准库，并由 AST 测试禁止 FastAPI、Pydantic、HTTP、数据库和 provider SDK 依赖。公开 `contracts` 负责序列化，纯 `domain` 负责不变量；应用服务已显式完成请求、候选、终态与公开 DTO 之间的映射，领域层仍不依赖传输模型。

Step 6 在 `domain/trip_request.py` 增加 `TripRequestInput`，负责城市、双日日期、人数、偏好和自由文本的规范化与确定性校验：

- 应用边界必须显式传入评估时刻，领域代码不读取系统当前时间；
- 评估时刻转换为上海 UTC+08:00 后计算包含边界的 D+1 至 D+5；
- 公开请求只传 `start_date`，应用映射时派生 `end_date = start_date + 1 day`，领域层仍验证严格顺序和连续性；
- Windows Python 基线没有内置 IANA tzdata，因此当前及未来五天的上海民用时间使用标准库固定 UTC+08:00 表达，不新增运行依赖；
- 输入文本先做首尾空白清理，再检查长度和规范化后的重复偏好；不会改变公开 DTO 字段或隐式放宽类型。

Step 7 在 `domain/schedule.py` 增加纯领域时间规则：

- `DailyAvailability` 只接受 day offset 0/1 和无时区的目的地本地时间，开始时间必须严格早于结束时间；
- `ActivityTimeSlot` 以本地日期和无时区 wall-clock time 表达单日活动，零时长、反向和跨夜活动均拒绝；
- `TwoDayTimePlan` 要求窗口恰好覆盖 offset 0/1，活动必须属于双日范围并完整落在对应窗口内；
- 重叠检测按日期分组后在副本上排序，相邻活动允许首尾相接，任何正时长交叠均拒绝，调用方输入顺序保持不变；
- 窗口按 `day_offset` 匹配而非元组位置，避免反序输入导致日期错绑。

Step 8 在 `domain/route_validation.py` 增加路线链裁决：

- `DailyRoutePlan` 根据“住宿锚点 → 按时间顺序的活动地点 → 住宿锚点”建立期望路线链；
- 相邻地点相同时不要求无意义的自环路线；不同地点之间必须存在正的可用交通分钟；
- 已提供路线必须按顺序匹配期望链，额外段、反向段、错端点或乱序段属于确定性冲突；
- 提供链可以是期望链的有序子序列，未匹配段以 `RouteValidationStatus.MISSING` 和 `ExpectedRouteLeg` 返回，不冒充完整验证；
- 路线时长可恰好填满“窗口开始至首活动、活动之间、末活动至窗口结束”的间隔，超出一分钟即拒绝；
- 校验器不调用高德、不补路、不重排活动，也不调整用户时间。

Step 9 在 `domain/budget.py` 增加预算汇总与裁决：

- `BudgetCostItem` 保留费用 ID、类别、可信状态、金额和来源，继续强制 unknown 无金额、known 有金额、verified 有来源；
- `summarize_budget` 仅累加 verified、estimated 和 user_provided 金额，unknown 只增加 `unknown_count`，不会按零参与合计；
- 金额先精确转换为整数分后相加，再还原为两位 CNY `Decimal`，不受进程全局 Decimal context 精度影响；
- `known_total > budget` 时始终为 `over_budget`；否则存在 unknown 为 `budget_indeterminate`；全部已知且不超预算才是 `within_budget`；
- 已知合计恰好等于预算视为未超支，但若仍有 unknown，结果继续不可判定；
- 汇总保留调用方费用顺序，不获取或推测任何价格。

自动排程、provider 结果、状态执行和编排仍属于后续 Step。

## 外部结果契约

所有外部端口使用统一方向的结果 envelope：

```text
status: ok | partial | unavailable
data: provider-neutral typed data | null
provider: deepseek | amap | qweather
fetched_at: timestamp | null
valid_until: timestamp | null
warnings: list[warning]
error_code: stable project error code | null
retryable: boolean
source_records: list[SourceRecord]
```

规则：

- `partial` 必须说明缺失字段和可用字段；
- `unavailable` 不得携带伪造的成功数据；
- 无法确定有效期时 `valid_until` 为空并产生警告；
- provider 原始错误映射为稳定项目错误码，原始信息只在脱敏诊断中保留；
- 适配器必须校验响应 Schema、单位、坐标、时间和枚举后再返回领域数据。

F-001 Step 10 已在 `domain/provider_result.py` 固化 provider-neutral 基础：

- `ProviderResult` 只接受 DeepSeek、高德和和风三类外部 provider；有可用数据时必须提供带时区获取时间和同 provider 来源；
- `ok` 要求数据且无错误，`partial` 要求可用数据、稳定错误和安全警告，`unavailable` 要求无数据/时间/来源且必须有稳定错误；
- `ProviderErrorCategory` 将 timeout、rate limited、server、auth、schema、empty result 和 unknown 映射为项目错误码；只有 timeout、rate limited 和 server 可重试；
- 错误对象不保存 provider 原始 message、异常或 body；警告只允许单行短文本，并拒绝 URL、Authorization 和常见 Key/Token/Secret 标记；
- 有数据但 `valid_until` 为空时必须明确警告有效期未知；freshness 使用显式评估时刻，`evaluated_at <= valid_until` 为 fresh，之后为 stale；
- 本模型不定义 provider 端口、不依赖 SDK/HTTP，也不执行重试或外部调用。

F-001 Step 11 已在 `application/ports/` 固化三组窄端口：

- `AmapPort`：`resolve_city`、`search_pois` 和单段 `calculate_routes`；
- `QWeatherPort`：`get_weather_forecast` 和 `get_current_weather_alerts`；
- `DeepSeekPort`：为兼容既有窄端口保留 `generate_plan_candidate` 和 `repair_plan_candidate` 方法名，但二者只返回 provider-neutral 的未信任 `ModelTextOutput`；生产应用层严格解析后只能形成无最终时间的 `PlanProposal`，模型不得形成 scheduled candidate 或宣告终态；
- 所有方法均为异步、只接收一个冻结 typed request，并返回带具体 payload 类型的 `ProviderResult`；
- 端口 DTO 使用项目自有 dataclass/领域值，不包含裸 dict/Any、Key、JWT、Header、Base URL、HTTP/SDK request 或 provider 私有响应；
- 端口层禁止依赖 FastAPI、Pydantic、HTTP 客户端、SDK、settings、config、adapters、infrastructure 或环境变量；鉴权、传输和重试仍由后续 adapter 负责。

F-001 Step 12 已在 `adapters/fakes/` 建立三组端口级测试替身：

- 每个端口方法拥有独立的有序 `ProviderResult` 脚本，调用按适配器全局序号记录冻结 typed request 快照；
- 未配置脚本与脚本耗尽使用不同稳定错误，不提供默认成功、循环返回或隐式兜底；
- fake 配置强制 provider 匹配、synthetic 警告和 `synthetic_` 来源类型；不可用结果虽没有来源，也必须带 synthetic 警告；
- fake 不读取环境变量，不访问网络，不 sleep、不自动重试，也不包含真实 provider 转换逻辑；
- 生产入口不默认装配 fake。它们只服务后续离线状态机与编排测试，不能作为真实服务可用性证据。

F-001 Step 14 已在 `application/services/` 建立最小离线编排边界：

- `OfflinePlanningOrchestrator` 只通过构造函数接收 `AmapPort`、`QWeatherPort` 和 `DeepSeekPort`，不读取配置或选择具体 adapter；
- 顺序收集城市、POI、天气和当前预警，生成候选后只请求首两个活动间的一段路线；完整住宿往返路线补全仍属于后续 Step；
- 城市、POI 或 DeepSeek 不可用时进入 `failed`；天气、预警、路线不可用或任一可用结果为 partial 时进入 `partial`；
- happy 候选停在 `validating`，只有后续确定性校验才能裁决为 `ready`、`partial` 或 `conflict`；
- 编排 outcome 冻结并保留原始 typed `ProviderResult`，应用层不改写 provider 来源、错误类别或时效信息；
- 当前编排已接入调用预算、deadline 和一次候选结构修复，但不执行 HTTP retry、Repository 或真实传输行为。

F-001 Step 15 已在 `application/tooling/` 建立调用治理边界：

- 五个 `PlanningToolName` 与 DeepSeek 候选生成/修复组成唯一 capability 集；能力必须匹配允许阶段，字符串构造的未知能力不能进入调用；
- 每个逻辑调用在端口执行前 reserve permit 并消耗独立预算，拒绝不会触发端口；route permit 同时受活跃数量 2 的限制；
- 高德/和风 6 秒、DeepSeek 35 秒和任务 90 秒以冻结策略表达；调用前剩余总时限必须覆盖完整单次窗口；
- 调用完成时再次检查单次与总时限，并输出冻结调用快照；时钟由应用边界注入且必须单调、有限，不读取 wall clock；
- 当前策略不创建线程、不 sleep、不执行 HTTP timeout 或重试。它无法主动取消永不返回的 await；真实 adapter 必须在传输层配置客户端 timeout，应用层再对其映射结果和总时限进行裁决。

F-001 Step 16 已在 `application/planning/` 建立模型输出信任边界：

- 端口返回的模型文本只在应用解析/修复协调中作为隔离数据存在，不能直接进入领域候选、终态、来源或日志；
- proposal 本地解析使用精确字段集合并拒绝重复 JSON 键、错误类型、非严格双日日期顺序、候选集外地点、POI 白名单以外来源、非连续优先级及未知选择/时长类别；任何最终时间、路线、verified、provider 或终态字段均为非法额外字段；
- 模型无权提供 provider、状态、工具调用、路线或新事实；提示控制标记属于不可修复错误，不会把危险文本重放给 repair；
- generation 与 repair 共享唯一冻结 proposal Schema；结构性错误或 `finish_reason=length` 最多调用一次 `repair_plan_candidate`，两者拥有独立预算 1 并共同受任务 90 秒总时限约束。repair 不接收或生成最终时间，也不承担确定性调度；
- 修复后仍无效时稳定发布 `model_output_invalid`；adapter HTTP/envelope Schema 失败保持 `provider_schema_invalid`。本地候选错误沿 resolver → outcome → executor → API 只传递 generation/repair 阶段和项目自有无值枚举；时间类可进一步区分活动越窗、住宿到首项、跨地点活动、末项回住宿的非正数间隔及日程容量不足。错误结果不携带原始文本、字段路径、字段值、时间值、地点或坐标；
- 旧精确时间 candidate 的 generation/repair 规则和五类无值时间诊断仅保留为迁移回归。Step 45H 后生产正常路径使用无最终时间的 proposal；模型不再负责精确活动时刻，也不再通过 repair 猜测路线间隔；
- 规划上下文显式携带两日窗口、自由偏好、交通方式、住宿锚点、逐日天气/当前预警和 POI-only `activity_source_ids`，不得用占位摘要替代已取得的天气事实；
- 本边界仍完全 provider-neutral，不导入 DeepSeek SDK、HTTP、Prompt 模板、配置或凭证。

D-009 已由 Step 45H 实现。DeepSeek 只输出 `PlanProposal`，每项只含有序 POI、优先级、`required`/`optional` 建议、游览时长类别和解释；最终 `start_time`/`end_time`、路线事实和终态字段会被严格 Schema 拒绝。确定性调度器在高德路线返回后生成 final validation 可消费的带时间 `PlanCandidate`。每日最多 2 项、60/120/180 分钟时长、景区/博物馆缺省 120 分钟、步行/公交 10/15 分钟缓冲，以及 optional/required/unknown/路线失败策略均已落地，详细规则见 [F-001-CR1 变更卡](./project-management/f-001-cr1-deterministic-scheduling.md)。

F-001 Step 17 已完成候选到确定性终态的应用边界：

- 请求显式携带住宿锚点、两日时间窗口、费用项和数据评估时刻；应用不设置隐藏住宿、窗口、费用或 freshness 默认值；
- 路线补全从纯领域 `expected_legs()` 推导住宿往返链，缺坐标不调用 provider，其他路段逐个受现有预算、阶段和 deadline 治理；
- 每个路线结果必须绑定预期起终点、请求模式和本次响应来源；无效或不可用结果不进入路线链，也不转换为零分钟；
- 最终校验复用两日时间、路线连续性和 Decimal 预算规则，并验证 POI 城市/候选、天气日期/地点、来源引用及显式 freshness；
- 零 issue 才可 `ready`；事实缺失/unknown/过期为 `partial`；超预算、时间/路线硬冲突或引用越权为 `conflict`，且 conflict 优先；
- 所有终态仍经同一状态机从 `validating` 进入，DeepSeek 和 provider 不能声明或覆盖裁决。

F-001 Step 18 已在 `application/repositories/` 与 `adapters/repositories/` 建立临时任务边界：

- 应用层 Protocol 只暴露原子创建/复用、按 job ID 读取、受版本保护的推进和 retry；具体适配器不泄漏给 API 或 Agent；
- 规范化 typed 请求排除 `client_request_id` 后序列化为排序 canonical JSON，并仅保留 SHA-256 摘要；请求正文、Prompt、provider 数据和凭证不进入指纹；
- 单进程适配器用异步锁原子化 client ID 预留，同 ID/同请求返回已有不可变快照，同 ID/异请求稳定冲突；
- job 以 version 防止并发丢失更新，普通推进和 retry 都委托唯一状态机；retry 最多 3 个 attempt，并保留 job/client ID、更新 trace；
- `InMemoryPlanningJobRepository` 仍是单进程测试替身，不跨重启、不跨进程；F-002 的 SQLite adapter 已实现同一应用端口并保持原幂等语义。

F-001 Step 19 已在 `api/` 建立任务资源 HTTP adapter，F-002 Step 4 只更新组合根装配：

- `app.py` 是唯一组合根；本地应用默认装配 SQLite Repository，测试可注入应用端口，`APP_ENV=test` 且未显式提供临时 SQLite 路径时使用独立内存替身；
- POST、GET 和 retry 路由只依赖 `PlanningJobRepository` 与可选的窄 `PlanningJobExecutor` 应用端口，不导入离线编排服务、provider 端口/fake、数据库或网络客户端；
- job 到 `TripPlanResponse` 的映射只公开请求摘要和可观察任务字段，不公开规范化请求、指纹或内部 version；
- Repository 的幂等、未找到、retry 策略和未知错误分别映射为固定 409、404、409 和 500 envelope；请求 Schema 错误统一映射为 422，原始验证细节不返回；
- 未注入 executor 时 POST 只登记 `draft`；注入时只有新建 job 会通过 FastAPI background task 调度一次，幂等复用不重复调度，retry 成功后重新调度同一 job。该机制不是持久化队列，进程退出会中断在途执行，但已提交快照可从 SQLite 恢复。

F-001 Step 20 已建立终态结果快照和 API 映射边界：

- `PlanningJobResult` 只接受 ready、partial、conflict、needs_input、failed，并冻结各状态的 plan、诊断和 retryable 组合；
- 结果快照校验全部公开来源/地点引用和敏感赋值文本；Repository 还验证计划日期、预算及 resolved destination 与原请求/计划一致；
- 只有 `record_result` 能把合法前置状态推进到终态并原子保存载荷；普通状态推进不能创建无载荷终态；
- GET/重复 POST 从快照恢复完整公开结果；retry 清空旧快照后返回 normalizing，避免展示上一 attempt 的计划和错误；
- Step 35 已用只供验收的 `SyntheticPlanningJobExecutor` 把五个冻结结果沿合法状态路径写入 job，并通过真实浏览器 POST/GET/retry 验证边界；默认应用不注入该 fake。Step 37 已实现 `ProviderPlanningJobExecutor`，三家 adapter 全部就绪时才由组合根装配并写入真实编排终态。

F-001 Step 24 已建立浏览器侧任务跟踪边界：

- 严格 TypeScript client 只调用同源 `POST /api/trip-plans` 和 `GET /api/trip-plans/{job_id}`，拒绝额外字段、非法日期时间、未知错误码和不一致任务标识；
- 前端只展示服务端实际返回的 `draft`、`normalizing`、`collecting`、`planning`、`enriching_routes`、`validating` 或终态，并校验允许的状态跃迁，不从计时器推测进度；
- 每两秒最多自动刷新 15 次，终态立即停止，超限后暂停并允许用户手动继续；新请求、卸载和重置通过 `AbortController` 取消在途工作；
- 未装配 executor 时后端 POST 只产生 `draft`；装配 synthetic 或真实执行器时，前端只消费服务端返回的合法阶段和终态。测试中的阶段推进使用可编程 HTTP 替身或 synthetic executor，不冒充 live provider 能力。

F-001 Step 25 已建立终态结果展示边界：

- 前端对 resolved destination、双日计划、活动、天气、预警、路线、预算、费用、来源引用和诊断字段逐层执行严格 guard，并校验计划日期、目的地、预算和地点引用与请求摘要一致；
- ready/partial 结果组件只消费服务端快照，金额保持 Decimal 字符串展示，前端不重新裁决预算、路线或终态；`unknown` 无金额并显示为“未知”；
- 窄屏按冻结设计优先展示结果，桌面保持输入/结果双栏；
- 浏览器终态证据来自本机拦截的冻结后端 synthetic fixture，不代表 POST 已具备执行规划的能力。

F-001 Step 26 已建立诊断、来源和失败展示边界：

- 前端复核五种终态的 plan/diagnostics/retryable 组合，拒绝重复来源 ID 和所有悬空来源引用；conflict 允许按后端契约携带计划但不强制 resolved destination；
- 所有来源逐条展示 provider、类型、获取时间、有效截止和 freshness；warnings、uncertainties、violations 和安全 errors 不混成成功结论；
- conflict 不展示未通过校验的候选为可执行行程；needs_input 指向缺失字段；failed 不显示原始响应、凭证或内部异常；
- Step 26 只展示 retryable 恢复边界；真实 retry 调用已在 Step 27 受控接通。

F-001 Step 27 已建立前端重试和窄屏恢复边界：

- 只有服务端声明 retryable 的 partial/failed 且 attempt 小于 3 才出现重试入口；client 只调用同源任务 retry 资源；
- 重试同步加锁并立即移除旧终态，服务端快照必须复用 job/client ID、递增一次 attempt、更换 trace，且清空上一尝试的计划、来源和诊断；后续轮询不得改变该 attempt/trace；
- 409、网络失败、非法快照和三次上限均稳定停止，不自动递归重试、不创建替代 job，也不恢复陈旧计划；
- 920px 以下非初始状态结果优先并折叠输入，展开入口保留 `aria-expanded`；返回修改根据安全字段映射恢复焦点，桌面双栏不变。

F-001 Step 28 已在 `adapters/providers/` 建立 DeepSeek 传输边界：

- adapter 实现现有 `DeepSeekPort`，使用异步 `httpx2` 调用正式 `/chat/completions`，固定 `deepseek-v4-flash`、关闭 thinking、JSON object 输出、8000 token 上限、35 秒 timeout、禁止 redirect 和环境代理；
- API Key 和配置由构造函数显式注入，配置对象隐藏 Key；adapter 不读取环境，由组合根按全量配置条件装配，缺少真实凭证不影响健康检查或任务资源 API；
- 结构化 planning context、observation 和待修复输出只作为不可信 user data 发送；system prompt 不接受 provider 文本，模型没有 tool call 能力；
- 每个生成/修复端口调用只执行一次 HTTP 尝试，不 sleep 或自动重试。应用层仍独立治理逻辑生成/修复预算与总 deadline，HTTP 失败矩阵与扩展重试策略留给 Step 33；
- 只有通过状态码、大小、JSON、模型、唯一 choice、结束原因、角色、无 tool/reasoning 内容和非空文本校验的响应才形成 `ModelTextOutput`；上游错误 body、异常和凭证不进入 `ProviderResult`、日志或文档；
- 成功结果的模型来源没有可证明的固定有效期，因此 `valid_until` 保持为空并携带明确警告；本离线证据不证明真实 DeepSeek 服务、模型权限或响应质量。

F-001 Step 29–30 已在同一 provider adapter 包建立高德城市、POI 与路线传输边界：

- `AmapAdapter` 当前实现 `resolve_city`、`search_pois` 与 `calculate_routes`；正式 Host 固定为 `restapi.amap.com`，地理编码使用 v3，POI 与路线规划使用 v5 2.0，客户端 timeout 为 6 秒；
- 城市解析必须得到唯一城市级结果；普通城市要求 `level=市`，北京、上海、天津、重庆兼容 provider 把 `city` 返回空数组并把直辖市放在 `province` 的结构差异；
- POI 搜索按 city adcode 强限制，只取第一页且最多 25 条；F-001 项目类别只映射 `scenic_area -> 110000` 与 `museum -> 140100`，不允许任意项目字符串穿透为 provider typecode；
- 高德 POI ID 经固定 namespace UUIDv5 转为稳定项目 ID；provider 区县 adcode 必须属于请求城市，结果的项目 `city_adcode` 保持城市级语义；异城、Schema 坏记录和重复 ID 有剩余候选时产生 partial，无剩余候选则不可用；
- 高德原生坐标显式标为 `provider_native`；缺失坐标保留 `None`，后续路线/天气按事实缺失降级，不由 adapter 猜测；
- 城市解析保留高德 `citycode`，公共交通请求显式提供 `city1/city2`；F-001 单城市切片将同一已解析 citycode 传到两端，不执行隐藏反向地理编码，也不从 adcode 猜 citycode；
- 路线只接收项目允许的步行/公共交通模式与 provider-native 坐标；分别调用 v5 walking 和 transit integrated，要求唯一选项及响应回显端点与请求精确一致；距离按整数米保留，`cost.duration` 秒数以纯整数向上取整为分钟，provider 附带票价不进入预算事实；
- `RouteLeg.source_ids` 与对应 `SourceRecord.source_id` 使用同一 ID；路线有效期未知并明确警告，无路线 infocode 映射为 `empty_result`，坏 Schema 不进入领域层；
- HTTP 状态和 HTTP 200 内的 `infocode` 都映射为项目安全错误，每个端口调用只执行一次 HTTP 尝试；Key、上游 info/body 和异常不进入领域结果、日志或来源；
- adapter 配置仍由构造函数注入并由组合根按全量配置条件装配。本地实现不证明账户、Web Service Key、POI 2.0 权限、配额或持续 live 数据质量。

F-001 Step 31 建立和风天气 JWT、预报与预警传输边界：

- `QWeatherAdapter` 实现 `get_weather_forecast` 与 `get_current_weather_alerts`，只接受账户专属 `*.qweatherapi.com` Host；httpx2 固定 6 秒 timeout、禁 redirect/环境代理且每个端口调用一次 HTTP 尝试；
- 鉴权使用 Ed25519 PKCS8 私钥生成 15 分钟 JWT，Header 仅含 `alg/kid`，Payload 仅含 `sub/iat/exp`，并只在 Bearer Header 中传输；adapter 不支持旧 API Key，也不读取环境或私钥文件；
- 中国大陆按和风官方坐标约定复用高德 GCJ-02/provider-native 坐标，确定性四舍五入到两位；当前逐日预报使用 `/weather/v1/daily/{latitude}/{longitude}`，固定取 7 日、本地时间和中文，再只映射请求双日；
- 预报日期、时区、摄氏温度和昼夜条件全部通过本地 Schema；缺日/坏记录只产生带来源的 partial，不补造事实；预报响应没有固定有效期，保持 unknown validity；
- 当前预警使用 `/weatheralert/v1/current/{latitude}/{longitude}`；`zeroResult=true` 是带来源的成功空快照，重复、坏格式或 `expireTime <= fetched_at` 的记录不作为当前预警，非空结果的 `valid_until` 取最早失效时间；
- HTTP/传输/Schema 错误映射为项目稳定分类，私钥、JWT、上游 body 与异常不进入结果；Step 37 补充收口要求 `metadata.attributions` 安全且非空并原样进入领域/公开来源，缺失或非法即拒绝结果，UI 与对应天气/预警共同展示固定和风链接与原始归因；
- Step 31 本身只建立 adapter，没有进入 `app.py`；随后 Step 32 完成私钥路径读取、JWT 环境字段、启动检查和组合根装配。两者都不证明账户、凭据、Host、额度、权限或 live 数据质量。

F-001 Step 32 建立本地配置与组合根边界：

- 本地运行的 `Settings` 只自动读取项目根部被 Git 忽略的 `.env.local` 和当前进程环境；`APP_ENV=test` 时明确禁用 dotenv source，只接受测试进程环境，第三方敏感字段不参与对象 `repr`；
- DeepSeek 和高德以各自 Key 为独立配置组；和风以账户 Host、项目 ID、凭据 ID和绝对 Ed25519 私钥路径为一个原子配置组；
- 配置组全空时标记 `disabled`，FastAPI 和精确健康契约仍可启动；完整且通过 adapter 本地校验时标记 `ready` 并在应用组合根创建 adapter；部分配置或非法 Key/Host/ID/路径/PEM 使启动以稳定错误码失败；
- 和风 PEM 仅在组合根按显式绝对路径读取，读取前限制为普通文件和 16 KiB 上限；PEM 内容、Key、账号标识和路径不进入启动报告、异常文本或 `repr`；
- 启动检查只做本地结构、文件和密码材料校验，不发网络请求，不证明授权、配额、条款、Host 可达性或 provider 可用性；Step 32 当时尚未接入任务 POST，Step 37 补充收口按下述全量就绪条件完成了执行器装配。

Step 37 补充收口已把真实 provider 执行器接入组合根：仅当 DeepSeek、高德、和风三组 adapter 全部存在时，任务 POST/retry 才调度 `ProviderPlanningJobExecutor`；否则执行器保持 `None`。执行器通过应用端口驱动既有单编排器，先把住宿文本解析为同城高德 POI 锚点，再收集景点/天气/预警、请求 DeepSeek 候选、补全路线、执行确定性预算和终态校验，最后经 Repository 唯一写入口发布。该路径已由离线 fake 测试证明，并在 Step 38 取得一次受控 live 契约证据；不代表持续可用或 ready/partial 真实计划已通过 UAT。

## 外部服务职责

| 服务 | 唯一职责 | 不能作为其事实来源的内容 |
| --- | --- | --- |
| DeepSeek | 需求理解、工具调用建议、POI/优先级/顺序 proposal、自然语言解释 | 最终精确时间、天气、POI、路线、实时价格、预算校验结果 |
| 高德 | 地理编码、基础 POI、地点详情、路线及其提供方元数据 | 酒店库存或实时房价、天气、餐饮预算、计划优劣 |
| 和风天气 | 指定地点和时间范围的天气预报、预警及其元数据 | POI、路线、营业状态、价格、行程安排 |
| 应用代码 | 数据转换、来源关联、基于实际路线的精确排程、日期/时间/路线/预算校验、影响分析 | 不伪造缺失的第三方事实 |

## 主要数据流

### 创建计划

```text
用户输入
→ API Schema 校验
→ TripRequest 规范化
→ 确认缺失的硬约束
→ 编排 Agent 选择窄工具
→ 适配器获取外部数据并记录来源
→ Agent 生成不含最终精确时间的 PlanProposal
→ 代码校验 POI / 来源 / 日期 / 优先级 / 时长类别
→ 高德按住宿和有序活动查询实际路线
→ 确定性调度器生成 start_time / end_time
→ 领域校验器独立复验日期 / 时间 / 路线 / 预算 / 冲突
→ proposal 结构失败最多一次受控修复；排程硬冲突不交给模型绕过
→ 保存计划版本、来源、决策和 trace
→ Web UI 展示 ready / partial / conflict
```

LLM 输出必须先通过 Schema 和领域校验。校验器结果是硬边界，不能通过 Prompt 指令跳过。

### 局部重规划

```text
结构化修改 + 当前 plan_id
→ 捕获 job version、plan version 和 replan trace
→ 纯代码计算直接/传递影响、预算和来源动作
→ cross_city：Provider 调用和写入前拒绝
→ 仅 same_day_low：自动进入独立 replan lifecycle 的 replanning
→ 其他已批准高影响分类：持久化影响快照并等待 15 分钟确认
→ 只复用仍 fresh/valid 且未受影响的转换后来源
→ 对批准范围生成候选并执行完整确定性重校验
→ 单事务追加计划版本、lineage、change set、来源和 decision
→ 返回本次 baseline→result diff，保留旧版本
```

F-003 只接受 `replace_activity`、`delete_activity`、`adjust_activity_time` 和
`reorder_activities` 四种 tagged command。影响范围由确定性代码计算；大模型可以在
批准范围内生成替换候选和解释结果，但不能分类影响、扩大修改集合、跳过确认或提交版本。
重规划不增加 planning attempt，也不是 retry、版本恢复或完整计划重生成入口。

## 显式状态机

F-001/F-002 的 PlanningJob 状态以 [api-contract.md](./api-contract.md) 和代码中的
`ALLOWED_PLANNING_TRANSITIONS` 为准，包含 `enriching_routes`，不包含任何局部重规划状态。
F-003 不修改该状态图；确认和重规划由下方独立 replan lifecycle 承载。

Step 13 已建立 `PlanningStateMachine.transition` 作为 F-001 单次状态转换的应用层裁决入口。它直接读取冻结转换表，不维护第二份状态图；输入和结果均为冻结 typed value。`partial` 与 `failed` 的恢复边只有在显式 retry 且任务被标记为可重试时才成立，其他普通边拒绝 retry 触发。状态机本身无任务存储、attempt、trace、provider 或时钟副作用；完整轨迹与持久化仍由后续应用用例负责。

| 状态 | 含义 | 允许的主要下一状态 |
| --- | --- | --- |
| `draft` | 用户仍在输入 | `normalizing` |
| `normalizing` | 校验和规范化需求 | `needs_input`、`collecting`、`failed` |
| `needs_input` | 缺少必要硬约束 | `normalizing`、`cancelled` |
| `collecting` | 调用外部工具并记录来源 | `planning`、`partial`、`failed` |
| `planning` | 生成并严格准入无最终时间的 proposal；无规则时长停止等待输入 | `needs_input`、`enriching_routes`、`validating`、`failed` |
| `enriching_routes` | 按代码推导端点查询实际路线，并由确定性调度器生成精确时间 | `validating`、`partial`、`failed` |
| `validating` | 执行确定性校验 | `ready`、`partial`、`conflict`、`planning` |
| `ready` | 计划通过当前必需校验 | 无；重规划创建独立资源 |
| `partial` | 有可用结果但数据或预算不完整 | 仅显式 retry 可回到 `normalizing` |
| `conflict` | 存在不能自动解决的约束冲突 | 无 |
| `failed` | 当前请求无法产生安全结果 | 仅显式 retry 可回到 `normalizing` |

PlanningJob 状态转换由应用层执行并记录原因；工具不能自行改变状态。

F-003 独立 replan lifecycle 冻结为：

| replan 状态 | 允许的下一状态 |
| --- | --- |
| `analyzing` | `awaiting_confirmation`、`replanning`、`needs_input`、`rejected`、`failed` |
| `awaiting_confirmation` | `replanning`、`cancelled`、`expired`、`conflict` |
| `replanning` | `completed`、`needs_input`、`conflict`、`failed` |
| `rejected`、`completed`、`needs_input`、`conflict`、`failed`、`cancelled`、`expired` | 无 |

`analyzing` 是纯确定性、零 Provider 阶段。只有分类集合精确为 `{same_day_low}` 且所有
自动执行前置条件成立时才自动进入 `replanning`；`adjacent_day`、`cross_day`、
`accommodation_effect`、`budget_risk`、`source_refresh` 或 `unknown_impact` 任一出现都进入
`awaiting_confirmation`。`cross_city` 和不受支持的结构化修改进入 `rejected`。确认只授权已
持久化的影响快照；unknown impact 经确认后若仍无法收敛为可验证范围，进入 `needs_input`，
不能靠确认放宽硬边界。

D-009 保持状态名称不变：`planning` 已改为生成并校验无最终时间的 proposal，`enriching_routes` 已改为查询实际路线并运行确定性调度器；无规则可补足的 unknown 游览时长通过新增的 `planning → needs_input` 边安全收口。

## 状态与持久化

- `TripPlan` 是计划内容的事实来源，每次成功重规划创建新版本；
- 应用状态由显式状态机维护，不能只存在于 Prompt 或前端内存；
- Web UI 使用服务端响应作为计划和确认状态的事实来源；
- 外部响应可按 provider、查询参数和有效期建立受控缓存，但不能把过期缓存伪装为最新数据；
- 计划、来源、工具调用和用户确认通过 `trace_id`、`plan_id`、`plan_version` 和 `decision_id` 关联；
- 本地应用模式使用 SQLite 保存任务、attempt、计划版本和来源；测试仍可通过组合根注入内存 Repository。

### F-002 SQLite 持久化边界

F-002 Step 1 已冻结本地 SQLite 设计，Step 2–4 已实现基础设施、Repository adapter 和现有 API 装配：

- `schema_migrations`、`planning_jobs`、`planning_attempts`、`plan_versions`、`source_records`、`plan_version_sources`、`decision_records` 和 `acceptance_records` 由项目自有 migration runner 建立；
- `planning_jobs` 保存当前任务快照、allowlist 结构化请求、SHA-256 指纹、attempt、trace、状态、retryable、乐观 version 和 30 天 `expires_at`；`planning_attempts` 保存每次 attempt 的状态和安全终态元数据；
- `plan_versions` 追加保存经过 typed model 校验的计划 JSON，不能原地覆盖；`source_records` 只保存转换后的来源元数据、获取时间、validity、freshness、归因和安全链接；
- 真实执行器的 attempt 1 继续沿用 F-001 的 job 级 UUIDv5 标识；retry attempt 2/3 使用由 `job_id + attempt + trace_id` 派生的稳定命名空间，避免同一 job 的追加式 plan/source 标识触发唯一约束，同时保持重启后可复现；
- 金额、坐标和温度使用十进制文本，时间使用带时区 ISO-8601 文本，JSON 读写前后都必须经过项目 typed model；`unknown` 费用为 `amount=null`，不得转成零；
- 所有业务记录通过 `job_id` 隔离并启用外键级联删除；单计划 DELETE 由 Repository 原子删除 job，启动时 maintenance port 最多清理 1000 个已到期 job，当前不提供清空全部数据；
- Repository 继续实现既有 `get_or_create`、`get`、`advance`、`record_result`、`retry` 原子端口；SQLite adapter 不泄漏到 domain、API 或 Agent；
- 连接初始化固定 `foreign_keys=ON`、`busy_timeout=5000`、`journal_mode=WAL`、`synchronous=FULL`；迁移采用升序版本、checksum 校验、事务提交和失败回滚，不支持自动降级；
- 持久化保存安全结构化字段，不保存 Key、Token、JWT、私钥、Cookie、Authorization、原始 provider 响应、原始错误 body 或完整 Prompt。

应用组合根在 lifespan 接受请求前创建父目录、打开连接并完成 migration，migration 失败或数据库版本高于应用支持版本时安全停止启动，关闭时释放连接。显式数据库路径必须为项目源码树外的绝对路径；未配置时使用操作系统本地应用数据目录。模块导入本身不创建数据库。`APP_ENV=test` 且未显式提供临时路径时使用内存替身；SQLite 集成测试只使用独立临时数据库。

当前重启恢复的是最后一次已提交快照；后台规划执行不是持久化队列，不承诺重启后自动续跑。Step 5 已实现单计划删除、migration 后一次有界 30 天清理，以及内部 typed acceptance record 写入。验收证据只允许固定 case/environment/status 和代码化 check/limitation，不保存完整日志、Prompt 或 provider body，也没有公开验收记录 API。

该设计不新增历史列表、版本比较或恢复 API，不扩展多城市/多日/局部重规划，不授权真实 Provider 调用。具体字段、事务和测试矩阵以 F-002 当前实施计划为准。

### F-003 migration v2 与 Repository 边界（Step 1 冻结）

F-003 在 v1 之上只前向增加 `replan_requests` 和 `plan_version_lineage`，不改写 v1
计划版本，也不为旧版本伪造父节点。`decision_records` 继续作为 job-owned typed 决策记录，
由 `replan_requests.decision_id` 建立可空的一对一关联。

- `replan_requests` 保存 job 内唯一的 `replan_request_id`、SHA-256 command 指纹、
  baseline plan/version、内部 expected job version、独立 trace、操作、allowlist request JSON、
  typed impact JSON、replan 状态、15 分钟过期时间、可空 decision/result version、安全错误码、
  aggregate version 和带时区时间戳；
- `plan_version_lineage` 以 `(job_id, child_version)` 为主键，保存 parent version、唯一
  replan ID、可空 decision ID、typed change-set JSON 和创建时间；child/parent 都必须属于
  同一 job，child 必须大于 parent；
- v2 为 `plan_versions(job_id, version_number, plan_id)` 增加唯一索引，并让 baseline 的三列
  外键精确引用同一版本；同时增加 job/replan 幂等唯一约束、job/status/updated、待确认 expires、baseline 和 lineage
  索引；job 删除继续级联全部 F-003 记录；
- JSON 只接受项目 typed model 的 `model_dump(mode="json")`，读取时重新校验并 fail closed；
  不保存完整自然语言修改、Prompt、provider 原始响应或错误 body；
- migration 2 继续使用既有升序、name/checksum、单 migration 事务和 rollback 规则；v1→v2
  保留全部数据，重复执行幂等，高版本数据库 fail closed，不支持自动 down migration。

F-003 新增独立 `ReplanRepository`，不修改 `PlanningJobRepository`。它拥有 reserve/get、
记录分析、确认/取消、开始执行、失败终结和原子提交能力；每个写命令同时检查 replan
aggregate version，执行和提交还检查捕获的 job version 与 baseline plan/version。成功提交在
同一 SQLite 事务内写 plan version、采用来源及关联、lineage、decision、replan completed、
当前 planning attempt 的 plan version、PlanningJob 快照和 version；任一写入失败全部回滚。两个相同 baseline 的并发 replan
最多一个提交成功，另一方稳定返回 `version_conflict`。失败、冲突、取消、过期和 needs_input
只更新 replan/decision 安全状态，不替换当前计划。

F-003 Step 2 已实现纯领域 `domain/replanning.py`：四种 command、impact context/analysis、
source action、budget result 和 plan change set 均为 framework-free frozen/slotted value；分类器
只依赖显式 baseline 依赖图，不读取 Repository、SQLite、HTTP、Provider、环境或时钟。只有精确
`same_day_low` 为 AUTO；重排活动集合、共享来源、unknown 费用、跨日依赖、cross-city 和 diff
scope 都在领域边界 fail closed。Step 2 完成时该实现尚未接入 migration、Repository、application service 或 API；后续接入由 Step 3–5 完成。

F-003 Step 3–5 已依次实现 migration v2、独立 ReplanRepository、application replan 编排和三个窄 HTTP 资源。API 使用严格 tagged command DTO，将 auto/approve 执行作为 background task 调度并先返回 `replanning` 快照；completed 读取通过 typed replan result/change-set 投影，非成功终态继续保留原计划。`create_app` 只接受显式注入的 replan application service，不因路由存在而读取 Provider 配置、恢复持久化执行或访问网络；完整临时 SQLite 纵向装配与浏览器验证仍属于后续批准阶段。

### F-004A 单城市 2–7 日架构（Step 1 冻结，Step 2–4 已实现）

F-004A 在不改变现有单城市边界、PlanningStatus、SQLite schema version 2 和旧双日公开形状的前提下，引入严格可辨识的多日类型。旧类型继续作为兼容入口，不通过给旧模型增加 optional 字段来混合语义。

- `TripPlanRequest`、`TripRequestInput`、`TwoDayTimePlan`、`TripPlan` 和 `TripPlanResponse` 保持 legacy 定义；
- 新增 `TripPlanRequestV2`、`MultiDayTripRequestInput`、`MultiDayTimePlan`、`TripPlanV2` 和 `TripPlanResponseV2`；应用边界使用 `PlanningRequest`、`PlanningPlan`、`PlanningResponse` 显式联合；
- V2 请求必须携带 `request_version="2"`、显式 `start_date/end_date` 和 2–7 个窗口；V2 plan 携带 `plan_format_version="2"`，V2 response 携带 `response_version="2"`，避免仅凭数组长度猜测类型；
- `day_count = (end_date - start_date).days + 1`，只允许 2–7；开始日期继续使用现有 D+1 至 D+5 上海本地日历门禁，结束日期由连续跨度决定，不因天气覆盖不足而缩短；
- `DailyAvailability` 的基础 offset 校验扩为 0–6；legacy `TwoDayTimePlan` 仍额外要求 `{0,1}`，`MultiDayTimePlan` 要求窗口集合精确等于 `range(day_count)`；
- proposal、candidate、plan days 和天气日期都必须与 `expected_dates = start_date..end_date` 精确一一对应，拒绝缺日、重复、越界和乱序；
- `PlanStructure` 继续要求全部地点属于一个 `city_adcode`；每个 plan day 必须引用同一个住宿锚点；活动不得跨夜，每日 1–2 项；完整路线链最多为每天 3 段；
- scheduler 继续以实际路线、60/120/180 分钟时长、类别缺省和步行/公交缓冲生成最终时间；固定输入必须得到固定输出；最终校验按日期遍历而非硬编码 offset 0/1；
- 餐饮为每人每日金额 × 人数 × `day_count`；住宿为一晚金额 × (`day_count - 1`)；Decimal、费用 confidence 和 unknown 规则不变；
- QWeather 缺少任一请求日期、响应只有部分日期或 validity/freshness 不可确定时保留已验证事实并形成 partial；不得补造日天气或把缺日转为 ready。

Repository port 的方法集合保持不变，只有 typed 参数和快照内部类型扩为显式联合。legacy 指纹继续对原 `TripPlanRequest.model_dump(mode="json", exclude={"client_request_id"})` 做相同 canonical JSON 和 SHA-256；V2 指纹对包含 `request_version/end_date/day_windows` 的 V2 dump 使用同一序列化规则。禁止先把 legacy 请求补成 V2 再计算指纹。

SQLite 水合按以下闭集判别：`request_version` 缺失时只用 legacy model；值精确为 `"2"` 时只用 V2 model；其他值、冲突字段或对应 plan format 不一致时以现有安全 Repository 错误 fail closed。`planning_jobs.request_json`、`plan_versions.plan_json`、来源链接、attempt、trace、version 和事务边界不变，因此不需要 migration v3，也不重写 v1/v2 数据。旧应用遇到 V2 JSON 会因额外字段拒绝并停止读取，不得删除或错误投影该记录。

F-003 对 legacy 双日计划保持原行为；V2 恰好 2 日时可经严格 typed 映射构造现有 replan impact context。任何 `day_count > 2` 的 replan 必须在 reserve、decision、executor 和 Provider 之前返回既有 `replan_scope_not_supported`，不产生 replan、decision、plan version 或 current-plan 写入。

Provider 治理使用按任务构造的不可变 policy，不修改 legacy 默认值：

- resolve city 1、POI search 3、forecast 1、current alert 1、generation 1、repair 1；各单次 timeout 保持现值；
- route 并发保持 2，route `max_calls = min(28, 4 × day_count)`；legacy/V2 两日仍为 8；
- 任务总期限为 legacy/两日 90 秒；V2 三至七日使用 `min(180, 90 + 18 × (day_count - 2))` 秒，只补偿额外有界路线批次，不增加单次超时或 HTTP 次数；
- 每日最多 3 个 primary route requirement；双模式 fallback 只使用总预算剩余额度，按日期和住宿往返链稳定顺序尝试，预算耗尽后不得继续调用；缺少必要路线时按现有安全 route failure 收口，不发布不完整路线链；
- POI HTTP 调用数仍不超过 3，单次候选上限使用 `min(20, max(6, 2 × day_count + 2))`，为最多 14 项活动提供有界目录；
- QWeather 仍只发一次 7 日 forecast 请求和一次 current-alert 请求；请求行程超出响应覆盖时按部分天气处理，不追加天气调用。

Step 2–4 已依次落地多日领域/排程/终检、V2 contracts/Repository/API/schema v2 水合，以及 Provider 编排。组合根按请求创建不可变 `ToolCallGovernor`；legacy 默认 policy 不变，V2 3–7 日使用冻结路线预算和总期限。DeepSeek 只接收版本化完整日期上下文并继续输出无最终时间 proposal；QWeather 缺日只保留已验证日期并形成 partial；executor 生成 typed `TripPlanV2`，unknown 费用仍为空。该实现没有新增公开端点、Schema、migration、Provider 或依赖。

### F-004B1 多城市与用户提供城际段架构（Step 0–8 已实现并归档）

F-004B1 在 legacy/V2 之外增加独立 V3 变体，不继承单城市请求或计划形状，也不改变现有 11 个 `PlanningStatus`。V3 仍经过 contract → application → domain → adapter → Repository 的既有依赖方向；城市顺序、城际段、日期连续性、缓冲、费用和终态均由 typed model 与确定性代码裁决，LLM 不能改写。

#### 类型与领域边界

- `TripPlanRequestV3` 复用通用值类型，但字段集合独立：`request_version="3"`、日期、窗口、旅客/预算/偏好/市内方式、2–3 个 `CityStayV3`、1–2 个 `UserProvidedIntercitySegmentV3` 和餐饮预算；不含单城市 `city/accommodation/intercity_transport_cost`；
- `CityStayV3` 固定为 `city/nights/accommodation`；城市文本按既有规范化规则唯一，Step 4 解析后的 adcode 也必须唯一且属于中国大陆；
- `UserProvidedIntercitySegmentV3` 固定为相邻城市索引、`rail/air/coach`、出发/到达站点、带 `+08:00` 的出发/到达时间和可空用户票价；段数精确为城市数减 1；
- `day_count` 只允许 3–7，2 城至少 3 日、3 城至少 4 日；每城 `nights >= 1` 且夜数之和精确等于 `day_count - 1`；
- 第 i 个转移日由前 i 个城市累计夜数唯一派生；段必须在该上海本地自然日内从索引 i 到 i+1，`arrival_at > departure_at`，拒绝跨夜、第三城市、联程和重复城市闭环；
- `PlanIntercitySegmentV3` 保存系统段 ID、城市索引、方式、站点 location ID、时间、一个 `CostItem` 和用户来源；`TripPlanV3` 保存有序 `city_adcodes`、1–2 个段、3–7 个 `PlanDayV3`、地点和预算；
- `PlanDayV3` 显式保存 `departure_city_index/arrival_city_index/overnight_city_index/intercity_segment_id`。非转移日三个索引相同且 segment ID 为空；转移日必须为 i/i+1/i+1 并引用唯一段；
- 转移日最多 1 项活动，其他日 1–2 项；活动地点只能属于当天出发或到达城市，市内 `RouteLeg` 两端必须同城，不能用步行/公交 leg 横跨城市。

#### 排程、预算、来源与终态

- scheduler 先按城市夜数构造每日城市骨架，再把用户段作为不可变占用区间：铁路前/后 60/30 分钟、航空 120/60、长途客运 45/30；活动和市内路线不得进入占用区间；
- 转移日前活动只能在出发城市并在出发缓冲前结束；转移日后活动只能在到达城市并在到达缓冲后开始；固定输入必须得到固定顺序和时间；
- 住宿按每城 `one_night_cost × nights`，餐饮按每日金额 × 人数 × day_count，市内交通沿用现有规则；每个城际段始终产生费用项，用户票价为 `user_provided`，缺失为 `unknown/amount=null`；
- 用户段产生 `provider=user`、`source_type=user_provided_intercity_segment` 的来源，`fetched_at` 表示本地记录时间，`valid_until=null`、`freshness=unknown_validity`，warning 明确“用户提供、未核验班次/余票/库存”；该来源不能被提升为 Provider 验证事实；
- 用户已提供所有必需段字段且确定性计划完整时，未核验 availability 本身不阻止 `ready`，因为 F-004B1 只对用户输入做可执行性规划；但任何金额、天气、路线或其他已纳入预算/执行判断的 unknown 继续按既有规则产生 `partial`；
- 请求字段缺失/形状非法在创建 job 前 422；城市解析歧义或必要地点信息不足为 `needs_input`；日期/住宿/段/缓冲不可同时满足为 `conflict`；必要 Provider/路线/模型失败且不能形成安全计划为 `failed`；不得用 warning 把 conflict/failed 提升为 partial。

#### Repository、SQLite 与 API 数据流

- `PlanningRequest/PlanningPlan/PlanningResponse` 联合显式增加 V3 tag；legacy/V2 的 `PlanningJobResult` 保持不变，新增独立 `PlanningJobResultV3(resolved_destinations, plan, terminal fields)`，由内部 `PlanningResult` 联合承载；V3 request/plan/response 分别以 `request_version/plan_format_version/response_version="3"` 判别，未知或冲突版本 fail closed；
- `PlanningJobRepository` 方法集合、attempt/trace/version/expected_version、append-only plan version、source 关联、DELETE 和 30 天清理不变；`PlanningJob.request/result` 只扩展为 request/result typed union，并校验 V3 request 只能搭配 V3 result/plan；
- V3 指纹继续排除 `client_request_id`，对 V3 原始 typed dump 做相同 canonical JSON + SHA-256；禁止把 legacy/V2 转成 V3 后重算；
- `planning_jobs.request_json` 和 `plan_versions.plan_json` 已能保存严格 typed JSON，表、列、索引、外键和 migration 1/2 均不需要变化；读取必须先按 tag 选唯一 model，再校验 request/plan/response format 一致；
- 旧应用遇到 V3 JSON 因额外 tag/字段拒绝并 fail closed；不得删除、改写或投影为 legacy/V2；回滚通过重新部署支持 V3 的应用完成；
- POST/GET/retry/DELETE 继续使用现有 URI；GET/retry 响应由持久化 request tag 决定；V3 replan 在 API 读取 job 后、创建 service/reserve/decision/executor/Provider 之前返回既有 422 `replan_scope_not_supported`。

#### Provider 编排与交付边界

- 城际 Provider port、adapter 和 HTTP 调用数为 0；用户段直接作为 immutable input fact 进入 scheduler，不经 DeepSeek 生成或修复；
- 现有城市 Provider 可按城市复用：resolve city ≤ C、POI HTTP ≤ 3C、forecast ≤ C、current alert ≤ C；DeepSeek generation 1/repair 1 是整任务上限，不按城市倍增；
- 城市 fan-out 并发 2，route 并发 2，route 总调用 ≤ `min(28, 4 × day_count)`，总 deadline ≤ 180 秒；adapter 内 retry 必须计入同一调用和总时限，取消后 active call 收敛为 0；
- POI、天气、路线和模型测试只允许 fake/MockTransport/synthetic；Step 4 不读取 `.env.local`，不调用真实高德、和风、DeepSeek 或城际服务；
- 四层交付保持 domain/contracts → persistence/API → planning → UI/delivery；Step 2 不进入 Repository/API，Step 3 不进入 Provider/UI，Step 4 不进入 UI，Step 5 才实现前端。

Step 4 已按该边界实现独立 `MultiCityPlanningOrchestrator`。城市事实通过并发 2 的有界 fan-out 复用现有 Amap/QWeather ports，所有城市共享一个 governor 和一次全局 DeepSeek proposal/repair 预算；proposal 只包含逐日城市索引与 namespaced POI 引用，用户站点、城际段原文和 fare 不进入模型 payload。确定性应用层再注入用户段、缓冲、市内路线、活动时刻、预算、来源和 terminal。deadline 前置拒绝与取消 drain 已由离线测试证明；没有新增城际 port/adapter、Schema、migration、依赖或真实调用。

F-004B1 后续 Step 5–8 已完成严格 V3 前端、schema v2 临时 SQLite 往返与重启恢复、loopback desktop/390px、网络/console/accessibility、独立隐私兼容审查、四层 stacked PR 和归档。最终归档 main 为 `c5f07e12abdc37f977ee0f7181a5f2800f015066`，CI run `32386260285` 成功；这些仍是 synthetic/离线证据，不构成真实 Provider UAT。F-005 已在既有三家 Provider 与同一架构边界内完成韧性、时效和离线 Agent 评估并归档；F-004B2 Provider/法律 Gate 已阻塞并归档，未新增城际 Provider、Schema、依赖、公开 API shape 或真实 UAT。当前无活动任务。

## F-005 韧性执行架构（Step 1 冻结）

### 纯政策、任务级运行态与适配器边界

F-005 采用三层显式组合，不把 retry 隐藏在全局 HTTP client 或 Provider adapter 单例中：

1. `domain/resilience.py` 保存 Provider operation、事实关键性、失败处置、freshness 使用和 retry schedule 的纯值对象/纯函数；`provider_result.py` 只扩展安全、可选、非公开的 `retry_after_seconds`，不引入框架依赖；
2. `application/tooling/resilience.py` 保存每个 planning attempt 新建的 `ProviderAttemptBudget`、可注入 clock/sleeper/random 和 attempt executor；预算对象经现有编排调用链显式传递，禁止 module global、`contextvars` 或跨 job 共享可变状态；
3. 高德/和风 adapter 继续只负责一次 HTTP 交换、Schema/单位/时区转换和安全错误规范化。429 的 `Retry-After` 在 adapter 边界解析为最多 2 秒的数值，不保存原始 header；DeepSeek 保持一次 generation transport 和一次 repair transport，不接入传输 retry。

生产调用顺序固定为：

```text
logical governor reserve
→ initial HTTP attempt
→ classify ProviderResult
→ 可重试且额外预算、task deadline、terminal/cancel 均允许
→ reserve extra-attempt slot
→ injected delay
→ 最多一次 retry attempt
→ logical governor complete
→ capability/freshness disposition
→ deterministic validation / terminal projection
```

- initial attempt 不占“额外 attempt”预算；retry slot 以 Provider 和任务两个计数原子预留。高德最多 3、和风最多 1、任务合计最多 4；每个逻辑调用最多 2 个实际 HTTP attempt。
- timeout/5xx 的 delay 为注入式 full jitter `0–200ms`。429 只有合法 delta-seconds 或可由注入式 UTC clock 计算的 HTTP-date 且结果在 `0..2s` 内才属于受控限流；最终 delay 为 `min(2s, Retry-After + jitter)`，缺失、非法或超界时不自动重试。
- 只重放完全相同的 immutable typed、幂等只读请求。retry 保持原逻辑 permit 和原并发槽，不增加逻辑工具计数，也不扩大 route/city fan-out 并发。
- Amap/QWeather 每个 HTTP attempt 最多沿用现有 6 秒 timeout；DeepSeek 沿用 35 秒。attempt timeout、delay 和第二 attempt 都计入现有任务总 deadline；剩余时限不足以覆盖下一 delay 和该 Provider 的完整单次 timeout 时不启动 retry。
- 取消发生在 delay 或 HTTP 中时立即传播；未启动的 retry 为 0。终态、任务取消、deadline 或预算关闭先关闭 task runtime，再 cancel/drain active peers；返回 Repository/API 前 active peer 必须为 0。
- planning job 的用户级 retry 会创建新的 task-scoped attempt budget；它不改变现有最多 3 个 planning attempt。F-003 replan 与 planning retry 继续隔离，V3 replan 在创建 runtime 之前拒绝。

安全内存诊断只包含 trace ID、Provider/operation 枚举、逻辑调用和 attempt 序号、稳定错误码、retry 决策、有限毫秒耗时以及来源/预算计数。它不进入 domain result、公开 JSON、SQLite 或 CI artifact；原始 header、URL query、请求/响应 body、Prompt、异常文本和堆栈不得进入诊断。

### 能力关键性与失败处置矩阵

| 能力/事实 | 成为最终计划所需时 | 未被最终采用或可选时 |
| --- | --- | --- |
| 城市解析、住宿锚点、V3 站点解析 | 失败且用户不能通过补充/消歧修正时 `failed`；可消歧输入才 `needs_input` | 未使用候选不投影 |
| POI/活动候选 | 无法形成当天最小可执行活动集合时 `failed` | 个别候选缺失可丢弃；仍有可执行计划时 `partial` |
| 最终采用的市内路线 | 无合法事实时 `failed`；已知路线使窗口不可满足时 `conflict` | 未采用候选不投影；fallback 只按既有业务空/本地非法边界 |
| 天气预报、当前预警 | 不阻断骨架计划，但缺失/不可安全使用时 `partial` | 从计划事实和模型上下文剔除并披露缺口 |
| DeepSeek proposal/repair | generation 失败或唯一 repair 后仍非法为不可自动重试 `failed` | 模型不能提供终态、路线、费用可信状态或 attribution |

Provider auth/schema/empty/unknown 不自动重试；timeout/5xx/受控 429 只在上表所列内部 attempt 政策下重试。retry 耗尽后按能力关键性形成 `failed` 或 `partial`。Provider failure 本身不产生 `needs_input` 或 `conflict`；这两个终态只能由输入裁决或确定性规则产生。

### freshness 快照与使用矩阵

`fetched_at` 是来源获取/观测时刻，业务事件时间保留在具体 typed payload；`valid_until` 只来自可证明合约或项目确定性规则。`freshness` 不是 Provider 声明，而是在 planning/replan attempt 的显式 `evaluated_at` 由 `fetched_at + valid_until` 计算的快照：`evaluated_at <= valid_until` 为 fresh，超过为 stale，缺少有效期为 unknown-validity；`evaluated_at < fetched_at` fail closed。

| 数据能力 | fresh | stale | unknown-validity |
| --- | --- | --- | --- |
| 最终采用的路线 | 可进入排程 | 从候选中拒绝；无 fresh/unknown 替代时 `failed + data_stale` | 可进入排程但最高 `partial`，显示 validity unknown |
| 城市、住宿、站点、POI | Schema/地理/引用校验通过后可用 | 只可作为明确披露的 partial 事实；无法形成必要目录时 failed | 可用但最高 partial |
| 天气预报、当前预警 | 可显示并进入有限建议 | 从计划事实和模型输入剔除，保留 partial + `data_stale`；不得声称当前预警 | 可显示“有效期未知”，最高 partial |
| DeepSeek proposal/repair | 仍须确定性校验 | 不适用 Provider TTL；不得伪造 fresh | 模型来源不能单独支持 ready，参与决策时保持 partial 边界 |
| user/system | 只证明输入/规则来源 | 不按 Provider freshness 重分类 | D-013 的用户城际 availability 排除不变；其他 unknown 仍按既有规则裁决 |

Repository 继续保存现有来源 freshness 快照并原样往返；GET 不按当前墙钟重新改写已完成计划。新 planning attempt 或获批准 replan 使用新的 `evaluated_at` 重算实际重新取用的来源，不能把复用来源、归因或用户确认提升为 fresh。

Step 5 已在该架构内完成 Agent 边界收窄：legacy/V2/V3 repair 仅接收日期/城市/窗口骨架、允许 location/source 目录和稳定无值诊断组成的 `PlanRepairBrief`，不再回传原始模型输出、完整 planning context、自由文本或 Provider observation。generation builder 与 DeepSeek adapter 对 Provider display label/category token 实施双层 allowlist；固定 48-case 离线 eval 两次确定性执行，加权分 `100.0` 且五类安全硬门禁失败为 0。实现未改变公开 API、Repository/SQLite、Schema、依赖或 Provider 调用边界，也不构成 live UAT。

## 错误与降级

稳定错误类别方向：

- `input_invalid`：输入格式或硬约束不合法；
- `configuration_missing`：缺少所需服务配置；
- `provider_unauthorized`：第三方鉴权失败；
- `provider_rate_limited`：第三方限流；
- `provider_timeout`：调用超时；
- `provider_unavailable`：服务不可用；
- `provider_schema_invalid`：provider HTTP/响应 envelope 不能通过 adapter Schema；
- `data_missing`：请求成功但关键数据缺失；
- `data_stale`：数据超过允许时效；
- `model_output_invalid`：模型输出 JSON、日期/时间、POI/来源引用或字段不合法，唯一一次修复后仍失败；
- `constraint_conflict`：计划违反不能自动解决的约束；
- `budget_incomplete`：存在未知费用，无法判断完整预算；
- `confirmation_required`：变更超过自动重规划边界。

重试只用于明确可重试的网络、超时或限流错误，并设置次数、退避和总时限。鉴权失败、Schema 不合法、硬约束冲突和用户确认不能通过盲目重试解决。公开错误可附项目自有的安全 `diagnostic_code`；候选诊断只允许阶段与稳定类别的闭集组合，内部信息缺失时退回通用诊断。任何诊断都不得记录 provider 原文、字段路径或值、Prompt、凭证、异常或堆栈。

D-009 运行语义为：完全缺少可用路线时长就不能生成经过验证的精确时间。只有 `partial` provider 结果仍携带端点和方式合法的 `RouteLeg` 时，调度后计划才能以 uncertainty 形成 `partial`；`unavailable`、缺坐标或空路线不得按 0 排程，进入 `failed`。已知路线、缓冲和游览时长总需求超过日窗口时进入 `conflict`，而不是 provider 错误。

Step 45N–45P 将公开的双交通方式语义落实为有界、逐路段的确定性策略：同时允许公交和步行时先请求公交；只有业务空结果或无 provider error 的本地非法路线允许在剩余的 8 次总预算内尝试步行。AUTH、Schema、timeout、rate limit、server 和 unknown 等 provider-wide 失败不切换 mode。Step 45R 进一步把 terminal 提升为 batch-level 停止信号：最多两条已批准并发路线中，已在途的同批调用可以完成，但任一 terminal 都会阻止后续首选批次及当前或既有候选的全部 fallback；并发 task 异常或外部取消时，未完成 peer 必须先 cancel 并完整 drain，再传播原异常或取消。每段只采用首选顺序中第一个合法结果，合法结果必须匹配 provider、端点、mode、距离/时长上界，且 RouteLeg 引用集合必须与可投影来源精确一致；未采用或非法结果不进入最终计划、来源、error、uncertainty 或 retryable 投影。调用预算或 90 秒总 deadline 耗尽必须进入项目自有安全诊断，不得成为 `internal_error`。scheduler 使用每段实际 mode 的 10/15 分钟缓冲，不能把公交规则套到步行降级段。

## 可观测性

- 每次用户用例生成 `trace_id`；
- 每个需要解释或确认的规划决定生成 `decision_id`；
- 工具日志记录工具名、provider、开始/结束时间、状态、稳定错误码、重试次数和来源数量；
- 计划日志记录版本、状态转换、校验摘要和影响范围；
- 用户确认日志记录展示的影响、选择和确认时间；
- 不记录 API Key、Cookie、完整连接串、完整 Prompt、未脱敏原始响应或不必要个人信息。

B-000 只需要健康日志。业务 trace 和指标在实现对应用户价值时加入。

## 安全边界

- 第三方 Key 仅在后端本地配置中使用，不进入浏览器或可提交文件；
- 外部返回的 POI 描述、天气文本和模型内容都视为不可信数据，不视为系统指令；
- 工具参数必须由类型、枚举、长度和地理范围约束，避免模型任意构造请求；
- 模型只能调用明确注册且当前状态允许的工具；
- Repository 和文件系统操作不直接暴露给模型；
- 默认 CI 和测试不使用真实 Secret；
- 本地服务默认绑定 `127.0.0.1`，不提供公网访问。

## MCP 边界

MCP 不是 MVP 的必需组件。第一版优先使用进程内端口和适配器，减少额外协议、权限和运行故障面。

只有满足以下条件时才考虑 MCP：

- 同一工具需要被多个独立应用或运行时复用；
- 需要清晰的跨进程权限、发现和审计边界；
- 输入输出可以收窄为稳定、结构化、无隐藏副作用的契约；
- 额外部署和失败处理成本有明确收益。

不通过 MCP 暴露：

- 内部预算、日期和冲突校验函数；
- 原始数据库、Repository 或文件系统；
- 第三方通用 HTTP 代理；
- API Key 或 provider 原始响应；
- 会隐式修改多个系统的复合操作。

即使未来采用 MCP，LLM 也只获得任务所需的最小工具集合；应用层仍负责授权、状态、校验和确认。

## 测试方向

- 领域规则：纯单元测试和属性/边界用例；
- 应用状态机：使用端口替身验证转换、重试、确认和局部重规划；
- 适配器：使用脱敏合约 fixture 验证转换与错误映射；
- Repository：使用临时 SQLite 验证持久化合约；
- API：离线集成测试；
- Web UI：组件状态和用户流程测试；
- live smoke：独立标记、显式凭证、默认关闭，不进入普通 CI。

pytest 在导入应用前固定 `APP_ENV=test`，禁止读取 `.env.local`，并由自动 fixture 拒绝非 loopback socket；这两层护栏共同防止本机已有真实凭证时默认测试误装配 provider 或产生费用。

详细选择、门禁和证据规则由 B-000 Step 6 的 `testing-strategy.md` 定义。

## 替换、回滚与演进

- 更换 DeepSeek、高德、和风天气或 SQLite 时，只替换对应适配器，保持端口和领域模型稳定；
- provider 字段或错误变化先在适配器中兼容并通过合约测试，再更新核心模型；
- 状态机和数据模型变化需要显式迁移策略，不能靠 Prompt 隐式兼容；
- D-009 迁移采用 `PlanProposal → deterministic scheduler → existing PlanCandidate` 的绞杀式替换，不长期保留两个可独立生成精确时间的正常路径；
- 失败发布优先用反向提交或 `git revert` 回滚，不使用破坏性工作树清理；
- 出现真实多领域并行、独立审查和调度需求前，不演进为多 Agent。
