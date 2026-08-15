# 当前实施计划

## 当前状态

- 当前任务：`F-001 单城市双日旅行计划垂直切片`
- 任务等级：`L`
- 当前分支：`feat/f-001-single-city-two-day-plan`
- 当前形式状态：补充 Step 45G 已完成 D-009 架构变更控制和详细设计，九项实施决策、stacked PR 和新范围例外均已批准；Step 45E 的真实 UAT `FAIL` 仍是最新 live 结论。形式上仍等待用户批准 Step 46，但该合并 Step 继续受调度迁移未实施和真实 UAT FAIL 阻塞；实际下一动作是另行批准 Step 45H 的离线实现。最后一次 live 授权已经消耗。
- 已完成：Step 0 至 Step 45，以及补充 Step 45A–45G；最新真实任务以 `candidate_repair_time_invalid` 安全失败，没有 ready/partial 计划。Step 45G 不包含生产实现或新 live 证据。
- Step 38 已完成：严格按一次杭州双日计划、DeepSeek 最多 3 次、高德最多 16 次、和风最多 4 次、总费用不超过 12 元的授权执行。三家服务均返回可解析结果；计划经确定性校验进入 `conflict`，另以同一授权预算内 1 次高德公交路线窄探针补齐路线 live 契约。
- Step 39 已按同一调用和 12 元费用边界执行；唯一任务因 DeepSeek `provider_schema_invalid` 安全失败，UAT 结论为 `FAIL`，未重试或再次提交。
- Step 41 已完成离线阻塞修复和独立全量门禁；Step 42 已同步长期文档、证据和 120 文件单 PR 范围例外；Step 43 已形成单一本地提交；Step 44 已推送分支并创建 Draft PR #4；Step 45 的远程 Windows 离线门禁已通过。补充 Step 45A 的唯一真实任务以 `model_output_invalid` 安全失败；Step 45B 已离线补齐候选诊断、Prompt 规则和纵向回归；Step 45C 的完整候选最终以 2 项 `route_conflict` 进入 `conflict`；Step 45D 已离线修复候选路线正数时间窗口准入；Step 45E 则证明 generation 与唯一一次 repair 仍未生成时间可行候选，安全诊断为 `candidate_repair_time_invalid`。在获得 ready/可解释 partial 证据或用户正式调整验收决策前，不得进入 Step 46、标记 ready 或合并。

任务卡、范围、验收与完整 Step 状态以 [current-task.md](./current-task.md) 为准。本文件只维护执行顺序、当前 Step 输入输出、验证和停止条件，不复制完整任务卡。

## 已完成结果

### Step 0：事实与契约复核

- 确认 `main` 与 `origin/main` 同步，基线提交为 `50980887dadc0500d98dcd29966a5da2da74b2e2`；
- 确认 Python 3.13.3、Node.js 22.16.0、pnpm 11.19.0 和统一门禁通过；
- 官方确认 `deepseek-v4-flash`、高德 Web Service 边界、和风 JWT/API Host 及天气日期范围；
- 记录技术栈和测试策略中的 B-000 状态漂移；
- 未修改文件，未调用真实 API。

### Step 1：功能分支

- 创建并切换到 `feat/f-001-single-city-two-day-plan`；
- 工作区保持干净；未提交、未推送。

### Step 2：任务与文档固化

- 将用户批准的 F-001 任务卡、十二项决策和两个注释覆盖固化到当前任务；
- F-001 成为 roadmap 中唯一 `ACTIVE` 任务；
- 同步文档地图、进度和根 README；
- 修正 GitHub 远程/CI 与 B-000 review 的旧状态；
- 将文档状态检查器的任务 ID 匹配从 B-000 写死值泛化，并增加 F-001 回归测试；
- 未写旅行规划业务代码，未调用真实 API，未提交或推送。

### Step 3：冻结跨层契约

- 新增 provider-neutral 的 `contracts` 包，冻结请求、金额、费用、来源、地点、路线、天气、计划、响应、状态和错误枚举；
- Money 的 JSON/OpenAPI 表达固定为十进制字符串，运行时拒绝二进制浮点和超过两位小数；
- `unknown` 金额必须为空，`verified` 费用和外部事实必须引用来源；
- 冻结 F-001 状态转换表，`needs_input`、`ready`、`conflict` 为当前任务终态，`partial`/`failed` 只可经受控 retry 返回规范化；
- 新增 [api-contract.md](../api-contract.md)，明确 POST、GET、retry、幂等、HTTP 状态和安全错误 envelope；
- API 路由、状态机执行器、Repository、算法和 provider 调用均未实现；
- 新增 8 项契约测试；全量门禁通过，后端共 15 项 pytest。

### Step 4：建立标准验收样例

- 固定 `2026-08-13T10:00:00+08:00`、杭州、D+2/D+3、2 人、4000 元的共享 synthetic 请求；
- 建立 `ready`、`partial`、`conflict`、`failed` 四个严格响应样例；
- 每个 case 明确预期终态、计划存在性、retryable、费用/未知项、错误、不确定性、来源 provider 和禁止主张；
- 新增 `TripPlan.locations` 地点目录，解决活动、住宿、路线和天气地点引用无法解析的契约缺口；
- 自动验证全部来源 ID 和地点 ID 引用、fixed clock 日期范围、synthetic 标识、URL/凭证隔离和禁止主张；
- 新增 [acceptance-cases.md](../acceptance-cases.md) 作为唯一验收样例说明；
- 新增 18 项验收测试，全量门禁通过，后端共 33 项 pytest；
- 未实现规划规则、API 路由、状态执行器、fake adapter 或真实 provider 调用。

### Step 5：领域模型红绿测试

- 先运行领域测试，确认因 `intelligent_travel_assistant.domain` 不存在而在收集阶段失败，保留了可复现的 RED 证据；
- 新增纯标准库 `domain` 基础，实现 Money、费用、来源目录、坐标、地点、路线、天气和计划结构的不变量；
- 新增稳定的 `DomainInvariantError`，领域包不依赖 Pydantic、FastAPI、HTTP、SQLite 或 provider SDK；
- 以 19 项领域测试覆盖正向及高风险负向规则，并用 AST 测试锁定依赖边界；
- 明确把动态日期窗口、日内排程、路线链和预算汇总留给 Step 6–9，未提前实现；
- 全量门禁通过：后端 52 项 pytest、前端 13 项 Vitest、文档检查器 21 项测试、类型检查和构建均通过；
- 未访问真实 API，未读取或写入凭证，未提交或推送。

### Step 6：日期和输入约束

- 新增纯领域 `TripRequestInput`，应用边界显式传入评估时刻，领域层不读取系统当前时间；
- 将评估时刻规范化到上海 UTC+08:00，以包含边界方式校验开始日 D+1 至 D+5；
- 校验严格连续双日、日期顺序、跨月/跨年、人数 1–8、偏好最多 5 个和自由文本最多 200 字；
- 城市、偏好和自由文本清理首尾空白，并在规范化后拒绝重复偏好；
- 冻结请求契约通过离线测试映射到领域输入，`end_date` 由应用边界按开始日加一天派生；
- 新测试先因 `TripRequestInput` 不存在而 RED，最小实现后 29 项日期/输入测试转绿；
- 全量门禁通过：后端 81 项 pytest、前端 13 项 Vitest、文档检查器 21 项测试、类型检查和构建均通过；
- 未实现排程、路线、预算、API 或 provider 调用，未访问网络、凭证，未提交或推送。

### Step 7：时间窗口和重叠校验

- 新增 `DailyAvailability`、`ActivityTimeSlot` 和 `TwoDayTimePlan` 纯领域模型；
- 两个窗口必须按 day offset 恰好覆盖 0/1，时间采用无时区的目的地本地 wall-clock 语义；
- 每日窗口和活动均要求正向同日时长，零时长、反向和跨夜均以稳定错误拒绝；
- 活动必须属于双日日期并完整落在相应窗口内，边界贴合和相邻活动首尾相接允许通过；
- 重叠检测按日期分组并在副本上排序，不受输入顺序影响且不修改调用方活动顺序；
- frozen synthetic 请求和 ready 计划可无漂移映射到时间规则；
- 新测试先因领域类型不存在而 RED，最小实现后 23 项时间规则测试转绿；
- 全量门禁通过：后端 104 项 pytest、前端 13 项 Vitest、文档检查器 21 项测试、类型检查和构建均通过；
- 未实现路线时长、路线链、自动排程、预算、API 或 provider 调用，未访问网络、凭证，未提交或推送。

### Step 8：路线连续性校验

- 新增 `RouteActivity`、`ExpectedRouteLeg`、`DailyRoutePlan` 和结构化路线裁决结果；
- 按“住宿 → 活动地点序列 → 住宿”生成期望路线链，相邻同地点不生成自环段；
- 已提供路线必须是期望链的有序子序列，错端点、反向/乱序和额外段以稳定错误拒绝；
- 缺失路线返回 `missing` 及精确缺段，不冒充 verified，也不调用 provider 自动补路；
- 校验窗口开始至首活动、活动间、末活动至窗口结束三类间隔，恰好填满可通过，超出一分钟即失败；
- 不同地点间零交通间隔为冲突，同地点首尾相接无需路线；
- ready synthetic 四段路线全部 verified，partial synthetic 空路线全部 missing；
- 新测试先因 `DailyRoutePlan` 不存在而 RED，最小实现后 15 项路线测试转绿；
- 全量门禁通过：后端 119 项 pytest、前端 13 项 Vitest、文档检查器 21 项测试、类型检查和构建均通过；
- 未调用高德、未补路或修改活动，未实现预算、API 或 provider adapter，未访问凭证，未提交或推送。

### Step 9：Decimal 预算和 unknown 规则

- 新增 `BudgetCostItem`、`BudgetSummaryResult`、费用类别和预算裁决枚举；
- known total 只累加 verified、estimated 和 user_provided 金额，unknown 无金额且只增加 unknown count；
- 以整数分精确累加后还原两位 CNY Decimal，不受全局 Decimal context 精度影响；
- 已知合计超预算始终为 over budget；否则有 unknown 为 indeterminate；全部已知且未超才为 within budget；
- 已知合计恰好等于预算允许通过，但存在 unknown 时仍不可判定；
- ready、partial、conflict synthetic 的 known total、unknown count 和 assessment 均由领域规则精确重算；
- 新测试先因领域预算类型不存在而 RED，最小实现后 16 项预算规则测试转绿；
- 全量门禁通过：后端 135 项 pytest、前端 13 项 Vitest、文档检查器 21 项测试、类型检查和构建均通过；
- 未获取、推测或生成真实价格，未实现 provider、状态机、API 或 Agent，未访问凭证，未提交或推送。

### Step 10：provider result、错误分类和 freshness 模型

- 新增 provider-neutral `ProviderResult`、`ProviderError`、结果/错误/freshness 枚举和显式时效裁决；
- ok、partial、unavailable 各自冻结合法的 data/error/time/source 组合，unknown validity 必须有警告；
- 只允许 DeepSeek、高德和和风外部 provider，有数据时来源必须存在且 provider 一致；
- timeout、rate limited、server 可重试；auth、schema、empty result、unknown 不可盲目重试；
- 错误对象不保存原始异常/body，警告拒绝 URL、Authorization、Key/Token/Secret、换行和超长文本；
- freshness 使用显式评估时刻，valid until 边界包含在 fresh 内；
- ready、partial、failed synthetic 的来源 freshness 和 timeout/server 策略均由领域模型重算；
- 新测试先因 provider result 类型不存在而 RED，最小实现后 39 项 provider 结果测试转绿；
- 全量门禁通过：后端 174 项 pytest、前端 13 项 Vitest、文档检查器 21 项测试、类型检查和构建均通过；
- 未定义端口、adapter 或 HTTP 重试器，未访问网络/凭证，未提交或推送。

### Step 11：高德、和风和 DeepSeek 端口

- 新增 `AmapPort`、`QWeatherPort` 和 `DeepSeekPort` 三组异步 Protocol；
- 精确冻结五个工具方法：城市解析、POI 搜索、单段路线、逐日预报和当前预警；
- DeepSeek 的 `generate_plan_candidate` 是应用规划依赖，不计入工具白名单，也不能声明终态；
- 所有方法只接收一个 frozen/slotted typed request，并返回具体 payload 的 `ProviderResult`；
- 端口 DTO 使用项目自有 dataclass/领域值，不包含裸 dict/Mapping/Any、Secret/Header/Base URL 或 SDK/HTTP 类型；
- AST/annotation 测试禁止端口依赖框架、HTTP/SDK、settings/config/adapters/infrastructure 或环境读取；
- 新测试先因 application 包不存在而 RED，最小实现后 15 项端口契约测试转绿；
- 全量门禁通过：后端 189 项 pytest、前端 13 项 Vitest、文档检查器 21 项测试、类型检查和构建均通过；
- 未实现 fake、真实 adapter、HTTP、Agent、状态机或 API，未访问网络/凭证，未提交或推送。

### Step 12：可编程 fake adapter

- 新增三个异步端口 fake，并为六个方法分别配置独立、有序的 `ProviderResult` 脚本；
- 每次调用先记录带全局序号的冻结 typed request 快照，再消费对应脚本；未配置与耗尽分别抛出稳定安全错误；
- 配置时强制 provider 匹配、synthetic 警告及 `synthetic_` 来源类型，避免离线数据冒充真实响应；
- ok、partial、unavailable 和七类安全错误均可直接注入，不联网、不读环境变量、不 sleep 或自动重试；
- 生产入口无 fake 导入或默认装配；新增测试先因 adapters 包不存在而 RED，最小实现后 17 项测试转绿；
- 全量后端 206 项 pytest、Ruff format/check、strict mypy 和构建通过；未实现状态机、编排、真实 adapter 或 API，未访问网络/凭证，未提交或推送。

### Step 13：状态机及非法状态转换测试

- 新增纯应用层 `PlanningStateMachine.transition` 单一状态裁决入口，以及冻结 typed command/result；
- 直接复用 Step 3 的 `ALLOWED_PLANNING_TRANSITIONS`，不复制或修改第二份转换图；
- 系统性覆盖 11×11 状态组合：全部允许边成功，全部非边、自环和无出口终态外跳稳定失败；
- `partial`/`failed → normalizing` 只接受显式 `retry` 且 `retryable=true`，retry 不能伪装成普通推进；
- 状态机不依赖端口、fake、provider、框架、环境、网络或计时能力，不保存任务或实现 retry attempt；
- 新测试先因 state machine 包不存在而 RED，最小实现后 135 项状态机测试转绿；全量后端 341 项 pytest、Ruff format/check、strict mypy 和构建通过；未实现编排、Repository、API，未提交或推送。

### Step 14：离线应用编排闭环

- 新增构造函数注入三组端口的 `OfflinePlanningOrchestrator`，生产代码不导入或实例化 fake/真实 adapter；
- typed 请求依次执行城市、POI、天气、当前预警、候选计划和首段路线，并由 Step 13 状态机生成完整不可变状态轨迹；
- happy 路径形成候选后停在 `validating`，不在 Step 17 最终确定性校验前提前宣称 `ready`；
- 城市/POI/DeepSeek 不可用稳定进入 `failed`；天气、预警、路线不可用或任一可用结果为 partial 时保留原始 `ProviderResult` 并进入 `partial`；
- 路线只请求首两个候选活动间的一段，完整住宿往返路线补全留给 Step 17；
- 编排结果冻结并保留各 provider 的三态、来源和安全错误；重复运行不共享状态轨迹；
- 新测试先因 application services 包不存在而 RED，最小实现后 9 项编排测试转绿；全量后端 350 项 pytest、Ruff format/check、strict mypy 和构建通过；未实现工具预算、timeout/retry、模型修复、路线补全、Repository 或 API，未提交或推送。

### Step 15：工具白名单、调用预算和超时边界

- 新增五个冻结工具加 DeepSeek 候选生成的 `ToolCallCapability`；未知字符串和错误阶段在预算消费前拒绝；
- 冻结逻辑调用预算：城市解析 1、POI 3、天气预报 1、当前预警 1、路线 8、DeepSeek 生成 1；每项独立计数并在端口调用前拒绝超限；
- 冻结单次时限：高德/和风 6 秒、DeepSeek 35 秒；任务总时限 90 秒，路线活跃 permit 最多 2；
- `ToolCallGovernor` 使用注入的单调时钟和冻结 permit/record/snapshot，不依赖异步运行时、网络、环境或 sleep；拒绝时使用稳定安全错误；
- 调用前要求剩余总时限覆盖完整单次 timeout；调用返回后区分单次超时和任务总超时，精确边界允许完成；
- 拒绝时不生成调用记录；route permit 在完成或超时后释放；非法/重复/跨 governor permit、时间倒退和非法时钟均稳定拒绝；
- Step 14 六个端口调用均接入 reserve/complete，outcome 保留治理快照；测试证明预算预耗尽时 fake 调用数仍为零；
- 新测试先因 application tooling 包不存在而 RED，最小实现及编排接入后新增 37 项测试；全量后端 387 项 pytest、Ruff format/check、strict mypy 和构建通过；
- 当前 deadline 是应用层调用前/返回后裁决，不会中断永不返回的 await；真实网络 I/O 取消仍由后续 adapter 的客户端 timeout 实现。未实现 HTTP 重试、sleep/backoff、DeepSeek 修复或完整路线并发，未提交或推送。

### Step 16：DeepSeek 严格输出和单次修复测试

- `DeepSeekPort` 改为返回 provider-neutral `ModelTextOutput`，并新增窄的 `repair_plan_candidate`；模型文本先被视为不可信数据，只有 `DeepSeekCandidateResolver` 可以把它转换为 `PlanCandidate`；
- 本地解析器要求精确根/day/activity 字段、严格 JSON、无重复键、严格日期/时间/UUID、恰好双日、每日 1–3 个活动，并只允许引用上下文中的地点和 observation source；
- 模型不能注入终态、provider、tool calls、路线、候选集外 POI 或虚构来源；命中提示控制标记时直接安全失败且不重放给 repair；
- 可修复结构错误最多调用一次独立 repair capability；repair 预算为 1、单次窗口 35 秒，并且仍要求任务剩余时间覆盖完整窗口；
- 首次有效只调用生成；修复成功返回 typed candidate；第二次无效返回安全 `model_output_invalid`，结果不携带原始模型文本；provider unavailable 的稳定错误语义保持不变；
- Step 14 编排统一通过 resolver 获取候选，outcome 显式记录修复状态和候选解析错误，不把文本结果误当成领域候选；
- 相关回归 112 项、全量后端 421 项 pytest、前端 13 项 Vitest、文档检查器 21 项测试以及 format/lint/typecheck/build/文档契约全部通过；未调用真实模型、未读取凭证、未实现路线补全或终态裁决，未提交或推送。

### Step 17：路线补全和最终确定性校验

- `OfflinePlanningRequest` 新增显式住宿锚点、两日时间窗口、费用项和数据评估时刻；不使用隐藏住宿、时间、费用或 freshness 默认值；
- `DailyRoutePlan.expected_legs()` 公开纯推导结果，编排按“住宿 → 当日活动 → 住宿”生成每个非自环路段；示例双日各一个活动时形成四段，逐段受既有路线预算和阶段治理；
- 缺坐标时不调用 provider，超时/不可用、错误端点、错误模式或错误来源的路线不进入已验证链，统一保留为结构化 `partial`；已知路线超过可用活动间隔则为 `conflict`；
- `FinalValidationResult` 以冻结 typed issue 汇总时间窗口/重叠、路线、预算、地点/POI、天气日期和地点、provider 降级、来源引用与 freshness；模型不能声明或覆盖终态；
- `ready` 要求零 issue；事实不完整、unknown 费用、过期/未知有效期或未验证硬约束进入 `partial`；超预算、时间/路线硬冲突或引用越权进入 `conflict`，且 conflict 优先于 partial；
- 活动来源进一步限定为 POI 响应来源，路线来源必须属于对应路线响应；同一来源 ID 的冲突记录、候选集外/异城地点和过期来源均不能形成假 ready；
- Step 14 编排已从停在 `validating` 改为始终经过 `validating` 后进入 `ready`、`partial` 或 `conflict`；关键城市/POI/DeepSeek 失败仍为 `failed`；
- 新增 13 项测试；核心相关回归 93 项、全量后端 434 项 pytest、Ruff format/check 和 strict mypy 通过。未调用真实服务、未实现 Repository/API/UI，未提交或推送。

### Step 18：进程内任务 Repository 和幂等规则

- 新增应用层 `PlanningJobRepository` Protocol、冻结 `PlanningJob`/reservation/请求指纹值和稳定安全错误；
- 请求指纹对规范化 typed 请求的 canonical JSON 做 SHA-256，并排除 `client_request_id`；不使用 Python 随机 hash，也不保留 canonical 原文；
- 新增 `InMemoryPlanningJobRepository`，用单进程 `asyncio.Lock` 原子化 ID 预留；同一 client ID/同一请求复用原 job，不分配新 ID，不同请求稳定冲突；
- job 快照不可变；普通推进和 retry 均复用 Step 13 状态机，以 `version` 做乐观并发控制；retry 仅允许 retryable 的 partial/failed，最多 3 次 attempt，并生成新 trace；
- 12 项红绿测试覆盖稳定指纹、去重、冲突、20 路并发单创建、快照不可变、非法跳转、版本竞争、retry attempt/trace/上限、不存在和离线依赖边界；
- 定向 12 项测试、Ruff format/check 和 strict mypy 通过；统一门禁通过，后端共 446 项 pytest、前端 13 项 Vitest、文档检查器 21 项测试以及构建/文档契约均为绿色。未实现 SQLite、migration、FastAPI 路由、后台 worker、跨进程锁或真实外部调用，未提交或推送。

### Step 19：POST、GET 和 retry API

- 新增独立 `api/` HTTP adapter，三个路由只依赖 `PlanningJobRepository` Protocol；`app.py` 作为组合根为每个应用实例装配独立进程内 Repository；
- POST 返回 `202`、相对 `Location` 和严格 `TripPlanResponse`，同请求重复提交复用同一资源，不同内容稳定映射 `409 idempotency_conflict`；
- GET 返回当前资源；不存在和非 UUID 路径统一映射 `404 job_not_found`；retry 读取当前 version 后原子推进，成功保留 job/client ID、更新 attempt/trace，不可重试和 attempt 上限统一映射 `409 retry_not_allowed`；
- HTTP/Pydantic 请求错误统一为 `422 input_invalid`；未知 Repository 异常统一为无内部细节的 `500 internal_error`；所有错误均使用既有 `ApiErrorResponse`；
- 新增 12 项离线 API 测试，覆盖精确公开字段、Location、幂等、404/409/422/500、retry 上限、应用实例隔离、健康接口兼容和无编排/provider/存储依赖；相关 39 项回归通过；统一门禁中的后端 458 项 pytest、前端 13 项 Vitest、文档检查器 21 项测试、Ruff format/check、strict mypy、Vite build 和文档契约均为绿色；
- POST 只登记 `draft` job，不启动编排或后台执行。未接入 SQLite、真实 provider、产品 UI，未提交或推送。

### Step 20：API 五种终态与安全错误

- 新增冻结 `PlanningJobResult`，集中校验五种终态的 plan/diagnostics/retryable 组合、来源和地点引用、敏感赋值文本及 duplicate source；
- Repository 新增原子 `record_result`，复用唯一状态机并校验 result 的日期、预算和目的地 adcode 与原请求一致；普通 `advance` 对合法终态返回 `result_required`，不能创建缺少结果载荷的伪终态；
- retry 保留 job/client ID、更新 attempt/trace，同时清空上一次 result，避免 normalizing 响应继续展示陈旧计划、来源或错误；
- API mapper 只从已验证结果快照填充 resolved destination、plan、violations、warnings、uncertainties、sources 和 errors；内部 version、指纹和原请求仍不公开；
- 补充第五个“住宿区域需要澄清”的 `needs_input` synthetic fixture；ready/partial/conflict/needs_input/failed 五类 GET 响应与冻结 JSON 逐字段一致；
- 新增 16 项终态/负向测试，并扩展验收测试；相关 61 项回归通过；统一门禁中的后端 477 项 pytest、前端 13 项 Vitest、文档检查器 21 项测试、Ruff format/check、strict mypy、Vite build 和文档契约均为绿色。未启动规划执行、后台任务、真实 provider、SQLite 或前端，未提交或推送。

### Step 21：产品 UI 设计稿

- 新增自包含可交互参考稿 `docs/design/f-001-ui-reference.html`，覆盖输入、处理中、ready、partial、conflict、needs_input、failed、来源、费用可信状态、unknown、安全错误和恢复动作；
- 采用“城市旅笺 / field journal”视觉方向，桌面为输入/结果双栏，窄屏结果优先且输入可折叠；没有生产 React、API/provider、图片、地图、PDF、外部字体/脚本或新增依赖；
- 修正 partial/conflict 演示状态，使未完成路线不标为已验证、未知费用不显示为 0、冲突住宿费用和来源数量与裁决一致；
- 本地 Microsoft Edge/Playwright 在 `1440×900` 和 `390×844` 完成结构与视觉检查；七种视图切换、关键状态文案、键盘焦点和恢复动作可观察，窄屏 `documentWidth=390` 无水平溢出，控制台 0 error/0 warning；浏览器仅访问本地静态资产；
- HTML 通过项目前端 Prettier 检查。未提交、未推送。

### Step 22：用户批准并冻结 UI 参考

- 用户明确批准 Step 21 的桌面 `1440×900` 与窄屏 `390×844` 参考稿，未提出修改；
- `docs/design/f-001-ui-reference.html` 以 SHA-256 `F2AA5727F7F0FAC5300BF49BD454F6A2DB2437D3D25ADC29B5B9BB54113C1434` 标识为 Step 23–27 实现参考；
- 冻结“城市旅笺”视觉方向、信息顺序、桌面双栏、窄屏结果优先/输入折叠、七种视图、unknown、来源/时效、安全错误和恢复动作；
- 允许生产实现做组件拆分、语义化和无障碍增强、连续窄屏适配，但不得改变状态语义、弱化来源或扩大产品范围；
- 本 Step 仅更新批准与冻结记录，未修改原型或生产 React；统一门禁中后端 477 项 pytest、前端 13 项 Vitest、文档检查器 21 项测试、format/lint/typecheck/build 和文档契约全部通过；未提交、未推送。

### Step 23：旅行需求表单

- 以无新增依赖的 React 受控表单落实冻结设计，覆盖城市、开始日期、人数、总预算、兴趣、节奏、市内交通、住宿、可选住宿费用、餐饮预算和补充要求；
- 新增与后端冻结请求同形的 TypeScript DTO 和显式映射；金额保持 Decimal 字符串，餐饮默认 `100.00`，未知住宿与城际费用为 `null`，结束日期仍由后端派生；
- 自定义校验覆盖城市、日历日期、1–8 人、正数总预算、非负可选费用、至少一种交通、住宿锚点和 200 字补充要求；错误与字段关联并聚焦首错；
- 首页切换为“城市旅笺”产品工作台，提交后只显示内存 DTO 准备态；保留健康客户端与测试，不调用计划 API 或任何外部服务；
- 前端 format/lint/typecheck、18 项 Vitest 和 Vite build 通过；Microsoft Edge/Playwright 验证桌面/390px、空表单错误焦点、有效 DTO 准备态、无水平溢出、0 console error/warning 和仅本机请求；统一门禁中的后端 477 项 pytest、文档检查器 21 项测试和全部文档契约也通过；未提交、未推送。

### Step 24：轮询和真实处理阶段显示

- 新增严格的 TypeScript 计划 API client，只访问同源 POST/GET 端点，并校验精确根字段、UUID、日历日期、ISO 时间、Decimal、稳定错误码和公开状态；
- 新增受控任务 hook：每两秒最多轮询 15 次，终态立即停止，达到上限后保留最新状态并允许手动继续；新请求、重置和组件卸载会取消在途请求；
- UI 如实展示 `draft`、规范化、事实收集、结构规划、路线补全和确定性校验阶段，校验任务标识与允许状态跃迁；不根据时间伪造后端进度；
- 表单提交接入本机 POST，提交/跟踪期间阻止重复请求；HTTP、网络、Schema 和状态不一致均映射为安全用户错误，不泄漏原始异常；
- 前端 format/lint/typecheck、36 项 Vitest 和 Vite build 通过；本地 Edge 验证真实 `202 draft`、15 次 GET 后暂停、手动恢复、桌面/390px、零控制台错误及仅本机请求；
- 后端未改动，POST 仍只登记 `draft`，终态详情留给 Step 25–26；未调用 provider，未提交、未推送。

### Step 25：双日计划、天气、路线和预算卡片

- 新增严格终态嵌套 TypeScript DTO 和逐层 guard，并校验计划日期、目的地、预算和地点引用与请求摘要一致；
- ready/partial 结果页实现双日活动、天气/预警、路线摘要、费用可信状态和预算汇总；前端只展示服务端裁决，不重算预算或路线；
- `unknown` 费用无金额并显示为“未知”，已知零费用仅在服务端明确给出金额时显示 `¥0.00`；
- 43 项前端 Vitest、format/lint/typecheck/build 通过；本地浏览器用后端冻结 ready/partial synthetic JSON 验证桌面和 390px 窄屏，结果优先、无水平溢出且控制台 0 error/0 warning；
- 浏览器 fixture 拦截只证明前端能消费后端冻结契约，不代表 POST 已自动执行规划；未改后端、未调用 provider、未提交或推送。

### Step 26：来源、不确定性、冲突和错误界面

- 前端 guard 与后端终态不变量对齐，接受冻结 conflict 计划并拒绝伪造终态组合、重复来源和悬空来源引用；
- 新增来源/时效、warnings、uncertainties、violations 和安全 errors 组件，逐条展示 provider、获取时间、有效截止和 freshness；
- conflict 保留确定性预算冲突且不把候选展示为可执行行程；needs_input 明确缺失字段；failed 只显示安全错误和已保留来源；
- 服务端声明可重试时只展示禁用的恢复入口，不在本 Step 提前调用 retry API；
- 54 项前端 Vitest、format/lint/typecheck/build 通过；浏览器使用后端冻结 partial/conflict/needs_input/failed JSON 验证桌面和 390px 窄屏、结果优先、无水平溢出及 0 console error/warning；
- 全部浏览器请求仅访问本机 Vite、`/@fs` fixture 和被拦截的本机 `/api`；未改后端、未调用 provider、未提交或推送。

### Step 27：重试、防重复提交和窄屏布局

- 严格 client 接入同源 `POST /api/trip-plans/{job_id}/retry`，只接受 `202 normalizing` 且已清空旧计划、来源和诊断的快照；
- 任务 hook 只允许 retryable 的 partial/failed 且 attempt 小于 3，复用 job/client ID，强制 attempt 加一、trace 更换，并在请求开始时移除旧终态；同步 busy guard 阻止双击重复请求；
- retry 后的全部轮询快照保持相同 job/client ID、attempt 和 trace，拒绝状态、标识或尝试不一致；安全 409、网络失败和非法响应均进入脱敏错误界面；
- partial/failed 提供明确重试入口，三次上限不再展示重试；needs_input 返回表单时按服务端字段聚焦住宿输入，其他恢复动作聚焦城市；
- 窄屏非初始状态结果优先并折叠输入，保留带 `aria-expanded` 的展开入口；桌面双栏和信息层级不变；
- 61 项前端 Vitest、format/lint/typecheck/build 通过。Microsoft Edge/Playwright 验证 partial/failed retry、双击单请求、attempt 2、390×844 输入折叠、结果优先、焦点恢复、无水平溢出及 0 console error/warning；全部响应为本机 synthetic 数据，未调用 provider；
- 完成后停止，等待用户批准 Step 28。

### Step 28：DeepSeek adapter 及离线契约测试

- 在 `adapters/providers/` 实现 `DeepSeekPort` 的 Chat Completions HTTP adapter，固定正式 Base URL、`deepseek-v4-flash`、关闭 thinking、JSON object 输出、8000 token 上限和 35 秒客户端超时；
- 配置由构造函数显式注入并隐藏 API Key，不读取环境；每个生成或修复端口调用只执行一次 HTTP 尝试，不 sleep、不自动重试，逻辑调用与修复预算继续由应用治理层负责；
- Prompt 只允许项目冻结的候选结构，结构化上下文、provider observation 和待修复文本都作为不可信 user data 传入，不开放模型工具调用；
- 响应在进入 `ModelTextOutput` 前校验状态码、1 MB body、顶层对象、模型、唯一 choice、结束原因、assistant role、无 tool/reasoning 内容、非空文本和 32000 字符上限；错误映射为项目自有安全类别，不保留上游 body、异常或凭证；
- 21 项离线 HTTP mock transport 测试覆盖精确请求、修复隔离、HTTP/传输失败、空/畸形/超大响应、固定配置和零环境/SDK/log/sleep 边界；测试先因 provider adapter 不存在而 RED，最小实现后转绿；
- 后端全量 498 项 pytest、Ruff format/check 和 strict mypy 通过；未读取真实凭证、未调用 DeepSeek、未装配生产任务执行器、未提交或推送；
- 完成后停止，等待用户批准 Step 29。

### Step 29：高德地理编码和 POI adapter

- 在现有 provider adapter 包实现城市解析和 POI 搜索，固定正式 `https://restapi.amap.com`、地理编码 v3、POI 搜索 2.0 v5、6 秒客户端超时、禁止 redirect 和环境代理；
- 城市请求使用 `address` 与 `city` 双重限定；只接受唯一城市级结果，并兼容四个直辖市以空数组返回 `city`、以省级名称表达城市的官方字段差异；高德坐标明确标为 provider native；
- POI 请求强制 `region=<city adcode>`、`city_limit=true`、第一页和最多 25 条；F-001 仅冻结 `scenic_area -> 110000`、`museum -> 140100` 两个项目类别映射，未知类别在传输前拒绝；
- POI provider ID 经固定 UUID namespace 转换为稳定项目 ID；辖区 adcode 按行政层级归属城市，异城、坏坐标、坏类型或重复记录被丢弃，有剩余候选时返回 partial，否则安全失败；缺坐标保持 `None`，不伪造位置；
- HTTP 状态和高德 HTTP 200 内的 `infocode` 分别映射 auth、rate limited、server、schema 和 unknown；每个端口调用只执行一次 HTTP 尝试，不保存或输出上游错误 body、Key 或异常；
- 42 项离线 mock transport 测试先因 Amap provider 模块不存在而 RED，最小实现后转绿；后端全量 540 项 pytest、Ruff format/check 和 strict mypy 通过；
- route 方法留给 Step 30；环境加载和生产装配留给 Step 32。未读取真实 Key、未调用高德、未提交或推送；
- 完成后停止，等待用户批准 Step 30。

### Step 30：高德路线 adapter

- 在现有 `AmapAdapter` 实现单路段步行和公共交通路线，固定高德路线规划 2.0 的 v5 walking 与 transit integrated 端点、6 秒客户端超时、禁止 redirect 和环境代理；
- 公共交通官方请求必须携带起终点 `citycode`，因此内部 `CityResolution` 与 `RouteCalculationRequest` 保留并传递高德 3–4 位 citycode；F-001 单城市编排显式把同一已解析 citycode 传给两端，不猜测、不增加隐藏反向地理编码调用；
- 只接受一个与请求起终点完全一致的路线选项；距离严格解析为非负整数米，`cost.duration` 严格解析为正整数字符串秒，并用纯整数向上取整为分钟；不采信 transit fee 或其他未进入领域契约的附加费用；
- walking/transit 响应各生成带同一 `source_id` 的 `RouteLeg` 与 `SourceRecord`，有效期保持未知并警告；无路线 `20800`–`20803` 映射为空结果，HTTP/业务错误继续使用安全分类且不保留上游 body、Key 或异常；
- 37 项离线 mock transport 测试覆盖精确请求、两种模式、秒到分钟边界、超长数字、坏 Schema、空路线、无路线 infocode、非法端口请求、HTTP 和 timeout；相关回归 116 项通过；统一门禁中的后端全量 577 项 pytest、前端 61 项 Vitest、文档检查器 21 项测试、Ruff format/check、strict mypy、Vite build 和 17 份必需文档契约均为绿色；
- 环境加载和生产装配仍留给 Step 32。未读取真实 Key、未调用高德、未提交或推送；
- 完成后停止，等待用户批准 Step 31。

### Step 31：和风预报和当前预警 adapter

- 新增未装配的 `QWeatherAdapter`，只实现 `QWeatherPort` 的逐日预报和当前预警；固定账户专属 `*.qweatherapi.com` Host、6 秒 timeout、禁止 redirect 与环境代理，每个端口调用只执行一次 HTTP 尝试；
- 依据当前官方 API 使用 `/weather/v1/daily/{latitude}/{longitude}` 和 `/weatheralert/v1/current/{latitude}/{longitude}`，坐标按中国大陆 GCJ-02/provider-native 语义接收并以 Decimal 四舍五入到两位；预报固定请求 7 天、本地时间和中文，只输出请求中的连续两日；
- JWT Header 只包含 `alg=EdDSA` 与凭据 ID，Payload 只包含项目 ID、`iat` 和 `exp`；使用 Ed25519 PKCS8 私钥签名、30 秒时钟偏移与 15 分钟寿命，并只通过 Bearer Header 发送，不实现 API Key 兼容；
- 预报严格校验日期、时区、摄氏温度单位/范围、白天与夜间条件；缺日或部分坏记录保留可用数据并返回 partial，绝不补造天气；当前预警的 `zeroResult=true` 是成功空快照，坏/重复/已过期记录不作为当前预警，非空结果的 `valid_until` 取最早 `expireTime`；
- HTTP 400/404/405、401/403、429、5xx 与未知状态映射为项目安全错误，超时、坏 JSON、超大响应和配置错误不保留 Bearer、私钥、上游 body 或异常；
- 新增直接依赖 cryptography `46.0.7`（范围 `<47`）并更新 uv 锁；51 项离线 mock transport/JWT 测试、相关回归 102 项通过；统一门禁中的后端全量 628 项 pytest、前端 61 项 Vitest、文档检查器 21 项测试、Ruff format/check、strict mypy、Vite build 和 17 份必需文档契约均为绿色；
- 环境读取、私钥路径加载、`.env.example` JWT 字段、启动检查和生产装配仍属于 Step 32；当前 `QWEATHER_API_KEY` 占位不是可用配置契约。未读取真实私钥、未访问和风天气、未提交或推送；
- 完成后停止，等待用户批准 Step 32。

### Step 32：配置加载、凭证隔离、脱敏和启动检查

- 扩展冻结 `Settings`：只自动读取项目根 `.env.local` 和进程环境，DeepSeek 模型/Base URL 保持 Literal，Key 使用 `SecretStr`，和风账号字段与私钥路径不进入 `repr`；
- 新增本地组合根，DeepSeek、高德和和风配置组全空时分别报告 `disabled` 且健康服务照常启动；只有完整且通过 adapter 本地校验的组才构造为 `ready`，整个过程不访问网络；
- 和风配置原子包含账户专属 Host、项目 ID、凭据 ID和绝对 Ed25519 私钥路径；部分配置、相对/缺失/非法/超限私钥均以稳定错误码拒绝启动，错误不保留 Key、PEM、路径或底层异常；
- `.env.example` 和默认 CI 改为当前 JWT 字段并全部保持空值，废弃 `QWEATHER_API_KEY`；文档检查器新增模板完整性、空路径和废弃字段负向契约；
- 17 项配置/启动专项测试、24 项配置与健康相关测试、23 项文档检查器测试、Ruff format/check 和 strict mypy 通过；统一门禁中的后端全量 645 项 pytest、前端 61 项 Vitest、Vite build 和 17 份必需文档契约均为绿色；
- 未读取或保存真实凭证，未调用外部 API，未把任务 POST 接到规划执行器，未提交或推送；`ready` 只表示本地可构造，不证明鉴权或 live 可用。
- 完成后停止，等待用户批准 Step 33。

### Step 33：完整 provider 失败注入矩阵

- 新增三家真实 adapter 的统一离线传输矩阵：DeepSeek 生成、高德城市解析、和风双日预报分别注入成功、空数据、401、403、429、timeout、503、Schema 漂移和连接失败；
- 27 项参数化 transport case 全部使用进程内 httpx2 MockTransport，证明每个调用只有一次 HTTP 尝试，并统一裁决 provider、三态、安全错误码、retryable、空来源和敏感详情不进入结果；
- 在离线编排器以七个 `ProviderErrorCategory` 穷举城市、POI、DeepSeek 三个关键边界和天气、预警、路线三个非关键边界，共 42 项注入 case；关键失败稳定 `failed` 并精确短路，非关键失败保留候选与确定性校验并稳定 `partial`；
- 专项 89 项测试通过，其中包含 69 项新矩阵 case 和 20 项原编排回归；原有 stale/unknown-validity、适配器 infocode/HTTP 细分、状态机和调用治理测试继续覆盖时效与重试上限；
- 首轮矩阵因误把内部 `user/system` 来源当作外部 provider、且对 DeepSeek 安全复制结果使用身份断言而 RED；只修正测试矩阵边界和相等性语义，未发现或修改生产实现；
- 统一门禁通过：后端 714 项 pytest、前端 61 项 Vitest、文档检查器 23 项测试、Ruff format/check、strict mypy、Vite build 和 17 份必需文档契约全部绿色；未读取真实凭证、未访问 provider、未提交或推送。
- 完成后停止，等待用户批准 Step 34。

### Step 34：Agent 结构化输出和确定性评估

- 在既有严格解析测试上新增 10 类命名 scorecard：精确合法 JSON、畸形 JSON、Markdown 包裹、重复键、越权终态字段、候选集外 POI、虚构来源、日期越界、提示控制文本和超长输出；
- 合法 case 连续解析 10 次得到完全相同的冻结 typed candidate；九个非法 case 全部得到精确、无原文的本地错误码，其中提示控制标记明确不可修复，其余仅允许进入既有单次修复边界；
- 新增上下文目录顺序不变性评估：兴趣、工具白名单、地点和 observation 顺序变化不改变同一合法候选的解析结果；
- 对 ready、partial、conflict、failed 四个代表场景各执行 10 次相同输入，40 次运行的终态、状态历史、候选、路线补全和最终确定性校验结果逐项一致；
- 连同既有合法首轮、一次修复、二次失败、provider unavailable、剩余时限、提示控制、路线/预算/来源裁决测试，专项相关 107 项全部通过；新增 15 项评估 case；
- 统一门禁通过：后端 729 项 pytest、前端 61 项 Vitest、文档检查器 23 项测试、Ruff format/check、strict mypy、Vite build 和 17 份必需文档契约全部绿色；未修改生产代码，未调用模型/provider，未读取凭证、提交或推送。
- 完成后停止，等待用户批准 Step 35。

### Step 35：离线前后端浏览器闭环

- 新增窄 `PlanningJobExecutor` 应用端口；HTTP 层只在新建 job 或已批准 retry 后通过 FastAPI background task 调度该端口，幂等重复 POST 不重复调度，路由不依赖编排器、provider 或 fake；
- 新增只供离线验收的 `SyntheticPlanningJobExecutor` 和浏览器支持组合根；五个冻结结果均经真实状态机路径、进程内 Repository 和 `record_result` 发布，浏览器不再拦截任务响应；默认应用不装配该 fake，也没有调用真实 provider；
- 首轮浏览器发现轮询可能错过合法中间状态；修正前端从“必须观察每条直接边”改为只接受状态图中可达的后继，仍拒绝回退与不可达分支，并新增采样跳跃和反向状态回归测试；
- Playwright Chromium 通过真实本机 POST/GET 验证 ready、partial、conflict、needs_input、failed；partial 通过真实 retry 到 attempt 2，needs_input 返回后焦点定位住宿字段；ready 显示双日天气、四段路线、预算、unknown 和来源；
- 桌面与 `390×844` 均通过，窄屏 `scrollWidth=375`、结果优先且输入折叠；浏览器控制台 0 error/0 warning，动态业务请求全部指向 `127.0.0.1:5173/api` 并由 Vite 代理到 `127.0.0.1:8000`；
- 专项后端 20 项、前端 62 项及 Ruff/strict mypy/Prettier/ESLint/typecheck 通过；本步启动的浏览器、前端 PID `13652` 和五个最终场景后端 PID `43336/43476/40608/14824/16992` 已精确停止。未执行真实 API、提交或推送；
- 完成后停止，等待用户批准 Step 36。

### Step 36：全量本地门禁

- 在项目根目录运行 `powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify.ps1`，统一门禁一次通过；
- 运行时版本精确为 Python 3.13.3、Node.js 22.16.0 和 pnpm 11.19.0，后端与前端锁文件、依赖同步和 peer dependency 检查通过；
- 后端 Ruff format/check、strict mypy 全部通过，pytest 共 737 项通过；前端 Prettier、CI workflow 格式、ESLint、TypeScript、62 项 Vitest 和 Vite build 全部通过；
- 文档检查器 23 项测试通过，17 份必需文档、19 个 Markdown 文件及 CI、状态和安全契约有效；全程未调用真实 provider、未读取凭证、未提交或推送；
- 完成后停止，等待用户批准 Step 37。

### Step 37：外部账户、配额、条款和费用上限审计

- 只读检查确认项目根目录只有无秘密的 `.env.example`，不存在 `.env.local`；DeepSeek Key、高德 Web Service Key、和风 API Host/项目 ID/凭据 ID/Ed25519 私钥路径全部未配置；未登录、注册、创建凭据或调用业务 API；
- DeepSeek 官方当前确认 `deepseek-v4-flash`、人民币计价；2026-08-14 现行价为百万 token 缓存未命中输入 1 元/输出 2 元，但官方已公告 2026-08-17 起改为峰谷价：高峰输入 3 元/输出 9 元，空闲输入 1.5 元/输出 4.5 元。按每次最多 1M 输入、8000 输出和最多 3 次做保守上界，新价下模型费用约为高峰 9.216 元、空闲 4.608 元；账户余额、Key、模型权限和已接受条款仍未验证；
- 高德个人认证开发者当前基础 LBS 月配额 150,000 次、基础搜索月配额 5,000 次，超额基准价均为 30 元/万次；按项目最多 16 次 HTTP 尝试，调用增量费用保守上界约 0.048 元。个人免费许可文本限定个人研究学习，且对缓存、截图、衍生展示和脱离服务单独展示有限制，当前实际生活旅行工具的许可适配需要账户侧确认并建议提交官方工单；
- 和风天气当前天气/预警等前 50,000 次/月为 0 元，随后 0.0007 元/次，最低账单金额 0.01 元；项目最多 4 次 HTTP 尝试。账户、项目、JWT 凭据、专属 Host、当月用量和信用状态均未验证；
- 2026-08-14 现行价下三家调用费保守合计约不超过 3.106 元；2026-08-17 新价生效后，同一硬调用预算的高峰保守上界约 9.274 元、空闲约 4.666 元。原 5 元上限不再天然成立且没有 provider 侧硬消费锁；用户随后批准将一次受控 smoke 的总费用上限调整为 12 元，调用次数不变，执行前仍须重新核价；
- 发现两个代码/产品合规缺口：和风 adapter 未保留并原样展示响应中的 `metadata.attributions`，产品页也没有固定的“天气服务由和风天气驱动”链接；DeepSeek 生成结果没有明确的 AI 生成披露。另有高德真实数据截图、临时存储和组合展示的许可解释风险；
- 只读审计时默认应用仍未装配真实规划执行器，因此即使配置凭证也不能完成产品级 live smoke；
- 只读审计结论为 `BLOCKED/NOT READY`。用户随后批准代码补充收口，但账户、配额与高德许可等外部条件仍须完成，因此不进入 Step 38。

#### Step 37 补充收口（用户批准）

- 和风 adapter 现在要求响应包含安全、非空的 `metadata.attributions`，原样写入领域与公开 `SourceRecord`；缺失、空、超长、错误类型或控制字符归因统一按 Schema 失败，UI 同时固定展示“天气服务由和风天气驱动”及官方链接；
- 结果包含 DeepSeek 来源时，UI 明确披露“本计划包含 DeepSeek AI 生成内容”，并保留确定性校验与仍可能不准确的提示；没有对应来源时不虚假展示归因或 AI 披露；
- 新增真实 provider 任务执行器与组合根：三家 adapter 全部存在才启用；住宿文本先经受控高德 POI 查询解析为锚点，再执行景点、天气、候选、路线、预算、终态与 Repository 发布。任一配置缺失时执行器为 `None`，启动和 CI 不访问 provider；
- 全部验证使用 fake 或 httpx2 MockTransport；统一门禁通过后端 744 项 pytest、前端 63 项 Vitest、文档检查器 23 项测试及全部格式、lint、strict mypy、TypeScript 和构建；未读取凭证、未调用真实 API；
- 用户已自行创建三家账户与凭证；被 Git 忽略的 `.env.local` 经无网络启动检查确认三家 adapter 和真实执行器均为 `ready`，不记录任何秘密值。和风账单余额和应计费用均为 0，首次 smoke 位于当前零元计价区间；
- 用户根据高德工程师电话沟通明确确认六项使用边界：个人、非商业、本地自用；允许查询并组合展示地理编码、POI、步行/公交路线与天气/AI 说明；固定标注“数据来源：高德地图”；不保存原始响应或持久缓存；转换结果只存在进程内且重启即失；不公开部署或传播真实数据截图，无需企业技术服务许可；
- 前端在存在高德来源时固定展示“地理位置、POI 和路线数据来源：高德地图”及官方链接，并以正反测试防止缺失或无来源时误展示；Step 37 完成，停止并等待用户单独批准 Step 38。

### Step 38：一次受控真实 API 冒烟

- 2026-08-14 执行前无网络检查确认三家 adapter 与真实执行器均为 `ready`，测试城市固定为杭州，未输出凭证、请求正文、上游响应或真实地点明细；
- 只创建一个双日规划任务。任务在首轮进入 `conflict`，同时保留结构化计划；公开来源按 provider 脱敏计数为高德 3、和风 2、DeepSeek 1、system 1、user 1，无 provider 错误码；
- 冲突由确定性校验报告 1 项日程冲突和 2 项路线冲突，不是鉴权、配额、计费、Schema 或许可异常。由于候选日程先失效，编排器按设计跳过了该候选的路线补全；
- 为验证被跳过的 live 路线端点，只在同一授权和高德预算内增加 1 次固定杭州测试坐标的公交路线窄探针。结果为 `ok`、有数据、距离和时长均为正、无错误分类；未再次调用 DeepSeek、和风或创建第二个计划；
- 全程未保存 provider 原始响应、未建立持久缓存、未创建或保存真实高德数据截图；任务与转换结果只在本次进程内存在，输出和记录仅保留脱敏状态及计数；
- Step 38 的 live 服务契约验证结论为 `PASS`，但该次具体计划的产品终态为 `conflict`，不能作为 ready 旅行计划或 Step 39 UAT 通过证据。

### Step 39：真实数据桌面和窄屏 UAT

- 用户明确批准新的 provider 调用，并沿用一次杭州双日计划、DeepSeek 最多 3 次、高德最多 16 次、和风最多 4 次、总费用不超过 12 元的硬边界；
- 现有 React UI 在桌面 `1440×900` 只提交一次本机任务 API。高德与和风各产生可公开来源，DeepSeek 响应未通过严格 Schema，任务以 `provider_schema_invalid`、`retryable=false` 进入 `failed`；未出现鉴权、配额、计费或许可异常；
- Schema 异常触发用户指定停止条件：没有点击 retry、没有第二次提交、没有额外 provider 调用。后端、前端和浏览器随后按精确 PID 关闭，`8000/5173` 均不再监听；
- 失败态桌面和 `390×844` 均无水平溢出，来源与时效、高德/和风归因和安全失败文案可见；无 DeepSeek 来源时不误展示 AI 生成披露，不显示 retry 动作，控制台 0 error/0 warning，DOM 未发现密钥、私钥或 Bearer 标记；
- 视口切换前后本机任务 API 资源计数保持不变，证明窄屏检查没有再次提交。Playwright 自动生成的本次临时 YAML/控制台文件已精确移除，未保存截图、上游响应、真实地点或路线明细；
- UAT 同时观察到页脚仍显示过期的 `F-001 · STEP 35`。它不影响安全失败，但属于待修复的状态文案漂移；
- Step 39 执行动作已完成，UAT 结论为 `FAIL`：系统安全失败路径有效，但没有 ready/partial 真实计划，不能满足真实数据 UAT 或 F-001 完成定义。

### Step 40：独立 QA、测试审查和预 PR review

- 审查对象为工作区相对 `main` 的完整变更及全部未跟踪文件；当前 HEAD 仍为 `50980887dadc0500d98dcd29966a5da2da74b2e2`，无 F-001 提交、推送或 PR；
- 已证实本地候选二次校验失败会被发布为 `provider_schema_invalid`，adapter 多种 envelope/HTTP 异常也使用同一码；现有安全信息不足以区分 Step 39 是 adapter 拒绝、输出截断还是 repair 后仍失败，未推测或恢复原始响应；
- 已证实默认测试应用会固定加载项目 `.env.local`，在本地凭证存在时可能装配真实执行器；因此没有直接运行默认统一入口。通过进程内禁用 dotenv source 的护栏运行全量后端 744 项测试，并独立运行前端 63 项、Ruff、mypy、Prettier、ESLint、TypeScript、Vite build、文档检查器 23 项和文档契约，结果均通过；
- 另确认 DeepSeek 上下文未携带两日时间窗口、自由文本和真实天气/预警内容，repair 请求未携带其声明的候选 Schema；时间窗口重复 offset 未在 provider 调用前拒绝，天气 location ID 与查询坐标语义不一致，DeepSeek timeout 与 governor 边界存在错误覆盖风险；
- 工作区共有 119 个修改/未跟踪文件，粗略净新增约 2.44 万行，已越过任务卡“约 70 文件或 5000 行净新增”的停止阈值；该偏差必须在 Step 41 明确拆分或由用户重新批准范围；
- UI failed/桌面/窄屏的 Step 39 证据仍有效，但前端缺少 `provider_schema_invalid + retryable=false + 保留高德/和风来源 + 无 DeepSeek 披露` 的离线回归，页脚仍显示过期 `F-001 · STEP 35`；
- Step 40 结论：独立审查已完成，F-001 不具备提交、PR 或再次 live UAT 条件；可以在用户批准后进入 Step 41 修复，但任何 live 回归仍需新的单独授权和费用边界。按本 Step 的四文档写入限制完成同步后，文档检查器仅因 `docs/README.md` 仍声明等待 Step 40 而失败；该状态地图不在本 Step 允许写入范围，须在后续文档修复中同步。

### Step 41：修复阻塞问题并重复门禁

- 测试组合在导入应用前固定 `APP_ENV=test`，不读取项目 `.env.local`，并以自动 fixture 拒绝全部非 loopback socket；默认 API 测试即使本机存在真实凭证也只装配禁用 provider 的测试应用；
- DeepSeek adapter 为安全 envelope 失败保留项目自有原因枚举，任务错误可选发布不含原文和值的 `diagnostic_code`；本地候选首次/repair 后仍无效稳定发布 `model_output_invalid`，不再冒充 provider Schema；
- generation 与 repair 共享冻结候选 Schema；上下文补齐两日时间窗、自由偏好、交通方式、住宿锚点、逐日天气/当前预警和仅允许活动引用的 POI 来源；`finish_reason=length` 只能进入既有单次 repair；
- 输入契约在创建任务前拒绝逆序/零长度时间窗和重复 day offset；候选必须按起止日期顺序输出，活动不能引用天气来源；默认天气锚点 ID 与住宿坐标保持一致，provider timeout 不再被 governor 的返回后 deadline 覆盖；
- 前端页脚改为不随 Step 过期的任务名称，并新增不可重试 `provider_schema_invalid`、安全诊断、保留既有来源和无 DeepSeek 来源不披露 AI 的回归；
- 冻结 Python 3.13.3、Node.js 22.16.0、pnpm 11.19.0 下统一 `scripts/verify.ps1` 一次通过：后端 756 项 pytest、前端 64 项 Vitest、文档检查器 23 项，以及锁、依赖、Ruff、strict mypy、Prettier、ESLint、TypeScript、Vite build 和文档契约全部绿色；未读取本地凭证、未调用真实 API、未提交或推送。Step 41 后工作区共 120 个变更文件，超过约 70 文件/5000 行停止阈值；用户随后批准作为一个完整垂直切片 PR 交付并接受本次范围例外。

### Step 42：更新 evidence、progress、架构和决策文档

- `DONE`；已同步 Step 41 验证事实、长期架构/Agent/API/测试契约、roadmap、状态和 evidence，未执行 live API、暂存、提交、推送或 PR；
- 用户明确批准 F-001 以单一完整垂直切片 PR 交付，并接受当前 120 个变更文件的任务级范围例外；该决定已记录为 D-008，不扩大产品范围或降低 review、CI、安全门禁；
- 文档专项门禁和 `git diff --check` 通过后，下一步为待用户单独批准的 Step 43 精确暂存与本地提交。

### Step 43：精确暂存并创建本地提交

- `DONE`；提交前统一 `scripts/verify.ps1` 在 Python 3.13.3、Node.js 22.16.0、pnpm 11.19.0 下一次通过，包含后端 756 项 pytest、前端 64 项 Vitest、文档检查器 23 项和全部静态、构建、文档契约门禁；
- 工作区 120 个变更文件与用户批准的完整 F-001 垂直切片范围一致；精确暂存后复核 staged 文件数、diff、`.env.local` 忽略和敏感文件边界；
- 创建一个本地提交，未调用真实 API、未推送、未创建 PR；下一步为待单独批准的 Step 44。

### Step 44：推送并创建 Draft PR

- `DONE`；将 `feat/f-001-single-city-two-day-plan` 推送至 `origin` 并设置 upstream，基线为 `main`；
- 创建 Draft PR #4：`feat: deliver single-city two-day travel planning slice`，PR 正文包含完整切片范围、统一门禁、120 文件例外、Step 39 真实 UAT `FAIL` 和 live 回归需重新授权的边界；
- GitHub Actions 已触发 Windows offline verification；本 Step 不等待或处置结果，Step 45 仍需用户单独批准；
- 未调用真实 API、未把 PR 标记 ready、未合并。

### Step 45：等待远程 CI 并修复阻塞问题

- `DONE`；Draft PR #4 的 Windows offline verification 运行 `31807998195` 在 4 分 45 秒内通过，setup、统一验证和 teardown 全部成功；
- 没有失败检查、外部检查或需修复的 CI finding，因此未修改业务代码；
- 状态文档提交推送后，同一 Windows 离线门禁已对最终 PR head 复验通过；
- PR 继续保持 Draft，Step 39 真实 UAT `FAIL` 与单独授权 live 回归边界不变；下一步为待单独批准的 Step 46。

### 补充 Step 45A：修复后的受控真实数据 UAT 回归

- `DONE / FAIL`；执行前确认功能分支与 Draft PR #4 head 一致、工作区干净、最终 Windows offline verification 成功，三家 provider 和真实执行器均为 `ready`，本地配置保持 Git 忽略且和风私钥位于仓库外；
- 费用预检的保守上界低于 3.10 元；DeepSeek 余额检查只输出可用状态并计入 3 次 HTTP 上限。唯一任务保留高德 3 条、和风 2 条公开来源后，以 `model_output_invalid`、`candidate_local_validation_failed`、`retryable=false` 终止；公开结果不暴露 generation/repair 的分别计数，因此证据只声明 DeepSeek 总 HTTP 未超过 3，不虚构精确调用明细；
- 触发停止条件后未重试、未再次提交、未进行路线补全或额外 provider 调用。桌面和 `390×844` 失败终态均无水平溢出，无重试入口且返回修改入口可用；高德/和风归因与来源时效可见；
- 未保存截图、provider 原始响应、持久缓存、真实地点、路线坐标或完整用户请求；DOM 与临时日志脱敏扫描通过，临时日志和本地服务已清理；
- F-001 保持 `PARTIAL`，Step 46 不可批准合并。下一步应先另行批准一个纯离线最小修复 Step：为候选首次校验和 repair 后校验记录不含字段值的阶段/验证码，补齐纵向测试，再基于证据决定是否申请新的单次 live 回归。

### 补充 Step 45B：离线定位并修复 DeepSeek 候选本地校验可靠性

- `DONE`；未读取 `.env.local`、私钥或 Step 45A 模型原文，三家 provider 配置显式为空，测试自动拒绝非 loopback socket；
- 红测证明 resolver 丢失 generation/repair 阶段与候选验证码、API 只发布通用诊断，且 generation/repair Prompt 未完整表达本地候选规则；
- 最小修复沿 resolver → outcome → executor → API 传递阶段与八类项目自有枚举，公开错误保持 `model_output_invalid`、`retryable=false`；generation 与 repair 复用同一冻结候选规则，不放宽日期、时间、POI/来源引用或安全文本校验；
- MockTransport 纵向回归串联真实 DeepSeek adapter、resolver、executor、Repository 和 FastAPI GET，覆盖首次失败、repair 成功、repair 再失败、截断、非法引用、最多一次 repair 和原文不泄漏；
- 专项 78 项、相关纵向/失败回归 120 项通过；统一 `scripts/verify.ps1` 在 Python 3.13.3、Node.js 22.16.0、pnpm 11.19.0 下通过，包含后端 766 项、前端 64 项、文档检查器 23 项及全部静态、类型、构建和文档契约门禁。F-001 仍为 `PARTIAL`，因为没有新的 live ready/partial 证据。Step 46 继续阻塞；任何受控 live 回归仍需单独授权调用与费用边界。

### 补充 Step 45C：Step 45B 后受控真实数据 UAT 回归

- `DONE / FAIL`；执行前确认功能分支、HEAD、Draft PR #4、19 个预期工作区变更、空暂存区、`.env.local` 忽略、仓库外私钥、三家 provider/真实执行器 `ready`、有效天气日期和 12 元费用边界；DeepSeek 余额可用性检查计入总 HTTP 上限；
- 只通过现有 Web UI 创建一个杭州双日任务，没有 retry 或第二次提交。模型候选成功通过本地严格校验，公开结果包含完整双日结构、高德/和风/DeepSeek 来源和 AI 披露；最终确定性校验产生 2 项 `route_conflict`，路线数据未形成可验证路线段，终态为 `conflict`；
- 预算保留住宿、城际交通和门票 3 项 unknown，已知餐饮 400 元，预算为 indeterminate；公开来源计数为 user 1、system 1、高德 3、和风 2、DeepSeek 1；
- 桌面 `1280×800` 的 `scrollWidth=1265`，窄屏 `390×844` 的 `scrollWidth=375`；只有 1 次 POST 和同任务 3 次 GET，视口切换未增加请求，控制台 0 error/0 warning，DOM 与 1070 字节临时日志未发现秘密或原始响应标记；
- 没有保存截图、provider 原始响应、持久缓存、完整请求或路线坐标；本次工具生成的精确临时快照/日志已移除，浏览器和本地服务已关闭；
- Step 45C 未满足 ready/partial 通过标准，F-001 保持 `PARTIAL`，Step 46 继续阻塞。下一步应先单独批准纯离线路线冲突证据审查，不得再次 live 调用或放宽确定性校验。

### 补充 Step 45D：离线修复候选时间安排与路线连续性不一致

- `DONE`；显式使用测试环境空 provider 配置，默认测试组合禁用 `.env.local` 并拒绝非 loopback 网络，没有读取凭证或调用真实 API；
- 红测证明旧 parser 会接受首项贴合窗口起点、末项贴合窗口终点和不同地点活动零间隔；纵向编排稳定复现候选不进入 repair、两天路线补全均被跳过并最终形成 `route_conflict`；
- 根因是冻结候选规则只要求单项 `end_time > start_time`，没有在候选进入路线补全前复用 `DailyRoutePlan` 的住宿往返及不同地点正数交通窗口不变量；
- 最小修复在候选准入层复用 `DailyRoutePlan.expected_legs()`，时间不可行沿现有 `candidate_time_invalid` 进入唯一一次 repair；generation 与 repair Prompt 使用同一条正数交通窗口规则；
- 回归覆盖窗口首尾边界、跨地点零间隔、同地点连续活动、repair 成功/再失败、正常双日路线链和真实路线时长超过间隔的硬冲突。最终路线裁决未放宽；
- 专项 162 项通过；统一 `scripts/verify.ps1` 在 Python 3.13.3、Node.js 22.16.0、pnpm 11.19.0 下完整通过，包含后端 772 项、前端 64 项、文档检查器 23 项，以及锁文件、格式、lint、strict mypy、TypeScript、Vite build 和文档契约；
- 本 Step 不产生 live UAT 通过证据、不暂存、不提交、不推送、不修改 Draft PR。下一动作必须由用户单独批准最后一次受控 live 回归，Step 46 继续阻塞。

### 补充 Step 45E：Step 45D 后最后一次受控真实数据 UAT

- `DONE / FAIL`；执行前确认功能分支和 HEAD、21 个既定工作区文件、空暂存区、Draft PR #4 与远程 CI、`.env.local` 忽略、仓库外私钥、三家 provider/真实执行器 `ready`、有效天气日期和 12 元费用边界；没有执行独立 provider 探针；
- 只通过现有 Web UI 创建一个杭州双日任务，没有 retry、第二次提交或重复生成。generation 候选未通过时间可行性检查，唯一一次 repair 后仍失败，最终为 `failed`、attempt 1、`retryable=false`、无计划，公开错误为 `model_output_invalid`，安全诊断为 `candidate_repair_time_invalid`；
- 公开来源脱敏计数为 user 1、system 1、高德 3、和风 2；任务没有进入路线补全，因此本次不能验证真实路线时长落入交通窗口，也没有 DeepSeek 计划来源；
- 桌面 `1280×800` 的 `scrollWidth=1265`，窄屏 `390×844` 的 `scrollWidth=375`，均无水平溢出；页面无 retry 控件、有返回修改入口，高德/和风归因和时效可见，控制台 0 error/0 warning；
- 只有 1 次 POST 和同任务 4 次 UI GET；为提取项目自有安全诊断另执行 3 次同任务只读 GET，不触发 provider。DOM、浏览器临时文件和空运行日志未发现凭证或原始响应标记；未保存截图、provider 原始响应、持久缓存、地点、坐标、路线明细或完整请求，精确临时文件已移除且本地服务已停止；
- 本 Step 未修改生产代码或测试，真实 UAT 仍为 `FAIL`，F-001 保持 `PARTIAL`。最后一次 live 授权已经消耗，Step 46 继续阻塞。

### 补充 Step 45F：离线细化候选时间诊断并确定时间规划责任边界

- `DONE`；只使用 synthetic、fake 和 `httpx2.MockTransport`，测试组合设置 `APP_ENV=test`、禁用 dotenv、保持三家 provider 配置为空并拒绝非 loopback 网络；未读取 `.env.local`、私钥或 Step 45E 模型原文，未调用真实 API；
- 红测分别复现活动越出日窗口、住宿到首项无正数间隔、不同地点活动无正数间隔、末项返回住宿无正数间隔和日程容量不足。根因是候选层捕获 `DailyRoutePlan` 的稳定不变量后统一压缩为 `candidate_time_invalid`，且 repair 只收到通用验证码；
- resolver → outcome → executor → API 现只额外传递上述五类项目自有无值枚举；DeepSeek repair 只接收类别及项目静态规则提示，不接收诊断字段值、时间、地点、坐标或上游详情。公开错误保持 `model_output_invalid`、`retryable=false`，最多一次 repair；
- generation/repair 原有 Prompt、PlanningContext、冻结 Schema 和候选规则已经完整传递两日窗口、住宿锚点和正数交通窗口，未发现其他可证实遗漏。日期、时间、路线连续性、实际路线时长和最终确定性校验没有放宽；
- 专项 165 项与后端全量 786 项通过；统一门禁包含前端 64 项、文档检查器 23 项及全部格式、lint、strict mypy、TypeScript、Vite build 和文档契约；
- 三次真实 UAT 仍未证明 LLM 独立生成精确时刻可靠。已记录待用户批准的 D-009：由确定性代码生成时间骨架和排程，LLM 只负责 POI 选择、顺序建议与解释。本 Step 未改变候选 DTO 核心语义或实施调度重写；在用户决定前不再纯 Prompt 调优或执行 live，Step 46 继续阻塞。

### 补充 Step 45G / F-001-CR1：确定性时间排程责任调整的变更控制与详细设计

- `DONE / DESIGN ONLY`；用户正式批准 D-009 的职责方向，本 Step 只读审查现有 candidate、路线补全、状态机、final validation、API、Repository 和测试，并起草 [F-001-CR1 变更卡](./f-001-cr1-deterministic-scheduling.md)；
- 推荐新增不含最终精确时间的 `PlanProposal`/`ActivitySelection`，由 DeepSeek 提议 POI、顺序、优先级、required/optional、时长类别和解释；高德按代码推导端点返回实际路线；纯确定性 scheduler 再形成现有带时间 `PlanCandidate`；
- 推荐公开 API、Repository 和 UI 主体不变，复用现有五种终态及 warnings/uncertainties/violations；状态 enum 不增加，unknown 时长需要新增 `planning → needs_input` 边；
- F-001 每日最多 2 项，完整双日路线最多 6 段，并为每天一次 optional 移除后的桥接路线保留 2 段，总计不超过现有 8 段路线预算；
- 复审确认 `activity_visit_order_invalid → day_schedule_capacity_exceeded` 语义不等价；目标诊断必须区分活动序列/重叠与真正的确定性容量不足；
- 使用基于功能分支的 stacked PR 隔离 Step 45H，最终仍由 PR #4 面向 main 交付；用户已批准 24–34 文件、1200–2200 行的新范围例外，D-008 的 120 文件例外不自动覆盖其他新增范围；
- 本 Step 未修改生产代码、测试、DTO、Prompt 或 UI，未调用 provider、暂存、提交、推送或修改 PR。九项实施决策均已确认；Step 45H 实现、Step 46 和新的 live UAT仍未授权。

### 补充 Step 45H：实施并离线验证 F-001-CR1

- `TODO / AWAITING_STEP_APPROVAL`；每日活动上限、时长映射、交通缓冲、optional 自动移除、required/unknown 终态、路线 unavailable 终态、stacked PR 和新增范围均已批准，生产实现仍需单独批准；
- 实施顺序为 proposal 红测与 DTO/Schema、时长策略、无时间路线链、纯 scheduler、overflow/unknown、orchestrator/state、final validation/executor/API 纵向回归、Agent eval 和统一离线门禁；
- 预计影响 24–34 个文件、1200–2200 行，前端生产代码预计不变；超过上界、需要公开 API/UI、提高 provider 预算或复杂求解器时立即停止；
- 本 Step 不含真实 API、live UAT、提交、推送、PR 写入、ready-for-review 或合并；这些动作仍分别等待后续授权。

## 后续 Step 摘要

```text
Step 3–4   契约与验收样例
Step 5–10  领域模型、校验与 provider 结果
Step 11–20 端口、fake、状态机、离线编排与 API
Step 21–27 UI 设计审批与实现
Step 28–32 三个真实 adapter 的实现与安全配置
Step 33–36 失败矩阵、Agent 评估、浏览器闭环与全量门禁
Step 37–39 外部就绪、单独授权 live smoke 与真实 UAT
Step 40–47 独立 QA、修复、证据、提交、PR、合并与归档
```

首次外部服务调用已在 Step 38 的明确授权和预算内完成。任何后续 live 调用仍需单独批准；提交、推送、PR 和合并分别等待对应 Step 授权。
