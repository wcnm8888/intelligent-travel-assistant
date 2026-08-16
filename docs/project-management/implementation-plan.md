# 当前实施计划

## 当前状态

- 当前任务：`F-002 计划持久化、来源与版本`
- 任务状态：`ACTIVE`；任务卡状态：`APPROVED`
- 当前 Step：`Step 6` PR #6 已创建，实施提交 CI 通过
- 下一批准动作：等待用户批准 Step 6（Step 6 与 Git/PR 授权均已取得；保留此状态锚点供文档检查器识别）；当前验证最终文档 head CI，随后等待合并授权
- 当前分支：`feat/f-002-local-plan-persistence`
- 当前实施提交：`729119b9f583bfa80c421a9231f19694df38ab5f`
- `main` 与 `origin/main`：一致
- 工作区：实施提交后仅有本次 PR/CI 交付证据文档变更；未修改生产代码、测试、前端或依赖

## Step 6 执行基线

- 用户已批准全量门禁、文档收口和交付审查；Step 6 在审查与门禁完成前保持 `TODO`；
- 审查对象是 `HEAD` 到当前工作区的完整 F-002 累计差异，包括未跟踪的 persistence 源码和测试；
- 允许对累计审查发现的 F-002 范围内缺陷做最小修复，并同步权威文档；不扩大 Schema、migration、公开 API、产品或隐私边界；
- 测试继续只使用内存替身和 `tmp_path` SQLite，不创建真实业务数据库，不读取 `.env.local`，不调用真实 Provider 或非 loopback 网络；
- 本地审查阶段不创建分支、提交、推送、PR 或合并；后续用户已另行授权分支、提交、推送、PR 和 CI，但仍未授权合并。

## Step 6 审查结果

- 初次本地统一门禁通过：91 个 Python/脚本文件 format、Ruff、strict mypy，后端 922 项、前端 65 项、文档检查器 23 项及 Vite build 全部通过；
- 范围检查通过：没有 frontend、依赖、lockfile、环境、CI 或数据库文件变更；没有真实 Provider、非 loopback 网络或真实业务数据库访问；
- 初次交付阻塞：真实执行器的 `_id(job_id, suffix)` 使 retry 继续生成相同 `plan_id` 和 user/system `source_id`；SQLite schema 的 `UNIQUE(job_id, plan_id)` 与 `PRIMARY KEY(job_id, source_id)` 会拒绝第二个终态；
- 用户批准后已保持 Schema、migration 和 attempt 1 标识不变，仅为 attempt 2/3 引入由 job/attempt/trace 派生的稳定命名空间；
- 纵向红测先得到第二 attempt `failed`，修复后得到第二个 `partial` 计划版本、两个 attempt、不同 plan ID 和不重叠 user/system source ID；相关执行器、Repository、API 专项 53 项通过；
- 修复后统一门禁再次通过：91 个 Python/脚本文件 format、Ruff、strict mypy，后端 923 项、前端 65 项、文档检查器 23 项及 Vite build 全部通过；最终本地复审无剩余 P0/P1；
- 用户已授权创建指定功能分支、精确暂存、提交、推送、创建 PR 和验证远程 CI；不授权自动合并。任务在 PR/CI 证据形成前不能归档。
- 实施提交 `729119b9f583bfa80c421a9231f19694df38ab5f` 已推送；PR #6 OPEN、非 Draft、base `main`；Windows offline verification run `31923661440` / job `95107606302` 通过。当前只追加交付证据并验证最终文档 head，不自动合并。

## 执行基线修复

- 原文件清单错误地禁止了 Step 2 所需的 SQLite/migration 基础设施和临时测试；
- 本次只修复 `current-task.md` 的阶段化允许/禁止文件清单；
- 未修改生产源码、未创建数据库、未运行 Step 2；（以上为基线修复阶段的历史记录）
- 未读取 `.env.local` 或任何秘密；
- Step 2 后续已获用户批准并完成实现验证；状态收口在本次获得授权后完成。

## Step 3 执行基线修复

- 用户已批准修复 Step 3 文件清单，并在基线门禁通过后重新进入 Step 3；
- Step 3 明确允许 persistence 目录内的 SQLite `PlanningJobRepository` adapter、typed hydration、job/attempt/version/source 映射和对应临时数据库测试；
- Step 3 项目管理文档及最终状态收口所需的 `docs/README.md`、`roadmap.md` 已纳入允许范围；
- Repository Protocol、API、前端、Provider、依赖、环境文件、真实数据库、删除/清理、版本比较/恢复和历史列表仍禁止修改；
- 基线修复本身不实现 Repository；门禁通过后才进入 Step 3 实现。

## Step 3 实现验证结果

- 已在 persistence adapter 内实现既有 `PlanningJobRepository` 的五个方法，没有修改 application Protocol；
- 已实现 allowlist request JSON、typed result metadata、追加式 plan version、source records/link、attempt/trace 和乐观 version 的原子写入与恢复；
- 已验证重启恢复、幂等创建与冲突、同连接并发更新、跨连接 stale version、retry、两版计划、五种终态、unknown/Decimal/时区/freshness round-trip、事务回滚、损坏数据 fail closed 和隐私字段拒绝；
- persistence 测试 28 项、后端全量 904 项、前端 65 项、文档检查器 23 项以及统一 format/lint/strict mypy/build/docs 门禁通过；
- 未接入 API、前端或 Provider，未修改依赖、Schema 或 migration，未创建真实业务数据库，未读取秘密或访问真实网络；
- Step 3 标记为 `DONE`；Step 4 仍为 `TODO`，等待用户批准。

## Step 4 执行基线

- 用户已明确批准进入 Step 4；
- 实现仅允许修改 settings、bootstrap、app 组合根，以及临时 SQLite 的 bootstrap/API 集成测试；公开路由、DTO 和 Repository Protocol 不变；
- 本地模式默认使用应用数据目录中的 SQLite；test 模式只有显式传入 `tmp_path` 数据库路径时才启用 SQLite，否则继续使用内存测试替身；
- 应用 lifespan 必须在接受请求前完成连接和 migration，失败时 fail closed；shutdown 必须关闭连接；
- Step 4 验证重启读取、重复 POST、同 client ID 输入冲突、并发创建和 retry 冲突；不实现删除、清理、历史列表、版本比较/恢复或 Step 5；
- 最终状态收口允许同步 architecture、api-contract、testing-strategy、README、roadmap 和项目管理文档。

## Step 4 实现验证结果

- 已在 settings、bootstrap 和 app 组合根内装配本地 SQLite Repository；显式路径必须为源码树外的绝对路径，默认路径位于操作系统本地应用数据目录，模块导入不创建数据库；
- lifespan 在接受请求前打开连接并完成 migration，失败或高版本数据库安全停止启动，关闭时释放连接；测试注入优先，`APP_ENV=test` 未显式提供临时路径时继续使用内存替身；
- 新增 9 项组合根/API 测试，覆盖默认路径安全、迁移与关闭、应用重启恢复、重复 POST、异请求幂等冲突、16 路并发创建、retry 乐观冲突和高版本 fail closed；
- 统一门禁通过：91 个 Python/脚本文件 format、Ruff、strict mypy，后端 913 项、前端 65 项、文档检查器 23 项和前端 build 全部通过；
- 未修改公开路由/DTO、Repository Protocol、Schema、migration、前端、Provider 或依赖；未创建真实业务数据库，未读取秘密，未访问真实 Provider 或非 loopback 网络；
- Step 4 标记为 `DONE`；Step 5 仍为 `TODO`，等待用户批准。

## Step 5 执行基线

- 用户已明确批准 Step 5：单计划删除、30 天保留期启动清理、隐私安全收口和 acceptance record 持久化；
- 允许修改范围限定为新增窄 Repository/maintenance/acceptance port、内存测试替身、SQLite adapter、单计划 DELETE route、启动清理装配、对应测试和权威文档；
- 冻结 schema 与 migration 不变；acceptance record 使用既有 `acceptance_records` 表，删除依赖既有 job 级外键级联，清理依据既有 `expires_at` 索引；
- acceptance record 仅提供内部 typed 写入边界，不新增公开写入或历史查询 API；DELETE 只删除一个明确 job ID，不提供清空全部数据；
- 测试只使用内存替身和 `tmp_path` SQLite，不读取 `.env.local`，不访问真实 Provider 或非 loopback 网络，不创建真实业务数据库。

## Step 5 实现验证结果

- 已实现单计划 Repository delete 和 `DELETE /api/trip-plans/{job_id}`；存在返回 204，缺失/非法 ID 返回安全 404，删除释放 client request ID；
- SQLite 删除依赖既有外键级联移除 job-owned attempt、版本、来源关联、decision 和 acceptance；没有批量清空入口；
- migration 完成后启动一次有界 cleanup，每次最多删除 1000 个 `expires_at <= now` 的 job；aware datetime 在 Python 精确比较，避免 SQLite `julianday` 微秒舍入提前删除；
- acceptance record 使用固定 status 和代码化 case/environment/check/limitation typed model，只写既有表，校验 attempt/plan version 归属，不开放公开 API；
- 定向 80 项通过；统一门禁中后端 922 项、前端 65 项和文档检查器 23 项通过；Schema、migration、前端、Provider、依赖和真实业务数据库未改变。

## Step 2 实现验证结果

- 已在允许的 persistence 路径实现 SQLite 连接生命周期、事务工具、migration runner 和初始 schema；
- 已完成 12 项定向 SQLite 测试、全后端 888 项离线测试、Ruff format/check 和 persistence 目录 strict mypy；
- 代码与测试没有接入 Repository、API、前端、Provider、依赖或真实数据库；
- Step 2 状态收口已同步 `docs/README.md`、`roadmap.md`、`current-task.md`、本计划、`progress.md` 和 `evidence.md`；Step 2 现标记为 `DONE`；
- Step 3 仍为 `TODO`，未获用户批准前不得进入。

## Step 0 结果

- 已只读核对项目规则、文档地图、roadmap、current-task、progress、evidence 和本计划。
- 已核对 F-001 `PARTIAL`、Step 45M 历史真实 UAT `FAIL`、Step 45T 真实 UAT `PASS`、unknown 费用不按 0、混合交通 fallback 仅有离线证据。
- 已确认当前没有可迁移的旧 SQLite 数据，F-001 结果此前只在进程内存在。
- 已确认 F-002 的本地 SQLite、结构化字段、来源 freshness、版本、删除、30 天保留期、migration runner、API 和隐私边界。
- 未实现 SQLite，未修改 Repository，未新增 API，未调用真实 Provider。
- 未读取 `.env.local`，未读取、复制或输出 Key、Token、JWT、私钥或 Cookie。

## Step 1 结果：冻结设计

Step 1 已完成。以下设计只冻结实现边界，不代表 SQLite、Repository 或 API 已实现。

### 1. Schema 总体约束

- SQLite 只保存项目自有、经过 typed model 校验的结构化数据；所有 UUID 用小写 canonical string，枚举用受限 TEXT，布尔值用 `INTEGER NOT NULL CHECK (value IN (0, 1))`。
- `Decimal` 金额、坐标和温度使用规范化十进制 TEXT；日期、time 和带时区 datetime 使用规范化 ISO-8601 TEXT，禁止 SQLite REAL/浮点承载金额。
- JSON 只保存 `model_dump(mode="json")` 后的 allowlist 结构，写入前和读取后都必须重新经过 Pydantic/领域模型校验；数据库 JSON 不得直接返回 API。
- `planning_jobs` 是任务当前快照；`planning_attempts` 保存每个 attempt 的当前状态与终态元数据；`plan_versions` 追加保存带计划的结果快照；source、decision、acceptance 均由 job 级外键隔离。
- 所有业务表通过 `job_id` 归属任务，启用 `PRAGMA foreign_keys=ON`；删除任务时级联删除其 attempt、version、source link、decision 和 acceptance 记录。

### 2. 表与字段冻结

| 表 | 主键 | 核心字段与 nullable 语义 |
| --- | --- | --- |
| `schema_migrations` | `version INTEGER` | `name TEXT NOT NULL`、`checksum TEXT NOT NULL`、`applied_at TEXT NOT NULL`；已执行版本不可改名或改 checksum |
| `planning_jobs` | `job_id TEXT` | `trace_id`、`client_request_id`、`request_fingerprint`、`request_json`、`status`、`attempt`、`version`、`retryable`、`created_at`、`updated_at`、`expires_at`；`client_request_id/request_json` 非空，`version >= 1`，`attempt 1..3` |
| `planning_attempts` | `(job_id, attempt)` | `trace_id`、`status`、`retryable`、`started_at`、`updated_at`、`result_metadata_json`、`current_plan_version`；中间态 metadata/version 可空，终态 metadata 必须非空 |
| `plan_versions` | `(job_id, version_number)` | `plan_id`、`attempt`、`trace_id`、`status`、`plan_json`、`created_at`；`plan_json` 对有计划结果非空，追加写入，不原地更新 |
| `source_records` | `(job_id, source_id)` | `attempt`、`provider`、`source_type`、`provider_record_id` 可空、`fetched_at`、`valid_until` 可空、`freshness`、`reference_url` 可空、`attributions_json`、`warnings_json`；不含原始响应 |
| `plan_version_sources` | `(job_id, version_number, source_id)` | 连接 `plan_versions` 与 `source_records`；三列均非空，外键必须同一 job |
| `decision_records` | `decision_id TEXT` | `job_id`、`attempt`、`trace_id`、`plan_version` 可空、`kind`、`status`、`proposal_json`、`validation_json`、`user_choice_json` 可空、`created_at`、`decided_at` 可空；只保存安全结构化摘要 |
| `acceptance_records` | `acceptance_id TEXT` | `job_id`、`attempt`、`plan_version` 可空、`case_id`、`status`、`observed_at`、`environment`、`evidence_json`；不保存原始 provider 响应、Prompt、秘密或完整日志 |

约束和索引：

- `planning_jobs.client_request_id` UNIQUE；`request_fingerprint` 为 64 位小写 SHA-256；`(job_id, attempt)`、`(job_id, version_number)` 唯一。
- `plan_versions.plan_id` 在任务范围内唯一；`plan_version_sources`、decision 和 acceptance 的外键均为 `ON DELETE CASCADE`。
- 索引 `planning_jobs(expires_at)`、`planning_jobs(updated_at)`、`planning_jobs(status)`、`planning_attempts(job_id, attempt)`、`plan_versions(job_id, created_at)`、`source_records(job_id, freshness, valid_until)`、`decision_records(job_id, created_at)` 和 `acceptance_records(job_id, observed_at)`。
- 不提供全局历史计划查询索引；F-002 不新增历史列表 API。

### 3. 结果快照与状态语义

- `ready`：必须有 `plan_json`，无 error/violation，`retryable=false`。
- `partial`：必须有 `plan_json`，且至少有 warning、uncertainty、violation 或 error；保留可恢复状态和来源。
- `conflict`：可有或没有 `plan_json`，必须保留 violation/error；不允许 retryable。
- `needs_input`：没有 `plan_json`，必须保留安全 error；不允许 retryable。
- `failed`：没有 `plan_json`，必须保留安全 `ApiError` 摘要；是否 retryable 只取 typed error 的 retryable 语义。
- `unknown` 不是任务状态；费用以 `confidence="unknown"`、`amount=null`、预算 `unknown_count` 和 `budget_indeterminate` 保存。来源 freshness 以 `fresh/stale/unknown_validity` 保存，不推测缺失时效。
- `result_metadata_json` 只保存 resolved destination、violations、warnings、uncertainties、errors 和 source ID 引用等安全字段；完整计划只放在 `plan_versions.plan_json`，来源从 `source_records` 重建。
- GET 恢复时必须先重新构造 `TripPlanRequest`、`PlanningJobResult` 和 `PlanningJob`；任何 JSON/外键/状态不一致都作为持久化损坏错误停止，不能返回伪造快照。

### 4. Migration runner

- 首个 schema 版本为 `1`，一次性建立上述表、约束和索引；后续版本按递增整数注册，执行顺序严格升序。
- runner 只接受项目内显式 migration 清单，记录 `(version, name, checksum, applied_at)`；已执行版本 checksum/name 不一致立即失败。
- 每个 migration 在单独事务中执行：`BEGIN IMMEDIATE` → 校验前置版本 → 执行 SQL → 写入 `schema_migrations` → `COMMIT`；异常统一 `ROLLBACK`，不留下半个版本。
- 不支持自动 down migration、自动降级或猜测修复。数据库版本高于当前代码、checksum 漂移、迁移失败或 schema 不完整时 fail closed，应用不启动。
- F-001 进程内状态没有迁移来源；首次 SQLite 启动不导入旧内存 job，也不伪造历史版本。

### 5. SQLite 连接与事务

- 采用标准库 SQLite，Repository adapter 与 `application` Protocol 隔离；连接由 Repository 生命周期创建/关闭，应用组合根负责注入，领域层不接触 SQLite。
- 连接初始化固定 `foreign_keys=ON`、`busy_timeout=5000`、`journal_mode=WAL`、`synchronous=FULL`；数据库文件位于本地应用数据目录，不位于源码、Git 或前端静态目录。
- async port 由 adapter 的单连接串行执行边界承载；同一连接不被并发线程直接共享，关闭时先停止新操作并等待在途事务完成。
- `get` 使用一致性读；`get_or_create`、`advance`、`record_result`、`retry`、delete 和 cleanup 使用 `BEGIN IMMEDIATE`，所有相关行和子表写入在同一事务中完成。
- busy/locked 超过 5 秒返回内部 persistence failure，不伪装成业务版本冲突；业务版本冲突只由 expected version 条件更新产生。

### 6. Repository contract 映射

- `get_or_create(request)`：先生成 fingerprint；以 `client_request_id UNIQUE` 原子插入 job 与 attempt 1。唯一冲突后读取已有 job，同 fingerprint 返回 `created=false`，不同 fingerprint 返回 `IDEMPOTENCY_CONFLICT`。
- `get(job_id)`：读取 job 当前字段、current attempt、plan version、source records 和 result metadata，经过 typed hydration 后返回不可变 `PlanningJob`。
- `advance(...)`：校验状态机和 retryable 规则，执行 `WHERE job_id=? AND version=?` 的条件更新；影响行数为 0 时返回 `VERSION_CONFLICT`，成功则 version 加 1。
- `record_result(...)`：先完成现有 typed result 和 request match 校验，再在一个事务中写 sources、plan version、result metadata、attempt 和 job 当前快照；任何一项失败全部回滚。
- `retry(...)`：读取并校验 expected version、当前状态和 attempt < 3；保留旧 attempt/version，新增 attempt 与 trace，清空当前结果引用，状态回到 `normalizing`，version 加 1。
- 后续新增的 `delete(job_id)` 和 `cleanup_expired(now)` 属于 Repository/maintenance port，不改变现有五个方法；Step 1 不实现，也不新增 HTTP 路由。
- 所有 Repository error 继续使用现有稳定错误码；SQLite 异常不得泄漏 SQL、路径、参数、请求文本或内部堆栈。

### 7. 版本、删除与保留期

- job `version` 是并发控制版本，每次成功状态/结果/retry 写入都递增；`plan_versions.version_number` 是计划快照序号，只在产生带计划结果时递增，二者不混用。
- 计划版本只追加，不比较、不恢复、不原地覆盖；旧版本仅作为内部审计和 F-003 前置基线，不提供历史列表接口。
- `expires_at = created_at + 30 days`，使用注入的 aware UTC 时钟计算；启动后 migration 完成再执行一次有界 cleanup。
- 单计划删除在事务中删除 `planning_jobs`，依赖级联移除所有子记录；不存在的 job 返回现有 `JOB_NOT_FOUND` 语义。F-002 不支持清空全部数据。

### 8. 测试矩阵冻结

| 层级 | 必测内容 | 隔离与证据 |
| --- | --- | --- |
| schema/migration | 首次建库、重复运行、checksum 漂移、顺序、失败 rollback、版本过高 fail closed | 每个用例独立 `tempfile` 数据库；不触碰本地业务 DB |
| connection | PRAGMA、WAL、busy timeout、关闭、迁移失败不启动 | 本地临时文件；不启动真实服务 |
| repository | 同请求复用、异请求冲突、20 路并发、状态机、version conflict、retry attempt/trace/limit | fixed UUID、注入时钟、SQLite adapter 与内存 adapter 同一 contract |
| persistence round-trip | request、result、source、plan、Decimal、date/time、timezone、enum | typed model 重建后逐字段比较 |
| terminal states | ready、partial、conflict、needs_input、failed 与 retryable 组合 | 复用五个 synthetic fixtures，标记离线 |
| version/source | append-only、唯一约束、source freshness、链接关系、旧版本不变 | 事务提交前后和失败回滚断言 |
| lifecycle | 重启读取、单计划删除、30 天边界 cleanup、未过期保留 | 两个 Repository 实例共享临时 DB；不使用默认真实路径 |
| privacy | 拒绝原始 provider body、Prompt、Authorization、Key/Token/JWT/private key/Cookie；错误摘要脱敏 | AST/模式扫描与 DB JSON 内容断言 |
| API regression | 现有 POST/GET/retry/health DTO 和状态不变；不新增历史 API | FastAPI TestClient 注入 fake/SQLite 临时 adapter |
| network boundary | 普通 pytest、文档门禁和 SQLite 测试不访问外网或真实 Provider | `APP_ENV=test`、loopback-only fixture、无 `.env.local` 读取 |

Step 1 只冻结矩阵；具体测试文件和实现归入 Step 2–5。

## Step 地图

| Step | 目标 | 状态 |
| --- | --- | --- |
| 0 | 事实核对、Git 基线、已确认决策和允许文件清单 | DONE |
| 1 | 冻结 Schema、migration、Repository contract、SQLite 连接边界和测试矩阵 | DONE |
| 2 | 实现 SQLite 连接、migration runner 和基础 schema | DONE |
| 3 | 实现持久化 Repository 与任务/attempt/version/source 映射 | DONE |
| 4 | 接入现有 API，完成重启、幂等、并发和冲突语义 | DONE |
| 5 | 完成删除、保留期清理、隐私安全和验收记录持久化 | DONE |
| 6 | 完成全量门禁、文档收口和交付审查 | TODO |

## Step 2 输入与禁止项

Step 2 的唯一目标是实现 SQLite 连接、migration runner 和基础 schema。该 Step 已获批准并完成。

输入为已批准的 F-002 current-task、当前 Repository Protocol/内存 adapter、当前 API 与状态契约、测试策略和质量门禁；实现已限制在 persistence 基础设施和临时 SQLite 测试。

Step 2 不得扩大到 Repository 接入、API、历史 UI、版本比较/恢复、多城市、局部重规划、真实 Provider、登录、同步、多用户或公网部署。

## 停止条件

发现任何已确认的数据、隐私、迁移、删除或 API 边界需要变化；发现 F-001 历史事实可能被改写；需要读取秘密或调用真实 Provider；或需要修改未列入允许范围的文件时，立即停止并请求确认。

## 权威入口

- 当前任务：[current-task.md](./current-task.md)
- 路线图：[roadmap.md](./roadmap.md)
- 进度：[progress.md](./progress.md)
- 证据：[evidence.md](./evidence.md)
