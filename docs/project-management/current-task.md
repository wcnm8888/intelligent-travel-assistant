# 当前任务

## 任务元数据

- 任务 ID：`F-005`
- 名称：外部服务韧性、数据时效与 Agent 评估
- 等级：`L`
- 状态：`ACTIVE`
- 最近完成 Step：`Step 8 - 全量门禁与 stacked PR`，状态 `DONE`
- 当前 Step：`Step 9 - 依序合并与归档`，状态 `TODO`；尚未批准、尚未进入
- 前置任务：F-001 至 F-004B1 已交付并归档
- 基线提交：`c5f07e12abdc37f977ee0f7181a5f2800f015066`
- 首层本地分支：`feat/f-005-resilience-domain-contracts`
- 长期决策：`D-014`
- 交付拓扑：五层 stacked PR；用户已在 Step 8 批准于 application/Agent 与 UI 之间新增独立离线 application eval 集成层；merge 仍须 Step 9 单独批准

## 用户目标与工程价值

当高德、和风天气或 DeepSeek 发生鉴权失败、限流、超时、暂时不可用、Schema 漂移、空数据、过期数据或无效模型输出时，用户仍能稳定知道哪些事实可信、过期、缺失或未验证，当前是否存在可用计划，以及应该安全重试、修改输入还是修复本地配置。

工程上统一现有 `ProviderResult`、freshness、调用治理、proposal/repair、最终校验、API 错误投影和前端终态语义，建立完全离线的固定 Agent 评估门禁，同时保持 legacy/V2/V3、F-003 replan、F-004A 多日和 F-004B1 多城市兼容。

## 基线事实与保留边界

- Step 0 复核时 `HEAD == main == origin/main == c5f07e12abdc37f977ee0f7181a5f2800f015066`，工作区干净；
- PR #19/#23/#24/#25/#26 均为 `MERGED`，当前没有开放 PR；PR #26 的 merge commit 为 `c5f07e12abdc37f977ee0f7181a5f2800f015066`；
- main CI run `32386260285` 在该提交上 `completed/success`；
- F-004B1 Step 0–8 已完成并归档；F-005 激活前没有活动任务；roadmap 顺序为 F-005 → F-004B2；
- F-001 产品状态保持 `PARTIAL`；Step 45M 真实 UAT 为 `FAIL`，Step 45T 真实 UAT 为 `PASS`；
- unknown 金额保持 `null`，不得按 0 处理；混合交通 fallback 只有离线证据；
- F-004A 和 F-004B1 均没有真实 Provider UAT；F-004B1 城际 Provider 调用恒为 0；
- SQLite schema 保持 version 2，migration 只允许既有 version 1/2；
- 本任务默认完全离线，不读取 `.env.local`、秘密或本地 Provider 配置，不调用真实 Provider。

## 已批准产品与失败语义

- `needs_input` 只用于用户能够修正的缺失、歧义或必要输入；
- `conflict` 只用于确定性代码发现的硬约束冲突；
- 关键链路无法形成安全计划时为 `failed`；
- 只有仍存在可执行计划但非关键事实缺失、过期或不可完整验证时才为 `partial`；
- `ready` 必须满足关键数据、来源、时效和确定性校验边界；不得把缺失、过期或参与决策的未验证数据提升为 ready；
- 鉴权失败不得自动重试；关键链路为 failed，可选事实为 partial，并提示本地配置问题；
- 限流、超时和暂时服务不可用在批准的自动重试耗尽后，按关键性进入 failed 或 partial；
- Provider Schema 漂移不自动重试；关键链路为 failed，可选事实为 partial；
- 空数据不自动重试；只有用户可修正的输入问题才能进入 needs_input；
- DeepSeek generation 输出不合法只允许既有一次语义 repair，repair 后仍无效为不可自动重试的 `model_output_invalid`；
- legacy/V2/V3 继续使用现有五种终态、attempt 3 上限和同 URI API。

## 已批准数据时效政策

- 保留现有 `fetched_at` 作为来源获取/观测时间，不新增公开 `observed_at` 字段；
- Provider payload 自带的业务发生时间继续存在于 typed data，不与来源获取时间混用；
- `valid_until` 只有 Provider 合约或项目确定性规则能够证明时才填写；本任务不虚构统一 TTL 或 Provider TTL；
- freshness 由 `fetched_at + valid_until + evaluated_at` 计算，attribution 只证明来源，不证明 freshness、准确性或 availability；
- 已采用的关键路线事实 stale 时不得继续支持已验证排程；没有合法替代时进入 failed；unknown validity 时最多形成 partial；
- 天气预报、当前预警、POI、城市和住宿事实 stale/unknown-validity 时按能力剔除或披露为 partial，不得提升 ready；
- DeepSeek proposal 始终是不可信建议，不能单独支持 ready；
- 用户输入和系统规则继续显示来源，但不冒充 Provider 验证；D-013 已冻结的用户提供城际 availability 排除边界不变；
- unknown 费用继续为 `amount=null`，不得从缺失值生成合法零元费用。

## 已批准重试、deadline 与 fallback 治理

- Amap/QWeather 的幂等只读请求只对 timeout、5xx 和受控 429 最多额外尝试一次；
- DeepSeek 不做自动传输重试，整个 job 的 generation 1、repair 1 上限不变；
- 每个可重试逻辑调用最多 2 个 HTTP attempt；Amap 额外 attempt 最多 3、QWeather 最多 1、任务额外总计最多 4；
- retry 使用注入式 full jitter `0–200ms`；合法 `Retry-After` 最多 2 秒；剩余任务时限不足时不等待、不重试；
- HTTP attempt 计入独立 attempt 预算和任务总 deadline，不增加既有逻辑工具预算；
- 终态、外部取消、deadline 或预算耗尽后不得启动新调用；active peer 必须 cancel/drain 并归零；
- 混合交通 fallback 保持现有确定性边界：只有业务空结果或无 Provider error 的本地非法路线可以按用户已允许顺序 fallback；
- auth、schema、timeout、rate limit、server 和 unknown 等 Provider-wide 失败不触发 route mode fallback；
- 不新增 Provider，不扩大铁路、航空或长途客运调用；F-004B1 城际 Provider 调用仍为 0。

## 已批准 Agent 安全与离线评估

- legacy/V2/V3 proposal/repair 都只接收 bounded、typed、allowlist 输入；
- repair 不接收原始无效模型输出、完整用户自由文本、Provider 原始响应或敏感内容；
- Provider 文本先转换为项目自有枚举、ID、数值和有限文本，不得成为 system/tool 指令；
- 非 allowlist 字段、tool call/tool result/system role 内容、提示控制标记、目录外 POI/来源以及模型提供的终态、路线、费用可信状态或 Provider attribution 必须拒绝；
- 建立至少 48 个完全离线 synthetic Agent eval case；legacy、V2、V3、F-003 各至少 6 个，至少 12 个安全攻击 case；
- 评分至少覆盖正确性、约束遵守、来源完整性、unknown/partial 真实性、工具授权/调用预算、失败安全性和确定性重复；
- 安全、来源伪造、工具越权、预算超限和假 ready 为 `100%` 硬门禁，其他维度加权总分至少 `95%`；
- 不使用 LLM-as-judge，不调用真实模型；评估结果不得表述为真实 Provider UAT。

## 已批准 API、隐私与可观察性边界

- 不新增 URI、公开顶层错误码或 JSON 键；复用既有 `data_stale` 和安全 `diagnostic_code`；
- legacy/V2/V3 JSON 键集合、canonical fingerprint、Repository 方法集合和 SQLite schema v2 保持兼容；
- F-003 replan lifecycle、planning retry 与 replan attempt 隔离、失败不替换原计划等语义不变；
- 全部 V3 replan 继续在 Provider、decision、lineage 和 plan version 写入前拒绝；
- 诊断只允许 trace ID、Provider/capability 枚举、逻辑调用/attempt 序号、状态、稳定错误码、retry 决策、有限耗时与来源/预算计数；
- 不保存 Key、Token、Cookie、Authorization、完整 Prompt、完整自由文本、Provider 原始响应、原始错误 body、原始模型输出或异常堆栈；
- 诊断不进入 SQLite；CI 只输出聚合分数和失败 case ID，不上传 case payload artifact；
- 不新增账号、云同步、遥测平台或公网服务。

## 测试与验收矩阵

- domain：错误分类、fresh/边界/stale/unknown-validity、关键性和终态决策；
- contracts：现有错误码、legacy/V2/V3 shape、unknown/null、额外字段拒绝；
- adapters：auth/429/timeout/5xx/schema/empty/unknown、attempt、jitter、Retry-After、取消和安全诊断；
- application：逻辑调用/HTTP attempt/总 deadline、终态零新调用、peer drain、retry→fallback→stop；
- Agent：proposal/repair 最小化、提示注入、工具越权、来源伪造和固定 eval 门禁；
- API：现有 URI 与 envelope、data_stale、retryable、attempt 3、F-003/F-004A/F-004B1 兼容；
- Repository/SQLite：临时 schema v2、restart/retry/delete、typed round-trip、无诊断持久化；
- frontend：partial/failed/stale/unknown、配置/重试/修改输入恢复动作、桌面与 390px；
- browser/security：loopback-only、console/network/accessibility、隐私模式与 case payload 不泄漏；
- 默认测试仅使用 fake、MockTransport、synthetic fixture 和临时 SQLite，阻断非 loopback 网络。

## Step 1 冻结的可实现契约

- 结构：纯 `domain/resilience.py` 政策 + 每个 planning attempt 显式创建的 `application/tooling/resilience.py` runtime + 单次 HTTP adapter；禁止全局或 `contextvars` attempt 预算。
- 顺序：logical reserve → initial attempt → error/freshness classify → 额外预算/deadline/terminal 检查 → delay → 最多一次 retry → logical complete → capability disposition → deterministic terminal。retry 保持同一逻辑 permit/并发槽；fallback 只在 retry 结束后按既有业务空/本地非法边界执行。
- 时限：Amap/QWeather 每 HTTP attempt 沿用 6 秒、DeepSeek 35 秒；timeout/5xx 使用 `0–200ms` full jitter，受控 429 的最终 delay 不超过 2 秒。剩余 deadline 不足 delay 加完整 attempt timeout 时不启动 retry。
- freshness：`evaluated_at <= valid_until` 为 fresh；缺少有效期为 unknown；GET 返回持久化快照，不按墙钟改写。stale 最终路线拒绝，stale 天气/预警剔除，stale/unknown 地点事实最多 partial。
- Agent：generation 使用 bounded typed allowlist；repair 使用只含日期/城市骨架、允许 location/source 目录、固定规则和稳定验证码的 `PlanRepairBrief`，不含原始模型输出、自由文本、偏好/硬约束或 Provider observations。
- eval：固定 legacy/V2/V3/F-003 各 12 case，每组正常/边界、Provider 失败、freshness/unknown、安全攻击各 3，全部重复执行两次。权重为 25/20/15/15/10/15，总分至少 95%，提示注入、来源伪造、工具越权、预算超限和假 ready 零失败。
- API/UI：复用既有 `data_stale` 和四个 capability diagnostic code；unknown-validity 继续由 source/uncertainty 表达。顶层 retryable 与 `attempt < 3` 共同决定 UI retry，前端不得重算 freshness 或终态。
- stack：Stack 1 纯 domain；Stack 2 attempt runtime/adapter 输入；Stack 3 application、后端同 shape 投影和 Agent 输入安全；Stack 4 仅让固定 eval 经过 legacy/V2/V3/F-003 各自真实离线 application 入口；Stack 5 前端与交付验收。详细矩阵以 architecture、api-contract、agent-domain-spec、design-spec 和 testing-strategy 为准。

## Step 2 实现结果

- `ProviderError` 新增内部 `retry_after_seconds`，只允许 rate-limited 使用有限、非负、`<=2s` 数值；其他类别、bool、NaN/Infinity 和越界值 fail closed。没有修改公开 contract 或 JSON shape。
- 新增纯 `domain/resilience.py`：冻结高德/和风每逻辑调用最多 2 HTTP attempt、Provider 额外预算 3/1、任务额外预算 4、attempt timeout 6 秒；DeepSeek generation/repair 为 1 attempt、35 秒、0 transport retry。
- `decide_retry` 只对 Amap/QWeather timeout、server 和带安全 Retry-After 的受控 rate-limit 返回 retry；full jitter 限 `0..200ms`，最终 rate-limit delay 封顶 2 秒；attempt/Provider/任务预算、remaining deadline、terminal 或 cancelled 任一不允许时确定性停止。
- `decide_freshness` 冻结 route stale reject、weather/alert stale omit、location stale partial-use、unknown-validity partial-use；`decide_provider_failure` 的 Provider 失败处置闭集只有 required→failed、optional→partial，不包含 needs_input/conflict。
- 安全诊断是 8 项 `StrEnum` 闭集，决策对象 frozen/slotted；未引入自由诊断文本、原始 header/body、Prompt 或持久化字段。
- RED 在 collection 阶段因新领域符号不存在失败；GREEN 定向 108 项通过。完整 domain + contracts/golden 342 项、Ruff format/lint 和 strict mypy 134 files 通过；unknown 金额/null、freshness inclusive boundary、legacy/V2/V3 exact shape 和领域依赖边界保持。
- 本 Step 生产/测试范围精确为 5 文件：3 个 domain 文件和 2 个 domain 测试文件；未修改 adapter、application、API、Repository、SQLite、Provider、前端、Schema/migration、依赖或 lockfile，未进入 Step 3。

## Step 3 实现结果

- RED：新增 runtime 与 adapter 安全 Retry-After 测试后，首次定向运行在 collection 阶段因 `ProviderAttemptRuntime` 尚不存在失败；随后只实现批准范围内的最小 GREEN。
- 新增显式 `ProviderAttemptRuntime`：每个 planning attempt 独立持有 HTTP attempt 记录、Amap/QWeather/任务额外预算、总 deadline、active task 与 closed 状态；没有模块全局预算或 `contextvars`。
- runtime 复用 Step 2 纯领域政策，覆盖单 attempt timeout、注入式 jitter/sleeper、retry delay、Provider/任务预算、deadline 前置拒绝、异常/取消 close、active peer cancel/drain，以及 closed 后零新调用；尚未由任何 planning service 创建或调用。
- Amap/QWeather adapter 仍各自只执行一次 HTTP exchange，不含 sleep 或 retry；只把 timeout/request/HTTP/Schema 错误规范化为安全 `ProviderError`，并将合法 `Retry-After` delta/HTTP-date 收敛为 `0..2s` 数值，不保留原始 header 或 body。DeepSeek 生产代码未修改，既有 transport retry=0 回归通过。
- GREEN 定向 121 项通过；Provider/DeepSeek/治理/既有编排兼容回归 378 项，domain/contracts 164 项通过；全 backend Ruff format/lint 和 strict mypy 136 files 通过。
- 本 Step 生产/测试范围为 8 个已批准核心或受控相邻文件、净新增 859 行、未预期文件 0；未修改 planning application service、API、Repository、SQLite、前端、Schema/migration、依赖或 lockfile，未读取秘密、调用 Provider、commit、push、创建 PR、触发 CI 或进入 Step 4。

## Step 4 实现结果

- RED：显式 runtime 接线测试首次因 orchestrator/executor 参数不存在而 4 项失败；freshness 纵向测试随后证明 stale weather 仍进入 plan。最小 GREEN 后同一 runtime 已覆盖 legacy/V2/V3 的城市、POI、天气、预警、路线和 DeepSeek generation/repair。
- executor 对每个 planning attempt 创建一次 runtime，在任何 Repository/API 终态发布前 close；logical governor 仍只 reserve/complete 一次，HTTP retry 只进入独立 attempt 记录与预算。
- deadline 不足时禁止启动 HTTP，并安全投影为既有 `provider_timeout`/diagnostic；并发城市与路线收集在异常、取消时 cancel/drain active peers。runtime 终态关闭后拒绝新 execution。
- retry 在 route fallback 前完成；auth/schema/timeout/rate-limit/server/unknown 和 stale route 均不触发 mode fallback。stale required route 进入 failed + `data_stale`，stale weather/alert 被剔除并进入 partial；参与决策的 unknown-validity 不提升 V3 ready。
- 后端只复用既有 URI、JSON keys、`data_stale`、retryable 和 diagnostic code；未修改 Repository 接口、SQLite schema v2、migration 或 F-003 replan 写入边界。
- 定向 runtime/application `60 passed`，全 backend `1264 passed`；Ruff format/lint 和 strict mypy 136 files 通过。任务累计生产/测试 22 文件、净新增 2713 行，未触发任务 90 文件/8000 行阈值；Step 4 核心/受控相邻范围内无未预期文件。
- 未进入 Step 5 Agent eval、前端、Schema/migration、依赖/lockfile、数据库、秘密、真实 Provider/外部网络、commit、push、PR 或远程 CI。

## Step 5 实现结果

- RED：测试首次在 collection 因 `PlanRepairBrief` 不存在失败，证明 repair 端口仍包含原始无效输出和完整 context；最小 GREEN 将 legacy/V2/V3 repair 统一为不含这些字段的 frozen/slotted brief。
- brief 只含 request version、expected dates、day windows、V3 city skeleton、允许 location/source ID 目录、项目 category/city adcode、稳定 validation code 和可选无值 time failure；预留 F-003 affected refs/command category，不携带 baseline 未受影响内容。
- generation 和 repair 对 Provider 文本执行双层门禁：只允许最多 120 字、trimmed 单行、无控制符/提示控制标记的 display label；category/kind 只允许项目 token。unsafe 文本投影为 `null`，原始值不进入 system/user model message。
- 固定离线 eval 位于 `backend/evals/f005`：`f005-v1` 共 48 case，legacy/V2/V3/F-003 各 12，每 slice 正常/边界、Provider 失败、freshness/unknown、安全攻击各 3；固定 runner 连续执行两次并严格解析 case shape。
- 六维权重 25/20/15/15/10/15 的结果为 100.0%；提示注入、来源伪造、工具越权、预算超限和假 ready 五类硬门禁失败均为 0。报告只包含版本、计数、分数和失败 case ID，不输出 payload。
- 定向 Agent/adapter/ports/eval `127 passed`，全 backend `1270 passed`；Ruff format/lint、strict mypy 137 source files 和 eval 4 files 通过。
- 任务累计生产/测试/eval 36 文件、净新增 3421 行；经 case fixture 无语义机械压缩后，Stack 3 估算净新增 1706 行，低于单 stack 2500 行阈值；无未预期文件。
- 未进入前端、Schema/migration、依赖/lockfile、数据库、秘密、真实 Provider/外部网络、commit、push、PR、CI 或 Step 6；离线 eval 不构成真实 Provider/模型 UAT。

## Step 6 实现结果

- RED 首次运行 30 个前端定向用例时有 4 项按预期失败，分别证明鉴权配置标题、固定错误优先级、stale 恢复文案和 unknown-validity 披露尚未实现；最小 GREEN 后同一命令全部通过。
- 失败与 partial 组件只消费服务端既有 `status/retryable/errors/uncertainties/sources/attempt`：鉴权显示本机配置问题且无 retry；暂时失败沿用受控 job retry；stale 显示“数据可能已经变化/重新获取数据”；unknown-validity 明示“不代表当前有效”。
- 错误显示顺序冻结为用户输入、确定性冲突、配置、可重试暂时失败、stale、不可重试数据/模型错误；排序只影响呈现，不改变服务端数组、状态、freshness 或恢复许可。
- legacy/V2/V3 exact parser、attempt 3 上限、unknown 金额、F-003 replan 和 V3 用户城际来源语义均保持；前端全量 `99 passed`，Prettier、ESLint、TypeScript、Vite build 与无 SQLite API/contracts `98 passed`。
- 本 Step 6 个批准组件/测试文件、净新增 230 行、未预期文件 0；任务累计 42 文件/3651 净新增行，低于 Stack 4 与任务阈值。
- 未创建临时 SQLite、启动浏览器、访问网络或 Provider，未修改 Schema/migration、依赖/lockfile、后端生产代码、数据库、秘密或交付状态，也未进入 Step 7。

## Step 7 验收结果

- 临时 schema v2 SQLite 纵向最终 `31 passed`；冻结 V3 browser fixture 在当日成为 D+0 后，以 RED `1 failed` 锁定日期漂移，再只为 browser 测试支撑增加显式 `ITA_BROWSER_START_DATE` 平移，默认 fixture、contracts、Repository、Schema 和 migration 均未改变。
- Edge loopback synthetic QA 在 `1440×1000` 与 `390×844` 覆盖 V3 partial、第三日键盘切换、skip link、retry、reload 恢复、unknown/null、stale/unknown-validity 文案；overflow、重复 ID、ARIA 引用、无名称控件、console error/warning 均为 0。
- 浏览器 57 条请求全部为 `127.0.0.1`；临时 SQLite 的 migration 仍为 1/2，TEXT 列秘密/原始 payload/运行诊断模式扫描为 0，三份临时文件已移入可恢复的 Windows 回收站。
- 独立 Codex Security diff scan `c0d1100d-227b-4572-aa5a-769cb0689541` 覆盖 8 个信任面，coverage complete、0 finding；安全/韧性定向 `365 passed`，SQLite `31 passed`，Ruff 通过，项目权威 strict mypy 对 137 source files 通过。
- Step 7 仅受控修改 2 个测试文件、净新增 59 行；任务累计 44 个生产/测试/eval 文件、净新增 3710 行，未触发阈值；生产源码、Schema/migration、依赖/lockfile 未产生 Step 7 差异。
- 过程偏差：首次用 `npx --yes @playwright/cli@latest --help` 探测 CLI 时可能查询 npm registry；后续全部使用 `npx --offline`，产品/浏览器请求仍全为 loopback且未调用 Provider。由于严格非 loopback 约束曾可能被触发，Step 7 的机器状态为 `DONE`，但不能写成无条件 `PASS`；该偏差已由用户明确接受。
- 未读取 `.env.local`、秘密或本地 Provider 配置，未调用真实 Provider，未 commit、push、PR、CI、merge 或进入 Step 8。

## 核心文件清单与受控相邻扩展

### Step 0–1：治理与设计

- `docs/README.md`
- `docs/product-brief.md`
- `docs/architecture.md`
- `docs/api-contract.md`
- `docs/agent-domain-spec.md`
- `docs/design-spec.md`
- `docs/testing-strategy.md`
- `docs/decisions.md`
- `docs/project-management/{roadmap,current-task,implementation-plan,progress,evidence}.md`

### Stack 1 / Step 2：领域与 contracts

- `backend/src/intelligent_travel_assistant/domain/provider_result.py`
- 允许新增 `backend/src/intelligent_travel_assistant/domain/resilience.py`
- `backend/src/intelligent_travel_assistant/domain/__init__.py`
- 对应 domain/resilience 与相邻 contracts golden 测试；公开 `contracts/errors.py` 原则上不修改，只有发现既有 `data_stale` 与冻结文档冲突时才停止报告

### Stack 2 / Step 3：Provider runtime

- 允许新增 `backend/src/intelligent_travel_assistant/application/tooling/resilience.py`
- `backend/src/intelligent_travel_assistant/adapters/providers/{amap,qweather}.py` 及直接 exports
- DeepSeek 只做 transport retry=0 回归；其 typed proposal/repair 输入修改归 Stack 3 / Step 5
- 对应 adapter failure matrix、MockTransport 和 governance 测试

### Stack 3 / Step 4–5：application 与 Agent 安全

- `backend/src/intelligent_travel_assistant/application/tooling/{governance,resilience}.py`
- `backend/src/intelligent_travel_assistant/application/services/{offline_planning,multicity_planning,provider_planning_jobs,provider_replanning}.py` 与必要 bootstrap 入口
- `backend/src/intelligent_travel_assistant/application/planning/{candidate_resolution,final_validation}.py` 和 DeepSeek typed request 直接入口
- 同 shape 后端 `data_stale`/retryable 投影在 Step 4 收口；不得留给前端推导

### Stack 4 / Step 8 批准修订：真实离线 application eval 集成

- `backend/evals/__init__.py`
- `backend/evals/f005/{__init__.py,application.py,models.py,runner.py,cases.json}`
- `backend/tests/evals/test_f005_agent_eval.py`
- 只允许从固定 synthetic case 驱动 legacy/V2/V3/F-003 各自真实离线 application 入口，并观测真实终态、来源、unknown/partial 和逻辑调用/HTTP attempt 预算；不得新增生产接口、公开 shape、Provider 调用或由 case 自报观测结果

### Stack 5 / Step 6–7：前端与交付验证

- `frontend/src/{tripPlanningApi,PlanningStage,ResultEvidence,TripPlanResult,MulticityTripPlanResult}.tsx/ts`
- 对应 frontend exact-shape、临时 SQLite、browser 和安全测试；API compatibility 作为相邻回归运行，不在该层新增 shape
- 交付与当前状态文档

受控相邻扩展自动覆盖同层直接导出/类型依赖、对应测试和 synthetic fixture、机械格式/import/type 修复，以及当前状态文档。不得借此新增 URI、Provider、Schema/migration、依赖、数据留存、外部服务、产品能力或跨越当前 Step/stack。

## Stacked PR 与规模阈值

1. `feat/f-005-resilience-domain-contracts`
2. `feat/f-005-provider-runtime`
3. `feat/f-005-application-agent-eval`
4. `feat/f-005-agent-eval-integration`
5. `feat/f-005-ui-delivery`

每层以直接前层为 base；前层 squash merge 后，后续层从最新 main clean-restack，只移植本层净提交，不 force-push 重写已审查历史。

- 单 Step 超过 5 个未预期生产/测试文件：停止；
- 单 stack 超过 30 个生产/测试文件或净新增 2500 行：停止并重新拆分；
- 任务累计超过 90 个生产/测试文件或净新增 8000 行：停止并重新切片。

## Step 地图

| Step | 唯一目标 | 状态 |
| --- | --- | --- |
| Step 0 | 复核最终 Git/PR/CI，激活任务，修正当前状态漂移并创建首层本地分支 | DONE |
| Step 1 | 冻结可实现的失败、时效、重试、Agent eval、API/UI、测试和交付设计 | DONE |
| Step 2 | TDD 实现纯领域 resilience/freshness/retry/诊断决策 | DONE |
| Step 3 | 实现显式 task-scoped attempt runtime 与 Amap/QWeather 安全错误输入 | DONE |
| Step 4 | 实现 legacy/V2/V3 application deadline、取消、预算和 fallback 治理 | DONE |
| Step 5 | 实现 proposal/repair 最小化、Provider 文本隔离和固定离线 Agent eval | DONE |
| Step 6 | 统一同 shape API 错误投影与前端失败/时效/恢复展示 | DONE |
| Step 7 | 完成临时 SQLite、loopback 浏览器和独立隐私安全审查 | DONE |
| Step 8 | 运行全量门禁并完成五层 stacked PR 与远程 CI | DONE |
| Step 9 | 依序合并、必要 clean-restack、main CI、归档和任务关闭 | TODO |

## 验收标准

- 所有批准失败类别具有稳定终态、retry 和用户恢复语义；
- 自动 retry 次数、jitter、Retry-After、attempt budget 和 deadline 可离线精确断言；
- terminal/cancel/deadline/budget 后新调用为 0，active peer 最终为 0；
- stale/unknown-validity、unknown 金额、来源和 partial/ready 不失真；
- legacy/V2/V3、F-003 replan、F-004A 多日和 F-004B1 多城市兼容门禁通过；
- schema 仍为 v2，无 migration v3；城际 Provider 调用仍为 0；
- 至少 48 个离线 eval case 达到批准阈值，结果不冒充真实 UAT；
- 临时 SQLite、desktop/390px loopback、network/console/accessibility 和独立隐私安全审查通过；
- 全量 format/lint/typecheck/test/build/docs/diff/secret/scope 门禁与五层 CI 通过后才能交付。

## 明确非目标

- 新 Provider 或 F-004B2 真实城际 Provider；
- 真实 Provider UAT 或新的 live 调用；
- Schema/migration、新依赖或 lockfile 修改；
- 生产高可用、分布式熔断、7×24 告警、公网 SLO；
- 登录、同步、云数据库、遥测平台、公网部署；
- 预订、支付、出票、库存或交易能力；
- 把 synthetic、MockTransport、临时 SQLite 或离线 eval 描述为真实 Provider/模型质量。

## 停止条件

- 需要改变已批准产品、API、Provider、数据留存、隐私、Schema、依赖、交付或真实调用边界；
- 需要新增公开 URI/JSON 键/顶层错误码、migration v3、新 Provider 或依赖；
- 需要读取秘密、`.env.local`、本地 Provider 配置或访问非 loopback/真实外部服务；
- 需要修改历史 evidence、归档任务卡或跨越当前 Step/stack；
- 需要创建真实数据库或保存被禁止的诊断内容；
- 达到任一文件/净新增行停止阈值；
- Git/CI/文档事实冲突无法解释。

## 下一批准入口

Step 8 已按用户批准的五层拓扑完成本地全量门禁、逐层独立 review、Draft stacked PR #27/#28/#29/#30/#31 和逐层远程 CI；五层首轮 runs `32450657207`、`32450661429`、`32450664838`、`32450668170`、`32450671589` 全部成功。Step 7 的 `npx` 偏差与 Step 8 Codex CLI 全局插件外连失败偏差均已由用户接受，且都不构成真实 Provider UAT。下一入口仅为用户单独批准 Step 9；此前不得 merge、clean-restack、运行最终 main CI、归档或进入后续任务。
