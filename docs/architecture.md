# 系统架构

## 文档状态

本文件定义 Intelligent Travel Assistant 当前批准的目标架构。B-000 只建立工程基线和接口边界；除健康检查骨架外，本文描述的旅行业务模块、状态机、Repository 和外部适配器都尚未实现。

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
    ports/
      llm.py
      map.py
      weather.py
      repositories.py
    adapters/
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
| Agent Orchestrator | 需求解释、工具选择、计划提议和说明 | 结构化请求、领域状态、工具目录 | 结构化计划候选、决策记录 | 直接网络、直接 SQL、隐藏副作用 |
| Domain | 旅行请求、行程、费用、约束和来源规则 | 领域值 | 校验结果、派生值 | FastAPI、React、SDK、文件系统 |
| Ports | 外部能力与 Repository 契约 | 项目自有输入模型 | 项目自有结果模型 | provider SDK 类型 |
| Adapters | 第三方传输、鉴权、转换、错误映射 | 端口调用 | 标准结果 envelope | 业务规划决策 |
| Persistence | 计划、trace、来源和确认记录持久化 | Repository 命令 | 领域对象或持久化结果 | UI、模型 Prompt |
| Observability | 结构化日志、trace 关联、运行指标 | 安全事件数据 | 本地日志和诊断 | 秘密、完整 Prompt 或原始敏感响应 |

## 核心数据模型方向

以下是领域概念，不是 B-000 中要实现的数据库 Schema：

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

金额使用十进制定点语义；默认币种为人民币 `CNY`，但币种仍作为显式字段。日期和时间使用目的地当地上下文；需要绝对时间时使用带时区值。

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

## 外部服务职责

| 服务 | 唯一职责 | 不能作为其事实来源的内容 |
| --- | --- | --- |
| DeepSeek | 需求理解、工具调用建议、结构化计划候选、自然语言解释 | 天气、POI、路线、实时价格、预算校验结果 |
| 高德 | 地理编码、基础 POI、地点详情、路线及其提供方元数据 | 酒店库存或实时房价、天气、餐饮预算、计划优劣 |
| 和风天气 | 指定地点和时间范围的天气预报、预警及其元数据 | POI、路线、营业状态、价格、行程安排 |
| 应用代码 | 数据转换、来源关联、日期/时间/路线/预算校验、影响分析 | 不伪造缺失的第三方事实 |

## 主要数据流

### 创建计划

```text
用户输入
→ API Schema 校验
→ TripRequest 规范化
→ 确认缺失的硬约束
→ 编排 Agent 选择窄工具
→ 适配器获取外部数据并记录来源
→ Agent 生成结构化计划候选
→ 领域校验器检查日期 / 时间 / 路线 / 预算 / 冲突
→ 校验失败则受控修订，达到上限后返回冲突
→ 保存计划版本、来源、决策和 trace
→ Web UI 展示 ready / partial / conflict
```

LLM 输出必须先通过 Schema 和领域校验。校验器结果是硬边界，不能通过 Prompt 指令跳过。

### 局部重规划

```text
用户修改 + 基线 plan_version
→ 代码计算直接影响对象
→ 扩展依赖影响范围
→ 分类 same_day / adjacent_day / cross_city / accommodation
→ same_day：自动进入重规划
→ 其他类别：展示影响并等待用户确认
→ 只重新获取过期或受影响数据
→ 生成新计划版本
→ 对受影响范围和跨边界约束重新校验
→ 展示变更摘要，保留旧版本
```

影响范围由确定性代码计算。大模型可以解释影响，但不能自行决定跳过确认。

## 显式状态机

| 状态 | 含义 | 允许的主要下一状态 |
| --- | --- | --- |
| `draft` | 用户仍在输入 | `normalizing` |
| `normalizing` | 校验和规范化需求 | `needs_input`、`collecting`、`failed` |
| `needs_input` | 缺少必要硬约束 | `normalizing`、`cancelled` |
| `collecting` | 调用外部工具并记录来源 | `planning`、`partial`、`failed` |
| `planning` | 生成结构化计划候选 | `validating`、`failed` |
| `validating` | 执行确定性校验 | `ready`、`partial`、`conflict`、`planning` |
| `awaiting_confirmation` | 变更跨越自动授权边界 | `replanning`、`ready`、`cancelled` |
| `replanning` | 对批准影响范围生成新版本 | `validating`、`failed` |
| `ready` | 计划通过当前必需校验 | `awaiting_confirmation`、`replanning` |
| `partial` | 有可用结果但数据或预算不完整 | `collecting`、`awaiting_confirmation`、`replanning` |
| `conflict` | 存在不能自动解决的约束冲突 | `needs_input`、`awaiting_confirmation`、`replanning` |
| `failed` | 当前请求无法产生安全结果 | `collecting`、`planning`、`cancelled` |
| `cancelled` | 用户取消当前流程 | 无 |

状态转换由应用层执行并记录原因；工具不能自行改变全局状态。

## 状态与持久化

- `TripPlan` 是计划内容的事实来源，每次成功重规划创建新版本；
- 应用状态由显式状态机维护，不能只存在于 Prompt 或前端内存；
- Web UI 使用服务端响应作为计划和确认状态的事实来源；
- 外部响应可按 provider、查询参数和有效期建立受控缓存，但不能把过期缓存伪装为最新数据；
- 计划、来源、工具调用和用户确认通过 `trace_id`、`plan_id`、`plan_version` 和 `decision_id` 关联；
- MVP 使用 SQLite，具体表、索引和迁移在后续持久化任务中设计。

## 错误与降级

稳定错误类别方向：

- `input_invalid`：输入格式或硬约束不合法；
- `configuration_missing`：缺少所需服务配置；
- `provider_unauthorized`：第三方鉴权失败；
- `provider_rate_limited`：第三方限流；
- `provider_timeout`：调用超时；
- `provider_unavailable`：服务不可用；
- `provider_schema_invalid`：响应不能通过项目 Schema；
- `data_missing`：请求成功但关键数据缺失；
- `data_stale`：数据超过允许时效；
- `model_output_invalid`：模型输出格式或字段不合法；
- `constraint_conflict`：计划违反不能自动解决的约束；
- `budget_incomplete`：存在未知费用，无法判断完整预算；
- `confirmation_required`：变更超过自动重规划边界。

重试只用于明确可重试的网络、超时或限流错误，并设置次数、退避和总时限。鉴权失败、Schema 不合法、硬约束冲突和用户确认不能通过盲目重试解决。

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

详细选择、门禁和证据规则由 B-000 Step 6 的 `testing-strategy.md` 定义。

## 替换、回滚与演进

- 更换 DeepSeek、高德、和风天气或 SQLite 时，只替换对应适配器，保持端口和领域模型稳定；
- provider 字段或错误变化先在适配器中兼容并通过合约测试，再更新核心模型；
- 状态机和数据模型变化需要显式迁移策略，不能靠 Prompt 隐式兼容；
- 失败发布优先用反向提交或 `git revert` 回滚，不使用破坏性工作树清理；
- 出现真实多领域并行、独立审查和调度需求前，不演进为多 Agent。
