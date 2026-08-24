# 当前任务：F-006 MVP 体验收口与本地验收

## 任务状态

- 任务：`F-006 MVP 体验收口与本地验收`
- 状态：`ACTIVE`
- 当前 Step：`Step 8 - 合并、最终 CI 与归档（TODO / 待单独批准）`
- 批准入口：用户已批准 F-006 推荐决策、D-017 和 Step 0–7；Step 8 仍须单独批准
- 基线：`main == origin/main == b99d5fc4c89b0f25ec89e4e12cd1755a7c3be46f`
- 最近归档：F-004C Step 0–6 `DELIVERED / ARCHIVED`；归档 PR #37、main CI run `32486428083` success
- 阻塞保留：F-004B2 `BLOCKED / ARCHIVED`

## 用户价值与问题定义

F-006 只收口现有本地 MVP 的完整使用体验、恢复、本地运行和离线验收。用户应能用产品语言选择单城市、多城市手工交通段或已购铁路段，得到一致的处理中与终态体验，在刷新、重启、失败和删除场景中有明确恢复动作，并能通过一个安全的本地入口启动和停止应用。

Step 2 已关闭无凭证/Provider 组合不完整时 job 滞留 `draft` 的缺口，Step 4 已关闭全版本本机恢复和单任务删除缺口，Step 5 已交付安全 PowerShell 本地运行入口。Step 6 又以临时 schema v2 SQLite、14 个组合 journey、loopback desktop/390px、干净检出启动和独立安全扫描关闭了本地验收缺口。Step 7 已完成本地全量门禁、四层精确提交、push、stacked Draft PR、独立 review、findings 关闭和逐层远程 CI；Step 8 未获批准，不得 merge、运行最终 main CI 或归档。

## 已批准决策（D-017 摘要）

### 产品与状态

- F-006 不扩大产品、Provider、API 或数据范围；完成状态固定为 `DELIVERED / LOCAL_ACCEPTANCE_PASS / ARCHIVED`，项目真实 Provider 就绪仍为 `PARTIAL`；
- F-001 保持 `PARTIAL`，Step 45M `FAIL`、Step 45T `PASS`、unknown 不按 0 和混合交通 fallback 仅离线证据保持；
- 用户只看到“单城市”“多城市·自行填写交通段”“多城市·填写已购铁路车次”，不显示 legacy/V2/V3/V4；单城市 2 日/多日仍由内部规则选择 legacy/V2；
- 只做局部 UX 收口，统一状态、结果摘要、预算、来源、冲突和恢复动作层级；允许少量语义 tokens 和共享组件，不做设计系统重写或品牌重塑。

### API、运行与恢复

- 现有 POST/GET/retry/DELETE 和 replan URI、公开顶层 shape、错误码、strict contracts、fingerprint 与旧记录行为不变；不新增 Provider readiness 健康字段、URI 或公开 JSON key；
- 无凭证或 Provider 组合不完整时复用 `configuration_missing`，job 必须安全进入 `failed`，不得无限停留 `draft`，且 Provider 调用为 0；
- 使用统一“上次本机任务”UUID pointer 覆盖 legacy/V2/V3/V4，并兼容旧 V3/V4 pointer；localStorage 只保存 UUID。job 不存在或已过期时清除 pointer，不显示缓存结果；
- 复用既有 DELETE，只允许删除当前终态或已恢复任务；不实现历史列表、清空数据库或运行中取消 API；
- SQLite schema 保持 version 2，migration 只有 1/2，30 天生命周期和级联删除不变；V3/V4 replan 继续全链路写前拒绝。

### 安全、验收与真实调用

- V4 interests-only preferences、Agent bounded allowlist、票务个人信息禁令及 `user_provided / unknown_validity / 用户提供，未核验` 保持；
- F-004B2 保持 `BLOCKED / ARCHIVED`；不恢复真实城际 Provider；F-004B1/F-004C 城际 logical call 和 HTTP attempt 均为 0；
- 新增安全 PowerShell 本地运行入口，覆盖固定版本、端口冲突、loopback、健康等待、SQLite 错误和 Ctrl+C 精确子进程清理；
- synthetic 只用于测试/验收，不作为产品模式；保留 F-005 固定 48-case eval，另建 F-006 组合式离线 journey cases；
- 核心验收不执行真实 Provider UAT。任何 live 调用必须成为独立、默认关闭且另行批准的 Gate；
- 干净检出安装验收仅在后续获批 Step 中允许访问项目已配置的软件包仓库，且仅限依赖缓存缺失；不得访问业务 Provider。

### UX 与可访问性

- desktop/390px 覆盖键盘、焦点恢复、label/description/error 关联、live region、44px 触控、颜色对比和零横向溢出；
- `styles.css` 只允许有限收口；净新增超过 600 行、替换约 30% 以上现有样式或需要 UI 框架/路由器/新依赖时停止并重新批准。

## Step 1 可实现设计冻结

### 无配置安全终态

- “无凭证/Provider 组合不完整”指三组必要 adapter 没有全部装配成功；全空配置或某个必要 adapter 缺失时，production bootstrap 必须装配一个安全 unavailable executor，而不是向 API 注入 `None`。单个 Provider 的部分字段、非法 URL 或其他现有配置校验错误仍在启动阶段 fail closed，不转换为 planning job；
- 新建 legacy/V2/V3/V4 job 保持既有 POST `202` 和 GET shape。安全 executor 只执行 `draft → normalizing → failed`，写入对应版本的 typed result：`status=failed`、`plan=null`、`errors=[configuration_missing]`、`retryable=false`、固定安全 message“本机服务配置不完整，无法生成旅行计划。”和 `diagnostic_code=required_provider_configuration_missing`；legacy 的 `resolved_destination=null`，V3/V4 的 `resolved_destinations=[]`，violations/warnings/uncertainties/sources 均为空；
- 该路径不得创建调用 governor 或 attempt runtime，不得调用 Amap/QWeather/DeepSeek，不得进入 proposal/repair；logical call 和 HTTP attempt 都是 0。配置修复后用户须重启本地服务并新建任务，不显示 retry；
- retry URI、幂等 reservation 和已存在记录语义保持。`created=false` 不重新调度；历史 `draft` 不做启动扫描、回填或迁移，恢复后只按权威状态展示，不能伪造失败结果；
- production 组合根必须总能提供 live executor 或安全 unavailable executor；API 端口的 optional executor 仅为既有隔离测试/依赖注入兼容保留，不新增公开 readiness 字段或即时 HTTP 配置错误。

### 三种产品模式与内部版本选择

- 表单首层只显示一个键盘可达的产品模式选择：“单城市”“多城市·自行填写交通段”“多城市·填写已购铁路车次”；所有帮助、状态、错误和结果文案禁止出现 legacy/V2/V3/V4；
- “多城市·自行填写交通段”严格构造 V3；“多城市·填写已购铁路车次”严格构造 V4，并继续遵守 interests-only、用户提供未核验和票务隐私边界；
- 单城市保持当前确定性选择：结束日期未被用户编辑时，自动使用开始日加 1 日并构造 legacy；用户显式编辑结束日期后构造 V2，即使最终仍为 2 日。不得仅按天数重新推导版本，也不得改变 fingerprint；
- 切换模式必须清空不兼容段及其错误；进入 V4 同时清空并隐藏自由文本。模式变化用单一 polite live region 通知，不静默携带旧模式数据。

### 全版本恢复与旧 pointer 迁移

- 新 canonical key 固定为 `ita.last-local-job`，值只能是 job UUID。legacy/V2/V3/V4 的严格 POST 响应均写入该 key；不得保存版本、请求、结果、错误或敏感数据；
- 启动时先读 canonical；仅当 canonical 不存在时，依次兼容旧 `ita.active-v4-job`、`ita.active-v3-job`。GET 响应是版本和状态的唯一权威，不从 key 名推断版本；成功读取旧 key 后 best-effort 写 canonical 并移除两个旧 key；
- 非法 UUID 在发请求前清除命中的 pointer；GET `404`/已过期时清除 canonical 和旧 pointer，不展示缓存结果，回到新建表单并显示非阻塞恢复提示。网络、5xx 或 response parse 失败不自动清除 pointer，保留稍后重试入口；
- localStorage 不可用或抛错时，规划仍可继续，只跳过保存/恢复。新任务覆盖 canonical；同任务 retry 保持 canonical；“返回修改”清除 canonical 和旧 pointer 但不删除 SQLite 记录，防止刷新后重新恢复已放弃任务。

### 终态 DELETE

- 后端既有 `DELETE /api/trip-plans/{job_id}`、`204` 和错误 envelope 不变；新增的前端 client 只消费该 URI，不改变后端可删除状态范围；
- UI 只在权威响应已是 `ready/partial/needs_input/conflict/failed` 时提供“删除本机任务”，包括当前终态和恢复后的终态。processing、paused 非终态、提交中、retry 中均不得展示，因为 DELETE 不是取消 API；
- 使用页面内两步确认，不使用浏览器原生 confirm：触发后显示“确认删除/取消”，确认获得焦点；取消或 Escape 返回触发按钮；成功清除全部 pointer、回到新建表单并聚焦表单标题；失败保留任务和 pointer，显示安全错误并允许单独重试删除；
- “返回修改”与 DELETE 明确分离：前者只清 pointer，后者删除当前单条 job；不实现历史列表、批量删除、清库或运行中取消。

### 本地 PowerShell 运行契约

- 后续新增单一 `scripts/run-local.ps1`，固定校验 Python `3.13.3`、Node `22.16.0`、pnpm `11.19.0`；固定后端 `127.0.0.1:8000`、前端 `127.0.0.1:5173`，与现有 Vite strictPort/proxy 一致，不开放自定义 host 或公网绑定；
- 启动前用本机只读 listener 检查两个端口；冲突时只报告端口并退出，绝不停止既有进程。常规运行使用 frozen/offline 依赖模式且不访问软件包仓库；runner 自身不读取、检查或输出 `.env.local`/秘密，后端继续沿用既有 settings 边界；
- runner 只启动并保存自己创建的两个精确子进程，先等待后端 `/api/health`，再等待前端根页，单项最多 30 秒且请求仅 loopback；任一子进程提前退出、health 超时或 SQLite 初始化失败时，给出固定脱敏提示并收口另一个子进程；
- Ctrl+C 和所有失败路径都在 finally 中按保存的 PID/Process 对象停止并等待子进程；禁止按名称、端口或通配符杀进程，禁止删除数据库或修改系统配置。成功后只输出本机 URL，不自动打开浏览器；
- 干净检出验收若依赖缓存缺失，可在 Step 6 的独立、明确记录阶段访问项目已配置的软件包仓库；这一例外不进入日常 runner，业务 Provider 网络始终为 0。

### 局部 UX、可访问性与组合验收

- 保留现有“旅笺”视觉与单页结构，只新增有限的 status/success/partial/conflict/error/focus tokens 和最小共享组件；状态必须同时使用标题/文案，不能只靠颜色；
- 信息层级固定为产品模式 → 表单分组 → 处理阶段 → 终态摘要 → 主恢复动作 → 预算/来源/诊断。`configuration_missing` 显示“检查本机服务配置”且无 retry；unknown 金额显示“未知”，partial 保留可用计划，failed 不伪造计划；
- legacy 与 V2 恰好 2 日保留既有 F-003 replan；V2 3–7 日不显示控件并保持既有 scope 拒绝，V3/V4 继续全链路写前拒绝。提交、恢复、终态、返回修改和删除分别把焦点送到处理标题、恢复后的状态/结果标题、首错或表单标题、删除确认/原触发按钮；
- desktop/390px 必须验证 fieldset/legend、label/description/error 引用、一个 canonical live region、失败/删除错误 alert、逻辑 Tab 顺序、可见焦点、44×44px 触控、文本 4.5:1/非文本焦点 3:1 对比、reduced motion 和零横向溢出；
- 新增不少于 12 个完全离线的组合式 journey case，不做版本×状态笛卡尔积；分层覆盖四版本无配置、三产品模式、五终态、processing/paused、canonical/旧 pointer/非法与 404、reload/retry/DELETE、legacy/V2 两日 replan、V2 3–7 日 scope 拒绝、V3/V4 写前拒绝、unknown/来源/隐私。临时 schema v2 SQLite 验证 create/read/restart/retry/delete，代表性 desktop/390px browser 验证网络仅 loopback、console 0 error/warning 和 accessibility；F-005 固定 48-case eval 原样运行且不得重标为真实 UAT。

## Step 地图

| Step | 唯一可验证目标 | 当前状态 |
| --- | --- | --- |
| Step 0 | 激活任务、建立 D-017、Step 0–8、四层 stack、文件治理和最终 F-004C 基线 | DONE |
| Step 1 | 冻结无凭证终态、产品模式、恢复/DELETE、本地运行、UX、验收矩阵与文件归属 | DONE |
| Step 2 | 以 TDD 实现无凭证/配置不完整的零 Provider 安全终态与兼容接线 | DONE |
| Step 3 | 实现产品模式语言、共享状态/结果层级和有限 UX foundation | DONE |
| Step 4 | 实现全版本恢复、过期 pointer 清理、终态 DELETE 和完整旅程恢复 | DONE |
| Step 5 | 实现安全 PowerShell 本地运行入口、preflight、健康等待与精确停止 | DONE |
| Step 6 | 执行临时 SQLite、组合 synthetic browser、desktop/390px、网络/console/accessibility、干净检出和独立隐私安全验收 | DONE |
| Step 7 | 运行本地全量门禁并完成四层 commit/push/stacked PR/独立 review/逐层远程 CI，不合并 | DONE |
| Step 8 | 依序合并、必要 clean-restack、最终 main CI、归档与任务关闭 | TODO |

## 四层 stacked PR

1. `feat/f-006-local-runtime-compatibility`
   - 无凭证/配置不完整安全终态、bootstrap/application/API 兼容和直接测试。
2. `feat/f-006-mvp-ux-foundation`
   - 产品模式词汇、有限语义 tokens、共享状态/结果/来源/预算/冲突层级和直接组件测试。
3. `feat/f-006-mvp-journey-recovery`
   - App/use hook/request/API client/replan 的全版本 pointer、恢复、DELETE、焦点和旅程测试。
4. `feat/f-006-local-acceptance-delivery`
   - PowerShell 本地运行、统一 synthetic journey/browser 支撑、干净检出验收和当前交付文档。

后续层只能依赖前层已交付能力；前层 squash 后，后续层须从最新 main 做可审查 restack，禁止用 force-push 掩盖历史。Step 7 前不得 commit、push 或创建 PR，Step 8 前不得 merge。

## 核心文件与受控相邻扩展

### Stack 1 核心

- `backend/src/intelligent_travel_assistant/bootstrap.py`
- `backend/src/intelligent_travel_assistant/application/execution.py`
- 允许新增一个直接的安全 unavailable/no-provider executor
- `backend/src/intelligent_travel_assistant/app.py`
- `backend/src/intelligent_travel_assistant/api/trip_plans.py` 仅兼容接线
- 对应 bootstrap/application/API/Repository 兼容测试

### Stack 2 核心

- `frontend/src/styles.css`
- `frontend/src/TripRequestForm.tsx`
- `frontend/src/PlanningStage.tsx`
- `frontend/src/TripPlanResult.tsx`
- `frontend/src/MulticityTripPlanResult.tsx`
- `frontend/src/ResultEvidence.tsx`
- 对应组件、parser 和 accessibility 测试

### Stack 3 核心

- `frontend/src/App.tsx`
- `frontend/src/useTripPlanningJob.ts`
- `frontend/src/tripRequest.ts`
- `frontend/src/tripPlanningApi.ts`
- `frontend/src/replanningApi.ts`
- `frontend/src/ReplanPanel.tsx`
- 对应恢复、删除、重试、重规划和旅程测试

### Stack 4 核心

- 允许新增 `scripts/run-local.ps1`
- `scripts/verify.ps1`
- `scripts/check_docs.py` 及直接测试
- 允许新增统一 F-006 browser/synthetic journey 支撑，最小复用既有 browser helpers
- `README.md`、`.env.example` 仅在后续获批 Step 修正运行说明，不在 Step 0 修改
- 当前治理、权威状态和 evidence 文档

受控相邻扩展仅限直接 export、factory/wiring、同层 typed helper、对应测试/明显 synthetic fixture、browser 支撑和当前状态/evidence 文档。单 Step 出现超过 5 个未预期生产/测试文件时立即停止；Schema、migration、依赖、lockfile、Provider、公开 API shape、数据留存或隐私变化不属于相邻扩展。

## 规模阈值

- 任一 stack 超过 20 个生产/测试/script 文件或净新增 1600 行时停止并重新拆分；
- 任务累计超过 65 个生产/测试/script/fixture 文件或净新增 5200 行时停止并重新拆分；
- `styles.css` 净新增超过 600 行、替换约 30% 以上既有样式、或需要新 UI 框架/路由器/依赖时停止并重新批准。

## 验收标准

- 三种用户产品模式可理解、可键盘操作，内部 legacy/V2/V3/V4 选择与 exact compatibility 不变；
- 无凭证/配置不完整任务稳定进入 `failed / configuration_missing`，不调用 Provider、不遗留 `draft`；
- legacy/V2/V3/V4 都能只凭 UUID 从 SQLite authoritative job 恢复；旧 pointer 可迁移读取，404/过期会清理，不缓存请求或结果；
- 当前终态/已恢复任务可以确认后 DELETE；不出现历史列表、清库或运行中取消能力；
- processing、paused 和 ready/partial/needs_input/conflict/failed 的文案、层级、预算、来源、unknown、重试/修改/恢复动作一致；
- legacy/V2 恰好 2 日保留 F-003 replan；V2 3–7 日保持 scope 拒绝，V3/V4 replan 继续全链路写前拒绝；
- PowerShell 本地入口能 fail-closed 处理版本、端口、loopback、健康等待、SQLite 错误，并在 Ctrl+C 后只清理自己启动的精确子进程；
- 临时 schema v2 SQLite、组合 synthetic journey、desktop/390px、keyboard/focus/live region/44px/contrast/overflow、network/console/privacy 验收通过；
- F-005 固定 48-case eval 保持不变并通过；F-006 journey cases 完全离线，默认测试/CI 阻断非 loopback 网络；
- 文档检查、format/lint/typecheck/test/build、逐层 review、远程 CI、最终 main CI 和归档均通过后，任务才可标记 `DELIVERED / LOCAL_ACCEPTANCE_PASS / ARCHIVED`。

## 停止条件

- 需要新增/修改 URI、公开顶层 JSON key/错误码、strict contract、fingerprint 或旧记录语义；
- 需要 Schema、migration、依赖、lockfile、新 UI 框架/路由器或公开健康能力变化；
- 需要真实 Provider、秘密、账号、付费、生产部署或非 loopback 业务访问；
- 需要恢复 F-004B2、改变 V4 隐私/来源、扩大 replan 或实现历史列表/清库/运行中取消；
- 无法解释 Git/CI/文档事实冲突，或触发任一文件/净新增行/style 阈值；
- 当前 Step 目标要求跨入下一 Step 才能完成。

## 明确非目标

- 不新增旅行产品版本、Provider、真实城际事实或真实 Provider UAT；
- 不实现预订、支付、出票、订单、乘客、证件、账号、同步、云数据库、公网部署或生产高可用；
- 不新增 API、历史列表、清空全部数据库、运行中取消 API、Provider readiness 健康字段或后台持续任务；
- 不修改 SQLite schema v2、migration 1/2、依赖或 lockfile；
- 不重写设计系统、品牌、路由或技术栈；
- 不把 synthetic、MockTransport、离线 eval、loopback QA 或干净检出验收表述为真实 Provider UAT。

## Step 7 结论与 Step 8 授权边界

Step 0–7 为 `DONE / PASS`。Step 7 本地全量门禁已通过：固定 Python 3.13.3、Node 22.16.0、pnpm 11.19.0，后端 `1388 passed`、前端 `131 passed`、文档测试 `29 passed`，format/lint/typecheck/build/文档契约全部通过。四层已形成精确父链；独立 review 发现的 Stack 1/2 分层自足问题、Stack 3 恢复边界问题和 Stack 4 runner/状态文档问题均已修复，最终复审无未关闭 finding。

四层 Draft PR #38/#39/#40/#41 的 base/head 拓扑与批准顺序一致；对应 Windows offline CI runs `32503520656`、`32503533764`、`32503554642`、`32547492597` 均为 success。当前仅等待用户单独批准 Step 8；不得 merge、运行最终 main CI 或归档。不得读取秘密、调用 Provider、修改 Schema/migration、依赖或 lockfile。
