# 验收证据索引

## F-004B1 Step 7：全量门禁与四层 stacked PR 交付

- 日期：2026-08-20；结论：`PASS`；用户明确批准 Step 7，本次完成 commit、push、四层 Draft PR、远程 CI 与独立范围 review，没有进入 Step 8 的 ready/merge/main CI/归档；
- 本地全量门禁：Python 3.13.3、Node 22.16.0、pnpm 11.19.0；Ruff format/lint、strict mypy 134 files、backend `1166 passed`、frontend `10 files / 95 passed`、Prettier、ESLint、TypeScript、Vite build、文档检查器 `24 passed`、17 required/24 Markdown contracts 和 `git diff --check` 全部通过；
- Stack 1：Draft PR #19，base/head `main` / `feat/f-004b1-multicity-domain-contracts`，head `206bd9c3f6176a0cbc1476e3f4f10cc312e2f361`，最终 CI run `32379371761`=`PASS`；生产/测试 9 文件、净新增 1679 行；
- Stack 2：Draft PR #20，base/head 为 Stack 1 / `feat/f-004b1-multicity-persistence-api`，head `10f301d1a94b0ec7b87b043a9e11d0715d8570d4`，最终 CI run `32379662820`=`PASS`；生产/测试 21 文件、净新增 1393 行；
- Stack 3：Draft PR #21，base/head 为 Stack 2 / `feat/f-004b1-multicity-planning`，head `de935c67f9e7d2daf993447758a56b622a492195`，最终 CI run `32379802803`=`PASS`；生产/测试 10 文件、净新增 2120 行；
- Stack 4：Draft PR #22，base/head 为 Stack 3 / `feat/f-004b1-multicity-ui-delivery`；状态文档收口前的代码交付 head `923927449da68517d8edf91c0d411949ff141fa2`，CI run `32379941695`=`PASS`；生产/测试 14 文件、`+2644/-147`、净新增 2497 行，另含 13 份已批准当前文档；
- 失败透明度：首轮 #19 run `32377941830` 与 #20 run `32378099288` 为 `FAIL`；根因是 V3 Planning unions 和 union 测试过早落入领域层、测试包化改变旧 helper import，以及持久化层尚未对 V3 planning fail closed。追加提交 `206bd9c`/`10f301d` 修正层级，随后以普通 merge 传播到 #21/#22；没有 amend、rebase、force-push 或隐藏失败；首轮 #21 `32378139822` 与 #22 `32378757080` 原本已成功；
- 范围审计：四层均满足单层 ≤30 个生产/测试文件且净新增 ≤2500 行；累计生产/测试净新增 7689 行，小于 8000。未修改 Schema/migration、依赖/lockfile，未新增城际 Provider/adapter；added-line 秘密模式无命中，唯一新增外部 URL 是测试 fixture 的 `https://example.com/ticket`；独立 review 未发现阻塞 finding；
- 安全边界：没有读取 `.env.local`、秘密或本地 Provider 配置，没有调用 DeepSeek、高德、和风、城际 Provider 或非批准服务；没有创建或修改业务数据库；四个 PR 保持 Draft 且未 merge；
- clean-restack：前层未发生 squash merge，触发条件不存在；本 Step 只用普通追加提交和逐层 merge，后续层重建/移植保留给获批的 Step 8；
- 保留边界：F-001 `PARTIAL`、Step 45M `FAIL`、Step 45T `PASS`、unknown、混合交通 fallback 仅离线和 F-004A 无真实 Provider UAT 均保持；
- 下一动作：等待用户明确批准 Step 8；不得自动标记 PR ready、按序 merge、clean-restack、运行 main CI、创建 F-004B1 归档卡或关闭任务。

## F-004B1 Step 6：临时 SQLite 纵向、loopback 浏览器与独立审查

- 日期：2026-08-20；结论：`PASS`；用户明确批准进入 Step 6，本次没有进入 Step 7 全量门禁、Git 交付或远程 CI；
- TDD/纵向修复：`SyntheticPlanningJobExecutor` 首轮 V3 测试以 `synthetic_result_invalid` RED，扩为显式 `PlanningResult` 后转绿；临时 SQLite API 支持模块首轮缺失 RED，完成后覆盖 create/read/restart/retry/delete。retry 先暴露 source id、再暴露 plan id 唯一冲突；确认这是 schema v2 的既有 job 唯一性后，只让 browser synthetic executor 按 attempt 生成新标识，不改 Repository/schema/migration；
- SQLite 证据：新纵向模块 `10 passed`；联合 legacy/V2/V3 API、SQLite、Repository 与 executor 集合 `45 passed in 16.85s`。覆盖 2/3 城、ready/partial/conflict/needs_input/failed、幂等、重启、retry attempt 2、DELETE、安全临时路径和 V3 replan 前置拒绝；
- 浏览器链路：真实 `127.0.0.1` Vite → FastAPI → schema v2 SQLite → synthetic executor 生成 2 城 3 日 partial；desktop `1440×1000` 与 `390×844` 均为横向 overflow 0，刷新后恢复 job/result，retry 到 attempt 2 成功；58 条资源/API 请求全部为 `127.0.0.1`，页面 console error 0、warning 0；
- 键盘与 accessibility：第三日通过 Enter 可达并更新焦点，skip link 可聚焦并进入 `trip-request-form`，删除/新增第三城后焦点有效；DOM audit 为 duplicate ids 0、missing ARIA refs 0、unlabeled active interactive elements 0、H1 1、live regions 3；新增第三城最初因触发按钮 disabled 导致焦点落到 body，新增 RED 后修复为聚焦 `cityStays.2.city`，专项 `7 passed`；
- 前端/静态回归：前端 `10 files / 95 passed`，Prettier、ESLint 0 warning、TypeScript 和 Vite build 通过；触及后端四文件 Ruff format/check、strict mypy `Success: no issues found in 4 source files`；文档检查器通过 17 份必需文档、24 份 Markdown 与 CI/status/safety contracts，`git diff --check` 通过；当前 shell Node 为项目固定 `22.16.0`；
- 独立审查：Codex Security diff scan `efd6640a-731a-47ce-b4e8-58bf3931d5dc`，snapshot digest `82326e4f44ca85c0dd2b404d4e327976761d8ede97a4c34df822296b8787a800`；36/36 生产文件 review item、6/6 信任面完成，coverage `complete`、finding 0。覆盖 contracts/domain、Repository/SQLite、API/replan、planning/provider governance、frontend 和 compatibility；TAC advisory connector 返回 `USER_NOT_LOGGED_IN`，因此 TAC 状态保持未验证；
- 隐私与网络：SQLite 只保存 allowlist typed JSON；浏览器 `localStorage` 只保存 job UUID；未持久化票号、订单号、证件、乘客、联系方式、Cookie、Authorization、完整 Prompt 或 Provider 原始响应；未读取 `.env.local`、秘密或本地 Provider 配置，未调用 DeepSeek、高德、和风、城际 Provider 或非 loopback 服务；
- 清理与 Git：精确关闭 browser、Vite 和 uvicorn 后，删除本轮两份 `ita-f004b1-*.sqlite3` synthetic 临时文件；`HEAD == main == origin/main == 1a3e0a0`，仍在 `feat/f-004b1-multicity-domain-contracts`，未 commit/push/PR/merge；schema/migration、依赖/lockfile 无 Step 6 差异；
- 保留边界：F-001 `PARTIAL`、Step 45M `FAIL`、Step 45T `PASS`、unknown、混合交通 fallback 仅离线和 F-004A 无真实 Provider UAT 均保持；本 Step synthetic 证据不证明任何真实 Provider 质量；
- 下一动作：等待用户明确批准 Step 7；不得自动运行全量门禁、提交、push、创建四层 stacked PR、远程 CI 或进入 F-005/F-004B2。

## F-004B1 Step 5：前端多城市交互与离线恢复

- 日期：2026-08-20；结论：`PASS`；用户明确批准进入 Step 5，本次没有进入临时 SQLite/loopback 浏览器、独立审查或交付 Step；
- TDD RED：新增 V3 parser/表单测试后，严格 V3 response 被旧 parser 以 `response_invalid` 拒绝，页面找不到“多城市” radio；同次运行其余既有前端 `88 passed`，证明失败只对应本层缺失行为；
- 请求与表单：新增独立 V3 request DTO；默认仍为单城市，只有显式 scope 选择提交 V3。2/3 城卡、每城住宿/夜数、相邻 rail/air/coach 段、累计夜数派生转移日、`+08:00` datetime、fare null/user、字段首错和缓冲窗口拒绝均由 typed state 形成；
- 顺序治理：城市只通过有可访问名称的上移/下移按钮调整；卡自身字段随城市移动，所有相邻段立即清空并 live 披露；第三城删除只移除第二相邻段，焦点回到第二城标题；不以拖拽为唯一入口；
- 严格响应：V3 parser 校验独立 response/summary/plan tag、有序 destinations/adcodes、3–7 日、日城市连续性、站点/段/地点/source 引用、固定 user source 语义、terminal shape；tag 漂移、伪造 Provider source 和 ready 携带 unknown 均 fail closed；legacy/V2 parser 回归保持；
- 结果语义：路线/停留、转移日、住宿城市、城际段/市内路线分组、三种缓冲、user_provided/unknown、partial 诊断与 source/freshness 可读；V3 不渲染 replan 控件，并固定说明修改需新建任务；unknown cost item 显示“未知/金额未知”，不伪装实时/已核验；
- 离线恢复：V3 create 后只向本机 `localStorage` 写入 key `ita.active-v3-job` 的 job UUID；重启后只调用同源 GET 读取 SQLite 权威快照，不保存请求、站点、时间、fare、Prompt 或 Provider 数据；损坏/未知响应进入安全错误且不删除服务端记录；legacy/V2 不写恢复指针；
- 验证：专项 `7 passed`，前端全量 `10 files / 95 passed`；Prettier check、ESLint 0 warning、TypeScript、Vite production build 通过，构建产物 JS `298.11 kB`/gzip `88.78 kB`；实际 Node 24.19.0 相对声明 22.16.0 仅产生 engine warning；
- 范围与安全：本 Step 只修改批准的前端入口、相邻结果组件/fixture/tests/styles 和当前文档；`frontend/package.json`、`pnpm-lock.yaml` 无差异；未修改 backend/schema/migration，未创建数据库、读取 `.env.local`/秘密或调用任何 Provider/外部服务；未 commit/push/PR/merge；
- 保留边界：F-001 `PARTIAL`、Step 45M `FAIL`、Step 45T `PASS`、unknown、混合交通 fallback 仅离线和 F-004A 无真实 Provider UAT 均保持；
- 未覆盖范围：desktop/390px 真浏览器、0 overflow、keyboard/console/network、临时 SQLite create/read/restart/retry/delete、五终态与独立隐私/兼容审查必须等待 Step 6 单独批准。

## F-004B1 Step 4：离线多城市 planning 与调用治理

- 日期：2026-08-20；结论：`PASS`；用户明确批准进入 Step 4，本次没有进入前端、浏览器或交付 Step；
- TDD RED 1：新增 Step 4 测试后，collection 因 `MultiCityPlanningOrchestrator` 和多城市治理策略不存在失败，证明旧 executor 无法执行 V3；
- TDD RED 2：首个 V3 纵向测试进入 proposal parser 后因日期校验只接受 `request_version="2"` 失败，并错误尝试 repair；扩展为严格 V2/V3 日期全集判别后转绿；
- 编排：新增独立 `MultiCityPlanningOrchestrator`，按城市复用现有 Amap/QWeather ports，全任务只调用一次 DeepSeek generation，唯一 repair 仍由 governor 控制；legacy/V2 继续走既有 `OfflinePlanningOrchestrator`；
- 确定性边界：proposal 必须逐日复制 departure/arrival/overnight 城市索引并只引用合法城市 POI；应用注入用户段、三种缓冲、市内路线、活动时刻、逐城住宿、餐饮、城际 fare、来源和 terminal，不允许模型改写城市或段；
- 调用治理：策略精确为 resolve ≤ C、POI ≤ 3C、forecast/alert ≤ C、generation/repair 各 1、route ≤ min(28,4D)、城市 fan-out 2、route concurrency 2、deadline 180 秒；两城纵向实际为 resolve 2、POI 6、forecast 2、alert 2、generation 1、route 4；
- deadline/取消：deadline 在首个 Provider call 前耗尽时调用为 0 并返回安全诊断；取消时两条在途 route peer 完整 drain、active=0 且后续 route 未启动；
- 隐私与城际边界：V3 model payload 不含用户站点、城际段原文或 fare；repair 不接收原始模型输出、自由文本、兴趣或硬约束；没有新增铁路/航空/客运 port、adapter、HTTP/MCP 或调用；
- executor/API：既有 executor 对 V3 分派独立编排器，同 URI create/retry 可调度 V3；Provider 组合不完整时仍不启用真实 executor；V3 replan 写前拒绝保持；
- 验证：Step 4 新增集合 `9 passed`；application 全目录 `505 passed`；API/contracts/持久化相关 `141 passed`；bootstrap `22 passed`；DeepSeek/parser 相邻 `102 passed`；Ruff format `130 files already formatted`、Ruff lint `All checks passed`、strict mypy `Success: no issues found in 63 source files`、`git diff --check` 通过；
- 范围与安全：schema.py、migrations.py、Repository 方法集合、依赖、lockfile、前端均未修改；未读取 `.env.local`/秘密/Provider 配置，未调用真实 Provider、非 loopback 服务或远程 Git；未 commit/push/PR/merge；
- 保留边界：F-001 `PARTIAL`、Step 45M `FAIL`、Step 45T `PASS`、unknown、混合交通 fallback 仅离线和 F-004A 无真实 Provider UAT 均保持；
- 未覆盖范围：前端多城市输入/解析/展示/离线恢复、浏览器、完整临时 SQLite 纵向和交付仍未实现或验证，必须等待 Step 5–8 单独批准。

## F-004B1 Step 3：V3 typed unions、SQLite schema v2、同 URI API 与 replan 写前拒绝

- 日期：2026-08-20；结论：`PASS`；用户明确批准进入 Step 3，本次没有进入 V3 planning、Provider 编排或前端；
- TDD RED 1：新增 application/SQLite/API 测试后，collection 因 `PlanningJobResultV3` 不存在失败，证明 V3 不能通过 Repository 边界；
- TDD RED 2：新增无 plan 跨版本终态负向测试后，V3 job 接受 legacy failed result 且未抛错；将 request/result variant 匹配置于 plan-null 快路径之前后转绿；
- contracts/API：`PlanningRequest/PlanningPlan/PlanningResponse` 精确扩为 legacy/V2/V3 tagged union；POST/GET/retry/DELETE 保持原 URI，V3 使用独立 response/summary/plural destinations，非法/模糊 tag 返回既有 422；
- Repository：新增独立 `PlanningJobResultV3` 与内部 `PlanningResult` union；port 方法集合不变；V3 fingerprint 排除 client ID，城市顺序、夜数、窗口、站点、时间和 fare 继续参与；
- SQLite：V3 request/result/plan/source 只进入 schema v2 的既有 JSON/版本表；重启水合、retry attempt 2、DELETE 级联、30 天有界清理、plan tag 损坏 fail closed 和旧 models 读取 V3 失败均通过；migration 表仍精确为 1/2；
- replan：API 与 application service 的 create/decide/execute 对 V3 前置返回 `replan_scope_not_supported`；spy 证明 reserve/lookup/decision/executor 调用为 0，SQLite `replan_requests/decision_records/plan_version_lineage` 均为 0，job version/status 不变；
- Provider 边界：trip API 不为 V3 调度现有 executor；两个受 union 影响的既有 Provider service 只新增 V3 fail-closed guard，不实现 V3 Provider；相邻纯离线回归 `33 passed`；
- 验证：Step 3 新增集合 `31 passed`；Repository/API/replan 相关回归 `170 passed`；SQLite API 重启/兼容回归 `17 passed`；Ruff format `130 files already formatted`、Ruff lint `All checks passed`、strict mypy `Success: no issues found in 130 source files`；
- 范围与安全：未修改 schema.py、migrations.py、依赖、lockfile、前端或 Provider adapter；临时数据库只由 pytest `tmp_path`/系统临时目录创建并关闭；未读取 `.env.local`/秘密/Provider 配置，未调用外部服务或执行 commit/push/PR/merge；
- 保留边界：F-001 `PARTIAL`、Step 45M `FAIL`、Step 45T `PASS`、unknown、混合交通 fallback 仅离线和 F-004A 无真实 Provider UAT 均保持不变；
- 未覆盖范围：V3 planning、按城市 Provider 编排、调用预算/deadline/cancellation、前端、浏览器和完整端到端终态仍未实现或验证；这些必须等待对应 Step 单独批准。

## F-004B1 Step 2：多城市纯领域与独立 V3 contracts

- 日期：2026-08-20；结论：`PASS`；用户明确批准只进入 Step 2，本次没有进入 Repository/API、SQLite、Provider 或前端；
- TDD RED 1：新增领域与 contract 测试后，collection 分别因 `CityStay` 和 `TripPlanRequestV3` 不存在失败；这是当前层能力缺失，不是环境或外部服务失败；
- TDD RED 2：初次 GREEN 审查新增两个负向测试，分别证明 plan 可在转移前跨日跳城、response 可偏离 summary 夜数派生转移日；两项均以 `DID NOT RAISE ValidationError` 失败，最小连续性校验后转绿；
- TDD RED 3：五终态对齐审查证明携带 `errors` 的 ready 响应未被拒绝；补齐 ready/needs_input/retryable 终态 shape，并用一个正向测试覆盖全部五种合法终态后转绿；
- 领域实现：新增 2–3 城/3–7 日、每城至少一晚、累计夜数派生转移日、相邻用户段、+08:00 同日时间、rail 60/30、air 120/60、coach 45/30、普通/转移日活动和同城市内路线规则；
- 预算/状态：逐城住宿成本保留 unknown，城际 fare 只允许 `user_provided` 或 `unknown/null`，五终态由显式事实确定性分类；未核验 availability 本身不伪装成 partial 信号；
- V3 contracts：新增独立 request/plan/response、city stay、user segment、plan segment/day、request summary，以及住宿/站点/活动/路线引用、跨日连续性、来源与终态 final validation；V3 尚未接入现有 Planning unions；
- 验证：新增测试最终 `33 passed`；domain/contracts、相邻 legacy/V2 和 fingerprint 定向回归最终 `102 passed`；Ruff format `126 files already formatted`、Ruff lint `All checks passed`、strict mypy `Success: no issues found in 126 source files`；
- 兼容：legacy 固定 fingerprint `f8e8a85d192745f703d968695945c2fa4200f224d4e8ae9162a69abd57bf7edd` 与 V2 fingerprint 定向测试通过；现有 `PlanningRequest/PlanningPlan/PlanningResponse` 仍只含 legacy/V2；
- 范围与安全：未修改 Repository/API、SQLite Schema/migration、Provider、前端、fixture、依赖或 lockfile；未创建数据库、读取 `.env.local`/秘密/Provider 配置、调用外部服务或执行 commit/push/PR/merge；
- 保留边界：F-001 `PARTIAL`、Step 45M `FAIL`、Step 45T `PASS`、unknown、混合交通 fallback 仅离线和 F-004A 无真实 Provider UAT 均保持不变；
- 未覆盖范围：尚未证明 V3 fingerprint、Repository/SQLite round-trip、同 URI API、replan 写前拒绝、Provider planning、前端或浏览器行为；这些必须等待对应 Step 单独批准。

## F-004B1 Step 1：领域、API、Repository、Provider、UI 与测试设计冻结

- 日期：2026-08-20；结论：`PASS`；用户已明确批准进入 Step 1，本次只完成实现前设计冻结；
- 事实锚点：读取现有 V2 strict tagged contracts、PlanningJob/Repository typed model、schema/migration 1/2、SQLite TypeAdapter 水合、V2 replan scope 检查和前端单城市 request/response 入口；未发现与已批准任务卡冲突；
- 领域/架构：冻结独立 V3 request/plan/response 与 `PlanningJobResultV3`、2–3 城/3–7 日、每城至少一晚、累计夜数派生转移日、相邻用户段、每日城市骨架、方式缓冲、预算/来源和五终态；
- API/兼容：冻结同 URI legacy/V2/V3 callable discriminator、V3 精确字段、三个 `"3"` format tag、canonical fingerprint、稳定 violation/uncertainty code 和 legacy/V2 键集合不变；
- Repository/SQLite：冻结现有方法集合、typed request/plan/result union、request/result 匹配、schema v2 typed JSON、migration 仅 1/2、旧应用读取 V3 fail closed 和无 migration v3；
- replan：冻结全部 V3 在 service/reserve/decision/executor/Provider/write 前返回既有 422 `replan_scope_not_supported`，拒绝路径写入和外部调用均为 0；
- Agent/Provider：冻结用户段 immutable、城市 namespaced POI、确定性排程与终检、resolve≤C、POI≤3C、forecast/alert≤C、generation 1/repair 1、route≤min(28,4D)、两类并发 2、deadline≤180 秒和城际 Provider 调用 0；
- UI：冻结显式单/多城市模式、2–3 个城市停留卡、相邻段卡、夜数/时间/缓冲错误、V3 结果与离线恢复、V3 无 replan、desktop/390px/键盘/焦点门禁；
- 测试：冻结 Step 2–7 分层 RED/GREEN、legacy/V2 golden、V3 正负矩阵、schema 1/2 不变、临时 SQLite、loopback synthetic、隐私与调用预算断言；
- 自动化门禁：文档检查器通过，报告 17 份必需文档、24 个 Markdown 文件及 CI/status/safety contract 有效；检查器自身 24 项 unittest 通过；`git diff --check` 通过；
- 范围与安全：未修改源码、测试、前端生产文件、fixture、Schema、migration、依赖、lockfile 或数据库；未读取 `.env.local`、秘密或 Provider 配置，未调用真实 Provider或未批准外部服务；
- Git 边界：HEAD 保持 Step 0 基线，没有 staged change、commit、push、PR、merge 或远程分支；
- 保留边界：F-001 `PARTIAL`、Step 45M `FAIL`、Step 45T `PASS`、unknown、混合交通 fallback 仅离线和 F-004A 无真实 Provider UAT 均保持不变；
- 未覆盖范围：未进入 Step 2，没有新增 V3 代码或测试，也没有证明多城市运行、SQLite 往返、Provider 编排、前端或浏览器行为；这些必须等待对应 Step 单独批准。

## F-004B1 Step 0：事实复核、任务激活与治理基线

- 日期：2026-08-20；结论：`PASS`；执行范围仅为 Step 0 文档治理与本地分支创建；
- Git 基线：修改前 `HEAD == main == origin/main == 1a3e0a050721c72a6e83941f0cb5b2077decb1c7`，工作区干净；从该基线创建本地 `feat/f-004b1-multicity-domain-contracts`；
- GitHub 事实：CI run `32360800884` 在 `main`/`1a3e0a0` 上 completed/success；PR #13、#16、#17、#18 为 MERGED，#14/#15 为 CLOSED 且无 merge commit，与 F-004A clean-restack 归档记录一致；
- 任务事实：激活前 `current-task.md` 明确“当前无活动任务”；激活后 roadmap 恰有一个 `ACTIVE` 行，current-task、implementation-plan、progress 和 docs/README 统一指向 F-004B1 Step 1 `TODO`/待批准；
- 文档结果：完整已批准任务卡、Step 0–8、F-004B1 → F-005 → F-004B2 顺序、D-013 和“核心文件清单 + 受控相邻扩展”已写入当前权威文档；product-brief 的 F-004A“批准但未实现”和 api-contract 的“尚未实现”状态漂移已修正；
- 自动化门禁：`uv run --project backend --frozen python scripts/check_docs.py --root .` 通过，报告 17 份必需文档、24 个 Markdown 文件及 CI/status/safety contract 有效；文档检查器自身 24 项 unittest 通过；`git diff --check` 通过；
- 范围证据：diff 只包含批准的治理和当前事实文档；未修改源码、测试、前端、fixture、依赖、lockfile、Schema、migration、数据库或既有归档任务卡；本段仅新增于 evidence 顶部，未改写后续历史证据；
- 安全证据：未读取 `.env.local`、秘密或 Provider 本地配置，未调用 DeepSeek、高德、和风天气或城际 Provider，未访问未批准外部服务；
- Git 写入边界：没有 commit、push、PR、merge 或其他远程 Git 写入；
- 保留边界：F-001 `PARTIAL`、Step 45M `FAIL`、Step 45T `PASS`、unknown、混合交通 fallback 仅离线和 F-004A 无真实 Provider UAT 均保持不变；
- 未覆盖范围：未进入 Step 1，没有实现或测试 V3、多城市、城际段、Repository/API、Provider 编排、前端或 SQLite 往返；这些必须等待后续 Step 单独批准。

## F-004A Step 7：stacked PR、CI、合并与归档

- 最终结论：`PASS`；F-004A Step 0–7 已完成，三层功能、完整功能 main CI 和任务卡归档均已交付；
- Stack 1：PR #13，提交 `5e943ceddd0a8679c14d18ed4408d873b57712f8`，PR CI run `32358298975`=`PASS`；
- Stack 2：初始 PR #14 的 CI run `32358368917` 因 SQLite 纵向测试导入 Stack 3 browser helper 导致 Ruff import 分类失败；没有隐藏该失败。按 clean-restack 规则将纵向测试移入 Stack 3，以 PR #16 替代并关闭 #14；PR #16 提交 `62ec23c62e4e85680a82e893e68e920bb2351254`，CI run `32358898889`=`PASS`；
- Stack 3：初始累计 PR #15 的 CI run `32358429186`=`PASS`，但因前层 squash ancestry 由 clean PR #17 替代并关闭；PR #17 提交 `583e9da34b0d45e84a65da620cbb5d5fa8330a3c`，CI run `32359383850`=`PASS`；全程未 force-push；
- 合并顺序：#13 → #16 → #17，均 squash merge；完整功能 main CI run `32359762190`=`PASS`，耗时 4m36s；
- 最终本地门禁：后端 `1101 passed`、前端 `88 passed`、文档检查器 `24 passed`，Ruff、strict mypy、Prettier、ESLint、TypeScript、Vite build、依赖锁和文档契约通过；
- UAT：loopback synthetic 覆盖 3 日 ready、7 日 partial/unknown、2 日 V2 ready/replan；390px 无水平溢出，日期焦点/可访问名称正确，console 0 error/0 warning；
- 历史与真实性边界：F-001 仍为 `PARTIAL`；Step 45M 真实 `FAIL`、Step 45T 真实 `PASS`、unknown 不为 0、混合交通 fallback 仅离线证据均保留；F-004A 未调用真实 Provider，不把 synthetic 证据表述为真实天气、路线、预算或 Provider 质量；
- 数据与安全：schema version 保持 2，无 migration v3；未读取/输出秘密，未创建真实业务数据库；临时 SQLite、浏览器会话和本地监听均隔离并收口。

## F-004A Step 7：本地全量门禁、synthetic UAT 与交付准备

- 当时阶段结论：`LOCAL_PASS / DELIVERY_ACTIVE`；用户已明确授权修复范围内缺陷、复跑门禁与 UAT，并继续三层 stacked PR、远程 CI、依序合并和归档；
- 回归修复：在不改变公开 URI/DTO、Schema/migration、Repository 方法集合、Provider adapter、unknown/partial 或隐私边界的前提下，关闭 3–7 日 application replan 写前拒绝、proposal priority 顺序、V2 日数文案、SQLite retry/source 唯一性、五终态重启恢复、日期导航焦点和长文本窄屏换行缺口；
- 最终本地门禁：`scripts/verify.ps1` 通过，包含 Python 3.13.3、Node.js 22.16.0、pnpm 11.19.0，Ruff format/lint、strict mypy、后端 `1101 passed`、Prettier、ESLint、TypeScript、前端 `88 passed`、Vite build、文档检查器 `24 passed` 和 17 份必需文档/23 份 Markdown 契约；
- synthetic UAT：真实本机 Vite → FastAPI loopback 覆盖 3 日 ready、7 日 partial/unknown、2 日 V2 ready/replan；七日 unknown 门票保持“金额未知”且不是 `¥0`；2 日显示 8 个既有 replan 控件；390px 下 `scrollWidth == clientWidth == 375`，日期按钮把焦点送入带日期可访问名称的日卡，焦点轮廓可见；控制台 0 error/0 warning；
- 真实性边界：多日浏览器 fixture 仅验证 UI、API、SQLite 和状态投影，不证明生产 Provider 预算或真实天气/路线质量；legacy DTO/API/fingerprint 由独立自动化回归覆盖；没有调用 DeepSeek、高德或和风天气；
- 安全与清理：未读取 `.env.local`、Key、Token、JWT、私钥或 Cookie；业务请求仅访问 `127.0.0.1`；临时 SQLite 位于系统临时目录；浏览器会话及 8000/5173 监听进程已关闭；没有创建真实业务数据库；
- 当时远程交付尚未完成；后续 PR、CI、clean restack、依序合并、最终 main CI 和归档证据见本文件上方最终结论。

## F-004A Step 6：临时 SQLite 纵向、synthetic 浏览器 QA 和独立审查

- 结论：`PASS`；Step 6 已完成，当前 Step 7 为 `TODO` 并等待用户明确批准；
- RED 与修复：首轮纵向测试发现 V2 POST 永久停留 `draft`，根因为 API 仅调度精确 legacy 类型；用户批准后只调整 create/retry 对合法 V2 的既有 executor 调度，并增加 API 回归；公开 URI/DTO、Schema、migration、Repository、Provider 和前端未改变；
- SQLite：临时库覆盖 V2 2/3/7 日终态、重启恢复、幂等和删除；三日库 migration=`1,2`、status=`ready`、plan version=1，七日库 migration=`1,2`、status=`partial`、plan version=1、unknown_count=1；无 migration v3；
- 浏览器：真实本机 Vite → FastAPI loopback 覆盖桌面 legacy 两日、桌面 V2 三日和 `390×844` V2 七日 partial；两日保留 replan，三/七日隐藏 replan 并显示范围说明；七日末日可达且焦点进入 `trip-day-7`；unknown 门票显示“金额未知”且不是 `¥0`；无横向溢出或 console warning/error；CDP 记录的动态请求仅为 `127.0.0.1` 和内联 `data:`；
- 独立审查：发现 synthetic SQLite 仅校验绝对路径可能误触真实库的 P1；已强制路径位于系统临时目录且启动前不存在，并增加拒绝项目路径和既存临时文件测试；复验无剩余阻塞 finding；
- 验证：相关 API/SQLite/Repository/executor 回归 48 项通过；Ruff、strict mypy、`git diff --check` 通过；Step 7 全量门禁尚未执行；
- 安全：未读取 `.env.local` 或秘密，未调用真实 Provider，未访问非 loopback，未创建/修改真实业务数据库，未修改 schema/migration、依赖、lockfile 或环境文件，未创建分支或执行远程 Git；
- 下一动作：等待用户明确批准 Step 7；不得自动执行全量门禁、UAT、stacked PR、CI、合并或归档。

## F-004A Step 5：前端多日输入、动态展示和 replan 范围 UI

- 结论：`PASS`；Step 5 实现、验证和状态收口完成，当前 Step 6 为 `TODO` 并等待用户明确批准；
- TDD：新增 V2 parser 和日期导航测试先分别因 3/7 日响应被旧双日 parser 拒绝、导航组件缺失而失败；实现严格 tagged V2 解析和 `TripDayNavigation` 后转绿；
- 表单：显式结束日期、2–7 日动态窗口、默认双日 legacy 兼容、显式日期 V2、D+1 至 D+5、1/8 日拒绝、窗口错误和首错焦点均已覆盖；
- 结果：2/3/7 日动态摘要、可换行日期导航、全部日卡和键盘焦点已覆盖；3–7 日无可执行 replan，V2 两日保留既有 F-003 控件；
- 数据语义：7 日 partial fixture 保持 warning、天气缺失和 unknown 门票金额，页面显示“金额未知”且不显示 `¥0`；legacy fixture 和五终态回归继续通过；
- 验证：前端相关专项 75 项通过；统一 `scripts/verify.ps1` 在 Python 3.13.3、Node.js 22.16.0、pnpm 11.19.0 下通过后端 1088 项、前端 87 项、文档检查器 24 项，以及 Ruff format/lint、strict mypy、Prettier、ESLint、TypeScript、Vite build 和依赖锁检查；
- 范围与安全：只修改 Step 5 批准的 14 个既有前端文件并新增 2 个日期导航文件，以及批准的状态/UI/测试文档；未修改后端、公开 API、Repository、Schema、migration、Provider、依赖、lockfile、环境或数据库；未读取秘密、调用真实 Provider、访问非 loopback 网络、创建分支或远程写入；
- 下一动作：等待用户明确批准 Step 6；不得自动执行临时 SQLite 纵向、synthetic 浏览器 QA 或独立审查。

## F-004A Step 4：DeepSeek/QWeather/路线多日编排和失败语义

- 结论：`PASS`；Step 4 实现、验证和状态收口完成，当前 Step 5 为 `TODO` 并等待用户明确批准；
- TDD：新增动态 governor/期限测试最初因导出不存在而 collection 失败；新增 3/7 日真实 executor + fake Provider 纵向最初因缺少请求级 governor 和 V2 投影失败；7 日随后暴露旧 8 次路线预检查，移除该重复全局检查后由请求 policy 唯一裁决；
- 实现：V2 上下文、proposal/DeepSeek 日期规则、QWeather 2–7 日单次映射、N 日离线请求/路线/预算/typed plan 和请求级不可变 governor 已完成；legacy 默认 policy、双日 payload、公开 API、Repository、schema version 2 和 migration 序列不变；
- 失败与不确定性：缺少预期 proposal 日期本地 fail closed；7 日天气缺中间日只返回 partial 且调用一次；门票 unknown 保持 `None`，partial 不提升 ready；既有 terminal、fallback、deadline、异常 peer 和外部取消回归继续通过；
- 范围：核心 Step 4 文件外，预先披露并修改 `backend/src/intelligent_travel_assistant/bootstrap.py`，仅用于按请求 day count 创建 governor；这是治理规则允许的受控相邻组合根依赖，没有新增公开能力；
- 验证：Step 4 专项 `403 passed`；统一 `scripts/verify.ps1` 通过 Python 3.13.3、Node.js 22.16.0、pnpm 11.19.0，后端 `1088 passed`、前端 `76 passed`、文档检查器 `24 passed`，并通过 Ruff format/lint、strict mypy、Prettier、ESLint、TypeScript、Vite build 和依赖锁检查；
- 安全：未读取 `.env.local` 或秘密，未调用真实 Provider、访问非 loopback 网络、创建真实数据库、分支、提交、push、PR 或合并；未修改 Schema、migration、依赖、lockfile、环境或前端；F-001 `PARTIAL`、Step 45M `FAIL`、Step 45T `PASS`、unknown 和 fallback 历史边界不变；
- 下一动作：等待用户明确批准 Step 5；不得自动修改前端或进入 UI 实现。

## F-004A 阶段授权与文件范围治理修正

- 结论：原“未列文件一律禁止”规则过度依赖设计阶段穷举路径，已造成直接 contract 依赖、对应测试和状态收口重复请求授权，影响开发效率；
- 新规则：一次 Step 批准覆盖核心清单及满足已冻结行为所必需的同层直接依赖、对应测试/fixture、机械门禁修复和五份状态文档；相邻扩展先说明路径与原因，完成后统一留痕，不再逐文件追加授权；
- 仍需确认：产品/API 语义变化、Schema/migration、依赖、数据/隐私边界、秘密或真实外部访问、真实数据库、Git 远程写入、跨 Step/stack，以及超过 5 个未预期生产/测试文件；
- 本次仅修改治理和状态文档；Step 3 保持 `DONE`，Step 4 保持 `TODO`，没有修改生产源码、测试、Schema、migration、Provider、前端、依赖、环境或数据库，也没有进入 Step 4。

## F-004A Step 3：version 2 contracts、Repository/API 兼容与 SQLite 重启恢复

- 结论：`PASS`；Step 3 实现、验证和状态文档同步完成，当前 Step 4 为 `TODO` 并等待用户明确批准；
- TDD/兼容：V2 contract/API 测试先以 6 个预期失败证明端点仍仅接受 legacy；实现后同 URI request/response callable discriminator、未知版本 422、legacy 无标签 JSON 和 fingerprint golden 全部通过；
- Repository/SQLite：内存与 SQLite 使用显式 typed request/plan 联合，V2 计划可重启读取、幂等复用和删除；请求或计划版本损坏、request/plan 格式不配对均 fail closed；migration 仍精确为 version 1/2；
- replan：3–7 日在 service/reserve/write 前返回 `replan_scope_not_supported`；增补契约证明 V2 两日 completed replan 序列化保留 `response_version` 和 `plan_format_version`；
- 门禁：聚焦增补 26 项通过；统一 `scripts/verify.ps1` 在 Python 3.13.3、Node.js 22.16.0、pnpm 11.19.0 下通过，覆盖 121 个 Python/脚本文件 format、Ruff 和 strict mypy、后端 1073 项、前端 76 项、文档检查器 24 项、Prettier、ESLint、TypeScript 和 Vite build；
- 范围与安全：schema、migration、Provider adapter、前端、依赖、环境和真实数据库未修改；未读取 `.env.local` 或秘密，未访问真实 Provider 或非 loopback 网络，未创建分支、提交、push、PR 或合并；F-001 `PARTIAL`、Step 45M `FAIL`、Step 45T `PASS`、unknown 和 fallback 历史边界未改变；
- 下一动作：等待用户明确批准 Step 4；不得自动实现 Provider 多日编排。

## F-004A Step 2：多日领域、排程、预算与最终校验

- 结论：`PASS`；实现、验证和状态文档同步均已完成，Step 2 为 `DONE`，当前 Step 3 为 `TODO` 并等待用户明确批准；
- TDD RED：新增多日测试首次运行在收集阶段分别因 `MultiDayTripRequestInput`、`MultiDayTimePlan` 和多日预算函数缺失而失败，没有伪造 RED；
- 日期/窗口：新增独立 version 2 领域请求，支持连续 2–7 日并计算 `day_count`；基础 offset 为 0–6，legacy 双日请求和 `TwoDayTimePlan` 行为不变；
- 排程：proposal 必须为连续 2–7 日、每日 1–2 项、priority 连续且 selection 日期匹配；逐日住宿往返链最多 3 段，2/3/7 日确定性结果已覆盖；
- 预算：餐饮按每人每日 × 人数 × 天数，住宿按每晚 × (`day_count - 1`)；Decimal 通过 minor units 精确缩放，未知金额保持 `None` 而不是 0；
- 终检：schedule/routes 按候选日数遍历，3/7 日和中间日窗口冲突已覆盖；天气必须精确覆盖全部日期，中间日缺失产生 `weather_incomplete`；
- 测试：相关专项 136 项、后端全量 1065 项、format、Ruff、strict mypy、文档检查和 `git diff --check` 全部通过；格式/Ruff 首轮只发现新增文件机械格式和 import 顺序，修正后统一复验通过；
- 范围：只修改批准的 6 个生产文件、2 个既有测试、4 个新增测试和 4 份项目管理文档；未修改 contracts、Repository、SQLite/schema/migration、API、Provider adapter、前端、依赖、环境或数据库；
- 安全：未读取 `.env.local` 或秘密，未访问真实 Provider 或非 loopback 网络，未创建数据库、分支、提交、push、PR 或合并；F-001 `PARTIAL`、Step 45M `FAIL`、Step 45T `PASS`、unknown 和 fallback 历史边界未改变；
- 状态收口：README、current-task、implementation-plan、progress 和 evidence 已统一为 Step 0–2 `DONE`、Step 3 `TODO`；
- 下一动作：等待用户明确批准 Step 3；不得自动实现 contracts、Repository、SQLite 或 API。

## F-004A Step 1：实现前设计冻结

- 结论：`PASS`；领域、version 2 DTO/API、Repository/schema v2、Provider 治理、测试矩阵和 UI 设计均已形成闭集结论；Step 2 保持 `TODO`；
- 领域：legacy 类型独立保留；V2 冻结 2–7 日、offset 全集、每日 1–2 项、同一住宿锚点、N 日 proposal/scheduler/final validation、餐饮按日和住宿按夜；
- API：现有 URI 接受“无 version=legacy、精确 `request_version="2"`=V2”的严格 tagged union；V2 plan/response 有显式 format 标识；未知/模糊版本 422；不新增 `/api/v2`；
- 兼容：legacy response 不增加字段；读取 synthetic legacy fixture 后用现有生产 fingerprint 算法得到 golden `f8e8a85d192745f703d968695945c2fa4200f224d4e8ae9162a69abd57bf7edd`；V2 不通过补全 legacy 计算指纹；
- Repository/SQLite：port 方法集合、表、索引和事务不变；`request_version` 缺失/`2` 分别选择唯一 typed model，request/plan format 不一致 fail closed；schema migration 仍只有 version 1/2，无 migration v3；
- replan：legacy 双日不变，V2 两日可 typed 映射复用 F-003；3–7 日使用既有 `replan_scope_not_supported`，检查发生在 reserve/decision/executor/Provider 前且零写入；
- Provider：resolve 1、POI 3、forecast 1、alert 1、generation 1、repair 1；route 并发 2、上限 `min(28,4D)`；legacy/两日 90 秒，多日 `min(180,90+18×(D-2))` 秒；单次 timeout 不变；QWeather 不追加补拉；
- UI：结束日期、动态窗口、动态日卡、可访问日导航、2/3/7 日和桌面/390px 门禁已冻结；3–7 日不显示可执行 replan；
- 测试：领域、contracts、legacy golden、Repository/临时 SQLite、API、replan 零写入、Provider 治理、五终态、前端、浏览器和隐私矩阵已写入 testing-strategy；
- 只读探针：首次把整份 wrapper fixture 误传给 `TripPlanRequest` 得到预期 strict validation error；改为读取其 `request` 节点后得到上述 fingerprint golden，没有修改文件、数据库或状态；
- 范围：只修改 Step 1 获批文档；未修改生产源码、测试、Schema、migration、Repository、API、Provider、前端、依赖、环境或数据库；
- 安全：未读取 `.env.local` 或秘密，未调用真实 Provider，未访问非 loopback 网络，未创建分支、提交、push、PR 或合并；
- 下一动作：等待用户明确批准 Step 2，以 TDD 实现可变日期/窗口、排程、预算和最终校验；不得自动执行。

## F-004A Step 0：事实、漂移修正与执行基线

- 结论：`PASS`；已批准 F-004A 已激活，Step 0 完成，Step 1 保持 `TODO` 并等待用户明确批准；
- Git：进入 Step 时工作区干净；`main`、HEAD、本地 `origin/main` 均为 `e17cf4fe65407d98389a2713622adf398acc6f1b`；最近提交为 F-003 归档提交；
- CI：任务启动前只读核对的最新 main run `31939795749` 为 `PASS`；本 Step 按禁止非 loopback 网络的边界未重新访问 GitHub，未把未查询结果伪装为新证据；
- 历史：B-000、F-001、F-002、F-003 归档保持；F-001 `PARTIAL`、Step 45M `FAIL`、Step 45T `PASS`、unknown 不按 0 和混合交通 fallback 仅离线证据均未改变；
- Schema：代码 migration 列表只包含 version 1/2；当前 version 2 增加 replan 两表并复用 typed decision；F-004A 默认不增加 migration v3；
- 双日审计：公开请求派生结束日，窗口 offset 固定 0/1，计划恰好两日，DeepSeek/天气/最终校验、固定路线数组、餐饮乘 2、Repository 结果匹配和前端 parser/标签均含双日假设；
- 复用审计：单城市 PlanStructure、住宿往返路线链、确定性 scheduler、预算/unknown、来源/freshness、五终态、Repository 幂等/乐观锁、SQLite typed JSON 和 F-003 独立 lifecycle 可继续复用；
- 文档：修正 AGENTS 已失效应用事实和 PR 默认规则、F-003 design 状态、D-011 状态、项目入口与过期 Git/CI 指针；写入 F-004A 任务卡、Step 0–7、F-004A/F-004B 拆分、三层 stack 和 clean-restack 规则；
- 边界：只修改获批治理/长期文档；没有生产源码、测试、Schema、migration、Repository、API、Provider、前端、依赖、环境或数据库变化；
- 安全：未读取 `.env.local` 或秘密，未调用 DeepSeek/高德/和风天气，未访问非 loopback 网络，未创建真实数据库、分支、提交、push、PR 或合并；
- 下一动作：等待用户明确批准 Step 1；只冻结领域、version 2 DTO/API 兼容、Repository/schema v2 typed JSON、调用预算、测试矩阵和 UI 设计，不得自动实现。

## F-003 Step 8：全量门禁、synthetic UAT、stacked 交付与归档

- 结论：`PASS`；本地门禁、synthetic UAT、stacked PR CI、依赖顺序合并、完整功能 main CI 和任务卡归档均已完成；
- 首次失败证据：统一入口在 strict mypy 发现 `test_replan_repository.py` 的并发测试 helper 缺少返回类型；只补充 `ReplanRecord` 标注后从头完整复跑；
- 独立复审修复：关闭重复执行、分析/执行/取消异常悬挂、确认 TTL、旧 completed replan 元数据串版、unknown→ready、decision 响应丢失、陈旧确认按钮与焦点等交付阻塞；Schema、migration 和公开 API 未改变；跨 service/worker 原子 claim 仍明确不在本地单进程 composition 范围；
- 最终自动化门禁：Python 3.13.3、Node.js 22.16.0、pnpm 11.19.0；后端 1007 项、前端 76 项、文档检查器 24 项通过；锁、format、Ruff、strict mypy、ESLint、TypeScript、Vite build 和文档契约通过；
- UAT：deterministic synthetic FastAPI + Vite 只绑定 `127.0.0.1`；完成创建计划、调整活动时间、影响预览、确认和 completed 新版本/change set；确认态与完成态焦点正确，完整 change ref 可见；`390×844` 的 `scrollWidth/clientWidth` 均为 390；控制台 0 error/0 warning；首次复验因未设置公开夹具日期变量触发预期 `result_request_mismatch`，不计通过证据，按夹具契约重启后通过；
- 网络与隐私：有效复验的业务请求全部为 `http://127.0.0.1:5173`；未读取 `.env.local` 或秘密，未调用 DeepSeek、高德或和风天气，未创建真实 SQLite；
- 范围审查：62 个任务文件中 48 个为生产/测试、12 个为文档、2 个为文档检查脚本；无配置、依赖、CI、环境或数据库文件变化，新增内容的常见秘密格式扫描 0 命中；
- stacked PR：PR #7（领域）、#10（持久化/应用）、#11（API/UI/验收）分别以 CI run `31938572541`、`31938833604`、`31939013363` 通过；PR #8/#9 因 squash ancestry 重叠由等价干净 PR 替代并关闭；
- 合并证据：PR #7/#10/#11 依次合并；对应 main 逐层提交为 `5140fee3b23e3bb737f1cae248074bbe8d6dc389`、`55558bb7e8084da20c6b790d0ca8a5a91049d6bc`、`a9f1b83ee558de29e6f7c5b1bef67548fec9240a`；最终 main CI run `31939222646` 为 `PASS`；
- 历史边界：F-001 仍为 `PARTIAL`；Step 45M `FAIL`、Step 45T `PASS`、unknown 不按 0、混合交通 fallback 仅离线证据均未改变。

## F-003 Step 7：临时 SQLite 纵向、浏览器与独立审查

- 结论：`PASS`；两个已确认生产问题已在用户批准的最小范围内修复并复验，Step 7 为 `DONE`，未进入 Step 8；
- 修复：新 plan version 使用 planning job/attempt trace，独立 replan trace 仍保留在 replan/decision；SQLite 与内存 Repository 在 decide/begin_execution/commit 同时校验调用方、当前和创建时捕获的 job version；应用层把执行竞争稳定持久化为 `conflict`；
- 安全闭环：旧确认在 executor 前返回 `replan_job_version_conflict`，executor 调用为 0；同 baseline 并发最多追加一个 plan version，另一 replan 为 conflict；原计划不被替换；
- SQLite 纵向：completed、重复幂等、重启恢复、failed 原计划保留和并发冲突 3 项全部通过；迁移版本仍为 1/2，未修改 Schema 或 migration；
- 测试：聚焦 application/SQLite/API 18 项通过；领域、contract、application、Repository、API 相关回归 219 项通过；后端全量 999 项、前端 73 项通过；Ruff、format、strict mypy、ESLint、TypeScript 和 Vite build 通过；
- 浏览器：仅 `127.0.0.1` 的 deterministic synthetic FastAPI + Vite；修复后复验 completed、failed 和 version conflict。completed 显示本次 change set；failed/version conflict 保留原计划；`390×844` 下 `scrollWidth == clientWidth == 375`；资源 origin 仅 `http://127.0.0.1:5173`；预期 409 会产生一条浏览器网络错误日志，无未处理脚本异常；
- 浏览器夹具：增加 `ITA_BROWSER_START_DATE` 仅用于把冻结 synthetic plan/day/weather 日期对齐本次本地请求，避免验收日漂移假失败；未放宽生产 parser，Decimal 仍使用冻结格式 `4000.00`；
- 反证：synthetic 私密标记虽到达 plan insert 尝试，但同事务水合经 `_load_json` 拒绝并 rollback，没有敏感行持久化；跨 job decision 候选仅在已有任意本地 SQLite 写权限时成立，不形成新增安全边界；
- 安全报告：本机 Codex Security scan `06bb88d8-daa5-4e63-b39f-4d52ffe0d45f` 已完成并封存；对应 medium finding 的 fix report 已记录本机验证结论；
- 范围：按后续明确授权仅修改 application replan service、SQLite/内存 ReplanRepository、对应测试和批准文档；未修改 Schema、migration、Repository port、公开 API、Provider、前端、依赖、环境或真实数据库；
- 安全：未读取 `.env.local` 或秘密，未调用真实 Provider，未访问非 loopback 网络，未创建分支、提交、push 或 PR；
- 下一动作：等待用户明确批准 Step 8；不得自动开始全量交付、UAT、Git/PR/CI 或归档。

## F-003 Step 6：前端影响预览和确认流程

- 结论：`PASS`；四种结构化修改入口、影响预览、高影响确认/取消、replanning、completed 差异、安全终态、unknown/partial 和焦点恢复均已实现；
- RED：`replanningApi.test.ts` 与 `ReplanPanel.test.tsx` 首次运行因生产模块不存在而在收集阶段失败，既有 65 项仍通过；
- GREEN：前端 8 个测试文件共 73 项通过；ESLint、TypeScript、Prettier check 和 Vite build 通过；
- 首轮并行运行时一个既有 `TripRequestForm` 测试超过 5 秒；同一全前端套件串行复跑 73 项通过，未修改测试超时或弱化断言；
- API client 对额外字段、疑似秘密错误文本、completed/result/change-set/job/version 不一致 fail closed；HTTP 失败只展示安全 error envelope；
- 原计划在 analyzing、awaiting confirmation、replanning、cancelled、expired、needs_input、conflict、failed 和 rejected 时保持可读且不被替换；只有 completed typed result/change-set 能更新当前显示计划；
- unknown 金额继续显示未知且不按 0；partial 新版本继续显示 warning/uncertainty，不使用 ready 文案；
- 范围：仅批准的前端实现/测试与状态文档；没有后端、Schema/migration、Repository、API 契约、Provider、依赖、环境或数据库变更；
- 安全：未读取 `.env.local` 或秘密，未调用真实 Provider，未访问非 loopback 网络，未创建数据库、分支或远程写入；
- 累计范围审查：F-003 当前工作区共涉及 46 个生产/测试文件，按 tracked numstat 加 untracked 文件行数估算净新增约 8,360 行，超过任务卡 35 文件/3,000 行停止阈值；
- 用户决策：2026-08-16 明确选择 stacked PR；本次只同步执行基线，未创建分支、提交、push 或 PR；精确 stack/base 关系留待交付 Step 冻结；
- 下一动作：等待用户明确批准 Step 7；浏览器、临时 SQLite 纵向验证和独立安全/数据审查尚未执行。

## F-003 Step 5：三个窄 replan API 与现有 API 回归

- 结论：`PASS`；严格公共 DTO、create/get/decision 三端点、安全错误映射、后台执行快照及 completed result/change-set 投影已验证；
- 分支：`main`；未创建功能分支；工作区未提交；HEAD 与 `origin/main` 基线均为 `c836138240473f079565527b13a0d53516235c45`；
- 环境：本地离线、内存替身和临时 SQLite；未创建真实业务数据库，未读取秘密，未调用真实 Provider 或访问非 loopback 网络；

### 自动化门禁

| 验证项 | 命令入口 | 实际摘要 | 结论 |
| --- | --- | --- | --- |
| Step 5 专项 | contracts、replans API、application/repository/persistence replan 测试 | 31 passed | PASS |
| API 与相关回归 | `pytest backend/tests/api backend/tests/test_bootstrap.py backend/tests/application backend/tests/adapters/persistence backend/tests/contracts -q` | 571 passed | PASS |
| 后端全量 | `uv run --project backend pytest -q` | 1016 passed | PASS |
| 静态门禁 | Ruff format/check、strict mypy | 108 files formatted；Ruff 通过；61 source files 无类型问题 | PASS |

### API、数据和范围证据

- 四种 command 为拒绝额外字段的 tagged union，不接收完整 Prompt、provider ID、完整计划或自然语言修改；
- create/get/decision 返回冻结 ReplanResponse；相同决定幂等，相反决定、过期、baseline 和 command 幂等冲突使用稳定 409，cross-city/scope 使用 422；
- auto/approve 先返回 replanning 快照再调度 background task；同决定重放不重复执行；completed 才返回 typed result/change-set；
- F-001 现有 POST/GET/retry/DELETE DTO 与路由回归保持不变；没有列表、compare、restore 或批量清空 API；
- 未修改 Schema、migration、连接层、Provider adapter、前端、依赖、lockfile 或环境；Step 6 仍为 TODO，等待用户明确批准。

## F-003 Step 4：application replan、确认、并发和原子提交

- 结论：`PASS`；application service、确认 lifecycle、provider-neutral 离线执行、Repository outcome/commit 和 SQLite 原子版本提交均已验证；
- 分支：`main`；未创建功能分支；工作区未提交；HEAD 与 `origin/main` 基线均为 `c836138240473f079565527b13a0d53516235c45`；
- 环境：本地离线、内存替身和 `tmp_path` SQLite；未创建真实业务数据库，未读取秘密，未调用真实 Provider 或访问非 loopback 网络；

### 自动化门禁

| 验证项 | 命令入口 | 实际摘要 | 结论 |
| --- | --- | --- | --- |
| Step 4 专项 | `uv run --project backend pytest -q backend/tests/application/test_replan_service.py backend/tests/application/test_provider_replanning.py backend/tests/application/test_replan_repository_contract.py backend/tests/adapters/persistence/test_replan_repository.py` | 19 passed | PASS |
| application + persistence 回归 | `uv run --project backend pytest -q backend/tests/application backend/tests/adapters/persistence` | 494 passed | PASS |
| 后端全量 | `uv run --project backend pytest -q` | 1001 passed | PASS |
| 静态门禁 | `ruff format --check backend/src backend/tests`、`ruff check backend/src backend/tests`、`mypy backend/src` | 104 files formatted；Ruff 通过；59 source files 无类型问题 | PASS |
| 文档与 diff | `uv run --project backend python scripts/check_docs.py`、`git diff --check` | 17 份必需文档、22 个 Markdown 和 diff 通过 | PASS |

### 事务、并发和状态证据

- auto 与 approved replan 才能进入执行；相同决定重放幂等，相反决定冲突，15 分钟 TTL 到期持久化为 expired；
- 成功 commit 在单事务中写入新 plan version、source links、lineage、当前 attempt/job 和 completed replan；中途 lineage 失败时无新版本、无 lineage、job/replan 均不伪完成；
- 同 baseline 两个 replan 只有第一个提交成功，第二个得到稳定 job version conflict；确认前及 needs_input/conflict/failed/cancelled/expired 不替换当前计划；
- ready 和可执行 partial baseline 可进入编排；unknown amount 保持 `null`，partial 不提升为 ready；越界 change set 作为安全 conflict 收口；

### 范围与下一动作

- 未修改 API/contracts、bootstrap/组合根、Schema/migration/连接层、Provider adapter、前端、依赖、lockfile 或环境文件；
- F-001 `PARTIAL`、Step 45M `FAIL`、Step 45T `PASS`、unknown 非零语义和混合交通 fallback 仅离线证据保持不变；
- Step 4 已完成；Step 5 仍为 `TODO`，下一动作只能是等待用户明确批准 replan API 实现。

## F-003 Step 3：migration v2、Replan Repository 和 typed Decision

- 结论：`PASS`；migration v2、Replan Repository、typed Decision 和既有 API migration 基线均已验证；
- 分支：`main`；未创建功能分支；工作区未提交；基线 `c836138240473f079565527b13a0d53516235c45`；
- 环境：本地离线、临时 SQLite；未创建真实业务数据库；未调用真实 Provider；

### 自动化门禁

| 验证项 | 命令入口 | 实际摘要 | 结论 |
| --- | --- | --- | --- |
| API SQLite migration v2 回归 | `uv run --project backend pytest -q tests/api/test_sqlite_trip_plans_api.py` | 8 passed；明确验证 version 1/2，version 3 fail closed | PASS |
| Step 3 专项迁移/Repository/typed Decision | `uv run --project backend pytest -q tests/adapters/persistence/test_migrations.py tests/adapters/persistence/test_replan_repository.py tests/application/test_replan_repository_contract.py tests/domain/test_replanning_decisions.py` | 12 passed | PASS |
| 既有 persistence/application/API 回归 | `uv run --project backend pytest -q tests/adapters/persistence tests/application/test_planning_job_repository.py tests/api/test_sqlite_trip_plans_api.py tests/application/test_provider_planning_job_executor.py` | 81 passed | PASS |
| 后端全量 | `uv run --project backend pytest -q` | 963 passed | PASS |
| 静态门禁 | `ruff check backend/src backend/tests`、`ruff format --check backend/src backend/tests`、`mypy --strict backend/src` | 全部通过 | PASS |
| 文档与 diff | `uv run --project backend python scripts/check_docs.py`、`git diff --check` | 文档状态/安全契约和 diff 均通过 | PASS |

### 数据与隐私边界

- 只保存结构化 command、impact 和 decision；未保存 provider 原始响应、错误 body、完整 Prompt、Key、Token、JWT、Cookie 或 Authorization；
- 不改变 F-001 `PARTIAL`、45M `FAIL`、45T `PASS`、unknown 非零语义或混合交通 fallback 的离线证据边界；
- migration v2 仅新增 replan 表与 lineage，不修改既有 F-002 表的业务语义；

### 未覆盖范围与剩余风险

- 未实现 Step 4 的 application service、成功版本提交、完整重规划事务、API 或前端；
- Step 3 已完成；下一步只允许等待用户明确批准 Step 4；

## F-003 Step 2：纯领域重规划规则

- 结论：`PASS`；四种 typed command、确定性 impact、change set、预算重算和来源 reuse/refresh/drop 已实现；
- RED：四个新增测试模块首次运行均因 F-003 领域类型不存在而在收集阶段失败，证明测试先行；
- GREEN：`uv run --project backend pytest backend/tests/domain/test_replanning_*.py -q` 为 35 项通过；
- 回归：全部 domain 178 项通过；后端全量 981 项通过；
- 静态门禁：`ruff check backend/src backend/tests`、`ruff format --check backend/src backend/tests`、`mypy backend/src` 全部通过；
- 语义：只有精确 same_day_low 自动；高影响确认、cross-city 拒绝、共享来源不误删、unknown amount 保持空、change-set scope fail closed；
- 范围：只新增/修改批准的 domain 源码和四个 domain 测试，并同步允许文档；未修改 Repository、SQLite、migration、API、Provider、前端、依赖、环境或数据库；
- 安全：没有读取 `.env.local` 或秘密，没有真实 Provider 或非 loopback 网络调用，没有创建分支、提交或远程写入；
- 下一动作：等待用户明确批准 Step 3；开始前先核对 migration/Repository/Decision 的精确文件清单。

## F-003 Step 1：实现前设计冻结

- 结论：`PASS`；领域模型、八类可组合影响、独立 replan lifecycle、三个窄 API、migration v2、ReplanRepository、测试矩阵和 UI 交互已形成单一冻结契约；
- 兼容性：`PlanningStatus`、`PlanningJobRepository` 和既有 `TripPlanResponse` 不变；D-004 的旧措辞由 D-011 收口为独立 replan lifecycle；
- 数据：v2 只新增 `replan_requests` 和 `plan_version_lineage`，复用 typed `decision_records`；v1 数据不改写，既有版本不伪造 lineage；
- 原子性：确认前无 plan version；成功 ready/可执行 partial 单事务追加；needs_input/conflict/failed/cancelled/expired/rejected 保持原计划；
- 隐私：只保存 allowlist command、typed impact/change set 和安全代码；不保存完整自然语言修改、Prompt、provider body、秘密或原始错误；
- UI：冻结现有结果页内局部调整面板、15 分钟确认、baseline 保留、diff、焦点和桌面/390px 门禁；未实现前端；
- 范围：只修改 Step 1 允许文档；未修改生产源码、测试、Schema/migration 实现、API、Repository、前端、依赖、环境或数据库；
- 外部边界：未读取 `.env.local` 或秘密，未调用真实 Provider，未访问非 loopback 网络，未创建分支或执行远程写入；
- 下一动作：等待用户明确批准 Step 2；只用 TDD 实现纯领域 command/impact/diff/budget/source，不进入持久化。

## F-003 Step 0：事实核对、执行基线和允许文件清单

- 结论：`PASS`；F-003 任务卡已按用户批准决策激活，Step 0 为 `DONE`，Step 1 保持 `TODO` 且尚未执行；
- Git 基线：Step 0 开始时工作区干净；本地 `main` 与 `origin/main` 均为 `c836138240473f079565527b13a0d53516235c45`；没有创建分支、提交、推送、PR、合并或其他远程写入；
- CI 基线：main Windows offline verification run `31924427372` 对基线提交通过；
- 归档核对：B-000、F-001、F-002 已归档；F-001 产品状态 `PARTIAL`、Step 45M 真实 UAT `FAIL`、Step 45T 真实 UAT `PASS`、unknown 不为 0、混合交通 fallback 仅离线证据均保持不变；
- 代码基线：PlanningJob 仍使用 F-001 的 11 状态；现有 Repository 没有 replan port；`plan_versions` 没有 lineage/change set；`decision_records` 只有基础表；`acceptance_records` 有 typed 内部写入；migration 只有 version 1；现有 API 和前端没有局部重规划能力；
- 已批准边界：单城市双日、四种结构化修改、same-day low 自动、高影响确认、cross-city 拒绝、独立 replan lifecycle、15 分钟确认有效期、失败保持原计划、成功追加版本、migration v2、默认离线；
- 文档治理：已覆盖 F-002 在 current-task/implementation-plan 中残留的 ACTIVE/TODO/PR OPEN 当前措辞；F-003 一个任务、一个 Step 地图和一个交付目标成为当前唯一入口；
- 修改范围：仅 `docs/README.md`、roadmap、current-task、implementation-plan、progress、evidence 六份批准文档；没有生产源码、测试、Schema、migration、API、Repository、前端、依赖、环境或数据库文件变化；
- 安全边界：未读取 `.env.local`、Key、Token、JWT、私钥、Cookie 或 Authorization；未调用 DeepSeek、高德或和风天气，未访问非 loopback 网络，未创建或修改数据库；
- 验证：`uv run --project backend python scripts/check_docs.py` 通过；`git diff --check` 通过；`git diff --name-only` 只包含上述六份文档；
- 下一动作：等待用户明确批准 F-003 Step 1，只冻结领域、影响、确认、API、migration、Repository、测试和 UI 设计，不进入实现。

## F-002 最终交付与归档

- 结论：`PASS`；F-002 Step 0–6 已完成并归档；
- 分支：`feat/f-002-local-plan-persistence`；实施提交 `729119b9f583bfa80c421a9231f19694df38ab5f`，交付证据提交 `6b9f0ec44522502a334fef5d0b4e1b31e1d5000e`；
- PR：[PR #6](https://github.com/wcnm8888/intelligent-travel-assistant/pull/6) 已合并，merge commit `34fce5826db30ec30f7ae446ac2eb073a37cece9`；
- 远程门禁：实施提交 run `31923661440` 通过；最终 PR head run `31923863259` 通过；合并提交 main run `31924066600` / job `95108718835` 在 2 分 58 秒内通过；
- 最终能力：本地 SQLite migration、Repository 隔离、任务/attempt/plan version/source/decision/acceptance 持久化、现有 API 重启恢复与幂等/冲突语义、单计划删除和 30 天启动清理；
- 保持边界：无历史列表、版本比较/恢复、清空全部、前端历史页、登录、同步、多用户、云数据库、多城市、多日或局部重规划；不保存秘密、完整 Prompt、原始 provider 响应或错误 body；unknown 不转为 0，partial 不伪装为 ready；
- 安全与真实性：全部 F-002 自动化只使用内存替身、fake 和临时 SQLite；未读取 `.env.local`、调用真实 Provider、访问非 loopback 网络或创建真实业务数据库；
- F-001 历史保持：产品验收状态 `PARTIAL`，Step 45M 真实 UAT `FAIL`，Step 45T 真实 UAT `PASS`，门票等非关键费用为 `unknown`，混合交通 fallback 只有离线证据。

## F-002 Step 6 执行基线

- 状态：`PASS`；本地审查、最终 PR head CI、合并和合并提交 main CI 均已完成，Step 6 为 `DONE`；
- 用户授权：全量门禁、文档收口和交付审查；
- 审查范围：`HEAD` 到当前工作区的完整 F-002 累计差异，包括未跟踪 persistence 源码和测试；
- 允许：修复审查发现的 F-002 范围内缺陷、运行全量门禁、同步已经验证的文档事实；
- 禁止：扩大产品/Schema/migration/API/隐私范围、新增依赖、真实数据库、真实 Provider、秘密访问、分支、提交、推送、PR、合并或提前归档；
- 必须保持：F-001 `PARTIAL`、Step 45M `FAIL`、Step 45T `PASS`、unknown 不为 0、fallback 仅离线证据。
- 初次全量门禁：`scripts/verify.ps1` 通过；Python 3.13.3、Node.js 22.16.0、pnpm 11.19.0；91 个 Python/脚本文件 format、Ruff、strict mypy 通过，后端 922 项、前端 65 项、文档检查器 23 项和 Vite build 通过；
- 范围与安全：`git diff --check` 通过；仓库内无 SQLite/DB 文件；没有 frontend、依赖、lockfile、环境或 CI 变更；没有读取 `.env.local`、调用真实 Provider、访问非 loopback 网络或创建真实业务数据库；
- 初次阻塞证据：生产执行器以 `_id(job_id, suffix)` 生成 `plan_id`、user/system `source_id` 等稳定标识；retry 仍使用同一 job ID。SQLite schema 同时施加 `UNIQUE(job_id, plan_id)` 和 `PRIMARY KEY(job_id, source_id)`；新增纵向红测精确得到第二 attempt `failed`；
- 修复证据：用户批准后，attempt 1 继续使用 job ID 命名空间，attempt 2/3 使用 `job_id + attempt + trace_id` 派生 UUIDv5 命名空间；Schema、migration、公开 API、产品和隐私边界未改变；
- 纵向绿测：真实 `ProviderPlanningJobExecutor` 经纯离线 fake provider 写入临时 SQLite；第一次形成可重试 partial 计划，retry 后第二次形成新的 partial 计划；数据库含 2 个 attempt 和 2 个 plan version，两个 plan ID 不同，user/system source ID 不重叠，attempt 1 plan ID 与 F-001 原规则精确一致；
- 定向验证：执行器、SQLite Repository 和 SQLite API 共 53 项通过；
- 最终全量门禁：`scripts/verify.ps1` 再次通过；91 个 Python/脚本文件 format、Ruff、strict mypy，后端 923 项、前端 65 项、文档检查器 23 项和 Vite build 全部通过；
- 最终审查：按安全、迁移、API、并发、测试和数据完整性清单复审累计差异，无剩余 P0/P1；随后按用户授权完成分支、提交、推送、PR、远程 CI、合并和归档。
- 交付授权：用户已明确授权创建 `feat/f-002-local-plan-persistence`、精确暂存、提交、推送、创建 PR 并验证远程 CI；分支从与 `origin/main` 一致的 `38340dfed5c169911dc12042f4a90a5e042284c4` 创建，不授权自动合并。
- 交付事实：32 个 F-002 文件精确暂存，staged diff `+4120/-1220` 且无范围外或未暂存变更；实施提交 `729119b9f583bfa80c421a9231f19694df38ab5f` 已推送；PR #6 为 OPEN、非 Draft、base `main`、head `feat/f-002-local-plan-persistence`；
- 远程 CI：实施提交 run `31923661440` / job `95107606302` 通过；最终 PR head run `31923863259` / job `95108160182` 通过；PR #6 合并后的 main run `31924066600` / job `95108718835` 通过。

## F-002 Step 5 执行基线

- 状态：`PASS`；
- 用户授权：单计划删除、30 天保留期清理、隐私安全收口和 acceptance record 持久化；
- 允许范围：窄 Repository/maintenance/acceptance port、内存替身、SQLite adapter、单计划 DELETE route、启动清理装配、临时数据库测试和必要文档；
- 保持不变：schema/migration、既有 POST/GET/retry、unknown/partial 语义及 F-001 `PARTIAL`、Step 45M `FAIL`、Step 45T `PASS`、fallback 仅离线证据；
- 仍禁止：清空全部数据、历史列表、版本比较/恢复、前端、Provider、依赖、环境文件、真实数据库、真实网络、秘密或原始 Provider/Prompt 持久化。
- 实现：单计划 delete、DELETE 204/404、job-owned cascade、删除后幂等键释放、migration 后一次最多 1000 条的 30 天 cleanup、内部 typed acceptance record；
- 精度修复：定向测试发现 SQLite `julianday` 会舍入微秒，已改为有界候选读取后使用 Python aware datetime 精确比较，证明刚过边界删除、晚 1 微秒保留；
- 隐私：acceptance evidence 只允许代码化 check/limitation，敏感标记、非法 plan version 和不匹配 attempt 均在写入前拒绝或事务回滚；不保存完整日志、Prompt 或 provider body；
- 验证：Step 5 相关定向 80 项通过；统一门禁中 91 个 Python/脚本文件 format、lint、strict mypy 通过，后端 922 项、前端 65 项、文档检查器 23 项及 Vite build 通过；测试只使用内存与 `tmp_path` SQLite；
- 状态：Step 0–5 `DONE`，Step 6 `TODO`；下一动作是等待用户明确批准 Step 6。

## F-002 Step 4：现有 API SQLite 装配与恢复语义

- 状态：`PASS`；
- 用户授权：进入 Step 4，将 SQLite Repository 接入现有 API并验证重启、幂等、并发和冲突语义；
- 允许范围：settings、bootstrap、app 组合根，临时 SQLite bootstrap/API 测试，必要的 persistence 最小缺陷修复，以及 architecture、api-contract、testing-strategy 和项目状态文档；
- 保持不变：公开路由/DTO、Repository Protocol、Schema、migration、unknown/partial 语义和 F-001 历史证据；
- 实现：本地应用默认使用源码树外应用数据目录中的 SQLite；显式路径必须是源码树外绝对路径；lifespan 在服务请求前打开连接并完成 migration，失败时安全停止，并在关闭时释放连接；测试注入优先，无显式路径的 test 模式继续使用内存替身；
- API 证据：同一临时数据库上的应用重启可恢复 POST/GET 任务；重复 POST 保持原 job，同 ID 异请求返回 409；16 路并发重复创建只产生一个 job/attempt；并发 retry 只有首个成功，后续返回 409；高版本数据库阻止启动且连接关闭；
- 定向验证：`test_bootstrap.py`、`test_sqlite_trip_plans_api.py` 和既有 API 回归共 43 项通过，其中 Step 4 新增 9 项；
- 统一门禁：Python 3.13.3、Node 22.16.0、pnpm 11.19.0；91 个 Python/脚本文件 format、lint、strict mypy 通过；后端 913 项、前端 65 项、文档检查器 23 项、Vite build 和文档契约全部通过；
- 安全与范围：测试只使用 `tmp_path` 数据库；未创建或修改真实业务数据库，未读取 `.env.local` 或秘密，未调用真实 Provider或访问非 loopback 网络；未修改公开路由/DTO、Repository Protocol、Schema、migration、前端、Provider、依赖或环境文件；
- 状态：Step 0–4 `DONE`，Step 5 `TODO`；仍禁止删除/清理、历史列表、版本比较/恢复和 Step 5 实现；下一动作是等待用户明确批准 Step 5。

## F-002 Step 3：SQLite PlanningJobRepository 映射

- 状态：`PASS`
- Step 0、Step 1、Step 2、Step 3：`DONE`；Step 4：`TODO`；
- 实现：persistence adapter 内既有五方法 Repository 映射、typed hydration、job/attempt/trace、幂等指纹、乐观 version、结果 metadata、追加式 plan version 和 source records/link；
- 原子性：创建 job+attempt、状态更新、终态 source+plan version+attempt+job、retry 新 attempt+job 均在事务中完成；expected version 条件更新失败返回稳定 `VERSION_CONFLICT`；
- 数据语义：ready、partial、conflict、needs_input、failed 五种终态 round-trip；unknown 金额保持 `null`；Decimal、日期、time、aware datetime、freshness 和安全链接经 typed model 恢复；
- 安全：allowlist JSON 写入前和读取后校验；秘密样式请求和 source URL 被拒绝并回滚；损坏 JSON fail closed；无 `.env.local`、Provider、非 loopback 网络或真实数据库访问；
- 定向验证：persistence 28 项通过，其中 Step 3 Repository 16 项；既有内存 Repository 契约 12 项继续通过；
- 统一门禁：Python 3.13.3、Node 22.16.0、pnpm 11.19.0；90 个 Python/脚本文件 format、lint、strict mypy 通过；后端 904 项、前端 65 项、文档检查器 23 项、Vite build 和文档契约全部通过；
- 范围：未修改 Repository Protocol、API、前端、Provider、依赖、Schema 或 migration；未创建分支、提交、推送或 PR；
- 下一动作：等待用户明确批准 Step 4，不自动接入 API。

## F-002 Step 3 执行基线修复

- 状态：`PASS`；
- 原问题：Step 2 文件清单只覆盖 SQLite 基础设施，没有明确授权 Step 3 Repository adapter 和测试；
- 用户授权：允许修复 Step 3 文件清单，并在基线门禁通过后重新进入 Step 3；
- 已允许：persistence 目录内 SQLite `PlanningJobRepository` adapter、typed hydration、job/attempt/version/source 映射、对应临时数据库测试、项目管理文档和最终 README/roadmap 状态收口；
- 仍禁止：Repository Protocol、API、前端、Provider、依赖、环境文件、真实数据库、删除/清理、历史列表、版本比较/恢复和真实网络；
- 基线修复本身未实现 Repository、未创建数据库、未读取秘密、未调用 Provider；修复后的文档门禁通过，随后 Step 3 才进入实现。

## F-002 Step 2 实现验证与状态收口

- 状态：`PASS`
- Step 0、Step 1、Step 2：`DONE`；
- 已实现：persistence 目录内 SQLite 连接生命周期、事务工具、migration runner、初始 8 表 schema 和索引/约束；
- 已验证：定向 SQLite 测试 12 项通过；全后端离线 pytest 888 项通过；persistence format、Ruff check、strict mypy 通过；状态收口后的文档检查和 `git diff --check` 通过；
- 未执行：Repository、API、前端、Provider、真实数据库、真实网络、Step 3；
- 状态收口：用户已批准修改 `docs/README.md` 和 `docs/project-management/roadmap.md`，并已同步全部当前状态入口；
- 下一动作：等待用户明确批准进入 Step 3；Step 3 尚未执行。

## F-002 执行基线修复：Step 2 文件清单

- 状态：`PASS`
- Step 0、Step 1：保持 `DONE`；Step 2：保持 `TODO`；
- 原问题：执行清单错误地禁止 `backend/src/**` 和 `backend/tests/**`，与 Step 2 的 SQLite/migration 目标冲突；
- 修复内容：仅允许 `adapters/persistence/**` 基础设施、对应临时测试和项目管理证据文档；Repository、API、前端、Provider、依赖、环境文件和真实数据库仍被禁止；
- 未执行：SQLite、migration、Repository、API、前端、Provider、数据库创建、Step 2 测试、分支创建、提交、推送、PR 或合并；
- 未读取：`.env.local`、Key、Token、JWT、私钥、Cookie 或其他秘密；
- 结论：执行基线修复完成，下一步仍需用户明确批准进入 F-002 Step 2。

## F-002 Step 1：Schema、迁移、连接、Repository contract 和测试矩阵冻结

- 状态：`PASS`
- 任务状态：`ACTIVE`
- 当前 Step：`Step 1 DONE`；等待用户批准 Step 2
- 已只读审计：Repository Protocol、内存 adapter、任务模型、结果/来源模型、状态机、API、架构和测试策略；
- 已冻结：8 张 SQLite 表、字段与约束、索引、typed JSON 边界、migration runner、事务/rollback、连接 PRAGMA、busy timeout、version/attempt/trace、删除/30 天清理和测试矩阵；
- 已保持：F-001 `PARTIAL`、Step 45M 历史 `FAIL`、Step 45T `PASS`、unknown 不按 0、混合交通 fallback 仅离线证据；
- 未执行：SQLite、Repository、API、前端、数据库创建、Provider、真实网络、`.env.local` 读取、秘密读取、分支创建、提交、推送、PR 或合并；
- 设计文档：current-task、implementation-plan、progress、architecture、testing-strategy、decisions 已同步；
- 结论：Step 1 通过，下一步只能进入 F-002 Step 2。

## F-002 Step 0：事实核对与执行基线

- 状态：`PASS`
- 任务状态：`ACTIVE`
- 当前 Step：`Step 0 DONE`
- 环境：Windows，本地 `main`
- Git：`main` 与 `origin/main` 均为 `38340dfed5c169911dc12042f4a90a5e042284c4`；Step 0 开始前工作区干净，完成本次基线文档更新后仅有允许清单内 6 份文档变更；`main` 未配置 upstream，但本地远程跟踪引用已直接核对一致；
- 已核对：项目规则、文档地图、roadmap、current-task、progress、evidence、implementation-plan；
- 已保留：F-001 `PARTIAL`、Step 45M 历史 `FAIL`、Step 45T `PASS`、unknown 不按 0、混合交通 fallback 仅离线证据；
- 已确认：F-002 数据、隐私、迁移、删除、API、单城市双日和本地 SQLite 边界；
- 允许修改文件清单已写入 current-task；
- 未执行：SQLite、Repository、API、前端、Provider、真实网络、`.env.local` 读取、秘密读取、分支创建、提交、推送、PR 或合并；
- 结论：Step 0 通过，下一步只能进入 F-002 Step 1。

## 文档职责

本文件只保存任务最终可复现的验收结论、环境、命令入口、人工验收和剩余风险。它不保存完整终端日志、逐 Step 过程、聊天记录、Prompt、秘密、原始第三方响应或重复截图。

状态值：

- `NOT_RUN`：尚未执行；
- `PASS`：在记录环境和范围内通过；
- `FAIL`：已执行但不满足预期；
- `BLOCKED`：因明确前置条件不能执行；
- `PARTIAL`：只有部分范围得到证据，不能宣称完整通过。

## 当前证据状态

### F-001：单城市双日旅行计划垂直切片（已交付，产品状态 PARTIAL）

- 任务状态：`ARCHIVED`
- 当前结论：`PARTIAL`。D-009/F-001-CR1 已实现、审查并交付到 `main`；Step 45T 的唯一真实任务形成完整双日 `partial` 计划，只有非关键 unknown 费用，真实 UAT 为 `PASS`。Step 45M 历史 `FAIL` 保留；F-001 已完成代码交付和归档，但不宣称全量 `ready`；
- 分支：`main`；PR #5 已按 stacked 顺序合并至功能分支，PR #4 已复验并合并至 `main`；
- Step 45V：提交 `749acc905ff3739c9af87d800540e5513fea2765`，26 文件、`+1815/-102`，Windows offline verification run `31879377928` 通过；Step 45W 审查快照为 34 文件、`+4307/-332`，Step 45X 文档提交后当前 PR #5 累计范围为 34 文件、`+4336/-337`；
- Step 45W：独立远程 review 未发现 P0/P1，确认问题仅为文档和 stacked 顺序漂移；Step 45X 已修正这些事实；Step 46/47 已完成合并与最终归档收口；
- Step 34 自动化：10 类 Agent 输出 scorecard、目录顺序不变性、四终态各 10 次重复裁决通过；新增 15 项、专项相关 107 项通过。统一门禁包括 Python 3.13.3、Node.js 22.16.0、pnpm 11.19.0、后端 729 项 pytest、前端 61 项 Vitest、文档检查器 23 项测试、Ruff format/check、strict mypy、Vite build 和 17 份必需文档契约；
- Step 35 自动化：新增任务执行端口、五终态 synthetic executor 和轮询可达后继回归；专项后端 20 项、前端 62 项及相关静态门禁通过。Playwright Chromium 经真实本机 POST/GET/retry 验证 ready、partial attempt 2、conflict、needs_input 和 failed，`390×844` 下 `scrollWidth=375`、控制台 0 error/0 warning；动态业务请求仅访问本机 `/api`；
- Step 36 全量门禁：在项目根目录运行 `powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify.ps1` 一次通过；Python 3.13.3、Node.js 22.16.0、pnpm 11.19.0，后端 737 项 pytest、前端 62 项 Vitest、文档检查器 23 项测试，以及锁文件、依赖、peer、Ruff format/check、strict mypy、Prettier、ESLint、TypeScript、Vite build、17 份必需文档和 19 个 Markdown 文件契约全部通过；
- Step 37 初次就绪审计（2026-08-14）：当时项目内不存在 `.env.local`，六项 provider 配置全部未配置。随后用户自行创建三家账户与凭证；当前 `.env.local` 已被 Git 忽略，无网络启动检查仅输出非敏感状态 `deepseek=ready`、`amap=ready`、`qweather=ready`、`executor=ready`。该证据不证明服务端鉴权或 live 合约；
- Step 37 费用结论：DeepSeek 2026-08-17 峰谷价下同一调用预算的三家高峰保守上界约 9.274 元、空闲约 4.666 元；用户批准把一次受控 smoke 总费用上限由 5 元提高到 12 元，调用次数保持 DeepSeek 3、高德 16、和风 4，执行前必须重新核价；
- Step 37 代码补充收口：和风 `metadata.attributions` 现以严格 Schema 原样进入领域/公开来源，固定和风链接和 DeepSeek AI 生成披露按来源显示；真实执行器只在三家 adapter 全量就绪时装配，并通过 fake 端口完成住宿 POI、天气、候选、四段路线、预算、状态与 Repository 离线闭环。当时记录的统一门禁计数为后端 744 项、前端 63 项、文档检查器 23 项；Step 40 发现默认 test app 会固定加载 `.env.local`，因此“未读取凭证或访问 provider”的历史断言不再有充分隔离证据。没有证据表明当时实际发生额外 live 调用，但该门禁必须在 Step 41 修复隔离后重跑；
- Step 37 高德边界：用户根据高德工程师电话沟通明确确认个人、非商业、本地查询和组合展示合法，无需企业许可；原始响应和持久缓存禁止，转换结果只在进程内保存且重启即失，不公开部署或传播真实数据截图。前端存在高德来源时固定展示“数据来源：高德地图”及官方链接；该证据记录用户明确决策及电话沟通事实，不表述为书面许可书；
- Step 38 live smoke（2026-08-14）：执行前本地无网络检查为 `deepseek=ready`、`amap=ready`、`qweather=ready`、`executor=ready`。严格只创建一个杭州双日计划；任务首轮终态为 `conflict` 且含结构化计划，脱敏来源计数为高德 3、和风 2、DeepSeek 1、system 1、user 1，无 provider 错误码；确定性校验报告 1 项日程冲突和 2 项路线冲突；
- Step 38 路线补充证据：候选日程冲突使正常路线补全按设计跳过。为补齐 live 路线契约，仅在同一授权与高德调用预算内执行 1 次固定杭州测试坐标的公交路线探针，结果 `ok`、有数据、距离与时长为正、错误分类为空；未创建第二个计划，未增加 DeepSeek 或和风调用；
- Step 38 安全边界：没有记录凭证、真实地点、路线值、请求正文或上游响应；没有保存原始响应、持久缓存或真实高德数据截图。Step 38 live 服务契约结论为 `PASS`，但具体计划不能作为 ready 计划或真实数据 UAT 通过证据；
- Step 39 真实 UAT（2026-08-14）：用户批准沿用一次杭州双日计划、DeepSeek 3、高德 16、和风 4、总费用 12 元上限。桌面只产生一个任务 POST；终态为 `failed`、`attempt=1`、`retryable=false`，唯一错误码为 DeepSeek `provider_schema_invalid`，公开来源脱敏计数为 user 1、system 1、高德 3、和风 2；
- Step 39 停止与安全：Schema 异常后没有 retry、第二次 POST 或额外 provider 调用。桌面和 `390×844` 均无水平溢出，来源与时效、高德/和风归因、安全失败文案可见；无 DeepSeek 来源时不展示 AI 披露，无 retry 动作，控制台 0 error/0 warning，DOM 无秘密标记；
- Step 39 产物边界：未保存截图、provider 原始响应、持久缓存、真实地点或路线明细；本次 Playwright 临时 YAML/控制台文件已精确移除，进程与 `8000/5173` 监听均关闭。另发现页脚显示过期 `F-001 · STEP 35`；
- Step 39 结论：执行完成但 UAT 为 `FAIL`。安全失败和窄屏展示有效，DeepSeek Schema 阻塞使系统没有 ready/partial 真实计划，必须在后续审查/修复 Step 处置后重新取得 live 调用授权；
- Step 40 独立 QA（2026-08-14）：审查工作区相对 `main` 的全部修改及未跟踪文件，确认 HEAD 仍为 F-001 分支创建时的 main 基线，无提交、推送或 PR。工作区共 119 个变更文件，粗略净新增约 2.44 万行，超过任务卡约 70 文件/5000 行停止阈值；
- Step 40 DeepSeek 结论：公开 `provider_schema_invalid` 同时可由 adapter envelope 异常和本地候选二次失败产生；安全 `candidate_resolution_error=model_output_invalid` 在发布层丢失，且没有不含原文的安全子原因，因此无法从 Step 39 现有证据判定精确失败字段。未读取、恢复或保存原始响应；
- Step 40 代码阻塞：默认测试应用加载 `.env.local` 并可能装配真实执行器；DeepSeek 上下文缺少两日窗口、自由文本和真实天气/预警，repair 请求缺少候选 Schema；重复 day offset 未在 provider 前拒绝，天气地点 ID 与查询坐标语义不一致，模型截断/timeout、来源约束和候选日期顺序存在测试或实现缺口；
- Step 40 离线验证：没有运行可能读取 `.env.local` 的默认统一入口。先以进程内护栏禁用 dotenv source并断言六项 provider 配置为空，再运行全量后端 `744 passed`；冻结运行时为 Python 3.13.3、Node 22.16.0、pnpm 11.19.0，前端 `63 passed`，Ruff format/check、strict mypy、Prettier、ESLint、TypeScript、Vite build、uv lock、peer、CI 格式、文档检查器 `23 passed` 和审查前文档契约均通过。按授权只同步四份项目管理文档后，文档检查器仅报告 `docs/README.md` 仍为 Step 40；该文件未在本 Step 修改；
- Step 40 结论：审查证据充分，建议进入 Step 41 最小修复；当前阻塞再次 live UAT、提交和 PR。修复后必须先在真正不加载本地凭证的默认统一入口重跑，再单独申请一次受控 live 回归；
- Step 41 离线修复（2026-08-14）：pytest 在导入应用前固定 test composition，不读取 `.env.local`，并自动拒绝非 loopback socket；默认 API 组合根验证三家 provider 均 disabled、执行器为空，显式外网连接负例被阻断。DeepSeek provider envelope 与本地候选失败分别映射为 `provider_schema_invalid`/`model_output_invalid`，安全 `diagnostic_code` 不含原文；generation/repair Schema、截断单次修复、用户时间窗/自由文本/交通/住宿/天气上下文、日期顺序、POI 来源、天气坐标和 timeout 竞争均有离线回归；
- Step 41 自动化：Python 3.13.3、Node.js 22.16.0、pnpm 11.19.0；在项目根运行 `powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify.ps1` 一次通过，包含后端 756 项 pytest、前端 64 项 Vitest、文档检查器 23 项，以及锁、依赖、peer、Ruff format/check、strict mypy、Prettier、ESLint、TypeScript、Vite build、17 份必需文档和 19 个 Markdown 契约。全程未读取本地凭证、未访问真实 provider、未保存原始响应、未提交或推送；Step 41 后工作区共 120 个变更文件；
- Step 42 范围与文档决策（2026-08-14）：用户批准 F-001 作为一个完整垂直切片由单一 PR 交付，并接受当前 120 个变更文件的范围例外。长期 API/Agent/架构/测试契约、roadmap、任务状态、progress 和 evidence 已同步；文档检查器 23 项测试、17 份必需文档/19 个 Markdown 契约及 `git diff --check` 通过，暂存区为空；该例外不授权范围扩张、额外 live 调用或降低质量门禁；
- Step 43 本地交付（2026-08-14）：统一 `scripts/verify.ps1` 一次通过，运行时为 Python 3.13.3、Node.js 22.16.0、pnpm 11.19.0，后端 756 项 pytest、前端 64 项 Vitest、文档检查器 23 项及锁、依赖、Ruff、strict mypy、Prettier、ESLint、TypeScript、Vite build 和文档契约全部绿色；
- Step 43 范围与安全：120 个批准文件精确暂存，staged diff 与 `git diff --check` 通过；`.env.local` 保持忽略，Git 未跟踪 `.env.local`、PEM、Key 或 P8 文件，未发现 provider 原始响应或范围外路径。形成单一本地提交，未调用真实 provider、未推送或创建 PR；
- Step 44 远程交付（2026-08-14）：功能分支已推送并设置 upstream；创建 Draft PR #4 `feat: deliver single-city two-day travel planning slice`，base/head 为 `main`/`feat/f-001-single-city-two-day-plan`。PR 正文明确记录 Step 39 真实 UAT `FAIL`、F-001 `PARTIAL`、120 文件范围例外和新的 live 回归需单独授权；Windows offline verification 已触发，最终结果不在本 Step 宣称通过；
- Step 45 远程 CI（2026-08-14）：Draft PR #4 的 GitHub Actions 运行 `31807998195`、job `94791507659` 在 4 分 45 秒内成功，Windows offline verification 的 setup、统一验证和 teardown 全部通过；未发现需修复的失败检查。状态文档同步后，最终 PR head 的同一远程门禁复验通过；PR 保持 Draft，未执行 live 回归或合并；
- 补充 Step 45A 执行前门禁（2026-08-14）：功能分支与 Draft PR #4 head `3abe1c033890c70bcd4d2009fdef2753be22d5c2` 一致，工作区干净，最终 Windows offline verification 成功；三家 provider 与真实执行器均为 `ready`，`.env.local` 保持 Git 忽略，和风私钥位于仓库外。按当日官方单价和批准上限重新核算的保守费用上界低于 3.10 元；一次 DeepSeek 余额检查确认可用并计入 3 次 HTTP 上限；
- 补充 Step 45A 真实 UAT（2026-08-14）：只创建一个任务；终态 `failed`、`attempt=1`、`retryable=false`、无计划，稳定错误码为 DeepSeek `model_output_invalid`，安全诊断为 `candidate_local_validation_failed`。公开来源脱敏计数为 user 1、system 1、高德 3、和风 2；没有 DeepSeek 来源、路线来源或 AI 生成披露。公开结果不暴露 generation/repair 的分别计数，因此只确认 DeepSeek 总 HTTP 未超过 3、高德和和风均远低于 16/4 上限，不虚构更细调用数字；
- 补充 Step 45A 停止与 UI：失败后未重试、未再次提交、未进行路线补全或额外恢复调用。桌面 `1280×800` 与窄屏 `390×844` 的 `scrollWidth` 分别等于视口宽度；两种视口均无重试入口且有返回修改入口，高德/和风归因、来源和时效可见；
- 补充 Step 45A 安全边界：未保存截图、provider 原始响应、持久缓存、真实地点、路线坐标或完整用户请求。DOM 与 556 字节临时启动日志的模式扫描未发现 PEM、Bearer、Key、JWT 或原始响应标记；浏览器、本地服务均已关闭，临时日志文件已移除；
- 补充 Step 45A 结论：UAT 为 `FAIL`，但 Step 41 的 `provider_schema_invalid` / `model_output_invalid` 分类修复已由真实失败证实。当前安全诊断只说明候选本地校验失败，仍不能区分首次候选或 repair 阶段及具体安全验证码；下一修复应先离线增加不含原文/字段值的阶段和验证码诊断及纵向测试，不得放宽确定性校验。Step 46 合并继续阻塞；
- 补充 Step 45B 根因与红测（2026-08-14）：只读追踪确认 parser 已产生候选验证码，但 resolver outcome、离线 outcome 和任务执行器未把 generation/repair 阶段与验证码传到公开错误，最终只能发布 `candidate_local_validation_failed`；同时 generation/repair Prompt 没有完整表达解析器已强制的候选目录、双日顺序、父子日期、活动数、精确字段、来源和文本规则。新增 5 项针对性断言先全部失败，分别证明阶段缺失、Prompt 规则缺失和通用诊断硬编码；未读取 Step 45A 原始模型响应，因此不推测其具体字段；
- 补充 Step 45B 修复契约：resolver → offline outcome → executor → API 只传递 generation/repair 阶段与 JSON、Schema、日期、时间、POI 引用、来源引用、安全文本、截断八类闭集枚举；公开错误保持 `model_output_invalid`、`retryable=false`，内部信息缺失时才使用通用兜底。generation 与 repair 复用同一冻结候选规则，不放宽任何确定性校验，诊断不包含字段路径、字段值、模型文本或上游详情；
- 补充 Step 45B 离线验证：三家 provider 配置显式为空，测试组合禁用 `.env.local` 并拒绝非 loopback socket。专项 78 项和覆盖任务 API/失败矩阵的相关 120 项测试通过；真实 `DeepSeekAdapter` + `httpx2.MockTransport` → resolver → executor → Repository → FastAPI GET 纵向回归证明非法来源在唯一一次 repair 后稳定发布精确安全诊断，调用总数恰为 2，synthetic 原文不进入结果或 `repr`；
- 补充 Step 45B 统一门禁：Python 3.13.3、Node.js 22.16.0、pnpm 11.19.0；根目录 `scripts/verify.ps1` 一次通过，包含后端 766 项 pytest、前端 64 项 Vitest、文档检查器 23 项，以及锁、依赖、peer、Ruff format/check、strict mypy、Prettier、ESLint、TypeScript、Vite build、17 份必需文档和 19 个 Markdown 契约。未调用真实 provider、未读取本地凭证、未提交、推送或修改 PR；
- 补充 Step 45C 执行前门禁（2026-08-14）：当前分支与 HEAD `3abe1c033890c70bcd4d2009fdef2753be22d5c2` 正确，工作区恰有 19 个 Step 45A/45B 预期文件，暂存区为空，Draft PR #4 为 OPEN/Draft 且 Windows offline verification 成功；`.env.local` 保持忽略、私钥位于仓库外，三家 provider 与真实执行器均为 `ready`。DeepSeek 余额可用性检查成功并计入 3 次 HTTP 上限；按当日官方价、已发布配额与任务硬预算重新核对的最坏费用仍低于 12 元；
- 补充 Step 45C 真实结果（2026-08-14）：只创建一个杭州双日任务；模型候选通过本地严格校验并生成完整两日结构，最终确定性校验产生 2 项 `route_conflict`，路线保持未验证，任务终态 `conflict`、attempt 1，真实 UAT 为 `FAIL`。没有 `provider_schema_invalid`、`model_output_invalid` 或 `internal_error`，因此没有候选 diagnostic_code；
- 补充 Step 45C 数据摘要：公开来源计数为 user 1、system 1、高德 3、和风 2、DeepSeek 1；住宿、城际交通和门票 3 项费用保持 unknown，已知餐饮合计 400 元，预算为 indeterminate。调用证据只声明 DeepSeek 总 HTTP 不超过 3（含 1 次余额检查）、高德不超过 16、和风不超过 4，不虚构公开结果未提供的精确 provider 调用次数；
- 补充 Step 45C UI 与安全：桌面 `1280×800` 的 `scrollWidth=1265`，窄屏 `390×844` 的 `scrollWidth=375`；1 次 POST 后只有同任务 3 次 GET，视口切换没有增加请求，无 retry、第二次提交或额外恢复动作。控制台 0 error/0 warning，DOM 与 1070 字节临时日志的秘密/原始响应模式扫描无命中；未制作截图、保存 provider 原始响应、持久缓存、完整请求、真实路线坐标或路线明细，本次精确临时快照/日志已移除，浏览器及本地服务已关闭；
- 补充 Step 45D 红测与根因（2026-08-14）：解析层分别接受首项贴合窗口起点、末项贴合窗口终点和不同地点活动零间隔的三个新用例；纵向编排用例实际得到 `conflict` 而非预期的 repair/ready，并复现两天路线补全被跳过。纯领域 `DailyRoutePlan` 已有 `route_gap_not_positive` 规则，因此根因确定为候选准入与路线领域规则漂移，而非高德路线响应、鉴权或最终校验放宽；
- 补充 Step 45D 修复契约：候选解析在住宿锚点和两日窗口齐备时复用 `DailyRoutePlan.expected_legs()`；活动必须落在对应窗口内，住宿到首项、不同地点活动之间及末项返回住宿必须具有正数交通分钟。失败沿现有 `candidate_time_invalid` 进入最多一次 repair；generation/repair Prompt 复用同一规则；同地点连续活动无需自环路线，provider 返回路线时长超过间隔仍为最终硬冲突；
- 补充 Step 45D 离线验证：三家 provider 环境值显式为空，测试组合禁用 `.env.local` 并拒绝非 loopback 网络。候选、编排、路线领域和 DeepSeek adapter 专项 162 项通过；根目录 `scripts/verify.ps1` 在 Python 3.13.3、Node.js 22.16.0、pnpm 11.19.0 下一次完整通过，包含后端 772 项、前端 64 项、文档检查器 23 项和全部格式、lint、strict mypy、TypeScript、Vite build、17 份必需文档与 19 个 Markdown 契约；未调用真实 provider、暂存、提交、推送或修改 PR；
- 补充 Step 45E 执行前门禁（2026-08-14）：当前分支与 HEAD `3abe1c033890c70bcd4d2009fdef2753be22d5c2` 正确，工作区恰有 21 个既定 Step 45B–45D 变更文件且暂存区为空；Draft PR #4 为 OPEN/Draft、head 一致且 Windows offline verification 成功；`.env.local` 保持忽略、私钥位于仓库外，三家 provider 与真实执行器均为 `ready`。按当日 DeepSeek 官方单价与固定 8000 输出 token 上限重新计算的三家保守费用低于 12 元；未执行独立余额或 provider 探针；
- 补充 Step 45E 真实结果（2026-08-14）：只创建一个杭州双日任务；generation 候选未通过时间可行性准入，唯一一次 repair 后仍失败。终态为 `failed`、attempt 1、`retryable=false`、无计划，稳定错误为 DeepSeek `model_output_invalid`，安全诊断为 `candidate_repair_time_invalid`。该证据证明 Step 45D 新准入规则在 live 路径生效，但不能确定未记录的字段值或具体时间安排；
- 补充 Step 45E 来源、UI 与安全：公开来源脱敏计数为 user 1、system 1、高德 3、和风 2，没有 DeepSeek 计划来源或路线补全来源。桌面 `1280×800` 的 `scrollWidth=1265`，窄屏 `390×844` 的 `scrollWidth=375`，均无水平溢出；页面无 retry、有返回修改入口，高德/和风归因与时效可见，控制台 0 error/0 warning。仅 1 次 POST 和同任务 4 次 UI GET，另有 3 次同任务只读安全诊断 GET，均不触发 provider；没有第二次提交、retry 或独立 provider 探针；
- 补充 Step 45E 数据边界：未保存截图、provider 原始响应、持久缓存、真实地点、坐标、路线明细或完整请求。DOM、5 个本次浏览器临时文件和 4 个空运行日志的秘密/原始响应模式扫描无命中；上述临时文件已精确移除，浏览器及本地服务已关闭；
- 补充 Step 45F 红测与根因（2026-08-15）：只使用 synthetic/fake/MockTransport。六项初始断言先因缺少时间子类而失败；代码追踪确认 `DailyRoutePlan` 已稳定区分活动越窗、访问顺序错误和 `route_gap_not_positive`，但候选解析器统一压缩为 `candidate_time_invalid`，resolver 也只把该通用码交给 repair。没有读取或推测 Step 45E 原始模型输出；
- 补充 Step 45F 诊断契约：时间失败闭集为 `activity_outside_day_window`、`accommodation_to_first_gap_not_positive`、`between_locations_gap_not_positive`、`last_to_accommodation_gap_not_positive` 和 `day_schedule_capacity_exceeded`。resolver → outcome → executor → API 只传递 generation/repair 阶段和该无值枚举；公开错误保持 `model_output_invalid`、`retryable=false`，最多一次 repair；
- 补充 Step 45F repair 边界：DeepSeek repair payload 在既有完整 PlanningContext、冻结 Schema 和候选规则之外，只增加项目静态 `validation_time_failure` 与对应 `validation_hint`。提示不包含字段路径、字段值、时间值、地点、坐标、模型文本或上游详情；日期、时间、路线连续性和最终路线时长校验未放宽；
- 补充 Step 45F 离线验证：专项 165 项通过；真实 DeepSeek adapter + `httpx2.MockTransport` → resolver → orchestrator → executor → Repository → FastAPI GET 纵向回归证明 generation 细类进入唯一一次 repair、repair 再失败发布另一稳定细类，且路线 provider 未被调用。后端全量 786 项通过；根目录统一门禁同时覆盖前端 64 项、文档检查器 23 项及全部格式、lint、strict mypy、TypeScript、Vite build 和文档契约；
- 补充 Step 45F 架构结论：generation/repair 原有 Prompt、PlanningContext 和冻结规则已完整携带日窗口、住宿锚点和正数交通窗口，没有新的可证实规则遗漏。三次 live UAT 仍未形成 ready/partial 计划，继续纯 Prompt 调优缺少工程依据。该 Step 只提出 D-009，未在当时实施；用户随后在 Step 45G 前正式批准该方向，Step 46 继续阻塞；
- 补充 Step 45G 架构证据（2026-08-15）：用户正式批准 D-009 的职责迁移。只读代码追踪确认当前 `CandidateActivity` 同时要求模型给出 POI 与精确起止时间，而 `OfflinePlanningOrchestrator` 在模型候选之后才调用 `_enrich_routes`；模型生成时没有高德实际路线时长，因此继续 Prompt 调优不能消除信息缺口；
- 补充 Step 45G DTO 与兼容结论：推荐新增无最终时间的 `PlanProposal`/`ActivitySelection`，确定性 scheduler 再生成现有 `PlanCandidate`。该方案可保持 `TripPlanRequest`、`TripPlanResponse`、前端和 Repository Schema 不变，继续复用 `DailyRoutePlan` 与 final validation；把现有 candidate 时间字段改为 optional 的方案因阶段不变量模糊而被否决；
- 补充 Step 45G 调用预算结论：当前每日至多 3 项时，双日完整住宿往返链最坏已占 8 段，无法保证删除活动后仍有桥接路线预算。用户已批准 F-001 每日最多 2 项，使正常链最坏 6 段，并为每天一次 optional 调整各预留 1 段，最坏仍为 8；
- 补充 Step 45G 诊断复审：代码将 `activity_visit_order_invalid` 直接映射为 `day_schedule_capacity_exceeded`，但顺序/重叠错误不等同于容量不足。目标契约要求 `schedule_capacity_exceeded` 只能来自实际路线、缓冲与游览时长的确定性总量计算；Step 45F 四类 gap 诊断只作为迁移前回归保留；
- 补充 Step 45G 范围与交付结论：用户已批准先单独授权提交 Step 45B–45G，再以功能分支为 base 建立 stacked PR 隔离 Step 45H；最终仍由 PR #4 面向 main 交付。Step 45H 的 24–34 个文件、1200–2200 行新范围例外及全部九项实施决策均已批准，但生产实现仍需单独授权；
- 补充 Step 45H 红测证据（2026-08-15）：新增 proposal 与 scheduler 测试首次在 collection 阶段因缺少 `DeepSeekProposalResolver` 和 `RouteRequirement` 失败，证明测试先于生产实现；随后以最小 DTO、严格 parser、DeepSeek proposal Schema 和纯 scheduler 转绿；
- 补充 Step 45H 信任边界：模型输出每日 1–2 项 POI、连续优先级、required/optional、short/standard/long/unknown 和 POI 来源；任何最终时间、路线、route duration、verified、provider 或终态字段被精确额外字段规则拒绝。generation 与 repair 共用 Schema，仍最多一次 repair；
- 补充 Step 45H 调度证据：代码按住宿往返和跨地点链查询实际路线，使用 60/120/180 分钟、景区/博物馆 120 分钟缺省及步行/公交 10/15 分钟缓冲生成分钟级时间。固定输入重复结果一致，同地点不查自环；每天最多一次最低优先级 optional 移除并按需补一条桥接路线，总路线调用仍不超过 8；
- 补充 Step 45H 终态证据：无规则 unknown 通过新增 `planning → needs_input` 收口；required 容量不足为 `conflict`；路线 unavailable、缺坐标或端点/方式不合法不发布计划并进入 `failed`；partial provider 只有仍携带合法 `RouteLeg` 才能形成带计划 `partial`。existing `DailyRoutePlan` 和 final validation 未放宽；
- 补充 Step 45H 兼容与安全：`TripPlanRequest`、`TripPlanResponse`、Repository 和前端 Schema 未变化；旧精确时间 parser 只保留迁移回归，生产编排改用 proposal resolver。执行期间 `APP_ENV=test`、provider 配置为空、非 loopback 网络阻断；没有读取 `.env.local`/私钥、调用真实 API、执行 live UAT、暂存、提交、推送或修改 PR；
- 补充 Step 45H 门禁：统一 `scripts/verify.ps1` 在 Python 3.13.3、Node.js 22.16.0、pnpm 11.19.0 下通过，覆盖后端 818 项、前端 64 项、文档检查器 23 项及 Ruff、strict mypy、Prettier、ESLint、TypeScript、Vite build、锁文件和文档契约；首次运行只因一条测试中的多余 `type: ignore` 被 strict mypy 拒绝，移除机械注释后全入口从头通过；
- 补充 Step 45I 范围与职责审查（2026-08-15）：分支为 `feat/f-001-cr1-deterministic-scheduling`，基线/HEAD 为 `231db4bbd929443b6a6b986994d9f932d4e0f407`，暂存区为空、无 upstream；审查开始时完整工作区含 24 个 tracked 修改和 3 个 untracked 文件，共 27 文件、`+2158/-281`，无新增依赖或范围外文件。同步本 Step 允许的五份脱敏结论文档后仍为 27 文件，当前总差异为 `+2188/-286`。审查确认正常生产路径使用无最终时刻 proposal，实际路线之后由确定性 scheduler 形成既有 candidate，最终校验仍独立执行；未发现 P0/P1 生产缺陷；
- 补充 Step 45I findings：新 proposal parser 对重复键、日期、目录外 POI 和来源的拒绝虽已实现，但缺少新生产路径的直接负向测试；新 proposal → scheduler → executor → Repository → API 未完整锁定五种终态；被移除 optional 的历史路线 partial/error 未被测试证明不会污染最终 ready；60/120/180 与景区/博物馆缺省缺少完整直接断言。另发现 `api-contract.md`、`testing-strategy.md`、`docs/README.md` 和部分项目状态文档仍保留 D-009 实施前语义；上述 P2 缺口阻塞精确暂存和 stacked PR；
- 补充 Step 45I 离线与安全证据：在 `APP_ENV=test`、三家 provider 配置为空、非 loopback 网络阻断下，proposal/scheduler/adapter/orchestrator/executor 专项 127 项通过；统一 `scripts/verify.ps1` 再次通过后端 818 项、前端 64 项、文档检查器 23 项及全部 format、lint、strict typecheck、build、锁和文档契约。`.env.local` 保持 Git 忽略，tracked 秘密/PEM 扫描无命中；未读取 `.env.local` 或私钥，未联网、调用 provider、执行 live UAT、暂存、提交、推送或修改 PR；
- 补充 Step 45J findings 关闭（2026-08-15）：proposal 新路径直接覆盖三层重复键、未知字段、日期顺序/父子日期、目录外 POI、非法/重复来源和单次 repair 脱敏；scheduler 直接锁定 60/120/180 与景区/博物馆 120；optional 历史 route partial/error 不污染最终 ready；真实 executor → Repository → GET API 覆盖 partial、conflict、needs_input、failed、route retryable/source/uncertainty 和 warning 投影。门票 unknown 不按 0，ready 继续由零 unknown 冻结契约覆盖；
- 补充 Step 45J 门禁与安全：专项 125 项、统一后端 838 项、前端 64 项、文档检查器 23 项及全部 format/lint/typecheck/build 通过；最终 27 文件、`+2559/-297`，低于批准上限。只修改测试和文档，未读取凭证、调用 provider、执行 live UAT、暂存、提交、推送或修改 PR；
- 补充 Step 45K 远程交付（2026-08-15）：27 个批准文件精确形成提交 `bb52adea871c6cadc21ceaa5ef4255b79c3904cb`，推送 `feat/f-001-cr1-deterministic-scheduling` 并创建以 `feat/f-001-single-city-two-day-plan` 为 base 的 stacked Draft PR #5；Windows offline verification run `31867996619` 对相同 head 成功。PR #4/#5 保持 Draft，未 live 或合并；
- 补充 Step 45L 独立 review（2026-08-15）：核对 PR #5 单提交、27 文件、`+2559/-297`、base/head/Draft、成功 CI 和 stacked 依赖；专项 147 项、文档检查器 23 项、diff/秘密扫描通过，未发现当时可证实的 P0/P1 生产缺陷。发现 API 状态表及项目管理状态漂移，允许随下一次 UAT 证据收口但阻塞 PR ready；
- 补充 Step 45M 执行前门禁（2026-08-15）：分支、HEAD/upstream、PR #5 head、成功 CI、干净工作区和空暂存一致；无网络本地构造只输出 `deepseek=ready`、`amap=ready`、`qweather=ready`、`executor=ready`，私钥位于仓库外。冻结策略上限为 DeepSeek 2、高德总计 12/路线 8、和风 2，低于批准的 3/16/8/4；项目记录的高峰费用上界 9.274 元低于 12 元，未执行余额或 provider 探针；
- 补充 Step 45M 真实结果：现有 Web UI 只创建一个任务，终态 `failed`、attempt 1、`retryable=false`、无计划；唯一错误为高德 `data_missing`，`diagnostic_code=null`，无 violation/warning，只有 `activity_duration_estimated_model` uncertainty。来源计数为 user 1、system 1、高德 7、和风 2、DeepSeek 1；公开结果不足以安全推导具体失败路线、地点或精确 provider HTTP 次数；
- 补充 Step 45M 产品与安全证据：DeepSeek AI 披露、高德/和风归因与 freshness 可见；桌面 `1280×800` 的 `scrollWidth=1265`，窄屏 `390×844` 的 `scrollWidth=375`，均无水平溢出。只有 1 次 POST；同任务 GET 包含 UI 有界轮询及 1 次脱敏终态读取，不触发 provider。无 retry、第二个任务或额外探针，控制台 0 error/0 warning，DOM 和 5 个临时浏览器文件秘密模式扫描无命中；未保存截图、原始响应或持久缓存，临时文件和 `8000/5173` 服务均已关闭清理；
- 补充 Step 45M follow-up findings：公开请求允许同时选择步行和公交，但执行器无条件选择公交且没有用户允许方式内的 fallback；本次路线阶段 `data_missing` 与此缺口一致，但在无原始响应条件下不将其表述为唯一上游根因。另证实路线 unavailable 公开错误缺少稳定 `route_data_unavailable` diagnostic，前端可达状态表遗漏后端已允许的 `planning → needs_input`。下一步必须先离线修复并建立纵向测试，不得自动再次 live；
- 补充 Step 45N 离线修复证据（2026-08-15）：红测先证明双交通只走公交、`data_missing` 无路线 diagnostic 和前端拒绝 `planning → needs_input`；实现后，单路段公交 unavailable 只增加一次步行调用并形成混合 mode 计划，四段双模式均 unavailable 精确 8 次后公开 `route_fallback_exhausted`，六段压力样例在 8 次停止并输出 `route_call_budget_exhausted`。非法端点和缺坐标分别输出 `route_result_invalid`、`route_coordinates_missing`；
- 补充 Step 45N 纵向与安全证据：proposal → orchestrator → mixed-mode scheduler → executor → Repository → GET API 验证成功降级不保留未采用公交错误、保留 warning、按实际 mode 计算缓冲和公交费用；前端 App 接受 `planning → needs_input`。应用/adapters/路线领域专项 479 项、前端 65 项通过；冻结 Python 3.13.3、Node.js 22.16.0、pnpm 11.19.0 下统一门禁完整通过，包含后端 842 项、前端 65 项、文档检查器 23 项及依赖锁、格式、lint、strict mypy、TypeScript 和 Vite build。全程 `APP_ENV=test`、provider 配置为空、非 loopback 由测试夹具阻断，未读取 `.env.local`、调用 provider、执行 live UAT、暂存、提交、推送或修改 PR；
- 补充 Step 45O 独立审查（2026-08-15）：离线稳定复现 AUTH 首次失败后仍执行 8 次路线调用；ManualClock 在首个 route reserve 前时间不足和 route complete 后超过总期限时均公开 `internal_error`；18 位路线时长可超过 `timedelta.max`；额外未引用来源、wrong-provider envelope 和 operation 无关 diagnostic 存在投影风险。结论为不准入 live；
- 补充 Step 45P 红绿证据（2026-08-15）：修复前新增回归精确得到 9 个失败；修复后领域、Amap MockTransport、orchestrator、executor、Repository 和 GET API 专项 157 项通过。AUTH/Schema/timeout/rate/server/unknown 最多只完成当前两路并发批次且不进入 fallback；业务空结果与无 provider error 的本地非法路线仍能合法步行降级；deadline 不再产生 `internal_error`；`2147483647/2147483648` 米与 `1440/1441` 分钟边界、wrong provider/mode/source、额外来源和 POI/路线 diagnostic 分离均被锁定；统一 `scripts/verify.ps1` 最终通过后端 859 项、前端 65 项、文档检查器 23 项及依赖锁、格式、lint、strict mypy、TypeScript、Vite build 和文档契约；
- 补充 Step 45Q 独立复审（2026-08-15）：纯离线复现同一两路批次为 `[AUTH, EMPTY_RESULT]` 时仍额外发起 walking fallback；另复现一路非治理异常返回后同批 peer 仍处于 active 且继续运行。两项 P1 均阻塞 live，结论为 `DONE_WITH_BLOCKERS`；未读取凭证、访问 Provider 或修改文件；
- 补充 Step 45R 红绿证据（2026-08-15）：修复前纵向用例精确得到 3 次路线调用而非 2 次，异常用例证明 peer 未取消；修复后 AUTH/Schema/timeout/rate/server/unknown 与 EMPTY_RESULT 混合、terminal 与本地非法混合、前批可降级后批 terminal 等 8 项批次用例，以及 2 项 executor/Repository/GET API 与异步清理用例全部通过。批次 terminal 阻止所有后续首选与 fallback；异常 peer 在发布终态前已 cancel/drain，`active_route_calls == 0`。路线专项 182 项及统一门禁通过，统一入口包含后端 869 项、前端 65 项、文档检查器 23 项和全部静态、类型、构建、依赖与文档契约；未调用真实 Provider、执行 live、暂存、提交、推送或修改 PR；
- 补充 Step 45S 独立复审（2026-08-15）：核对分支/HEAD/upstream、26 个已跟踪未暂存文件、`+1574/-98`、空暂存/无未跟踪文件，以及 PR #4/#5 的 Draft/base/head/CI 事实；代码与测试复核未发现 P0/P1 生产缺陷。专项 233 项与统一门禁再次通过，统一入口包含后端 869 项、前端 65 项、文档检查器 23 项；只读外部任务取消探针得到两路 peer 均取消、`active_route_calls=0`、无遗留任务。仓库测试尚未固化外部任务取消与 fallback 批次 terminal，架构 Step 归属文字也待收口；这些不阻塞一次单独授权的受控 live，但应在提交和 PR ready 前关闭。未读取 `.env.local`/私钥、调用 Provider、执行 live、暂存、提交、推送或修改 PR；
- 补充 Step 45T 真实 UAT（2026-08-15）：在 head `bb52adea871c6cadc21ceaa5ef4255b79c3904cb` 加 26 个已审查工作区文件上只创建一个任务，终态为完整双日 `partial`，无 error/violation/retry。每天 2 项活动和 3 段公交路线通过时间窗口、无重叠、住宿往返、路线时长及固定缓冲校验；3 项费用保持 unknown，已知合计 520 元，预算为 `budget_indeterminate`；
- Step 45T 调用与来源边界：没有独立探针，调用受 DeepSeek 3、高德 16/路线 8、和风 4 和总费用 12 元上限；公开来源计数为 user 1、system 1、高德 9、和风 2、DeepSeek 1。全部首选公交路线直接可用，因此没有触发步行 fallback 或 fallback warning，不将本次结果虚构为真实混合方式质量证据；
- Step 45T UI 与安全：桌面 `1280×720` 为 `scrollWidth=1265`，窄屏 `390×844` 为 `scrollWidth=375`；来源、freshness、AI 披露、unknown 和返回修改入口可见，控制台 0 error/0 warning，DOM 秘密模式 0 命中。仅一次有效 POST，无第二任务或 retry；临时视口恢复、`8000/5173` 服务停止。未保存截图、Provider 原始响应、地点/坐标/路线明细、完整请求或持久缓存，未暂存、提交、推送或修改 PR。UAT 结论为 `PASS`；
- 补充 Step 45U 离线收口（2026-08-15）：新增六类 provider-wide terminal 首次出现在 fallback 批次的参数化纵向回归，四个公交首选空结果形成候选后，首个两路 walking 批次可完成，但不再启动后续 fallback；GET API 分别保留鉴权、Schema、timeout、限流、server、unknown 的冻结公开 code、`route_primary_unavailable` 和 retryable 语义，且不投影无效路线来源或路线不确定性。另以事件同步确认两路 route peer 均进入等待后取消外层规划 task，`CancelledError` 原样传播、两路 peer 均被 cancel/drain、governor 活动调用归零且没有后续调用。两份核心测试 115 项、路线/调度/executor/Repository/API 专项 292 项通过；统一 `scripts/verify.ps1` 通过后端 876 项、前端 65 项、文档检查器 23 项及格式、lint、strict mypy、TypeScript、构建、依赖锁和文档契约；
- 官方来源：[DeepSeek 模型与价格](https://api-docs.deepseek.com/zh-cn/quick_start/pricing)、[DeepSeek 用户协议](https://cdn.deepseek.com/policies/zh-CN/deepseek-terms-of-use.html)、[DeepSeek 开放平台服务协议](https://cdn.deepseek.com/policies/zh-CN/deepseek-open-platform-terms-of-service.html)、[高德服务升级与配额](https://lbs.amap.com/upgrade)、[高德开放平台服务协议](https://lbs.amap.com/pages/terms/)、[和风天气定价](https://dev.qweather.com/docs/finance/pricing/)、[和风天气注明来源](https://dev.qweather.com/docs/terms/attribution/)、[和风天气实时预警响应契约](https://dev.qweather.com/docs/api/warning/weather-alert/)；
- Step 27 浏览器：本地 Microsoft Edge 使用本机 synthetic partial/failed 响应验证 retry 恢复、双击只产生一次请求、attempt 2、旧终态清理和返回修改焦点；`390×844` 下输入区域折叠、结果优先且无水平溢出，干净会话控制台 0 error/0 warning；
- 请求边界：Step 35 浏览器业务请求仅为同源任务 API；DeepSeek、高德与和风 adapter 专项测试使用进程内 mock transport。Step 40 发现默认 API 测试组合根可能因 `.env.local` 装配真实执行器；Step 41 已用导入前 `APP_ENV=test`、禁用 dotenv source 和非 loopback socket 阻断关闭该风险，并由统一入口复验；
- 真实性边界：Step 38 只证明执行时三家鉴权与所触达 live Schema 可用，并证明一次高德公交路线契约；Step 45A 只证明修复后的本地候选错误分类与安全失败展示有效。两者都不证明持续可用、全部端点、结果质量或下一次费用；
- 未覆盖：混合交通方式 fallback 的真实 Provider 结果质量、长期配额和费用稳定性。完整双日 partial 和通过式真实数据 UAT 已由 Step 45T 覆盖；stacked 合并与归档已由 Step 46–47 完成；本次 live 授权已经消耗，不得自动再次调用。

### Step 46–47：stacked 合并与 F-001 归档

- Step 46 结论：`PASS`。PR #5（base `feat/f-001-single-city-two-day-plan`）先合并，merge commit 为 `4cf20235e0f51a6422c2404385aa2206cb553de7`；其新功能分支 head 的 Windows offline verification run `31881089652` 成功。
- PR #4 相对 `main` 的累计差异为 124 文件、`+34079/-584`；独立 review、`git diff --check`、文档检查、范围追溯和秘密扫描通过，未发现 P0/P1 阻塞缺陷。PR #4 正文已校正 D-009、Step 45M FAIL、Step 45T PASS、unknown 费用和 stacked 顺序后标记 ready 并合并。
- PR #4 merge commit 为 `d05e997dbeaa676702704ce791287eb036c80a6c`。合并后 main Windows offline verification run `31881327869` / job `95004221033` 成功；本地 `main` 与远程同步，工作区干净。
- Step 47 结论：`PASS（文档归档）`。仅修改权威项目文档并运行离线门禁；未调用 DeepSeek、高德或和风天气真实 API，未修改产品代码、公开 API、DTO、UI 或依赖。
- 归档边界：F-001 已交付但产品状态保留 `PARTIAL`；Step 45T 的完整双日 partial 为通过式真实证据，Step 45M 的 failed 为历史 FAIL 证据；门票等非关键费用保持 `unknown`，不按 0 处理；混合交通 fallback 仍只有离线测试证据。

### B-000：项目与工程基线

- 任务状态：`DONE`
- 最终验收结论：`PASS`
- 完成日期：2026-08-13
- 交付：PR #1 已 squash merge 为 `f10b1736b4f00386d653f430b24109e91fc888ec`；PR #2 已完成归档收口并 squash merge 为 `a21300c8c70764eb4aafc798bc54878373b5e3a0`；该归档提交的 `main` CI 运行 `31703994453` 通过；
- 已完成 Step 的检查属于实施进度验证，不是 B-000 最终验收证据；Step 8 已通过后端 Ruff、mypy、pytest 和本地健康请求；
- Step 8 红绿证明：受控注入未批准健康状态后，健康契约测试失败；恢复固定 `ok` 状态后全套 7 项测试通过；
- Step 9 已通过 Prettier、ESLint、TypeScript、组件测试、peer 检查和生产构建；受控移除重试触发后恢复测试失败，恢复实现后全套门禁重新通过；最终 review 后前端测试数为 13；
- Step 10 本地 Chromium 实现者验证：`127.0.0.1:5173` 初始健康请求 200；停止后端后重试 502 并显示可恢复错误；重启后端再重试 200 并恢复成功。受控延迟时 loading 可读且按钮禁用；390px 窄屏无水平溢出；Tab 可聚焦重试按钮；全部浏览器请求仅指向本机；
- Step 11 统一入口在 Windows PowerShell 5.1 下通过：Python 3.13.3、Node 22.16.0、pnpm 11.19.0，锁文件/依赖、后端测试、前端测试与 build、文档检查器测试及必需文档契约均为绿色；收口后的稳定计数为后端 7、前端 13、检查器 20、必需文档 15；
- Step 11 红绿证明：临时断链使文档检查精确报告 `README.md` 目标且统一入口返回 1；恢复后完整统一入口再次通过；
- Step 12 CI 契约：Windows runner、只读仓库权限、禁用 checkout 凭证持久化、空业务 provider 凭证、四个 Action 完整 SHA 和唯一统一门禁入口均通过本地检查；
- Step 12 负向证明：临时把 checkout 完整 SHA 改为浮动标签后，检查器以 `ci-action-pin` 返回 1；恢复后包括 10 项检查器测试的完整统一入口再次通过；
- Step 13 独立门禁：统一入口全绿；定向通过 5 项后端凭证/schema/404/非法端口、8 项前端 schema/失败恢复，以及 4 项文档/安全负向契约；
- Step 13 浏览器 QA：本地 Chromium 验证成功、后端停止错误、重启恢复、390px 无水平溢出和键盘聚焦；网络清单 33 条请求全部指向 `127.0.0.1:5173`，未访问业务 provider；
- Step 13 范围与安全：`git diff --check` 通过，0 暂存、0 远程；50 个未跟踪文件均位于批准结构内，provider 凭证仅为空模板，运行时无旅行规划或真实 provider 客户端；Agent1 和 `E:\Vibe coding` 未被本 Step 写入；
- Step 13 结论：`PASS`，无阻塞缺陷；另记录一个非阻塞关注项：文件数 50 超过原 40 个停止阈值。该数量已在用户批准 Step 13 前披露，本 Step 没有新增文件；
- Step 14 用户 UAT：用户确认成功、错误、重试恢复、文案和窄屏表现均符合预期，结论为 `PASS`；
- Step 14 本地交付：统一门禁、精确文件清单、staged diff、空凭证与敏感信息边界审查通过，B-000 基线形成单一、本地提交；
- Step 15 远程交付：私有仓库、远程 `main`、任务分支和 Draft PR #1 已创建；运行 `31698367871` 与 `31698957491` 因 Windows uv 冷启动版本探测失败，提交 `c229233` 后运行 `31699542476` 通过；
- Step 15 review：构建依赖约束、健康请求超时、CI 安全契约、冷启动回归覆盖、前端失败契约和状态文档六项 finding 均已关闭；提交 `b1d7ce0` 的本地门禁与远程运行 `31701500542` 通过，最终复审无新阻塞问题；
- Step 16：用户批准合并和归档；PR #1 于 2026-08-13 合并，PR #2 随后完成归档收口；归档提交的 `main` Windows CI 运行 `31703994453` 在 2 分 45 秒内通过。
- B-000 可宣称工程基线交付完成；不能宣称旅行规划业务、SQLite 业务 Schema 或真实外部服务通过。

## 每个任务的证据结构

任务验收时按以下结构新增或覆盖该任务的当前结论：

```text
## <任务编号：名称>

- 结论：PASS | FAIL | BLOCKED | PARTIAL
- 分支：
- 提交：
- 环境：
- 验收日期：
- 实现者验证：
- 独立 QA：
- 用户 UAT：

### 自动化门禁
| 验证项 | 风险/需求 | 命令入口 | 预期 | 实际摘要 | 结论 |

### 负向与红绿证明
| 错误类别 | 失败证明 | 恢复后结果 | 结论 |

### 人工验收
| 场景 | 步骤摘要 | 实际结果 | 结论 |

### 外部服务证据
| Provider | 模式 | 执行时间 | 范围 | 脱敏结果 | 有效边界 |

### 未覆盖范围与剩余风险
- ...

### 最终结论
- ...
```

未适用的章节标记“不适用”并说明原因，不能直接删除以隐藏未验证范围。

## 证据记录规则

- 命令记录稳定入口，不复制完整输出；
- `PASS` 必须同时说明覆盖范围，不能只写“测试通过”；
- 失败后重跑必须保留最终结论，并在负向证明中说明覆盖的错误类别；
- 代码、测试、Schema 和 Git 事实与文档冲突时，先修正文档或实现，再记录结论；
- 实现者验证、独立 QA、CI 和用户 UAT分别记录，不能相互替代；
- 没有远程时不能写“CI 通过”；没有真实凭证时不能写“provider 可用”；
- live smoke 结论必须记录执行时间，因为第三方可用性会变化；
- mock、fake、fixture 和回放结果明确标记为离线，不作为真实服务证据；
- 证据文件只保留最终摘要，详细临时日志在确认不再需要后按项目安全规则处理。

## B-000 最终证据要求

B-000 关闭前至少需要：

| 类别 | 必需证据 | 当前状态 |
| --- | --- | --- |
| 运行时 | Python 3.13.3、Node.js 22.16.0 和包管理版本检查 | PASS：本地、独立 QA 和 Windows 远程 CI 通过 |
| 后端 | 健康 API 测试、成功请求和错误边界 | PASS：实现者与 Step 13 独立 QA 均通过 |
| 前端 | loading/success/error/retry 组件测试和本地浏览器结果 | PASS：实现者、独立 QA 和最终用户 UAT 均通过 |
| 统一门禁 | format、lint、typecheck、test、build、docs、CI contract | PASS：review 修复后的本地门禁与 Windows 远程 CI 通过 |
| 安全 | `.env.local` 忽略、敏感模式和 staged diff 检查 | PASS：ignore、空凭证、敏感模式、独立 QA 和 staged diff 审查通过 |
| 离线边界 | 默认测试不访问真实第三方服务 | PASS：运行时审查无 provider 客户端，Chromium 请求清单仅包含本机 |
| 范围 | 无旅行业务逻辑、无 Agent1 或目标外修改 | PASS：范围符合；另记录文件数超过原估算与阈值的非阻塞关注项 |
| 独立 QA | 负向测试、diff 和文档一致性审查 | PASS：Step 13 完成，无阻塞缺陷 |
| 用户 UAT | 本地启动、后端故障、重试恢复、文案和窄屏表现 | PASS |
| GitHub 交付 | push、PR、远程 CI、review、merge | PASS：PR #1 交付基线，PR #2 完成归档为 `a21300c`，其 `main` CI 运行 `31703994453` 通过 |

B-000 的自动化、独立 QA、用户 UAT、GitHub 交付和归档均已完成。任务归档见 [B-000 project baseline](../archive/task-cards/B-000-project-baseline.md)。

## 外部服务证据边界

B-000 不调用 DeepSeek、高德或和风天气，因此本任务不会产生真实 provider 证据。

后续任务记录 live smoke 时只保存：

- provider 和测试能力；
- 执行时间与项目版本；
- 使用的测试环境名称，不保存 Key；
- 请求类别和次数摘要，不保存不必要用户数据；
- HTTP/项目稳定状态和脱敏字段摘要；
- 配额、时间和字段覆盖限制；
- 是否能重现以及失效条件。

第三方成功一次只证明该时间点、该账户权限和该样例可用，不能证明永久可用或所有数据完整。

## 禁止记录

- API Key、Token、Cookie、密码、私钥和连接串；
- `.env` 或 `.env.local` 内容；
- 完整 Prompt、完整模型响应或 provider 原始响应；
- 真实个人行程、联系方式和支付信息；
- 完整终端日志、浏览器网络导出和大体积构建产物；
- 未经验证的“应该通过”“看起来正常”或假成功结论。
