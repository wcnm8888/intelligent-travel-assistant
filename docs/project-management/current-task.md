# 当前任务

## 任务元数据

- 任务 ID：`F-001`
- 名称：单城市双日旅行计划垂直切片
- 等级：`L`
- 状态：`ACTIVE`
- 基线分支：`main`
- 功能分支：`feat/f-001-cr1-deterministic-scheduling`（stacked base：`feat/f-001-single-city-two-day-plan`）
- PR 目标：一个 PR 交付首个可验证的旅行计划端到端闭环
- 建议 PR 标题：`feat: deliver single-city two-day travel planning slice`
- 批准日期：2026-08-13
- 当前 Step：`Step 46 - 经用户批准后合并（TODO；PR #5 已 ready-for-review，仍需按 stacked 顺序合并并复验 PR #4）`
- 最近完成补充 Step：`Step 45X - 最终文档收口、PR #5 元数据校正与 ready-for-review（DONE）`
- 下一可执行 Step：`Step 46 - 先合并 PR #5 到 feat/f-001-single-city-two-day-plan，再复验并处理 PR #4（待单独批准）`

用户已经确认本任务的目标、范围、非目标、输入输出、状态模型、验收标准、风险边界和十二项工程决策，并授权执行 Step 0。后续仍坚持每次只执行一个单独批准的 Step；批准任务卡不等于授权真实 API 调用、提交、推送、创建 PR 或合并。

## 用户目标和工程价值

个人或小型同行群体可在本地 Web 页面输入一个中国大陆城市、连续两天日期、人数、总预算、偏好、交通要求和住宿要求，获得结合真实天气、POI、地理位置与路线数据的结构化旅行计划。系统必须用代码校验日期、时间、路线和预算，并明确展示来源、更新时间、未知费用、不确定性、冲突及失败恢复方式。

本任务第一次闭合以下工程价值链：

```text
用户提交双日需求
→ 受控工具获取真实城市、POI、路线和天气事实
→ deepseek-v4-flash 生成结构化候选
→ 确定性代码校验和裁决
→ Web UI 展示计划、来源、未知项、冲突和恢复动作
```

## 当前事实、能力缺口和前置条件

- B-000 已完成、合并并归档；功能分支基于同步且干净的 `main` 提交 `50980887dadc0500d98dcd29966a5da2da74b2e2` 创建。
- Python 固定为 3.13.3，Node.js 固定为 22.16.0，pnpm 固定为 11.19.0。
- 当前已有 FastAPI 健康/任务资源 API、React 旅行需求表单、严格任务 API/retry client、五种终态界面，以及 DeepSeek、高德和和风 HTTP adapter；Step 37 已将真实 provider 执行器接入组合根，只有三家完整配置同时就绪时才启用，并以离线 fake 证明住宿 POI 解析、天气、模型候选、路线、预算、状态和 Repository 发布闭环。Step 38 已完成一次受控 live 契约验证；仍无业务持久化，真实结果只在进程内临时存在。
- 用户已自行创建三家账户与本项目凭证；项目根 `.env.local` 已被 Git 忽略，本地无网络启动检查确认 DeepSeek、高德、和风 adapter 与真实规划执行器均为 `ready`。该结论只证明配置可构造，不证明鉴权、余额、控制台配额或 live 合约可用。
- `deepseek-v4-flash` 已由官方文档确认是 API model ID；Base URL 保持 `https://api.deepseek.com`。
- 和风天气使用 JWT 方案；账户专属 API Host、项目 ID、凭据 ID和本地 Ed25519 私钥均已通过本地结构校验。用户控制台账单显示余额与应计费用均为 0；天气与预警当前处于每月前 50,000 次的零元价格区间，因此首次 smoke 无需充值。
- Step 0 已验证本地统一门禁通过，并发现、记录了 B-000 收口后的两处文档状态漂移；本 Step 已修正。
- 产品 UI 的桌面与窄屏参考稿已由用户批准并冻结；Step 23–27 的实现必须保持其信息层级、状态语义和无障碍边界。

本地凭证已就绪；用户已根据高德工程师电话沟通确认个人、非商业、本地组合展示边界。Step 38 live smoke 已完成，当前剩余的是具体计划 `conflict`、真实数据 UAT、独立 QA 与交付门禁。

Step 39 已按与 Step 38 相同的一次计划、三家调用预算和 12 元费用上限执行真实数据 UAT。唯一任务因 DeepSeek `provider_schema_invalid` 安全进入不可重试 `failed`，触发用户指定停止条件；没有再次提交或重试。失败界面的桌面和 `390×844` 窄屏检查通过安全展示要求，但没有生成可验收的 ready/partial 计划，因此真实数据 UAT 结论为 `FAIL`，阻塞 F-001 完成。

Step 40 已完成全量工作区的独立只读 QA、测试审查和预 PR review。审查确认当前 `provider_schema_invalid` 同时覆盖 adapter envelope 异常和本地 `model_output_invalid`，缺少不含原文的安全子原因，无法从现有证据判定 Step 39 的精确失败字段；同时发现默认本地测试会加载 `.env.local` 并可能装配真实执行器、DeepSeek 上下文/repair 契约缺项、时间窗口输入未在 provider 调用前完整拒绝、天气地点引用与查询坐标不一致，以及工作区规模越过任务卡停止阈值。使用进程内禁用 dotenv source 的测试护栏后，后端 744 项、前端 63 项及适用静态、构建和审查前文档检查通过；默认统一入口因隔离缺陷未执行，不能记为全量门禁通过。按本 Step 授权只同步四份项目管理文档后，文档检查器准确报告 `docs/README.md` 仍停在 Step 40 的状态漂移；该文件不在 Step 40 允许写入范围，留待后续文档修复。Step 40 证据足以进入修复阶段，但当前仍阻塞真实 UAT、提交和 PR。

Step 41 已完成阻塞修复且未调用真实 provider：测试组合明确禁用本地 dotenv 并阻断非 loopback 网络；adapter envelope 失败与本地候选失败分别发布为 `provider_schema_invalid` 和 `model_output_invalid`，项目自有 `diagnostic_code` 仅保留安全枚举；DeepSeek 上下文补齐时间窗、自由偏好、交通方式、住宿锚点和天气事实，repair 携带冻结 Schema，截断输出进入唯一一次 repair；日期顺序、POI 来源、时间窗、天气地点坐标和 timeout 语义均已收紧。页脚改为稳定任务名称。冻结运行时下统一 `scripts/verify.ps1` 一次通过，包含后端 756 项、前端 64 项、文档检查器 23 项及全部静态、构建和文档契约门禁。真实 ready/partial UAT、提交和 PR 仍未完成。

Step 42 已同步 Step 41 的架构、Agent、API、测试和证据事实。用户明确批准 F-001 作为一个完整垂直切片由单一 PR 交付，并接受当前 120 个变更文件的范围例外；该例外只覆盖已审查的 F-001 工作区，不授权扩大功能或执行新的 live 调用。下一步为待单独批准的 Step 43，本 Step 未暂存、提交、推送或创建 PR。

Step 43 已按用户批准的 120 文件清单完成精确暂存和本地单提交交付。提交前统一 `scripts/verify.ps1` 在冻结运行时下一次通过，秘密、忽略规则、范围、staged diff 和文档状态检查通过；未调用真实 provider、未推送或创建 PR。下一步为待单独批准的 Step 44。

Step 44 已将 `feat/f-001-single-city-two-day-plan` 推送到私有仓库并创建面向 `main` 的 Draft PR #4。PR 正文明确保留 Step 39 真实 UAT `FAIL`、F-001 当前 `PARTIAL`、120 文件范围例外和任何 live 回归必须重新单独授权的边界；远程 CI 已触发但结果留给 Step 45。未调用真实 provider、未合并或执行其他远程写入。

Step 45 已完成 Draft PR #4 的远程 CI 核对。Windows offline verification 全部通过，没有失败检查或需修复的阻塞问题；状态文档同步后，同一远程门禁已对最终 PR head 复验通过。PR 仍保持 Draft，真实 ready/partial UAT 仍为 `FAIL`，本 Step 未调用真实 provider、标记 ready 或合并。

补充 Step 45A 已在用户重新授权的单任务、DeepSeek 最多 3 次 HTTP、高德最多 16 次、和风最多 4 次和总费用不超过 12 元边界内完成。执行前分支、PR head、干净工作区、远程 CI、凭证隔离和三家 provider/真实执行器 `ready` 状态均通过；一次脱敏 DeepSeek 余额检查可用并计入 HTTP 上限。唯一真实任务在保留高德 3 条、和风 2 条来源后，以 DeepSeek `model_output_invalid`、安全诊断 `candidate_local_validation_failed`、`retryable=false` 进入 `failed`，没有计划、路线补全、重试、第二次提交或额外恢复调用。失败终态在桌面和 `390×844` 均无水平溢出，归因、来源、时效和返回修改入口可见且无重试入口；DOM 与临时启动日志的脱敏扫描未发现秘密或原始响应标记，未保存截图、原始响应、持久缓存或真实地点/路线明细，临时日志已移除。Step 45A UAT 结论为 `FAIL`，F-001 仍为 `PARTIAL`，Step 46 合并继续阻塞。

补充 Step 45B 已在 provider 配置显式禁用、非 loopback 网络阻断的条件下完成离线修复。根因是 resolver 已知本地验证码，但 outcome、executor 和 API 只发布通用诊断；同时 generation/repair Prompt 未完整表达解析器已经强制的候选目录、日期和字段规则。修复后公开错误仍为 `model_output_invalid`、`retryable=false`，诊断只由 generation/repair 阶段与 JSON、Schema、日期、时间、POI 引用、来源引用、安全文本、截断八类安全枚举组成；generation 与 repair 共用冻结候选规则，所有确定性校验保持不放宽。MockTransport 纵向回归已覆盖 adapter → resolver → executor → Repository → API、首次失败、repair 成功、repair 再失败、截断和非法引用，并证明最多一次 repair、无模型原文泄漏。统一离线门禁在 Python 3.13.3、Node.js 22.16.0、pnpm 11.19.0 下通过：后端 766 项、前端 64 项、文档检查器 23 项及全部静态、类型、构建和文档契约绿色。Step 45B 不产生 live 通过证据；Step 46 继续阻塞，下一动作应是用户单独授权一次新的受控 live 回归。

补充 Step 45C 已按用户重新批准的一次任务、DeepSeek 最多 3 次 HTTP、高德最多 16 次、和风最多 4 次和总费用不超过 12 元边界执行。执行前 Git/PR、19 个预期工作区变更、凭证隔离、官方价格/配额、天气日期、三家 provider/真实执行器 `ready` 和 DeepSeek 余额可用性检查均通过；余额检查计入 DeepSeek HTTP 上限。唯一杭州双日任务形成完整两日候选并保留 DeepSeek 来源，证明 Step 45B 后模型候选通过本地校验；最终确定性路线校验报告 2 项 `route_conflict`，终态为 `conflict`，因此真实 UAT 仍为 `FAIL`。公开来源计数为 user 1、system 1、高德 3、和风 2、DeepSeek 1；住宿、城际交通和门票 3 项费用保持 unknown，已知餐饮合计 400 元，未按 0 处理。桌面 `1280×800` 与窄屏 `390×844` 均无水平溢出，只有 1 次 POST 和同任务 3 次 GET，视口切换未增加请求，控制台 0 error/0 warning，DOM 与临时日志脱敏扫描通过。没有 retry、第二次提交、截图、原始响应或持久缓存；本次临时快照和日志已精确移除，本地服务已关闭。Step 46 继续阻塞；下一动作必须先离线审查路线冲突是否来自候选排程、路线补全或最终校验契约，不得自动再次调用 provider。

补充 Step 45D 已在三家 provider 配置显式为空且测试拒绝非 loopback 网络的条件下完成。红测复现了首项活动贴合日窗口起点、末项活动贴合日窗口终点和不同地点活动零间隔均会被旧候选解析错误接受，随后两天路线补全被 `route_gap_not_positive` 跳过并最终各产生一项 `route_conflict`。修复后 generation/repair 共用的 Prompt 明确要求住宿往返和不同地点活动间保留正数交通时间；本地候选准入复用 `DailyRoutePlan.expected_legs()`，把边界不可行稳定分类为现有 `candidate_time_invalid` 并最多触发一次 repair。最终 `DailyRoutePlan.validate()`、真实路线时长超过间隔的硬冲突和同地点连续活动规则均未放宽。专项 162 项通过；冻结 Python 3.13.3、Node.js 22.16.0、pnpm 11.19.0 下统一门禁一次通过，包含后端 772 项、前端 64 项、文档检查器 23 项及全部静态、类型、构建和文档契约。新的受控 live 回归仍需单独授权，Step 46 继续阻塞。

补充 Step 45E 已按用户批准的最后一次受控 live 边界执行。执行前分支、HEAD、21 个既定工作区文件、空暂存区、Draft PR #4/远程 CI、凭证隔离、天气日期、三家 provider/真实执行器 `ready` 和 12 元费用上限均通过；未执行独立 provider 探针。唯一任务在 generation 候选时间校验失败后执行唯一一次 repair，最终以 DeepSeek `model_output_invalid`、安全诊断 `candidate_repair_time_invalid`、`retryable=false` 进入 `failed`，没有计划、路线补全、第二次提交或 retry。公开来源脱敏计数为 user 1、system 1、高德 3、和风 2；桌面 `1280×800` 与窄屏 `390×844` 均无水平溢出，失败恢复入口、归因和时效可见，控制台无 error/warning，DOM 与临时产物扫描无秘密或原始响应标记。临时浏览器文件和运行日志已精确移除，本地服务已停止。真实 UAT 结论仍为 `FAIL`，F-001 保持 `PARTIAL`，Step 46、ready-for-review 和合并继续阻塞。

补充 Step 45F 已在 `APP_ENV=test`、禁用 dotenv、三家 provider 空配置和非 loopback 网络阻断下完成。红测证明 `DailyRoutePlan` 已能识别活动越窗、访问顺序和非正数路线间隔，但候选层把它们全部压缩为 `candidate_time_invalid`，且唯一一次 repair 只收到该通用码。最小修复新增五类项目自有、无值时间诊断，并把对应静态规则提示传给 repair；公开错误保持 `model_output_invalid`、`retryable=false`，最多一次 repair，所有日期、时间、路线及最终校验均未放宽。专项 165 项与后端全量 786 项通过；统一门禁随后验证前端 64 项、文档检查器 23 项及全部静态、类型、构建和文档契约。离线证据确认 generation/repair 原有 Prompt、PlanningContext 和冻结规则已经完整，不能再把失败归因于规则遗漏。三次 live UAT 仍显示 LLM 独立生成精确活动时间不可靠，因此已起草“确定性代码负责时间骨架与排程，LLM 负责 POI 选择、顺序建议和解释”的待批准架构提议；本 Step 未实施该迁移，也未执行 live、暂存、提交、推送或修改 PR。

补充 Step 45G 已完成架构变更控制和详细设计。用户正式批准 D-009 的职责方向：LLM 只输出不含最终精确时刻的活动 proposal，高德提供代码确定端点的实际路线，确定性代码生成时间骨架并由现有校验器独立复验。设计采用新增 `PlanProposal`、保留现有带时间 `PlanCandidate`、不改变公开 API/Repository/UI，并以每天最多 2 项控制路线链在正常 6 段、每天一次 optional 调整后最坏 8 段。每日上限、60/120/180 分钟时长、景区/博物馆缺省 120 分钟、步行/公交 10/15 分钟缓冲、一次 optional 移除、required/unknown/路线失败终态、stacked PR 和 24–34 文件/1200–2200 行范围例外均已批准。Step 45G 未修改生产代码或测试；Draft PR #4 尚未包含 Step 45B–45G，Step 45H 实现仍需单独批准，详见 [F-001-CR1 变更卡](./f-001-cr1-deterministic-scheduling.md)。

补充 Step 45H 已在 stacked implementation branch 完成纯离线迁移：DeepSeek 严格准入无最终时刻的 `PlanProposal`，确定性调度器按实际 `RouteLeg`、60/120/180 分钟时长和步行/公交 10/15 分钟缓冲生成现有 `PlanCandidate`。每天最多 2 项、一次最低优先级 optional 移除及桥接路线、required 容量 conflict、unknown needs_input、路线 unavailable failed 和 partial-with-valid-route 语义均已落地；`planning → needs_input` 状态边已加入，公开 API、Repository 和 UI Schema 未改变。旧精确时间候选解析器只保留迁移回归，不再是生产正常路径。Step 45H 未读取凭证、调用 provider、执行 live UAT、暂存、提交、推送或修改 PR；真实 UAT 最新结论仍为 Step 45E `FAIL`。

补充 Step 45I 已完成独立离线 QA 与 stacked PR 前审查。审查开始时确认 27 个文件、`+2158/-281` 的实现范围与批准例外一致；同步本段脱敏结论后仍为相同 27 文件，当前总差异为 `+2188/-286`。审查未发现 P0/P1 生产缺陷；D-009 的 proposal → 实际路线 → 确定性 scheduler → 既有 candidate/final validation 职责迁移已经落地。专项 127 项和统一离线门禁均通过，统一入口包含后端 818 项、前端 64 项、文档检查器 23 项及全部静态、类型和构建门禁；测试显式禁用 provider 配置并阻断非 loopback 网络。审查同时发现 P2 测试缺口：新 proposal 负向信任边界未被完整直接锁定、新五终态纵向链覆盖不足、被移除 optional 的历史路线错误未证明不会污染最终结果，以及时长映射测试精度不足；另有 D-009 实施前后的文档语义漂移。上述问题阻塞精确暂存和 stacked PR，需先单独批准 Step 45J 做最小离线修复；没有授权新的 live UAT。

补充 Step 45J 已关闭上述 P2 测试和文档缺口。用户确认真实执行器因门票费用必须保持 unknown，成功计划合理收口为 `partial`，不以 0 或生产改动伪造 `ready`；真实纵向链覆盖 partial、conflict、needs_input、failed，ready 继续由零 unknown 冻结契约覆盖。Proposal 负例、时长映射、optional 路线污染、route retryable/source/uncertainty 和 warning API 投影均已补齐；专项 125 项与统一门禁通过，后端 838 项、前端 64 项、文档检查器 23 项。未调用 provider、修改生产代码、暂存、提交、推送或修改 PR；下一动作是待批准 Step 45K 交付 stacked Draft PR。

补充 Step 45K 已将 27 个批准文件精确暂存并形成提交 `bb52adea871c6cadc21ceaa5ef4255b79c3904cb`，推送 `feat/f-001-cr1-deterministic-scheduling` 并创建以 `feat/f-001-single-city-two-day-plan` 为 base 的 stacked Draft PR #5。远程 Windows offline verification run `31867996619` 对该 head 通过；PR #4 和 PR #5 均保持 Draft，未执行 live 或合并。

补充 Step 45L 已完成 PR #5 相对 stacked base 的独立只读 review。27 文件、`+2559/-297`、base/head、Draft、CI 和秘密边界一致；专项 147 项及文档检查器 23 项复验通过，未发现当时可证实的 P0/P1 生产缺陷。审查发现 API 状态机文档缺少 `planning → needs_input` 及项目状态仍停在 Step 45K 前；两项文档漂移不阻塞一次受控真实 UAT，但必须在 PR ready 前收口。

补充 Step 45M 已按单任务、DeepSeek 3、高德 16（路线 8）、和风 4 和 12 元上限执行 D-009 后真实 UAT。执行前当前 head/PR/CI/干净工作区、三家 provider 与执行器 `ready`、仓库外私钥及冻结调用预算均通过；没有独立 provider 探针。唯一任务以高德 `data_missing`、`retryable=false` 进入 `failed`，无计划、无 violation/warning；公开来源计数为 user 1、system 1、高德 7、和风 2、DeepSeek 1，证明 proposal、天气和部分路线事实已经形成，但必要路线没有全部可用。由于不保存原始响应，不能推测具体上游路线或地点。

Step 45M 同时发现三个离线可证实的后续 finding：请求允许步行和公交时，执行器当前无条件选择公交且没有在用户允许的方式内做确定性降级；路线不可用已知时，公开高德 `data_missing` 仍缺少 `route_data_unavailable` 安全诊断；前端可达状态表缺少后端已经允许的 `planning → needs_input`。本次 live 结果与第一个缺口一致但不足以单独证明其为唯一上游原因。桌面 `1280×800` 与 `390×844` 均无水平溢出，归因、freshness、AI 披露和安全失败展示正确，控制台 0 error/0 warning；仅 1 次 POST，无 retry 或第二个任务，临时浏览器文件和本地服务已精确清理。真实 UAT 结论为 `FAIL`，不得进入 Step 46。

补充 Step 45N 已纯离线关闭上述三个 finding。双选时冻结为公交首选、失败路段步行降级；路线结果必须同时匹配高德 provider、端点、请求 mode 和本次来源，所有首选与降级调用共用 8 次硬上限。成功降级保留实际混合 mode、对应缓冲和安全 warning，未采用的首选失败不污染最终来源/错误；失败按首选不可用、降级耗尽、坐标缺失、结果非法或调用预算耗尽输出无值诊断。前端已接受 `planning → needs_input`。专项链 479 项、前端 65 项通过；冻结 Python 3.13.3、Node.js 22.16.0、pnpm 11.19.0 下统一门禁完整通过，包含后端 842 项、前端 65 项和文档检查器 23 项。本 Step 没有读取凭证、调用真实 provider、执行 live UAT、暂存、提交、推送或修改 PR；Step 45M 的历史 UAT `FAIL` 保持不变。

补充 Step 45O 独立审查发现 Step 45N 仍有四类 live 阻塞：provider-wide 路线错误会盲目 fallback；路线阶段 deadline 异常被 broad catch 发布为 `internal_error`；距离/时长没有统一安全上界；wrong-provider、无效或未引用来源可能进入公开投影，且路线 diagnostic 可能误附到 POI 错误。补充 Step 45P 已以纯离线最小修复关闭这些路径：只有业务空结果和无 provider error 的本地非法路线允许降级；路线按最多两路并发分批且共享 8 次预算，deadline 以 `route_deadline_exhausted` 安全失败；距离/时长冻结为 `2147483647` 米与 `1440` 分钟；路线 provider、端点、mode、数值和来源精确一致后才能进入 scheduler/公开投影；路线错误与其他高德操作分别归属。专项 157 项及统一门禁通过，统一入口包含后端 859 项、前端 65 项、文档检查器 23 项和全部静态、类型、构建、依赖及文档契约检查。Step 45M 历史 UAT 仍为 `FAIL`，本 Step 没有 live、暂存、提交、推送或修改 PR。

补充 Step 45Q 已完成 Step 45P 的独立纯离线复审，结论为 `DONE_WITH_BLOCKERS`。复审证明同一两路并发批次若同时出现 provider-wide terminal 错误与可降级结果，上层仍会为后者启动 walking fallback；另证明裸 `asyncio.gather` 在一路抛出非治理异常时不会取消并等待同批 peer，执行器可能先发布 `internal_error`，而另一路 Provider 调用仍在运行。两项均为 P1，阻塞新 live、PR ready 和 Step 46；复审没有读取凭证、访问真实 Provider 或修改代码。

补充 Step 45R 已以最小纯离线修复关闭上述两项 P1：路线批次现在显式返回 batch-level terminal 状态，当前已在途批次允许完成，但任何 terminal 均阻止后续首选批次与全部 fallback；业务 `EMPTY_RESULT` 与无 Provider error 的本地非法路线仅在整批无 terminal 时允许降级。并发 task 任一路异常时，所有未完成 peer 会先被取消并完整 drain，再传播原异常；纵向测试证明终态发布前 `active_route_calls == 0`，且没有后续路线调用。新增红测在修复前稳定失败，修复后 10 项定向回归和 182 项路线专项通过；统一门禁通过后端 869 项、前端 65 项、文档检查器 23 项及全部静态、类型、构建与文档契约。Step 45M 历史 UAT 仍为 `FAIL`；本 Step 未调用真实 Provider、暂存、提交、推送或修改 PR。

补充 Step 45S 已完成独立只读复审。工作区仍为相对 `bb52adea871c6cadc21ceaa5ef4255b79c3904cb` 的 26 个已跟踪未暂存文件、`+1574/-98`，暂存区与未跟踪文件为空；PR #4/#5 均保持 Draft，PR #5 仍指向该提交。复审未发现 P0/P1 生产缺陷，确认 batch-level terminal、异常 peer cancel/drain、governor 归零、错误优先级、retryable 和来源投影符合冻结语义；专项 233 项与统一门禁再次通过，统一入口仍为后端 869 项、前端 65 项和文档检查器 23 项。一次不落盘的外部任务取消探针也证明两路 peer 均被取消、活动许可归零且无遗留任务。剩余非阻塞收口项是把外部取消和 terminal 出现在 fallback 批次的行为固化为仓库测试，以及修正架构文档把 Step 45R 完成的语义仍归于 Step 45N–45P 的文字漂移；二者不阻塞一次受控 live，但在提交和 PR ready 前应关闭。Step 45M 历史 UAT `FAIL` 不变，本 Step 未调用真实 Provider、暂存、提交、推送或修改 PR。

补充 Step 45T 已在用户批准的一次任务、DeepSeek 3、高德 16（路线 8）、和风 4 及总费用不超过 12 元边界内完成。执行前 26 文件、`+1592/-98`、空暂存、PR #4/#5、既有 CI、凭证隔离及三家 Provider/执行器 `ready` 均通过；没有独立 Provider 探针。唯一任务形成完整双日、每天 2 项活动和每天 3 段合法公交路线的 `partial` 计划，时间窗口、无重叠、住宿往返、路线时长和固定缓冲均通过；3 项费用保持 unknown，已知合计 520 元，预算为 `budget_indeterminate`，未按 0 处理。公开来源计数为 user 1、system 1、高德 9、和风 2、DeepSeek 1；没有错误、violation、retry 或第二个任务。本次全部必要公交路线直接可用，因此未触发步行 fallback；该条件分支仍只有离线证据。桌面 `1280×720` 的 `scrollWidth=1265`，窄屏 `390×844` 的 `scrollWidth=375`，均无水平溢出；来源、freshness、AI 披露、安全提示与返回修改入口可见，控制台无 error/warning，DOM 无秘密模式。临时视口已恢复，本地服务已停止，未保存截图、原始响应、真实地点/路线明细或持久缓存。真实 UAT 结论为 `PASS`；其提交前收口已由 Step 45U 完成，Step 46 仍等待提交、推送、远程 CI 和 stacked PR 处理。

## 范围

### 包含

- 每个请求只包含一个中国大陆城市、连续两个自然日和一个夜晚；
- 1 至 8 名同行者；
- 步行、公共交通或二者混合；
- 高德城市解析、基础 POI 和市内路线；
- 和风天气 7 日预报范围内的逐日天气和请求时正在生效的预警；
- `deepseek-v4-flash` 结构化规划；
- 日期、时间、地点、路线、预算、来源和引用完整性校验；
- `ready`、`partial`、`conflict`、`needs_input` 和 `failed` 终态；
- 轻量 Web 表单、真实处理阶段、结果卡、来源、未知项、冲突、失败和重试；
- 进程内临时任务状态、离线替身、失败注入、受控 live smoke 和用户 UAT。

### 非目标

- 多城市、跨城路线规划或自动取得城际报价；
- 正式 SQLite 业务表、migration、历史计划或重启恢复；
- 局部重规划；
- 酒店实时价格、库存、预订、票务、支付或订单；
- 登录、复杂用户系统或多人协作；
- 出租车实时价格、自驾停车规划、复杂地图、图片或 PDF；
- 多 Agent、通用 MCP 工具、SSE、WebSocket、正式任务队列或公网部署。

## 输入、输出和可观察状态

### 输入

`TripPlanRequest` 至少包含：

- 城市、开始日期、同行人数、总预算；
- 偏好、节奏、交通模式、住宿区域或住宿 POI；
- 两天各自的可用时间窗口；
- 可选住宿费用和城际往返费用；
- 可选硬约束；
- `client_request_id`。

输入约束：

- 日期按 `Asia/Shanghai` 解释，只接受从当地 D+1 至 D+5 开始的连续两天；
- 人数为 1 至 8；金额为人民币 `Decimal` 且最多两位小数；
- 偏好标签最多 5 个，自由文本最多 200 字；
- 城市必须唯一解析到中国大陆行政区，住宿锚点必须在该城市内；
- 默认时间窗口和餐饮预算必须在 UI 明示且允许修改，不能作为隐藏假设。

### 输出

`TripPlanResponse` 至少包含：

- `job_id`、`trace_id`、`status`、`attempt` 和请求摘要；
- 已解析目的地、两日计划、交通段、天气和当前预警；
- 分类费用、已知合计、未知项和预算可判定性；
- 约束冲突、警告、不确定性、来源、获取时间与数据时效；
- 是否可重试及安全的恢复动作。

每个外部事实必须引用已有 `source_id`。LLM 不得自行创建来源、坐标、路线时间或 `verified` 费用。

### 状态机

```text
draft
  → normalizing
  → needs_input | collecting
  → planning
  → enriching_routes
  → validating
  → ready | partial | conflict | failed
```

- 只有应用层状态机能够改变状态；provider 和 LLM 不能自行宣告成功。
- 相同 `client_request_id` 与相同请求体在进程存活期间去重；相同 ID 对应不同请求体返回 `409 idempotency_conflict`。
- 重试增加 `attempt` 并生成新 `trace_id`；服务重启后临时任务消失是已知限制。

## 数据模型和稳定边界

至少规划以下项目自有模型：

- `TripRequest`、`TravelerPreferences`、`AccommodationRequirement`；
- `LocationRef`、`PoiCandidate`、`RouteLeg`；
- `WeatherSnapshot`、`WeatherAlert`；
- `ItineraryItem`、`PlanDay`、`TripPlan`；
- `Money`、`CostItem`、`BudgetSummary`；
- `SourceRecord`、`Uncertainty`、`ConstraintViolation`、`ProviderResult`；
- `PlanningJob`、`PlanningTraceSummary`。

F-001 只定义 `PlanningJobRepository` 端口和进程内实现，不建立 SQLite 业务 Schema。领域层不得依赖 FastAPI、React、SQLite、第三方 SDK 或 provider 响应类型。

## 费用规则

费用状态只允许：`verified`、`estimated`、`user_provided`、`unknown`。

- `unknown.amount` 必须为空，绝不能用 `0` 表示缺失；
- `known_total` 只累加存在金额的费用；
- 已知费用已超过预算时为 `over_budget`；存在未知费用且已知费用未超限时为 `budget_indeterminate`；
- UI 只能显示“已知费用后的暂余”，不能把它描述为最终余额；
- 住宿与城际往返由用户输入，否则为 `unknown`；
- 餐饮费用由用户自行决定，UI 默认 `100 元/人/天`，按人数和天数计算；确认后的规则结果标记为 `estimated`；
- 公交无可靠票价时默认 `10 元/人/路线段`，标记为 `estimated`；
- 步行为明确规则下的 0 元，不是缺失值；
- 门票和其他费用没有可靠来源或用户输入时保持 `unknown`；
- LLM 不得临时编造价格或升级费用可信状态。

## Agent、工具和 provider 边界

采用一个 `TravelPlanningOrchestrator`、多个简单领域工具和显式状态机，不引入多 Agent 或 Agent 框架。

白名单工具：

- `resolve_city`
- `search_pois`
- `get_weather_forecast`
- `get_current_weather_alerts`
- `calculate_routes`

LLM 负责需求理解、受控工具选择、候选计划和解释；代码负责输入规范化、工具授权、调用预算、响应转换、路线补全、全部确定性校验和终态裁决。工具不提供通用 HTTP、文件、Shell、SQL 或 Repository 写入能力；provider 文本始终作为不可信数据处理，不能进入 system prompt。

D-009 已实现：LLM 不再负责最终 `start_time`/`end_time`；它只提议 POI、顺序、优先级、必选/可选、时长类别和解释。高德返回实际路线，确定性调度器据此生成时间，现有 `DailyRoutePlan` 和 final validation 再独立复验。

职责边界：

- DeepSeek：只负责理解、编排、候选和解释，不是真实事实或预算裁决来源；
- 高德：地理编码、基础 POI 和路线，不负责酒店库存、实时房价、天气或预算裁决；
- 和风天气：逐日天气和当前预警，不负责 POI、路线、费用或规划；
- MCP：F-001 不引入。只有未来出现跨宿主复用和独立权限收益时重新评估。

## 外部调用预算、超时和重试

单个规划任务的硬上限：

| 服务 | 正常逻辑调用 | 最大 HTTP 尝试 |
| --- | ---: | ---: |
| DeepSeek `deepseek-v4-flash` | 1 次生成，最多 1 次结构修复 | 3 |
| 高德 | 1 次城市解析、最多 3 次 POI、最多 8 个路线段 | 16 |
| 和风天气 | 1 次预报、1 次当前预警 | 4 |

- “DeepSeek 3”仅表示最多 3 次 HTTP 尝试，模型始终是 `deepseek-v4-flash`。
- 高德与和风天气单次超时 6 秒，DeepSeek 单次超时 35 秒，任务总时限 90 秒；路线并发最多 2。
- 仅超时、429 和 5xx 可在剩余时限与预算内重试一次；401、403、Schema 错误和业务空结果不盲目重试。
- DeepSeek 默认显式关闭 thinking；使用正式 Base URL 和本地严格 Schema，不启用需要 `/beta` 的服务端 strict 工具模式。
- DeepSeek 输出结构失败最多修复一次；修复后仍失败则进入 `failed`。

## API 和前端边界

后端计划接口：

- `POST /api/trip-plans`：创建任务并返回 `202`、`job_id` 和当前状态；
- `GET /api/trip-plans/{job_id}`：返回当前阶段或最终结果；
- `POST /api/trip-plans/{job_id}/retry`：仅对可重试终态创建下一尝试；
- 保留 `/api/health`。

前端只实现表单、处理阶段、两日计划卡、路线摘要、天气与当前预警、分类费用、来源、未知项、冲突、错误和重试。桌面 1440×900 与窄屏 390×844 均需验收；不实现地图组件。产品 UI 必须先经用户批准和冻结参考稿，健康诊断页不是产品视觉基线。

## 确定性校验

- 日期必须为请求中的连续两天，并由天气响应实际覆盖；
- 活动不得重叠或超出每日窗口，路线时长必须能放入相邻活动之间；
- Day 1 返回住宿锚点，Day 2 从住宿锚点开始；
- POI 必须属于解析城市并来自候选集；路线起终点必须匹配相邻地点；
- 路线缺失时不能宣称时间已完全验证，可形成 `partial`；
- 金额只使用 Decimal，未知费用不进入合计；
- 每个 provider 事实必须拥有来源、获取时间和有效期或“有效期未知”说明。

终态规则：

| 状态 | 判定 |
| --- | --- |
| `ready` | 全部硬校验通过，关键数据完整且预算可判定 |
| `partial` | 计划可使用，但天气、路线、费用或非关键数据不完整 |
| `conflict` | 已知预算超限、时间不可行或硬约束不能同时满足 |
| `needs_input` | 城市歧义、日期越界或缺少必要用户决定 |
| `failed` | 城市、POI、模型等关键链路无法形成安全计划 |

## 凭证、权限和安全边界

- 服务仅绑定 `127.0.0.1`；不创建账号、不登录、不付费、不部署公网；
- `.env.example` 只保存空占位；真实值只进入被 Git 忽略的本地配置；
- 不读取或复制 Agent1 的 `.env`；
- 日志、响应、DOM、截图、fixture 和 evidence 不得包含 Key、JWT、私钥、Authorization、完整敏感 URL、完整 prompt 或原始敏感响应；
- 和风天气私钥使用本地路径引用，不将 PEM 内容放入环境模板或仓库；
- 默认测试和 CI 完全离线，CI 中 provider 凭证保持为空；
- 真实 API 必须在专门 Step 再次取得用户授权。
- 用户根据高德工程师电话沟通明确确认：本项目的个人、非商业、本地自用查询和组合展示属于允许范围；只保留页面需要的进程内转换结果，程序重启后消失，不保存原始响应、不建立持久缓存、不公开部署、不传播真实数据截图。包含高德来源时，页面必须固定显示“数据来源：高德地图”及官方链接。

首次 live smoke 只允许一次完整计划：DeepSeek 最多 3 次、高德最多 16 次、和风最多 4 次，总费用上限人民币 12 元。该上限覆盖 2026-08-17 DeepSeek 峰谷价下约 9.274 元的保守高峰估算并保留余量；执行前仍须重新核价。不能确认权限、配额、条款或计费时立即停止。

## 测试与验收

测试矩阵至少覆盖：

- 输入和动态日期边界；
- Decimal、费用状态、未知不为零和用户餐饮预算；
- 时间重叠、路线连续性、城市范围和来源引用；
- 五个业务终态与非法状态转换；
- 幂等、重试预算、超时和停止；
- DeepSeek 非法 JSON、候选集外 POI、虚构来源、一次修复和提示注入；
- provider 成功、空数据、401/403、429、超时、5xx、Schema 漂移和过期数据；
- 前端 happy、partial、conflict、needs_input、failed、重试和防重复提交；
- 桌面、390px 窄屏、键盘可用性和敏感数据不进入 DOM；
- 至少一次经授权的真实 API 冒烟和真实数据 UAT；
- 独立 QA、PR review、统一门禁和远程 CI。

离线 fake 必须明确标记为 synthetic，不能冒充录制的真实响应。真实 provider 测试默认关闭，不进入常规 CI。

## 文件影响范围

允许在本任务分支修改：

- `backend/pyproject.toml`、`backend/uv.lock` 和 `backend/src/intelligent_travel_assistant/`；
- `backend/tests/`；
- `frontend/src/`、`frontend/package.json` 和 `pnpm-lock.yaml`；
- `.env.example`、`scripts/`、必要的 CI 配置；
- 当前权威产品、架构、技术、设计、Agent、测试和项目管理文档。

禁止修改 Agent1、`E:\Agent\zonghe-anli`、真实 `.env`、系统配置、无关项目、生产配置或 SQLite 业务 Schema/migration。

## 文档更新契约

- Step 状态同步 `current-task.md`、`implementation-plan.md` 和 `progress.md`；
- 产品、架构、技术、设计、Agent、测试或长期决策变化时更新对应唯一权威文档；
- 最终可复现验收写入 `evidence.md`；
- 任务完成后将任务卡与实施计划归档，roadmap 仅保留结果摘要；
- 不把聊天、完整终端输出或敏感 provider 响应当作项目事实。

## 风险、回滚和停止条件

主要风险包括 provider 版本/字段/坐标漂移、和风权限不足、POI 非权威营业与票价信息、天气时效、模型虚构、重试费用、90 秒体验、进程重启丢失任务和外部文本提示注入。

回滚依赖功能分支、端口和默认 fake 模式；F-001 不建立数据库迁移。不得使用破坏性 Git 或文件清理命令。

出现以下任一情况必须停止并请求批准：扩大到多城市、酒店库存/票务/支付、第二 Agent、正式 SQLite 持久化、公网或登录；首次真实 API smoke 费用可能超过 12 元；条款不允许当前存储/展示；关键坐标或字段语义无法确认；需要把通用 HTTP/MCP 暴露给 LLM；预计超过约 70 个修改文件或 5000 行净新增；同一阻塞连续出现三次。

范围停止条件已于 2026-08-14 触发并完成处置：用户批准当前 120 个 F-001 变更文件作为一个完整垂直切片 PR 的一次性例外。该批准不覆盖 Step 42 后的新范围扩张；任何新增目标外文件或能力仍必须停止并重新确认。

## 验收标准

1. 用户能在本地 Web UI 提交一个中国大陆城市的双日需求并看到真实处理阶段。
2. 系统可通过 fake 完整证明 ready、partial、conflict、needs_input 和 failed。
3. 计划只能引用工具提供的 POI、路线、天气和来源。
4. 日期、时间、路线、Decimal 预算与 unknown 规则由确定性代码校验。
5. 餐饮费用可由用户决定，默认 100 元/人/天且明确标记为估算。
6. 至少一个 provider 不可用时产生符合规则的 partial 或 failed，而不是虚构完整结果。
7. UI 显示来源、更新时间、不确定性、未知费用、冲突和可用恢复动作。
8. 默认测试、统一门禁和 CI 不访问真实 provider，不需要真实凭证。
9. 用户单独授权后，一次受控 live smoke 可生成杭州标准验收计划，结果允许为透明且合理的 `partial`。
10. 桌面与窄屏 UAT、独立 QA、PR review、统一门禁和远程 CI 均无阻塞问题。

## 完成定义

范围内实现、离线门禁、失败矩阵、Agent 评估、设计验收、浏览器 UAT、独立 QA、真实 API 冒烟、真实数据 UAT、远程 CI、文档和 evidence 必须全部完成；随后经用户分别批准提交、推送、PR、合并和归档，F-001 才能标记 `DONE`。只有离线实现时应记录为受 live gate 阻塞，不能宣称任务完成。

## Step 地图

| Step | 目标 | 当前状态 |
| --- | --- | --- |
| Step 0 | 复核 main、CI、文档状态和三方官方契约 | DONE |
| Step 1 | 创建并切换功能分支 | DONE |
| Step 2 | 固化任务卡、激活 roadmap 并修正文档漂移 | DONE |
| Step 3 | 冻结 API、DTO、状态和错误码契约 | DONE |
| Step 4 | 建立杭州双日 happy、partial、conflict、failed 验收样例 | DONE |
| Step 5 | 为金额、来源、POI、路线和天气定义严格领域模型测试 | DONE |
| Step 6 | 实现并验证日期和输入约束 | DONE |
| Step 7 | 实现并验证时间窗口和重叠校验 | DONE |
| Step 8 | 实现并验证路线连续性校验 | DONE |
| Step 9 | 实现并验证 Decimal 预算和 unknown 规则 | DONE |
| Step 10 | 建立 provider result、错误分类和 freshness 模型 | DONE |
| Step 11 | 建立高德、和风和 DeepSeek 端口 | DONE |
| Step 12 | 建立可编程 fake adapter | DONE |
| Step 13 | 实现状态机及非法状态转换测试 | DONE |
| Step 14 | 实现离线应用编排闭环 | DONE |
| Step 15 | 实现工具白名单、调用预算和超时边界 | DONE |
| Step 16 | 实现 DeepSeek 严格输出和单次修复测试 | DONE |
| Step 17 | 实现路线补全和最终确定性校验 | DONE |
| Step 18 | 实现进程内任务 Repository 和幂等规则 | DONE |
| Step 19 | 实现 POST、GET 和 retry API | DONE |
| Step 20 | 验证 API 五种终态与安全错误 | DONE |
| Step 21 | 起草产品 UI 设计稿 | DONE |
| Step 22 | 用户批准并冻结桌面和窄屏 UI 参考 | DONE |
| Step 23 | 实现旅行需求表单 | DONE |
| Step 24 | 实现轮询和真实处理阶段显示 | DONE |
| Step 25 | 实现双日计划、天气、路线和预算卡片 | DONE |
| Step 26 | 实现来源、不确定性、冲突和错误界面 | DONE |
| Step 27 | 实现重试、防重复提交和窄屏布局 | DONE |
| Step 28 | 实现 DeepSeek adapter 及离线契约测试 | DONE |
| Step 29 | 实现高德地理编码和 POI adapter | DONE |
| Step 30 | 实现高德路线 adapter | DONE |
| Step 31 | 实现和风预报和当前预警 adapter | DONE |
| Step 32 | 建立配置加载、凭证隔离、脱敏和启动检查 | DONE |
| Step 33 | 运行完整 provider 失败注入矩阵 | DONE |
| Step 34 | 运行 Agent 结构化输出和确定性评估 | DONE |
| Step 35 | 验证离线前后端浏览器闭环 | DONE |
| Step 36 | 运行全量本地门禁 | DONE |
| Step 37 | 检查外部账户、配额、条款和费用上限 | DONE |
| Step 38 | 经用户单独批准后执行受控真实 API 冒烟 | DONE |
| Step 39 | 执行真实数据桌面和窄屏 UAT | DONE |
| Step 40 | 独立 QA、测试审查和 PR review | DONE |
| Step 41 | 修复阻塞问题并重复门禁 | DONE |
| Step 42 | 更新 evidence、progress、架构和决策文档 | DONE |
| Step 43 | 精确暂存并创建本地提交 | DONE |
| Step 44 | 经用户批准后推送并创建 Draft PR | DONE |
| Step 45 | 等待远程 CI 并修复阻塞问题 | DONE |
| 补充 Step 45A | 修复后的受控真实数据 UAT 回归 | DONE（UAT FAIL） |
| 补充 Step 45B | 离线定位并修复 DeepSeek 候选本地校验可靠性 | DONE |
| 补充 Step 45C | Step 45B 后受控真实数据 UAT 回归 | DONE（UAT FAIL：route conflict） |
| 补充 Step 45D | 离线修复候选时间安排与路线连续性不一致 | DONE |
| 补充 Step 45E | Step 45D 后最后一次受控真实数据 UAT | DONE（UAT FAIL：repair time invalid） |
| 补充 Step 45F | 离线细化候选时间诊断并确定时间规划责任边界 | DONE（结论已进入 D-009） |
| 补充 Step 45G / F-001-CR1 | 确定性时间排程责任调整的变更控制与详细设计 | DONE（设计、九项策略和范围已批准） |
| 补充 Step 45H | 实施并离线验证 F-001-CR1 | DONE |
| 补充 Step 45I | 独立离线 QA 与 stacked PR 前审查 | DONE（无 P0/P1；P2 测试与文档缺口阻塞交付） |
| 补充 Step 45J | 修复 Step 45I 的最小离线测试与文档缺口 | DONE（测试与文档 findings 已关闭） |
| 补充 Step 45K | 精确暂存、提交、推送并创建 stacked Draft PR | DONE（PR #5 CI 通过） |
| 补充 Step 45L | stacked Draft PR 独立远程 review 与真实 UAT 准入判断 | DONE（无 UAT 阻塞代码 finding） |
| 补充 Step 45M | D-009 后受控真实数据 UAT | DONE（UAT FAIL：高德路线数据缺失） |
| 补充 Step 45N | 离线修复多交通方式降级、安全诊断和前端状态边 | DONE（无 live） |
| 补充 Step 45O | 独立离线 review 与真实 UAT 准入判断 | DONE（发现路线可靠性阻塞，不准入 live） |
| 补充 Step 45P | 最小离线路线可靠性修复 | DONE（无 live） |
| 补充 Step 45Q | Step 45P 独立离线复审与真实 UAT 准入判断 | DONE_WITH_BLOCKERS（发现两项并发停止 P1，不准入 live） |
| 补充 Step 45R | 最小离线并发停止语义修复 | DONE（无 live；待独立复审） |
| 补充 Step 45S | Step 45R 独立离线复审与真实 UAT 准入判断 | DONE_WITH_CONCERNS（无 P0/P1；准入一次单独授权的受控 live） |
| 补充 Step 45T | Step 45R 后受控真实数据 UAT | DONE（UAT PASS：完整双日 partial） |
| 补充 Step 45U | 关闭 Step 45S 非阻塞测试与文档缺口并完成提交前门禁 | DONE（无 live；待精确提交） |
| 补充 Step 45V | 精确暂存、提交、推送并更新 stacked Draft PR #5 | DONE（commit `749acc9`；CI 通过） |
| 补充 Step 45W | PR #5 新 head 独立远程复审与 stacked PR 收口判断 | DONE（无 P0/P1；文档收口后可 ready） |
| 补充 Step 45X | 最终文档收口、PR #5 元数据校正与 ready-for-review | DONE（文档提交、CI 和 ready 状态已完成） |
| Step 46 | 经用户批准后合并 | TODO |
| Step 47 | 归档 F-001 并完成文档收口 | TODO |

完成当前 Step 后停止，不自动进入下一 Step。
