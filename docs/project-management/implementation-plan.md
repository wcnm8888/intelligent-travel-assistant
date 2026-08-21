# 当前实施计划

当前无活动任务，因此没有正在执行的 Step。

## 当前状态

- 当前任务：无
- 最近完成：`F-005 外部服务韧性、数据时效与 Agent 评估`
- 任务状态：`DELIVERED / ARCHIVED`
- Step 0–9：`DONE`
- 完整功能 main：`fddd4e5add5919f1751279de9b833a3192ea6338`
- 完整功能 main CI：run `32452988076`，`PASS`
- 下一动作：等待用户从 roadmap 选择并批准下一任务卡

## Step 0：事实复核、任务激活与治理基线

唯一目标：在不进入设计实现的前提下，复核最终 F-004B1 归档事实，激活已批准的 F-005 并建立执行治理。

状态：`DONE`

完成结果：

- 复核 `HEAD == main == origin/main == c5f07e12abdc37f977ee0f7181a5f2800f015066` 和干净工作区；
- 复核 PR #19/#23/#24/#25/#26 均已合并、无开放 PR，PR #26 merge commit 为 `c5f07e1`；
- 复核 main CI run `32386260285` 在该提交上 `completed/success`；
- 确认激活前没有活动任务；
- 将完整已批准 F-005 任务卡写入 current-task，roadmap 中 F-005 成为唯一 ACTIVE；
- 写入 Step 0–9、D-014、核心文件、受控相邻扩展、四层 stacked PR 和规模阈值；
- 修正当前权威文档中 F-004B1 Step 0–8、PR #26、最终 main/CI 状态漂移；
- 创建首层本地分支 `feat/f-005-resilience-domain-contracts`；
- 未修改源码、测试、Schema、migration、依赖、lockfile、数据库或归档材料；未读取秘密或调用 Provider；未提交、push、创建 PR 或触发 CI。

## Step 1：实现前设计冻结

唯一目标：把 D-014 已批准方向冻结为可实现、可测试且兼容的精确失败、时效、重试、Agent eval、API/UI 和交付契约，不实现生产代码或测试。

状态：`DONE`

必须冻结：

- Provider failure → needs_input/conflict/failed/partial/ready 的能力关键性矩阵；
- `fetched_at/valid_until/evaluated_at/freshness/attribution` 权威关系和 stale/unknown-validity 使用矩阵；
- Amap/QWeather attempt、jitter、Retry-After、Provider/任务额外预算和 DeepSeek 0 传输 retry；
- 逻辑调用与 HTTP attempt 分离、总 deadline、主动取消、peer drain 和 terminal 零新调用；
- retry→route fallback→deterministic stop 顺序以及城际 Provider 调用 0；
- legacy/V2/V3 bounded proposal/repair 输入和不可信 Provider 文本隔离；
- ≥48 case eval 数据格式、维度、100% 安全硬门禁、95% 总分和 CI 输出边界；
- 不新增 URI/JSON 键/顶层错误码的 API 与前端恢复语义；
- unit/contract/adapter/application/API/SQLite/frontend/browser/security 测试矩阵；
- 四层 stack 的精确归属、验证入口和 clean-restack 规则。

完成结果：

- 冻结城市/住宿/站点/POI、最终路线、天气/预警和 DeepSeek 的关键性、retry 耗尽后终态以及 Provider failure 不得投影 needs_input/conflict 的矩阵；
- 冻结 freshness 为 attempt 评估快照、GET 不按墙钟改写、stale 路线拒绝、天气/预警剔除和 unknown-validity 最多 partial 的逐能力政策；
- 冻结纯 domain policy + 显式 job-scoped runtime + 单次 HTTP adapter 的边界，额外预算 3/1/4、full jitter、受控 Retry-After、每 attempt timeout、deadline 前置拒绝、terminal close 和 peer drain；
- 冻结 generation allowlist 与不含原始输出/自由文本/Provider observation 的 `PlanRepairBrief`，以及 Provider 文本有限 display label 门禁；
- 冻结 48-case 离线 eval 的 12×4 分布、两次确定性执行、25/20/15/15/10/15 权重、95% 总分和五类 100% 硬门禁；
- 冻结既有 `data_stale`/`diagnostic_code` 投影、前端恢复动作、attempt 3 组合、legacy/V2/V3/F-003 compatibility 和 schema v2 snapshot 边界；
- 冻结 Stack 1 domain、Stack 2 runtime、Stack 3 application/API/Agent eval、Stack 4 frontend/delivery 的精确归属及分层测试入口；
- 只修改当前权威与状态文档；没有修改生产源码、测试、fixture、Schema、migration、依赖或 lockfile，没有读取秘密、创建数据库、调用 Provider、访问非 loopback、commit、push、PR、CI 或进入 Step 2。

核心文件仅限批准的当前权威文档。禁止修改生产源码、测试、fixture、Schema、migration、依赖、lockfile、数据库或分支拓扑；禁止读取秘密、调用 Provider 或访问非 loopback 服务。

## Step 2：纯领域 resilience 与 freshness 决策

唯一目标：以 TDD 实现纯领域错误、时效、retry schedule 和安全诊断决策，不进入 adapter、application、API 或前端。

状态：`DONE`

批准入口：只允许以 TDD 修改 `domain/provider_result.py`、新增 `domain/resilience.py`、直接 export 与对应 domain/contracts golden 测试；不得进入 adapter、application、API、Repository、SQLite、Provider 或前端。

完成结果：

- RED：新增定向测试首次在 collection 因 `FactCriticality` 等 F-005 领域符号不存在失败；
- GREEN：`ProviderError` 加入仅 rate-limit 可用的 bounded Retry-After；新增纯 Provider/operation schedule、retry、freshness、required/optional failure 和安全诊断决策；
- retry 锁定 Amap/QWeather 2 attempts、Provider 额外 3/1、任务额外 4、6 秒 attempt，DeepSeek 1 attempt/35 秒/0 retry，以及 jitter、budget、deadline、terminal/cancelled 前置停止；
- freshness 锁定 inclusive boundary 复用、route stale reject、weather stale omit、location stale partial-use、unknown-validity partial-use；Provider failure 只可产生 failed/partial；
- 验证：定向 `108 passed`；domain + contracts/golden `342 passed`；全 backend `134 files already formatted`、Ruff lint 通过、strict mypy `134 source files` 通过；
- 生产/测试范围为 5 个批准文件，未进入 adapter/application/API/Repository/SQLite/前端，未修改 Schema/migration/依赖/lockfile，未创建数据库、读取秘密、调用 Provider、commit、push、PR 或 CI。

## Step 3：Provider runtime

唯一目标：实现可由每个 planning attempt 显式持有的统一 attempt runtime，并让现有 Amap/QWeather adapter 提供安全错误/Retry-After 输入；DeepSeek 只锁定 transport retry=0，不进入 application 编排接线、API 或 UI。

状态：`DONE`

完成结果：

- RED 首次因 `ProviderAttemptRuntime` 尚不存在而在 collection 失败；最小 GREEN 后 runtime + Amap/QWeather 定向 `121 passed`；
- 新增显式 task-scoped runtime，独立持有 attempt 记录、Provider/任务额外预算、deadline、active peers 和 closed 状态，覆盖单 attempt timeout、注入式 delay、终态/取消/异常 close、peer cancel/drain 与 closed 后零新调用；
- Amap/QWeather 保持单次 HTTP exchange，只输出安全 `ProviderError` 和规范化 `0..2s` Retry-After；不保留原始 header/body，不在 adapter 内 sleep/retry；DeepSeek 生产代码不变且 transport retry=0 回归通过；
- Provider/DeepSeek/治理/既有编排回归 `378 passed`，domain/contracts `164 passed`；全 backend Ruff format/lint 与 strict mypy 136 files 通过；
- 生产/测试范围为 8 个批准核心或受控相邻文件、净新增 859 行、未预期文件 0；没有 application planning service 接线，也未进入 API、Repository、SQLite、前端、Schema/migration、依赖或 Step 4。

## Step 4：application 调用治理

唯一目标：在 legacy/V2/V3 编排中统一逻辑调用、HTTP attempt、deadline、取消、peer drain、retry/fallback 停止顺序和同 shape 后端错误/时效投影。

状态：`DONE`

完成结果：

- RED 1：legacy/V2/V3 新接线测试首次因 orchestrator/executor 尚不接受显式 runtime 参数而 4 项失败；RED 2：过期天气仍进入计划投影，证明旧路径未消费 freshness 决策；
- 每个 planning attempt 由 executor 创建一个 runtime，并在 Repository/API 终态发布前 close；legacy/V2/V3、DeepSeek generation/repair、城市事实、天气/预警和路线复用同一实例；
- 逻辑 governor permit 只计一次，HTTP retry 独立计 attempt；deadline 不足时不启动 HTTP，并以既有 `provider_timeout` + 安全 diagnostic 投影；并发城市/路线异常或取消会 cancel/drain peers；
- retry 完成后才裁决 route fallback；stale required route 直接 failed，不触发 mode fallback；stale weather/alert 从 planning/model/UI payload 剔除并形成 partial；unknown-validity 不再提升 V3 ready；
- 同 URI、同 JSON keys、既有顶层 error code 保持；复用 `data_stale`、`retryable` 和安全 diagnostic code，Repository/SQLite schema 与 migration 未变；
- 定向 runtime/application 回归 `60 passed`，完整 backend `1264 passed`；Ruff format/lint 与 strict mypy 136 files 通过；文档、diff 与范围门禁见 Step 4 evidence；
- 未进入 Agent eval、前端、Schema/migration、依赖/lockfile、真实 Provider、外部网络、commit、push、PR 或远程 CI。

## Step 5：Agent 安全与离线评估

唯一目标：统一 proposal/repair 输入最小化与 Provider 不可信文本隔离，并建立达到批准阈值的固定离线 Agent eval 门禁。

状态：`DONE`

完成结果：

- RED：repair 最小化测试首次在 collection 因 `PlanRepairBrief` 不存在失败，证明旧端口仍依赖完整 `PlanningContext + invalid_output`；
- legacy/V2/V3 repair 现只接收 frozen/slotted `PlanRepairBrief`：日期/城市/窗口骨架、允许 location/source 目录、稳定 validation code 与可选无值 time failure；不再包含原始模型输出、完整 context、自由文本、preferences、hard constraints 或 Provider observations；
- generation/repair payload 对 Provider label 执行 120 字、单行、控制符和提示标记门禁，对 category/kind 只接受项目 token；adapter 在发送边界再次过滤，unsafe label 只变为 `null`，不进入 Prompt；
- 新增严格版本化 `f005-v1` 离线 eval：legacy/V2/V3/F-003 各 12 case，各 slice 四类各 3 case；连续确定性执行两次，六维加权 100.0%，五类硬门禁零失败；报告只含聚合计数和失败 case ID；
- 定向 Agent/adapter/ports/eval `127 passed`，完整 backend `1270 passed`；Ruff format/lint、strict mypy 137 source files 与 eval 4 files 通过；
- task 累计生产/测试/eval 36 文件、净新增 3421 行；按已批准 stack 归属估算 Stack 3 净新增 1706 行，均低于阈值；
- 未进入前端、Schema/migration、依赖/lockfile、真实 Provider、外部网络、数据库、commit、push、PR、CI 或 Step 6。

## Step 6：前端失败体验

唯一目标：消费 Step 4 已冻结的同 shape 后端结果，统一 data_stale、retryable、partial/failed 和恢复动作展示，不新增或推导服务端语义。

状态：`DONE`

完成结果：

- RED：新增同 shape 前端用例后，鉴权仍显示通用失败标题、错误沿服务端数组顺序展示、`data_stale` 仍使用通用 retry 文案、unknown-validity 未明确“不代表当前有效”，定向 30 项中 4 项按预期失败；
- GREEN：`ResultEvidence` 只根据既有 error code/freshness 字段显示固定配置、暂时失败、stale 与不可安全使用语义，并按“输入→冲突→配置→暂时失败→stale→不可重试”排序；没有重算 freshness、Provider 关键性或终态；
- failed 鉴权显示“本机服务配置需要检查”且不提供 retry；timeout/rate/unavailable 仍只在服务端 `retryable=true && attempt<3` 时使用既有 job retry；partial stale 使用“重新获取数据”，unknown-validity 明示“不代表当前有效”且不单独创造 retry；
- legacy/V2/V3 继续使用 strict exact-shape parser，unknown 金额和多城市用户城际来源语义不变；定向 30 项、前端全量 99 项、Prettier、ESLint、TypeScript、Vite build 及无 SQLite 的后端 API/contracts 兼容 98 项通过；
- 本 Step 仅修改 3 个批准生产组件及 3 个对应测试，`+290/-60`、净新增 230 行、未预期文件 0；任务累计 42 个生产/测试/eval 文件、净新增 3651 行，未触发阈值；
- 未进入临时 SQLite、浏览器、Schema/migration、依赖/lockfile、真实 Provider、外部网络、数据库、commit、push、PR、CI 或 Step 7。

## Step 7：纵向与独立审查

唯一目标：完成临时 SQLite、loopback synthetic desktop/390px、网络/console/accessibility 和独立隐私安全审查。

状态：`DONE`；结论含已披露过程偏差，不构成无条件 PASS

完成结果：

- 临时 schema v2 SQLite 纵向最终 `31 passed`；日期漂移以测试 RED 锁定后，只在 browser 支撑中用显式 `ITA_BROWSER_START_DATE` 平移冻结日期，未改变默认 fixture、生产 contracts、Repository、Schema 或 migration；
- Edge 在 desktop `1440×1000` 与 mobile `390×844` 完成 V3 partial、keyboard/skip link、retry、reload、unknown/null 和时效披露；overflow、DOM/ARIA、console 均通过，浏览器 57 条请求全为 loopback；
- 临时数据库 migration 仍为 1/2，秘密、原始响应/Prompt、运行诊断模式扫描为 0；三份精确临时文件移入可恢复的回收站；
- Codex Security scan `c0d1100d-227b-4572-aa5a-769cb0689541` 覆盖 8 个信任面、coverage complete、0 finding；定向 `365 passed`、SQLite `31 passed`、Ruff 与项目权威 strict mypy 137 files 通过；
- 仅受控修改 2 个测试文件、净新增 59 行；任务累计 44 文件/3710 净新增行，未触发阈值；未修改生产源码、Schema/migration、依赖/lockfile或交付状态；
- 首次 `npx --yes @playwright/cli@latest --help` 可能查询 npm registry，后续均为 `npx --offline`。该过程偏差已永久记录，因此 Step 7 不记为无条件 PASS；用户已明确接受该偏差。

## Step 8：全量门禁与 stacked PR

唯一目标：完成本地全量门禁、五层 stacked PR、逐层独立 review 和远程 CI，不合并。

状态：`DONE`

Step 8 批准修订：用户已接受 Codex CLI 全局插件外连失败偏差，并批准在原 application/Agent 层与 UI 层之间新增 `feat/f-005-agent-eval-integration`。该层只能让 legacy/V2/V3/F-003 的终态、来源、unknown/partial 和调用预算评估经过各自真实离线 application 入口，不得扩大生产/API/Provider/Schema/依赖边界；最终拓扑为 domain → provider runtime → application/Agent → application eval integration → UI/delivery。

## Step 9：依序合并与归档

唯一目标：依序合并、必要 clean-restack、完整 main CI、归档和任务关闭。

状态：`DONE`

完成结果：

- PR #27/#28/#29/#30/#31 按批准顺序 squash merge，对应 main commits 为 `1534cad`、`66445c1`、`afc8a45`、`472a519`、`fddd4e5`；
- 每个后续 PR 在前层合并后将 base 改为最新 main，GitHub 均为 CLEAN/MERGEABLE，tree diff 只含本层净变更；因此无需替代式 clean-restack，也没有 rebase 或 force-push；
- 逐层 main CI runs `32451655141`、`32451996154`、`32452323662`、`32452640620`、`32452988076` 全部成功；
- 完整功能 main 为 `fddd4e5add5919f1751279de9b833a3192ea6338`，F-005 完整任务卡已归档，current-task、roadmap、progress、evidence 和文档地图已切换为无活动任务；
- 未修改 Schema/migration、依赖或 lockfile，未读取秘密或调用真实 Provider。

## 全局禁止与停止条件

- 未经当前 Step 明确批准不得跨 Step 或 stack；
- 不新增 Provider、Schema/migration、依赖、URI、公开 JSON 键、账号、遥测或公网服务；
- 不读取 `.env.local`、秘密或本地 Provider 配置，不执行真实 Provider UAT；
- 不改写历史 evidence 或归档任务卡；
- 单 Step 超过 5 个未预期生产/测试文件、单 stack 超过 30 文件或 2500 净新增行、任务累计超过 90 文件或 8000 净新增行时停止；
- F-001 `PARTIAL`、Step 45M `FAIL`、Step 45T `PASS`、unknown 不按 0、混合交通 fallback 仅离线、F-004A/F-004B1 无真实 Provider UAT 和城际 Provider 调用 0 保持不变。
