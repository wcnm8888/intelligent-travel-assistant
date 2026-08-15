# 测试与质量策略

## 目的

本文件定义 Intelligent Travel Assistant 当前有效的测试分层、风险矩阵、外部服务隔离、Agent 评估、质量门禁和证据规则。测试从产品风险和验收标准推导，不以覆盖率数字或实现细节代替行为验证。

B-000 已建立后端健康服务测试、前端健康诊断测试、本地 Chromium 闭环、统一门禁、Windows CI、独立负向测试、范围/凭证审查和用户 UAT，并已完成 review、合并和归档。F-001 已在该基线上实现旅行领域、Agent 编排、provider 适配器、五种业务终态、产品 UI、失败注入和受控 live smoke；synthetic 浏览器闭环、离线门禁和 Step 45T 的完整双日 partial 真实数据 UAT 已通过。真实验收仍须如实保留 partial 边界：unknown 费用不按 0 处理，混合交通 fallback 只有离线证据。

## 核心原则

1. 先定义可观察行为和失败路径，再选择测试层级；
2. 确定性规则必须由确定性测试证明，大模型评估不能替代代码测试；
3. 默认测试和 CI 完全离线，不访问 DeepSeek、高德或和风天气；
4. 测试替身只能证明本地编排和失败处理，不能证明真实 provider 可用；
5. 高风险规则至少执行一次红绿证明，即确认测试能在错误行为下失败；
6. 实现者不能是唯一验收者，关键交付需要独立 QA 和用户 UAT；
7. 每项通过结论必须可复现，并明确未覆盖范围；
8. 不通过关闭 lint、类型检查、测试或降级断言来制造绿色结果；
9. 不在 fixture、日志、截图或 evidence 中保存真实凭证和不必要原始数据。

## 测试分层

| 层级 | 目标 | 主要对象 | 外部网络 | 典型工具 |
| --- | --- | --- | --- | --- |
| L0 静态与文档 | 发现格式、类型、断链、秘密和范围问题 | Markdown、配置、Python、TypeScript | 禁止 | 文档脚本、Ruff、mypy、ESLint、Prettier、TypeScript |
| L1 领域单元 | 证明纯业务规则和边界值 | 日期、时间、路线、金额、费用状态、约束 | 禁止 | pytest |
| L2 应用组件 | 证明用例、状态机、重试和确认流程 | application、Agent orchestration、端口替身 | 禁止 | pytest、受控 fake/spy |
| L3 适配器合约 | 证明 provider 转换、Schema 和错误映射 | DeepSeek、高德、和风天气 adapters | 默认禁止 | 脱敏合约 fixture、HTTP mock transport |
| L4 本地集成 | 证明 API、Repository 和本地组件协作 | FastAPI、SQLite、配置、健康契约 | 禁止 | pytest、FastAPI TestClient、临时 SQLite |
| L5 前端组件 | 证明用户可见状态和恢复操作 | React 组件、API client、表单 | 禁止 | Vitest、React Testing Library |
| L6 本地端到端/UAT | 证明浏览器到本地 API 的真实闭环 | React + FastAPI + 本地配置 | 默认禁止第三方网络 | 浏览器人工或自动化、用户 UAT |
| L7 live smoke | 证明真实 provider 的最小合约仍可用 | 单个真实适配器 | 显式允许 | 独立命令、专用测试凭证 |
| L8 Agent 评估 | 评估非确定性输出质量和越权行为 | 模型、Prompt、工具选择、解释 | 离线回放或显式 live | 固定 case 集、评分器、人工审核 |

测试优先落在最低且足以证明风险的层级。不能只用端到端测试覆盖本可在领域单元测试中稳定证明的规则。

## B-000 工程基线测试矩阵

| 风险或行为 | 最低验证 | 必须证明的失败 | 验收角色 |
| --- | --- | --- | --- |
| 后端健康接口不可用 | FastAPI API 测试 | 路由删除、状态码或字段改变时失败 | 实现者 + 独立 QA |
| 健康响应 Schema 漂移 | 精确 Schema 断言 | 缺字段、多余不允许字段或错误状态值时失败 | 独立 QA |
| 缺少第三方 Key 阻断健康检查 | 无 Key 启动与健康测试 | 健康路径误初始化真实 adapter 时失败 | 实现者 + 独立 QA |
| 前端后端连接状态缺失 | 组件测试 | 移除 `loading`、`success`、`error` 或 `retry` 时失败 | 实现者 + 独立 QA |
| 后端不可用无法恢复 | 组件测试 + 本地 UAT | 首次失败后重试不能转为成功时失败 | 独立 QA + 用户 |
| Python 规范或类型漂移 | Ruff + mypy | 引入明确 lint/类型错误时门禁失败 | CI |
| TypeScript 规范或类型漂移 | ESLint + Prettier + typecheck | 引入格式、规则或类型错误时失败 | CI |
| 前端构建失败 | Vite build | 无效导入或构建配置错误时失败 | CI |
| 文档断链或缺失 | 文档检查 | 删除必需文档、制造相对断链时失败 | 独立 QA |
| 本地秘密进入 Git | ignore、敏感模式和 staged diff 检查 | `.env.local` 可暂存或出现疑似真实 Token 时阻塞 | 实现者 + 独立 QA |
| 未批准外部调用 | 离线测试 + 依赖/代码审查 | 默认测试发生网络访问时失败 | 架构审查 |
| 修改目标目录外文件 | Git 路径审查 | 发现 Agent1、Vibe coding 或其他目录变化时阻塞 | 独立 QA |
| 浏览器健康闭环不可用 | 本地 UAT | success/error/retry 任一状态无法操作时阻塞 | 用户 |

B-000 不测试旅行规划、SQLite 业务 Schema、真实 Agent、真实 provider 或实时数据质量，因为这些能力不在 B-000 实现范围。

## 产品风险测试矩阵

| 风险 | 确定性测试 | 集成/组件测试 | Agent 评估或人工验收 |
| --- | --- | --- | --- |
| 日期范围非法或计划越界 | 边界值、性质测试 | API 422/领域错误映射 | 检查解释不淡化硬错误 |
| 活动时长为负、重叠或顺序错误 | 单元测试、随机合法/非法序列 | 状态机进入 conflict | 检查模型修订不扩大范围 |
| 路线段与活动地点不连续 | 路线链规则测试 | 缺路线数据返回不可判定 | 检查不编造路线 |
| 金额精度或负值错误 | Decimal 精度、边界和非法值 | API/Repository 往返 | 用户看到的金额一致 |
| `unknown` 被当作零 | 预算单元测试 | 计划摘要显示预算不完整 | 检查解释不宣称完整低于预算 |
| 来源丢失或错绑 | SourceRecord 关联规则 | adapter 到计划的合约测试 | 抽查解释引用真实来源 |
| 数据过期仍标为最新 | 可注入时钟、有效期边界 | stale/unknown-validity UI 状态 | 用户能看到获取时间与警告 |
| provider 超时、限流或鉴权失败 | adapter 错误映射测试 | partial/unavailable/retry 流程 | 错误文案可理解且不泄密 |
| 模型输出不符合 Schema | 解析和重试预算测试 | 状态机进入可恢复失败 | 统计 Schema 合格率 |
| 模型调用未授权工具 | 工具白名单和状态授权测试 | spy 断言无越权调用 | 对抗 case 检查提示注入 |
| 跨日/跨城修改未确认 | 影响分类和状态转换测试 | awaiting_confirmation 组件流程 | 用户 UAT 取消后原计划不变 |
| 当天修改重写其他日期 | plan diff 范围测试 | 新旧版本集成测试 | 局部性 case 人工审核 |
| 重试失控放大成本 | 调用预算和终止测试 | timeout/rate-limit 故障注入 | 审核调用摘要 |
| provider 文本被当作系统指令 | 数据/指令隔离测试 | 恶意 fixture 合约测试 | Prompt injection 对抗 case |

测试用例应引用产品成功标准、架构错误类别或具体任务验收标准，避免出现无法解释其风险来源的测试。

## 领域与状态机测试

F-001 Step 5 已建立第一批纯领域红绿测试：同一测试命令先因 `intelligent_travel_assistant.domain` 不存在而在收集阶段失败，随后在最小标准库实现加入后转为通过。当前覆盖金额/费用、来源、坐标/地点、路线基础字段、天气温度范围和计划引用完整性；AST 依赖测试阻止框架或基础设施进入 domain。

Step 6 的日期与输入测试同样先因 `TripRequestInput` 不存在而在收集阶段失败，再由最小实现转绿。测试显式注入评估时刻，覆盖上海本地跨日、D+0/D+1/D+5/D+6、非连续日期、跨月/跨年、严格日期类型、人数 0/1/8/9、偏好 5/6 个、200/201 字、空白清理和规范化后重复偏好；固定 synthetic 请求还验证公开契约到领域输入不会产生日期或文本漂移。该证据不覆盖 Step 7–9 的排程、路线链和预算汇总，也不证明 provider 或 API 可用。

Step 7 的时间规则测试先因 `ActivityTimeSlot` 等领域类型不存在而在收集阶段失败，再由最小实现转绿。覆盖 offset 0/1 集合、严格本地时间类型、零/反向时长、窗口边界贴合、窗口外一分钟、错误活动日期、输入正反序与包含式重叠、跨日同钟点不重叠、重复活动 ID、窗口反序匹配和 frozen synthetic 契约映射。校验不会自动排序或修改调用方活动，也不覆盖 Step 8 的路线时长和路线链。

Step 8 的路线测试先因 `DailyRoutePlan` 不存在而在收集阶段失败，再由最小实现转绿。覆盖住宿往返完整链、步行/公交一致性、全部缺失、单段缺失、错端点、反向、乱序、额外段、首段/活动间/返程分钟边界、零交通间隔、同地点免路线、空活动、ready synthetic 全部 verified 和 partial synthetic 全部 missing。`missing` 是结构化不可完整判定结果，不作为路线成功证据；测试不调用 provider，也不自动补路或修改活动。

Step 9 的预算测试先因 `BudgetAssessment` 等领域类型不存在而在收集阶段失败，再由最小实现转绿。覆盖零费用、预算低一分/恰好相等/高一分、空费用集、unknown 不改变已知合计、unknown 不降级超支、已知恰好等于预算但含 unknown、全部类别/可信状态、重复费用 ID、truth-state 负例和低精度 Decimal context。ready、partial、conflict synthetic 的 known total、unknown count 和 assessment 均由领域规则精确重算，不把 fixture 声明值当作计算证据。

Step 10 的 provider result 测试先因 `DataFreshness` 等领域类型不存在而在收集阶段失败，再由最小实现转绿。覆盖 ok/partial/unavailable 合法及非法字段组合、外部 provider 白名单、来源 provider 一致性、timeout/429 类别/5xx 类别与 auth/schema/empty/unknown 的安全码和 retryable、未知有效期警告、valid until 前/恰好等于/超过一微秒、无时区与时间倒置，以及 URL、Authorization、Key/Token、换行和超长警告拒绝。ready、partial、failed synthetic 的来源 freshness 与 timeout/server 错误策略均由领域模型重算；测试不读取系统时钟、不接收原始异常且不访问网络。

Step 11 的应用端口测试先因 `intelligent_travel_assistant.application` 不存在而在收集阶段失败，再由最小实现转绿。测试精确锁定五个工具方法、三个 provider 端口、异步签名、typed request 和 `ProviderResult[payload]` 返回；全部边界 DTO 必须是 frozen/slotted dataclass，DeepSeek 候选不得含终态/provider/retryable。AST 和 annotation 负向检查禁止框架、HTTP/SDK、配置/基础设施、环境读取、裸 dict/Mapping/Any 以及 secret/header/Base URL 参数进入端口层。

Step 12 的 fake adapter 测试先因 `intelligent_travel_assistant.adapters` 不存在而在收集阶段失败，再由最小实现转绿。三个 fake 覆盖六个异步方法，每个方法使用独立有序脚本；调用按适配器全局序号记录冻结 typed request 快照，未配置与耗尽分别稳定失败。配置时拒绝 provider 不匹配、缺少 synthetic 警告或非 `synthetic_` 来源；测试覆盖 ok/partial/unavailable、七类安全错误、生产入口不装配 fake，并用 AST 证明实现不导入网络/环境能力或调用 sleep。该替身只证明离线注入与端口协作，不证明真实 provider 可用。

Step 13 的状态机测试先因 `application.state_machine` 不存在而在收集阶段失败，再由最小实现转绿。测试从唯一冻结的 `ALLOWED_PLANNING_TRANSITIONS` 导出全部允许边，并穷举 11×11 状态组合证明所有非边、自环和无出口终态外跳被稳定拒绝；`partial`/`failed → normalizing` 还必须同时满足显式 retry 触发与 `retryable=true`，普通边拒绝伪造 retry。命令和结果均冻结，状态机无 provider、端口、fake、框架、环境、网络或时钟依赖。当前状态机只裁决一次转换，不证明完整编排、attempt/trace 更新或持久化。

Step 14 的离线编排测试先因 `application.services` 不存在而在收集阶段失败，再由最小实现转绿。测试使用构造函数注入的三组 fake 实际执行城市、POI、天气、当前预警、DeepSeek 候选和首段路线，断言全部状态变化来自显式状态机；happy 路径停在 `validating` 而非提前宣称 `ready`。城市、POI、DeepSeek 不可用进入 `failed`，天气或路线不可用进入 `partial`，可用但 partial 的结果不会被升级；结果原样保留 typed `ProviderResult` 的来源、错误与三态。AST 测试禁止生产编排器依赖 fake、HTTP/SDK、框架、环境或 sleep，重复运行验证状态轨迹不共享。该证据不覆盖调用预算、真实超时、模型修复、完整路线补全或最终确定性裁决。

Step 15 的调用治理测试先因 `application.tooling` 不存在而在收集阶段失败，再由最小实现转绿。测试锁定五个工具加 DeepSeek 生成 capability、阶段授权、城市 1/POI 3/天气与预警各 1/路线 8/生成 1 的独立逻辑预算、高德和和风 6 秒、DeepSeek 35 秒、任务 90 秒及路线 permit 并发 2。显式单调时钟覆盖完整单次窗口不足、精确 deadline、单次/总超时、时间倒退及非有限/布尔时钟；permit 测试覆盖重复、跨 governor、错误类型与并发槽恢复。治理接入编排器后，预算预耗尽会在 fake 调用前失败且三个端口调用记录均为空；happy outcome 保留六项调用快照。AST 证明策略无网络、环境、sleep 或异步运行时依赖。当前只做调用前与返回后 deadline 裁决，不证明真实 I/O 可被主动取消。

Step 16 的 DeepSeek 输出测试先因 `application.planning` 不存在而在收集阶段失败，再由最小实现转绿。测试覆盖精确合法 JSON、非法 JSON/根类型、重复键、缺失/额外/越权字段、错误类型、双日日期与父子日期绑定、本地时间、候选集外 POI、非法 UUID、虚构来源和提示控制标记；合法首轮只生成一次，可修复错误恰好 repair 一次，二次无效安全失败且结果不含原始文本，不可修复提示控制不重放。repair 拥有独立预算 1 和 35 秒窗口，剩余任务时限不足时在 fake 调用前拒绝；AST 负向测试阻止解析层引入 SDK、网络、环境读取或 sleep。补充 Step 45B 把本地失败冻结为 generation/repair 阶段与 JSON、Schema、日期、时间、POI 引用、来源引用、安全文本、截断八类闭集诊断；补充 Step 45D 在候选准入层锁定日窗口、住宿往返和跨地点正数交通窗口。补充 Step 45F 再以红测冻结活动越窗、住宿到首项、跨地点活动、末项回住宿的非正数间隔及日程容量不足五类安全时间诊断，证明 generation 失败只进入一次 repair、repair 再失败仍为 `model_output_invalid`/不可重试，且同地点连续活动不要求自环路线。纵向测试使用 `httpx2.MockTransport` 串联真实 DeepSeek adapter、resolver、orchestrator、executor、Repository 和 FastAPI GET，证明时间子类可安全传递且不含模型原文或输入值。真实路线时长超过已有间隔仍由最终硬冲突测试锁定。测试不调用真实模型、网络或凭证，也不证明真实 DeepSeek 响应质量。

Step 17 的最终校验测试先因 `AccommodationAnchor` 和最终裁决类型不存在而在收集阶段失败，再由最小实现转绿。测试覆盖双日住宿往返四段路线、缺坐标不调用、provider 超时、错误端点、路线超出活动间隔、天气缺日/错地点、预警不可用、unknown 费用、超预算、过期来源和活动窗口冲突；同时证明 `conflict` 优先于 `partial`、零 issue 才能 `ready`，活动与路线来源必须属于各自响应。新增 13 项测试，核心回归 93 项、全量后端 434 项通过；全部使用 synthetic fake，不证明高德路线质量或真实天气可用。

补充 Step 45G 已批准 D-009 的职责迁移并起草 F-001-CR1 详细设计；九项实施决策、stacked PR 和 24–34 文件范围例外随后获得批准，Step 45J 又把新增行上限调整为 2600。Step 45H 已按以下红绿顺序实现 proposal 和调度器：

- proposal parser：恰好双日、POI/来源白名单、日期、优先级、required/optional、时长类别、额外字段和 `start_time`/`end_time` 拒绝；
- 时长策略：模型类别、项目类别规则、unknown、估算 uncertainty 和分钟映射；用户逐活动时长仅预留，当前未进入公开请求；
- 路线链：住宿到首项、跨地点、末项回住宿、同地点无自环、正常双日调用数和一次 optional 桥接后不超过 8 段；
- 纯 scheduler：正常双日、恰好容纳、超出 1 分钟、walking/public-transit 缓冲、required/optional 溢出、unknown、固定输入重复一致；
- final validation：实际路线超出间隔仍为硬冲突，调度结果必须再次通过日期、重叠和 `DailyRoutePlan`；
- 失败语义：partial-with-route-data、route unavailable、缺坐标、needs_input、conflict 和 retryable 映射；
- 纵向链：真实 DeepSeek adapter 的 `MockTransport` → proposal parser → route fake → scheduler → final validation → executor → Repository → API；
- 隔离：`APP_ENV=test`、dotenv 禁用、三家配置为空和非 loopback 阻断继续作为默认门禁。

Step 45H 初始红测在 collection 阶段因缺少 `DeepSeekProposalResolver` 和 `RouteRequirement` 失败。Step 45J 又直接锁定 proposal 的 root/day/selection 重复键、未知字段、日期顺序/父子日期、目录外 POI、非法/重复来源，以及 60/120/180 分钟和景区/博物馆 120 分钟缺省。真实 proposal → scheduler → executor → Repository → GET API 链覆盖当前可达的 partial、conflict、needs_input、failed、route retryable、optional warning 和安全诊断；ready 继续由零 unknown 的冻结 API/Synthetic Executor 契约覆盖。被移除 optional 的历史 route partial/error 不得污染最终 ready 的来源、错误或 uncertainty。

Step 45N–45R 增加混合交通纵向回归：业务空结果和无 provider error 的本地非法首选路线可按用户允许方式降级；AUTH、Schema、timeout、rate limit、server 和 unknown 不触发 fallback。Step 45U 将六类 terminal 首次出现在 fallback 并发批次的行为固化到 executor → Repository → GET API：当前在途两路可完成，后续 fallback 不启动，公开 code、diagnostic 与 retryable 不被降级错误掩盖；事件同步的外部取消测试证明两路等待中 peer 均被 cancel/drain、governor 活动调用归零且取消语义原样传播。纵向链同时锁定 fallback exhausted、call budget、deadline、wrong provider、非法/额外来源和 operation-aware diagnostic；adapter/领域测试锁定距离 `2147483647/2147483648` 与时长 `1440/1441` 边界，证明异常值在 `timedelta` 和公开 DTO 前被拒绝。路线批次最多并发 2、总调用最多 8，未采用、非法或取消路线不进入来源与错误投影。前端 App 继续覆盖 `planning → needs_input`。所有场景只使用 fake/synthetic、MockTransport 和本机 API，不读取 provider 配置。

Step 45J 统一离线门禁在冻结 Python 3.13.3、Node.js 22.16.0、pnpm 11.19.0 下通过：后端 838 项、前端 64 项、文档检查器 23 项，以及 Ruff、strict mypy、Prettier、ESLint、TypeScript、Vite build、锁文件和文档契约全部绿色。该证据不调用真实 provider，也不替代 D-009 迁移后的 live UAT。

Step 45F 的 `activity_visit_order_invalid → day_schedule_capacity_exceeded` 已退出生产正常路径。迁移后 `schedule_capacity_exceeded` 只来自确定性容量计算；proposal 不产生最终精确时间的四类 gap 诊断。旧 candidate parser 与旧诊断只作为迁移回归保留，不与 scheduler 形成第二份生产事实来源。

Step 18 的 Repository 测试先因应用端口和适配器不存在而在收集阶段失败，再由最小实现转绿。12 项测试覆盖规范化 SHA-256 指纹、client ID 排除、同请求复用、异请求冲突、不同 client ID 独立任务、20 路并发只有一个创建者、冻结旧快照、非法状态跳转、乐观 version 竞争、retry attempt/trace/上限、任务不存在和安全错误。AST 负向测试禁止进程内 adapter 引入 FastAPI、HTTP/SDK、环境、SQLite 或 ORM；测试使用固定 UUID 和显式时钟，不访问网络。统一门禁中的后端 446 项测试通过。该证据只证明单进程原子性，不证明跨进程、重启恢复或 SQLite 持久化。

Step 19 的 API 测试先证明三个计划路由和 Repository 注入入口不存在，再由最小 HTTP adapter 转绿。12 项测试覆盖 `202 + Location`、精确公开字段、同请求复用、异请求 409、输入 422、GET 200/404、retry attempt/trace、非重试状态和上限 409、未知异常安全 500、应用实例隔离及健康接口兼容；相关 39 项回归和统一门禁中的后端 458 项测试通过。AST 负向测试禁止 HTTP adapter 依赖离线编排器、provider 端口/fake、网络客户端、SQLite 或 ORM。该证据只证明任务资源 HTTP 边界，不证明 POST 会执行规划或五种终态载荷已经接通。

Step 20 的终态测试先因 `PlanningJobResult`/`record_result` 不存在而在收集阶段失败，再由最小实现转绿。新增 16 项测试逐字段比较 ready、partial、conflict、needs_input、failed 的 GET JSON，覆盖重复 POST 保留终态、retry 清空旧结果、普通 advance 禁止无载荷终态、五类伪造字段组合、敏感错误文本、悬空来源、请求日期/预算错配和 stale version；验收集新增住宿区域需澄清的 needs_input case。相关 61 项回归和统一门禁中的后端 477 项测试通过。全部数据为 synthetic，不启动编排、provider 或网络，也不证明 POST 自动产出终态。

高风险确定性代码至少覆盖：

- 日期：开始/结束顺序、单日、跨月、跨年、当地日期边界；
- 时间：零/负时长、活动重叠、交通缓冲、跨日活动和缺失时间；
- 地点与路线：相同地点、断裂路线、无可用方式、缺坐标和不可判定；
- 金额：零、负值、小数精度、不同费用状态、所有类别是否出现；
- 预算：全部已知、部分未知、已知部分超支、已知部分未超支但不可完整判定；
- 来源：缺 provider、缺获取时间、未知有效期、过期、一个来源被多个字段引用；
- 状态机：所有允许转换、所有禁止转换、取消、失败恢复和终止状态；
- 重规划：same-day、adjacent-day、cross-city、accommodation、unknown 和版本冲突。

适合性质测试的恒等条件包括：

- 未知费用不会改变已知合计；
- 任何 `CostItem` 金额都不为负；
- `ready` 计划不包含阻塞级 `ConstraintViolation`；
- 未获得确认时不能从 `awaiting_confirmation` 进入 `replanning`；
- 局部重规划的新版本号高于基线，旧版本内容不被原地修改；
- 同一输入和固定时钟下的确定性校验结果保持一致。

## API 测试方向

每个业务 API 至少验证：

- 成功响应和精确 Schema；
- 缺字段、错误类型、非法枚举和超长输入；
- 404、409/422 及稳定项目错误到 HTTP 的映射；
- 重复提交、旧版本写入和状态冲突；
- 响应不包含秘密、provider 原始异常或不必要内部字段；
- 未配置外部服务时，只有需要该服务的用例失败，健康接口仍可用。

MVP 没有登录和角色权限，不伪造 401/403 测试。未来引入认证时必须重新扩展权限负向矩阵。

## Repository 与 SQLite 测试方向

持久化任务开始后验证：

- Repository 端口与 SQLite adapter 合约一致；
- 计划版本不可原地覆盖，旧版本可读取；
- `trace_id`、`decision_id`、来源和确认记录可关联；
- 事务部分失败时不留下伪成功版本；
- 重复保存、并发版本冲突和回滚行为明确；
- 时间、Decimal 和枚举往返不丢失语义；
- 测试使用临时数据库，不写入真实本地业务数据库。

具体 Schema、索引、事务和迁移测试在第一个持久化任务卡中定义。

## 前端测试方向

组件测试覆盖用户可见行为：

- `initial`、`editing`、`submitting`、`needs_input`；
- `collecting`、`planning`、`validating` 的分阶段加载；
- `ready`、`partial`、`conflict`、`error`；
- `awaiting_confirmation`、取消、确认和 `replanning`；
- 网络失败后重试、重复提交禁用和错误恢复；
- `unknown` 显示为未知而不是 `¥0`；
- 来源、获取时间、过期和估算说明可访问；
- 状态不仅依赖颜色，键盘焦点和窄屏无核心内容溢出。

React Testing Library 从标签、文本、角色和用户操作断言行为，不依赖内部组件状态或 CSS 类名作为唯一证据。正式产品 UI 需要浏览器 UAT，单元测试不能替代视觉和交互检查。

Step 23 的前端组件测试覆盖批准默认值、无独立结束日期、必填/金额/交通错误、首错焦点、Decimal 字符串 DTO、unknown 费用映射为 `null`、提交中禁用和零网络边界。本地 Microsoft Edge/Playwright 额外验证桌面与 `390×844` 窄屏、空表单错误焦点、有效 DTO 准备态、无水平溢出和仅本机静态请求；这些证据不证明计划 API、轮询或规划结果已接通。

Step 24 的前端测试使用注入的 HTTP 函数、任务 API 和轮询等待器，覆盖精确响应 Schema、同源 URL、安全 HTTP/网络/JSON 错误、任务标识一致性、允许状态跃迁、终态停止、15 次有界轮询、手动继续、重复提交禁用及卸载取消。Microsoft Edge/Playwright 以真实本机 FastAPI 验证 `202 draft`、15 次 GET 后暂停、手动恢复、桌面/`390×844` 无溢出和零控制台错误；全部请求只到本机 Vite 与 `/api`。阶段推进和五种终态仍由测试替身提供，不证明 POST 已启动规划执行器。

Step 25 的前端测试逐层覆盖终态嵌套 Schema、额外字段、错误 service、计划日期/城市/预算不一致、悬空地点引用、ready 缺少计划，以及 ready/partial 的双日活动、天气、路线、预算和费用可信状态。浏览器通过本机拦截直接读取后端冻结 ready/partial synthetic JSON，验证桌面和 `390×844` 窄屏结果优先、unknown 无金额、无水平溢出和零控制台错误；该 fixture 证据不证明后端 POST 已执行规划。

Step 26 的前端测试直接导入后端冻结 partial/conflict/needs_input/failed JSON，覆盖五种终态组合、重复/悬空来源、来源时效、诊断、硬冲突、安全错误和禁用 retry 边界。Microsoft Edge/Playwright 验证桌面与 `390×844` 的四种代表终态、结果优先、无水平溢出及零控制台错误；fixture 仍只证明前端契约消费。浏览器 QA 必须记录本步启动的 Vite 和浏览器精确 PID；`playwright-cli close` 超时时按精确 PID 收尾，禁止广泛终止 Node 或用户浏览器进程。

Step 27 的前端测试覆盖 retry endpoint 的精确 URL/方法/202、清空旧载荷、409 安全错误和非法 job；任务 hook 覆盖 partial/failed 成功恢复、同步 busy 防双击、旧结果移除、同 job/client ID、attempt 加一、trace 更换、轮询 attempt/trace 稳定、失败安全化及 attempt 3 上限。组件测试覆盖 retry 动作、needs_input 字段焦点和窄屏折叠语义。Microsoft Edge/Playwright 以本机 synthetic partial/failed 验证双击单请求、attempt 2、`390×844` 输入折叠、结果优先、返回焦点、无水平溢出及 0 console error/warning；不证明真实 provider 或后端自动执行规划。

Step 28 的 DeepSeek adapter 测试先因 `adapters.providers` 不存在而在收集阶段失败，再由最小实现转绿。21 项测试全部使用进程内 httpx2 mock transport，覆盖正式 URL、精确模型和非 thinking JSON 请求、planning/repair 不可信数据隔离、单次 HTTP 尝试、35 秒固定超时、401/402/403/429/5xx/未知状态、timeout/连接错误、空/畸形/超大响应、模型和结束原因漂移、来源与 unknown validity，以及配置脱敏。AST 负向测试阻止实现读取环境、引入 SDK/logging、sleep 或打印。后端全量 498 项 pytest、Ruff 和 strict mypy 通过；没有读取真实 Key、访问 DeepSeek 或证明 live 合约与生成质量。

Step 29 的高德 adapter 测试先因 `adapters.providers.amap` 不存在而在收集阶段失败，再由最小实现转绿。42 项测试全部使用进程内 httpx2 mock transport，覆盖 v3 geocode 与 v5 POI 2.0 的精确 GET 参数、普通城市/直辖市、provider-native Decimal 坐标、城市强限制、景区/博物馆 typecode、稳定 UUIDv5、辖区 adcode、缺坐标保真、异城/坏记录 partial 和空结果；HTTP 状态、官方 auth/限流/server/schema/未知 infocode、timeout、连接错误、非 JSON、超大响应、无效应用请求和配置脱敏也被注入。AST 负向测试阻止环境读取、SDK/logging、sleep 或打印。后端全量 540 项 pytest、Ruff 和 strict mypy 通过；不覆盖 Step 30 路线、真实 Key、POI 2.0 权限/配额或 live 数据质量。

Step 30 的高德路线 adapter 测试先因 `RouteCalculationRequest` 缺少公共交通官方必需的 citycode 而 RED，再由最小内部 DTO 修正和实现转绿。37 项测试全部使用进程内 httpx2 mock transport，覆盖 v5 walking/transit integrated 精确参数、起终点 citycode、provider-native Decimal 坐标、单路段来源关联、整数米、秒到分钟向上取整边界、超长数字、空/多条/坏路线、端点漂移、无路线 infocode、HTTP/timeout 安全映射和传输前请求拒绝；相关回归 116 项、后端全量 577 项、Ruff 和 strict mypy 通过。测试不读取真实 Key、不访问高德，也不证明 live 路线质量、交通时刻或票价。

Step 31 的和风 adapter 测试先因 `adapters.providers.qweather` 不存在而在收集阶段 RED，再由最小实现转绿。Step 37 补充后共 57 项测试，全部使用进程内 httpx2 mock transport 和运行时生成的 test-only Ed25519 私钥；除 JWT、端点、坐标、双日、预警、失败和脱敏外，新增 `metadata.attributions` 精确保留及缺失、空、错误类型、超长和控制字符拒绝。测试不读取真实私钥、不访问和风天气，也不证明账户 Host、权限、配额或 live 数据质量。

Step 32 的配置与启动测试使用进程环境隔离、临时目录和运行时生成的 test-only Ed25519 私钥，覆盖三组全空配置可启动健康服务、完整配置无网络装配、和风任一部分配置拒绝、相对/缺失/非法/超限私钥失败、固定模型/Base URL、防敏感 `repr` 和稳定错误码。`.env.example`/CI 负向契约强制所有当前字段为空并拒绝废弃 `QWEATHER_API_KEY`。Step 41 进一步把 `APP_ENV=test` 固定在应用导入前，明确禁用 `.env.local` dotenv source，并用自动 fixture 拒绝所有非 loopback socket；因此本机已有真实凭证时，默认 pytest 仍只装配 disabled provider。该证据不证明凭证有效、账户权限、网络可达或 live provider。

Step 33 新增统一失败矩阵。transport 层对 DeepSeek 生成、高德城市解析和和风双日预报各注入成功、空数据、401、403、429、timeout、503、Schema 漂移和连接失败，共 27 项；每项断言单次尝试、三态、provider、自有错误码、retryable、空失败来源及敏感详情不进入结果。应用层对七类错误分别注入城市、POI、DeepSeek 三个关键边界，以及天气、预警、路线三个非关键边界，共 42 项；关键链路精确短路为 failed，非关键链路保留候选并降级为 partial。既有测试继续覆盖高德业务 infocode、过期/未知时效、调用总预算和最多三次任务 retry。矩阵完全离线，不代表 live provider 可用。

Step 34 的离线 Agent scorecard 固定 10 类输出：合法精确 JSON，以及畸形、Markdown 包裹、重复键、越权终态、候选外地点、虚构来源、日期越界、提示控制和超长输出。每个 case 断言精确本地分类、可修复性和无原文错误；合法 case 重复 10 次且上下文目录重排后仍生成同一 typed candidate。ready、partial、conflict、failed 四场景各重复 10 次，终态、状态历史、候选、路线和最终校验完全相同。该评估同时复用既有单次修复、二次失败、剩余时限和提示控制测试；不评价 live 模型语言质量，也不把 synthetic 通过表述为 DeepSeek 真实通过。

Step 35 的浏览器闭环不拦截任务 API：专用本地组合根把冻结五终态交给 synthetic executor，经真实 FastAPI background task、状态机、进程内 Repository、POST/GET/retry 和 Vite 代理进入 React。自动化锁定新建只调度一次、幂等复用不重复调度、retry 重新调度，以及 ready/partial/conflict/needs_input/failed 的合法路径。轮询按状态图可达性接受因采样遗漏的中间快照，仍拒绝回退和不可达分支。Playwright 在桌面与 `390×844` 验证五终态、partial attempt 2、needs_input 焦点、unknown、来源、零横向溢出和零控制台告警；全部动态业务请求仅访问本机。该证据不证明默认应用已装配真实规划执行器或任何 live provider 可用。

## 外部适配器和失败注入

适配器合约测试覆盖统一 envelope 的 `ok`、`partial` 和 `unavailable`，并注入：

- 连接失败、DNS/网络不可用和超时；
- 401/403 类鉴权失败，映射为 `provider_unauthorized`；
- 429 或 provider 限流，映射为 `provider_rate_limited`；
- 连接超时映射为 `provider_timeout`，5xx 或临时不可用映射为 `provider_unavailable`；
- 200 但空数据；
- 200 但字段缺失、类型变化或未知枚举，映射为 `provider_schema_invalid`；
- 坐标、距离、单位、日期和时区异常；
- 数据超过有效期或 provider 不提供有效期；
- 返回文本包含看似系统指令的内容。

重试测试使用可控时钟或替代等待机制，不执行真实长时间 sleep。必须证明不可重试错误不会进入盲目重试，可重试错误受次数和总时限限制。

## 数据时效性策略

- 时效判断使用可注入时钟，不直接依赖测试运行时的真实当前时间；
- fixture 同时保存 `fetched_at`、`valid_until` 或“有效期未知”；
- 每个 provider 的具体有效期规则在真实合约接入后记录，当前不虚构统一 TTL；
- 测试至少覆盖 `fresh`、临界时间、`stale` 和 `unknown_validity`；
- 使用过期缓存进行降级时，结果必须保持 `partial` 并显示警告；
- 未来日期超出天气可用范围时返回数据缺失，不用模型常识填补。

## 测试替身与 fixture

- 使用端口级 fake、stub 或 spy，不在领域代码中加入测试分支；
- fixture 只在取得真实合约后创建，必须脱敏、最小化并标注 provider 与 Schema 版本；
- 不复制 Agent1 的 `.env`、缓存或响应文件；
- 固定 ID、时钟、随机种子和模型回放输入，减少不稳定测试；
- fixture 不包含真实姓名、联系方式、精确个人行程或未授权 provider 原文；
- 测试替身不得返回“假成功”来证明生产能力，结果说明必须标为离线测试。

B-000 不创建 DeepSeek、高德或和风天气 fixture，因为项目尚未取得并验证真实合约响应。

## Agent 评估

Agent 评估与普通单元测试分开：

| 维度 | 核心指标方向 | 失败示例 |
| --- | --- | --- |
| 需求理解 | 硬约束、软偏好、缺失项分类 | 把硬约束当偏好或静默补全 |
| 工具授权 | 必要工具率、越权调用数 | 在错误状态调用工具、发明工具 |
| 结构化输出 | Schema 合格率 | 缺字段、非法枚举、自由文本代替结构 |
| 事实忠实 | 无来源事实数 | 编造天气、路线、价格或营业信息 |
| 约束遵循 | 硬违规被保留并响应 | 尝试覆盖代码冲突结果 |
| 局部性 | 未受影响日期 diff | 当天修改重写其他日期 |
| 确认边界 | 高影响变更确认率 | 跨城或住宿变更自动执行 |
| 失败降级 | 部分结果和恢复动作 | provider 失败后返回假成功 |
| 可解释性 | 来源引用和不确定性表达 | 把 estimated 说成 verified |
| 安全 | 提示注入服从率应为零 | 把 provider 文本当系统命令 |

固定回归 case 应包含正常、边界、冲突、provider 失败、恶意外部文本和重规划。评估阈值、样本数量和模型 live 运行成本必须在 Agent 实现任务中基于真实基线确定；当前不虚构通过率。

D-009 的离线 Agent eval 已证明：模型 Schema 不接受最终精确时刻、路线时长、verified 时长或终态；同一冻结 proposal 重复解析一致；proposal 顺序不能覆盖 scheduler/final validation 的冲突。评估只使用 fake/MockTransport 和冻结输出，不调用真实模型；新的 live 质量回归仍需单独授权。

## live smoke 隔离

真实 API 验证必须满足全部条件：

- 用户已创建并授权使用对应账户、应用和专用测试 Key；
- 使用独立命令和标记，普通 `test` 与 CI 不会触发；
- 调用范围、次数、预计配额和可能费用在执行前明确；
- 只请求最小非敏感样例，不上传真实用户行程；
- 日志和证据只记录 provider、时间、稳定错误码和脱敏摘要；
- live 失败不能通过修改离线测试来掩盖；
- provider 可用性结论带执行时间，不能永久视为有效。
- 执行前必须验证产品已按 provider 当前条款展示归因/AI 生成披露；真实响应中的归因字段必须经过负向契约证明不会被丢弃、改写或与对应数据分离；
- 高德真实数据测试默认不保存截图、响应体或持久缓存，直到具体使用场景的许可边界已由账户条款或官方工单确认；

Step 37 初次审计时三家本地凭证均未配置；用户随后自行创建专用凭证，被 Git 忽略的本地配置经无网络检查确认三家 adapter 与真实执行器均可构造。补充收口以离线测试证明高德固定来源归因、和风归因原样传递、DeepSeek 披露按来源显示、三家齐备才装配真实执行器及无凭证零调用。Step 38 在 12 元上限和固定调用预算内只创建一个杭州双日计划：三家 live 契约均通过，但确定性终态为 `conflict`；同一授权内额外 1 次高德公交路线窄探针通过。全程没有保存原始响应、持久缓存或真实高德截图。DeepSeek 项目凭证不得从 Agent1 复制。

Step 39 的真实数据 UAT 沿用同一调用和费用硬边界，只经现有 UI 创建一个杭州双日任务。DeepSeek 返回内容未通过严格 Schema，任务以不可重试 `failed` 安全停止；高德和和风来源仍能在桌面与 `390×844` 失败界面正确归因，无 DeepSeek 来源时不展示 AI 披露，DOM 和控制台无敏感信息。该结果证明 live Schema 失败路径和响应式错误界面，不证明正常真实计划可用；UAT 结论为 `FAIL`，必须经后续审查和修复后重新授权 live 回归。

Step 40 发现默认测试可能读取本机 `.env.local`、本地候选失败误映射为 provider Schema、DeepSeek repair/上下文缺项及日期、来源、天气地点和 timeout 契约缺口。Step 41 用离线回归关闭这些阻塞：测试组合禁用 dotenv 并拒绝外网；adapter envelope 与本地候选失败分别锁定为 `provider_schema_invalid`/`model_output_invalid`，安全诊断不含原文；generation/repair 共享冻结 Schema，截断只允许一次 repair，时间窗/偏好/交通/住宿/天气和 POI-only 来源完整传递。冻结 Python 3.13.3、Node.js 22.16.0、pnpm 11.19.0 下统一入口一次通过：后端 756 项 pytest、前端 64 项 Vitest、文档检查器 23 项及全部格式、lint、typecheck、build 和文档契约为绿色。该结果不替代下一次单独授权的 live UAT。

## 质量门禁

每次任务按变更类型选择门禁，B-000 最终统一门禁至少包含：

| 门禁 | 目的 | 当前计划入口 |
| --- | --- | --- |
| format check | 防止未格式化差异 | Python/前端 formatter 配置 |
| lint | 发现静态规则问题 | Ruff、ESLint |
| typecheck | 发现类型边界问题 | mypy、TypeScript |
| unit/component tests | 证明局部行为和失败路径 | pytest、Vitest |
| integration tests | 证明 API 与本地组件协作 | pytest + FastAPI TestClient、临时资源 |
| build | 证明前端可构建 | Vite |
| docs check | 必需文档、相对链接、状态一致性 | Step 11 文档脚本 |
| CI contract | 只读权限、空 provider 凭证、Action SHA 和统一入口 | 文档与仓库检查脚本 |
| secret/ignore check | 阻止本地凭证进入交付 | ignore、敏感模式、staged diff |
| scope check | 阻止越界文件和无关实现 | Git 路径与 diff 审查 |
| browser UAT | 证明真实用户流程可操作 | 本地浏览器 |
| independent QA | 从规格设计负向测试并审查证据 | Step 40 |

`scripts/verify.ps1` 是 Windows 本地与 CI 的统一入口，按固定顺序验证运行时、锁文件、构建约束、依赖同步、后端、前端、构建、文档检查器测试和当前项目文档/仓库契约。任一原生命令返回非零时脚本整体失败。检查器的负向测试覆盖非法后端状态、前端失败恢复、文档断链、非空凭证、两种 GitHub Secret 语法、job 写权限、local/Docker Action 和浮动 Action 引用；Python 版本 probe 使用隔离 uv 环境覆盖 Windows 冷启动路径。

## 红绿证明

以下高风险能力首次实现时至少记录一次红绿证明：

- 健康响应 Schema；
- `unknown` 费用不按零处理；
- 预算 Decimal 精度；
- 禁止状态转换；
- 跨日/跨城/住宿变更需要确认；
- provider 错误映射和重试终止；
- 工具白名单与提示注入隔离；
- 文档断链、秘密忽略规则和 CI Action SHA 固定。

证据记录覆盖的错误类别和最终命令，不保存故意错误代码或完整终端输出。

## 角色与验收职责

| 角色 | 职责 | 不能替代 |
| --- | --- | --- |
| 实现者 | 编写实现和基础测试，运行相关门禁 | 独立负向测试、用户体验判断 |
| 独立 QA/审查者 | 从规格和风险设计失败用例，审查 diff 和证据 | 用户对真实流程的接受 |
| CI | 在固定环境重复离线门禁 | live provider、视觉体验、产品取舍 |
| 用户 UAT | 验证本地真实任务、文案和恢复流程 | 类型、lint、安全和底层合约测试 |

同一实现者可以运行检查，但不能作为唯一验收依据。

## 证据规则

最终证据写入 [evidence.md](./project-management/evidence.md)，每项至少记录：

- 关联任务和风险；
- 分支、提交、环境和时间；
- 验证层级与命令；
- 预期、实际和结论；
- 红绿或负向证明；
- 未覆盖范围和剩余风险；
- 是否需要并已完成人工 UAT。

不保存完整终端日志、Token、Cookie、密码、连接串、真实 `.env`、provider 原始敏感响应或个人行程数据。无法运行门禁时必须说明原因、替代检查、复现方式和是否阻塞，不能写成通过。

## 完成标准

一个任务只有在以下条件满足时才能由测试角度完成：

- 验收标准对应的正向和关键负向测试已执行；
- 适用的 format、lint、typecheck、test、build 和文档门禁通过；
- 高风险规则完成红绿或等价失败证明；
- 默认测试没有访问真实外部服务；
- 独立 QA 已审查关键路径、失败路径和 diff；
- 用户 UAT 已完成需要人工判断的流程；
- evidence 记录可复现结论和未覆盖范围；
- 没有用 mock、跳过测试或降低断言冒充真实能力。
