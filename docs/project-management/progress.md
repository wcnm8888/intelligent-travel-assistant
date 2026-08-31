# 项目进度

## 当前状态

- 当前任务：`F-007 高德路径规划 QPS 节流与真实调用稳定性`（`ACTIVE`）
- 当前 Step：`Step 8 - 依序合并与关闭`（`TODO`）
- Step 0–5、Step 7：`DONE / PASS`；Step 6：`DONE / UAT_NOT_FORMALLY_PASSED / INCONCLUSIVE`
- 基线：`main == origin/main == 905a950fa2483f2e441eb520a20897dcc1daa722`；归档 main CI run `32692800113` success
- 当前分支：`feat/f-007-amap-qps-integration-delivery`；Draft PR #43/#44 OPEN，尚未 merge
- 真实验收：2026-08-30 新增 `FAIL / AMAP_QPS_EXCEEDED`；高德步行路径规划限制 3 QPS、最高 6 QPS、超限 3 次；本地安全终态为 `provider_rate_limited`、`route_primary_unavailable`、`data_missing`
- 服务：Step 5A 完成后 `127.0.0.1:8000`（PID 52516）与 `127.0.0.1:5173`（PID 77692）仍 HTTP 200，未停止或重启
- F-004C：Step 0–6 `DONE / DELIVERED / ARCHIVED`；PR #34/#35/#36 和归档 PR #37 已合并；最终 main CI run `32486428083` success
- F-004B2：`BLOCKED / ARCHIVED`；不得恢复其 Provider 查询或 Step 2
- F-006：`DELIVERED / LOCAL_ACCEPTANCE_PASS / ARCHIVED`；其本地验收结论不因 F-007 真实 Provider QPS FAIL 改写，项目真实 Provider 就绪继续为 `PARTIAL`
- 下一入口：等待用户单独批准 Step 8；不 merge、不归档、不进入 F-008

## F-007 Step 7

- 状态：`DONE / PASS`；Stack 1/2 提交 `c73cd7f`/`273231a` 已推送，Draft PR #43/#44 按两层依赖建立且保持 OPEN；
- 本地：后端 `1424 passed`，前端 `132 passed`，format/lint/typecheck/build/docs 通过；受保护端口 8000 使唯一 runner preflight 按设计失败，未停止进程，其余文档/runner 28 项通过；
- review/CI：独立只读复审最终 `FIXED`；#43/#44 Windows offline runs `33363974674`/`33364033165` success；
- 范围：Stack 1 10 文件/净增 851 行，Stack 2 14 文件/净增 1147 行，累计 24 文件/净增 1998 行；Schema/migration、依赖/lockfile、公开 API 与 Provider/秘密边界无变化；
- 下一入口：Step 8 `TODO / BLOCKED_BY_APPROVAL`；不得自动 merge、归档、关闭 F-007 或进入 F-008。

## F-007 Step 6

- 状态：`DONE / UAT_NOT_FORMALLY_PASSED / INCONCLUSIVE`；用户已明确批准不再执行新的真实 Provider UAT；
- 历史事实：保留 2026-08-30 `FAIL / AMAP_QPS_EXCEEDED`，不得由后续离线门禁或补充观察覆盖；
- 补充证据：2026-08-31 观察到 0.50–0.52 秒间隔且未出现 `provider_rate_limited`，但缺少同期高德控制台 QPS/超限记录，因此只能作为积极补充证据，不能记为 PASS；
- 边界：本次只完成文档收口，没有读取秘密、调用真实 Provider或停止/重启现有服务；
- 下一入口：Step 7 本地全量离线门禁、规模/边界审计、两层交付、独立 review 与逐层远程 CI。

## F-007 Step 5A

- 状态：`DONE / PASS`；Step 5 的 accessibility finding 已关闭，未进入 Step 6；
- TDD：直接 CSS 门禁先以 `4.203700573694173:1` RED 失败；最小 GREEN 只将 `--status-partial` 从 `#9b6716` 调整为 `#925d12`，并让 `unknown_validity` 复用该 token；全局 amber、背景、布局、API、状态与交互不变；
- 验证：前端 `13 files / 132 tests`；desktop 1440×1000 与 390×844 实际渲染对比度均为 `5.071:1`，无横向溢出，390px 小于 44px 的可见按钮、broken descriptions、unlabeled controls 均为 0，console 0 error/0 warning；
- 网络/服务：28 条请求全部为 `127.0.0.1:15177`，API 仅代理至隔离 18007；结束后只关闭隔离进程，用户 8000/PID 52516 与 5173/PID 77692 保持 HTTP 200；
- 范围：只修改 `frontend/src/styles.css`、直接前端测试和当前状态/evidence 文档；Schema/migration、依赖/lockfile、Provider、秘密与 Git 交付均为 0；
- 规模：Step 5A 为 2 个批准生产/测试文件、净新增 58 行；任务累计 14 个生产/测试文件、净新增 1210 行，低于 30 文件/2200 行任务阈值；
- 后续入口已由已收口的 Step 6 和当前 Step 7 取代；本段保留 Step 5A 时点事实。

## F-007 Step 5

- 状态：`DONE / PASS`；隔离 loopback 与临时 SQLite、浏览器、network/console/accessibility 和独立隐私安全审查均已执行，原 finding 已由上方 Step 5A 关闭；
- 纵向：V4 synthetic POST → partial → retry attempt 2 → reload 恢复 → DELETE；SQLite migration 只有 1/2，删除后 job=0；V2/V3/V4 组合临时 SQLite `40 passed`；
- 浏览器：1440×1000 与 390×844 无横向溢出；label/description、live region、44px button、skip link、DELETE 两步确认及 Escape 焦点恢复通过；console 0 error/0 warning；99 条请求仅 `127.0.0.1:15177`；
- 安全：Codex Security scan `d34206c0-41f4-481a-8282-b00115238d76` 完整覆盖 6 个变更生产文件、0 finding；未读取秘密或调用 Provider；
- 原 finding：`partial` 状态章及 `unknown_validity` 普通文本对比度约 4.2:1，低于 WCAG AA 4.5:1；Step 5 当时未授权改前端，故正确阻塞，后由 Step 5A 关闭；
- 过程偏差：首次 V2 手工输入与固定 synthetic 结果摘要不一致，Repository 以 `result_request_mismatch` fail closed；未联网、未作为通过证据，V2 canonical 纵向由自动化矩阵通过；
- 服务/范围：验收仅用自有 18007/15177 与临时 E 盘数据库，结束后关闭隔离进程；用户 8000/5173 PID 未变；Schema/migration、依赖/lockfile、生产/测试源码均未在 Step 5 修改；
- 下一入口：Step 5A 已关闭 finding；Step 6 仍须单独批准且默认关闭。

## F-007 Step 4

- 状态：`DONE / PASS`；只使用 fake monotonic clock、MockTransport 与 synthetic fixture 完成离线稳定性和兼容回归，没有修改生产实现；
- 跨 job：两个并发 planning job 分别使用 public transit/walking，route concurrency 仍为 2；8 次 Amap route starts 为连续 0.5 秒槽位，任意半开 1 秒窗口最多 2 次；
- retry：MockTransport 503 与合法 Retry-After 429 各只重试一次；runtime 矩阵确认 timeout/server/受控 429 可重试，auth/schema/empty/unknown/无合法 Retry-After 不重试，initial/retry 共用 limiter 且 backoff 先于 slot；
- stop/drain：deadline 等号、shortfall、oversleep、terminal/cancel/budget 后零新 HTTP/零未启动 budget，waiter 与 active peer cancel-drain、单 runtime 关闭后共享 limiter 继续可用均通过；
- 兼容：相关集合 `299 passed`；后端 `1446 passed / 1 deselected`，deselect 仅因必须保留 8000/5173 服务与 runner 空闲端口 preflight 互斥，runner 其余 `4 passed`；前端 `131 passed` 及全部静态/build 门禁通过；
- 范围：Step 4 修改 3 个批准测试文件、净新增 289 行；累计 12 个生产/测试文件、净新增 1152 行；生产 adapter/planning/API/Repository/SQLite/frontend、Schema/migration、依赖/lockfile 零修改；
- 边界：未停止/重启服务，未读取秘密、创建数据库、调用 Provider 或执行 Git 交付；真实 F-007 UAT 仍为 FAIL，不能由本 Step 离线 PASS 覆盖；
- 下一入口：等待用户明确批准 Step 5 本地纵向与独立审查。

## F-007 Step 3

- 状态：`DONE / PASS`；以 TDD 将 Step 2 limiter 作为完整配置 production bootstrap 的单进程唯一实例，由既有 factory 注入 legacy/V2/V3/V4 task runtimes；
- RED：完整配置的四个 runtime `_attempt_limiter is None`，共享 identity 断言失败；configuration-missing 零 limiter 构造已通过；
- GREEN：完整配置四 runtime 共享同一 `PacedAttemptLimiter`；fake clock route starts 为 0/0.5/1.0/1.5，Amap POI、QWeather forecast 和 DeepSeek generation 不推进 limiter 时间线；
- 缺配置：完整性 Gate 在 limiter 构造前返回 `ConfigurationMissingPlanningJobExecutor`，保持零 limiter、零 Provider/Agent/governor/attempt 调用；
- 兼容：route concurrency=2、logical/HTTP attempt budget、最大 180 秒 deadline、terminal/cancel/peer drain 和公开 API/错误 shape 均由既有/Step 2 回归保持；
- 验证：bootstrap exact `2 passed`；bootstrap+四版本+Step 2 `181 passed`；后端全量 `1408 passed`；Ruff format/check 与 strict mypy `150 source files` 通过；
- 文档/服务：文档检查 17 required/29 Markdown、检查器 24 tests 和 whitespace checks 通过；后端/前端 HTTP 200，listener PID 保持 52516/77692；
- 范围：Step 3 为 2 个批准生产/测试文件、净新增 165 行；任务累计 10 个生产/测试文件、净新增 863 行，未预期文件 0；
- 边界：planning service、Provider adapters、API、Repository、SQLite、frontend、Schema/migration、依赖/lockfile 零修改；未读取秘密、创建数据库、调用 Provider、停止/重启服务或执行 Git 交付；
- 下一入口：等待用户明确批准 Step 4 离线稳定性与兼容回归。

## F-007 Step 2

- 状态：`DONE / PASS`；先 RED 后最小 GREEN，实现 exact Amap route pacing policy、process-shareable paced-slot limiter 和 task runtime 可选注入；
- RED：3 个定向模块按预期在 collection 阶段因缺少 `AttemptPacingPolicy`/`PacedAttemptLimiter` 失败，无环境或既有行为漂移；
- GREEN：仅 `AMAP + CALCULATE_ROUTES` 使用 0.5 秒 monotonic timeline；无 burst/idle token、半开窗口、并发 waiter、nonmatching、initial/retry、backoff→slot、deadline equality/shortfall/oversleep、pre/postflight、未启动 budget 和 cancel/drain 均由 fake clock 锁定；
- 验证：定向 `102 passed`，相邻 application/provider `257 passed`，后端全量 `1406 passed`；Ruff format/check 通过，strict mypy `150 source files` 通过；
- 文档/服务：文档检查 17 required/29 Markdown、检查器 24 tests 和 whitespace checks 通过；后端/前端均 HTTP 200，listener PID 保持 52516/77692；
- 范围：8 个批准生产/测试文件、净新增 698 行，未预期文件 0；Stack 1 当前低于 12 文件/1000 行阈值；
- 边界：bootstrap、planning service、Amap adapter、API、Repository、SQLite、前端、Schema/migration、依赖/lockfile 均零修改；未读取秘密、创建数据库、调用 Provider 或执行 Git 交付；
- 下一入口：等待用户明确批准 Step 3 的 bootstrap 单实例接线。

## F-007 Step 1

- 状态：`DONE / PASS`；只读核对现有 `ProviderAttemptRuntime`、bootstrap、legacy/V2/V3/V4 路径调用和测试入口后完成设计冻结，未修改生产源码、测试或 fixture；
- 接线：walking/public transit 均以 `AMAP + CALCULATE_ROUTES` 进入同一 task runtime；process limiter 由完整配置的 production bootstrap 单实例持有并通过 factory 注入各 job runtime，不进入 Amap adapter；
- policy：仅 exact Amap route 命中，0.5 秒 monotonic paced slot、无 token 累积、半开 1 秒窗口最多 2 starts；task runtime 与 limiter 使用同一 clock domain；
- 顺序：retry/backoff → preflight → slot → postflight/deadline/terminal/cancel/budget 复核与 retry reservation → HTTP；deadline 等号允许，slot wait/oversleep 计入 deadline；
- 取消：waiter 与 active peer 继续由 task runtime cancel/drain；关闭一个 runtime 不关闭 process limiter；post-slot 失败零 HTTP、零 retry budget 消耗，已授予 slot 不回收；
- 测试：fake clock/MockTransport 矩阵覆盖 scope、无 burst、并发、跨 job、initial/retry、deadline、budget、cancel/drain、bootstrap singleton、route concurrency=2 与全版本/F-005/持久化/API/UI 兼容；
- 文件：Stack 1 固定为 domain policy + 新 limiter + task runtime/exports/直接测试；Stack 2 固定为 bootstrap singleton + executor/multiday/multicity/adapter MockTransport 回归与验收交付；Amap adapter 生产文件不在批准清单；
- 验证：文档检查 17 required/29 Markdown、检查器 24 tests、`git diff --check` 均通过；范围仍为 7 份文档，后端/前端 health 均 200，listener PID 仍为 52516/77692；
- 边界：没有停止/重启 8000/5173，没有数据库、秘密、Provider 调用、Git 交付、Schema/migration、依赖/lockfile 或公开 shape 变化；
- 下一入口：等待用户明确批准 Step 2 的 TDD 实现。

## F-007 Step 0

- 状态：`DONE / PASS`；Step 0 开始前 HEAD/main/origin/main 一致、工作区干净、无开放 PR、无活动任务，最新归档 main CI `32692800113` success；
- 治理：F-007 已成为唯一 ACTIVE，current-task、roadmap、implementation-plan、D-018、两层 stack、核心文件和规模阈值已建立；
- 证据：新增 2026-08-30 `FAIL / AMAP_QPS_EXCEEDED` 当前证据，不覆盖 Step 45M `FAIL`、Step 45T `PASS` 或 F-006 `LOCAL_ACCEPTANCE_PASS`；
- Git：从干净 main 创建 `feat/f-007-amap-qps-policy-runtime`，没有 commit、push、PR 或远程 CI；
- 范围：只修改当前治理/权威文档；没有源码、测试、fixture、Schema/migration、依赖/lockfile、数据库或秘密变更，也没有 Provider 调用；
- 服务：用户当前 8000/5173 服务保持运行，未停止或重启；
- 下一入口：等待用户明确批准 Step 1 的 documentation-only 设计冻结。

## F-006 Step 8

- 状态：`DONE / PASS / ARCHIVED`；PR #38/#39/#40/#41 依序 squash merge，main commits 为 `22be214a`、`97dc949f`、`d70eb145`、`d82ca5c6`；
- clean-restack：#39/#40/#41 分别以普通 merge commit 吸收最新 main，GitHub diff 收敛为 9/11/17 个本层文件；无 rebase、无 force-push；
- CI：clean-restack PR runs `32690231596`/`32690839987`/`32691459865` success；逐层 main runs `32689910671`/`32690516152`/`32691143922`/`32691778088` success；
- 归档：[F-006 archive](../archive/task-cards/F-006-mvp-local-acceptance.md)；当前无活动任务；
- 真实性：结论仅为本地 MVP 验收通过，不新增真实 Provider UAT，不提升 F-001 或项目真实 Provider 就绪的 `PARTIAL` 状态。

## F-006 Step 7

- 状态：`DONE / PASS`；固定运行时下统一门禁通过，后端 `1388 passed`、前端 `131 passed`、文档测试 `29 passed`，Ruff、strict mypy、Prettier、ESLint、TypeScript、Vite build 和文档契约全部通过；
- 提交链：父链为 Stack 1 `b3e29aa` → Stack 2 `972b1d4` → Stack 3 `f5903f4` → Stack 4 `7a9b488` + 文档/runner 修正 `e6d3547`/`7f8cabb`/`2b95930`；没有 force-push，四分支均已普通 push；
- review/CI：四层最终独立 review 无未关闭 finding；Draft PR #38/#39/#40/#41 保持 open，对应 Windows offline CI runs `32503520656`/`32503533764`/`32503554642`/`32547492597` 均为 success；
- 范围：Stack 1 为 11 个生产/测试文件、净新增 472 行；Stack 2 为 9 个、净新增 134 行；Stack 3 为 11 个、净新增 843 行；Stack 4 为 3 个生产/测试/script 文件、净新增 969 行，另含批准的当前文档。任务累计去重后为 31 个生产/测试/script 文件、净新增 2418 行，`styles.css` 净新增 74 行，均低于阈值；Schema/migration、依赖/lockfile diff 为 0；
- 后续入口已由完成的 Step 8 取代；本段保留 Step 7 交付时点事实。

## F-006 Step 6

- 状态：`DONE / PASS`；新增 14 个完全离线组合 journey 与 1 个矩阵闭合测试，覆盖四版本无配置、五终态、V2/V3/V4 schema v2、unknown/null 与来源语义；
- SQLite：纵向集合 `56 passed`，确认 schema version 2、migration 只有 1/2；修正两个旧重启测试，使其比较异步 executor 已产生的权威 terminal result，而非初始 POST draft；
- clean checkout：E 盘临时检出以 frozen/offline 模式复用缓存，backend 36 包、frontend 257 包下载 0；实际 runner health、临时 SQLite migrations 和 Ctrl+C 精确清理通过，8000/5173 无遗留 listener/process；
- browser：全局 Playwright CLI 直连 loopback；desktop/390px V4 partial 覆盖 uppercase service number、unknown fare、user-provided/unknown-validity、reload、canonical UUID-only pointer、Escape 焦点返回和单任务 DELETE。所有业务请求为 loopback，console 0 error/warning，零横向溢出，基础 label/description/error/live region/44px/contrast 检查通过；
- eval/security：F-005 固定 48-case eval 对应测试 `26 passed`；Codex Security scan `dcb1c6b6-49e5-47da-87a0-706b43374a7e` 覆盖 21/21 并为 0 finding；synthetic/loopback 证据不等同真实 Provider UAT；
- 范围：Step 6 新增 1 个组合验收测试并修正 2 个直接 SQLite 重启测试；累计 29 个生产/测试/script 文件、净新增 1709 行，`styles.css` 净新增 74 行；Schema/migration、依赖/lockfile diff 为 0；
- 后续入口已由用户批准的 Step 7 取代。

## F-006 Step 5

- 状态：`DONE / PASS`；RED 因 runner 不存在得到 `2 errors / 1 failure`，最小 GREEN 后 runner contract/self-test/actual offline preflight `4 passed`；
- preflight：固定核对仓库声明和已安装 Python `3.13.3`、Node `22.16.0`、pnpm `11.19.0`；Corepack 与 uv 禁网，缺少已安装 backend/frontend 入口时安全退出，不自动安装；固定 8000/5173 端口只读检查，冲突不停止占用者；
- 运行/健康：直接持有 Python 与 Node Process，固定 loopback/strictPort，按 `/api/health` exact payload→frontend root 各等待最多 30 秒；健康请求禁 proxy/redirect；后端提前退出以固定 SQLite/权限诊断收口；
- 清理/隐私：Ctrl+C、提前退出和所有失败走 finally，只按保存的 Process ID 停止并等待自身两个进程；未知异常固定脱敏，不输出配置值；不自动打开浏览器；
- 验证：定向 `4 passed`，其中 contract self-test 只建立临时 loopback listener 和无害 PowerShell child，actual offline preflight 只读版本/端口且未启动业务服务；
- 范围：新增 1 个 runner、1 个直接 unittest 并同步运行/当前文档；未修改 Schema/migration/依赖/lockfile，未创建数据库、读取秘密、访问软件包仓库/Provider、执行 browser/Step 6 或 Git 交付；
- 下一批准动作：Step 6，仅执行临时 schema v2 SQLite、组合 synthetic journey、loopback desktop/390px、network/console/accessibility、干净检出和独立隐私安全验收。

## F-006 Step 4

- 状态：`DONE / PASS`；RED 定向集合为 `17 failed / 26 passed`，随后最小 GREEN 定向 `43 passed`；
- 恢复：canonical key 固定 `ita.last-local-job` 且只保存 UUID；读取顺序为 canonical→旧 V4→旧 V3，旧 pointer 仅在响应版本匹配后迁移；非法 UUID 请求前清除，`job_not_found` 清除且不显示缓存结果，网络/5xx/strict parser 错误保留 pointer 和恢复动作；
- 兼容：legacy/V2/V3/V4 共用既有 GET URI 和 strict response parser；storage 读写异常不阻断新提交；“返回修改”只清 pointer，不调用 DELETE；legacy/V2/V3/V4 请求、结果及 replan 回归保持；
- 删除/焦点：仅权威 terminal 状态显示单任务 DELETE；inline 两步确认支持确认焦点、取消/Escape 返回触发按钮；成功清 pointer、回到新建并聚焦表单标题，失败保留任务/pointer 并显示安全 alert；
- 验证：恢复/DELETE/API 定向 `43 passed`，前端全量 `12 files / 126 passed`；Prettier、ESLint、TypeScript、Vite production build 通过；
- 范围：15 个 Stack 3 生产/测试文件，净新增约 630 行，未预期文件 0；未修改后端、公开 API shape、Schema/migration、依赖/lockfile，未进入 runner、数据库/browser 或 Git 交付；
- 后续入口已由已完成的 Step 5 取代；本 Step 恢复与 DELETE 结论保持不变。

## F-006 Step 3

- 状态：`DONE / PASS`；RED 定向集合为 `3 failed / 19 passed`，精确证明三产品模式入口及主要恢复动作层级尚未实现；
- 产品语言：表单第一组只显示“单城市”“多城市·自行填写交通段”“多城市·填写已购铁路车次”，移除第二层城际类型和用户可见 V2/V3/V4；单城市仍由 `endDateEdited` 决定 legacy/V2，两种多城市继续进入既有 strict V3/V4 serializer；
- 层级：计划与无计划终态都先给摘要和主要恢复动作，再呈现逐日计划、预算、来源和详细诊断；共享组件不重算终态/freshness/预算，unknown 继续显示“未知”，冲突仍先由确定性 verdict 披露；
- 可访问性/样式：模式使用一个 `fieldset/legend`、原生 radio 和说明关联；选择后焦点留在 radio。只新增少量状态 token、48px 模式卡、44px 主要动作和 390px 单列规则，保留既有旅笺视觉/reduced-motion；
- 验证：定向 `49 passed`，前端全量 `109 passed`；Prettier、ESLint、TypeScript、Vite build 通过；
- 范围：9 个 Stack 2 生产/测试文件、净新增 130 行，`styles.css` 净新增 23 行，未预期文件 0；未修改 API/contracts/Repository/Schema/migration/依赖/lockfile，未进入 pointer/DELETE、runner、数据库或 browser；
- 后续入口已由已完成的 Step 4 取代；本 Step 产品模式与 UX foundation 结论保持不变。

## F-006 Step 2

- 状态：`DONE / PASS`；RED 为 3 个测试模块因安全 executor 尚不存在而收集失败；GREEN 后四版本 application/API/bootstrap 定向 33 项通过；
- 实现：新增只依赖 PlanningJobRepository 的 `ConfigurationMissingPlanningJobExecutor`；production bootstrap 在任一必要 adapter 缺失时使用它，完整组合仍使用既有 Provider executor；显式 Repository 注入保持原 optional executor 测试语义；
- 终态：legacy/V2/V3/V4 均走 `draft → normalizing → failed`，固定 `configuration_missing` message/diagnostic、`retryable=false`、空 plan/来源/违规/不确定项；不会进入 Provider、Agent、governor、attempt runtime、proposal 或 repair；
- 兼容：POST 首次仍为 202/draft snapshot，GET 为同 shape failed；重复 POST 不再调度，retry 返回既有 `retry_not_allowed`；existing normalizing retry 可收口，其他历史 draft 不扫描/回填；
- 验证：API/bootstrap 非 SQLite 集合 `59 passed / 5 deselected`，state-machine/四版本 Repository `169 passed`，全 backend `147 files` Ruff format、Ruff lint、66 source mypy 通过；schema/migration/依赖/lockfile diff 为 0；
- 范围：7 个生产/测试文件、净新增约 430 行、未预期文件 0，低于阈值；未创建数据库、读取秘密、启动服务、访问软件包仓库/Provider 或执行 Git 交付；
- 后续入口已由已完成的 Step 3 取代；本 Step 零调用安全终态结论保持不变。

## F-006 Step 1

- 状态：`DONE / PASS`；只完成权威设计与治理文档冻结，没有修改生产源码、测试、fixture、`.env.example`、Schema、migration、依赖或 lockfile；
- 无配置：冻结 production 安全 unavailable executor、`draft → normalizing → failed/configuration_missing`、固定安全 diagnostic、四版本 typed result 和 Provider/Agent/runtime 调用 0；现有部分/非法配置继续启动 fail closed；
- 产品与恢复：冻结三种用户模式、`endDateEdited` legacy/V2 规则、canonical `ita.last-local-job`、旧 V4→旧 V3 迁移优先级、失效/暂时错误处理和 localStorage 失败隔离；
- DELETE 与 runner：冻结仅终态 inline 删除确认、返回修改不删除，以及 Python 3.13.3/Node 22.16.0/pnpm 11.19.0、固定 127.0.0.1:8000/5173、health 等待和精确子进程清理；
- UX/验收：冻结局部信息层级、键盘/焦点/live region/44px/对比/390px，以及至少 12 个完全离线组合 journey、临时 schema v2 SQLite、loopback browser、F-005 48-case 保持和四层文件归属；
- 后续入口已由 Step 2 取代；Step 1 设计冻结结论保持不变。

## F-006 Step 0

- 已只读复核本地 Git 与 GitHub 事实：HEAD/main/origin/main 一致，PR #34–#37 均为 merged，开放 PR 为 0，CI run `32486428083` 在归档 main 上为 success；
- 已确认 F-004C 归档任务卡存在、当前开始前无活动任务，并保持 F-004B2 `BLOCKED / ARCHIVED`；
- 已将 F-006 激活为唯一 ACTIVE，建立 D-017、Step 0–8、四层 stacked PR、核心文件、受控相邻扩展和规模阈值；
- 已记录无凭证 draft、全版本恢复、DELETE UI、本地启动和组合验收缺口，但没有在 Step 0 修改代码或测试；
- 已从确认干净的 main 创建首层本地分支 `feat/f-006-local-runtime-compatibility`；没有新增提交或远程写入；
- Step 0 状态：`DONE / PASS`；文档检查器、24 项检查器测试、`git diff --check`、范围审计和秘密模式审计通过；
- 后续入口已由 Step 1 取代；Step 0 结论保持不变。

## F-004C Step 0

- 已复核 F-004B2 documentation-only closure：PR #33 已合并，最终 main CI run `32463645980` 为 `success`，归档任务卡存在；
- 已复核 Step 0 开始前 `main == origin/main == 577bdcbadf2e024022e59e52527d13edb0cbd659`、工作区干净、没有活动任务或开放 PR；
- 已从该干净 main 基线创建首层本地分支 `feat/f-004c-booked-rail-domain-contracts`；HEAD 未增加提交；
- 已激活 D-016：独立 V4 只承载用户已购铁路段，F-004B2 继续 `BLOCKED / ARCHIVED`，未来真实城际 Provider 必须使用新版本和新决策；
- 已建立 Step 0–6、三层 stacked PR、核心文件、受控相邻扩展和规模阈值；
- 本 Step 只修改当前治理与权威文档，不修改源码、测试、fixture、Schema、migration、依赖、lockfile、数据库、历史 evidence 或归档任务卡；
- 本 Step 不读取秘密，不调用 Provider，不 commit、push、创建 PR 或触发远程 CI，也不进入 Step 1。
- Step 0 状态：`DONE`；文档门禁、`git diff --check` 和范围审计通过。

## 当前边界与下一入口

F-004C V4 只支持中国大陆 2–3 城相邻、单向、同日、直达 rail 的用户提供段。`service_number` 必填并规范化，来源固定为 `user_provided / unknown_validity / 用户提供，未核验`；城际 Provider logical call 和 HTTP attempt 均为 0。legacy/V2/V3、SQLite schema v2 与 migration 1/2 保持不变。

Step 0–6 已完成。Step 5A 已将 V4 preferences 收窄为 interests-only strict allowlist，补齐 API 422、零 job/SQLite 写入、generation/repair context 和前端 synthetic sentinel，并经 Codex Security 与独立只读复审确认无 finding。三层交付、最终 main CI 与归档均已完成；当前没有活动任务。

## F-004C Step 1

- 状态：`DONE`；已冻结独立 V4 request/plan/response exact shape、service number 规范化、同日 `+08:00`/60–30 缓冲、positive/null fare 和 user/unknown 来源；
- 已冻结 canonical fingerprint、V4 typed union、SQLite schema v2 JSON 往返、同 URI API、V3/V4 replan 写前拒绝及旧版本 exact compatibility；
- 已冻结 Agent allowlist：service number、完整 segment 和原始城际文本不进入 proposal/repair；城际 logical call/HTTP attempt 均为 0；
- 已冻结显式 V3/V4 前端选择、V4 车次/隐私/来源展示、strict parser/recovery，以及 domain→SQLite/API→UI/browser 的分层测试矩阵；
- 三层核心文件和规模阈值不变；本 Step 只修改权威文档，没有修改源码、测试、fixture、Schema、migration、依赖或 lockfile，没有读取秘密、调用 Provider 或执行 Git 交付；
- Step 2 已完成；当前不得自动进入 Step 3。

## F-004C Step 2

- 状态：`DONE`；RED 首次因 V4 domain/contracts 直接 export 不存在而 collection 失败，随后以最小 GREEN 实现；
- 领域：新增 strict service number 规范化、固定 rail、同日 `+08:00`、派生 duration/transfer date、positive/null fare 和 60/30 分钟缓冲；
- contracts：新增独立 V4 request/plan/response concrete strict models，额外/票务越权字段、跨 tag、非 rail、错误时间与费用 fail closed；duration 只作 Python 派生属性，不进入 JSON；
- 来源：继续只允许 `user / user_provided_intercity_segment / unknown_validity / 用户提供 / 未核验班次、票价、余票或库存`，unknown fare 保持 null 并阻止 ready；
- 兼容：全量后端 `1344 passed`；legacy/V2/V3 union、shape 与既有行为未接线改动。V4 的全局 union、fingerprint、Repository/API/application 接线明确留给 Step 3；
- 静态门禁：Ruff format/check 与 mypy 全部通过；本 Step 6 个预期生产/测试文件、净新增约 1145 行，未触发阈值；
- 未执行：无数据库、Schema/migration、依赖/lockfile、外部调用、秘密读取、Git 交付或 Step 3 修改。

## F-004C Step 3

- 状态：`DONE`；三个新纵向测试模块首次因 `PlanningJobResultV4` 不存在而 collection RED，随后最小 GREEN；
- application：复用 V3 城市事实与离线规划路径，但在 Agent 边界前移除 service number，并在结果侧从原始 typed V4 request 确定性重建 `PlanBookedRailSegmentV4`；没有新增城际 Provider 能力或调用；
- Repository/SQLite：新增 V4 request/result/plan typed union、跨版本匹配、canonical fingerprint、memory/SQLite schema v2 hydration、restart/retry/delete；migration 仍精确为 1/2；
- API/replan：沿用 POST/GET/retry/DELETE URI 和顶层 envelope，OpenAPI 增为第四个严格 request 分支；V3/V4 replan 在 reserve/lookup/decision/executor 和持久化写入前拒绝；
- 验证：Step 3 定向 `9 passed`，相邻 V4/V3 application/Repository/API/contracts `73 passed`，全后端 `1353 passed`，Ruff/mypy 通过；
- 规模：Step 3 为 15 个预期生产/测试文件、净新增约 740 行；Stack 2 未超过 18 文件/1400 净行，任务累计未超过 50 文件/4000 净行；
- 未执行：无前端、浏览器、真实 Provider、Schema/migration、依赖/lockfile、秘密读取、Git 交付或 Step 4 修改。

## F-004C Step 4

- 状态：`DONE`；首批 6 项独立 V4 前端测试首次为 `1 passed / 5 failed`，随后补入同 URI retry 与三城市双段覆盖，最终 8 项全部通过；
- 表单：V3“自行填写交通段”仍为默认，显式选择“填写已购铁路车次”才生成 V4；切换清空段卡，V4 固定 rail，车次 trim/uppercase/格式校验并参与首错焦点；
- parser/result：V4 request/response/plan tags、segment exact keys 与 canonical service number fail closed；结果显示铁路车次、确定性格式化历时、用户提供/未核验、unknown-validity 和 null 金额，不推导服务端终态或声称可售/已出票；
- 恢复：沿用同 POST/GET/retry/DELETE URI；V4 使用独立本机 job UUID pointer，reload 只读 authoritative job，retry 只接受 attempt 2/3 的清空快照；V3 pointer 和旧版本行为保持；
- 验证：V4 定向 `8 passed`，全量前端 `107 passed`，Prettier、ESLint、TypeScript 和 Vite build 通过；
- 规模：Step 4 为 13 个预期生产/测试/fixture 文件、净新增约 802 行；Stack 3 未超过 18 文件/1400 净行，任务累计约 34 文件/2687 净行，未触发停止阈值；
- 未执行：无临时 SQLite、browser QA、真实 Provider、Schema/migration、依赖/lockfile、秘密读取、Git 交付或 Step 5 操作。

## F-004C Step 5

- 状态：`DONE / PASS`；SQLite、desktop/390px、仅 loopback 网络、console 和基础 accessibility 证据已完成；
- 原 finding：首次独立审查发现 V4 复用通用 preferences，可使 `free_text` / `hard_constraints` 进入 SQLite 和 generation context；Step 5 当时正确阻塞，历史证据保留；
- Step 5A 修正：V4 改用只含 `interests` 的 strict preferences；非法字段返回 422 且不创建 job，内部 projection 只复制 interests，前端 V4 清空并隐藏自由文本、serializer 只提交 interests；
- 回归：contracts/application/API/SQLite/Agent/frontend synthetic sentinel 全部通过；legacy/V2/V3 继续使用既有 preferences shape；后端全量 `1360 passed`、前端全量 `107 passed`，Ruff、mypy、Prettier、ESLint、TypeScript 与 Vite build 通过；
- 审查：Codex Security working-tree scan 为 0 findings，独立只读复审为 `NO FINDINGS`；原 privacy finding 已关闭；
- 规模：Step 5A 为 5 个批准生产文件和 4 个对应测试文件；按 Git numstat 复算，任务累计 35 个生产/测试/fixture 文件、净新增 3182 行，未触发 50 文件/4000 行停止阈值；Schema/migration、依赖/lockfile diff 为 0；
- Step 6 已完成；完整任务卡已归档，当前入口为等待用户起草并批准 F-006，不能自动开始。

## F-004C Step 6

- 状态：`DONE / PASS`；本地全量门禁为后端 `1360 passed`、前端 `107 passed`，Ruff、strict mypy、Prettier、ESLint、TypeScript、Vite build、文档测试与仓库契约全部通过；
- Review：逐层独立 review 均为 `NO FINDINGS`；Stack 1 过早暴露全局 V4 union 的 finding 在 push 前修正并由复审关闭；Step 5A 隐私 finding 保持关闭；
- 交付：PR #34/#35/#36 依序 squash merge；最终 PR CI runs `32482782649`、`32483888878`、`32484329856` 均为 `success`；
- Restack：#34/#35 squash 后以普通 merge restack 更新后续分支并重跑 CI，没有 force-push；最终各 PR diff 只含本层；
- main：完整功能 main 为 `14c4deaf5acfc4b8e3ccfb18db172dfe910eb26e`，最终 main CI run `32484789531` 为 `success`；
- 规模：任务累计 35 个生产/测试/fixture 文件、净新增 3182 行；Stack 1/2/3 为 6/15/15 文件、净新增 1174/814/1194 行，全部低于阈值；
- 范围：Schema、migration、依赖、lockfile、CI workflow 差异为 0；没有读取秘密或调用真实 Provider；城际 logical call/HTTP attempt 保持 0；
- 归档：[F-004C archive](../archive/task-cards/F-004C-booked-rail-user-provided.md)。当前无活动任务，F-006 仍只是候选。

## 保留历史事实

- F-001 产品状态为 `PARTIAL`；
- Step 45M 真实 UAT 为 `FAIL`，Step 45T 真实 UAT 为 `PASS`；
- unknown 金额不按 0；混合交通 fallback 只有离线证据；
- F-004A、F-004B1、F-005 均无真实 Provider UAT；
- F-004B1 城际 Provider 调用为 0；
- SQLite schema 保持 version 2，migration 只有 1/2。

## 权威入口

- [当前任务](./current-task.md)
- [实施计划](./implementation-plan.md)
- [路线图](./roadmap.md)
- [证据](./evidence.md)
- [D-016](../decisions.md#d-016f-004c-用户已购铁路段与车次信息)
- [D-015](../decisions.md#d-015f-004b2-真实城际-provider-与可信城际事实条件式边界)
- [F-004B2 BLOCKED archive](../archive/task-cards/F-004B2-real-intercity-provider-blocked.md)
- [F-005 archive](../archive/task-cards/F-005-external-service-resilience-freshness-agent-eval.md)
