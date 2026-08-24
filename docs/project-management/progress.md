# 项目进度

## 当前状态

- 当前任务：`F-006 MVP 体验收口与本地验收`
- 状态：`ACTIVE`
- 当前 Step：`Step 8 - 合并、最终 CI 与归档（TODO / 待单独批准）`
- 基线：`main == origin/main == b99d5fc4c89b0f25ec89e4e12cd1755a7c3be46f`，Step 0 开始前工作区干净
- F-004C：Step 0–6 `DONE / DELIVERED / ARCHIVED`；PR #34/#35/#36 和归档 PR #37 已合并；最终 main CI run `32486428083` success
- F-004B2：`BLOCKED / ARCHIVED`；不得恢复其 Provider 查询或 Step 2
- 当前授权：F-006 Step 0–7 已完成；Step 8 仍待用户单独批准

## F-006 Step 7

- 状态：`DONE / PASS`；固定运行时下统一门禁通过，后端 `1388 passed`、前端 `131 passed`、文档测试 `29 passed`，Ruff、strict mypy、Prettier、ESLint、TypeScript、Vite build 和文档契约全部通过；
- 提交链：父链为 Stack 1 `b3e29aa` → Stack 2 `972b1d4` → Stack 3 `f5903f4` → Stack 4 `7a9b488` + 文档/runner 修正 `e6d3547`/`7f8cabb`/`2b95930`；没有 force-push，四分支均已普通 push；
- review/CI：四层最终独立 review 无未关闭 finding；Draft PR #38/#39/#40/#41 保持 open，对应 Windows offline CI runs `32503520656`/`32503533764`/`32503554642`/`32547492597` 均为 success；
- 范围：Stack 1 为 11 个生产/测试文件、净新增 472 行；Stack 2 为 9 个、净新增 134 行；Stack 3 为 11 个、净新增 843 行；Stack 4 为 3 个生产/测试/script 文件、净新增 969 行，另含批准的当前文档。任务累计去重后为 31 个生产/测试/script 文件、净新增 2418 行，`styles.css` 净新增 74 行，均低于阈值；Schema/migration、依赖/lockfile diff 为 0；
- 下一动作：等待用户单独批准 Step 8；此前不得 merge、运行最终 main CI 或归档。

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
