# F-007 实施计划：高德路径规划 QPS 节流与真实调用稳定性

## 当前状态

- 当前任务：`F-007`，状态 `ACTIVE`；
- 当前 Step：`Step 7 - 本地全量门禁与两层交付`（`ACTIVE`）；
- Step 0–5：`DONE / PASS`；Step 6：`DONE / UAT_NOT_FORMALLY_PASSED / INCONCLUSIVE`；
- Step 5A 已将 `partial` / `unknown_validity` 实际渲染对比度提升至 `5.071:1` 并关闭 finding；用户已批准不再执行新的真实 Provider UAT；
- 基线：`main == origin/main == 905a950fa2483f2e441eb520a20897dcc1daa722`，归档 main CI run `32692800113` success；
- 当前本地分支：`feat/f-007-amap-qps-policy-runtime`，尚无 commit、push、PR 或远程 CI；
- 用户当前 `127.0.0.1:8000` 与 `127.0.0.1:5173` 服务必须保持运行，未经明确批准不得停止或重启。

## Step 0：激活治理与证据基线（DONE / PASS）

唯一目标：复核 Git/PR/CI/服务事实，激活 F-007、D-018、Step 0–8、两层 stack、规模阈值和新增真实验收失败证据。

- 已确认 Step 0 开始前 main、origin/main 与 HEAD 一致，工作区干净，无开放 PR、无活动任务；
- 已确认 2026-08-30 高德路径规划 QPS 证据为新的 `FAIL / AMAP_QPS_EXCEEDED`，不改写历史 UAT；
- 已创建首层本地分支；只修改当前治理与权威文档，没有进入实现或远程交付。

## Step 1：冻结可实现设计（DONE / PASS）

唯一目标：冻结 process-shared limiter 的 policy/runtime 接口、bootstrap 所有权、attempt 时序、deadline/cancel/drain 语义、测试矩阵和两层文件归属。

交付物仅为文档；已冻结以下实现契约：

- 现有 walking/public transit、legacy/V2/V3/V4 route 调用都在 adapter 外统一进入 `ProviderAttemptRuntime.execute(AMAP, CALCULATE_ROUTES, call)`，因此 limiter 不接触路线 mode、坐标、URL 或 Provider 原始内容；
- domain 使用内部 immutable `AttemptPacingPolicy(interval_seconds=0.5)` 和 exact `(AMAP, CALCULATE_ROUTES)` lookup；application 使用独立 `PacedAttemptLimiter`，只持有 policy、monotonic clock、async sleeper、一个 lock 与 `next_start_at`；
- task runtime 可选注入同一 limiter，并以 `latest_start_at=task_started_at+task_timeout-full_attempt_timeout` 申请 slot；production bootstrap 与 runtime 必须使用同一 monotonic clock domain；
- 算法为 `slot_at=max(now,next_start_at)`；`slot_at > latest_start_at` 时零等待拒绝，等号允许；sleep 后重读 clock，按实际 start 更新 `next_start_at=actual_start+0.5`；空闲不积累 token，取消后的已授予 slot 不回收；
- runtime 在进入 limiter 前和 slot 返回后都复核 closed/cancel/deadline/budget；retry extra budget 只在 post-slot reservation lock 下、HTTP start 前预留；顺序固定为 retry/backoff → preflight → slot → postflight/reserve → HTTP；
- task runtime close/异常继续 cancel+drain 等待/active peers，但不能关闭 bootstrap-owned limiter；limiter 无后台 task、无持久化、无跨进程生命周期；
- `build_planning_job_executor()` 在完整 adapter 路径创建一个 limiter，并通过 factory 闭包注入所有 job runtime；configuration-missing 路径不创建；Amap adapter 生产代码不在接线面。

测试矩阵冻结为：exact scope、半开窗口/无 burst、idle 后不攒 token、并发顺序、walking/transit 共线、nonmatching 零等待、initial/retry、backoff→slot、deadline 等号/差值/oversleep、未启动 budget 不消费、waiter/peer cancel-drain、跨 job singleton、MockTransport request-start 时间、route concurrency=2、legacy/V2/V3/V4/F-005/API/Repository/SQLite/前端兼容和默认网络阻断。

## Step 2：纯 limiter TDD（DONE / PASS）

唯一目标：先 RED 后最小 GREEN，实现与 Provider/HTTP adapter 解耦的 paced-slot policy/runtime。

必须验证：同一 monotonic 时间轴、连续 slot 间隔、无 burst、多个 job 共享、公平等待、取消 waiter、不在终态/预算耗尽后排队、等待计入 deadline、完整 attempt timeout 预留。不得接 production bootstrap 或调用网络。

实现结果：新增 exact Amap route `AttemptPacingPolicy(0.5)`、无 token 累积的 `PacedAttemptLimiter`，并让 task-scoped `ProviderAttemptRuntime` 可选注入 limiter；initial/retry、backoff→slot、deadline 等号/shortfall/oversleep、pre/postflight、未启动 retry budget、waiter/peer cancel-drain 和 runtime 独立关闭均由 fake clock 测试锁定。production bootstrap、planning service 与 Amap adapter 均未修改。

验证：RED 为 3 个预期缺失 symbol collection error；GREEN 定向 `102 passed`、相邻 application/provider `257 passed`、后端全量 `1406 passed`；Ruff format/check 通过，strict mypy `150 source files` 无问题。Step 2 为 8 个批准生产/测试文件、净新增 698 行，未预期文件 0，低于 Stack 1 阈值。

## Step 3：attempt runtime 与 bootstrap 接线（DONE / PASS）

唯一目标：让高德 `CALCULATE_ROUTES` 的 walking/public transit 初次 attempt 与 retry 都通过 production bootstrap 持有的单进程共享 limiter。

必须保持：retry/backoff → QPS slot → deadline/terminal/cancel 复核 → HTTP attempt；logical/HTTP attempt budgets、route concurrency=2、180 秒 deadline、其他 Provider/operation 和公开 shape 不变。

实现结果：完整配置的 `build_planning_job_executor()` 在 adapter 完整性 Gate 后创建一个 exact Amap route limiter，并由既有 `attempt_runtime_factory` 闭包注入 legacy/V2/V3/V4 的每个 task runtime；configuration-missing 路径在 limiter 构造前返回零调用 executor。fake clock 观察四 runtime route starts 为 0/0.5/1.0/1.5，Amap POI、QWeather 与 DeepSeek 不推进 limiter 时间线。

验证：RED 为完整配置 runtimes 的 limiter 为 `None`，缺配置零构造已 PASS；GREEN bootstrap exact `2 passed`，bootstrap/四版本/Step 2 集合 `181 passed`，后端全量 `1408 passed`，Ruff 和 strict mypy 通过。Step 3 只修改 2 个批准生产/测试文件、净新增 165 行；累计 10 个生产/测试文件、净新增 863 行，低于两层与任务阈值。

## Step 4：离线稳定性与兼容回归（DONE / PASS）

唯一目标：用 fake clock、MockTransport 与 synthetic fixture 证明 burst、retry、429/5xx/timeout、deadline、cancel/drain 和跨 job 竞争均按 D-018 收口。

必须覆盖 legacy/V2/V3/V4、F-005 resilience/eval、replan 写前拒绝、API/Repository/SQLite typed round-trip 和同 shape 前端消费；所有业务网络必须被阻断。

完成结果：两个并发 planning job 的 walking/public transit 在 route concurrency=2 下共享单一时间线，8 次 starts 精确为 0.5 秒连续槽位；Amap adapter 仅通过 MockTransport 验证 503 与合法 Retry-After 429 的批准重试，生产 adapter 未修改。Step 2/4 矩阵共同覆盖 timeout/5xx/429、不可重试错误、backoff→slot、deadline equality/shortfall/oversleep、terminal/cancel/budget 零新 HTTP、waiter/active peer drain 和 limiter 跨 job 可复用。

验证：Step 4 新增 exact `11 passed`，相关 domain/runtime/bootstrap/executor/multiday/multicity/Amap/F-005 集合 `299 passed`；后端 `1446 passed / 1 deselected`，唯一 deselect 是保持用户 8000/5173 服务运行时无法同时满足的 runner 空闲端口 preflight，runner 其余 `4 passed`；前端 `131 passed`，Prettier/ESLint/TypeScript/build、Ruff 与 strict mypy 均通过。Step 4 只改 3 个批准测试文件、净新增 289 行；累计 12 个生产/测试文件、净新增 1152 行。

## Step 5：本地纵向与独立审查（DONE / PASS）

唯一目标：执行临时 schema v2 SQLite、loopback desktop/390px、network/console/accessibility 和独立隐私安全审查。

不得调用真实 Provider；不得修改 Schema/migration、依赖/lockfile；不得停止或复用用户当前运行服务，必须使用隔离端口或在无法隔离时停止并报告。

执行结果：隔离 18007/15177 与临时 schema-v2 SQLite 完成 V4 POST/GET/retry/reload/DELETE，迁移仍只有 1/2；组合 SQLite 集合 `40 passed`。desktop/390px 均无横向溢出，label/description、live region、44px 按钮、skip link 与删除焦点恢复通过；浏览器 99 条请求只到 `127.0.0.1:15177`，console 0 error/0 warning。独立 Codex Security 覆盖 6 个变更生产文件且 0 finding。

Step 5 原 finding：`partial` 状态章与 `unknown_validity` 普通文本实测约 `4.2:1`，低于 WCAG AA `4.5:1`，因此当时正确阻塞。

Step 5A 关闭：直接测试先记录 RED `4.203700573694173:1`；随后仅将状态专用 token 调整为 `#925d12` 并让两处状态文字共用，实际渲染对比度为 `5.071:1`。前端 `132 passed`，desktop/390px overflow、console、network 和 accessibility 复验通过；用户 8000/5173 服务 PID 未变。Step 6 仍为默认关闭的独立 Gate，未自动进入。

## Step 6：独立真实高德 UAT（DONE / UAT_NOT_FORMALLY_PASSED / INCONCLUSIVE）

唯一目标：按实际证据关闭真实高德 UAT Gate，不把缺少 Provider 侧同期控制台证据的观察表述为 PASS。

收口结论：保留 2026-08-30 `FAIL / AMAP_QPS_EXCEEDED`；2026-08-31 的 0.50–0.52 秒间隔和未出现 `provider_rate_limited` 仅为积极补充证据。因缺少同期高德控制台 QPS/超限记录，正式状态为 `UAT_NOT_FORMALLY_PASSED / INCONCLUSIVE`。用户已批准不再执行新的真实 Provider UAT；本次收口不读取秘密、不调用 Provider、不停止或重启现有服务。

## Step 7：本地全量门禁与两层交付（ACTIVE）

唯一目标：运行统一本地门禁，按两层拓扑 commit、push、创建 stacked PR，完成逐层独立 review 和远程 CI。

不得 merge、运行最终 main CI、归档或关闭任务。必须分别审计文件数、净新增行、Schema/migration、依赖/lockfile、秘密和网络边界。

## Step 8：依序合并与关闭（TODO）

唯一目标：经用户单独批准后依序合并两层 PR，必要时 clean-restack，运行最终 main CI，归档任务卡并关闭 F-007。

合并后必须确认 main==origin/main、工作区干净、无开放 PR、current-task 无活动任务，并保留所有历史 UAT 与 PARTIAL 事实。

## 两层 stacked PR 归属

### Stack 1：`feat/f-007-amap-qps-policy-runtime`

- `domain/resilience.py`、domain export；新增 `application/tooling/rate_limiting.py`；`application/tooling/resilience.py` 与 tooling export；
- domain policy、纯 limiter、task runtime 注入及 fake monotonic clock、paced-slot、并发、取消、deadline 与预算测试；
- 不含 production bootstrap 或 adapter 接线。

### Stack 2：`feat/f-007-amap-qps-integration-delivery`

- `bootstrap.py` 创建单实例并由 factory 注入；`test_bootstrap.py` 验证完整/缺配置所有权；
- provider executor、multiday/multicity 与 Amap adapter MockTransport 回归，adapter 生产文件默认不修改；
- legacy/V2/V3/V4、F-005、API/Repository/SQLite/前端同 shape 回归；
- Step 5/6 验收支撑与当前状态/evidence 文档。

## 核心文件与受控相邻扩展

- 核心：`domain/resilience.py`、新 `application/tooling/rate_limiting.py`、`application/tooling/resilience.py`、direct exports、`bootstrap.py` 及其直接测试；
- 受控扩展：直接 export/protocol/helper、MockTransport/fake clock、Amap route 的直接 wiring、对应兼容回归和当前治理文档；
- Amap adapter 生产文件不在批准清单；若必须修改则停止并重新批准；
- 未在 Step 1 冻结的生产文件一律视为未预期文件；单 Step 超过 4 个时停止。

## 规模与停止治理

- Stack 1：最多 12 文件、净新增 1000 行；
- Stack 2：最多 18 文件、净新增 1400 行；
- 任务累计：最多 30 文件、净新增 2200 行；
- 触发任一阈值，或需要公开 API、Schema/migration、依赖/lockfile、新 Provider、账号/配额修改、跨进程协调、数据留存或隐私边界变化时停止并重新批准。

## 跨 Step 不变量

- 不保存或披露 Key、完整 URL、坐标、原始 Provider 响应/错误 body 或 infocode；limiter 状态不持久化；
- 默认测试/CI 阻断非 loopback；F-007 不再执行新的真实 Provider UAT；
- F-001 `PARTIAL`、Step 45M `FAIL`、Step 45T `PASS`、unknown/null、混合交通 fallback 仅离线、F-004B2 `BLOCKED / ARCHIVED`、schema v2/migration 1/2 均保持；
- F-006 `LOCAL_ACCEPTANCE_PASS` 与 F-007 `FAIL / AMAP_QPS_EXCEEDED` 并存，项目真实 Provider 就绪继续为 `PARTIAL`。
