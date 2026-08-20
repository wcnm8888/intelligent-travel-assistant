# 当前实施计划

## 当前状态

- 当前任务：`F-004B1 多城市领域、用户提供的城际段与离线约束`
- 任务状态：`ACTIVE / APPROVED`
- 等待用户批准 Step 8
- Step 0–7：`DONE`
- 当前分支：`feat/f-004b1-multicity-ui-delivery`
- 基线：`main == origin/main == 1a3e0a050721c72a6e83941f0cb5b2077decb1c7`
- 本轮停止点：Step 7 已收口；四层 Draft PR 与 CI 已完成，不进入 merge、main CI 或归档

## Step 0：执行基线与治理收口

唯一目标：在不进入实现的前提下，复核 F-004A 归档基线并激活已批准的 F-004B1。

状态：`DONE`

完成结果：

- 复核 main、origin/main、HEAD、干净工作区和归档提交一致；
- 复核 PR #13–#18 与 CI run `32360800884`；
- 确认 current-task 原先没有活动任务；
- 写入完整 F-004B1 任务卡并激活 roadmap；
- roadmap 顺序调整为 F-004B1 → F-005 → F-004B2；
- implementation-plan 切换为 Step 0–8；
- product-brief 与 api-contract 的 F-004A 当前状态漂移已修正；
- 新增 D-013，固化 V3、schema v2、全 V3 replan 拒绝、Provider/隐私和四层 stacked PR 决策；
- 建立“核心文件清单 + 受控相邻扩展”治理；
- 从干净 main 创建首层本地分支；
- 没有提交、push、PR、merge、源码、测试、数据库、migration、依赖、秘密读取或 Provider 调用。

## Step 1：实现前设计冻结

唯一目标：把已批准任务卡转写为可实现、可测试的精确领域/API/Repository/Provider/UI 契约，不实现生产代码。

状态：`DONE`

核心文件：

- `docs/architecture.md`
- `docs/api-contract.md`
- `docs/agent-domain-spec.md`
- `docs/design-spec.md`
- `docs/testing-strategy.md`
- `docs/decisions.md`
- 对应五份状态文档

必须冻结：

- V3 城市停留、住宿夜数、城际段、转移日、缓冲、活动数、预算、来源和终态不变量；
- legacy/V2/V3 严格判别、URI、fingerprint 和稳定错误语义；
- Repository typed union、schema v2 typed JSON、旧应用 fail closed 和无 migration v3 证明；
- V3 replan 写前拒绝顺序；
- 按城市 Provider 编排预算、deadline、并发、取消和完全离线测试边界；
- 前端输入、错误定位、结果信息架构、离线读取和响应式/可访问性；
- 分层测试矩阵、红绿证明和每个后续 Step 的精确核心文件。

停止条件：出现任何未批准产品/API 语义、migration v3、新依赖、新 Provider、隐私变化或实现需求。

完成结果：

- architecture 冻结独立 V3 类型、城市/夜数/段/每日城市骨架、缓冲、预算、来源、终态和分层数据流；
- api-contract 冻结同 URI 三分支 discriminator、V3 request/plan/response 精确字段、fingerprint、schema v2 水合和 replan 前置拒绝；
- agent-domain-spec 冻结用户段 immutable、城市命名空间、确定性排程、调用预算/并发/deadline 和隐私日志；
- design-spec 冻结显式单/多城市选择、城市停留卡、相邻段卡、错误定位、V3 结果/恢复和 desktop/390px 门禁；
- testing-strategy 冻结分层正负矩阵、legacy/V2 golden、schema 1/2 不变、intercity provider 0 和 Step 2–7 RED/GREEN 顺序；
- D-013 更新为 `APPROVED_AND_FROZEN`；未发现 migration v3、新依赖、新 Provider 或隐私边界变化需求；
- 未修改源码、测试、前端、fixture、Schema、migration、数据库、依赖或 lockfile；未读取秘密或调用 Provider。

## Step 2：多城市领域与 V3 contracts

唯一目标：以 TDD 实现纯领域模型、V3 contracts 和确定性校验，不进入持久化/API/Provider/UI。

状态：`DONE`

核心文件：

- `backend/src/intelligent_travel_assistant/contracts/trip_planning.py`
- `backend/src/intelligent_travel_assistant/domain/**` 中经 Step 1 冻结的多城市/排程/预算入口
- 对应 `backend/tests/**` 领域与 contract 测试
- 必要 synthetic fixture
- 对应五份状态文档

验证重点：

- 2/3 城市、3–7 日、每城至少一晚和夜数总和；
- 城市/日期/住宿/城际段连续性；
- 同日一次转移、无跨夜/第三城市、转移日最多一项活动；
- 三种方式缓冲和窗口冲突；
- user_provided/unknown 费用和五种终态；
- legacy/V2 golden 与 fingerprint 不变。

完成结果：

- 首轮 RED 因纯多城市领域类型与 `TripPlanRequestV3` 尚不存在而在 collection 阶段失败；最小实现后新增测试转绿；
- 第二轮 RED 证明 plan 缺少跨日城市连续性、response 未绑定 summary 夜数派生转移日；最小修复后转绿；
- 第三轮 RED 证明 V3 response 未拒绝携带 error 的 ready；对齐现有结果终态规则后，ready/partial/conflict/needs_input/failed 正负 shape 全部转绿；
- 新增纯领域 `CityStay`、`MultiCityTrip`、用户段、日排程、三种缓冲、逐城住宿预算、城际费用和五终态分类；
- 新增独立严格 V3 request/plan/response、城市/段/日 DTO、用户来源约束和 plan/response final validation；
- V3 未加入 `PlanningRequest/PlanningPlan/PlanningResponse` union；该集成明确留给 Step 3；
- 定向 domain/contracts/兼容回归 `102 passed`；全仓 Ruff format/lint 与 strict mypy 对 126 个文件通过；
- legacy 固定 digest `f8e8a85d192745f703d968695945c2fa4200f224d4e8ae9162a69abd57bf7edd` 和 V2 fingerprint 定向回归通过；
- 未进入 Repository/API/SQLite、Provider、前端、Schema/migration、依赖、lockfile、数据库、秘密或外部调用。

## Step 3：Repository、SQLite 与 API 兼容

唯一目标：实现 V3 typed union 的内存/SQLite 往返和同 URI API，不进入 Provider 编排或前端。

状态：`DONE`

核心文件：

- `backend/src/intelligent_travel_assistant/application/repositories/**`
- `backend/src/intelligent_travel_assistant/adapters/repositories/**`
- `backend/src/intelligent_travel_assistant/adapters/persistence/repository.py`
- `backend/src/intelligent_travel_assistant/api/**` 中 trip planning/replan 窄入口
- 对应 Repository、SQLite、API 与 migration 基线测试
- 对应五份状态文档

验证重点：

- schema version 保持 2，migration 文件无变化；
- get_or_create、fingerprint、expected_version、retry、record_result、DELETE 与 30 天清理；
- legacy/V2/V3 严格水合和旧数据回归；
- 旧应用读取 V3 fail closed；
- 所有 V3 replan 在 Provider/decision/版本写入前拒绝。

完成结果：

- 首轮 RED 在 collection 阶段证明 Repository 尚无 `PlanningJobResultV3`，V3 不能进入 application/SQLite/API；
- 后续 RED 证明无 plan 的 legacy failed result 可绕过 V3 request/result 版本匹配；调整匹配顺序后跨版本终态也 fail closed；
- `PlanningRequest/PlanningPlan/PlanningResponse` 扩为严格 legacy/V2/V3 三分支，旧两个 model 与 JSON 字段集合不变；
- 新增独立 `PlanningJobResultV3` 和内部 `PlanningResult` union，Repository port 方法集合不变；V3 fingerprint 排除 client ID 但保留城市顺序、夜数、窗口与用户段字段；
- 内存与 SQLite 复用既有 get/create/get/advance/record_result/retry/delete/cleanup；V3 metadata/plan 只写既有 JSON 列，schema version 保持 2；
- 同一 POST/GET/retry/DELETE URI 严格投影 V3；OpenAPI 精确包含三个 typed request 分支；V3 不调度尚未实现的 planning executor；
- V3 replan 在 API 和 application service 的 create/decide/execute 路径前置拒绝，reserve、lookup、decision、executor、replan/decision/lineage/plan version 写入均为 0；
- controlled adjacent guard 使既有 Provider planning/replanning 对 V3 显式 fail closed，不实现或调用 V3 Provider；对应离线回归 `33 passed`；
- 新增 Step 3 集合 `31 passed`；Repository/API/replan 相关 legacy/V2/V3 回归 `170 passed`；SQLite API 重启/兼容回归 `17 passed`；
- 全仓 Ruff format/lint 与 strict mypy 对 130 个文件通过；未修改 Schema/migration、依赖、lockfile、前端或真实 Provider 边界。

## Step 4：离线多城市 planning 与调用治理

唯一目标：实现 V3 planning、按城市复用现有适配器和确定性编排，不进入前端。

状态：`DONE`

核心文件：

- `backend/src/intelligent_travel_assistant/application/**` 中 planning/executor/scheduler 入口
- `backend/src/intelligent_travel_assistant/adapters/**` 中现有 DeepSeek/QWeather/Amap 边界的必要泛化
- bootstrap/app 的最小装配入口
- 对应 application/provider/synthetic 测试与 fixture
- 对应五份状态文档

验证重点：

- 城市解析 ≤ C、POI ≤ 3C、forecast ≤ C、alert ≤ C；
- generation 1、repair 1、route 并发 2、route ≤ min(28, 4D)；
- 城市 fan-out 并发 2、deadline ≤ 180 秒、intercity provider 调用 0；
- timeout、取消、partial/failed、来源和隐私边界；
- 默认测试阻断真实 Provider 和非 loopback 网络。

完成结果：

- TDD 首轮 RED 在 collection 阶段证明多城市编排器与 V3 governor 不存在；第二轮 RED 证明 proposal 日期校验仍只承认 V2；两项均以最小严格扩展转绿；
- 新增独立 `MultiCityPlanningOrchestrator`，按城市复用既有 Amap/QWeather ports，并通过一个全局 DeepSeek proposal/repair 边界生成 V3 活动选择；
- V3 proposal 强制逐日复制三个城市索引、限制当日 POI 城市，并由确定性代码注入用户城际段、60/30、120/60、45/30 缓冲、市内路线、活动时间、预算、来源和终态；
- 城市解析 ≤ C、POI ≤ 3C、forecast/alert ≤ C、generation/repair 各 1、route ≤ min(28,4D)、城市 fan-out/route 并发均为 2、deadline 为 180 秒；取消后 route active 收敛为 0；
- V3 repair 不接收原始模型输出、自由文本、兴趣或硬约束；model context 不包含用户站点、城际段原文或票价；城际 Provider port/adapter/调用保持 0；
- 现有 executor 和同 URI create/retry 已调度 V3；无完整 Provider 组合时仍不启用 executor；legacy/V2 路径与 shape 保持；
- Step 4 新增测试 `9 passed`；application 全目录 `505 passed`，API/contracts/持久化相关 `141 passed`，bootstrap `22 passed`，DeepSeek/parser 相邻 `102 passed`；
- Ruff format/lint、strict mypy 与 `git diff --check` 通过；未修改 schema/migration、Repository 方法集合、依赖、lockfile、前端或真实 Provider 边界。

## Step 5：前端多城市交互与离线恢复

唯一目标：实现最小多城市编辑器、严格 V3 解析、结果展示和重启恢复，不扩展产品范围。

状态：`DONE`

核心文件：

- `frontend/src/tripRequest.ts`
- `frontend/src/TripRequestForm.tsx`
- `frontend/src/tripPlanningApi.ts`
- `frontend/src/tripPlanModels.ts`
- `frontend/src/TripPlanResult.tsx`
- `frontend/src/App.tsx`
- 必要样式、对应测试和 synthetic fixture
- 对应五份状态文档

验证重点：

- 2/3 城市卡、住宿夜数、相邻城际段与字段级错误；
- 城市排序只由用户编辑；
- 转移日、缓冲、user_provided/unknown、partial 和来源展示；
- 已保存 V3 离线读取与重启恢复；
- desktop/390px、键盘、焦点、可访问名称和无水平溢出；
- 不显示 ¥0 unknown，不把 partial 显示为 ready。

完成结果：

- 首轮 RED 中既有 parser 以 `response_invalid` 拒绝严格 V3 response，表单不存在多城市 scope 与卡片；其余既有前端 `88 passed`；
- 独立 V3 请求/计划/响应 typed 变体与严格 parser 已覆盖 tag、城市/日期/夜数、日城市连续性、站点/段/source 引用、用户来源、unknown 与 terminal fail-closed；legacy/V2 解析和 JSON 形状保持；
- 表单默认单城市，只有显式选择多城市才提交 V3；支持 2/3 城、用户上移/下移、删除第三城、夜数差额、相邻段、派生转移日、+08:00、三种缓冲、字段首错与固定未核验披露；排序后清空全部相邻段；
- 结果页显示有序城市路线、停留、日城市、独立城际段/市内路线、缓冲、user_provided/unknown、partial、来源和固定无 replan 说明；unknown cost 行显示“未知”，不显示为 `¥0`；
- V3 创建后只在本机 `localStorage` 保存非敏感 job UUID 指针；应用重启用同源 GET 读取 SQLite 权威快照并直接恢复结果，损坏/未知响应进入安全错误且不删除服务端记录；legacy/V2 不写该指针；
- Step 5 专项 `7 passed`，前端全量 `95 passed`；Prettier check、ESLint、TypeScript 和 Vite build 通过；未修改依赖/lockfile、schema/migration、后端或 Provider 边界；
- desktop/390px 真实浏览器、0 overflow、console/network、临时 SQLite create/read/restart/retry/delete 和独立隐私/兼容审查仍严格保留给 Step 6。

## Step 6：纵向验收与独立审查

唯一目标：只用临时 SQLite 和 loopback synthetic executor 完成端到端验证、视觉 QA、隐私与兼容审查。

状态：`DONE`

核心文件：

- 已冻结的后端/前端纵向测试与 fixture
- loopback synthetic UAT 脚本或既有验收入口
- 对应五份状态文档

验证重点：

- V3 创建 → 查询 → 重启读取 → retry → DELETE；
- 2 城/3 城和五种终态；
- SQLite 重启、幂等、并发、保留期；
- legacy/V2 纵向回归；
- V3 replan 拒绝；
- 浏览器 console、网络 origin、desktop/390px 和 accessibility；
- 无真实数据库、秘密、Provider 或非 loopback 网络。

完成结果：

- 新增仅测试使用的 loopback 组合根和临时 SQLite API 纵向；数据库路径必须是系统临时目录内、启动前不存在的绝对文件，测试结束和浏览器进程关闭后已按精确路径清理；
- V3 create/read/restart/retry/delete、幂等、2/3 城、五终态和 V3 replan 前置拒绝通过；retry attempt 2 为 job 唯一 source/plan identity 生成新标识，不修改 schema v2 的既有唯一性；
- 真实 Vite → FastAPI → SQLite → synthetic executor 浏览器闭环在 `1440×1000` 与 `390×844` 通过；窄屏横向溢出为 0，页面 console error/warning 为 0，动态/静态请求共 58 条且全部为 `127.0.0.1`；
- 键盘验证覆盖第三日导航、skip link、删除/新增第三城与焦点恢复；DOM 审计为 duplicate id 0、无效 ARIA 引用 0、无可访问名称交互项 0、H1 1、live region 3；刷新后仅凭本机 job UUID 恢复 SQLite 权威结果；
- 浏览器实测发现“新增第三城”后触发按钮失效导致焦点落到 body；先补 RED 测试，再把焦点移到新城市输入，专项和前端全量转绿；
- 相关后端纵向 `45 passed`，前端全量 `95 passed`；触及文件 Ruff 与 strict mypy、ESLint、TypeScript 均通过；
- 独立 diff 安全审查 scan `efd6640a-731a-47ce-b4e8-58bf3931d5dc` 覆盖 36 个生产文件 review item、6 个信任面，结论 complete / 0 finding；TAC advisory 因 connector 未登录无法读取，不影响本地审查，但不应表述为 TAC 已验证；
- 未读取 `.env.local`、秘密或本地 Provider 配置，未调用 DeepSeek、高德、和风、城际 Provider 或非 loopback 服务；未修改 schema/migration、依赖/lockfile，未 commit/push/PR/merge；
- Step 7 全量门禁与四层 stacked PR 交付仍未授权、未执行。

## Step 7：全量门禁与 stacked PR 交付

唯一目标：运行完整本地门禁，按四层拓扑精确提交、push、创建 PR、clean-restack、review 和 CI。

状态：`DONE`。

核心范围：

1. `feat/f-004b1-multicity-domain-contracts`
2. `feat/f-004b1-multicity-persistence-api`
3. `feat/f-004b1-multicity-planning`
4. `feat/f-004b1-multicity-ui-delivery`

验证重点：

- backend/frontend/docs 全量门禁；
- 每层 diff、文件数、净新增行、依赖方向和秘密扫描；
- 单层 ≤ 30 个生产/测试文件且净新增 ≤ 2500 行；
- 前层 squash 后从最新 main clean restack，只移植下一层净变更；
- 不 force-push 重写已审查历史；
- 每层 PR/CI/review 成功。

完成结果：

- 统一入口最终通过：Ruff format/lint、strict mypy 134 files、backend `1166 passed`、frontend `10 files / 95 passed`、Prettier、ESLint、TypeScript、Vite build、文档检查器 `24 passed` 与 17 required/24 Markdown repository contracts；
- 四层 Draft PR 已创建：#19 `main → domain-contracts`、#20 `domain-contracts → persistence-api`、#21 `persistence-api → planning`、#22 `planning → ui-delivery`；
- 最终 head/CI 为 #19 `206bd9c` / `32379371761`、#20 `10f301d` / `32379662820`、#21 `de935c6` / `32379802803`、#22 `9239274` / `32379941695`，全部 `success`；
- 首轮 #19 `32377941830` 与 #20 `32378099288` 的独立门禁失败已保留：V3 union 和测试辅助模块过早跨层，及第二层执行器未对 V3 fail closed；通过普通追加提交与逐层 merge 修正，未 force-push 或隐藏失败；
- 四层生产/测试净新增分别为 1679、1393、2120、2497 行，单层文件数不超过 30；累计生产/测试净新增 7689 行，未触发重新切片；
- 范围、依赖方向、added-line 秘密模式、Schema/migration、依赖/lockfile 和城际 Provider 文件复核通过；独立 review 未发现阻塞 finding；
- 未读取秘密、调用真实 Provider、修改数据库、标记 PR ready、merge、运行 main CI 或归档。

## Step 8：合并、main CI 与归档

唯一目标：按依赖顺序合并四层交付，复核完整 main CI，并归档任务。

状态：`TODO`；当前未授权。

核心文件：

- `docs/archive/task-cards/F-004B1-*.md` 新归档任务卡
- roadmap、current-task、implementation-plan、progress、evidence、docs/README
- 必要当前权威文档状态收口

验证重点：

- 四层按序合并且 commit/PR/CI 事实一致；
- 完整 main CI 成功；
- 归档只复制最终任务事实，不改写既有历史 evidence 或归档任务卡；
- F-001 PARTIAL、Step 45M FAIL、Step 45T PASS、unknown、混合交通 fallback 仅离线、F-004A 无真实 Provider UAT 均保留；
- current-task 关闭且 roadmap 无意外 ACTIVE 任务。

## 核心文件清单 + 受控相邻扩展

一次 Step 批准覆盖：

- 核心文件同层直接依赖；
- 对应测试与 fixture；
- 仅为当前 Step 门禁通过所需的机械修复；
- `current-task.md`、`implementation-plan.md`、`progress.md`、`evidence.md`、`docs/README.md` 状态收口；
- 该 Step 已批准边界要求同步的权威设计文档。

以下不属于相邻扩展，必须停止：

- 改变冻结产品或公开 API 语义；
- Schema/migration、新依赖、新 Provider、数据或隐私变化；
- 秘密读取、真实 Provider 或未批准外部服务；
- 跨 Step/stack、历史 evidence 或归档任务卡修改；
- 单 Step 超过 5 个未预期生产/测试文件；
- 单 stack 超过 30 个生产/测试文件或净新增 2500 行；
- 总任务超过 90 个生产/测试文件或净新增 8000 行。

## 全程固定边界

- F-001 产品状态保持 `PARTIAL`；
- Step 45M `FAIL` 和 Step 45T `PASS` 均保留；
- unknown 金额不变为 0；
- 混合交通 fallback 仅有离线证据；
- F-004A 无真实 Provider UAT；
- 不自动进入下一 Step；
- 不扩大到 F-005 或 F-004B2。
