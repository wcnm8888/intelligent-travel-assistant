# 当前任务

## F-007：高德路径规划 QPS 节流与真实调用稳定性

- 状态：`ACTIVE`
- 当前 Step：`Step 7 - 本地全量门禁与两层交付`（`ACTIVE`）
- Step 0–5：`DONE / PASS`；Step 6：`DONE / UAT_NOT_FORMALLY_PASSED / INCONCLUSIVE`
- 基线：`main == origin/main == 905a950fa2483f2e441eb520a20897dcc1daa722`；归档 main CI run `32692800113` success；无开放 PR；Step 0 开始前工作区干净
- 当前分支：`feat/f-007-amap-qps-policy-runtime`；Step 7 开始时尚无 F-007 commit、push、PR 或远程 CI
- 服务保护：Step 5 完成后 `127.0.0.1:8000`（PID 52516）与 `127.0.0.1:5173`（PID 77692）仍健康运行，期间未停止或重启

## 问题与证据

- 2026-08-30 真实本地验收中，高德控制台显示步行路径规划 2.0 的 QPS 限制为 3、最高 QPS 为 6、超限 3 次；同期本地任务安全终态包含 `provider_rate_limited`、`route_primary_unavailable` 和 `data_missing`；
- 本次结论记为新的 `FAIL / AMAP_QPS_EXCEEDED`，不覆盖 Step 45M `FAIL` 或 Step 45T `PASS`，也不改写 F-006 `LOCAL_ACCEPTANCE_PASS`；
- 月调用量证据未显示总额度耗尽；当前修复对象是进程内路径规划 attempt 的节流与启动顺序，不是购买配额或修改高德账号。
- 2026-08-31 观察到的 0.50–0.52 秒间隔以及未出现 `provider_rate_limited` 仅作为积极补充证据；由于缺少同期高德控制台 QPS/超限记录，Step 6 不得记为 PASS，正式结论为 `UAT_NOT_FORMALLY_PASSED / INCONCLUSIVE`。

## 唯一目标

在不改变产品、Provider、公开 API、数据模型或调用预算的前提下，为 `Provider.AMAP + ProviderOperation.CALCULATE_ROUTES` 建立单进程共享、无突发、可取消且受总 deadline 约束的 paced-slot limiter，使 walking 与 public transit 的初次 attempt 和 retry 合计最多启动 2 次/秒。

## 已批准决策（D-018）

1. limiter 只覆盖高德路径规划，walking 与 public transit 共用；不扩大到其他 Provider 或 operation；
2. 固定 0.5 秒 slot，最多 2 HTTP attempts/秒；使用 monotonic clock、无 burst，窗口按半开区间计算；
3. limiter 在 production bootstrap 中单进程共享，跨 planning job/runtime 共用；不使用模块全局、`contextvars`、SQLite、Redis 或跨进程协调；
4. 初次 attempt 与 retry 都经过同一 limiter；顺序固定为 retry/backoff → QPS slot → deadline/terminal/cancel 复核 → HTTP attempt；
5. limiter wait 计入既有总 deadline；只有 `remaining >= wait + 完整 attempt timeout` 时才可启动；终态、取消、deadline 或预算耗尽后不得等待或启动，waiter 与 active peer 必须 cancel/drain；
6. 保持逻辑调用预算、HTTP attempt 预算、`route concurrency=2` 和最大 180 秒 deadline；
7. 保持现有 URI、公开 JSON shape 和错误码；复用 `provider_rate_limited`、timeout/deadline 与安全 diagnostic；
8. 不保存 Key、完整 URL、坐标、原始响应、原始错误 body 或高德 infocode；limiter 状态不进入 SQLite；
9. 默认测试与 CI 阻断非 loopback 网络；真实高德 UAT 仅允许在独立、默认关闭且另行批准的 Step 6 执行。

## Step 1 冻结设计

### 现有接线事实

- legacy/V2 与 V3/V4 的路线调用都先取得既有 `ToolCallGovernor` logical-call permit，再进入 `ProviderAttemptRuntime.execute(provider=AMAP, operation=CALCULATE_ROUTES, call=...)`；
- walking 与 public transit 只在 `RouteCalculationRequest.mode` 不同，在 attempt runtime 层使用相同 Provider/operation，因此共享 limiter 不需要看到路线模式、坐标或 URL；
- 单城市/多日 route batch 与多城市 route semaphore 均保持并发 2；limiter 只控制 HTTP attempt 的开始时刻，不替代 logical-call governor、route semaphore 或 attempt budget；
- `ProviderAttemptRuntime` 仍按 planning job/task 创建并负责 deadline、retry budget、terminal/cancel 与 peer drain；process-shared limiter 是独立长生命周期协作者，不随单个 runtime `close()` 关闭。

### 冻结的 policy 与接口

- domain 新增内部 immutable `AttemptPacingPolicy(interval_seconds=0.5)`，只由 `attempt_pacing_policy_for(Provider.AMAP, CALCULATE_ROUTES)` 返回；其他组合返回 `None`，不改变 retry schedule；
- application 新增窄 `PacedAttemptLimiter`，构造参数仅为 policy、monotonic clock 和 async sleeper；内部只有一个 `asyncio.Lock` 与 `next_start_at`，不得保存请求数据或形成公开 API；
- runtime 通过可选的内部 `attempt_limiter` 协作者调用 `acquire(provider, operation, latest_start_at)`；`latest_start_at = task_started_at + task_timeout - full_attempt_timeout`，runtime 与 limiter 必须使用 bootstrap 注入的同一 monotonic clock domain；
- acquire 只返回“已获得 slot”或“deadline 不足”，取消继续传播 `CancelledError`；不得新增公开错误码、JSON key、持久化状态或日志 payload；
- non-matching Provider/operation 不排队、不睡眠，保持现有行为；matching scope 不区分 walking/public transit。

### 冻结的 paced-slot 算法

1. runtime 在进入 limiter 前复核 closed/current-task cancellation、remaining time 和既有 retry budget；已耗尽时不排队；
2. limiter 在单一 lock 内读取 monotonic `now`，计算 `slot_at=max(now,next_start_at)`；空闲时间不累积 token；
3. 若 `slot_at > latest_start_at`，立即拒绝且不 sleep、不改变 `next_start_at`；等号允许启动，对应 `remaining >= wait + full attempt timeout`；
4. 若需等待，则在 lock 内 sleep 到 slot；醒来后重读 monotonic clock，回拨/非有限值 fail closed，oversleep 使用实际 `now`；
5. 获准时先将 `next_start_at=actual_start_at+0.5` 再返回；任务在返回后取消也视为保守消耗该 slot，禁止补发 burst；
6. runtime 返回后、HTTP 前在 reservation lock 下再次复核 closed/cancel/deadline/provider+task retry budget；retry 只在此时预留 extra attempt，随后才递增 attempts-started 并调用 HTTP；
7. 任一 HTTP attempt 的实际 start timestamps 必须满足相邻间隔 `>=0.5s`；任意半开窗口 `[t,t+1.0)` 最多 2 次；
8. retry 固定先完成既有 backoff，再排 QPS slot；初次 attempt 跳过 backoff但同样排 slot。

### 取消、关闭与 peer drain

- 等待 lock、slot sleep 和 active HTTP 都是现有 runtime active task 的可取消 await；`close()`/异常继续取消并 `gather(..., return_exceptions=True)` drain peers；
- 取消单个 task-scoped runtime 不关闭 process-shared limiter，也不影响其他 job 已排队 waiter；被取消 waiter 不启动 HTTP；
- limiter 自身不创建后台 task、不持有 active HTTP、不提供跨进程 close；进程生命周期结束即释放；
- post-slot 复核失败不得启动或消费 retry attempt budget；已保守消耗的时间 slot 不回收。

### production bootstrap 所有权

- `build_planning_job_executor()` 在确认必要 adapters 完整后创建恰好一个 limiter，并由 `attempt_runtime_factory` 闭包注入每个新 `ProviderAttemptRuntime`；
- configuration-missing executor 不创建 limiter；测试可显式不注入，以保持既有 isolated runtime 默认行为；
- 禁止 module singleton、`contextvars`、SQLite/Redis、跨 worker 协调和 adapter 内部 limiter；不得修改 Amap adapter 请求/解析实现。

### 离线测试矩阵

- policy：仅 Amap route 命中；0.5 秒值、非法 policy/clock fail closed；
- limiter：首个立即、后续 0.5 秒；任意半开 1 秒窗口最多 2；长时间空闲后无 token burst；并发 waiter 按 lock 到达顺序推进且无 starvation；
- scope：walking/public transit 共享同一时间线；Amap geocode/POI、QWeather、DeepSeek 零额外等待；
- runtime：initial/retry 都过 limiter，retry backoff 先于 slot；deadline 等号允许、差一个最小量拒绝；queue wait/oversleep 计入 deadline；slot 拒绝或 post-slot 失败不消费 retry budget；
- cancellation：排队 waiter 取消后零 HTTP；runtime close/异常 cancel+drain peers；一个 runtime 关闭后其他 job 继续使用 limiter；terminal 后零新调用；
- integration：两个独立 planning jobs 共享 bootstrap limiter；route concurrency 仍为 2，但 MockTransport 观察到的真实 request starts 间隔至少 0.5 秒；初次+retry 合并计数；
- compatibility：legacy/V2/V3/V4、F-005 48-case eval、API/Repository/SQLite/错误投影 exact regression；所有测试使用 fake clock/MockTransport 并阻断非 loopback 网络。

## Step 5/5A 执行证据与 finding 关闭

- 隔离环境：只在 `127.0.0.1:18007` / `127.0.0.1:15177` 启动验收后端/前端，使用 E 盘临时 schema-v2 SQLite；验收结束后只关闭自有隔离进程，用户 8000/5173 服务 PID 与 HTTP 200 状态保持不变；
- SQLite 纵向：V4 synthetic 通过 POST → `partial` → retry（attempt 2）→ reload 恢复 → DELETE；SQLite `schema_migrations=[1,2]`，删除后 `planning_jobs=0`。V2/V3/V4 与组合 journey 的临时 SQLite 集合 `40 passed`；
- 浏览器：desktop 1440×1000 与 390×844 均无横向溢出；表单 label/description 引用、live region、44px 可操作按钮、skip-link 键盘入口、删除确认/取消焦点恢复通过；console 为 0 error / 0 warning；99 条浏览器请求的唯一 authority 为 `127.0.0.1:15177`，后端只接收 loopback；
- 隐私安全：Codex Security diff scan `d34206c0-41f4-481a-8282-b00115238d76` 完整覆盖 6 个变更生产文件，结果 0 finding；未读取秘密、调用 Provider、写入 limiter 状态、修改公开 API 或扩大 SQLite 内容。可选 TAC connector 未登录，作为工具可见性限制保留；
- 原 accessibility finding：Step 5 的 `partial` 状态章与 `unknown_validity` 文本使用 `rgb(155,103,22)`，实测普通文本对比度约 `4.2:1`，低于 WCAG AA `4.5:1`；问号图标作为非文本标识满足 3:1，但不能替代文字合规；
- Step 5A 修正：新增直接 CSS 对比度门禁，RED 精确记录 `4.203700573694173:1`；最小 GREEN 仅将 `--status-partial` 调整为 `#925d12`，并让 `unknown_validity` 复用该状态专用 token，全局 `--amber`、背景、布局、公开 API、状态和交互均未改变；
- Step 5A 验证：直接门禁与前端全量 `13 files / 132 tests` 通过；隔离 18007/15177 的 desktop 1440×1000 与 390×844 实际渲染均为 `5.071:1`，两种视口均无横向溢出，390px 可见按钮小于 44px、broken descriptions、unlabeled controls 均为 0，console 0 error/0 warning；28 条浏览器请求全部为 `127.0.0.1:15177`；
- Step 5A 服务/范围：验收后只关闭隔离进程，用户 8000/PID 52516 与 5173/PID 77692 仍 HTTP 200；只修改 `frontend/src/styles.css`、直接对比度测试和当前状态/evidence 文档，未读取秘密、调用 Provider、修改 Schema/migration、依赖/lockfile 或执行 Git 交付；
- 规模：Step 5A 为 2 个批准生产/测试文件、净新增 58 行；F-007 累计 14 个生产/测试文件、净新增 1210 行，未触发任一 stack 或任务停止阈值；
- 过程说明：首次 V2 探索使用了与固定 synthetic 结果不一致的手工请求，Repository 以 `result_request_mismatch` fail closed；未产生 Provider 调用，也未作为通过证据。随后使用 V4 canonical synthetic 请求完成浏览器纵向，并由 40 项自动化 SQLite 矩阵覆盖 V2；
- 结论：Step 5A 已关闭唯一 accessibility finding，Step 5 状态为 `DONE / PASS`。

## Step 6 收口结论

- 用户已明确批准不再执行新的真实 Provider UAT；本次收口没有读取秘密、调用真实 Provider或停止/重启现有服务；
- 2026-08-30 `FAIL / AMAP_QPS_EXCEEDED` 保持有效，不被后续离线门禁或补充观察覆盖；
- 2026-08-31 的 0.50–0.52 秒间隔和未出现 `provider_rate_limited` 是积极补充证据，但没有同期高德控制台 QPS/超限记录，不能证明 Provider 侧峰值符合边界；
- Step 6 最终状态为 `DONE / UAT_NOT_FORMALLY_PASSED / INCONCLUSIVE`，不得表述为 QPS PASS；当前已进入用户批准的 Step 7。

## Step 4 完成证据

- 两个并发单城市 planning job 分别使用 walking/public transit，在 route concurrency=2 不变时共用同一 limiter；8 次 route attempt starts 为 `0.0/0.5/1.0/1.5/2.0/2.5/3.0/3.5`，相邻间隔不少于 0.5 秒，任意半开 1 秒窗口最多 2 次；
- Amap adapter 生产代码未改；MockTransport 对 walking 返回一次 503、对 transit 返回一次带合法 Retry-After 的 429，initial/retry 共用时间线并各只额外尝试一次；timeout/server/受控 429 可重试，auth/schema/empty/unknown/无合法 Retry-After 不重试；
- Step 2 既有 fake-clock 回归继续覆盖 backoff→slot、deadline 等号/shortfall/oversleep、terminal/cancel/budget 后零新 HTTP、waiter/active peer cancel-drain 和共享 limiter 可继续使用；
- F-005 48-case eval、legacy/V2/V3/V4、replan、API、Repository/SQLite typed round-trip、公开错误 shape 与前端同 shape 消费由全量离线门禁保持；
- 相关集合 `299 passed`；后端 `1446 passed / 1 deselected`，唯一 deselect 是用户要求保持运行的 8000/5173 与 F-006 runner 空闲端口 preflight 的已知互斥，runner 其余 `4 passed`；前端 `131 passed` 及静态/build 门禁通过；
- Step 4 只修改 3 个批准测试文件，净新增 289 行；任务累计 12 个生产/测试文件、净新增 1152 行，未触发规模阈值；未修改 Step 2/3 生产实现、Provider adapter、API、Repository、SQLite、前端、Schema/migration、依赖或 lockfile。

## Step 地图

| Step | 唯一可验证目标 | 状态 |
| --- | --- | --- |
| Step 0 | 复核基线并激活任务、D-018、证据、治理和首层本地分支 | DONE |
| Step 1 | 冻结 limiter policy/runtime、接线点、时序、测试矩阵和两层文件归属 | DONE |
| Step 2 | 以 TDD 实现纯 paced-slot policy/runtime，不接 production bootstrap | DONE |
| Step 3 | 将共享 limiter 接入高德 route attempt runtime 与 production bootstrap | DONE |
| Step 4 | 用 fake clock/MockTransport 完成 burst、retry、deadline、cancel/drain 和兼容回归 | DONE |
| Step 5 | 执行临时 SQLite、loopback 浏览器、network/console/accessibility 与独立隐私安全审查 | DONE |
| Step 6 | 按实际证据关闭真实高德 UAT Gate；缺少同期控制台证据时不得记为 PASS | DONE |
| Step 7 | 运行本地全量门禁并完成两层 commit/push/PR、独立 review 与逐层远程 CI，不 merge | ACTIVE |
| Step 8 | 经单独批准后依序合并、必要 clean-restack、最终 main CI、归档与关闭 | TODO |

## 两层 stacked PR

1. `feat/f-007-amap-qps-policy-runtime`
2. `feat/f-007-amap-qps-integration-delivery`

Stack 2 以 Stack 1 为父层；不得提前把后层实现混入前层。Step 7 前不得执行 Git 交付，Step 8 前不得 merge 或归档。

## 核心文件与受控相邻扩展

### Stack 1 核心文件

- `backend/src/intelligent_travel_assistant/domain/resilience.py` 与 `domain/__init__.py`；
- 新增 `backend/src/intelligent_travel_assistant/application/tooling/rate_limiting.py`；
- `backend/src/intelligent_travel_assistant/application/tooling/resilience.py` 与 `application/tooling/__init__.py`；
- `backend/tests/domain/test_resilience.py`、新增 `backend/tests/application/test_provider_attempt_rate_limiter.py`、`backend/tests/application/test_provider_attempt_runtime.py`。

### Stack 2 核心文件

- `backend/src/intelligent_travel_assistant/bootstrap.py` 与 `backend/tests/test_bootstrap.py`；
- `backend/tests/application/test_provider_planning_job_executor.py`、`test_multiday_provider_planning_job_executor.py`、`test_multicity_provider_planning.py`；
- `backend/tests/adapters/test_amap_route_adapter.py` 仅作不改 adapter 行为的 MockTransport 回归，默认不修改 adapter 生产文件；
- legacy/V2/V3/V4、F-005 resilience/eval、API/Repository/SQLite 与前端同 shape 回归；
- 当前状态与 evidence 文档。

受控相邻扩展只允许直接 export、factory/wiring、typed protocol/helper、MockTransport/fake clock、同层回归和当前状态文档。高德 adapter 生产文件不在冻结清单；若实现证明必须修改，立即停止并重新批准，不得借机改变请求内容、解析、公开 shape 或 Provider 范围。

## 规模治理

- 单 Step 超过 4 个未预期生产/测试文件：停止并重新拆分；
- Stack 1 超过 12 个文件或净新增 1000 行：停止并重新拆分；
- Stack 2 超过 18 个文件或净新增 1400 行：停止并重新拆分；
- 任务累计超过 30 个文件或净新增 2200 行：停止并重新拆分。

## 验收标准

- fake monotonic clock 证明同一进程所有 job 的高德 route attempt 启动间隔不少于 0.5 秒，且无启动 burst；
- 初次 attempt/retry 同门禁，顺序、remaining-time 判定、terminal/cancel/budget/deadline 停止与 peer drain 可复现；
- logical/attempt budget、concurrency=2、180 秒 deadline、legacy/V2/V3/V4、F-005 resilience/eval、API/Repository/SQLite 和公开错误 shape 不变；
- 默认测试/CI 无非 loopback 网络；隐私、Schema v2、migration 1/2、依赖与 lockfile 边界不变；
- Step 6 若获批，真实高德 UAT 单独记录，不能覆盖任何历史 UAT 或以离线证据替代。

## 停止条件与非目标

- 需要修改公开 API、Schema/migration、依赖/lockfile、Provider/account/key/QPS/配额/计费或数据留存边界时停止；
- 需要跨进程协调、Redis、分布式限流、生产 SLO、后台调度或新 Provider 时停止；
- 发现 limiter 不能在既有 attempt/deadline/cancel 模型内实现，或规模阈值触发时停止；
- 不再为 F-007 执行新的真实 Provider UAT；不得读取秘密或执行真实 Provider 调用；
- 不停止或重启用户当前 8000/5173 服务，不创建数据库，不改写历史 evidence 或归档任务卡。

## 保留事实

- F-001 产品状态为 `PARTIAL`，Step 45M `FAIL`、Step 45T `PASS`；unknown 不按 0；混合交通 fallback 只有离线证据；
- F-004A/F-004B1/F-004C/F-005/F-006 没有新增真实 Provider UAT；F-004B1/F-004C 城际 Provider 调用为 0；
- F-004B2 保持 `BLOCKED / ARCHIVED`；SQLite schema version 2，migration 只有 1/2；
- F-006 `LOCAL_ACCEPTANCE_PASS` 不因本次真实 Provider QPS `FAIL` 被改写；项目真实 Provider 就绪继续为 `PARTIAL`。
