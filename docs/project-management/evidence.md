# 验收证据索引

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
