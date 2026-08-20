# 当前实施计划

当前无活动任务，因此没有正在执行的 Step。

## 当前状态

- 当前任务：无
- 最近完成：`F-004A 单城市 2–7 日计划扩展`，`Step 0–7` 全部 `DONE`
- 任务状态：`DELIVERED`；任务卡已归档
- 交付结果：PR #13、#16、#17 已按依赖顺序合并；完整功能 main 提交为 `583e9da34b0d45e84a65da620cbb5d5fa8330a3c`
- clean restack：PR #14/#15 分别由 #16/#17 替代并关闭，没有 force-push
- main CI：run `32359762190`，`PASS`
- 下一动作：由用户从 roadmap 选择候选任务并批准新任务卡；不得自动进入 F-004B、F-005 或 F-006

## Step 0 结果

- 核对项目规则、文档地图、roadmap、当前状态、F-001/F-002/F-003 归档及长期产品/架构/API/Agent/UI/测试/决策文档；
- 核对本地 `main`、HEAD、本地 `origin/main`、最近提交和干净工作区；三者提交一致；
- 保留 F-001 `PARTIAL`、Step 45M 真实 `FAIL`、Step 45T 真实 `PASS`、unknown 不为 0 和混合交通 fallback 仅离线证据；
- 确认 F-002/F-003 已归档、SQLite schema version 为 2，旧双日 API、请求指纹、计划数据和 replan 边界必须兼容；
- 核对现有双日硬编码：日期派生、offset 0/1、两窗口/两计划日、proposal/天气/最终校验、固定路线数组、餐饮乘 2、Repository 请求匹配和前端双日解析；
- 核对可复用能力：单城市地点与住宿锚点、逐日路线链、确定性 scheduler、预算/unknown、来源/freshness、五终态、Repository 乐观锁、SQLite typed JSON 和 F-003 scope 拒绝边界；
- 修正项目 AGENTS 的应用现状和默认 PR 规则、F-003 design 状态、D-011 状态、项目入口及过期 Git/CI 指针；
- 将已批准 F-004A 任务卡写入 current-task，roadmap 拆分 F-004A/F-004B 并只激活 F-004A；
- 冻结三层 stacked PR 和 squash 后 clean restack 规则；
- 未修改生产源码、测试、Schema、migration、Repository、API、Provider、前端、依赖、环境或数据库；
- 未读取 `.env.local` 或秘密，未调用真实 Provider，未访问非 loopback 网络，未创建分支或远程写入。

## Step 1 完成结果

Step 1 只冻结实现前设计，没有写生产代码：

1. 2–7 日领域日期、窗口、proposal、candidate、plan 和天气覆盖不变量；
2. legacy request/response/fingerprint 与 version 2 request/response 的严格判别和兼容；
3. 同 URI API、GET/retry/DELETE 与 3–7 日 replan scope 拒绝；
4. Repository typed union、SQLite schema v2 JSON 水合、幂等、乐观锁和旧应用 fail-closed；
5. 每日最多 2 项、住宿往返、餐饮/住宿公式、unknown/partial 和来源语义；
6. route cap `min(28, 4 × day_count)`、并发 2、DeepSeek 1+1 和 QWeather 7 日覆盖；
7. 前端结束日期、动态日窗口/日卡、可访问导航和 390px 设计；
8. 分层测试矩阵、三层 stack 的精确文件归属和停止阈值。

冻结结论：legacy DTO/指纹独立保留；V2 使用显式 request/plan/response format；同 URI 严格判别；Repository 方法和 schema v2 不变；3–7 日 replan 零写入拒绝；route/POI/天气/总期限按 current-task 公式有界；2/3/7 日 UI 和全层测试矩阵已写入长期文档。

## Step 2 唯一目标

以 TDD 只实现纯确定性多日基础：

1. 2–7 日日期范围和 offset/窗口全集；
2. 可变长度时间计划与每日住宿往返路线链；
3. proposal/candidate 的 N 日排程基础和每日最多 2 项；
4. 餐饮按日、住宿按夜、Decimal/unknown 预算；
5. N 日最终日期、时间、路线、天气、来源和预算校验；
6. legacy 双日领域行为和既有测试不变。

## Step 2 允许文件

- 生产：`backend/src/intelligent_travel_assistant/domain/trip_request.py`、`backend/src/intelligent_travel_assistant/domain/schedule.py`、`backend/src/intelligent_travel_assistant/domain/foundation.py`、`backend/src/intelligent_travel_assistant/domain/route_validation.py`、`backend/src/intelligent_travel_assistant/domain/budget.py`、`backend/src/intelligent_travel_assistant/domain/__init__.py`、`backend/src/intelligent_travel_assistant/application/ports/models.py`、`backend/src/intelligent_travel_assistant/application/planning/scheduling.py`、`backend/src/intelligent_travel_assistant/application/planning/final_validation.py`；
- 测试：`backend/tests/domain/test_trip_request_input.py`、`backend/tests/domain/test_schedule_time_rules.py`、`backend/tests/domain/test_foundation_models.py`、`backend/tests/domain/test_route_continuity.py`、`backend/tests/domain/test_budget_rules.py`、允许新增的 `backend/tests/domain/test_multiday_trip_request.py`、`backend/tests/domain/test_multiday_schedule.py`、`backend/tests/application/test_provider_ports.py`、`backend/tests/application/test_deterministic_scheduling.py`、`backend/tests/application/test_final_plan_validation.py`、允许新增的 `backend/tests/application/test_multiday_scheduling.py`、`backend/tests/application/test_multiday_final_validation.py`；
- current-task、implementation-plan、progress、evidence；确有当前事实变化时的 architecture、agent-domain-spec、testing-strategy。

## Step 2 禁止

- contracts、Repository、SQLite、Schema、migration、API、Provider adapter、组合根、前端、依赖、环境或数据库；
- `.env.local`、秘密、真实 Provider和非 loopback 网络；
- 分支、提交、push、PR、合并；
- 修改 legacy 公开 DTO/指纹，或进入 Step 3。

## Step 2 实现结果

- 新增独立 `MultiDayTripRequestInput`，保留 legacy `TripRequestInput` 的恰好双日错误语义；2/3/7 日和 D+1/D+5 边界通过，1/8 日、反向和非严格日期拒绝；
- `DailyAvailability` 基础 offset 扩为 0–6，legacy `TwoDayTimePlan` 继续要求 `{0,1}`；新增 `MultiDayTimePlan` 校验 2–7 日窗口全集、每日 1–2 项、日期、窗口和重叠；
- scheduler 对 2–7 日 proposal 的连续日期、连续 priority、每日 1–2 项和窗口全集 fail closed，并逐日生成住宿往返路线链，最多 3 段/日；
- 餐饮使用每人每日金额 × 人数 × 天数，住宿使用每晚金额 × (`day_count - 1`)；使用 minor units 避免 Decimal context 漂移，未知金额保持 `None`；
- final validation 按候选天数遍历 schedule 和 routes，天气继续要求精确日期全集；中间日窗口冲突和天气缺日均被测试锁定；
- RED 为三个缺失导出导致的收集失败；GREEN 后专项 136 项、后端全量 1065 项、format、Ruff、strict mypy、文档检查和 diff 检查通过；没有 contracts、Repository、SQLite、API、Provider adapter、前端、依赖、数据库或秘密访问。

状态说明：Step 2 实现、验证和五份状态文档同步均已完成。

## Step 3 实现结果

- 新增严格 tagged 的 V2 request/plan/response contracts；无版本字段继续唯一解析为 legacy，未知或模糊版本保持安全 422，legacy synthetic 指纹 golden 不变；
- Repository 方法集合不变，内存与 SQLite request/result/plan 扩为 typed union；schema 与 migration 仍只有 version 1/2，格式或 request/plan 配对损坏时 fail closed；
- 现有 trip-plan URI 支持 V2 创建、读取、幂等、删除和重启恢复；V2 草稿不误调 legacy executor；3–7 日 replan 在 reserve/service/write 前拒绝；
- V2 恰好两日 completed replan 保留 `response_version` 与 `plan_format_version`，legacy replan 投影不变；
- 统一门禁通过：121 个 Python/脚本文件 format、Ruff、strict mypy，后端 1073 项、前端 76 项、文档检查器 24 项、TypeScript 和 Vite build 全绿；未修改 schema、migration、Provider、前端、依赖、环境或数据库。

状态说明：Step 3 实现、验证和五份状态文档同步均已完成。

## Step 4 实现结果

- `PlanningContext` 为 V2 携带版本和完整日期；proposal parser、DeepSeek generation/repair 规则按 2–7 日动态校验，legacy 双日 payload 和规则不变；
- QWeather 仍只请求一次 7 日预报，按完整请求日期筛选；缺少任一日期返回 partial，不补拉、不补造；
- 离线编排按 day count 构造 POI 上限、日期窗口、逐日路线链、餐饮/住宿预算和 typed `TripPlanV2`；门票 unknown 保持 `None`；
- `ToolCallGovernor` 支持按任务注入不可变 policy 和总期限；路线预算为 `min(28,4D)`、并发 2，总期限保持冻结公式；组合根按请求创建 governor；
- 专项 403 项通过；统一离线门禁通过后端 1088 项、前端 76 项、文档检查器 24 项及 format、Ruff、strict mypy、TypeScript 和 Vite build；
- 未修改公开 API、Repository、Schema、migration、Provider 集合、前端、依赖、环境或数据库；未读取秘密、调用真实 Provider、创建分支或远程写入。

状态说明：Step 4 实现、验证和状态文档同步均已完成。

## Step 5 实现结果

- 表单新增显式结束日期和按日期动态维护的 2–7 日窗口；未编辑结束日期时保留 legacy 双日请求，显式编辑后提交严格 tagged V2 请求；
- 前端 parser 只凭显式 response/plan format 标签判别 V2，校验连续 2–7 日、每日活动/路线/天气和住宿锚点，不按数组长度猜版本；
- 结果页动态展示 2–7 日摘要、可换行且可键盘操作的日期导航和全部日卡；切换日期聚焦对应卡片，不触发 API 或写入；
- 3–7 日隐藏可执行 replan 并显示范围说明，V2 两日继续复用 F-003 面板；partial、天气缺失、freshness 和 unknown 金额继续显式呈现；
- 统一离线门禁通过后端 1088 项、前端 87 项、文档检查器 24 项及 Prettier、ESLint、TypeScript、Vite build、Ruff 和 strict mypy；没有新增依赖或修改后端、Schema、migration、Provider、数据库与公开 API。

状态说明：Step 5 实现、验证和状态文档同步均已完成；后续 Step 6 也已完成。

## Step 6 实现结果

- 纵向测试锁定 V2 2/3/7 日经现有 POST、executor、SQLite schema v2、重启、幂等和单计划删除；migration 仍只有 1/2；
- 首轮 RED 发现 API 仅调度精确 legacy 请求；经用户批准后最小调整 create/retry 的既有 executor 调度条件，并增加 V2 create/retry 回归；
- desktop legacy 两日、desktop V2 三日和 `390×844` V2 七日 partial 均经真实 Vite → FastAPI loopback 闭环；七日末日可达并取得焦点，unknown 金额不为 0，3–7 日无 replan，零横向溢出和零 console warning/error；
- 独立审查发现测试组合根可能误用既存或非临时 SQLite；已 fail closed 为系统临时目录内、启动前不存在的文件，并增加两项负向测试；
- 相关回归 48 项、Ruff、strict mypy 和 `git diff --check` 通过；未调用真实 Provider、读取秘密、访问非 loopback、创建真实业务数据库或执行 Git 远程动作。

状态说明：Step 6 实现、验证、独立审查和状态文档同步均已完成；Step 7 随后完成门禁、UAT、stacked 交付、main CI 和归档。

## Step 地图

| Step | 独立验证目标 | 状态 |
| --- | --- | --- |
| Step 0 | 事实核对、文档漂移修正、执行基线与文件清单 | DONE |
| Step 1 | 规格、兼容、Repository、调用预算、测试和 UI 设计冻结 | DONE |
| Step 2 | 可变日期/窗口、排程、预算和最终校验 | DONE |
| Step 3 | version 2 contracts、Repository/API 兼容和 SQLite 重启 | DONE |
| Step 4 | DeepSeek/QWeather/路线多日编排和失败语义 | DONE |
| Step 5 | 前端多日输入、展示和 replan 范围 UI | DONE |
| Step 6 | 临时 SQLite 纵向、浏览器 QA 和独立审查 | DONE |
| Step 7 | 全量门禁、UAT、stacked PR、CI、合并和归档 | DONE |

## 阶段文件和交付规则

各 Step 的核心生产和测试清单以 [current-task.md](./current-task.md) 为执行基线。一次 Step 批准同时覆盖为满足冻结行为而必需的同层直接依赖、对应测试/fixture、机械门禁修复，以及五份状态文档；这些相邻扩展须先说明、后在 evidence 留痕，不再逐文件请求批准。改变产品/API 语义、Schema/migration、依赖、数据/隐私边界、外部调用、跨 Step/stack 或超过 5 个未预期生产/测试文件时，才停止并进行一次合并确认。三层 stack 规则、clean restack 和禁止 force-push 保持不变。

## 停止条件

- 旧双日 API、响应、请求指纹、已保存数据或 replan 兼容无法保持；
- 需要 migration v3、新依赖、新 Provider、真实调用或秘密；
- route 预算公式或 QWeather 7 日覆盖不能按批准 partial 边界安全实现；
- 需要多城市、跨夜、多住宿、城际交通或 3–7 日局部重规划；
- 受控相邻范围越过冻结语义、明确禁止项、当前 Step/stack 或 5 个未预期生产/测试文件；任一 stack 超过 35 个生产/测试文件或净新增 3000 行；
- 文档、代码、Schema、Git 或历史证据无法一致解释。

## 权威入口

- 任务卡：[current-task.md](./current-task.md)
- 进度：[progress.md](./progress.md)
- 路线图：[roadmap.md](./roadmap.md)
- 证据：[evidence.md](./evidence.md)
