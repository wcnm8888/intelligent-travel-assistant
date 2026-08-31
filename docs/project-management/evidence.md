# 验收证据索引

## F-007 Step 7：本地全量门禁、独立 review 与两层交付

- 日期：2026-08-31；结论：`DONE / PASS / OFFLINE DELIVERY`。不改写 Step 6 `UAT_NOT_FORMALLY_PASSED / INCONCLUSIVE` 或 2026-08-30 `FAIL / AMAP_QPS_EXCEEDED`；
- Git/PR：Stack 1 提交 `c73cd7f2de51d95c34e10b8f115032df851d2727`，Draft PR #43 base `main`；Stack 2 提交 `273231ad45a424e6b73894669e9041e915b3383f`，Draft PR #44 base `feat/f-007-amap-qps-policy-runtime`；两者均 OPEN，未 merge；
- 本地门禁：Python 3.13.3、Node 22.16.0、pnpm 11.19.0；后端 `1424 passed`，前端 `13 files / 132 tests`，Ruff format/check、strict mypy、Prettier、ESLint、TypeScript、Vite build、文档检查与 `git diff --check` 通过；
- runner 环境事实：统一入口只有 `test_runner_preflight_uses_installed_offline_runtimes_without_starting_services` 因受保护的本机 8000 端口占用而按设计 fail closed，明确没有停止既有进程；其余文档/runner `28 tests / OK`；
- 独立复审：初次发现 limiter admission wait 会侵占 6 秒 attempt timeout；后续继续发现 retry wait 误计已完成 attempt、stale permit 状态与超过 6 秒 attempt 规范化缺口。修复建立 governor-owned start/finish 生命周期、每 attempt 独立计时、取消原样传播和 TIMEOUT 规范化，最终只读复审结论 `FIXED`；
- 远程 CI：PR #43 run `33363974674` / job `99400728962` success（5m28s）；PR #44 run `33364033165` / job `99400899510` success（5m37s）；均为 Windows offline verification；
- 规模：Stack 1 为 10 文件、`+890/-39`、净新增 851 行；Stack 2 为 14 文件、`+1282/-135`、净新增 1147 行；任务累计 24 文件、净新增 1998 行，低于 12/1000、18/1400、30/2200 阈值；受控相邻扩展为 governance/planning timeout lifecycle 与直接回归，未预期生产/测试文件未超过 4；
- 边界：SQLite schema version 2、migration 1/2、依赖、lockfile、公开 API shape、Provider/account/key/QPS/配额/计费和数据留存边界均未变化；未读取秘密、调用真实 Provider、创建数据库、停止/重启现有服务或访问非 loopback 业务网络；
- 下一入口：Step 8 `TODO / BLOCKED_BY_APPROVAL`。必须等待用户单独批准后才可依序 merge、必要 clean-restack、最终 main CI、归档和关闭；不得进入 F-008。

## F-007 Step 6：真实 UAT Gate 如实收口

- 日期：2026-08-31；结论：`UAT_NOT_FORMALLY_PASSED / INCONCLUSIVE`，不得表述为 QPS PASS；
- 保留事实：2026-08-30 `FAIL / AMAP_QPS_EXCEEDED` 继续有效，不被后续离线证据或补充观察覆盖；
- 积极补充证据：2026-08-31 观察到 0.50–0.52 秒间隔，且未出现 `provider_rate_limited`；这些观察支持进程内 pacing 行为较先前改善，但不等同 Provider 侧 QPS 证明；
- 缺失证据：没有同期高德控制台 QPS/超限记录，因此无法正式证明 Provider 侧峰值符合边界；
- 执行边界：用户已批准 F-007 不再执行新的真实 Provider UAT；本次只做文档收口，没有读取秘密、调用真实 Provider或停止/重启现有服务；
- 后续入口：执行已批准的 Step 7 离线门禁与两层交付；Step 7 不得改写本结论。

## F-007 Step 5A：状态文字对比度修正与 Step 5 收口

- 日期：2026-08-30；结论：`PASS / OFFLINE LOOPBACK ONLY`。Step 5 的 accessibility finding 已关闭；未执行 Step 6 或真实 Provider UAT，不覆盖 `FAIL / AMAP_QPS_EXCEEDED`；
- TDD：新增直接 CSS 对比度门禁，RED 精确记录 `4.203700573694173:1` 低于 4.5；最小 GREEN 只将 `--status-partial` 从 `#9b6716` 调整为 `#925d12`，并让 `.freshness--unknown_validity` 复用该专用 token；全局 `--amber`、背景、布局、公开 API、状态和交互不变；
- 自动化：直接门禁通过，前端全量 `13 files / 132 tests` 通过；对 `--paper` 与 `--paper-raised` 的静态 WCAG AA 门禁均不低于 4.5；
- 工具链说明：当前 shell 的裸 pnpm 使用 Node `24.19.0`，相对项目声明的 `22.16.0` 产生 engine warning；测试、Prettier、ESLint、TypeScript 与 Vite build 均通过，但本 Step 不把该结果冒充冻结 Node 门禁，固定运行时的统一全量门禁仍属于 Step 7；
- 浏览器：隔离 18007/15177 上的 V4 canonical synthetic partial 结果，在 1440×1000 和 390×844 的 `.result-stamp--partial` 与 `.freshness--unknown_validity` 实际复合背景上均实测 `5.071:1`；两种视口均无横向溢出，390px 可见按钮小于 44px、broken descriptions、unlabeled controls 均为 0，live region=3；
- network/console：28 条浏览器请求全部指向 `127.0.0.1:15177`，API 仅由 Vite 代理至隔离 18007；console 0 error/0 warning；没有非 loopback 业务访问或 Provider 调用；
- 服务/范围：验收后只关闭本次隔离进程；用户 8000/PID 52516 与 5173/PID 77692 继续 HTTP 200。Step 5A 只修改 `frontend/src/styles.css`、一个直接前端测试及当前状态/evidence 文档；未修改 Schema/migration、依赖/lockfile，未读取秘密、执行 Git 交付或进入 Step 6；
- 规模审计：Step 5A 为 2 个批准生产/测试文件、净新增 58 行；按已冻结归属复算，Stack 1 为 8 文件/净新增 755 行，Stack 2 为 6 文件/净新增 455 行，均低于各自 12/1000 与 18/1400 阈值；F-007 累计 14 文件/净新增 1210 行，低于任务 30/2200 阈值；
- 下一入口：Step 6 真实高德 UAT 仍为 `TODO / DEFAULT_CLOSED`，必须等待用户单独明确批准。

## F-007 Step 5：临时 SQLite、loopback 浏览器与独立隐私安全审查

- 日期：2026-08-30；结论：`DONE_WITH_FINDING / BLOCKED`；未执行真实 Provider UAT，不覆盖 `FAIL / AMAP_QPS_EXCEEDED`；
- 隔离：用户服务始终保持 8000/PID 52516、5173/PID 77692；验收使用 18007/15177 与 E 盘临时 SQLite，结束后只关闭验收进程；四个端点验收期间均 HTTP 200；
- SQLite：V4 canonical synthetic 完成 POST、终态 partial、retry 到 attempt 2、reload 恢复及 DELETE；检查得到 `schema_migrations=[1,2]`、执行中 1 个 partial job、删除后 0 job。F-006 组合矩阵与 V2/V3/V4 SQLite API 集合 `40 passed in 59.29s`；
- 浏览器：desktop 1440×1000 与 mobile 390×844 均无水平溢出；duplicate id、broken `aria-describedby`、unlabeled control 与可见按钮小于 44px 的结果均为 0；live region=2；skip link 首个 Tab 可达；DELETE 确认按钮自动获焦，Escape 后焦点回到触发按钮；
- network/console：Playwright 记录 99 条请求，唯一 authority 为 `127.0.0.1:15177`；Vite proxy 后端日志仅 loopback；console 0 error/0 warning，只有 React DevTools info；无非 loopback 业务访问；
- 独立审查：Codex Security diff scan `d34206c0-41f4-481a-8282-b00115238d76`，6/6 变更生产文件覆盖完整、0 finding；审查确认 limiter 不持有/记录 Key、URL、坐标、响应、错误 body 或请求数据，不进入 SQLite/API，跨 job 共享和 task cancel/drain 边界未发现可验证安全缺陷。TAC connector 未登录，仅影响可选状态可见性；
- accessibility finding：结果状态 `partial` 与 freshness `unknown_validity` 的普通文本前景 `rgb(155,103,22)` 实测约 `4.2:1`，低于 WCAG AA `4.5:1`；装饰问号按非文本 3:1 可通过，但文字 finding 仍成立。Step 5 禁止前端修改，未修复；
- 过程记录：首次 V2 探索的手工请求与固定 synthetic result summary 不匹配，SQLite Repository 以 `result_request_mismatch` fail closed；没有 Provider/Agent 调用，未作为 PASS。随后 V4 canonical 浏览器路径通过，V2 canonical 路径由 40 项自动化集合覆盖；
- 范围：Step 5 仅新增被 Git ignore 的临时 config、日志、截图和 E 盘临时数据库，并同步当前状态/evidence 文档；未修改生产源码、测试、fixture、Schema/migration、依赖/lockfile，未执行 commit/push/PR/CI；
- 下一入口：阻塞 Step 6；需用户另行批准最小 Step 5A 调整既有状态色并重新执行 desktop/390px contrast 与范围审计。

## F-007 Step 4：离线稳定性、跨 job 竞争与兼容回归

- 日期：2026-08-30；结论：`PASS / OFFLINE ONLY`；不覆盖 2026-08-30 `FAIL / AMAP_QPS_EXCEEDED`，不构成真实 Provider UAT；
- 跨 job 证据：两个并发单城市 planning job 分别使用 public transit 与 walking；route concurrency 常量保持 2，共享 limiter 观察 8 次 route starts 为 `0.0/0.5/1.0/1.5/2.0/2.5/3.0/3.5`，相邻间隔 `>=0.5s`，任意 `[t,t+1)` 最多 2 次；此前 Amap geocode/POI、QWeather、DeepSeek 调用不推进该时间线；
- MockTransport：Amap walking 首次 503、transit 首次带合法 Retry-After 的 429，两个 runtime 的 initial/retry 合并进入同一 limiter，各自仅额外尝试一次并最终成功；未修改 Amap adapter 生产代码；
- retry 分类：timeout/server/合法 Retry-After 429 为 2 attempts；auth/schema/empty/unknown/无合法 Retry-After 429 为 1 attempt；额外预算只在获准 slot 后、HTTP 前预留；
- deadline/stop：Step 2/4 fake-clock 集合覆盖 backoff→slot、deadline 等号允许、shortfall/oversleep 拒绝、terminal/cancel/budget 后零新 HTTP、零未启动 retry budget；waiter 与 active peer cancel/drain，一个 runtime 关闭不关闭共享 limiter；
- exact 命令：`uv run --project backend --frozen pytest -q backend/tests/application/test_provider_planning_job_executor.py backend/tests/application/test_provider_attempt_runtime.py backend/tests/adapters/test_amap_route_adapter.py -k "two_concurrent_planning_jobs_share_one_paced_route_timeline_without_burst or route_retry_matrix_paces_only_approved_second_attempts or route_retry_backoff_precedes_shared_qps_slot or walking_and_transit_mock_transport_retries_share_paced_http_starts"` → `11 passed / 97 deselected`；
- 相关集合：domain/limiter/runtime/bootstrap/provider executor/multiday/multicity/Amap adapter/governance/F-005 eval `299 passed in 7.79s`；
- 后端：首次全量为 `1446 passed / 1 failed`，唯一失败是 F-006 runner `PreflightOnly` 因用户要求保持 8000 端口运行而按设计 fail closed；未停止服务。精确 deselect 后为 `1446 passed / 1 deselected`，runner 其余测试 `4 passed / 1 deselected`；
- 前端/静态：前端 `12 files / 131 passed`；Prettier、ESLint、TypeScript、Vite build 通过；backend Ruff format/check 与 strict mypy 通过；
- 范围：Step 4 只修改 3 个批准测试文件，净新增 289 行；任务累计 12 个生产/测试文件、净新增 1152 行，低于 Stack 1/2 与任务阈值；production planning service、Provider adapter、API、Repository、SQLite、frontend、Schema/migration、依赖/lockfile diff 为 0；
- 外部与服务：全部新证据使用 fake monotonic clock、MockTransport、synthetic fixture 和默认网络阻断；8000/PID 52516 与 5173/PID 77692 未停止或重启；未读取秘密、创建数据库、调用 Provider、commit、push、PR、远程 CI 或进入 Step 5；
- 下一入口：等待用户明确批准 Step 5 本地纵向与独立隐私安全审查。

## F-007 Step 3：production bootstrap 单实例接线

- 日期：2026-08-30；结论：`PASS / TDD RED→GREEN`；
- RED 测试：在 `test_bootstrap.py` 新增完整配置四类 task runtime 共享 identity，以及缺配置零 limiter 构造测试；只使用 synthetic key/private key 与内存 Repository，无网络；
- RED 命令：`uv run --project backend --frozen pytest -q backend/tests/test_bootstrap.py -k "route_limiter"`；
- RED 结果：exit 1，`1 failed / 1 passed / 23 deselected`；完整配置的 legacy/V2/V3/V4 runtimes 当前 `_attempt_limiter is None`，exact shared-instance 断言失败；configuration-missing 路径零 limiter 构造已通过；
- RED 边界：尚未修改 bootstrap 生产代码；未修改 planning service、Provider adapter、API、Repository、SQLite、frontend、Schema/migration、依赖/lockfile；未停止/重启服务、读取秘密、创建数据库、调用 Provider 或执行 Git 交付；
- GREEN 实现：完整配置 Gate 通过后，`build_planning_job_executor()` 使用 domain exact policy、同一 `monotonic` 与 `asyncio.sleep` 创建一个 `PacedAttemptLimiter`；既有 factory 闭包把该实例注入每个 `ProviderAttemptRuntime`；configuration-missing 在构造前返回；
- 共享证据：由同一 production factory 创建的 legacy/V2/V3/V4 runtimes limiter identity 完全相同；fake clock 下四次 route attempt starts 为 `0.0/0.5/1.0/1.5`；
- 隔离证据：相同 runtimes 的 Amap `SEARCH_POIS`、QWeather forecast、DeepSeek generation 均不推进 fake clock；walking/public transit 在 application 中继续共用 `CALCULATE_ROUTES` operation；
- budget/cancel：route concurrency=2、logical/HTTP attempt budgets、最大 180 秒 deadline、terminal/cancel/postflight/peer drain 由 Step 2 与 legacy/V2/V3/V4 集成回归保持；未新增后台 task、公开状态或持久化；
- GREEN 验证：bootstrap exact `2 passed`；bootstrap、domain/limiter/runtime、provider executor、multiday、multicity 集合 `181 passed`；后端全量 `1408 passed in 75.56s`；Ruff format/check 和 strict mypy `150 source files` 通过；
- 文档/diff：文档检查 17 required/29 Markdown、检查器单元测试 24 项、tracked 与两个 untracked 新文件 whitespace checks 全部通过；
- 范围：Step 3 只修改 `bootstrap.py` 与 `test_bootstrap.py`，`+165/-0`；累计生产/测试 10 文件、`+901/-38`（净新增 863 行），未预期文件 0；planning services、Provider adapters、API、Repository、SQLite、frontend、Schema/migration、依赖/lockfile diff 为 0；
- 服务/外部边界：后端 `/api/health` 与前端根页均 HTTP 200，listener 保持 8000/PID 52516、5173/PID 77692；全部测试使用 synthetic values、内存 Repository、fake clock/MockTransport 与默认网络阻断；未停止/重启服务、读取本地秘密、创建数据库、调用真实 Provider、commit、push、PR、远程 CI 或 Step 4；
- 当前限制：production bootstrap 已接线但未经 Step 4 离线 burst 矩阵、Step 5 本地纵向或 Step 6 真实 UAT，不得宣称 F-007 已完成或真实 QPS 已 PASS；
- 下一入口：等待用户明确批准 Step 4。

## F-007 Step 2：纯 pacing policy、paced-slot limiter 与 runtime 注入

- 日期：2026-08-30；结论：`PASS / TDD RED→GREEN`；
- RED 范围：先只修改批准的 `test_resilience.py`、新增 `test_provider_attempt_rate_limiter.py` 和 `test_provider_attempt_runtime.py`，未修改生产源码；
- RED 命令：`uv run --project backend --frozen pytest -q backend/tests/domain/test_resilience.py backend/tests/application/test_provider_attempt_rate_limiter.py backend/tests/application/test_provider_attempt_runtime.py`；
- RED 结果：exit 1，3 个模块在 collection 阶段按预期失败；domain 缺少 `AttemptPacingPolicy` export，application tooling 缺少 `PacedAttemptLimiter` export；没有环境、网络或既有断言漂移；
- RED 边界：未接 bootstrap、planning service、Amap adapter、API、Repository、SQLite 或前端；未停止/重启 8000/5173，未读取秘密、创建数据库、调用 Provider 或执行 Git 交付；
- GREEN 实现：domain 新增 immutable `AttemptPacingPolicy` 和 exact lookup；application 新增仅持有枚举 scope、clock、sleeper、lock 与 `next_start_at` 的 `PacedAttemptLimiter`；task runtime 以可选协作者完成 preflight→slot→postflight/reserve→HTTP，未注入时保持既有行为；
- pacing 证据：fake monotonic start 序列为 0/0.5/1.0/1.5/2.0，任意 `[t,t+1)` 最多 2 次；idle 后下一次可立即开始但不补发 token；walking/public transit 共用 operation，Amap geocode/POI、QWeather/DeepSeek bypass；
- deadline/budget：`slot_at == latest_start_at` 允许，shortfall 与 oversleep 拒绝；slot 拒绝、runtime 在 slot wait 中关闭或 postflight 失败均零后续 HTTP、零未启动 retry budget；
- cancellation：取消 waiter 不启动 attempt，limiter 可继续使用；task runtime close 取消/drain active peers，但不关闭共享 limiter；两个独立 runtime 共用时间线并可独立关闭；
- GREEN 验证：定向 domain/limiter/runtime `102 passed`；相邻 provider executor、multiday、multicity、offline orchestrator、candidate resolution、Amap adapter `257 passed`；后端全量 `1406 passed in 77.19s`；Ruff format/check 通过，strict mypy `150 source files` 无问题；
- 文档与 diff：文档检查 17 required/29 Markdown、检查器单元测试 24 项、tracked 及两个 untracked 新文件 whitespace check 均通过；
- 范围：8 个批准生产/测试文件，`+736/-38`（净新增 698 行），未预期文件 0；production bootstrap、planning services、Provider adapters、API、Repository、SQLite、frontend、Schema/migration、依赖/lockfile diff 为 0；
- 服务与外部边界：后端 `/api/health` 与前端根页均 HTTP 200，listener 仍为 8000/PID 52516、5173/PID 77692；未停止/重启服务，未读取秘密、创建数据库、调用 Provider、访问非 loopback 业务服务、commit、push、PR、远程 CI 或 Step 3；
- 下一入口：等待用户明确批准 Step 3；当前 limiter 尚未由 production bootstrap 注入，因此本 Step 不宣称真实调用 QPS 已修复。

## F-007 Step 1：process-shared paced-slot 可实现设计冻结

- 日期：2026-08-30；结论：`PASS / DOCUMENTATION_ONLY`；
- 现状核对：legacy/V2 的 `_lookup_route` 与 V3/V4 的 `_collect_routes` 均通过既有 `_governed_call` 进入 `ProviderAttemptRuntime.execute(provider=AMAP, operation=CALCULATE_ROUTES)`；walking/public transit 仅在 typed request mode 不同，现有 route concurrency 保持 2；
- 所有权：完整配置的 `build_planning_job_executor()` 未来创建一个 process-scoped limiter，并通过 `attempt_runtime_factory` 闭包注入每个 task-scoped runtime；缺配置 executor 不创建；runtime close 不关闭 shared limiter；Amap adapter 不作为生产修改面；
- 算法：exact Amap route scope、0.5 秒 monotonic paced slot、无 idle token 累积、相邻 starts 至少 0.5 秒、任意 `[t,t+1.0)` 半开窗口最多 2 次；`slot_at > latest_start_at` 零等待拒绝，等号允许；sleep/oversleep 计入 deadline；
- 时序：initial/retry 共门禁；retry/backoff → preflight → slot → postflight deadline/terminal/cancel/budget 复核与 retry reservation → HTTP；未启动 attempt 不消费 retry budget，已授予 slot 在后续取消时保守不回收；
- 取消：等待 lock/slot 与 active HTTP 都保留在现有 runtime active task 集合；close/异常 cancel 并 drain peers；取消一个 runtime 不影响其他 job 后续使用 limiter；
- 测试矩阵：fake clock、MockTransport、scope/nonmatching、半开窗口、idle/no-burst、并发顺序、walking/transit 共线、initial/retry、deadline 边界/oversleep、budget、waiter/peer drain、跨 job singleton、bootstrap 缺配置和 legacy/V2/V3/V4/F-005/API/Repository/SQLite/UI exact regression；
- 文档门禁：`check_docs.py` 通过 17 份 required/29 份 Markdown，检查器单元测试 `24 tests / OK`，`git diff --check` 通过；
- 范围：diff 仍只有 7 份当前治理/权威文档；没有生产源码、测试、fixture、archive、Schema/migration、依赖/lockfile、数据库、秘密读取、Provider 调用、commit、push、PR 或远程 CI；
- 服务：`/api/health` 与前端根页均 HTTP 200；listener 仍为 8000/PID 52516 和 5173/PID 77692，未停止或重启；
- 下一入口：等待用户明确批准 Step 2；真实 Provider UAT 仍只允许在另行批准的 Step 6。

## F-007 Step 0：QPS FAIL 证据、治理激活与基线复核

- 日期：2026-08-30；结论：`PASS`（Step 0 治理）/ `FAIL / AMAP_QPS_EXCEEDED`（新增真实本地验收证据）；
- Git/CI/PR：Step 0 开始前 `HEAD == main == origin/main == 905a950fa2483f2e441eb520a20897dcc1daa722`，工作区干净，无开放 PR；归档 main CI run `32692800113` 为 completed/success；
- 真实现象：用户在本机单城市杭州行程验收中得到 `provider_rate_limited`、`route_primary_unavailable` 和 `data_missing` 安全终态；高德控制台同期显示“步行路径规划 2.0”接口 QPS 限制 3、最高 QPS 6、超限 3 次；月调用量未显示总额度耗尽；
- 证据边界：该现象支持“路径规划请求发生 QPS 突发并触发限流”，不把控制台聚合数据冒充逐 attempt trace，也不推断 Key、完整 URL、坐标、原始响应、错误 body 或 infocode；
- 历史隔离：本条是新的 F-007 真实验收 FAIL，不覆盖 Step 45M `FAIL`、Step 45T `PASS`，不改写 F-006 `LOCAL_ACCEPTANCE_PASS`，项目真实 Provider 就绪继续为 `PARTIAL`；
- 治理：F-007、D-018、Step 0–8、两层 stacked PR、核心文件/受控相邻扩展和规模阈值已写入当前权威文档；首层本地分支为 `feat/f-007-amap-qps-policy-runtime`；
- 范围：本 Step 只修改当前治理与权威文档；没有源码、测试、fixture、Schema/migration、依赖/lockfile、数据库、秘密读取、Provider 调用、commit、push、PR 或远程 CI；
- 服务：Step 0 完成复核时用户现有 `127.0.0.1:8000` 与 `127.0.0.1:5173` listener 均保持运行，未停止或重启；
- 下一入口：等待用户明确批准 F-007 Step 1；真实高德 UAT 仍默认关闭，只有 Step 6 可在独立批准后执行。

## F-006 Step 8：依序合并、main CI、归档与任务关闭

- 日期：2026-08-24；结论：`PASS / DELIVERED / LOCAL_ACCEPTANCE_PASS / ARCHIVED`。用户明确批准 Step 8，PR #38/#39/#40/#41 已按批准顺序 squash merge；main commits 依次为 `22be214a`、`97dc949f`、`d70eb145`、`d82ca5c6`；
- clean-restack：#39/#40/#41 在前层 squash merge后分别将 base 改为 main，并以普通 merge commit 吸收最新 main；GitHub diff 收敛为 9/11/17 个本层文件，mergeability 均为 CLEAN/MERGEABLE；没有 rebase、替代 PR 或 force-push；
- CI：clean-restack PR runs `32690231596`、`32690839987`、`32691459865` 全部 success；逐层 main runs `32689910671`、`32690516152`、`32691143922`、`32691778088` 全部 success；完整功能 main `d82ca5c65794749932be65724455aca146a7cbca` 的 run `32691778088` 为 success；
- 归档：完整任务卡保存为 [F-006 archive](../archive/task-cards/F-006-mvp-local-acceptance.md)，current-task、implementation-plan、progress、roadmap、docs map 与 D-017 已切换为关闭状态；
- 范围：归档层只修改当前治理/权威文档并新增任务卡；生产源码、测试、Schema/migration、依赖/lockfile 和 CI workflow diff 为 0；
- 边界：未读取秘密或调用真实 Provider；F-006 的 synthetic/loopback/clean-checkout/local acceptance 不等于真实 Provider UAT。F-001 和项目真实 Provider 就绪继续为 `PARTIAL`，Step 45M `FAIL`、Step 45T `PASS`、unknown/null、混合交通 fallback 仅离线及 F-004B2 `BLOCKED / ARCHIVED` 均保持；
- 下一入口：当前无活动任务和 roadmap 候选；新工作必须先起草并批准任务卡或路线图变更。

## F-006 Step 7：本地全量门禁、独立 review 与四层交付

- 日期：2026-08-22；结论：`PASS`。固定 Python `3.13.3`、Node `22.16.0`、pnpm `11.19.0` 运行 `scripts/verify.ps1`，Ruff format/lint、151 个 source strict mypy、后端 `1388 passed`、Prettier、ESLint、TypeScript、前端 `12 files / 131 passed`、Vite build、文档测试 `29 passed` 和 17 required/28 Markdown 契约全部通过；
- TDD/门禁修正：首次统一门禁依次暴露并关闭一个 mypy `Any`、两个异步终态测试假设和一个绝对日期测试脆弱点；随后独立 review 又关闭 Stack 1 测试归属、Stack 2 提前 `remove` 接口引用，以及 Stack 3 跟踪暂时失败、损坏 canonical pointer 回落和 storage-disabled 页内恢复问题。Stack 4 再将 runner 的版本错误、固定双端口冲突、提前退出、health timeout、SQLite 安全投影、精确 child cleanup 和受控 Windows Ctrl+C→`finally` 清理固化为离线 self-test；相关测试全部使用动态上海日期和权威 terminal polling；
- 提交链：`b99d5fc` → Stack 1 `b3e29aa` → Stack 2 `972b1d4` → Stack 3 `f5903f4` → Stack 4 `7a9b488` + 文档/runner 修正 `e6d3547`/`7f8cabb`/`2b95930`。四层最终独立 review 无未关闭 finding；Stack 4 复审核对 `f5903f4..2b95930`，确认 Ctrl+C/失败只清理两个已持有 Process、无关 peer 保持存活，且无 Schema/migration、依赖/lockfile、秘密或 Provider 边界变化；
- GitHub：Draft PR #38（`main`→Stack 1）、#39（Stack 1→Stack 2）、#40（Stack 2→Stack 3）、#41（Stack 3→Stack 4）均 open；对应 Windows offline CI runs `32503520656`、`32503533764`、`32503554642`、`32547492597` 均为 success；没有 merge、最终 main CI 或归档；
- 范围：四层生产/测试/script 分别为 11/9/11/3 文件，净新增 472/134/843/969 行；任务累计去重后为 31 文件、净新增 2418 行，`styles.css` 净新增 74 行。全部低于 20/1600、65/5200 和 600 行阈值；Schema/migration、依赖/lockfile、CI workflow 和秘密配置 diff 为 0；
- 边界：本地门禁显式清空 Provider key 环境变量；未读取秘密、调用真实 Provider 或访问非 loopback 业务服务。本条证据不等同真实 Provider UAT；F-001 `PARTIAL`、Step 45M `FAIL`、Step 45T `PASS`、unknown/null、混合交通 fallback 仅离线及 F-004B2 `BLOCKED / ARCHIVED` 均保持；
- 下一入口：等待用户单独批准 Step 8；此前不得 merge、运行最终 main CI 或归档。

## F-006 Step 6：临时 SQLite、组合 journey、loopback QA 与独立安全审查

- 日期：2026-08-21；结论：`PASS`。新增 14 个完全离线组合 journey 和 1 个矩阵闭合测试；临时 schema v2 SQLite 纵向集合 `56 passed`，migration 仍只有 1/2；
- journey/eval：四版本无配置安全失败、legacy 五终态、V2 ready、多城市 V3 ready/partial、已购铁路 V4 partial、unknown fare=null、unknown-validity 与 user-provided 来源均由 typed application/API/SQLite 入口验证；F-005 固定 48-case eval 对应测试 `26 passed`；
- 重启测试修正：两个既有 SQLite restart case 原先错误地把初始 POST draft 当成重启后的预期结果；本 Step 只修正测试，使第一进程先取得权威 `failed/configuration_missing` terminal result，再验证重启和幂等返回 exact match，生产代码未因该漂移修改；
- 干净检出：临时检出位于 `E:\Agent\.tmp\f006-step6\clean-checkout-20260821-2340`，只应用当前 diff 和 8 个明确 untracked 任务文件；backend frozen/offline 安装 36 包、frontend frozen/offline 复用 257 包，下载 0。实际 `scripts/run-local.ps1` 通过 exact health，SQLite migration 为 1/2；Ctrl+C 后 8000/5173 listener 为 0，未遗留指向检出的 Python/Node process；
- 浏览器：使用已安装全局 Playwright CLI，不通过 `npx` 探测或安装；V4 partial journey 在 `1440×1000` 与 `390×844` 覆盖 G1234 规范化、unknown/null、用户提供未核验、reload 恢复、canonical UUID-only pointer、inline DELETE、确认/Escape/完成后的确定性焦点。浏览器业务请求与后端均仅 loopback，console 0 error/0 warning，document 无横向 overflow，label/description/error 引用、live region、390px 可见交互 44px、颜色/焦点对比检查通过；
- 隐私安全：Codex Security diff scan `dcb1c6b6-49e5-47da-87a0-706b43374a7e` 对 snapshot `94712a80...` 覆盖 21/21 changed-file review items，并人工补充 runner/SQLite/browser 边界，0 finding；报告位于 `C:\Users\24696\AppData\Local\Temp\codex-security-scans-4q2I1p\13-intelligent-travel-assistant\b99d5fc4c89b0f25ec89e4e12cd1755a7c3be46f_20260821T154710Z_nciw1eon\report.md`；
- 直接门禁：组合/SQLite `56 passed`，runner unittest `28 passed`，新增/修正 3 个 Python 测试文件 Ruff check/format 通过；前端全量 `12 files / 126 passed`；
- 范围：Step 6 只新增 1 个组合验收测试、修正 2 个相邻 SQLite restart 测试并更新当前状态/evidence；累计生产/测试/script 29 文件、净新增 1709 行，`styles.css` 净新增 74 行，低于全部阈值。Schema/migration、依赖/lockfile diff 为 0；未读取秘密、调用真实 Provider、访问非 loopback 业务服务、commit、push、PR、CI、merge 或 Step 7；
- 证据边界：F-001 `PARTIAL`、Step 45M `FAIL`、Step 45T `PASS`、混合交通 fallback 仅离线、F-004B2 `BLOCKED / ARCHIVED` 均保持；本 Step synthetic/loopback/clean-checkout 不等同真实 Provider UAT；
- 后续入口已由用户批准的 Step 7 取代；本条历史 Step 6 证据不改写。

## F-006 Step 5：安全 PowerShell 本地运行入口

- 日期：2026-08-21；结论：`PASS`。新增唯一 `scripts/run-local.ps1`，固定 Python `3.13.3`、Node `22.16.0`、pnpm `11.19.0` 和 `127.0.0.1:8000/5173`；
- RED：`uv run --project backend --frozen python -m unittest scripts.tests.test_run_local` 在 runner 不存在时得到 `2 errors / 1 failure`，精确证明入口、所有权清理和自检缺失；
- GREEN：同一模块最终 `4 passed`。contract self-test 验证 exact version/health parser、额外字段拒绝、临时 loopback listener 冲突/释放和精确无害 PowerShell child 清理；actual `-PreflightOnly` 核对已安装版本/入口与固定端口，未启动 FastAPI、Vite 或 SQLite；
- 离线/端口：设置 Corepack 禁网和 uv offline；直接使用已安装 `.venv` Python 与 Vite entry，缺失时不安装。端口检查只读 active listeners，冲突只报告 8000/5173，不查询 PID、不停止占用者；
- 健康/清理：直接 Process 模型避免 uv/pnpm wrapper 遗留；backend exact `/api/health`→frontend root 各 30 秒，HTTP 仅 127.0.0.1、禁 proxy/redirect。Ctrl+C、提前退出或任意失败只对保存的两个 Process ID 执行 stop/wait；
- 安全诊断：后端早退固定提示 backend/SQLite 路径或权限问题；所有未知异常使用固定脱敏 fallback，不回显 raw stderr、配置值或秘密。成功只输出 `http://127.0.0.1:5173/`，不自动打开浏览器；
- 范围：1 个 runner、1 个直接 unittest 和批准的运行/状态文档；未修改 Schema/migration、依赖/lockfile、公开 API shape，未创建数据库/启动业务服务、读取秘密、访问软件包仓库/Provider、执行 browser/Step 6 或 Git 交付；
- 下一入口：等待用户单独批准 F-006 Step 6，只允许临时 schema v2 SQLite、组合 synthetic journey、loopback desktop/390px、network/console/accessibility、干净检出与独立隐私安全验收。

## F-006 Step 4：全版本本机恢复、终态 DELETE 与焦点

- 日期：2026-08-21；结论：`PASS`。canonical localStorage key 固定为 `ita.last-local-job` 且只写 job UUID；legacy/V2/V3/V4 均通过既有 GET URI 和 strict response parser 恢复；
- RED：`corepack pnpm --dir frontend exec vitest run src/localJobRecovery.test.tsx src/tripPlanningApi.test.ts` 在生产实现前得到 `17 failed / 26 passed`，精确证明 canonical/旧 pointer 迁移、失效清理、错误保留、全版本恢复和 DELETE client/UI 尚未实现；
- GREEN：同一集合最终 `43 passed`。读取顺序 canonical→旧 V4→旧 V3；非法 UUID 在网络前清理，旧 pointer 只在相符 V3/V4 响应后迁移；`job_not_found` 清 pointer 并返回新建，网络/5xx/strict parser 失败保留 pointer 和“稍后重试恢复”；localStorage 异常被隔离，不阻断新任务；
- DELETE/焦点：前端 client 对既有单任务 URI 发送 DELETE 并要求 204；仅 terminal 渲染“删除本机任务”。inline 确认把焦点送到确认按钮，取消/Escape 回到原触发按钮；成功清全部 pointer、移除结果并聚焦“行前设定”，失败保留任务/pointer 并显示安全 alert；“返回修改”只清 pointer；
- 兼容：canonical 新建/恢复覆盖 legacy/V2，旧 pointer 迁移覆盖 V3/V4；同一 strict parser、状态跳转、retry 和 replan 既有测试通过。公开 POST/GET/retry/DELETE/replan URI、顶层 shape、fingerprint、Repository/SQLite schema v2、migration 1/2 均未修改；
- 验证：前端全量 `12 files / 126 passed`；Prettier check、ESLint、TypeScript `tsc --noEmit` 和 Vite production build 均通过；`git diff --check` 通过；
- 范围：15 个 Stack 3 生产/测试文件，净新增约 630 行，未预期文件 0，低于 20 文件/1600 净行阈值；没有 PowerShell runner、组合 journey、SQLite/browser 验收、依赖/lockfile、秘密读取、数据库/服务、软件包仓库/Provider 访问或 Git 交付；
- 下一入口：等待用户单独批准 F-006 Step 5，只允许安全本地 PowerShell runner，不得自动进入 SQLite/browser 验收或交付。

## F-006 Step 3：三产品模式与有限 UX foundation

- 日期：2026-08-21；结论：`PASS`。前端第一组只显示“单城市”“多城市·自行填写交通段”“多城市·填写已购铁路车次”，不再向用户显示 legacy/V2/V3/V4 或第二层城际类型；
- RED：`corepack pnpm --dir frontend exec vitest run src/TripRequestForm.test.tsx src/PlanningStage.test.tsx` 在生产实现前得到 `3 failed / 19 passed`；缺口分别为三产品模式 group 不存在、plan conflict 恢复动作位于预算之后、needs_input 恢复动作位于诊断之后；
- GREEN：合并模式入口后继续通过既有 `endDateEdited` 与 strict serializer 选择 legacy/V2/V3/V4；切换进入已购铁路时仍清空/隐藏自由文本和相邻段。计划与无计划终态把主要恢复动作放在摘要之后、支持信息之前，共享组件只消费服务端 status/retryable/attempt/errors，不重算终态、freshness 或预算；
- 语义与兼容：unknown 费用仍显示“未知”且不按 0；partial 先展示已有计划，conflict verdict 先展示确定性冲突，configuration missing 不出现 retry；legacy/V2 两日 replan、V2 多日 scope、V3/V4 strict parser 与既有请求/结果测试保持；
- 可访问性基础：三个模式位于单一 `fieldset/legend`，原生 radio 保持键盘/焦点行为并关联说明；主要动作至少 44px，模式卡至少 48px，390px 下单列，既有 focus-visible/reduced-motion/overflow-wrap 保持。真实 desktop/390px browser、单一全页 live region 与焦点恢复纵向仍按计划留给后续批准 Step；
- 验证：扩大后的前端定向集合 `49 passed`；前端全量 `11 files / 109 passed`；Prettier check、ESLint、TypeScript `tsc --noEmit` 和 Vite production build 均通过；
- 范围：9 个 Stack 2 生产/测试文件，`243 additions / 113 deletions`、净新增 130 行；`styles.css` 为 `31 additions / 8 deletions`、净新增 23 行。未预期文件 0，低于 20 文件/1600 净行与 styles 600 行阈值；
- 安全与交付：未修改 API/contracts/fingerprint/Repository、Schema、migration、依赖或 lockfile；未进入 canonical/旧 pointer、DELETE、runner、SQLite/browser 或 Step 4；未读取秘密、创建数据库、启动服务、访问软件包仓库/Provider，未 commit、push、创建 PR 或触发 CI；
- 下一入口：等待用户单独批准 F-006 Step 4，只允许完整旅程 pointer/recovery/terminal DELETE 与焦点收口，不得自动进入 runner、数据库/browser 或交付。

## F-006 Step 2：无配置零调用安全终态与兼容接线

- 日期：2026-08-21；结论：`PASS`。production bootstrap 在必要 adapter 不完整时装配 `ConfigurationMissingPlanningJobExecutor`，完整配置仍装配既有 `ProviderPlanningJobExecutor`；显式 Repository 测试注入继续允许 optional executor；
- RED：`uv run --project backend --frozen pytest -q backend/tests/application/test_configuration_missing_planning_job_executor.py backend/tests/api/test_configuration_missing_trip_plans_api.py backend/tests/test_bootstrap.py` 在生产实现前以 3 个 collection ImportError 失败，精确证明 executor/export 尚不存在；
- GREEN：同集合最终 `33 passed`；扩大后的非 SQLite API/bootstrap 集合 `59 passed, 5 deselected`，覆盖 production 组合根、legacy/V2/V3/V4 POST→GET、同 shape errors、idempotent reuse、retry-not-allowed、配置全空/单 Provider/完整组合及既有部分配置 fail closed；
- Repository/状态：纯内存 state-machine 与 legacy/V2/V3/V4 typed Repository 集合 `169 passed`；executor 只接受 job ID，不扫描其他 draft，支持新建 `draft→normalizing→failed` 和 existing normalizing retry，结果固定为 `configuration_missing`、安全 message/diagnostic、`retryable=false`、空 plan/来源，AST 门禁证明无 adapter/Agent/tooling/network import；
- 静态门禁：全 backend Ruff format `147 files already formatted`、Ruff lint通过；`mypy backend/src` 对 66 个 source files 通过；
- SQLite 限制：用户本 Step 明确禁止创建数据库，因此 5 个 SQLite 测试被显式 deselect，没有运行或宣称 SQLite 纵向 PASS；`schema.py`、`migrations.py`、依赖和 lockfile diff 为 0，typed Repository 路径由内存契约验证；
- 范围：7 个生产/测试文件，净新增约 430 行，未预期文件 0；只另同步当前状态/evidence 文档。没有前端、fixture、`.env.example`、Schema、migration、依赖、lockfile 或归档修改；
- 安全与交付：未读取 `.env.local`/秘密/本地 Provider 配置，未创建数据库或启动业务服务，未访问软件包仓库/Provider，未 commit、push、创建 PR 或触发 CI；
- 下一入口：等待用户单独批准 F-006 Step 3，只允许三产品模式语言、legacy/V2 内部映射和有限 UX foundation，不得自动进入 pointer/DELETE、runner、浏览器验收或交付。

## F-006 Step 1：可实现设计冻结

- 日期：2026-08-21；结论：`PASS`。本 Step 只冻结无配置安全终态、三种产品模式、legacy/V2 内部选择、全版本恢复/旧 pointer、终态 DELETE、本地 PowerShell runner、局部 UX/accessibility、组合验收和四层文件归属；
- 代码事实：production bootstrap 当前只有三组必要 adapter 全部存在时才返回 planning executor；API 在 executor 为 `None` 时 reserve 但不调度，因此新 job 可停留 `draft`。前端当前只保存 `ita.active-v4-job`/`ita.active-v3-job`，单城市由 `endDateEdited` 选择 legacy/V2；Vite 固定 `127.0.0.1:5173`、strictPort 并代理 `127.0.0.1:8000`；
- 冻结结论：安全 executor 必须走 `draft→normalizing→failed`，输出既有 `configuration_missing`、固定 `required_provider_configuration_missing`、不可重试且 Provider/Agent/runtime 调用 0；canonical key 为 `ita.last-local-job`，旧 key 顺序 V4→V3；DELETE 只在前端权威终态显示；runner 固定 Python 3.13.3/Node 22.16.0/pnpm 11.19.0 和 8000/5173；
- 兼容与边界：不新增 URI/公开 key/错误码/strict shape/fingerprint；SQLite schema v2、migration 1/2、旧记录、V3/V4 replan 写前拒绝、V4 interests-only/privacy、F-004B2 阻塞和全部历史 live/离线事实保持；
- 范围：只修改当前治理和权威 Markdown；没有修改生产源码、测试、fixture、`.env.example`、Schema、migration、依赖、lockfile、历史 archive 或既有 evidence，未创建数据库/服务，未读取秘密，未访问软件包仓库/Provider，未执行 Git 写入；
- 验证：文档检查器、检查器测试、`git diff --check`、只允许 Markdown 的范围审计和秘密模式审计通过；
- 下一入口：等待用户单独批准 F-006 Step 2，仅以 TDD 实现 Stack 1 无配置安全终态与兼容接线，不得自动进入 UX、恢复、runner、数据库或交付。

## F-006 Step 0：任务激活、基线复核与治理

- 日期：2026-08-21；当前结论：`PASS`。F-006 已作为唯一 `ACTIVE` 任务进入 Step 0；本条只记录当前事实与治理证据，不改写下方 F-004C 或更早历史 evidence；
- Git：Step 0 开始前在 `main`，工作区干净，`HEAD == main == origin/main == b99d5fc4c89b0f25ec89e4e12cd1755a7c3be46f`；
- PR：#34/#35/#36 已依序 squash merge，归档 PR #37 已合并；GitHub 开放 PR 为 0；
- CI：run `32486428083` 为 `completed / success`，event `push`，branch `main`，head SHA 为 `b99d5fc4c89b0f25ec89e4e12cd1755a7c3be46f`；
- 归档：F-004C Step 0–6 `DELIVERED / ARCHIVED`，完整任务卡仍位于 [F-004C archive](../archive/task-cards/F-004C-booked-rail-user-provided.md)；F-004B2 继续 `BLOCKED / ARCHIVED`；
- 治理：current-task、roadmap、implementation-plan、progress、docs map 与 D-017 已建立 F-006 Step 0–8、四层 stack、核心文件、受控相邻扩展和规模阈值；
- 分支：已从上述干净 main 创建 `feat/f-006-local-runtime-compatibility`；HEAD 仍为基线提交，没有 commit、push、PR 或远程 CI；
- 范围：只修改批准的当前治理与权威 Markdown；没有修改生产源码、测试、fixture、`.env.example`、Schema、migration、依赖、lockfile、历史 archive 或既有 evidence 条目；没有创建数据库或启动服务；
- 外部边界：只执行 GitHub PR/CI 只读查询；没有读取 `.env.local`、秘密或本地 Provider 配置，没有访问软件包仓库，没有调用高德、和风、DeepSeek、12306 或其他业务 Provider；
- 门禁：文档检查器通过（17 份必需文档、28 个 Markdown、CI/status/safety contracts）；检查器测试 `24 passed`；`git diff --check`、范围审计和 added-line 秘密模式审计均通过；
- 下一入口：等待用户单独批准 F-006 Step 1；不得自动修改生产源码、测试或进入实现。

## F-004C Step 6：三层交付、最终 main CI 与任务归档

- 日期：2026-08-21；结论：`PASS / DELIVERED / ARCHIVED`。F-004C Step 0–6 全部完成，当前没有活动任务；完整任务卡已归档为 [F-004C archive](../archive/task-cards/F-004C-booked-rail-user-provided.md)；
- 本地全量门禁：最终完整工作树 `scripts/verify.ps1` 通过，包含后端 `1360 passed`、前端 `107 passed`、Ruff format/lint、strict mypy、Prettier、ESLint、TypeScript、Vite build、24 项文档检查器测试和仓库文档契约；
- 独立 review：首次逐层 review 发现 Stack 1 过早把 V4 接入全局 discriminator/Planning unions，会使独立 CI 暴露未接线 API；修复将全局 wiring 移入 Stack 2，并 clean-restack 三层。最终 `abc1297^!`、`e9dec42^!`、`95e3d12^!` 逐层复审均为 `NO FINDINGS`；隐私安全复审也无未关闭 finding；
- 范围：Stack 1/2/3 分别为 6/15/15 个生产/测试/fixture 文件，净新增 1174/814/1194 行；任务累计 35 个文件、净新增 3182 行，均低于 18/1400 单 stack 与 50/4000 任务阈值；Schema、migration、依赖、lockfile、CI workflow 差异均为 0；
- PR/CI：PR #34/#35/#36 初始三层 CI 均成功；#34/#35 squash 后，后续分支通过普通 merge restack 吸收最新 main，没有 force-push。最终逐层 CI runs 为 `32482782649`、`32483888878`、`32484329856`，全部 `success`；
- 合并：PR #34/#35/#36 依序 squash merge，main 提交依次为 `b9c9ebb827fb38936eb93092e1d946621479b750`、`e59cd262a96bb451e87626563d5f8676bc9f7679`、`14c4deaf5acfc4b8e3ccfb18db172dfe910eb26e`；
- 最终 main：`main == origin/main == 14c4deaf5acfc4b8e3ccfb18db172dfe910eb26e`，CI run `32484789531` 为 `success`，实现合并后开放 PR 为 0；
- 安全与历史：没有读取 `.env.local`、秘密或 Provider 配置，没有调用高德、12306、和风、DeepSeek 或其他真实 Provider；F-004C 城际 logical call/HTTP attempt 为 0。F-001 `PARTIAL`、Step 45M `FAIL`、Step 45T `PASS`、unknown 不按 0、混合交通 fallback 仅离线、F-004A/F-004B1/F-005/F-004C 无真实 Provider UAT、F-004B2 `BLOCKED`、SQLite schema v2/migration 1/2 均保持；
- 下一入口：F-006 只是 roadmap 候选，必须先起草并批准任务卡，不得因 F-004C 归档而自动开始。

## F-004C Step 5A：V4 preferences 隐私修正与 Step 5 收口

- 日期：2026-08-21；结论：`PASS`。V4 已改用只含 `interests` 的专用 strict preferences；`free_text` / `hard_constraints` 在 FastAPI contract 解析阶段返回 422，早于 planning job reserve、SQLite 和 executor。Step 5 原 `BLOCKED` finding 保留在下方历史条目，本修正不改写首次审查事实；
- RED/backend：定向 contracts + SQLite API 首次为 `3 failed / 20 passed`；两个非法 preferences 字段未抛 validation error，SQLite API 返回 202 而不是 422。RED/frontend 首次为 `2 failed / 105 passed`；V4 仍显示自由文本且 DTO 仍含 `free_text` / `hard_constraints`；
- GREEN/contracts/API/SQLite：新增 V4 interests-only strict model 和 synthetic sentinel；非法 `free_text` / `hard_constraints` 均 422，`planning_jobs=0`、executor 未调度，SQLite 文本中无 sentinel；legacy/V2/V3 继续使用既有 preferences shape；
- GREEN/application/Agent：V4→内部 planning projection 显式只复制 interests，并为旧内部模型使用空安全默认；generation context 的自由文本/硬约束为空，repair payload 不含两个键，sentinel 不进入 generation 或 repair；service number 与完整城际段既有隔离不变；
- GREEN/frontend：进入 V4 时清空并隐藏自由文本，V4 serializer 的 preferences 精确为 `{interests}`；切回 V3 时字段仍为空，不恢复或静默携带 sentinel；
- 验证：Step 5A backend 定向 `26 passed`，frontend 全量 `107 passed`，F-004C scoped backend `51 passed`，后端全量 `1360 passed`；Ruff format/check、strict mypy（144 source files）、Prettier、ESLint、TypeScript 和 Vite build 全部通过；
- 独立安全审查：Codex Security working-tree scan `f997d002-9bdd-4a96-9807-ebd1198de42d` 完整覆盖 25 个权威源码项，0 candidates / 0 findings；本机报告位于 `C:/Users/24696/AppData/Local/Temp/codex-security-scans-IZ4PUi/13-intelligent-travel-assistant/577bdcbadf2e024022e59e52527d13edb0cbd659_20260821T115513Z_qjsazt_p/report.md`。Codex Security Access connector 未登录，TAC 受保护输出可见性无法核验，但不改变本地扫描结论；
- 独立只读复审：结论 `NO FINDINGS`。复审确认 422/零持久化/Agent 隔离/前端清空与 legacy/V2/V3 兼容闭环；另一个 defense-in-depth 候选因生产结果只能由同一 typed request 在可信进程内确定性重建、无外部 result 写入口而关闭为非可操作 finding；
- 范围：Step 5A 只修改 5 个批准的生产文件和 4 个对应测试文件，以及当前权威状态/evidence 文档；未修改 Schema、migration、依赖或 lockfile，未读取秘密、调用 Provider、执行 Git 写入或进入 Step 6；按 Git numstat 复算，任务累计为 35 个生产/测试/fixture 文件、净新增 3182 行，低于 50 文件/4000 净新增行阈值；
- Step 5 结论：原 privacy finding 已关闭，先前临时 schema v2 SQLite、loopback desktop/390px、network/console/accessibility 证据继续有效；10 个 synthetic `-wal` / `-shm` sidecar 的本机策略清理限制保持披露，不含真实 Provider、凭证或用户数据；
- 下一入口：等待用户单独批准 Step 6，才允许运行交付前全量门禁并按三层拓扑执行 commit、push、stacked PR、独立 review、远程 CI、依序合并、必要 clean-restack、最终 main CI 和归档。

## F-004C Step 5：临时 SQLite、loopback browser QA 与独立隐私安全审查

- 日期：2026-08-21；结论：`BLOCKED`。SQLite、desktop/`390×844`、loopback network、console 和基础 accessibility 证据已完成，但独立隐私安全审查发现 V4 自由文本可绕过 D-016 禁止票务/个人数据边界；Step 5 不得记为通过，也不得进入 Step 6；
- SQLite：新增 V4 browser support 与临时 schema v2 HTTP 纵向；2/3 城分别覆盖 create/read/restart/idempotency/retry/delete、V3 旧记录读取、1/2 相邻段、`G1234`/`D2281`、unknown fare `null` 和 migration 精确 `1/2`。新增纵向 `3 passed`，F-004C scoped backend `47 passed`，Ruff 与 strict mypy（144 files）通过；
- Browser：真实本机 Vite → FastAPI → 临时 SQLite → synthetic V4 executor 在 desktop 验证两城 create/reload/retry/attempt 2，在 `390×844` 验证三城两段、service number 规范化、partial、两项 unknown 不按 0、用户提供/未核验和来源时效；desktop/mobile 水平 overflow、重复 ID、无可访问名称控件均为 0；成功窄屏会话 console error/warn 为 0；
- 网络：浏览器共观察 75 条 HTTP/WebSocket 请求，非 loopback 为 0；API 只出现同 URI create/get/retry。城际 Provider logical call 和 HTTP attempt 均为 0，没有调用高德、12306、和风、DeepSeek 或其他外部服务；
- 工具边界：本机缺少已缓存 Playwright CLI 包，`npm_config_offline=true` 的探测以 `ENOTCACHED` fail closed，没有访问 registry；改用已安装的 Codex 应用内浏览器。该浏览器的 date `fill` 未触发 React state，测试仅通过本地 CDP 在页面内设置 synthetic 日期并派发 input/change 事件；没有修改生产代码或持久浏览器配置，结束时已关闭验收 tabs 并恢复 viewport；
- 临时数据：成功三城数据库只含 schema versions `1/2`、V4 partial attempt 1、`G1234`/`D2281` 和两项 null fare，禁止字段名扫描为 0；五个精确主 SQLite 文件已在验证后删除。最终范围审计发现其 10 个 synthetic `-wal` / `-shm` sidecar 仍在系统临时目录；两次使用精确 `Remove-Item -LiteralPath` 的清理均被本机命令策略拒绝，因此没有绕过策略删除。这些 sidecar 不含真实 Provider、凭证或用户数据，但必须如实保留为本机清理限制。字段名扫描也不能关闭下述“禁止值藏入合法自由文本”的 finding；
- 独立隐私 finding（MEDIUM/P2）：`TripPlanRequestV4` 复用允许 `preferences.free_text` / `hard_constraints` 的 `TravelerPreferences`。订单、证件、联系方式、座位、二维码、Cookie 或自由备注等禁止内容可作为合法嵌套字符串通过 strict parser；完整 request 会写入 SQLite，且 V4→V3 application 投影只移除 `service_number`，这些自由文本仍可进入 generation context。现有负向测试只拒绝 segment 额外键，SQLite 测试只查字段名，未证明禁止值不可进入；
- 审查工具事实：主流程首次 Codex Security workspace scan 在创建 scanId 前因本地 Unicode surrogate 编码失败，未重试冒充成功；独立审查者随后形成只读报告，并在工作树新增 SQLite/browser support 后人工复核 finding 仍成立。报告位于本机临时安全扫描目录，不作为仓库交付物；
- 自动化：frontend `107 passed`，ESLint、TypeScript、Vite build 通过；Node 实际版本为 24.19.0，与项目声明 22.16.0 的 engine warning 保留，不把该环境差异写成冻结 Node 门禁；
- 范围：Step 5 新增 2 个直接 browser/SQLite 测试支撑文件，生产源码、Schema/migration、依赖/lockfile 改动为 0；没有读取秘密、执行真实 Provider UAT、commit、push、PR、CI、merge 或 Step 6；
- 下一入口：需要用户另行批准一个 F-004C 隐私修正步骤，至少为 V4 使用不含自由文本/硬约束的专用 preferences allowlist（或严格强制两者为空），并以 synthetic sentinel 证明 API 422、SQLite 和 generation/repair context 均不含禁止值；修复与独立复审通过后，才能恢复 Step 5 收口。不得自动修复或进入 Step 6。

## F-004C Step 4：V4 前端交互、strict parser、来源披露与恢复

- 日期：2026-08-21；结论：`PASS`。授权只覆盖前端与直接测试；没有进入临时 SQLite、browser QA、Provider 或 Git 交付；
- RED 命令：`corepack pnpm --dir frontend test -- bookedRailPlanning.test.tsx`；新增独立 V4 synthetic fixture 和 6 项前端契约测试后，结果为 `1 passed / 5 failed`；
- RED 事实：现有前端没有“填写已购铁路车次”显式选择、service number 表单/规范化/首错、V4 response/plan parser 与结果 dispatch，也没有 V4 reload storage pointer；V4 extra/tag/service-number 负向拒绝已 fail closed；
- GREEN/表单：保留 V3“自行填写交通段”为默认，显式选择“填写已购铁路车次”才提交 V4；切换只清空相邻段，V4 固定 rail，service number 在 blur/submit 时 trim + uppercase 并按闭集校验，首个 segment 错误获得焦点；
- GREEN/parser/result：新增独立 V4 typed request/response/plan 和 strict parser；V3/V4 tag drift、额外 duration、非 canonical service number 均拒绝。V4 结果显示车次、由响应发到时间格式化的历时、用户提供/未核验、unknown-validity 与 null 金额，不推导服务端终态或声称车次真实、可售、已出票；
- GREEN/recovery：沿用既有 POST/GET/retry/DELETE URI；V4 使用独立本机 job UUID pointer，reload 经同源 GET 恢复，retry 只接受 attempt 2/3 的 cleared snapshot；V3 pointer 与 legacy/V2/V3 行为保持；
- 验证：V4 定向 `8 passed`；全量前端 `107 passed`；Prettier、ESLint、TypeScript 和 Vite production build 通过；文档检查器测试 `24 passed`，文档检查器通过 17 份必需文档/27 份 Markdown；`git diff --check` 通过；
- 规模/范围：Step 4 共 13 个预期 production/test/fixture 文件，净新增约 802 行；Stack 3 低于 18 文件/1400 净行，任务累计约 34 文件/2687 净行，未触发阈值。Schema/migration/依赖/lockfile diff 为 0，新增外部 URL/凭证/Provider 模式为 0；
- 安全边界：测试完全使用本地 jsdom、注入 HTTP 函数和 synthetic 数据，没有浏览器验收、非 loopback 网络、真实 Provider、秘密、数据库、Schema/migration、依赖/lockfile 或 Git 写入；
- 下一入口：等待用户单独批准 Step 5，仅执行临时 schema v2 SQLite 纵向、loopback desktop/390px browser QA、network/console/accessibility 与独立隐私安全审查；不得自动执行 Git 交付或 Step 6。

## F-004C Step 3：application、Repository/schema v2、同 URI API 与 replan 写前拒绝

- 日期：2026-08-21；结论：`PASS`。用户单独批准 V4 application、typed unions、schema v2 JSON、同 URI API、fingerprint/幂等和 V3/V4 replan 写前拒绝；本次没有修改 Schema/migration、依赖/lockfile、Provider、前端或进入 Step 4；
- RED：新增 booked-rail application、Repository/SQLite 和 API/replan 三个测试模块后，首次定向命令均在 collection 阶段因 `PlanningJobResultV4` 无法从 application Repository 直接 export 导入而失败；错误精确指向本 Step 尚未实现的 typed result/纵向接线，没有旧测试、数据库、网络或环境失败；
- RED 命令：`uv run --project backend pytest backend/tests/application/test_booked_rail_application.py backend/tests/application/test_booked_rail_planning_job_repository.py backend/tests/api/test_booked_rail_trip_plans_api.py -q`，结果 `3 errors during collection`；
- GREEN/application：新增 `PlanningJobResultV4` 和 V4 planning typed path；V4 先被投影为不含 service number 的内部 V3 allowlist 输入复用既有城市规划，再从原始 typed V4 request 在 Agent 边界外确定性重建 V4 rail segment/plan/result。DeepSeek payload 不含 `service_number`、车次值或完整 `intercity_segments`；只使用既有 Amap/QWeather/DeepSeek 城市规划调用，没有城际 Provider port/logical call/HTTP attempt；
- GREEN/数据：`PlanningRequest` / `PlanningPlan` / `PlanningResponse`、application result、memory/SQLite Repository 均增加严格 V4 member；canonical fingerprint 排除 client ID、对 service number trim/case 等价、值变化改变 digest；SQLite 继续使用既有 request/result/plan JSON 列，restart/retry/delete 与 migration 1/2 往返通过；
- GREEN/API/replan：POST/GET/retry/DELETE URI 与公开顶层 envelope 不变，OpenAPI 只增加批准的第四个 V4 request 分支；同 client/body 幂等复用、service number 变化返回既有 409。V3/V4 replan create/decide/execute 在 reserve/lookup/decision/executor 前拒绝，SQLite replan/decision/lineage 写入均为 0；
- 兼容：旧三版本 OpenAPI 断言只同步合法第四分支，未知 tag 继续 422；legacy/V2/V3 exact contracts、fingerprint golden、Repository/API/replan 与既有 application 行为由全量回归覆盖；
- 验证：Step 3 新增定向 `9 passed`；V4 + 相邻 V3 application/Repository/API/contracts `73 passed`；全后端 `1353 passed`；Ruff check 和 mypy 对 142 个 source files 通过；
- 规模/范围：Step 3 修改 15 个预期生产/测试文件，净新增约 740 行，低于 Stack 2 的 18 文件/1400 净行阈值；任务累计低于 50 文件/4000 净行。`schema.py`、`migrations.py`、依赖/lockfile 和 frontend diff 为 0；
- 安全/Git：测试仅使用 fake ports 和临时 schema v2 SQLite；未读取秘密或本地 Provider 配置，未调用真实高德、12306、和风、DeepSeek 或其他外部服务；未 commit、push、创建 PR 或触发远程 CI；
- 下一入口：等待用户单独批准 Step 4；只允许 V4 前端选择、表单、strict parser、来源/未核验/unknown 展示和本机恢复，不得自动进入浏览器验收、Git 交付或 Step 5。

## F-004C Step 2：V4 纯领域与 strict contracts

- 日期：2026-08-21；结论：`PASS`。用户单独批准只以 TDD 实现 V4 纯领域与 strict contracts；本次没有进入 application、Repository、API、SQLite、replan 接线、Provider、前端或 Step 3；
- RED：先新增 `test_booked_rail_rules.py` 与 `test_booked_rail_trip_planning_contracts.py`，首次定向命令在 collection 阶段分别因 `BookedRailIntercitySegment` 和 `TripPlanRequestV4` 无法从直接 export 导入而失败；两项错误均精确指向本 Step 尚未实现的能力，没有旧测试、环境、数据库或外部网络失败；
- RED 命令：`uv run --project backend pytest backend/tests/domain/test_booked_rail_rules.py backend/tests/contracts/test_booked_rail_trip_planning_contracts.py -q`，结果 `2 errors during collection`；
- GREEN：在 `multicity.py` 新增 `BookedRailIntercitySegment`、`BookedRailTrip` 和 strict service number 规范化；在 `trip_planning.py` 新增独立 V4 request/plan/response concrete strict models及直接 export。固定 rail、相邻索引、同日 `+08:00`、派生 transfer date/duration、60/30 缓冲、positive/null fare、user/unknown 来源和票务字段 fail-closed 均由离线测试覆盖；
- shape/来源：request/plan/response tag 均严格为 `4`；`service_number` 按 strict string → trim → uppercase → `^[A-Z0-9]{1,12}$`；duration 只作为 Python 派生属性且不进入 dump；来源只能是既有 user-provided/unknown-validity/未核验闭集，unknown fare 为 null 并阻止 ready；
- 兼容边界：`PlanningRequest` / `PlanningPlan` / `PlanningResponse` 及 application/Repository/API union 接线没有在本 Step 改动，留给 Step 3；因此 legacy/V2/V3 全局 union 与 shape 不受影响；
- 验证：V4 定向 `35 passed`；V4 + 既有多城市/多日相邻回归 `85 passed`；全后端 `1344 passed`；`ruff format --check` 为 139 文件已格式化，`ruff check` 通过，mypy 对 139 个 source files 无问题；
- 规模/范围：本 Step 只修改 4 个批准生产文件并新增 2 个对应测试文件，均为预期文件；生产/测试净新增约 1145 行，低于单 stack 18 文件/1400 净行阈值。累计工作区另含 Step 0–1 已批准文档，未触及 application、Repository、API、SQLite、Schema、migration、依赖、lockfile、Provider 或前端；
- 安全/Git：未创建数据库，未读取秘密或本地 Provider 配置，未调用高德、12306、和风、DeepSeek 或其他外部服务；未 commit、push、创建 PR 或触发远程 CI；
- 下一入口：等待用户单独批准 Step 3；仅允许 application、Repository/schema v2 typed JSON、同 URI API、V4 fingerprint/幂等和 V3/V4 replan 写前拒绝，不得自动进入前端或 Step 4。

## F-004C Step 1：V4 contracts、领域、兼容与交付设计冻结

- 日期：2026-08-21；结论：`PASS`。用户批准只冻结设计；Step 1 已完成，当前停在 Step 2 TDD 待单独批准，没有修改或执行生产/测试实现；
- 事实核对：在分支 `feat/f-004c-booked-rail-domain-contracts`、HEAD/main/origin/main `577bdcbadf2e024022e59e52527d13edb0cbd659` 上只读检查现有 V3 contracts/domain、canonical fingerprint、typed Repository/SQLite hydration、schema/migration 1/2、同 URI API、replan guard 和前端 multi-city parser/form/result 入口；Step 0 未提交文档原样保留；
- contracts/domain：冻结独立 V4 request/plan/response/result、固定 rail 的 `BookedRailIntercitySegmentV4`、规范化 `service_number`、同日 `+08:00`、派生转移日、60/30 缓冲、内部 duration 和 positive/null fare；额外/缺失/跨 tag 字段 fail closed；
- 来源/终态：复用既有 user intercity source shape，固定 unknown-validity 与“用户提供，未核验”；D-013 availability 排除保持，用户段本身不冒充核验也不单独强制 partial，unknown fare 及其他缺口继续阻止 ready；
- 兼容/数据：V4 fingerprint 包含规范化 service number 且排除 client ID；legacy/V2/V3 exact shape/fingerprint/旧记录不变；V4 使用独立 typed union 和 schema v2 既有 JSON 路径，Schema SQL/migration 必须保持不变；
- replan/Agent：V3/V4 create-replan 在 reserve 前以既有 scope error 拒绝，后续 decision/executor/Provider/runtime/lineage/plan write 为 0；service number、完整 segment 和原始城际文本不进入 proposal/repair；城际 logical call/HTTP attempt 为 0；
- UI：现有“自行填写交通段”继续默认生成 V3；只有显式选择“填写已购铁路车次”才生成 V4。切换清空段卡，V4 固定 rail，严格展示车次、未核验、unknown、隐私和无 replan/交易边界；
- 测试/交付：冻结 domain/contracts → application/Repository/API/SQLite → UI/browser/privacy 的 RED→GREEN 矩阵、三层核心文件和受控相邻扩展；18 文件/1400 净行单 stack、50 文件/4000 净行任务阈值保持；
- 文档门禁：`uv run --project backend --frozen python -m unittest scripts.tests.test_check_docs` 为 24 项通过；`uv run --project backend --frozen python scripts/check_docs.py --root .` 通过 17 份必需文档、27 份 Markdown、CI、状态和安全契约；`git diff --check` 通过；
- 范围：累计工作区只修改 13 份批准的当前治理/权威 Markdown；没有源码、测试、fixture、Schema、migration、依赖、lockfile、CI、环境文件、数据库或归档任务卡变化，既有 evidence 条目未改写；
- 安全：未创建数据库，未读取 `.env.local`、秘密或 Provider 配置，未调用高德、12306、和风、DeepSeek 或其他 Provider，未 commit、push、创建 PR 或触发远程 CI；
- 下一入口：等待用户单独批准 Step 2；批准范围只能是 Stack 1 的 V4 纯领域与 contracts TDD，不得自动进入 Repository/API/application/前端或 Step 3。

## F-004C Step 0：任务激活、D-016 与三层交付治理

- 日期：2026-08-21；结论：`PASS`。Step 0 已完成，F-004C 是 roadmap 唯一 `ACTIVE` 任务；当前入口切换为 Step 1 设计冻结待单独批准，没有进入实现；
- 基线：Step 0 开始前 `HEAD == main == origin/main == 577bdcbadf2e024022e59e52527d13edb0cbd659`，工作区干净、没有活动任务或开放 PR；F-004B2 `BLOCKED` 归档任务卡存在；
- Git/PR/CI：F-004B2 documentation-only closure PR #33 已合并，最终 main CI run `32463645980` 为 `success` 且 head SHA 为上述基线；已从干净 main 创建本地 `feat/f-004c-booked-rail-domain-contracts`，HEAD 未增加提交；没有 commit、push、创建 PR 或触发远程 CI；
- 治理：current-task 已写入完整 F-004C 任务卡；roadmap 顺序为 F-004C → F-006 且 F-004B2 保持 `BLOCKED / ARCHIVED`；implementation-plan 已切换为 Step 0–6；D-016、三层 stacked PR、核心文件、受控相邻扩展和规模阈值已建立；
- D-016：独立 V4 只承载用户提供的已购铁路段；`service_number` 规范化且参与 V4 fingerprint，来源固定为 `user_provided / unknown_validity / 用户提供，未核验`；D-016 只替代 D-015 未实现的 V4 Provider union 预留，不改变 F-004B2 阻塞历史；
- 不变量：legacy/V2/V3 exact shape、fingerprint、旧记录和行为不变；SQLite schema 保持 version 2、migration 只有 1/2；V3/V4 replan 写前拒绝；F-004C 城际 Provider logical call 和 HTTP attempt 均为 0；
- 文档门禁：`uv run --project backend --frozen python -m unittest scripts.tests.test_check_docs` 为 `24 passed`；`uv run --project backend --frozen python scripts/check_docs.py --root .` 通过 17 份必需文档、27 份 Markdown、CI、状态和安全契约；`git diff --check` 通过；
- 范围：只修改 README、product-brief、architecture、agent-domain-spec、decisions、current-task、implementation-plan、progress、roadmap 和 evidence 共 10 份当前治理/权威 Markdown；没有修改源码、测试、fixture、Schema、migration、依赖、lockfile、CI、环境文件、数据库或归档任务卡，既有 evidence 条目未改写；
- 安全：未创建数据库，未读取 `.env.local`、秘密或本地 Provider 配置，未调用高德、12306、和风、DeepSeek 或其他 Provider，未注册账号、申请 Key、付费、抓取或逆向；
- 保留事实：F-001 `PARTIAL`、Step 45M `FAIL`、Step 45T `PASS`、unknown 不按 0、混合交通 fallback 仅离线、F-004A/F-004B1/F-005 无真实 Provider UAT、F-004B1 城际 Provider 调用 0、F-005 离线证据不等于真实 UAT，以及 SQLite schema v2/migration 1/2 均保持；
- 下一入口：等待用户单独批准 F-004C Step 1，仅冻结 V4 contracts、领域、兼容、fingerprint、replan、schema v2 和测试设计；不得自动进入 Step 1 或 Step 2。

## F-004B2 documentation-only blocked closure

- 日期：2026-08-21；结论：`BLOCKED / ARCHIVED`。F-004B2 Step 0 已完成、Step 1 Provider/法律 Gate 已正式 `BLOCKED`，Step 2–10 均未执行；本次关闭不把候选 Provider、V4 Provider union 或真实 UAT 表述为已交付能力；
- 基线：closure 开始时 `HEAD == main == origin/main == 96f73d99c04a72e1e697172306d8f33d006419ec`，当前分支为 `docs/f-004b2-blocked-closure`；原 7 个未提交文档已原位保留，没有 stash、reset、丢弃或覆盖；
- 归档：完整任务卡保存为 [F-004B2 BLOCKED archive](../archive/task-cards/F-004B2-real-intercity-provider-blocked.md)，current-task 已恢复为无活动任务；roadmap 保持 F-004B2 `BLOCKED`，候选顺序为 F-004C → F-006；D-015 状态为 `PROVIDER_LEGAL_GATE_BLOCKED / TASK_ARCHIVED`；
- 文档门禁：`uv run --project backend --frozen python -m unittest scripts.tests.test_check_docs` 为 `24 passed`；`uv run --project backend --frozen python scripts/check_docs.py --root .` 通过 17 份必需文档、27 份 Markdown、CI、状态和安全契约；`git diff --check` 通过；
- 任务级一致性审计：以 `96f73d99c04a72e1e697172306d8f33d006419ec...HEAD` 为范围复核 name-status 和 diff；current-task/README/progress/implementation-plan 均声明无活动任务，roadmap 的 ACTIVE 行为 0，F-004B2 在 roadmap/D-015/归档卡中均为 `BLOCKED`，Step 2–10 均保持 `BLOCKED_BY_STEP_1`，归档链接存在，F-004C 与 F-006 都仅为候选；
- 范围：只涉及 README、product-brief、architecture、agent-domain-spec、decisions、current-task、implementation-plan、progress、roadmap、evidence 和新增归档任务卡共 11 份 Markdown；没有源码、测试、fixture、Schema、migration、依赖、lockfile、CI、环境文件或数据库变化；
- 安全：没有读取秘密或本地 Provider 配置，没有创建数据库，没有调用高德、12306、和风、DeepSeek 或其他 Provider；历史 evidence 仅追加本次 Step 0/1/closure 事实，既有条目未改写；
- 保留事实：F-001 `PARTIAL`、Step 45M `FAIL`、Step 45T `PASS`、unknown 不按 0、混合交通 fallback 仅离线、F-004A/F-004B1/F-005 无真实 Provider UAT、F-004B1 城际 Provider 调用 0、F-005 离线证据不等于真实 UAT，以及 SQLite schema v2/migration 1/2 均保持。

## F-004B2 Step 1：高德 Provider 与法律 Gate

- 日期：2026-08-21；结论：`BLOCKED`。用户明确批准只审核其提供的高德官方书面回复，并要求 SQLite 持久化禁止或 rail 字段授权不足时正式阻塞；本审核没有访问回复中的价格链接或任何其他外部资料；
- 已建立事实：回复确认所述非商用个人开发 Web 服务 API 场景原则上符合许可；建议 UI 声明“数据来源于高德地图，仅供参考”；路径规划 App/H5 跳转不强制；仅程序运行期间的内存临时保存允许；私人测试截图原则上允许但建议模糊 POI ID 和具体地址；
- 持久化硬阻塞：回复明确禁止将 API 数据长期存储或持久化到本地 SQLite；D-015 则要求只保存最终选中的规范化 observation、最长随 planning job 保留 30 天。两者直接冲突，且本 Step 不获准改变架构；
- rail 字段硬阻塞：回复只涉及 POI 名称、经纬度、路线距离和预计时间，没有明确授权 Provider 记录 ID、车次、铁路发到站和时间、历时等首版 rail 事实；不得从一般 Web API 许可推定这些字段获准；
- 未建立边界：回复只指向免费配额说明，没有在提交证据中给出产品计费项、数值配额、QPS 或超额价格；也没有固定 endpoint/version、凭证、允许域名、UAT 次数/费用、脱敏、留存或销毁规则；
- Gate 判定：持久化与 rail 字段两项分别都足以阻塞，故当前 Provider 未选定，Step 2–10 全部 `BLOCKED_BY_STEP_1`；允许内存临时保存不能替代获批的 schema v2 planning job 持久化；
- 范围：只更新当前治理与 evidence 文档；未修改源码、测试、fixture、Schema/migration、依赖/lockfile或归档任务卡，未读取秘密/Provider 配置、注册账号、申请 Key、付费、调用 Provider、commit、push、PR 或 CI；
- 恢复入口：补充正式书面授权必须同时覆盖所需 rail 字段和最终 observation 最长 30 天的本地 SQLite 保存边界；替代路径必须另行起草并批准产品/持久化架构变更。不得自动进入 Step 2 或 F-006。

## F-004B2 Step 0：条件式激活、D-015 与交付治理

- 日期：2026-08-21；结论：`PASS`。Step 0 开始前 `main == origin/main == 96f73d99c04a72e1e697172306d8f33d006419ec`，工作区干净、没有活动任务或开放 PR；
- Git/PR/CI：PR #27/#28/#29/#30/#31 已依序 squash merge，归档 PR #32 已合并；最终归档 main CI run `32453988289` 为 `success` 且 head SHA 为 `96f73d99c04a72e1e697172306d8f33d006419ec`。首次只读查询 PR #32 时出现一次 TLS 握手超时，立即重试后取得一致事实；未发生远程写入；
- 治理：F-004B2 已成为 roadmap 唯一 ACTIVE，F-006 保持候选；完整条件式任务卡、Step 0–10、D-015、五层 stacked PR、核心文件、受控相邻扩展和规模阈值已写入当前权威文档；
- Gate：当前没有选定 Provider。高德跨城公交路径规划仅为优先待验证候选；Step 1 只能审核用户提供的正式书面授权、合同、工单回复或官方控制台事实，并必须得出 `PASS` 或 `BLOCKED`。Step 1 未 PASS 前所有实现阻塞；
- 分支：已从上述干净 main 基线创建本地 `feat/f-004b2-intercity-domain-contracts`，HEAD 仍为 `96f73d99c04a72e1e697172306d8f33d006419ec`；未 commit、push、创建 PR 或触发远程 CI；
- 文档门禁：文档检查器单元测试 `24 passed`；`check_docs.py --root .` 通过 17 份必需文档、26 份 Markdown、CI、状态和安全契约检查；`git diff --check` 通过；
- 范围：只修改当前治理与权威文档；未修改源码、测试、fixture、Schema/migration、依赖/lockfile、历史 evidence 或归档任务卡，未创建数据库、读取秘密/Provider 配置、注册账号、申请 Key、付费、抓取/逆向或调用任何 Provider；
- 保留事实：F-001 `PARTIAL`、Step 45M `FAIL`、Step 45T `PASS`、unknown 不按 0、混合交通 fallback 仅离线、F-004A/F-004B1/F-005 无真实 Provider UAT、F-004B1 城际 Provider 调用 0、F-005 离线证据不等于真实 UAT，以及 SQLite schema v2/migration 1/2 均保持；
- 下一动作：等待用户另行批准 F-004B2 Step 1 并提供可审计的正式书面证据；不得自动进入。

## F-005 Step 9：顺序合并、main CI 与归档关闭

- 日期：2026-08-21；结论：`PASS`。PR #27 → #28 → #29 → #30 → #31 已按批准顺序 squash merge；对应 main commits 为 `1534cad13d567bce515f96af75c08f568e484619`、`66445c10b6529d118ccf9346fb92bdc83b94e0b1`、`afc8a45abbe191d266a288406dba72fb8b4466b1`、`472a519ca061e29c8d3b6e395fb0acc2bbe28f0a`、`fddd4e5add5919f1751279de9b833a3192ea6338`；
- stack 处置：#28–#31 在直接前层进入 main 后把 base 改为最新 main；每次均复核 GitHub `CLEAN/MERGEABLE` 与本地 tree diff，依次只含 Stack 2 的 8、Stack 3 的 17、Stack 4 的 7、Stack 5 的 8 个生产/测试/eval 文件及批准状态文档，因此无需创建替代式 clean-restack PR，没有 rebase、amend 或 force-push；
- 逐层 main CI：runs `32451655141`、`32451996154`、`32452323662`、`32452640620`、`32452988076` 全部 `success`；完整功能 main 为 `fddd4e5add5919f1751279de9b833a3192ea6338`；
- 归档：F-005 完整任务卡已移入 `docs/archive/task-cards/F-005-external-service-resilience-freshness-agent-eval.md`，当前任务、计划、roadmap、progress 和文档地图已切换为无活动任务；
- 边界：未修改 Schema/migration、依赖或 lockfile；未读取 `.env.local`、秘密或 Provider 配置，未调用 DeepSeek、高德、和风或城际 Provider。F-001 `PARTIAL`、Step 45M `FAIL`、Step 45T `PASS`、unknown/null、混合交通 fallback 仅离线、F-004A/F-004B1 无真实 Provider UAT 和 F-004B1 城际 Provider 调用 0 均保持。

## F-005 Step 8：五层全量门禁、独立 review 与 stacked PR 交付

- 日期：2026-08-21；结论：`PASS`。用户已接受 Step 7 的 `npx` 偏差及 Step 8 已披露的 Codex CLI 全局插件外连失败偏差；后者没有访问真实 Provider、没有形成 Provider UAT，也没有修改项目数据或扩大交付权限；
- 拓扑修订：用户批准在 `feat/f-005-application-agent-eval` 与 `feat/f-005-ui-delivery` 之间新增 `feat/f-005-agent-eval-integration`，形成五层 stack；新层只承载固定 eval 及其测试，不新增生产/API/Repository/SQLite/Provider/前端能力；
- RED/GREEN：新增测试首次在 collection 因 `evals.f005.application` 不存在失败；最小 GREEN 让 legacy/V2/V3 经过真实 `ProviderPlanningJobExecutor` 与各自 orchestrator，让 F-003 经过真实 `ReplanApplicationService`，并从入口结果观测终态、发布来源、unknown/null、logical call 和 HTTP attempt；
- 防伪边界：case schema 明确拒绝 `published_source_ids` 与 `unknown_amount`，category→scenario 精确矩阵不可重标，安全 case 必须保留 99 次额外调用攻击，fixture 不能抬高代码拥有的预算、关闭攻击或改写期望调用数；统计覆盖全部 capability 与全部 Provider attempt。DeepSeek 使用 synthetic key 与 `httpx.MockTransport`，Amap/QWeather 使用项目 fake，未访问网络或真实 Provider，F-004B1 城际 Provider 调用仍为 0；
- 独立 review 修复：第 3 层新增发布时路线 freshness 复核，legacy/V2/V3 的关键路线若在规划期间过期均以 `failed + plan=None` 拒绝；发布时钟被钳制为不早于任务开始且无效时 fail closed。V3 DeepSeek timeout 与 Amap route auth/schema 等错误保留原 Provider code、attribution、diagnostic/retryable，不再统一改写成 `model_output_invalid` 或可重试 route failure。第 4 层的 F-003 stale/unknown-cost 改变真实 baseline facts，成功结果沿用真实 baseline status；四个 slice 的 normal 与 unknown-validity 使用可区分的显式 synthetic 有效性事实，不虚构生产 TTL；
- 当前验证：真实入口/fixture 防伪/场景矩阵/完整调用预算/freshness 对照/阈值/确定性 eval `26 passed`；从仓库根直接对 eval 子目录运行 mypy 曾因项目包按已安装非 `py.typed` 模块解析产生 11 个 `import-untyped`，不作为权威门禁结论；最终项目统一门禁通过 backend format/lint、strict mypy `139 source files`、backend `1309 passed`、frontend format/lint/typecheck、`99 passed`、build、文档测试 `24 passed` 与文档检查器；
- 本地范围：Stack 1/2/3/4/5 分别为 5/8/17/7/8 个生产测试 eval 文件，净新增 938/1056/1533/1933/597 行；累计 45 文件/6057 净新增行，低于全部阈值。Schema/migration、依赖/lockfile、`.env` 均未变，secret-like 审计唯一命中为 synthetic 测试 key；
- 独立 review：最终五层均为 NO FINDINGS；过程中发现的非法 domain 状态、并发预算超卖、Retry-After 重复 deadline、发布时路线过期、V3 错误投影、eval 自评分/可关闭攻击和状态文档漂移均以对应 RED/GREEN 修复并复审关闭；
- 远程交付：Stack 1 `b66b061` → Stack 2 `c0d571a` → Stack 3 `8b51501` → Stack 4 `5c38431` → Stack 5 feature `89ce7bf` 已普通 push；Draft PR #27/#28/#29/#30/#31 的 base 依次为 main/直接前层，首轮 Windows offline verification runs `32450657207`、`32450661429`、`32450664838`、`32450668170`、`32450671589` 全部 success；
- 边界：未 merge、clean-restack、运行最终 main CI、归档或进入 Step 9；未读取 `.env.local`、秘密或 Provider 配置，未调用真实 Provider。下一动作仅为等待用户单独批准 Step 9。

## F-005 Step 7：临时 SQLite、loopback 浏览器与独立隐私安全审查

- 日期：2026-08-21；结论：`DONE WITH DISCLOSED PROCESS DEVIATION`；临时 schema v2 SQLite、desktop/`390×844` loopback synthetic 浏览器、network/console/accessibility 与独立隐私安全审查均已完成，但首次探测 Playwright CLI 的 `npx --yes @playwright/cli@latest --help` 可能查询 npm registry，违反本 Step 的严格非 loopback 进程边界；该偏差无法追溯撤销，因此不把 Step 7 网络约束写成无条件 `PASS`，进入 Step 8 前须由用户明确接受；
- SQLite 纵向：Provider 配置显式为空，四组 schema v2 API 纵向初始 `30 passed`；冻结 V3 browser fixture 的 `2026-08-21` 在当日变为 UI 的 D+0，新增测试先得到精确 `1 failed`，随后仅在受控 browser 测试支撑中允许显式 `ITA_BROWSER_START_DATE` 平移冻结 0–6 日 ISO 日期，不改变默认 fixture、公开 contract、Repository、Schema 或 migration；最终四组纵向 `31 passed`；
- 浏览器：真实 Edge 经 Vite → FastAPI → 临时 SQLite → synthetic executor 在 `1440×1000` 和 `390×844` 完成 V3 partial、第三日键盘切换、skip link、retry 与 reload 恢复；unknown 金额保持未知而非 0，`provider_timeout` 显示可安全重试，unknown-validity 明示“不代表当前有效”；desktop/mobile 横向 overflow 均为 0，重复 ID、缺失 ARIA 引用和无可访问名称交互控件均为 0；console 共 3 条且 error/warning 均为 0；
- 网络：浏览器审计列出 57 条请求，全部指向 `http://127.0.0.1:5173`，API create/get/retry 均为 loopback；浏览器和产品运行时未请求外部服务，未调用 DeepSeek、高德、和风或城际 Provider。Playwright wrapper 因 Windows `bash.exe` 指向无 `/bin/bash` 的 WSL 不可用，首次 `npx` 探测可能产生的 npm registry 查询作为上述过程偏差永久保留；发现后所有 Playwright CLI 命令均改为 `npx --offline`；
- 持久化与隐私：成功数据库只包含 migration `1/2` 和既有 10 张表；job attempt 为 2、状态 partial、plan version/source record 各 2。对全部 TEXT 列扫描 `diagnostic_code`、Authorization、Bearer、api_key、private_key、raw_response、invalid_output、full_prompt 均为 0；公开 typed `provider_timeout` 仅存在于结果快照。三份精确 `ita-f005-step7-*.sqlite3` 临时文件已移入 Windows 回收站，原路径均不存在且可恢复；
- 独立审查：Codex Security diff scan `c0d1100d-227b-4572-aa5a-769cb0689541`，snapshot digest `d65a569a3e71d3639f40e634b609379d1c9f784f573489f7b4014bba76160fe8`；29 个生产/eval/frontend review item，加上 browser 日期支撑与 SQLite 测试，覆盖 Browser/API、SQLite、Amap/QWeather、attempt runtime、DeepSeek、离线 eval、legacy/V2/V3 投影和测试支撑 8 个信任面，coverage complete、0 candidate、0 finding；TAC advisory 因未登录为 unknown，不作为通过证据；
- 自动化：安全/韧性定向 `365 passed`，SQLite 纵向 `31 passed`；受控两测试文件 Ruff format/check 通过；一次从仓库根目录对两个测试文件直接运行 strict mypy 因包解析方式产生 9 个 `import-untyped/no-any-return` 非权威失败，随后按项目权威入口 `uv run --directory backend --frozen mypy` 重跑并得到 `Success: no issues found in 137 source files`，未把无效调用写成门禁通过；
- 范围：Step 7 仅修改 `backend/tests/browser_multicity_support.py` 与 `backend/tests/api/test_sqlite_multicity_trip_plans_api.py` 两个受控相邻测试文件，`+61/-2`、净新增 59 行、未预期文件 0；加上当前状态/证据文档后，未修改生产源码、Schema/migration、依赖/lockfile。任务累计生产/测试/eval 44 文件、净新增 3710 行，低于全部阈值；
- 交付边界：未读取 `.env.local`、秘密或本地 Provider 配置，未创建真实数据库，未 commit、push、创建 PR、触发远程 CI、merge 或进入 Step 8；本证据仍是 synthetic/offline，不构成真实 Provider/模型 UAT，F-001 `PARTIAL`、Step 45M `FAIL`、Step 45T `PASS`、unknown/null、混合交通 fallback 仅离线、F-004A/F-004B1 无真实 Provider UAT 和 F-004B1 城际 Provider 调用 0 均保持；
- 下一动作：等待用户明确接受上述 `npx` 非 loopback 过程偏差并批准 F-005 Step 8；在此之前不得运行全量交付门禁、commit、push、创建四层 stacked PR 或触发远程 CI。

## F-005 Step 6：同 shape 前端失败、时效与恢复体验

- 日期：2026-08-21；结论：`PASS`；用户批准仅让前端消费 Step 4 已冻结 shape，本次未进入临时 SQLite、浏览器 QA、Schema/migration、依赖、真实 Provider 或交付；
- RED：鉴权配置标题、固定错误优先级、`data_stale` 恢复文案和 unknown-validity 披露新增后，定向 30 项中 4 项按预期失败；原实现仍使用通用标题/数组顺序/通用 retry/“未提供截止时间”；
- GREEN：鉴权显示本机配置问题且无 retry；暂时失败仍由 `retryable && attempt<3` 控制；stale 显示“数据可能已变化/重新获取数据”；unknown-validity 显示“不代表当前有效”且不单独提供 retry；错误排序只改变呈现，不重算 freshness 或终态；
- 兼容：legacy/V2/V3 strict parser、attempt 3、unknown/null、F-003 replan、多城市用户城际来源及既有 URI/JSON key 均保持；
- 验证：定向前端 `30 passed`，前端全量 `99 passed`；Prettier、ESLint、TypeScript、Vite build 通过；不创建 SQLite 的后端 API/contracts `98 passed`；文档检查器、文档测试与 `git diff --check` 在状态同步后通过；
- 范围：本 Step 3 个批准生产组件 + 3 个对应测试，`+290/-60`、净新增 230 行、未预期文件 0；任务累计 42 文件/3651 净新增行，未触发 Stack 4 或任务阈值；
- 安全：未读取 `.env.local`、秘密或 Provider 配置，未访问网络、调用 Provider、创建数据库、启动浏览器，未修改后端生产代码、Schema/migration、依赖/lockfile，未 commit、push、PR、CI 或进入 Step 7；
- 保留事实：F-001 `PARTIAL`、Step 45M `FAIL`、Step 45T `PASS`、unknown 不按 0、混合交通 fallback 仅离线、F-004A/F-004B1 无真实 Provider UAT 和 F-004B1 城际 Provider 调用 0 均保持；
- 下一动作：等待用户明确批准 F-005 Step 7，仅执行临时 SQLite、loopback synthetic desktop/390px、网络/console/accessibility 和独立隐私安全审查。

## F-005 Step 5：Agent 输入最小化、Provider 文本隔离与固定离线 eval

- 日期：2026-08-21；结论：`PASS`；用户批准只实现 proposal/repair 输入最小化、Provider 不可信文本隔离和固定离线 Agent eval，本次未进入前端、Schema/migration、依赖、真实 Provider 或交付；
- RED：新增 repair 安全边界测试后，首次在 collection 因 `PlanRepairBrief` 不存在失败；旧实现仍以 `PlanningContext + invalid_output` 传入 repair，缺口被真实证明；
- repair GREEN：legacy/V2/V3 共用 frozen/slotted `PlanRepairBrief`，只含日期/城市/窗口骨架、允许 location/source 目录和稳定无值诊断；不含原始模型输出、完整 context、自由文本、preferences、hard constraints、Provider observations 或异常文本；
- 文本隔离：generation builder 与 DeepSeek adapter 双层应用 display-label 门禁，拒绝超 120 字、非单行、控制符和提示控制标记；category/kind 只接受项目 token。负向测试证明 unsafe Provider label、`tool_call` category 和原始 invalid output 不进入 model payload；
- eval：`f005-v1` 固定 48 case，legacy/V2/V3/F-003 各 12，每 slice 四类各 3；重复执行两次一致。六维加权分为 `100.0`，提示注入/来源伪造/工具越权/预算超限/假 ready 五类硬门禁失败均为 0；
- 验证：Agent/adapter/ports/eval 定向 `127 passed`；全 backend `1270 passed`；Ruff format `141 files already formatted`、Ruff lint通过、strict mypy `137 source files` 和 eval `4 source files` 通过；文档检查器、文档测试和 `git diff --check` 在状态同步后通过；
- 范围：任务累计生产/测试/eval 36 文件、净新增 3421 行；case JSON 仅做无语义一-case-一行压缩，Stack 3 估算净新增 1706 行，未触发 30 文件/2500 行或任务 90 文件/8000 行阈值；
- 安全：未读取 `.env.local`、秘密或本地 Provider 配置，未访问网络或调用 Provider，未创建数据库，未修改前端、Schema/migration、依赖/lockfile，未 commit、push、PR、CI 或进入 Step 6；
- 保留事实：F-001 `PARTIAL`、Step 45M `FAIL`、Step 45T `PASS`、unknown 不按 0、混合交通 fallback 仅离线、F-004A/F-004B1 无真实 Provider UAT 和 F-004B1 城际 Provider 调用 0 均保持；本 eval 不构成真实 Provider/模型 UAT；
- 下一动作：等待用户明确批准 F-005 Step 6；前端只能消费 Step 4 既有同 shape 语义，不得重算 freshness 或推导服务端终态。

## F-005 Step 4：application runtime、停止顺序与同 shape 后端投影

- 日期：2026-08-21；结论：`PASS`；用户明确批准将显式 attempt runtime 接入 legacy/V2/V3 application 编排，本次未进入 Step 5 Agent eval、前端、Schema/migration、依赖或真实 Provider 调用；
- RED：4 个首批接线测试因 `attempt_runtime`/factory 参数不存在而失败；接线 GREEN 后新增 freshness 纵向测试，首次以“stale weather 仍进入 plan”失败，证明旧投影缺口真实存在；
- runtime：executor 每个 planning attempt 只创建一个 runtime，同一实例覆盖 Amap/QWeather/DeepSeek 与城市/天气/路线调用；Repository/API 终态写入前 close，deadline 前置拒绝不启动 HTTP，取消/异常时城市和路线 peers 均 cancel/drain；
- 调用治理：logical permit 只计一次，HTTP retry 独立计 attempt/Provider/task budget；DeepSeek 仍 0 transport retry。retry 完成后才进入既有 route fallback，Provider-wide failure 和 stale route 不 fallback，F-004B1 城际 Provider 调用仍为 0；
- freshness/shape：stale required route 为 `failed + data_stale + route_source_stale`，stale weather/alert 从上下文与 plan 剔除并 partial，unknown-validity 不提升 V3 ready；未新增 URI、JSON key 或顶层错误码，Repository typed union/SQLite schema v2/migration/F-003 replan 不变；
- 验证：定向 runtime/application `60 passed`；全 backend `1264 passed`；Ruff format `136 files already formatted`、Ruff lint `All checks passed`、strict mypy `Success: no issues found in 136 source files`；文档检查器和 `git diff --check` 在状态同步后通过；
- 范围：任务累计生产/测试 22 文件、净新增 2713 行，低于任务 90 文件/8000 行阈值；Step 4 只修改批准的 Stack 3 核心、直接 export/bootstrap 与对应测试，无未预期文件；
- 安全：未读取 `.env.local`、秘密或本地 Provider 配置，未访问非 loopback/真实 Provider，未创建数据库，未修改前端、Schema/migration、依赖/lockfile，未 commit、push、创建 PR、触发 CI 或进入 Step 5；
- 保留事实：F-001 `PARTIAL`、Step 45M `FAIL`、Step 45T `PASS`、unknown 不按 0、混合交通 fallback 仅离线、F-004A/F-004B1 无真实 Provider UAT 和 F-004B1 城际 Provider 调用 0 均保持；
- 下一动作：等待用户明确批准 F-005 Step 5；不得自动实现 Agent eval、前端或后续交付。

## F-005 Step 3：task-scoped attempt runtime 与 Provider 安全错误输入

- 日期：2026-08-21；结论：`PASS`；用户明确批准实现显式 task-scoped attempt runtime，并让 Amap/QWeather adapter 提供安全错误和 Retry-After 输入，本次未进入 Step 4 application 编排接线；
- RED：新增 `test_provider_attempt_runtime.py` 及 Amap/QWeather 429 测试后，首次定向运行在 collection 阶段因 `ProviderAttemptRuntime` 不存在失败；该失败只指向批准的新 runtime 缺口；
- GREEN：新增显式 runtime，独立持有 attempt 记录、Amap/QWeather/任务额外预算、deadline、active peers 与 closed 状态，复用 Step 2 纯领域 retry schedule/decision；单 attempt timeout、注入式 delay、budget/deadline 拒绝、取消/异常 close、peer cancel/drain 和 closed 后零新调用均由离线测试覆盖；
- adapter 边界：Amap/QWeather 仍各自只做一次 HTTP exchange，没有 sleep/retry；timeout/request/HTTP/Schema 错误输出安全 `ProviderError`，429 的原始 `Retry-After` 只解析为合法 delta/HTTP-date 的 `0..2s` 数值，原始 header/body 不进入结果、记录或持久化；DeepSeek 生产代码未修改且 transport retry=0 回归通过；
- 验证：runtime + Amap/QWeather 定向 `121 passed`；runtime/governance `61 passed`；Provider/DeepSeek/治理/既有编排兼容回归 `378 passed`；domain/contracts `164 passed`；全 backend `136 files already formatted`、Ruff lint 通过、strict mypy `136 source files` 通过；`git diff --check` 通过；
- 范围：本 Step 生产/测试范围为 8 个批准核心或受控相邻文件、净新增 859 行、未预期文件 0；未修改 planning application service、API、Repository、SQLite、前端、Schema/migration、依赖或 lockfile；未创建数据库、读取 `.env.local`/秘密、调用 Provider/非 loopback 服务、commit、push、创建 PR 或触发远程 CI；
- 保留事实：F-001 `PARTIAL`、Step 45M `FAIL`、Step 45T `PASS`、unknown 不按 0、混合交通 fallback 仅离线、F-004A/F-004B1 无真实 Provider UAT 和 F-004B1 城际 Provider 调用 0 均保持；
- 下一动作：等待用户明确批准 F-005 Step 4；不得自动把 runtime 接入 legacy/V2/V3 application 编排，也不得进入 Agent eval、API、Repository、SQLite、前端或后续 stack。

## F-005 Step 2：纯领域 resilience、freshness、retry 与安全诊断

- 日期：2026-08-21；结论：`PASS`；用户明确批准只以 TDD 实现纯领域 `ProviderResult` 安全扩展、resilience/freshness/retry schedule 和诊断决策，本次未进入 Step 3；
- RED：先新增 `test_resilience.py` 和 `ProviderError` Retry-After 测试；首次定向命令在 collection 阶段因 `FactCriticality` 无法从 domain 导入而失败，证明新领域能力尚不存在，未出现环境或旧行为失败；
- GREEN：`ProviderError.retry_after_seconds` 只允许 rate-limit 的有限 `0..2s` 值；其他类别、bool、NaN/Infinity、负数和超界值 fail closed；该字段是内部领域值，没有进入 contracts/JSON；
- schedule/retry：纯 `resilience.py` 锁定 Amap/QWeather 每逻辑调用最多 2 attempts、Provider 额外预算 3/1、任务额外预算 4、attempt timeout 6 秒；DeepSeek generation/repair 为 1 attempt、35 秒、0 transport retry。timeout/server 使用注入 jitter，受控 429 使用 Retry-After+jitter 且封顶 2 秒；attempt/Provider/任务预算、remaining deadline、terminal/cancelled 确定性停止；
- freshness/failure：fresh 继续、unknown-validity 最高 partial；route stale 拒绝且 required 为 failed，weather/alert stale 剔除为 partial，location stale 只可 partial-use；Provider failure 处置闭集为 required→failed、optional→partial，不产生 needs_input/conflict；
- 诊断/安全：8 项 project-owned `StrEnum` 闭集覆盖 attempt timeout、budget/deadline/Retry-After 和四类 stale capability；决策对象 frozen/slotted，不接收自由诊断文本、原始 header/body、Prompt、异常或秘密；
- 自动化门禁：定向 ProviderResult/resilience `108 passed`；完整 domain + contracts + trip planning golden `342 passed`；全 backend `134 files already formatted`、Ruff lint `All checks passed`、strict mypy `Success: no issues found in 134 source files`；文档检查器自身 `24 tests / OK`，项目文档 `17 required / 25 Markdown` 及 CI/status/safety contracts 通过，`git diff --check=0`；unknown/null、freshness inclusive boundary、legacy/V2/V3 exact shape 和 domain dependency boundary 均在该集合中通过；
- 命令更正：一次从仓库根目录运行未带 target 的 mypy 只打印 usage、没有执行检查；随后使用显式 `backend/src backend/tests` 重跑并取得上述 134-file PASS，未把无效命令表述为门禁结果；
- 范围：生产/测试精确为 5 文件、净新增 856 行——`domain/provider_result.py`、新增 `domain/resilience.py`、domain export、现有 ProviderResult 测试和新增 resilience 测试；没有未预期文件，低于 stack/任务阈值；没有 adapter、application、API、Repository、SQLite、前端、fixture、Schema/migration、依赖或 lockfile 修改；
- 安全/Git：未创建数据库，未读取 `.env.local`、秘密或本地 Provider 配置，未调用 DeepSeek、高德、和风、城际 Provider 或其他外部服务；没有 commit、push、PR、merge 或远程 CI；
- 保留事实：F-001 `PARTIAL`、Step 45M `FAIL`、Step 45T `PASS`、unknown 不按 0、混合交通 fallback 仅离线、F-004A/F-004B1 无真实 Provider UAT 和 F-004B1 城际 Provider 调用 0 均保持；
- 下一动作：等待用户明确批准 F-005 Step 3；不得自动实现 Provider attempt runtime、修改 adapter 或进入 Step 4 application 接线。

## F-005 Step 1：失败、时效、韧性、Agent eval 与交付设计冻结

- 日期：2026-08-21；结论：`PASS`；用户明确批准只进入 Step 1，本次只完成可实现设计冻结，没有进入 Step 2 或任何生产/测试实现；
- 失败与 freshness：逐能力冻结城市/住宿/站点/POI、最终采用路线、天气/预警和 DeepSeek 的关键性、retry 耗尽后 failed/partial 处置、Provider failure 不得投影 needs_input/conflict，以及 attempt 评估快照、GET 不按墙钟改写、stale 路线拒绝和 unknown-validity 不提升 ready；
- runtime：冻结纯 domain policy、显式 job-scoped attempt runtime 和单次 HTTP adapter 三层；Amap/QWeather 每逻辑调用最多 2 attempt，高德/和风/任务额外预算 3/1/4，full jitter 0–200ms、受控 Retry-After 最多 2 秒、remaining-deadline 前置拒绝、terminal/cancel 后零新调用和 active peer drain；DeepSeek transport retry 保持 0；
- Agent/eval：冻结 bounded generation context、不含原始输出/完整自由文本/Provider observation 的 `PlanRepairBrief`、Provider 文本隔离，以及 legacy/V2/V3/F-003 各 12 的 48-case 离线集、两次确定性执行、25/20/15/15/10/15 权重、95% 总分和五类 100% 硬门禁；
- API/UI/交付：冻结同 URI/exact shape、既有 `data_stale`/安全 `diagnostic_code`、attempt 3 恢复动作、schema v2 snapshot、Stack 3 后端投影、Stack 4 前端消费，以及四层核心文件和分层测试入口；
- 文档门禁：`uv run --project backend --frozen python -m unittest scripts.tests.test_check_docs` 为 `24 tests / OK`；`uv run --project backend --frozen python scripts/check_docs.py --root .` 通过 `17` 份必需文档、`25` 份 Markdown、CI/status/safety contracts；`git diff --check` 返回 0；
- Git/范围：仍在 `feat/f-005-resilience-domain-contracts`，`HEAD == main == origin/main == c5f07e12abdc37f977ee0f7181a5f2800f015066`；累计 Step 0–1 diff 精确为 13 份批准文档，批准范围外 0、archive 0、源码/测试/Schema/migration/依赖/lockfile 0；
- 安全边界：没有创建数据库，没有读取 `.env.local`、秘密或本地 Provider 配置，没有调用 DeepSeek、高德、和风、城际 Provider 或其他外部服务，没有 commit、push、PR、merge 或远程 CI；
- 保留事实：F-001 `PARTIAL`、Step 45M `FAIL`、Step 45T `PASS`、unknown 不按 0、混合交通 fallback 仅离线、F-004A/F-004B1 无真实 Provider UAT 和 F-004B1 城际 Provider 调用 0 均保持；
- 下一动作：等待用户明确批准 F-005 Step 2；只允许纯领域 TDD，不得自动进入 adapter、application、API、Repository、SQLite、Provider、前端或后续 stack。

## F-005 Step 0：事实复核、任务激活与治理基线

- 日期：2026-08-21；结论：`PASS`；用户明确批准 F-005 全部任务卡决策和 Step 0，本次只执行事实复核、任务激活、当前状态漂移修正与首层本地分支创建；
- Git 基线：修改前 `HEAD == main == origin/main == c5f07e12abdc37f977ee0f7181a5f2800f015066`，工作区干净；GitHub remote main 也指向同一提交；
- GitHub 事实：PR #19/#23/#24/#25/#26 均为 `MERGED`，PR #26 merge commit 为 `c5f07e1`；当前无开放 PR；main CI run `32386260285` 在该提交上 `completed/success`；
- 任务事实：激活前 current-task 明确“当前无活动任务”；激活后 roadmap 恰有一个 ACTIVE 行，F-005 完整任务卡、D-014 和 Step 0–9 已写入当前权威文档，Step 0 为 DONE、Step 1 为 TODO；
- 治理结果：核心文件清单、受控相邻扩展、四层 stacked PR、单 Step/stack/任务规模阈值和真实停止条件已冻结；
- 状态收口：当前权威文档已统一 F-004B1 Step 0–8 完成归档、PR #26 合并、最终 main `c5f07e1` 和最终归档 main CI `32386260285`；没有修改本文件后续历史条目或任何归档任务卡；
- 分支：确认 main 干净后创建本地 `feat/f-005-resilience-domain-contracts`；没有 commit、push、PR、merge 或远程 CI 写入；
- 自动化门禁：文档检查器及其自身测试、`git diff --check`、状态一致性、范围与敏感模式审计均通过；diff 只包含批准的当前治理和权威事实文档；
- 安全边界：未修改源码、测试、fixture、Schema、migration、依赖、lockfile 或数据库；未读取 `.env.local`、秘密或本地 Provider 配置，未调用 DeepSeek、高德、和风天气或城际 Provider；
- 保留事实：F-001 `PARTIAL`、Step 45M `FAIL`、Step 45T `PASS`、unknown 不按 0、混合交通 fallback 仅离线、F-004A/F-004B1 无真实 Provider UAT 和 F-004B1 城际 Provider 调用 0 均保持；
- 下一动作：等待用户明确批准 F-005 Step 1；不得自动进入设计冻结或实现。

## F-004B1 Step 8：clean-restack、依序合并、main CI 与归档

- 日期：2026-08-20；结论：`PASS`；用户明确批准 Step 8，本次完成依序 squash merge、必要 clean-restack、逐层 main CI、归档 PR 准备和任务关闭；
- Stack 1：PR #19 在 CI `32379371761` 成功后合并为 `9f37e4f81f19da42003592fef43f80c01ce5b629`，main CI `32381619737`=`PASS`；
- Stack 2：从最新 main 创建 `feat/f-004b1-multicity-persistence-api-restack`，只 cherry-pick 原第二层三个净提交；本地 backend `1157`、frontend `88`、docs `24` 全量通过；PR #23 CI `32382212012`=`PASS`，合并为 `712fd516358c80f1aa9a46aae3a0d88b2d9248f8`，main CI `32382625338`=`PASS`；原 #20 留下替代说明后关闭；
- Stack 3：从最新 main 创建 `feat/f-004b1-multicity-planning-restack`，只 cherry-pick planning 净提交；本地 backend `1166`、frontend `88`、docs `24` 全量通过；PR #24 CI `32383225699`=`PASS`，合并为 `ec499fb25151955aeca8805771edd2b594fd861d`，main CI `32383721748`=`PASS`；原 #21 留下替代说明后关闭；
- Stack 4：从最新 main 创建 `feat/f-004b1-multicity-ui-delivery-restack`，只 cherry-pick UI/docs 层净提交；本地 backend `1166`、frontend `95`、docs `24` 全量通过；PR #25 CI `32384318796`=`PASS`，合并为 `c1fecb0e5545a25330aa179e7f25decd58c07139`，完整功能 main CI `32384768085`=`PASS`；原 #22 留下替代说明后关闭；
- clean-restack 事实：#23/#24/#25 均以当时最新 `origin/main` 为唯一基线，只移植所属层净提交；未 amend、rebase、force-push、删除远程分支、隐藏失败或改写原 PR 历史；
- GitHub 最终事实：#19/#23/#24/#25 `MERGED`，#20/#21/#22 `CLOSED` 且指向对应替代 PR；Step 7 的首轮失败 runs `32377941830`/`32378099288` 继续保留；
- 归档：新增 [F-004B1 完整任务卡](../archive/task-cards/F-004B1-multicity-domain-user-intercity-offline.md)，roadmap 将 F-004B1 设为 DONE，current-task/implementation-plan/progress/docs README 统一关闭任务；没有改写既有历史 evidence 或旧归档卡；
- 保留边界：F-001 `PARTIAL`、Step 45M `FAIL`、Step 45T `PASS`、unknown、混合交通 fallback 仅离线和 F-004A/F-004B1 无真实 Provider UAT 均保持；
- 安全边界：未读取 `.env.local`、秘密或本地 Provider 配置，未调用 DeepSeek、高德、和风或城际 Provider，未修改业务数据库、Schema/migration、依赖或 lockfile；
- 下一动作：当前没有活动任务；等待用户从 roadmap 选择并批准下一任务卡，不自动进入 F-005、F-004B2 或 F-006。

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
