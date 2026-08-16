# F-003：局部重规划与影响确认（归档）

## 归档元数据

- 任务 ID：`F-003`
- 名称：局部重规划与影响确认
- 等级：`L`
- 状态：`DELIVERED`
- 任务卡状态：`APPROVED`
- 批准日期：2026-08-16
- 完成 Step：`Step 0–8`
- Step 0 状态：`DONE`
- Step 1 状态：`DONE`，设计冻结完成
- Step 2 状态：`DONE`
- Step 3 状态：`DONE`
- Step 4 状态：`DONE`，精确文件清单内实现与门禁已通过
- Step 5 状态：`DONE`，精确文件清单内实现与门禁已通过
- Step 6 状态：`DONE`，精确文件清单内实现与前端门禁已通过
- 验收结论：`PASS`
- 基线分支：`main`
- 建议功能分支：`feat/f-003-local-replanning-confirmation`
- 交付状态：stacked PR 已按依赖顺序通过 CI 并合并；因 squash merge 改写 ancestry，后两层使用等价干净分支重新提交，原 PR #8/#9 作为 superseded 关闭
- 交付策略：`STACKED_PR`，冻结为 `feat/f-003-replanning-domain` → `feat/f-003-replanning-persistence` → `feat/f-003-local-replanning-confirmation`；base 依次为 `main`、领域分支、持久化分支
- PR：领域 [#7](https://github.com/wcnm8888/intelligent-travel-assistant/pull/7)、持久化/应用 [#10](https://github.com/wcnm8888/intelligent-travel-assistant/pull/10)、API/UI/验收 [#11](https://github.com/wcnm8888/intelligent-travel-assistant/pull/11)
- superseded PR：#8、#9，已说明替代关系并关闭
- 主线功能合并提交：`a9f1b83ee558de29e6f7c5b1bef67548fec9240a`
- 合并后 main CI：run `31939222646`，`PASS`

## 用户目标和工程价值

用户查看已保存的单城市双日计划时，可以替换或删除活动、调整活动时间或同一天顺序。系统先用确定性代码计算直接和间接影响：低影响的当天内部修改可自动执行；跨日、住宿关联、预算风险、来源失效或无法确定影响的修改必须先展示影响并等待确认；超出单城市双日边界的修改必须拒绝。

成功修改必须追加新计划版本，不静默覆盖旧版本。F-003 把 F-002 的“可保存版本”扩展为“可安全演进、可确认、可审计的计划”。

## 前置事实和历史边界

- B-000、F-001、F-002 已交付并归档；
- F-001 产品验收状态继续为 `PARTIAL`；
- Step 45M 历史真实 UAT `FAIL` 和 Step 45T 真实 UAT `PASS` 均必须保留；
- 门票等非关键费用保持 `unknown`，金额为 `null`，不得按 0 处理；
- 混合交通 fallback 只有离线证据；
- F-002 已实现本地 SQLite、追加式计划版本、来源、attempt/trace、乐观 version、单计划删除、30 天清理和 typed acceptance record；
- F-002 没有历史列表、任意版本比较、版本恢复或局部重规划 API；
- F-003 不导入、不改写 F-001/F-002 历史验收记录。

## 已批准范围

- 保持单城市双日计划；
- 支持 `replace_activity`、`delete_activity`、`adjust_activity_time`、`reorder_activities` 四种结构化操作；
- 基于当前 plan ID/version 计算直接与传递影响；
- same-day low impact 在确定性分析和重校验通过后自动执行；
- adjacent/cross-day、住宿影响、预算风险、来源刷新和 unknown impact 必须确认；
- cross-city 直接拒绝；
- 确认请求持久化且有效期 15 分钟；
- 成功重规划追加计划版本、父版本 lineage、change set、decision、trace 和来源关联；
- 只提供本次基线到结果的结构化 diff；
- 新增窄 replan API 和前端影响预览/确认流程；
- SQLite migration 方向为 version 2；
- 默认开发、测试、CI 和验收完全离线；真实 Provider UAT 必须另行限次授权。

## 非目标

- 新增活动；
- 修改住宿锚点、城市或旅行日期；
- 跨城市重规划；
- 通用历史计划或 replan 列表；
- 任意两个版本比较；
- 恢复旧版本；
- 清空全部本地数据；
- 登录、同步、多用户、云数据库或公网部署；
- 多城市、多日扩展；
- 自动预订、支付、库存或出票；
- 多 Agent；
- 保存 provider 原始响应、原始错误 body、完整 Prompt、完整自然语言修改请求或秘密。

## 当前代码和 Schema 基线

- `PlanningStatus` 与 `ALLOWED_PLANNING_TRANSITIONS` 仍是 F-001 的 11 状态，不含局部重规划状态；
- 已批准采用独立 replan lifecycle，不把 `awaiting_confirmation/replanning` 加入现有 `PlanningJob.status`；D-004 的“应用状态机”在 Step 1 解释为独立 replan 状态机并同步长期文档；
- `PlanningJobRepository` 当前只有 `get_or_create/get/advance/record_result/retry/delete`；
- `PlanningJob.version` 和 Repository `expected_version` 已存在，但未暴露在现有 HTTP DTO；
- `TripPlanResponse` 不包含 plan version；现有 POST/GET/retry/DELETE 形状必须保持兼容；
- `plan_versions` 追加写入但没有父版本、change set 或公开读取接口；
- `decision_records` 已有基础表，但没有 typed Decision model、Repository port 或生产读写路径；
- `acceptance_records` 已有 typed 内部写入边界；
- migration runner 当前只包含 schema version 1；
- 当前前端“返回修改需求”只重置表单，不是局部重规划。

## 修改命令与输入

所有 replan 输入必须是严格 tagged union，不接受 JSON Patch、完整新计划或客户端直接提交 provider ID。

公共字段方向：

```text
replan_request_id
job_id
baseline_plan_id
operation
target_activity_id
typed_payload
optional_reason_code
```

- replacement 只接受结构化类别/偏好；
- delete 只接受现有 activity ID；
- adjust time 使用目的地当地时间；
- reorder 必须提交同一天完整且无重复的 activity ID 顺序；
- 不保存完整自然语言修改请求，只允许安全 reason code。

## 影响分类与确认边界

| 分类 | 行为 |
| --- | --- |
| `same_day_low` | 不影响另一日、住宿、硬约束、预算可判定性或来源有效性时自动执行 |
| `adjacent_day` | 必须确认 |
| `cross_day` | 仅限原双日范围，必须确认 |
| `accommodation_effect` | 只表示住宿往返受影响，必须确认；不得修改住宿锚点 |
| `budget_risk` | 已知超支、unknown 增加或可判定性下降时必须确认；确认不放宽硬约束 |
| `source_refresh` | 必要来源过期或受修改影响时必须确认后再获取 |
| `cross_city` | 在任何 Provider 调用或写入前拒绝 |
| `unknown_impact` | 不自动执行，进入 needs_input 或安全拒绝 |

影响分析允许同时返回多个分类，必须保存直接对象、传递对象、受影响日期、路线、预算、来源动作和所需重校验。

## Replan lifecycle 与状态语义

独立 replan lifecycle 方向：

```text
analyzing
→ awaiting_confirmation | replanning | rejected
→ completed | needs_input | conflict | failed | cancelled | expired
```

- 分析、等待确认或执行失败期间，原 PlanningJob 当前计划保持不变；
- `approve` 只授权展示过的影响范围；`cancel` 不修改计划；
- 重复相同决定幂等，相反决定返回冲突；
- 过期确认不能执行；
- `ready` 和可执行 `partial` 可以在原子事务中成为新当前版本；
- `conflict`、`needs_input`、`failed`、`cancelled` 和 `expired` 不替换当前可用计划；
- `unknown` 金额保持 `null`，freshness 不得被提升；
- replan 不增加 retry attempt，不受三次 retry 上限冒充。

## 版本、并发、来源和事务

- `replan_request_id` 在同一 job 内唯一；同 ID 同命令复用，异命令返回幂等冲突；
- 分析时捕获 baseline plan/version 和 job expected version；确认和提交都重新比较；
- 基线变化返回稳定版本冲突，不自动重新基线；
- 同一基线的并发 replan 最多一个提交成功；
- 确认前不创建正式 plan version；
- 成功提交必须在一个事务内写入新 plan version、source links、lineage、decision、replan 状态和当前快照；
- 任一步失败全部 rollback，不留下伪完成版本；
- 未受影响且仍 fresh/valid 的来源可复用；修改对象、相邻路线、相关费用和 stale/无效必要来源必须重新评估；
- 新活动候选不得继承被替换活动的来源；未采用、取消或失败的来源不进入新版本；
- 旧版本继续受单 job 删除和 30 天保留期管理；删除 job 级联删除所有 F-003 子记录；
- 旧 acceptance 不复制到新版本；新版本未验收时只能为 `not_run`。

## SQLite migration v2 冻结设计

v2 新增 `replan_requests`：

- `replan_id` 主键；`job_id` 外键级联；job 内唯一 `replan_request_id`；
- command SHA-256 `request_fingerprint`、`baseline_plan_id`、`baseline_plan_version`、内部 `expected_job_version`、独立 `trace_id`；
- 受限 `operation`、typed `request_json`、可空 typed `impact_json`、十值 replan `status`、`aggregate_version`；
- 可空且唯一 `decision_id`、可空 `result_plan_version`、可空安全 `error_code`；
- `created_at/updated_at`、等待确认时的 `expires_at`、可空 `decided_at`；UUID、fingerprint、状态、版本和 JSON 非空均使用 CHECK；
- v2 先为 `plan_versions(job_id, version_number, plan_id)` 增加唯一索引；baseline 的 job/version/plan ID 以一个三列外键精确引用该元组，result version 以同 job 两列外键引用 `plan_versions`，不得把一个版本号与另一版本的 plan ID 拼接。

v2 新增 `plan_version_lineage`：

- `(job_id, child_version)` 主键；同 job `parent_version`、唯一 `replan_id`、可空 `decision_id`、typed `change_set_json` 和 `created_at`；
- child/parent 都外键到 `plan_versions`，replan 外键到 `replan_requests`，child 必须大于 parent；
- 既有 v1 版本不补造 lineage；只有 F-003 成功提交的新版本写入该表。

索引冻结为 job/status/updated、job/awaiting-confirmation/expires、job/baseline 和 lineage parent；job 删除继续级联。现有 `decision_records` 不改表：`attempt` 记录当前 planning attempt 但 replan 不递增 attempt，`trace_id` 使用 replan trace，`plan_version` 指 baseline，`proposal_json` 保存 typed command，`validation_json` 保存 typed impact，`user_choice_json` 只保存 approve/cancel；kind/status 使用受限项目代码。low-impact 自动决定记录 `auto_approved`，高影响先记录 `pending`。

migration 2 名称/checksum 进入既有严格升序 runner；单 migration 事务、失败 rollback、重复运行幂等、高版本 fail closed、不支持自动 down。v1 数据和 schema 1 历史保持不变。

## API 与前端方向

现有 POST/GET/retry/DELETE 保持兼容。拟新增：

```text
POST /api/trip-plans/{job_id}/replans
GET  /api/trip-plans/{job_id}/replans/{replan_id}
POST /api/trip-plans/{job_id}/replans/{replan_id}/decision
```

- 不新增历史 replan/plan version 列表、任意版本比较或恢复端点；
- 前端在现有活动上提供四种结构化修改入口；
- 展示影响、确认原因、预算、来源动作、过期、取消、冲突和本次 diff；
- 取消或失败后继续展示原计划；
- 新交互必须先更新设计规格并获得用户设计批准，真实页面还需桌面和 `390×844` 视觉验收；
- 状态不得只用颜色表达，焦点恢复和重复提交禁用必须可验证。

Step 1 已在 `api-contract.md` 和 `design-spec.md` 冻结精确请求、响应、HTTP 错误、局部调整面板、桌面/390px 布局、焦点、过期和 diff 交互。现有 `TripPlanResponse` 不增加字段；公开 baseline token 使用当前 `plan_id`，内部版本只由服务端捕获。用户已批准并完成 Step 6 前端实现；浏览器视觉与纵向验收仍留在 Step 7。

## Repository contract 冻结

新增独立 `ReplanRepository`，保持 `PlanningJobRepository` 原方法和签名不变。port 使用 frozen typed model，不出现 SQLite 类型、SQL 或裸 JSON dict。方法语义冻结为：

1. `reserve(request) -> ReplanReservation`：在 job 内按 request ID + 指纹幂等创建/复用 analyzing aggregate，并捕获 baseline/job version；
2. `get(job_id, replan_id) -> ReplanRecord`：typed 恢复，损坏 JSON/status/reference fail closed；
3. `record_analysis(..., expected_replan_version)`：原子保存 impact 和 typed decision，转入 awaiting_confirmation、replanning 或分析终态；
4. `decide(..., choice, now, expected_replan_version, expected_job_version)`：检查 15 分钟 TTL、baseline 和重复/相反决定；
5. `begin_execution(..., expected_replan_version, expected_job_version)`：只允许 auto-approved 或 approved 资源进入 replanning；
6. `record_outcome(..., expected_replan_version)`：只写 needs_input/conflict/failed/rejected/cancelled/expired 的安全摘要，不替换当前计划；
7. `commit(..., expected_replan_version, expected_job_version)`：单事务写 plan version、采用来源和 links、lineage、decision、replan completed、当前 planning attempt 的 plan version，以及 PlanningJob 当前结果/version。

同一 baseline 并发最多一个 commit 成功；另一方返回稳定 `version_conflict`。确认前不创建 plan version。SQLite 与内存 adapter 必须通过共享 contract suite。重启恢复持久化 replan 状态和版本，但不自动续跑 analyzing/replanning 后台工作。

## Provider、数据和隐私边界

- 影响分析必须纯确定性、零 Provider 调用；
- 普通开发、自动化测试和 CI 只使用 fake、synthetic、MockTransport 和临时 SQLite；
- 实际 replacement 只能复用现有窄 provider ports，只获取受影响或失效事实；
- 未单独批准 live UAT 时不得调用 DeepSeek、高德或和风天气；
- 不读取、保存或输出 `.env.local`、Key、Token、JWT、私钥、Cookie、Authorization；
- 不保存 provider 原始响应、错误 body、完整 Prompt、模型原始输出、完整日志或完整自然语言修改请求；
- Repository 和 SQLite 类型不得泄漏到 domain、Agent 或前端。

## 验收与测试矩阵

| 风险/行为 | 必需证据 |
| --- | --- |
| same-day 越界仍自动执行 | 影响分类单元/性质测试必须升级确认或拒绝 |
| 未确认执行高影响修改 | 应用/Repository 证明无写入、无 Provider 调用 |
| 取消或过期改变计划 | 当前 plan ID/version 保持不变 |
| stale confirmation 提交 | API 返回 409 version conflict |
| 两个并发 replan 同时成功 | SQLite 只允许一个原子提交 |
| 新版本覆盖旧版本 | 旧 typed plan 保持不变 |
| unknown 变为 0 | domain/API/UI 保持 amount null |
| partial 伪装 ready | contract 和 Repository 拒绝 |
| 来源错误继承 | source reuse/refresh/drop 规则测试 |
| 事务部分失败 | 无新版本、lineage 或伪完成状态 |
| retry 与 replan 混淆 | replan 不增加 attempt |
| cross-city 触发外部调用 | Provider 调用前拒绝且调用数为 0 |
| v1 数据迁移损坏 | v1→v2 round-trip、重复运行、checksum 和 rollback |
| 前端重复确认或窄屏失效 | 组件、浏览器、键盘和 390px 验收 |
| 默认测试访问真实网络 | 非 loopback 阻断，Provider 调用数为 0 |

## Step 地图

| Step | 目标 | 状态 |
| --- | --- | --- |
| Step 0 | 核对事实、清理 F-002 当前文档残留、激活任务卡并冻结执行基线 | DONE |
| Step 1 | 冻结领域模型、影响分类、replan lifecycle、API、migration、Repository、测试和 UI 设计 | DONE |
| Step 2 | TDD 实现纯领域影响分析、diff、预算和来源策略 | DONE |
| Step 3 | 实现 migration v2、Replan Repository 和 typed Decision 持久化 | DONE |
| Step 4 | 实现 replan application service、确认、并发和事务提交 | DONE |
| Step 5 | 新增窄 replan API，并保持现有 API 回归 | DONE |
| Step 6 | 实现经批准的前端修改、影响预览和确认流程 | DONE |
| Step 7 | 完成临时 SQLite 纵向测试、浏览器 QA 和独立安全/数据审查 | DONE |
| Step 8 | 完成全量门禁、用户 UAT、Git/PR/CI、合并和归档 | DONE |

## 阶段化允许文件

Step 0 已允许且本次只修改：

- `docs/README.md`；
- `docs/project-management/roadmap.md`；
- `docs/project-management/current-task.md`；
- `docs/project-management/implementation-plan.md`；
- `docs/project-management/progress.md`；
- `docs/project-management/evidence.md`。

Step 1 已批准并仅修改：

- 上述 F-003 项目管理文档；
- `docs/architecture.md`；
- `docs/api-contract.md`；
- `docs/agent-domain-spec.md`；
- `docs/design-spec.md`；
- `docs/testing-strategy.md`；
- `docs/decisions.md`。

Step 1 只做规格和设计冻结，不修改生产源码、测试、Schema、migration、API 实现或前端实现。

Step 2 待用户批准后只允许：

- `backend/src/intelligent_travel_assistant/domain/replanning.py`；
- `backend/src/intelligent_travel_assistant/domain/__init__.py`；
- `backend/tests/domain/test_replanning_commands.py`；
- `backend/tests/domain/test_replanning_impact.py`；
- `backend/tests/domain/test_replanning_change_set.py`；
- `backend/tests/domain/test_replanning_budget_sources.py`；
- 本任务卡、实施计划、进度、证据及真实受影响的 architecture/agent-domain-spec/testing-strategy。

Step 2 只实现纯领域 command、impact、change set、预算和来源策略；禁止 Repository、SQLite、migration、API、应用编排、Provider 和前端。

Step 3 已获用户批准，只允许修改以下精确文件：

- `backend/src/intelligent_travel_assistant/domain/replanning.py`；
- `backend/src/intelligent_travel_assistant/domain/__init__.py`；
- `backend/src/intelligent_travel_assistant/application/repositories/models.py`；
- `backend/src/intelligent_travel_assistant/application/repositories/ports.py`；
- `backend/src/intelligent_travel_assistant/application/repositories/__init__.py`；
- `backend/src/intelligent_travel_assistant/adapters/persistence/schema.py`；
- `backend/src/intelligent_travel_assistant/adapters/persistence/migrations.py`；
- `backend/src/intelligent_travel_assistant/adapters/persistence/repository.py`；
- `backend/src/intelligent_travel_assistant/adapters/persistence/__init__.py`；
- `backend/src/intelligent_travel_assistant/adapters/repositories/memory.py`；
- `backend/src/intelligent_travel_assistant/adapters/repositories/__init__.py`；
- `backend/tests/domain/test_replanning_commands.py`；
- `backend/tests/domain/test_replanning_decisions.py`；
- `backend/tests/application/test_replan_repository_contract.py`；
- `backend/tests/adapters/persistence/test_migrations.py`；
- `backend/tests/adapters/persistence/test_replan_repository.py`；
- `backend/tests/api/test_sqlite_trip_plans_api.py`（仅 migration v2 测试基线）；
- 本文件、实施计划、进度和证据文档；
- `docs/architecture.md`、`docs/testing-strategy.md`，仅在确有 Step 3 设计影响时修改。

Step 3 只实现 migration v2、独立 ReplanRepository、typed Decision 持久化及其内存/临时 SQLite 测试；禁止修改连接层、PlanningJobRepository contract、API、组合根、Provider、前端、依赖、环境文件或真实数据库。完成后停止，不进入 Step 4。

Step 4 已获用户批准，只允许修改：

- `backend/src/intelligent_travel_assistant/domain/replanning.py`、`domain/__init__.py`；
- 新增 `backend/src/intelligent_travel_assistant/application/replanning/{__init__,models,ports,service}.py`；
- `backend/src/intelligent_travel_assistant/application/ports/models.py`、`ports/providers.py`；
- 新增 `backend/src/intelligent_travel_assistant/application/services/provider_replanning.py`，以及 `services/__init__.py`；
- `backend/src/intelligent_travel_assistant/application/repositories/{models,ports,__init__}.py`；
- `backend/src/intelligent_travel_assistant/adapters/persistence/{repository,__init__}.py`；
- `backend/src/intelligent_travel_assistant/adapters/repositories/{memory,__init__}.py`；
- `backend/tests/domain/test_replanning_decisions.py`；
- 新增 `backend/tests/application/test_replan_service.py`、`test_provider_replanning.py`；
- `backend/tests/application/test_replan_repository_contract.py`；
- `backend/tests/adapters/persistence/test_replan_repository.py`；
- `docs/README.md`、`docs/architecture.md`、`docs/agent-domain-spec.md`、`docs/testing-strategy.md`、`docs/decisions.md`；
- roadmap、current-task、implementation-plan、progress、evidence。

Step 4 只实现 application replan、确认、并发、离线 provider-neutral 执行编排、`begin_execution/record_outcome/commit` 和原子版本提交。禁止 API/contracts、bootstrap/组合根、Schema/migration/连接层、Provider adapter、前端、依赖、环境、真实数据库和真实 Provider；完成后停止，不进入 Step 5。

## Step 4 结果

- 新增 application replan use case 与 provider-neutral 执行端口，完成幂等 reserve、确定性 analysis、15 分钟确认、取消/过期、安全失败和成功提交编排；
- ReplanRepository 新增 `begin_execution`、`record_outcome`、`commit`，内存替身与 SQLite adapter 保持相同版本、决定和冲突语义；
- SQLite 成功路径在单事务中追加 plan version、lineage 和来源关联，并更新当前 attempt/job/replan；注入中途失败时全部回滚；
- 同一 baseline 的并发 replan 只有一个提交成功，另一方稳定得到 job version conflict；确认前和非成功终态不创建新计划版本；
- ready 与可执行 partial 可作为 baseline，unknown 金额保持 `null`，partial 不提升为 ready；越界 change set 稳定收口为 conflict；
- Step 4 专项 19 项、application+persistence 回归 494 项、后端全量 1001 项通过；Ruff format/check、strict mypy、文档检查和 `git diff --check` 通过；
- 未修改 API/contracts、bootstrap/组合根、Schema/migration/连接层、Provider adapter、前端、依赖或环境；只使用临时 SQLite，未访问真实 Provider、秘密或非 loopback 网络，未进入 Step 5。

## Step 5 精确文件清单

Step 5 已获用户明确批准，只允许修改：

- 新增 `backend/src/intelligent_travel_assistant/contracts/replanning.py`；
- `backend/src/intelligent_travel_assistant/contracts/errors.py`、`contracts/__init__.py`；
- `backend/src/intelligent_travel_assistant/application/replanning/{models,service,__init__}.py`；
- `backend/src/intelligent_travel_assistant/application/repositories/{models,ports,__init__}.py`，仅补充 completed replan 的 typed change-set 读取投影；
- `backend/src/intelligent_travel_assistant/adapters/persistence/{repository,__init__}.py` 与 `adapters/repositories/{memory,__init__}.py`，仅实现同一投影；
- 新增 `backend/src/intelligent_travel_assistant/api/replans.py`；
- `backend/src/intelligent_travel_assistant/api/{errors,__init__,trip_plans}.py`；
- `backend/src/intelligent_travel_assistant/app.py`，仅增加可注入 replan service 和路由装配；
- 新增 `backend/tests/contracts/test_replanning_contracts.py`、`backend/tests/api/test_replans_api.py`；
- `backend/tests/application/test_replan_service.py`、`test_replan_repository_contract.py`；
- `backend/tests/adapters/persistence/test_replan_repository.py`；
- `backend/tests/api/test_trip_plans_api.py`、`test_sqlite_trip_plans_api.py`，仅做既有 API 精确回归或路由边界验证；
- `docs/README.md`、roadmap、current-task、implementation-plan、progress、evidence；必要时同步已冻结事实到 api-contract、architecture、testing-strategy 和 decisions。

Step 5 只实现三个窄 replan API、严格 DTO、安全错误映射、completed result/change-set 投影和最小可注入组合根。明确禁止 Schema、migration、SQLite 连接层、Provider adapter、前端、依赖/lockfile、环境、真实数据库、真实 Provider、历史列表、版本比较/恢复、批量清空、多城市、多日或 Step 6。

## Step 5 结果

- 新增严格 `ReplanRequest`、四种 tagged command、decision、impact、change-set 和 `ReplanResponse` 公共 DTO；额外字段、完整 Prompt、未知 operation 和非法 choice 均由统一 422 拒绝；
- 实现 create/get/decision 三个窄端点、Location、202/200、404/409/422/安全 500 映射；未新增列表、compare、restore 或批量 API；
- API 将 auto/approve 执行作为 background task 调度并先返回 `replanning` 快照；相同决定重放不重复执行，相反决定冲突，确认恰好 15 分钟到期返回 409 并持久化 expired；
- completed replan 的 typed result/change-set 由内存与 SQLite Repository 一致恢复；非 completed 不投影结果且不替换原计划；
- `create_app` 只新增可注入 replan application service 和固定路由；默认组合仍不读取秘密、不访问 Provider，完整 SQLite 纵向装配留在后续批准阶段；
- Step 5 专项 31 项、API/bootstrap/application/persistence/contracts 回归 571 项、后端全量 1016 项通过；108 文件 format、Ruff、61 source files strict mypy 通过；
- 未修改 Schema、migration、连接层、Provider adapter、前端、依赖、lockfile 或环境；未创建真实数据库，未调用真实 Provider，未进入 Step 6。

## Step 6 精确文件清单

Step 6 已获用户明确批准，只允许修改：

- 新增 `frontend/src/replanningApi.ts`、`frontend/src/replanningApi.test.ts`；
- 新增 `frontend/src/ReplanPanel.tsx`、`frontend/src/ReplanPanel.test.tsx`；
- `frontend/src/App.tsx`、`frontend/src/App.test.tsx`；
- `frontend/src/PlanningStage.tsx`、`frontend/src/PlanningStage.test.tsx`；
- `frontend/src/TripPlanResult.tsx`、`frontend/src/TripPlanResult.test.tsx`；
- `frontend/src/styles.css`；
- `docs/README.md`、roadmap、current-task、implementation-plan、progress、evidence；
- `docs/testing-strategy.md`，仅记录实际完成的 Step 6 组件测试证据。

Step 6 只实现现有结果页内的四种结构化修改入口、影响预览、15 分钟确认/取消、replanning 状态、completed baseline→result 差异、unknown/partial 与安全错误展示、焦点恢复和窄屏布局。禁止修改后端、Schema、migration、Repository、API 契约、Provider、依赖/lockfile、环境文件、真实数据库、历史列表、任意版本比较/恢复、多城市、多日、登录、同步或进入 Step 7；浏览器纵向验收留在 Step 7。

## Step 6 结果

- 新增严格 replan API client/parser，只接受三个既有窄端点和冻结响应形状；额外字段、不一致 completed 投影和疑似秘密错误文本 fail closed；
- 结果页为 ready/可执行 partial 提供替换、删除、调整时间和同日完整重排入口，conflict 不展示可执行入口；
- 面板展示 impact categories、日期、路线、直接/传递对象、预算 unknown、来源 reuse/refresh/drop 与 freshness，并明确原计划在 pending/失败/取消时不变；
- 高影响确认默认焦点不落在 approve，重复决定在 pending 时禁用；cancel/关闭恢复触发入口焦点；completed 才切换 typed result，并仅显示本次 baseline→result change set；
- RED 阶段两个新模块缺失导致专项测试收集失败；GREEN 后前端 8 个测试文件共 73 项通过，lint、typecheck、format check 和 Vite build 通过；
- 未修改后端、Schema/migration、Repository、API 契约、Provider、依赖、环境或数据库；未读取秘密、调用真实 Provider、访问非 loopback 网络或进入 Step 7。
- F-003 累计工作区超过任务卡的 35 文件/3,000 行停止阈值后，用户明确选择并批准 stacked PR；Step 8 随后获批并完成。

## Step 7 精确文件清单

Step 7 已获用户明确批准，只允许修改：

- 新增 `backend/tests/api/test_sqlite_replans_api.py`，只覆盖临时 SQLite 下 replan API、重启恢复、幂等、版本/并发冲突和原计划保留；
- 新增 `backend/tests/browser_replan_support.py`，只提供绑定 `127.0.0.1` 的 deterministic synthetic 浏览器测试应用；
- `docs/README.md`、`docs/project-management/roadmap.md`、本文件、`implementation-plan.md`、`progress.md`、`evidence.md`；
- `docs/testing-strategy.md`，只记录实际完成的 Step 7 纵向、浏览器和独立审查证据。

浏览器命令产生的截图、trace 和临时输出只允许位于被 Git 忽略的本机测试输出目录，不作为生产资产提交。Step 7 禁止修改任何生产源码、既有 Schema/migration、Repository/API contract、前端、Provider、依赖/lockfile、环境文件和真实数据库；禁止读取秘密、调用真实 Provider、访问非 loopback 网络、创建分支或远程写入；不得进入 Step 8。

用户随后明确批准 Step 7 最小生产修复范围，额外允许修改 `application/replanning/service.py`、SQLite/内存 ReplanRepository 及对应 application、Repository、临时 SQLite/API 测试；`browser_replan_support.py` 可修复日期漂移造成的本地验收夹具假失败。该授权不包含 Schema、migration、Repository port、公开 API、Provider、前端、依赖、环境或 Step 8。

## Step 7 完成结果

- 新 plan version 继续使用 planning job/attempt trace；独立 replan trace 只保留在 replan/decision 审计记录中，SQLite 提交与重启水合不再触发 `stored_plan_version_mismatch`；
- SQLite 与内存 Repository 的 decide/begin_execution/commit 均同时校验调用方版本、当前 job version 和 replan 创建时捕获的 `expected_job_version`；旧确认在 executor 前稳定冲突，执行期竞争在应用层持久化为 `conflict`，原计划保持不变；
- 同一 request ID 仍保持幂等；不同 baseline 继续返回 baseline/version conflict。Schema、migration、Repository port 和公开 API 未改变；
- 临时 SQLite 纵向、application/Repository/API 相关回归共 219 项通过；后端全量 999 项、前端 73 项、Ruff、format、strict mypy、ESLint、TypeScript 和 build 均通过；
- 本机 synthetic 浏览器复验 completed、failed、version conflict；成功显示本次 change set，失败/冲突保留原计划，`390×844` 下 `scrollWidth == clientWidth == 375`，资源 origin 只有 `http://127.0.0.1:5173`；
- 原 medium finding 已由失败回归和真实 SQLite 边界复验关闭；过期确认 executor 调用为 0，并保留安全 `replan_job_version_conflict` 语义；
- 私密文本候选已由临时 SQLite probe 反证：同事务完成水合会经 `_load_json` 拒绝 synthetic 私密标记并 rollback；跨 job decision 候选要求任意本地数据库写权限，不构成当前本地威胁模型下的新增越权；
- 未修改 Schema、migration、Repository port、公开 API、Provider、前端、依赖或环境；未创建真实数据库，未读取秘密，未调用真实 Provider，未进入 Step 8。

## Step 8 执行与交付基线

- 用户已明确批准 Step 8 的全量门禁、离线 UAT、stacked PR、CI、按依赖合并和归档；
- 首次统一门禁在 strict mypy 发现一个测试 helper 缺少返回类型；仅在已批准测试文件补充 `ReplanRecord` 返回类型后，从统一入口完整复跑通过；
- 本地统一门禁通过：后端 999 项、前端 73 项、文档检查器 23 项，以及锁文件、format、lint、strict mypy、TypeScript 和 Vite build 全绿；
- 本机 synthetic UAT 完成“创建计划 → 调整时间 → 影响预览 → 确认 → completed 新版本/change set”；`390×844` 下 `scrollWidth == clientWidth == 375`，浏览器控制台 0 error/0 warning，全部请求仅访问 `127.0.0.1:5173`；
- 本次 UAT 不读取 `.env.local`，不调用真实 Provider，不创建真实 SQLite；F-001 的真实 UAT 历史和混合交通离线边界保持不变；
- 当前累计范围为 48 个生产/测试文件、约净新增 8,596 行；已按批准的 stacked PR 拆为领域、持久化/应用、API/前端/验收三层；
- 本地主题提交为 `c441327`（domain）、`d34f0bc`（persistence/application）、`bf949a1`（API）和 `b103b64`（UI）；PR、远程 CI、合并和归档仍待完成，不得提前把 F-003 标记为 DONE。

## Step 3 结果

- migration v2 严格追加 `replan_requests`、`plan_version_lineage` 和必要索引，保留 v1 数据、checksum、顺序、事务 rollback 与高版本 fail-closed；
- 新增独立 ReplanRepository port、内存 contract double、SQLite adapter 和 typed Decision 映射，PlanningJobRepository 与 PlanningJob 11 状态保持不变；
- API SQLite 生命周期测试明确验证 migration 1/2，并以 version 3 验证未来数据库拒绝启动；没有修改 API 生产实现或公开契约；
- Step 3 专项 12 项、相关 persistence/application/API 回归 81 项、后端全量 963 项通过；Ruff check、Ruff format 和 strict mypy 通过；
- 只使用临时 SQLite；未创建真实业务数据库，未读取秘密，未调用真实 Provider，未进入 Step 4。

## Step 2 结果

- 新增纯领域 `replanning.py`，实现四种 frozen/slotted command、八类可组合 impact、AUTO/CONFIRM/REJECT disposition、直接/传递依赖和确定性重校验集合；
- 同日重排必须精确覆盖该日完整活动集合；cross-day 只能由依赖图推导，cross-city 为 REJECT，只有精确 `{same_day_low}` 为 AUTO；
- 来源策略只返回 `reuse/refresh/drop`，stale/unknown-validity 必须 refresh，仍被其他对象引用的共享来源不能误 drop，refresh/drop 重叠 fail closed；
- 预算重算复用 Decimal/unknown 规则，unknown 保持 `amount=None`，已知超支、unknown 增加或可判定性下降标记 budget risk；
- change set 只比较 baseline→result，区分 added/removed/changed 和 activity/route/schedule/cost/source code；新增对象必须通过 origin ref 接受局部性校验；
- 35 项新增测试通过；领域 178 项、后端全量 981 项、Ruff、format 和 strict mypy 通过；
- 未实现或修改 Repository、SQLite、migration、API、Provider、前端、依赖或环境；未访问真实 Provider、秘密或非 loopback 网络。

预计后续范围：

- `backend/src/intelligent_travel_assistant/domain/**` 中的 replan 领域模块；
- `backend/src/intelligent_travel_assistant/application/replanning/**` 和窄 Repository models/ports；
- `backend/src/intelligent_travel_assistant/adapters/persistence/**`；
- `backend/src/intelligent_travel_assistant/api/**` 与 contracts 中 F-003 窄扩展；
- bootstrap/app 的最小装配；
- 对应 `backend/tests/**`；
- `frontend/src/**` 中的 replan API、状态、交互和测试；
- 必要的当前架构、设计、测试、决策和项目管理文档。

## 全程禁止文件和能力

- `.env.local`、任何真实秘密或本地私钥；
- 未批准的 provider adapter、依赖、lockfile、CI 权限和环境配置；
- 真实业务 SQLite/DB 文件；
- F-001/F-002 归档任务卡内容改写；
- 历史列表、版本恢复、清空全部数据、多城市、多日、登录、同步、云数据库、公网部署或交易能力；
- 未单独授权的真实 Provider 调用；
- 未获当前 Step 授权的分支、提交、推送、PR、合并或远程写入。

## Step 0 结果

- 项目规则、文档地图、roadmap、归档卡、当前架构/测试/决策、源码契约和 Git/CI 已核对；
- `main`、`origin/main` 均为 `c836138240473f079565527b13a0d53516235c45`，Step 0 开始时工作区干净；
- 最终 main CI run `31924427372` 为 `success`；
- F-002 的旧 ACTIVE/TODO/PR OPEN 残留已从 current-task 和 implementation-plan 当前正文移除；
- F-003 已按批准决策激活，Step 0–1 为 DONE；
- 当前 Schema 仍为 version 1，没有创建或修改数据库；
- 没有修改源码、测试、API、Repository、migration、前端、依赖或环境文件；
- 没有读取秘密、调用真实 Provider、访问非 loopback 网络、创建分支或执行 Git 远程写入。

## 风险、回滚和停止条件

- D-004 的“应用状态机包含确认/重规划”已由 D-011 收口为独立 replan lifecycle；不得把它重新加入 `PlanningJob.status`；
- migration v2 必须无损保留 v1 数据；旧应用遇到高版本数据库继续 fail closed，不自动 down migration；
- conflict/failed/取消/过期不替换当前计划；
- UI 设计未批准不得进入前端实现；
- 预计超过 35 个生产/测试文件或净新增 3000 行时停止并请求重新切片或 stacked PR 决策；
- 需要新增依赖、改变城市/日期/住宿锚点、版本恢复、历史列表、完整自然语言保存、秘密或真实 Provider 时立即停止；
- 连续三次出现同一阻塞时停止报告。

## 文档更新契约

- 当前任务入口：本文件；
- 当前实施：`implementation-plan.md`；
- 当前状态：`progress.md`；
- 可复现证据：`evidence.md`；
- 路线状态：`roadmap.md`；
- Step 1 按真实设计变化更新 architecture、api-contract、agent-domain-spec、design-spec、testing-strategy 和 decisions；
- 完成后归档到 `docs/archive/task-cards/F-003-local-replanning-impact-confirmation.md`；
- 不把逐轮 Prompt、完整日志、秘密或临时产物写入长期文档。

## 完成定义

- 四种批准操作完成端到端闭环；
- 影响范围由确定性代码计算，自动/确认边界有负向证明；
- 取消、过期和版本冲突不改变当前计划；
- 成功重规划追加新版本和 lineage，旧版本不覆盖；
- unknown 不转为 0，partial 不伪装 ready；
- 来源继承、刷新和 drop 可追溯；
- v1→v2 migration、事务、并发和回滚通过；
- 现有 API 兼容，新 API 与 UI 通过；
- 默认测试不读取秘密、不访问真实 Provider或非 loopback 网络；
- UI 设计、真实页面视觉验收、独立 QA 和用户 UAT 完成；
- format、lint、typecheck、test、build、docs 和 CI 全绿；
- Git diff、提交、PR、合并、文档收口和归档完成；
- F-001/F-002 历史事实保持不变；
- current-task 重新回到无活动任务。
