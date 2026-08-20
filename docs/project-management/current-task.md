# 当前任务

## 任务元数据

- 任务：`F-004A 单城市 2–7 日计划扩展`
- 等级：`L`
- 状态：`APPROVED / ACTIVE`
- 当前 Step：`Step 7 - 全量门禁、UAT、stacked PR、CI、合并和归档`，状态 `ACTIVE`；本地门禁与 synthetic UAT 已通过，正在执行三层 stacked 交付
- Step 0：`DONE`；只完成事实核对、文档漂移修正、执行基线和阶段化允许文件清单
- Step 1：`DONE`；只冻结领域、DTO/API、Repository/schema v2、Provider 治理、测试和 UI 设计
- Step 2：`DONE`；以 TDD 完成可变日期、窗口、排程、预算和最终校验，并通过后端全量门禁
- Step 3：`DONE`；以 TDD 完成 version 2 contracts、Repository/API 兼容和 schema v2 SQLite 重启恢复
- Step 4：`DONE`；以 TDD 完成 DeepSeek/QWeather/路线多日编排、动态调用治理和失败语义
- Step 5：`DONE`；完成前端多日输入、严格 V2 解析、动态日卡和 replan 范围 UI
- Step 6：`DONE`；完成临时 SQLite 纵向、desktop/390px loopback synthetic 浏览器 QA 和独立审查
- 分支与交付：三层 stacked PR；Step 7 已获用户明确授权创建分支、提交、推送、创建 PR、验证 CI、依序合并和归档

## 用户目标与工程价值

用户可以在一个中国大陆城市内生成连续 2–7 日、每日最多 2 项活动的结构化计划，并继续看到逐日天气、住宿往返路线、预算、unknown、来源、freshness、冲突和 partial。工程上把散落的双日常量收敛为显式行程跨度，同时证明现有确定性排程、Repository、SQLite typed JSON、Provider 边界和前端严格解析可扩展而不破坏已交付双日能力。

## 当前事实、缺口和前置条件

- B-000、F-001、F-002、F-003 已交付归档；F-001 产品状态仍为 `PARTIAL`；
- Step 45M 历史真实 UAT `FAIL`、Step 45T 真实 UAT `PASS` 均保留；门票等非关键费用保持 `unknown`，混合交通 fallback 只有离线证据；
- 当前应用可本地运行，支持单城市双日计划、SQLite 持久化、版本追加和 F-003 局部重规划；
- SQLite migration 序列为 version 1/2，当前 schema version 为 2；现有计划与请求保存在 typed JSON 中；
- 当前公开请求只含 `start_date`，后端派生 `end_date = start_date + 1 day`；窗口、proposal、计划、天气筛选、校验、预算、Repository 匹配和 UI 均存在双日假设；
- F-004A 任务卡及产品、日期、数据、API、兼容、Repository、UI、隐私、测试和 stacked PR 决策已获用户批准；Step 0–6 已完成，Step 7 已获批准并完成本地门禁与 synthetic UAT，远程交付和归档尚在执行。

## 产品范围

### 范围内

- 一个中国大陆城市、连续 2–7 日；日期使用目的地本地日历语义；
- 每日 1–2 项活动、每日独立可用窗口、同一住宿锚点、住宿往返路线链；
- 现有步行/公共交通市内路线；不新增交通模式；
- 计划、来源、预算、天气、warning、uncertainty 和五种终态的多日表达；
- 餐饮按“每人每日 × 人数 × 天数”，住宿按“一晚金额 × (天数 - 1)”；
- 旧双日请求/API/指纹/数据/replan 兼容；新请求和响应采用严格、可辨识的 version 2 typed 变体；
- 本地 SQLite schema v2 的多日 typed JSON 往返、重启恢复、幂等、并发和删除回归；
- React 输入结束日期、2–7 日校验和动态逐日展示；桌面及 `390×844` 验证。

### 非目标

- 多城市、同日跨城、跨夜活动、多住宿锚点、铁路/航班/长途客运/自驾 Provider；
- 实时票价、库存、预订、支付、出票或价格承诺；
- 对 3–7 日计划执行 F-003 局部重规划、版本比较/恢复、历史列表或清空全部数据；
- 新增 Provider、登录、同步、多用户、云数据库、公网部署、复杂地图、图片或 PDF；
- migration v3、ORM/Alembic 或依赖升级；
- 真实 Provider 调用或 live UAT；此类验证必须另行批准调用次数、费用和停止条件。

## 目标用户和核心场景

- 计划 2–7 日单城市短途旅行的个人、家庭或小型同行群体；
- 输入城市、开始/结束日期、逐日窗口、人数、总预算、偏好、交通和住宿要求；
- 读取逐日活动、路线、天气、预算与来源；数据缺失时得到明确 partial/unknown，而非假 ready；
- 关闭并重启应用后读取同一已提交计划；旧双日任务继续按原协议读取和重试；
- 对 3–7 日计划发起局部重规划时，在 Provider 调用和写入前得到稳定 `replan_scope_not_supported`。

## 输入、输出和可观察状态变化

- 旧输入：原 `TripPlanRequest` 保持字段、严格性、日期派生和 canonical fingerprint 字节不变；
- 新输入：严格 version 2 request，显式 `request_version="2"`、`start_date`、`end_date` 和与跨度一致的 2–7 个唯一 `day_windows`；其余字段沿用已批准类型和隐私边界；
- 输出：旧 job 继续返回原 `TripPlanResponse`；version 2 job 返回可辨识的严格多日响应变体，计划 `days` 与闭区间日期逐日一一对应；
- 任务状态仍使用现有 11 个 `PlanningStatus` 和 ready/partial/conflict/needs_input/failed 终态，不新增状态；
- Repository 的 attempt、trace、version、expected_version、幂等和删除语义不变；
- 多日计划成功提交仍追加 plan version；unknown 金额保持 `null`，partial 不提升为 ready。

## 日期、窗口、计划和预算模型方向

- 引入显式 `day_count = (end_date - start_date).days + 1`，只允许 2–7；
- 用可变长度时间计划替代生产路径中的 `TwoDayTimePlan`，窗口 offset 必须精确为 `0..day_count-1` 且唯一；旧类型可作为兼容层或迁移回归保留；
- proposal、candidate、plan days 和天气日期必须精确覆盖请求日期，不允许缺日、重复、越界或重排；
- `PlanStructure` 继续要求全部地点属于同一 `city_adcode`，每天引用同一住宿锚点；
- 每日最多 2 项活动；确定性 scheduler 继续负责分钟级时间、路线缓冲、optional 容量降级和最终校验；
- 餐饮金额为 `daily × travelers × day_count`；住宿已知金额为 `one_night × (day_count - 1)`；门票、城际交通等无可靠金额时保持 unknown；
- 天气缺日、超出可用预报或 freshness 无法确认时，只要计划仍可用则进入 partial 并保留 warning/uncertainty；不得补造天气。

## API 与兼容边界

- 保持现有 `/api/trip-plans`、`/api/trip-plans/{job_id}`、retry、DELETE 和三个 replan URI；不新增历史列表 API；
- POST 在同一路径接受旧严格请求或带 `request_version="2"` 的新严格变体；额外字段和模糊形状 fail closed；
- GET/retry 根据已持久化请求类型返回对应严格响应；旧响应 JSON 形状不增加字段；
- 若 Step 1 无法证明同 URI 严格判别且不破坏 OpenAPI/旧客户端，立即停止并重新决定 `/api/v2`，不得自行新增端点；
- 旧双日指纹算法和结果匹配规则保持逐字节兼容；version 2 使用包含版本、结束日期和全部窗口的独立 canonical fingerprint；
- 旧计划继续可读、可 retry、可按 F-003 规则 replan；`day_count > 2` 的 replan 在分析/Provider/写入前拒绝且不创建 decision 或 plan version。

## Repository、SQLite 和迁移边界

- `PlanningJobRepository` 方法集合不变；允许其 typed request/result 类型扩展为显式兼容联合，不允许 SQLite 类型泄漏到 port；
- 内存与 SQLite adapter 必须对旧/新请求具有一致的 get_or_create、指纹、expected_version、retry、record_result 和 delete 语义；
- plan/source/version 仍在既有事务中原子写入；多日 JSON 在写入前和水合后均通过对应 typed model；
- schema v2 已能保存版本化 typed JSON 和来源链接，F-004A 默认无 migration v3，不重写旧记录；
- 若实现需要新列、索引、关系实体或查询能力，立即停止并提交 migration v3 决策，不得隐式改 schema；
- 新代码回滚到旧应用时，旧应用可对 version 2 记录 fail closed，但不得损坏、删除或错误投影数据；恢复服务应重新部署支持 version 2 的代码。

## Provider、调用预算和失败语义

- 不新增 Provider；高德仍仅用于单城市解析/POI/步行/公交，和风用于日预报/当前预警，DeepSeek 只输出 allowlist proposal；
- route 并发保持 2；每任务路线调用上限冻结为 `min(28, 4 × day_count)`，任何额外调用需求必须在 Step 1 停止复核；
- DeepSeek generation 1、repair 1 的上限不增加；Prompt/Schema 必须按 2–7 日动态生成并继续拒绝最终时间、路线、provider 和终态字段；
- 和风请求继续为 7 日预报，解析器只映射请求日期；超出可用覆盖或缺日按 partial 处理，不做第二 Provider 或虚构数据；
- provider auth/schema/timeout/rate/server/unknown 的稳定分类、deadline、取消清理和隐私边界保持不变；
- 默认测试只用 fake、MockTransport、synthetic fixture 和临时 SQLite，阻断非 loopback 网络。

## 数据与隐私边界

- 继续只保存 allowlist 结构化用户请求、转换后的必要地点/路线/预算/天气字段、来源元数据、获取时间、validity、freshness、attribution、安全链接和 typed acceptance 摘要；
- 不保存 Key、Token、JWT、私钥、Cookie、Authorization、完整 Prompt、provider 原始响应、原始错误 body 或完整日志；
- 不读取 `.env.local`；本任务默认不访问真实 Provider；
- 地点、路线和预算按已批准本地 SQLite 边界保存，不扩大为云同步、账号数据或公网服务；
- 保留单计划 DELETE、30 天 expires_at 和启动有界清理；不新增清空全部数据。

## UI 方向

- 表单增加结束日期并显示 2–7 日范围、连续性和逐日窗口错误；旧双日默认仍可快速完成；
- 结果页动态渲染 N 日，不使用固定 `days[0]/days[1]`、双日标签或固定两项窗口；
- 提供可键盘到达的日期导航/标题结构，不能只靠颜色或横向滚动；
- partial、unknown、来源 freshness、冲突和 retry 文案继续与终态一致；
- 3–7 日结果不展示可执行 replan 控件，或明确显示当前范围不支持，不能发起隐藏写入；
- Step 5 前必须在 Step 1 冻结桌面和 `390×844` 的信息层级与视觉验收。

## 测试和验收矩阵

- 领域：2/3/7 日边界、1/8 日拒绝、连续日期、窗口全集、跨夜拒绝、每日 1–2 项、住宿往返链、固定输入确定性；
- 预算：餐饮按天数、住宿按夜数、Decimal round-trip、unknown 仍为 `null`、partial 不为 ready；
- proposal/Provider：2–7 日严格 Schema、日期绑定、缺日/重复/越界、天气部分覆盖、route cap/并发/deadline/fallback；
- Repository：旧指纹 golden、version 2 指纹、幂等创建、异请求冲突、expected_version、retry、SQLite 重启、多日 JSON/来源 round-trip、删除；
- API：旧 request/response golden 不变、新 variant 严格判别、GET/retry/DELETE、额外字段拒绝、3–7 日 replan 零调用/零写入拒绝；
- 前端：结束日期、动态窗口、2/3/7 日、严格 parser、loading/五终态、unknown/partial、replan 范围、桌面/390px、键盘和焦点；
- 隔离：临时 SQLite 相互隔离，不创建真实业务数据库，不读取 `.env.local`，非 loopback 和真实 Provider 调用为 0；
- 回归：F-001 五终态、F-002 持久化/清理/删除、F-003 双日 replan、schema version 2 和历史证据不变。

## 验收标准

- 旧双日 request/response/fingerprint golden 和既有计划读取全部通过；
- 2、3、7 日 version 2 计划可确定性生成、持久化、重启读取和删除；1 日、8 日、日期/窗口不一致严格拒绝；
- 每日最多 2 项、日期/时间/住宿往返/路线/预算/来源校验覆盖全部天；
- route 调用不超过冻结公式且并发不超过 2；取消和 terminal 后无遗留调用；
- 天气缺失、freshness unknown、非关键费用 unknown 形成真实 partial/uncertainty，不出现零金额或假 ready；
- 3–7 日 replan 返回稳定范围错误，Provider 调用、decision、plan version 和 current snapshot 写入均为 0；
- SQLite 仍为 schema version 2，无 migration 文件或真实业务数据库变化；
- 前端完成 2/3/7 日输入与展示，桌面和 390px 无横向溢出，关键流程可键盘完成；
- 全量 format、lint、typecheck、test、build、文档、diff、隐私和 stacked PR CI 门禁通过。

## Step 1 冻结结果

- 领域：legacy 类型独立保留；V2 使用 `MultiDayTripRequestInput`/`MultiDayTimePlan`，2–7 日、offset 全集、每日 1–2 项、同一住宿锚点和按日期遍历均已冻结；
- DTO：`TripPlanRequestV2` 必须有 `request_version="2"`，`TripPlanV2`/`TripPlanResponseV2` 分别有 plan/response format 标识；legacy JSON 不增加字段；
- API：现有 URI 使用“缺 version=legacy、精确 `2`=V2”的 callable discriminator/tagged union；未知或模糊版本 422，不自行新增 `/api/v2`；
- 指纹：legacy 算法逐字节不变，synthetic golden 为 `f8e8a85d192745f703d968695945c2fa4200f224d4e8ae9162a69abd57bf7edd`；V2 独立包含版本、结束日期和全部窗口；
- Repository：方法集合不变，request/result/plan 扩为显式 typed union；SQLite 按 request version 水合，JSON/format 不一致 fail closed；schema 仍为 version 2，无 migration v3；
- replan：legacy 双日不变，V2 两日可 typed 映射复用 F-003；3–7 日在 reserve/decision/executor/Provider 前返回既有 `replan_scope_not_supported`，零写入；
- Provider：resolve 1、POI 3、forecast 1、alert 1、generation 1、repair 1；route 并发 2、上限 `min(28,4D)`；legacy/两日 90 秒，V2 多日总期限 `min(180,90+18×(D-2))`；单次 timeout 不变；
- POI 候选上限 `min(20,max(6,2D+2))`；QWeather 仍单次 7 日预报，缺日不补拉并按 partial；
- UI：显式结束日期、动态窗口和日卡、可换行/可键盘日导航、2/3/7 日及 390px 门禁；3–7 日隐藏可执行 replan 并显示范围说明；
- 测试：领域、contracts、legacy golden、Repository/SQLite、API、replan 零写入、Provider 治理、五终态、前端和浏览器矩阵已冻结；默认完全离线。

## Step 地图

| Step | 独立验证目标 | 状态 |
| --- | --- | --- |
| Step 0 | 事实核对、文档漂移修正、执行基线与阶段化文件清单 | DONE |
| Step 1 | 冻结领域/DTO/API 兼容、调用预算、Repository、UI 和测试矩阵 | DONE |
| Step 2 | TDD 实现可变日期/窗口、排程、预算和最终校验 | DONE |
| Step 3 | 实现 version 2 contracts、Repository/API 兼容和 SQLite 重启恢复 | DONE |
| Step 4 | 实现 DeepSeek/QWeather/路线多日编排、治理和失败语义 | DONE |
| Step 5 | 实现前端多日输入、动态展示和 replan 范围 UI | DONE |
| Step 6 | 临时 SQLite 纵向、synthetic 浏览器 QA 和独立审查 | DONE |
| Step 7 | 全量门禁、UAT、stacked PR、CI、合并和归档 | TODO |

## 阶段化允许文件清单

下列清单是每个 Step 的预期核心范围，不再作为“遗漏一个相邻文件即停止”的绝对白名单。用户批准某个 Step 后，同时授权以下受控相邻修改，无需逐文件再次确认：

- 为实现该 Step 已冻结行为而直接必需的同层 contract、导出、组合根或适配代码；不得借此新增产品能力、公开端点、Provider、Schema、migration 或依赖；
- 与已批准生产改动一一对应的测试、既有 synthetic fixture，以及门禁直接暴露的机械格式、import 和类型标注修复；
- `docs/README.md`、current-task、implementation-plan、progress、evidence 的阶段状态和证据收口；长期文档仅同步本 Step 已产生的事实，不借文档扩大范围；
- 新增相邻文件前必须先在执行更新中说明路径、必要性和所属层，最终在 evidence 中列明；满足上述条件即可继续，不要求用户逐项追加授权。

仍须停止并取得一次新的合并确认：改变已冻结产品/API 语义、Schema/migration、依赖、数据或隐私边界；读取秘密、真实 Provider/非 loopback、真实数据库、Git 远程写入；跨越当前 Step/stack；或未预期扩展超过 5 个生产/测试文件。明确列为禁止的文件和行为不因受控相邻规则而自动解禁。

### Step 0

- `AGENTS.md`；
- `docs/README.md`、`docs/product-brief.md`；
- `docs/project-management/roadmap.md`、`current-task.md`、`implementation-plan.md`、`progress.md`、`evidence.md`；
- `docs/architecture.md`、`docs/api-contract.md`、`docs/agent-domain-spec.md`、`docs/design-spec.md`、`docs/testing-strategy.md`、`docs/decisions.md`，仅同步已批准边界或明确漂移。

### Step 1

- `docs/README.md`、`docs/product-brief.md`；
- 五份项目管理文档：`docs/project-management/roadmap.md`、`current-task.md`、`implementation-plan.md`、`progress.md`、`evidence.md`；
- `docs/architecture.md`、`docs/api-contract.md`、`docs/agent-domain-spec.md`、`docs/design-spec.md`、`docs/testing-strategy.md`、`docs/decisions.md`。

### Step 2

- 生产：`backend/src/intelligent_travel_assistant/domain/trip_request.py`、`backend/src/intelligent_travel_assistant/domain/schedule.py`、`backend/src/intelligent_travel_assistant/domain/foundation.py`、`backend/src/intelligent_travel_assistant/domain/route_validation.py`、`backend/src/intelligent_travel_assistant/domain/budget.py`、`backend/src/intelligent_travel_assistant/domain/__init__.py`、`backend/src/intelligent_travel_assistant/application/ports/models.py`、`backend/src/intelligent_travel_assistant/application/planning/scheduling.py`、`backend/src/intelligent_travel_assistant/application/planning/final_validation.py`；
- 测试：`backend/tests/domain/test_trip_request_input.py`、`backend/tests/domain/test_schedule_time_rules.py`、`backend/tests/domain/test_foundation_models.py`、`backend/tests/domain/test_route_continuity.py`、`backend/tests/domain/test_budget_rules.py`、允许新增的 `backend/tests/domain/test_multiday_trip_request.py`、`backend/tests/domain/test_multiday_schedule.py`、`backend/tests/application/test_provider_ports.py`、`backend/tests/application/test_deterministic_scheduling.py`、`backend/tests/application/test_final_plan_validation.py`、允许新增的 `backend/tests/application/test_multiday_scheduling.py`、`backend/tests/application/test_multiday_final_validation.py`；
- 对应项目管理文档，以及确有事实变化时的 architecture/agent-domain-spec/testing-strategy。

### Step 3

- 生产：`backend/src/intelligent_travel_assistant/contracts/trip_planning.py`、`contracts/__init__.py`、`application/repositories/models.py`、`application/repositories/ports.py`、`application/repositories/__init__.py`、`adapters/repositories/memory.py`、`adapters/persistence/repository.py`、`api/trip_plans.py`、`api/replans.py`、`app.py`；
- 测试：`backend/tests/test_trip_planning_contracts.py`、允许新增的 `backend/tests/contracts/test_multiday_trip_planning_contracts.py`、`backend/tests/application/test_planning_job_repository.py`、允许新增的 `test_multiday_planning_job_repository.py`、`backend/tests/adapters/persistence/test_repository.py`、允许新增的 `test_multiday_repository.py`、`backend/tests/api/test_trip_plans_api.py`、`test_trip_plan_terminal_results.py`、`test_sqlite_trip_plans_api.py`、`test_replans_api.py`、`test_sqlite_replans_api.py`、允许新增的 `test_multiday_trip_plans_api.py`、`test_sqlite_multiday_trip_plans_api.py`；
- 允许新增 fixture：`backend/tests/fixtures/synthetic_hangzhou_multiday_request_v2.json`、`synthetic_hangzhou_multiday_ready_v2.json`、`synthetic_hangzhou_multiday_partial_v2.json`；旧 fixture 不得改写为 V2；
- 禁止 `backend/src/intelligent_travel_assistant/adapters/persistence/schema.py`、`migrations.py` 和 `backend/tests/adapters/persistence/test_migrations.py`，除非停止并获 migration v3 新批准。

### Step 4

- 生产：`backend/src/intelligent_travel_assistant/application/ports/models.py`、`providers.py`、`application/planning/candidate_resolution.py`、`scheduling.py`、`final_validation.py`、`application/services/offline_planning.py`、`provider_planning_jobs.py`、`application/tooling/governance.py`、`tooling/__init__.py`、`adapters/providers/deepseek.py`、`qweather.py`、`adapters/fakes/scripted.py`；
- 测试：`backend/tests/application/test_plan_proposal_resolution.py`、`test_deepseek_candidate_resolution.py`、`test_deterministic_scheduling.py`、`test_final_plan_validation.py`、`test_offline_planning_orchestrator.py`、`test_provider_planning_job_executor.py`、`test_tool_call_governance.py`、允许新增的 `test_multiday_provider_planning_job_executor.py`，以及 `backend/tests/adapters/test_deepseek_adapter.py`、`test_qweather_adapter.py`、`test_provider_failure_matrix.py`、允许新增的 `test_multiday_deepseek_adapter.py`、`test_multiday_qweather_adapter.py`；
- 不允许新增 Provider、依赖、环境或真实调用。

### Step 5

- `frontend/src/App.tsx`、`App.test.tsx`、`tripRequest.ts`、`TripRequestForm.tsx`、`TripRequestForm.test.tsx`、`tripPlanningApi.ts`、`tripPlanningApi.test.ts`、`tripPlanModels.ts`、`TripPlanResult.tsx`、`TripPlanResult.test.tsx`、`PlanningStage.tsx`、`PlanningStage.test.tsx`、`useTripPlanningJob.ts`、`ReplanPanel.tsx`、`ReplanPanel.test.tsx`、`styles.css`、`test/tripPlanningFixtures.ts`；允许新增 `frontend/src/TripDayNavigation.tsx` 和 `TripDayNavigation.test.tsx`；
- 对应项目管理文档和已批准 UI 事实的 `docs/design-spec.md`/`testing-strategy.md`。

### Step 6

- `backend/tests/browser_support.py`、允许新增的 `backend/tests/browser_multiday_support.py`、`backend/tests/api/test_sqlite_multiday_trip_plans_api.py` 和上述三个 V2 fixture；
- 前端既有测试文件只允许修正验收 fixture 或增加浏览器可观察断言，不修改生产 UI；
- 项目管理文档与 `docs/testing-strategy.md`；浏览器临时产物必须位于 Git 忽略路径。

### Step 7

- 全量验证、审查、任务项目管理文档、长期文档、`docs/archive/task-cards/F-004A-single-city-multiday-plan.md`；
- 生产修复不得夹带进入交付 Step；发现阻塞先停止，另获最小修复授权；
- Git/远程动作只在 Step 7 明确授权后按三层 stack 执行。

## 精确禁止文件与行为

- 所有 Step 默认禁止 `backend/pyproject.toml`、`backend/uv.lock`、根 `package.json`、`pnpm-lock.yaml`、`.env.example`、`.env.local`、`.github/**` 和数据库文件；
- 禁止修改 `adapters/persistence/schema.py`、`migrations.py` 或创建 migration v3；
- 禁止读取/输出秘密、调用真实 Provider、访问非 loopback 网络、创建真实业务数据库；
- 禁止多城市、跨城/跨夜、局部重规划扩域、历史/恢复、登录/同步/公网；
- 禁止把 unknown 转为 0、partial 投影为 ready，或改写 F-001/F-002/F-003 历史证据；
- Step 0–1 均禁止且实际未发生任何源码、测试、前端、依赖、数据库、分支、提交、push、PR 或合并。

## Stacked PR 与 clean restack

- Stack 1：`feat/f-004a-multiday-domain-contracts`，只含领域、typed contracts 及其测试；目标 `main`；
- Stack 2：`feat/f-004a-multiday-application`，只含 Repository/API/Provider 编排及其测试；开发时基于 stack 1；
- Stack 3：`feat/f-004a-multiday-ui-delivery`，只含 UI、纵向验收和交付文档；开发时基于 stack 2；
- 每层独立 review、CI、验收和合并；前层未通过不得合并后层；
- GitHub squash 合并前层后，从最新 `main` 创建后层干净分支，只 cherry-pick/重建该层自身提交；关闭被 supersede 的旧 PR；不 force-push 重写已审查历史；
- 任一 stack 超过 35 个生产/测试文件或净新增 3000 行、出现跨层循环依赖或无法独立验证时停止并重新拆分。

## 文档更新契约

- Step 状态：current-task、implementation-plan、progress、docs/README 同步；
- 产品范围：product-brief、roadmap；架构/Repository/schema：architecture、decisions；
- DTO/API：api-contract；Agent/Provider：agent-domain-spec；UI：design-spec；测试/证据：testing-strategy、evidence；
- 任务交付后完整卡片进入 archive，current-task 重置；历史验收不得改写。

## 风险、回滚和停止条件

- 兼容风险：旧请求、响应或指纹 golden 改变即停止；
- 数据风险：需要 migration v3、旧记录重写或旧应用可能损坏新数据即停止；
- 调用风险：路线预算公式不足、天气覆盖不能安全 partial、Provider 次数需要增加即停止；
- 产品风险：需要多城市、跨夜、多住宿、城际 Provider 或 3–7 日 replan 即停止；
- 隐私风险：需要保存原始 Provider/Prompt/秘密或访问真实服务即停止；
- 范围风险：受控相邻扩展若改变冻结语义、跨 Step/stack、触及明确禁止项、超过 5 个未预期生产/测试文件，或单 stack 超阈值时停止；普通直接依赖、对应测试和状态收口不再触发逐文件授权；
- 回滚优先按单 stack revert；SQLite schema 不变，无数据库 down migration；旧应用读取 version 2 记录只允许 fail closed。

## 完成定义

- Step 0–7 全部经用户逐步批准并完成；
- 2/3/7 日正向与 1/8 日负向、旧双日兼容、SQLite 重启、Provider 治理、前端和隐私矩阵全部通过；
- schema 仍为 version 2，unknown/partial 和 F-001 历史事实不变；
- 三层 stacked PR 依序通过独立 review、CI、合并后 main CI；
- 文档与代码事实一致，任务卡归档，roadmap/progress/current-task 收口。

## Step 0–6 证据与下一入口

- 本地 Git：`main`、HEAD、本地 `origin/main` 均为 `e17cf4fe65407d98389a2713622adf398acc6f1b`；进入 Step 0 时工作区干净；
- 最新远程 CI 证据沿用任务启动前只读核对的 main run `31939795749`=`PASS`；本 Step 因禁止非 loopback 网络未重新查询远端；
- 已核对 schema migration 仅 version 1/2，以及当前双日代码和测试事实；
- 本 Step 未修改源码、测试、数据库、依赖、环境或前端，未读取秘密、调用 Provider、创建分支或远程写入；
- Step 1 仅修改获批文档，未修改源码、测试、Schema、migration、Repository、API、Provider、前端、依赖、环境或数据库；
- Step 2 已按 TDD 取得缺少多日类型/预算函数的预期 RED，随后以最小实现完成 2–7 日请求、offset/窗口全集、每日 1–2 项、N 日排程、餐饮/住宿公式及 N 日 schedule/route/weather 终检；
- legacy `TripRequestInput`/`TwoDayTimePlan`、公开 contracts、Repository、SQLite/schema/migration、API、Provider adapter、前端、依赖和环境均未修改；unknown 保持 `None`，未转为 0；
- 相关专项 136 项、后端全量 1065 项、format、Ruff 和 strict mypy 已通过；文档检查与 `git diff --check` 也已通过；
- Step 2 状态已在 README、任务卡、实施计划、进度和证据文档中同步收口；
- Step 3 已实现严格 legacy/V2 tagged contracts、typed Repository 联合、同 URI API、schema v2 SQLite 重启恢复和 3–7 日 replan 零写入拒绝；V2 两日 completed replan 保留 response/plan 两层版本标签；
- Step 3 统一门禁通过：121 个 Python/脚本文件 format、Ruff 和 strict mypy，后端 1073 项、前端 76 项、文档检查器 24 项及 TypeScript/Vite build 全绿；
- Step 4 已按任务构造不可变 Provider policy：legacy/两日保持 90 秒和 8 次路线预算，V2 3–7 日使用冻结期限与 `min(28,4D)` 路线预算，并发保持 2；
- DeepSeek V2 上下文和规则按完整日期动态生成；QWeather 保持单次 7 日请求，缺日只形成 partial；执行器按请求构造 N 日计划、预算、来源和 unknown；
- Step 4 专项 403 项、统一门禁后端 1088 项、前端 76 项、文档检查器 24 项及全部静态检查和 build 通过；`bootstrap.py` 作为已披露的受控相邻组合根修改，未改变 API、Schema、migration、依赖或隐私边界；
- Step 5 已实现显式结束日期、2–7 日动态窗口、legacy/V2 请求兼容、严格 tagged V2 响应解析、可换行日期导航和动态日卡；3–7 日隐藏可执行 replan，V2 两日保留既有 replan；
- 组件证据覆盖 2/3/7 日、1/8 日拒绝、用户结束日期保留、首错焦点、partial/unknown、V2 双日 replan 和多日范围说明；统一门禁通过后端 1088 项、前端 87 项、文档检查器 24 项及全部静态检查和 build；
- 本 Step 未修改后端、API、Repository、Schema、migration、Provider、依赖、环境或数据库，未读取秘密、访问 Provider/非 loopback、创建分支或远程写入；
- Step 6 以临时 SQLite 完成 V2 2/3/7 日 API → executor → Repository → schema v2 → 重启 → 幂等 → 删除纵向；发现并最小修复 V2 create/retry 未调度 executor 的阻塞，公开 URI/DTO、Schema、migration、Repository 和 Provider 均未变化；
- 真实本机 loopback 浏览器覆盖桌面 legacy 两日、桌面 V2 三日和 `390×844` V2 七日 partial；末日可达并聚焦、3–7 日 replan 隐藏、unknown 门票不是 0、无横向溢出、无 console warning/error，动态请求仅到 `127.0.0.1`；
- 独立审查发现 synthetic SQLite 路径保护不足；已强制路径位于系统临时目录且启动前不存在，并以拒绝项目路径和既存临时文件的负向测试收口；相关回归 48 项及 Ruff、strict mypy、diff 检查通过；
- 唯一下一步：按已批准的 Step 7 完成三层 stacked PR、远程 CI、依序合并、最终 main CI 和归档；只有真正越过冻结产品/API、Schema/migration、依赖、数据/隐私或外部访问边界时停止。
