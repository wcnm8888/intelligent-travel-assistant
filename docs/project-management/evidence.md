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

### F-001：单城市双日旅行计划垂直切片（进行中）

- 任务状态：`ACTIVE`
- 当前结论：`PARTIAL`。Step 38 已完成受控真实 API 冒烟；Step 39 已执行但真实数据 UAT 因 DeepSeek Schema 异常 `FAIL`；Step 40 独立 QA、Step 41 离线阻塞修复和 Step 42 文档收口已完成，尚无通过式真实 UAT 或 Git/PR 交付；
- 分支：`feat/f-001-single-city-two-day-plan`，已形成单一本地提交，未推送、无开放 PR；
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
- 官方来源：[DeepSeek 模型与价格](https://api-docs.deepseek.com/zh-cn/quick_start/pricing)、[DeepSeek 用户协议](https://cdn.deepseek.com/policies/zh-CN/deepseek-terms-of-use.html)、[DeepSeek 开放平台服务协议](https://cdn.deepseek.com/policies/zh-CN/deepseek-open-platform-terms-of-service.html)、[高德服务升级与配额](https://lbs.amap.com/upgrade)、[高德开放平台服务协议](https://lbs.amap.com/pages/terms/)、[和风天气定价](https://dev.qweather.com/docs/finance/pricing/)、[和风天气注明来源](https://dev.qweather.com/docs/terms/attribution/)、[和风天气实时预警响应契约](https://dev.qweather.com/docs/api/warning/weather-alert/)；
- Step 27 浏览器：本地 Microsoft Edge 使用本机 synthetic partial/failed 响应验证 retry 恢复、双击只产生一次请求、attempt 2、旧终态清理和返回修改焦点；`390×844` 下输入区域折叠、结果优先且无水平溢出，干净会话控制台 0 error/0 warning；
- 请求边界：Step 35 浏览器业务请求仅为同源任务 API；DeepSeek、高德与和风 adapter 专项测试使用进程内 mock transport。Step 40 发现默认 API 测试组合根可能因 `.env.local` 装配真实执行器；Step 41 已用导入前 `APP_ENV=test`、禁用 dotenv source 和非 loopback socket 阻断关闭该风险，并由统一入口复验；
- 真实性边界：Step 38 只证明执行时三家鉴权与所触达 live Schema 可用，并证明一次高德公交路线契约；不证明持续可用、全部端点、结果质量或下一次费用。唯一计划的确定性终态是 `conflict`；
- 未覆盖：ready/partial 真实计划、通过式真实数据 UAT、Step 39 原始失败的精确上游字段、长期配额和费用稳定性、提交、PR、CI 和合并。新的 live 回归仍需单独授权。

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
