# 当前任务

## 任务元数据

- 任务 ID：`F-002`
- 名称：计划持久化、来源与版本
- 等级：`L`
- 状态：`ACTIVE`
- 任务卡状态：`APPROVED`
- 当前 Step：`Step 6 - 完成全量门禁、文档收口和交付审查`（PR #6 OPEN，实施提交 CI 通过）
- Step 0–5 状态：已完成；Step 5 的删除、清理、acceptance、隐私测试和状态收口均已完成；Step 6 状态：TODO
- 下一 Step：`Step 6 - 完成全量门禁、文档收口和交付审查`
- 基线分支：`main`
- 当前功能分支：`feat/f-002-local-plan-persistence`
- 建议功能分支：`feat/f-002-local-plan-persistence`
- PR 目标：一个功能分支、一个 PR；仅交付本地 SQLite 持久化基础和恢复能力

## 用户目标和工程价值

用户在本地完成单城市双日旅行规划后，关闭并重新启动应用仍能恢复计划、状态、来源、freshness、unknown 费用和可重试信息。

F-002 为 F-003 局部重规划提供稳定的计划版本、来源和 trace 基线。

## F-001 依赖与必须保留的历史事实

- F-001 已交付并归档，产品验收状态保持 `PARTIAL`；
- Step 45M 历史真实 UAT 为 `FAIL`，不得被后续证据覆盖；
- Step 45T 真实 UAT 为 `PASS`，只证明完整双日 `partial` 计划；
- 门票等非关键费用保持 `unknown`，不得按 0 处理；
- unknown 费用的金额必须为 `null`，预算可判定性必须保持真实；
- 混合交通 fallback 只有离线证据，不得写成真实 Provider 质量已验证；
- F-001 完整归档任务卡位于 `docs/archive/task-cards/F-001-single-city-two-day-plan.md`；
- 当前没有可迁移的旧 SQLite 数据，F-001 只有进程内临时状态。

## 范围

- 本地 SQLite 数据库；
- Repository 隔离数据库实现；
- Schema 版本和项目内迁移 runner；
- 任务、attempt、trace、状态、幂等指纹和乐观 version 持久化；
- 经过领域校验的计划结果快照；
- 转换后的必要结构化字段、来源、获取时间、validity、freshness 和安全归因；
- 内部追加式计划版本记录；
- 单个计划删除和保留期清理；
- 现有 POST/GET/retry API 使用持久化 Repository；
- 重启恢复、事务、并发、Decimal、时区、unknown、五种终态和安全边界测试；
- 相关架构、测试、决策、进度和证据文档收口。

## 非目标

- 多城市、多日和局部重规划；
- 版本比较、恢复和影响范围计算；
- 历史计划页面和历史列表 API；
- 登录、同步、多用户、云数据库和公网部署；
- provider 原始响应、完整 Prompt、Key、Token、JWT、私钥和 Authorization 持久化；
- 新的真实 Provider 调用；
- 自动预订、支付、库存和交易能力。

## 已确认的数据与隐私边界

- 仅支持本地 SQLite；
- 保存经过 allowlist 的结构化用户请求，用于恢复和受控 retry；
- 允许保存计划所需的转换后地点、路线、预算和天气字段；
- 允许保存来源元数据、获取时间、validity、freshness、attribution 和安全链接；
- 不保存 provider 原始响应、原始错误 body、完整 Prompt、Key、Token、JWT、私钥或 Cookie；
- 支持内部追加式版本，但 F-002 不提供版本比较和恢复；
- 支持删除单个计划；暂不支持清空全部本地数据；
- 数据保留期为 30 天，并在启动时执行过期清理；
- 使用项目自有 SQL migration runner，不引入 ORM/Alembic；
- 不修改现有公开 POST/GET/retry API 形状；
- 允许离线读取已保存计划；
- 保持单城市双日范围，不扩展多城市和局部重规划。

上述决策已由用户确认。若实现中发现需要扩大范围或改变这些边界，必须停止并请求重新确认。

## 当前代码复用边界

可复用：

- `PlanningJobRepository` Protocol；
- `PlanningJob`、`PlanningJobResult`、`PlanningJobReservation`；
- `request_fingerprint()`；
- `PlanningStateMachine`；
- `expected_version`、attempt、trace 和 retry 语义；
- `TripPlanRequest`、`TripPlan`、`SourceRecord`、`CostItem`、`BudgetSummary`；
- 五种终态和结果引用校验。

必须新增或重构：

- SQLite Repository adapter；
- 数据库连接生命周期；
- Schema migration runner；
- PlanVersion、AcceptanceRecord 和安全 DecisionRecord 的持久化边界；
- 重启恢复和事务测试；
- 删除、清理和数据库文件安全策略。

## Schema 与 API 边界

首版表方向：

```text
schema_migrations
planning_jobs
planning_attempts
plan_versions
source_records
plan_version_sources
decision_records
acceptance_records
```

必须具备唯一约束、外键、状态和 version 校验、`client_request_id` 幂等约束、`(job_id, version_number)` 版本约束、更新时间和来源 freshness 索引。

计划快照必须先通过现有 typed 模型校验，再以结构化 JSON 保存；数据库 JSON 不得绕过领域模型直接返回 API。

保持现有 `POST /api/trip-plans`、`GET /api/trip-plans/{job_id}`、`POST /api/trip-plans/{job_id}/retry` 和健康接口兼容。F-002 只允许按已确认范围新增单计划删除能力，不新增历史列表、版本比较或版本恢复 API。

## Step 0 执行基线

Step 0 只完成：

- 项目规则和权威文档核对；
- F-001 历史事实核对；
- main、origin/main、工作区和最近提交核对；
- F-002 数据、隐私、迁移、删除和 API 边界确认；
- 允许修改文件清单建立。

Step 0 明确不做：

- 不实现 SQLite；
- 不修改 Repository；
- 不新增 API；
- 不修改前端；
- 不调用 DeepSeek、高德或和风天气；
- 不读取、复制或输出 `.env.local`、Key、Token、JWT、私钥或 Cookie；
- 不创建 PR、推送或合并。

## 允许修改文件

Step 0 允许修改：

- `docs/README.md`
- `docs/project-management/roadmap.md`
- `docs/project-management/current-task.md`
- `docs/project-management/implementation-plan.md`
- `docs/project-management/progress.md`
- `docs/project-management/evidence.md`

Step 1 经批准的设计收口另外更新：

- `docs/architecture.md`
- `docs/testing-strategy.md`
- `docs/decisions.md`

Step 1 设计冻结已完成，Step 2 的允许范围为：

- `backend/src/intelligent_travel_assistant/adapters/persistence/**`
- `backend/tests/adapters/persistence/**`
- `docs/README.md`（仅用于 Step 2 状态收口）
- `docs/project-management/roadmap.md`（仅用于 Step 2 状态收口）
- `docs/project-management/current-task.md`
- `docs/project-management/implementation-plan.md`
- `docs/project-management/progress.md`
- `docs/project-management/evidence.md`

Step 2 允许范围只覆盖 SQLite 连接生命周期、migration runner、初始 schema 和对应临时 SQLite 测试。

Step 3 已获用户批准，允许修改：

- `backend/src/intelligent_travel_assistant/adapters/persistence/**`（仅限 SQLite `PlanningJobRepository` adapter、typed hydration 和任务/attempt/version/source 映射）；
- `backend/tests/adapters/persistence/**`（仅限 SQLite Repository adapter 与临时数据库集成测试）；
- `docs/project-management/current-task.md`；
- `docs/project-management/implementation-plan.md`；
- `docs/project-management/progress.md`；
- `docs/project-management/evidence.md`；
- `docs/README.md`（仅用于 Step 3 最终状态收口）；
- `docs/project-management/roadmap.md`（仅用于 Step 3 最终状态收口）。

Step 3 允许范围只覆盖现有 `PlanningJobRepository` Protocol 的 SQLite adapter，以及 job、attempt、trace、幂等指纹、乐观 version、结果快照、plan version 和 source records 的持久化与恢复。Step 2 冻结的 schema、migration 和隐私边界不得改变。

Step 4 已获用户批准，允许修改：

- `backend/src/intelligent_travel_assistant/settings.py`（仅限本地 SQLite 路径设置和路径安全校验）；
- `backend/src/intelligent_travel_assistant/bootstrap.py`（仅限持久化资源装配、startup migration 和 shutdown close）；
- `backend/src/intelligent_travel_assistant/app.py`（仅限 lifespan 与默认 Repository 装配）；
- `backend/tests/test_bootstrap.py`（仅限持久化启动/关闭和配置隔离测试）；
- `backend/tests/api/test_sqlite_trip_plans_api.py`（仅限临时 SQLite 的 API 重启、幂等、并发和冲突测试）；
- `backend/src/intelligent_travel_assistant/adapters/persistence/**` 与 `backend/tests/adapters/persistence/**`（仅在 Step 4 集成暴露已证实缺陷时做最小修复）；
- `docs/architecture.md`、`docs/api-contract.md`、`docs/testing-strategy.md`（仅同步 Step 4 已实现事实）；
- `docs/README.md`、`docs/project-management/roadmap.md`、`docs/project-management/current-task.md`、`docs/project-management/implementation-plan.md`、`docs/project-management/progress.md`、`docs/project-management/evidence.md`（执行和状态收口）。

Step 4 允许范围只覆盖现有 POST/GET/retry API 的默认本地 SQLite 装配、应用启动前 migration、关闭连接，以及重启、API 幂等、并发和冲突语义。测试只使用 `tmp_path` 临时数据库；`APP_ENV=test` 且未显式提供临时路径时继续使用内存替身。

Step 4 仍禁止：

- `backend/src/**` 中除上述明确文件以外的文件；
- `backend/tests/**` 中除上述明确测试文件以外的文件；
- `frontend/**`；
- `backend/pyproject.toml`；
- `backend/uv.lock`；
- `package.json`；
- `pnpm-lock.yaml`；
- `.env.example`；
- `.env.local`；
- `.github/**`；
- `docs/decisions.md`；
- Repository Protocol/contract 或公开 API/DTO 修改、前端、Provider、DELETE endpoint、版本比较/恢复、历史计划 API、删除/保留期业务逻辑；
- 任何数据库文件、SQLite 文件或真实 Provider 调用。

Step 5 已获用户批准，允许修改：

- `backend/src/intelligent_travel_assistant/application/repositories/models.py`、`ports.py`、`__init__.py`（仅限删除、maintenance 和 typed acceptance record 边界；既有五个 Repository 方法语义不变）；
- `backend/src/intelligent_travel_assistant/adapters/repositories/memory.py`（仅限单计划删除测试替身）；
- `backend/src/intelligent_travel_assistant/adapters/persistence/repository.py`、`__init__.py`（仅限单计划删除、过期清理、acceptance record 写入和隐私校验）；
- `backend/src/intelligent_travel_assistant/api/trip_plans.py`（仅限新增单计划 DELETE endpoint）；
- `backend/src/intelligent_travel_assistant/bootstrap.py`、`app.py`（仅限 migration 后启动清理和已批准 maintenance 装配）；
- `backend/tests/application/test_planning_job_repository.py`、`backend/tests/adapters/persistence/test_repository.py`、`backend/tests/api/test_trip_plans_api.py`、`backend/tests/api/test_sqlite_trip_plans_api.py`、`backend/tests/test_bootstrap.py`（仅限 Step 5 边界和回归）；
- `docs/architecture.md`、`docs/api-contract.md`、`docs/testing-strategy.md`、`docs/decisions.md`（仅同步 Step 5 已实现事实）；
- `docs/README.md`、`docs/project-management/roadmap.md`、`docs/project-management/current-task.md`、`docs/project-management/implementation-plan.md`、`docs/project-management/progress.md`、`docs/project-management/evidence.md`（执行和状态收口）。

Step 5 允许范围只覆盖：单计划删除及 job 级级联、migration 后一次有界启动清理、30 天边界、typed acceptance record 的内部持久化、敏感字段拒绝和对应临时 SQLite/内存测试。DELETE 不支持清空全部数据；acceptance record 不新增公开写入或历史查询 API。

Step 5 仍禁止：

- 修改 schema 或 migration、引入 ORM/Alembic或新增依赖；
- 历史计划列表、版本比较/恢复、清空全部数据、前端历史页面；
- Provider、真实网络、真实数据库文件、环境文件、`.github/**`；
- 多城市、多日、局部重规划、登录、同步、多用户、云数据库或公网部署；
- 保存或输出 provider 原始响应、原始错误 body、完整 Prompt、Key、Token、JWT、私钥、Cookie 或 Authorization；
- 改写 F-001 `PARTIAL`、Step 45M `FAIL`、Step 45T `PASS`、unknown 不为 0 或 fallback 仅离线证据。

Step 6 已获用户批准，允许修改：

- F-002 Step 0–5 已修改的生产代码、测试和文档，仅限累计差异审查发现的范围内缺陷修复；
- `docs/README.md`、`docs/project-management/roadmap.md`、`docs/project-management/current-task.md`、`docs/project-management/implementation-plan.md`、`docs/project-management/progress.md`、`docs/project-management/evidence.md`，用于 Step 6 执行与状态收口；
- 相关架构、API、测试和决策文档，仅用于同步已经验证的实现事实。

Step 6 允许范围只覆盖：F-002 累计 diff 审查、必要的范围内修复、全量 format/lint/typecheck/test/build/docs 门禁、数据库文件与隐私边界检查，以及本地交付审查。Step 6 不授权创建分支、提交、推送、PR、合并、真实 Provider 调用、真实业务数据库创建或任务归档。

Step 6 仍禁止：

- 扩大已批准的产品、数据、隐私、Schema、migration 或公开 API 范围；
- 历史列表、版本比较/恢复、清空全部数据、前端历史页面、多城市、多日或局部重规划；
- 新增依赖、修改环境文件、读取或输出秘密、访问真实 Provider 或非 loopback 网络；
- 改写 F-001 `PARTIAL`、Step 45M `FAIL`、Step 45T `PASS`、unknown 不为 0 或 fallback 仅离线证据；
- 创建分支、提交、推送、PR、合并或在未完成远程交付前归档 F-002。

## Step 0 验收

- [x] 指定项目文档已只读核对；
- [x] F-001 `PARTIAL`、45M `FAIL`、45T `PASS`、unknown 和 fallback 证据边界已核对；
- [x] main 与 origin/main 指向同一提交；
- [x] Step 0 开始前工作区干净；当前仅有允许清单内的 6 份项目管理文档变更；
- [x] F-002 已确认决策无未决阻塞；
- [x] 允许修改文件清单已建立；
- [x] 未实现 SQLite、Repository 或 API；
- [x] 未调用真实 Provider；
- [x] 未读取或输出秘密材料。

## Step 1 验收

- [x] Repository Protocol、内存 adapter、任务模型、结果快照、来源模型、状态机、API 和测试策略已只读审计；
- [x] Schema、约束、索引、JSON typed boundary 和删除级联已冻结；
- [x] migration runner、版本校验、事务、失败和回滚边界已冻结；
- [x] SQLite 连接生命周期、PRAGMA、busy timeout、并发和乐观锁语义已冻结；
- [x] 现有 Repository contract 映射、版本、attempt、trace、source、decision 和 acceptance 边界已冻结；
- [x] unknown、partial、conflict、needs_input、failed 和 retryable 语义已冻结；
- [x] 临时数据库、测试替身、重启、删除、保留期、隐私和 Provider 隔离测试矩阵已冻结；
- [x] 未修改生产代码、Repository、API、前端或依赖；
- [x] 未调用真实 Provider，未读取或输出秘密材料。

## Step 地图

| Step | 目标 | 状态 |
| --- | --- | --- |
| Step 0 | 事实核对、Git 基线、已确认决策和允许文件清单 | DONE |
| Step 1 | 冻结 Schema、migration、Repository contract、SQLite 连接边界和测试矩阵 | DONE |
| Step 2 | 实现 SQLite 连接、migration runner 和基础 schema | DONE |
| Step 3 | 实现持久化 Repository 与任务/attempt/version/source 映射 | DONE |
| Step 4 | 接入现有 API，完成重启、幂等、并发和冲突语义 | DONE |
| Step 5 | 完成删除、保留期清理、隐私安全和验收记录持久化 | DONE |
| Step 6 | 完成全量门禁、文档收口和交付审查 | TODO |

## Step 6 执行基线

Step 5 已完成并通过。用户已批准 Step 6 及真实 retry 标识冲突的最小修复。实现保持 attempt 1 的 `job_id` 命名空间兼容；attempt 2/3 使用由 `job_id + attempt + trace_id` 派生的稳定命名空间，使内部 plan、activity、route、cost 和 user/system source 标识在同一 job 的不同 attempt 间隔离。Schema、migration、公开 API、产品和隐私边界均未改变。

真实执行器 → SQLite → retry → 第二计划版本纵向红测先复现第二 attempt 降级为 `failed`，修复后证明第二个 `partial` 计划版本、两个 attempt 和互不冲突的来源均已持久化；attempt 1 `plan_id` 精确保持原 UUIDv5 规则。统一门禁通过 923 项后端、65 项前端、23 项文档检查器及全部 format/lint/strict mypy/build/docs。最终本地交付复审无剩余 P0/P1。

用户已明确授权创建 `feat/f-002-local-plan-persistence`、精确暂存、提交、推送、创建 PR 并验证远程 CI。实施提交为 `729119b9f583bfa80c421a9231f19694df38ab5f`；PR #6 以 `main` 为 base，状态 OPEN、非 Draft；Windows offline verification run `31923661440` / job `95107606302` 在 3 分 38 秒内通过。当前正在追加本交付证据并验证最终文档 head；F-002 保持 `ACTIVE`，Step 6 在最终 head CI 和后续合并/归档授权完成前保持 `TODO`，不得自动合并。

## 完成定义

- 所有持久化、迁移、事务、并发、版本、删除、保留期和隐私验收标准通过；
- F-001 历史事实没有被改写；
- unknown 没有被转换为 0；
- partial 没有被伪装为 ready；
- 默认测试不访问真实 Provider；
- 独立数据库审查完成；
- 全量 format、lint、typecheck、test、build 和文档门禁通过；
- Git diff、PR、CI、用户验收和文档收口完成；
- F-002 任务卡按项目规则归档，current-task 转为无活动任务。
