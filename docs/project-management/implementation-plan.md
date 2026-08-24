# 最近关闭计划：F-006 MVP 体验收口与本地验收

## 当前状态

当前无活动任务，因此没有正在执行的 Step。

- 当前任务：无
- 当前 Step：无；F-006 Step 0–8 已全部完成
- 最近关闭：`F-006 DELIVERED / LOCAL_ACCEPTANCE_PASS / ARCHIVED`
- 完整功能 main：`d82ca5c65794749932be65724455aca146a7cbca`
- 完整功能 main CI：run `32691778088`，`PASS`
- 归档任务卡：[F-006 archive](../archive/task-cards/F-006-mvp-local-acceptance.md)
- 基线：`main == origin/main == b99d5fc4c89b0f25ec89e4e12cd1755a7c3be46f`
- F-004C：`DELIVERED / ARCHIVED`；PR #34/#35/#36、归档 PR #37 和 CI run `32486428083` 已完成
- F-004B2：`BLOCKED / ARCHIVED`

## Step 0：激活与治理

唯一目标：在已核实的干净归档 main 上激活 F-006，建立 D-017、Step 0–8、四层 stacked PR、核心文件、受控相邻扩展和规模阈值。

状态：`DONE / PASS`。Git/PR/CI/归档复核、D-017、任务卡、Step 0–8、四层 stack、核心文件、规模阈值和首层本地分支均已完成；文档检查器及其 24 项测试、`git diff --check`、范围和秘密模式审计通过。没有源码、测试、数据库、秘密读取、Provider/软件包仓库访问、commit、push、PR 或远程 CI。

允许：

- 只读核对 main/origin/main、工作区、PR #34–#37、CI run `32486428083`、F-004C archive、开放 PR 和活动任务；
- 修改批准的当前治理与权威文档；
- 在确认 main 干净后创建 `feat/f-006-local-runtime-compatibility`。

必须记录但不实现：

- 无凭证/配置不完整 job 可能停留 draft；
- 全版本统一恢复 pointer 与旧 V3/V4 pointer 兼容；
- 当前终态/已恢复任务 DELETE UI；
- 安全 PowerShell 本地运行入口；
- 组合式离线 journey/browser/clean-checkout 验收。

完成门禁：Git/PR/CI/归档事实一致；F-006 唯一 ACTIVE；五份当前入口一致；D-017、核心文件、stack 和阈值明确；文档检查器及其测试、`git diff --check`、范围和秘密模式审计通过；diff 无源码/测试/fixture/配置/数据库/历史 archive 或历史 evidence 改写。

## Step 1：可实现设计冻结

唯一目标：冻结无凭证安全终态、产品模式词汇、全版本恢复/DELETE、本地运行、局部 UX、可访问性、组合验收、文件归属和兼容矩阵。

状态：`DONE / PASS`。已冻结 `draft → normalizing → failed/configuration_missing` 的零调用 typed 结果、三产品模式与 legacy/V2 内部选择、canonical/旧 pointer 迁移、终态 DELETE、固定版本/固定 loopback 端口 PowerShell runner、局部 UX/accessibility、至少 12 个组合式 journey 和四层精确归属。只修改权威文档，未执行实现、测试、服务、数据库、外部访问或 Git 交付。

冻结实现入口：production bootstrap 必须在必要 adapter 不齐时提供安全 unavailable executor；POST 仍返回 202，GET 得到各版本同 shape `failed`，固定 `diagnostic_code=required_provider_configuration_missing`、`retryable=false` 且 Provider/Agent 调用为 0。单城市沿用“结束日期是否被显式编辑”选择 legacy/V2；V3/V4 分别对应两种多城市产品模式。恢复 key 固定为 `ita.last-local-job`，旧 V4 后旧 V3；DELETE 只在前端终态开放；runner 固定 Python 3.13.3/Node 22.16.0/pnpm 11.19.0 与 127.0.0.1:8000/5173。

完成门禁：产品、架构、API、Agent、设计、测试与 D-017 的冻结契约一致；文档检查器及测试、`git diff --check`、范围与秘密模式审计通过。Step 2 仍待用户单独批准，不得自动进入。

## Step 2：无凭证安全终态与运行兼容

唯一目标：先记录 RED，再以最小 GREEN 让无凭证或 Provider 组合不完整的 job 同 shape 进入 `failed / configuration_missing`，且 Provider 调用为 0。

状态：`DONE / PASS`。RED 先以缺失 `ConfigurationMissingPlanningJobExecutor` 的 3 个收集错误成立；最小 GREEN 新增纯 Repository executor、直接 export、bootstrap live/unavailable 选择和 production app wiring。四版本按 `draft → normalizing → failed` 写 typed `configuration_missing`，固定 message/diagnostic、不可重试且无 Provider/Agent/runtime 能力；完整配置仍使用既有 `ProviderPlanningJobExecutor`，显式测试 Repository 继续允许 optional executor。

验证覆盖 legacy/V2/V3/V4、POST/GET/retry/idempotent reuse、draft 不滞留、existing normalizing retry、其他历史 draft 不扫描、typed Repository、配置全空/单 Provider/完整组合和部分配置 fail closed。59 项 API/bootstrap 定向、169 项 state-machine/四版本 Repository 定向、全 backend Ruff format/lint 和 66 个 source strict mypy 通过。因本 Step 明确禁止创建数据库，5 个 SQLite 测试被显式 deselect；schema/migration diff 为 0，未宣称 SQLite 运行证据。原 Step 3 准入限制已由后续单独批准和完成事实取代。

## Step 3：MVP UX foundation

唯一目标：实现三种用户产品模式词汇，以及状态、结果摘要、预算、来源、冲突和恢复动作的有限共享层级。

状态：`DONE / PASS`。RED 以三个预期失败证明旧表单缺少三产品模式且两个终态恢复动作位于支持信息之后；最小 GREEN 合并模式入口、移除用户可见版本术语、复用既有 `endDateEdited`/strict serializer，抽取共享恢复动作并调整摘要→动作→计划→预算→来源→诊断层级。局部样式只新增四个状态 token、三列/窄屏单列入口和 44px 主要动作。

验证：定向 49 项、前端全量 109 项通过；Prettier、ESLint、TypeScript、Vite build 通过。9 个 Stack 2 生产/测试文件净新增 130 行，`styles.css` 净新增 23 行；没有改变 API/contract/终态推导，没有新增路由器、UI 框架或品牌重写。后续 Step 4 已由单独批准完成。

## Step 4：完整旅程恢复与 DELETE

唯一目标：实现 legacy/V2/V3/V4 统一 UUID pointer、旧 V3/V4 pointer 兼容、404/过期清理、当前终态/已恢复任务 DELETE 和焦点恢复。

状态：`DONE / PASS`。RED 定向集合为 `17 failed / 26 passed`，证明 canonical pointer、全版本恢复、旧 key 迁移、错误保留和 DELETE client/UI 尚不存在；最小 GREEN 统一保存 UUID，按 canonical→旧 V4→旧 V3 读取，校验 UUID 后才发 GET，并仅在旧 key 响应版本匹配后迁移。`job_not_found` 清 pointer，网络/5xx/strict parser 错误保留 pointer 和“稍后重试恢复”；storage 异常不阻断新建。

终态复用既有 DELETE URI 和 error envelope；inline 确认支持确认焦点、取消/Escape 返回触发按钮，成功清 pointer 并聚焦表单标题，失败保留结果/pointer 并显示安全 alert。新建与恢复 legacy/V2/V3/V4 均使用同一 GET/strict parser；processing/paused/submitting/retrying 不出现删除。定向 `43 passed`，前端全量 `126 passed`，Prettier、ESLint、TypeScript 与 Vite build 通过。15 个 Stack 3 生产/测试文件净新增约 630 行，未触发 20 文件/1600 行阈值；Step 5 仍待单独批准。

不得保存请求/结果/版本到 localStorage，不实现历史列表、清库或运行中取消；V3/V4 replan 继续写前拒绝。

## Step 5：安全本地运行入口

唯一目标：提供一个 PowerShell 入口，完成固定版本 preflight、端口冲突、loopback 启动、健康等待、SQLite 错误提示和 Ctrl+C 精确子进程清理。

状态：`DONE / PASS`。RED 时 `scripts/run-local.ps1` 尚不存在，定向 unittest 得到 `2 errors / 1 failure`；最小 GREEN 新增唯一入口及 4 项离线 contract/preflight 测试。runner 精确核对仓库声明和已安装 Python `3.13.3`、Node `22.16.0`、pnpm `11.19.0`，Corepack/uv 禁网且依赖缺失不安装；固定端口用本机 listener 只读检查，冲突仅报告端口。

运行时直接启动并持有 `.venv` Python 与 Vite Node Process，避免 wrapper 子进程；后端 strict health→前端 root 各等待最多 30 秒且禁 proxy/redirect。Ctrl+C、提前退出和失败统一 finally，只按两个 Process ID 停止并等待；早期后端/SQLite 失败和未知异常投影为固定安全诊断。自检只使用临时 loopback listener 和无害 PowerShell child，实际 preflight 未启动业务服务。未创建数据库、读取秘密、访问软件包仓库/Provider 或进入 Step 6。

不得修改系统配置、杀死非本脚本创建的进程、读取秘密值或访问业务 Provider；不得新增依赖。

## Step 6：本地纵向与独立验收

唯一目标：在临时 schema v2 SQLite 和完全 synthetic/loopback 环境完成组合 journey、desktop/390px、network/console/accessibility、干净检出启动及独立隐私安全审查。

状态：`DONE / PASS`。新增 14 个完全离线组合 journey 和 1 个矩阵闭合测试；临时 SQLite 纵向集合 `56 passed`，确认 schema v2、migration 仅 1/2，重启测试按权威终态比较且不把初始 draft 当作持久化终态。F-005 固定 48-case eval 对应测试保持通过。

干净检出在 E 盘临时目录以 frozen/offline 模式安装，backend 36 个包与 frontend 257 个包均来自缓存、下载 0；实际 runner 的 backend/frontend strict health、临时 schema v2 SQLite 和 Ctrl+C 精确清理通过，8000/5173 无遗留 listener/process。Playwright 直接使用已安装全局 CLI，V4 partial journey 在 desktop/390px 完成提交、reload 恢复、canonical UUID-only pointer、Escape 焦点返回和单次 DELETE；network 仅 loopback，console 0 error/warning，label/description/error 引用、live region、390px 44px 可见触控目标、颜色对比和横向 overflow 检查通过。

独立 Codex Security diff scan `dcb1c6b6-49e5-47da-87a0-706b43374a7e` 覆盖 21/21 变更项及 runner/动态边界，结论 0 finding。累计生产/测试/script 为 29 文件、净新增 1709 行，`styles.css` 净新增 74 行；Schema/migration、依赖/lockfile diff 均为 0。未读取秘密、调用真实 Provider、访问非 loopback 业务服务或执行 Git 交付。

代表性矩阵已覆盖三种产品模式、legacy/V2/V3/V4、五终态、processing/paused、reload/retry/delete、legacy/V2 两日 replan、V2 3–7 日 scope 拒绝和 V3/V4 replan 写前拒绝；没有制造全部版本×全部状态的笛卡尔积。缓存完整，因此干净检出未访问软件包仓库；业务 Provider 网络为 0。

## Step 7：本地门禁与四层 stacked PR

唯一目标：运行全量本地门禁，按四层拓扑完成精确 commit、push、stacked PR、逐层独立 review 和远程 CI。

状态：`DONE / PASS`。本地统一门禁已通过：Python 3.13.3、Node 22.16.0、pnpm 11.19.0；后端 `1388 passed`、前端 `131 passed`、文档测试 `29 passed`，其余 format/lint/typecheck/build/文档契约均通过。四层已形成独立父链；review findings 已通过普通追加提交关闭，最终逐层复审无未关闭 finding。Draft PR #38/#39/#40/#41 的 base/head 拓扑正确，对应 Windows offline CI runs `32503520656`/`32503533764`/`32503554642`/`32547492597` 均为 success。

本 Step 不 merge、不运行最终 main CI、不归档。每层必须独立可测试、只依赖前层，review finding 关闭后才能继续。

## Step 8：合并、最终 CI 与归档

唯一目标：依序合并四层 PR，必要时 clean-restack，运行最终 main CI，将 F-006 以 `DELIVERED / LOCAL_ACCEPTANCE_PASS / ARCHIVED` 关闭归档。

状态：`DONE / PASS`。PR #38/#39/#40/#41 已依序 squash merge；#39/#40/#41 通过普通 merge clean-restack 收敛为本层净差异，无 force-push。完整功能 main `d82ca5c6`，main CI run `32691778088` success；任务卡已归档并关闭活动任务。

归档必须继续披露项目真实 Provider 就绪为 `PARTIAL`，不得把离线/loopback/clean-checkout 证据等同于真实 UAT。

## 四层归属

1. `feat/f-006-local-runtime-compatibility`：`bootstrap.py`、安全 unavailable executor/直接 export、必要的 `app.py`/`api/trip_plans.py` 兼容 wiring，以及 bootstrap/application/API/Repository 四版本测试；不得带入前端。
2. `feat/f-006-mvp-ux-foundation`：`TripRequestForm.tsx`、`PlanningStage.tsx`、`TripPlanResult.tsx`、`MulticityTripPlanResult.tsx`、`ResultEvidence.tsx`、有限 `styles.css` 与直接组件/accessibility 测试；只做产品语言和表现层级，不接 pointer/API client。
3. `feat/f-006-mvp-journey-recovery`：`App.tsx`、`useTripPlanningJob.ts`、`tripRequest.ts`、`tripPlanningApi.ts`、`replanningApi.ts`、`ReplanPanel.tsx` 及恢复/删除/焦点/journey 测试；若为动作 props 或确认样式必须相邻修改 Stack 2 文件，只能是最小追加，不得重做视觉 foundation。
4. `feat/f-006-local-acceptance-delivery`：新增 `scripts/run-local.ps1`、必要的 `verify.ps1`/文档检查器直接契约、统一 synthetic/browser helper、clean-checkout/SQLite/browser 验收测试、README/运行说明和当前交付文档；不得把依赖安装或 Provider 调用写入日常 runner。

受控相邻扩展仅限直接 export/factory/wiring、同层 typed helper、对应测试/明显 synthetic fixture/browser 支撑和当前状态/evidence 文档。Schema、migration、依赖、lockfile、Provider、公开 API shape、数据留存或隐私变化必须停止并重新批准。

## 规模治理

- 单 Step 超过 5 个未预期生产/测试文件：停止；
- 任一 stack 超过 20 个生产/测试/script 文件或净新增 1600 行：停止并重新拆分；
- 任务累计超过 65 个生产/测试/script/fixture 文件或净新增 5200 行：停止并重新拆分；
- `styles.css` 净新增超过 600 行、替换约 30% 以上现有样式、或需要新 UI 框架/路由器/依赖：停止并重新批准。

## 跨 Step 不变量

- F-001 `PARTIAL`、Step 45M `FAIL`、Step 45T `PASS`；unknown 不按 0；混合交通 fallback 仅离线；
- F-004A/F-004B1/F-004C/F-005 无真实 Provider UAT；F-004B1/F-004C 城际 Provider 调用为 0；
- F-004B2 `BLOCKED / ARCHIVED`；F-005 离线 evidence 不等于真实 UAT；
- SQLite schema version 2，migration 只有 1/2；
- legacy/V2/V3/V4 exact compatibility；V3/V4 replan 全链路写前拒绝；
- V4 interests-only、票务隐私禁令及 `user_provided / unknown_validity / 用户提供，未核验`；
- 默认测试与 CI 阻断非 loopback 网络；真实 Provider UAT 不属于核心 F-006。
