# 当前实施计划

## 当前状态

- 当前任务：`F-003 局部重规划与影响确认`
- 任务状态：`ACTIVE`；任务卡状态：`APPROVED`
- 已完成：`Step 0、Step 1、Step 2、Step 3、Step 4、Step 5、Step 6、Step 7`
- 当前 Step：`Step 8`，状态 `ACTIVE`；用户已明确批准进入
- 下一动作：完成 stacked PR 推送/CI/依赖顺序合并、main CI 和归档收口
- 当前分支：`feat/f-003-local-replanning-confirmation`；三层本地 stack 已建立
- 基线提交：`c836138240473f079565527b13a0d53516235c45`
- main CI：run `31924427372`，`success`

## Step 0 结果

- 核对项目规则、文档地图、roadmap、F-001/F-002 归档、当前架构/测试/决策、相关源码契约、Git 和 CI；
- 确认 F-001 `PARTIAL`、Step 45M `FAIL`、Step 45T `PASS`、unknown 不为 0、混合交通 fallback 仅离线证据；
- 确认当前 PlanningJob 为 11 状态，现有 Repository 没有 replan port，decision 只有基础表，migration 只有 version 1，前端没有局部重规划；
- 按批准任务卡采用独立 replan lifecycle；旧 D-004 状态机表述留给 Step 1 在长期文档中正式解释和收口；
- 清除 current-task 与本文件中 F-002 的 ACTIVE/TODO/PR OPEN 当前状态残留；
- 激活 F-003，建立 Step 地图、阶段化允许文件和停止条件；
- 未修改源码、测试、Schema、migration、API、前端、依赖、环境或数据库；
- 未读取 `.env.local` 或秘密，未调用真实 Provider，未访问非 loopback 网络；
- 未创建分支、提交、推送、PR 或合并。

## Step 1 唯一目标

冻结实现前规格，不写生产代码：

1. typed replan command、impact、change set、confirmation、decision 和 lifecycle；
2. same-day 自动与高影响确认的确定性规则；
3. retry、replan、版本恢复的边界；
4. Repository port、事务、幂等、expected version 和并发冲突；
5. migration v2、`replan_requests`、`plan_version_lineage` 和现有 decision_records 映射；
6. 三个窄 replan API 的请求、响应和稳定错误；
7. 来源 reuse/refresh/drop、预算、unknown 和终态语义；
8. UI 信息架构、影响预览、确认/取消/过期/冲突和视觉门禁；
9. 测试矩阵、文件估算和一个 PR/stacked PR 阈值复核。

## Step 1 允许文件

- `docs/README.md`；
- `docs/project-management/roadmap.md`；
- `docs/project-management/current-task.md`；
- `docs/project-management/implementation-plan.md`；
- `docs/project-management/progress.md`；
- `docs/project-management/evidence.md`；
- `docs/architecture.md`；
- `docs/api-contract.md`；
- `docs/agent-domain-spec.md`；
- `docs/design-spec.md`；
- `docs/testing-strategy.md`；
- `docs/decisions.md`。

Step 1 已按用户批准执行并完成；上述清单只记录本 Step 实际文档边界，不授权实现。

## Step 1 禁止

- 生产源码、测试、Schema、migration、Repository、API 或前端实现；
- 依赖、lockfile、环境文件、CI 或真实数据库；
- `.env.local`、秘密、真实 Provider 和非 loopback 网络；
- 分支、提交、推送、PR、合并；
- 历史列表、任意版本比较/恢复、清空全部、多城市、多日、住宿锚点/城市/日期修改；
- 未经 UI 设计批准进入前端实现；
- 自动进入 Step 2。

## 后续 Step 地图

| Step | 独立验证目标 | 状态 |
| --- | --- | --- |
| Step 0 | 事实、执行基线和文件清单 | DONE |
| Step 1 | 规格、架构、数据、API、测试和 UI 设计冻结 | DONE |
| Step 2 | 纯领域影响分析、diff、预算和来源策略 | DONE |
| Step 3 | migration v2、Replan Repository、Decision 持久化 | DONE |
| Step 4 | application replan、确认、并发和事务提交 | DONE |
| Step 5 | replan API 与现有 API 回归 | DONE |
| Step 6 | 前端修改、影响预览和确认流程 | DONE |
| Step 7 | 临时 SQLite 纵向测试、浏览器 QA 和独立审查 | DONE |
| Step 8 | 全量门禁、UAT、Git/PR/CI、合并和归档 | ACTIVE |

## Step 1 冻结结果

- 四种 typed command、八类可组合 impact、reuse/refresh/drop、change set 和 unknown/partial 语义已冻结；
- PlanningJob 11 状态保持不变；独立十状态 replan lifecycle 和 15 分钟 confirmation TTL 已冻结；
- 三个窄 API、严格 DTO、幂等/版本/确认冲突和现有 API 兼容边界已冻结；
- migration v2 只新增 `replan_requests`、`plan_version_lineage`，复用 typed `decision_records`，无损保留 v1；
- 新增独立 ReplanRepository port；PlanningJobRepository 不变；成功提交单事务，非成功终态保留原计划；
- Step 2–7 分层测试矩阵和现有结果页内局部调整面板已冻结；未实施任何代码、Schema、migration、API 或 UI。

## Step 2 唯一目标和允许文件

Step 2 用 TDD 实现纯领域 `ReplanCommand`、`ImpactAnalysis`、`PlanChangeSet`、预算重算和来源 reuse/refresh/drop 策略，不接触持久化或应用服务。

只允许：

- `backend/src/intelligent_travel_assistant/domain/replanning.py`；
- `backend/src/intelligent_travel_assistant/domain/__init__.py`；
- `backend/tests/domain/test_replanning_commands.py`；
- `backend/tests/domain/test_replanning_impact.py`；
- `backend/tests/domain/test_replanning_change_set.py`；
- `backend/tests/domain/test_replanning_budget_sources.py`；
- F-003 项目管理文档和真实受影响的 architecture/agent-domain-spec/testing-strategy。

禁止 Repository、SQLite、migration、API、前端、依赖、环境、真实 Provider、分支和远程写入。完成后停止，不进入 Step 3。

## Step 2 完成证据

- RED：四个新增测试模块最初因 F-003 类型未导出而在收集阶段失败；
- GREEN：35 项 command/impact/change-set/budget/source 测试通过；
- 回归：领域 178 项、后端全量 981 项通过；
- 静态门禁：后端 Ruff check、Ruff format check、strict mypy 均通过；
- 边界：实现只在批准的 domain 模块、domain 导出和四个测试文件内；没有持久化、HTTP、Provider 或前端副作用。

## Step 3 唯一目标和精确文件清单

Step 3 已完成 migration v2、独立 ReplanRepository 和 typed Decision 持久化；未实现应用服务、确认流程、API、前端或 Provider 接入。

允许修改：

- `backend/src/intelligent_travel_assistant/domain/replanning.py`、`domain/__init__.py`；
- `backend/src/intelligent_travel_assistant/application/repositories/models.py`、`ports.py`、`__init__.py`；
- `backend/src/intelligent_travel_assistant/adapters/persistence/schema.py`、`migrations.py`、`repository.py`、`__init__.py`；
- `backend/src/intelligent_travel_assistant/adapters/repositories/memory.py`、`__init__.py`；
- `backend/tests/domain/test_replanning_commands.py`、`test_replanning_decisions.py`；
- `backend/tests/application/test_replan_repository_contract.py`；
- `backend/tests/adapters/persistence/test_migrations.py`、`test_replan_repository.py`；
- `backend/tests/api/test_sqlite_trip_plans_api.py`，仅更新 migration v2 测试基线；
- 本文件、`current-task.md`、`progress.md`、`evidence.md`；
- `docs/architecture.md`、`docs/testing-strategy.md`，仅在确有 Step 3 影响时修改。

禁止修改连接层、现有 PlanningJobRepository contract、API、组合根、Provider、前端、依赖、环境文件、真实数据库和其他未列文件；不进入 Step 4。

## Step 3 完成证据

- API SQLite 生命周期 8 项、Step 3 专项 12 项、相关 persistence/application/API 回归 81 项、后端全量 963 项通过；
- Ruff check、Ruff format check、strict mypy 通过；
- migration 历史明确为 version 1/2，version 3 继续触发高版本 fail-closed；
- 未修改 API 生产实现、连接层、Provider、前端、依赖、环境或真实数据库；
- Step 4 保持 TODO，等待用户单独批准。

## Step 4 唯一目标和精确文件清单

Step 4 已完成 application replan、确认、并发、离线 provider-neutral 执行编排和原子事务提交。精确生产、测试与文档文件以 current-task 的 Step 4 清单为准。

本 Step 禁止 API/contracts、bootstrap/组合根、Schema/migration/连接层、Provider adapter、前端、依赖、环境、真实数据库和真实 Provider；不进入 Step 5。

## Step 4 完成证据

- application service 编排 reserve → analysis → confirmation/auto → execution → outcome/commit，并保持重复创建和相同确认幂等；
- 15 分钟过期、相反决定、stale job/replan version 和同 baseline 并发均 fail closed；
- SQLite commit 单事务追加 plan version、source link、lineage 并更新当前 attempt/job/replan；注入 lineage 写入失败时完整回滚；
- provider-neutral executor 仅依赖注入端口，change set 超出已分析对象时返回安全 conflict；没有连接真实 Provider；
- Step 4 专项 19 项、application+persistence 494 项、后端全量 1001 项、Ruff、format、strict mypy、文档和 diff 门禁通过；
- Step 5 保持 TODO，未修改 API、组合根、Schema/migration/连接层、Provider adapter、前端、依赖或环境。

## Step 5 唯一目标和精确文件清单

Step 5 已获用户批准，只实现三个窄 replan API、严格公共 DTO、安全错误映射、completed result/change-set 读取投影和 `create_app` 的最小可注入装配。精确生产、测试和文档文件以 current-task 的 Step 5 清单为准。

禁止 Schema/migration/连接层、Provider adapter、前端、依赖、环境、真实数据库、真实 Provider、历史列表、版本比较/恢复、批量清空、多城市、多日和 Step 6。

## Step 5 完成证据

- 严格公共 DTO 覆盖四种 tagged command、decision、impact、result 和 change set，拒绝额外字段、Prompt 和未知操作；
- 三个窄 API 覆盖 Location、202/200、404/409/422/安全 500、幂等、确认冲突、精确 TTL 和 scope 拒绝；
- auto/approve 先返回 replanning 快照并由 background task 执行；同决定重放不重复执行，非成功终态保持原计划；
- completed typed result/change-set 可由内存和 SQLite Repository 读取；现有 POST/GET/retry/DELETE 回归保持不变；
- Step 5 专项 31 项、相关回归 571 项、后端全量 1016 项、Ruff、format 和 strict mypy 通过；
- 未进入 Step 6，未修改 Schema/migration/连接层、Provider adapter、前端、依赖或环境。

## Step 6 唯一目标和精确文件清单

Step 6 已获用户批准，只实现结果页内四种结构化修改入口、影响预览、确认/取消、执行状态、completed 差异和可访问恢复流程。精确生产、测试和文档文件以 current-task 的 Step 6 清单为准。

禁止后端、Schema/migration、Repository、API 契约、Provider、依赖、环境、真实数据库、历史列表、版本比较/恢复、多城市、多日和 Step 7。浏览器与临时 SQLite 纵向验证留在 Step 7。

## Step 6 完成证据

- 新增严格 replan client/parser 与结果页内局部调整面板，覆盖四入口、结构化编辑、impact、确认/取消、replanning、completed diff、安全终态、unknown/partial 和焦点恢复；
- 两个新模块缺失的 RED 证据已取得；GREEN 后前端 73 项测试通过；lint、typecheck、format check 与 Vite build 通过；
- 首轮并行全门禁中一个既有表单测试因 5 秒超时失败；串行复跑全前端 73 项通过，判定为并行资源竞争而非产品回归；
- 未修改后端、Schema/migration、Repository、API 契约、Provider、依赖、环境或数据库；未进入 Step 7。
- 累计 46 个生产/测试文件、估算净新增约 8,360 行已超过任务卡停止阈值；用户已确认采用 stacked PR，建议按领域 → 持久化/应用 → API/前端/验收组织，精确 Git 边界留待交付 Step 冻结。

## Step 7 唯一目标和精确文件清单

Step 7 已获用户批准，只做临时 SQLite 纵向测试、本机 synthetic 浏览器 QA 和独立安全/数据审查。允许新增 `backend/tests/api/test_sqlite_replans_api.py`、`backend/tests/browser_replan_support.py`，并更新 `docs/README.md`、roadmap、current-task、implementation-plan、progress、evidence；`docs/testing-strategy.md` 只可记录实际测试证据。浏览器临时产物必须被 Git 忽略。

禁止修改生产源码、Schema/migration、Repository/API contract、前端、Provider、依赖/lockfile、环境文件或真实数据库；禁止读取秘密、调用真实 Provider、访问非 loopback 网络、创建分支、提交、推送或创建 PR。完成后停止，不进入 Step 8。

## Step 7 完成证据

- 临时 SQLite 纵向 3 项中 failed 路径通过，成功/重启和并发路径因 replan trace 与 planning job/attempt trace 不一致而失败；事务正确 rollback，但资源停留 `replanning`；
- 浏览器在桌面和 `390×844` 验证 completed、failed、expired、version conflict，原计划保留、completed diff、零横向溢出和 loopback-only 请求成立；
- 33 个变更源/测试文件独立安全审查完成，确认 stale confirmation 未绑定 captured job version 的 medium finding；私密文本与跨 job decision 两个候选被反证排除；
- 下一次授权必须同时修复 trace/计划版本水合一致性，以及 decide/begin_execution 在执行前对持久化 `expected_job_version` 的检查；保持 Schema、migration、公开 API、Provider、前端、unknown/partial 和隐私边界不变；
- 用户已批准最小修改 application replan service、SQLite/内存 ReplanRepository 及对应测试；Schema、migration、公开 API、Provider、前端、unknown/partial 和隐私边界保持不变；
- 修复后聚焦回归 18 项、相关领域/contract/application/Repository/API 回归 219 项、后端全量 999 项和前端 73 项通过；Ruff、format、strict mypy、ESLint、TypeScript 和 build 通过；
- SQLite 成功提交、幂等、重启恢复和同 baseline 并发路径通过；stale confirmation 在 executor 前冲突，竞争失败持久化为 conflict；planning plan version 使用原 planning trace，replan trace 仍独立留存；
- 浏览器复验 completed、failed 和 version conflict，`390×844` 无横向溢出且只有 loopback 资源；Step 7 标记 DONE，Step 8 保持 TODO。

## Step 8 交付计划与当前证据

- 独立复审阻塞已在既定 Step 7 最小生产范围内关闭；最终本地统一门禁通过后端 1007、前端 76、文档检查器 24，并覆盖全部静态、类型、锁文件和构建门禁；
- synthetic loopback UAT 已复验影响预览、确认、completed 新版本/change set、确认/完成焦点、完整 change ref、390px 零横向溢出和 0 console error/warning；没有真实 Provider 或真实数据库；
- stack 1：`feat/f-003-replanning-domain`，base `main`，提交 `c441327`；
- stack 2：`feat/f-003-replanning-persistence`，base stack 1，提交 `d34f0bc`；
- stack 3：`feat/f-003-local-replanning-confirmation`，base stack 2，提交 `bf949a1`、`b103b64` 和本 Step 文档提交；
- 每层必须独立通过 Windows offline CI；按 stack 1 → stack 2 → stack 3 顺序合并并在每次 retarget 后复验；
- 三层全部合并且 main CI 通过后，才允许创建归档提交，将任务卡迁入 archive，并把 current-task 重置为无活动任务。

## 停止条件

- 任一已批准产品、数据、隐私或 API 边界需要改变；
- migration v2 无法无损保留 v1；
- 需要新增依赖、读取秘密或调用真实 Provider；
- 需要版本恢复、历史列表、跨城市、多日、登录、同步或公网能力；
- UI 设计未批准但要求进入实现；
- 预计超过 35 个生产/测试文件或净新增 3000 行而未重新批准；
- 文档、代码、Schema 或 Git 事实无法一致解释。

## 权威入口

- 任务卡：[current-task.md](./current-task.md)
- 进度：[progress.md](./progress.md)
- 路线图：[roadmap.md](./roadmap.md)
- 证据：[evidence.md](./evidence.md)
