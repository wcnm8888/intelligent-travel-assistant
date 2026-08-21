# 项目 Roadmap

## 使用规则

本文件是 Intelligent Travel Assistant 的项目级候选任务和优先级入口，不是任务批准记录。

- 执行期同一时刻最多只有一个 `ACTIVE` 任务；任务关闭、等待用户选择时允许没有活动任务；
- `CANDIDATE` 表示方向已进入路线图，不代表任务卡、范围或实现 Step 已批准；
- 用户必须从 roadmap 选择任务，再起草并批准 `current-task.md`；
- 不得因为前置任务完成而自动开始下一任务；
- 产品范围或架构边界变化时，先更新产品/架构文档并获得确认，再调整 roadmap；
- 已完成任务只保留一行结果摘要，完整任务卡进入 archive。

状态值：`ACTIVE`、`CANDIDATE`、`BLOCKED`、`DONE`、`DROPPED`。

## 当前阶段

目标：B-000、F-001、F-002、F-003、F-004A、F-004B1 和 F-005 已完成归档；F-004B2 已以 `BLOCKED` 状态归档。F-004C 是当前唯一 `ACTIVE` 任务，后续候选为 F-006。

| 顺序 | 任务 | 状态 | 用户价值 | 关键依赖 |
| --- | --- | --- | --- | --- |
| 0 | B-000 项目与工程基线 | DONE | 已建立可开发、可运行、可验证、可交接的本地工程底座；PR #1 已合并 | 无 |
| 1 | F-001 单城市双日旅行计划垂直切片 | DONE（产品状态 PARTIAL） | 用户能用真实天气、POI 和路线生成第一份可校验计划 | B-000、外部服务就绪门禁 |
| 2 | F-002 计划持久化、来源与版本 | DONE | 用户能保存、恢复和追踪计划版本及来源 | F-001 |
| 3 | F-003 局部重规划与影响确认 | DONE | 用户能调整当天，并在跨日/跨城影响前掌握决定权 | F-002 |
| 4 | F-004A 单城市 2–7 日计划扩展 | DONE | 用户可生成更长但仍可控、可追溯的单城市行程；PR #13/#16/#17 已依序合并 | F-003 |
| 5 | F-004B1 多城市领域、用户提供的城际段与离线约束 | DONE | 用户可表达 2–3 城顺序、住宿切换和用户提供的相邻城际段 | F-004A、D-013、归档任务卡 |
| 6 | F-005 外部服务韧性、时效与 Agent 评估 | DONE | provider 失败或数据过期时仍得到可信、可恢复结果 | F-001 至 F-004B1、D-014、归档任务卡 |
| 7 | F-004B2 真实城际 Provider 与可信城际事实 | BLOCKED | 经正式书面授权 Gate 后，为相邻城市段提供来源和时效可信的同日直达 rail 参考事实 | D-015 Step 1：SQLite 持久化禁止且 rail 字段授权不足 |
| 8 | F-004C 用户已购铁路段与车次信息 | ACTIVE | 用户可录入已购票的相邻铁路段和车次事实，并继续按用户提供、未核验语义规划 | F-004B1、F-004B2 BLOCKED closure、D-016 |
| 9 | F-006 MVP 体验收口与本地验收 | CANDIDATE | 用户可稳定完成完整本地旅行决策流程 | F-001 至 F-005；F-004C 完成后进入 |

B-000 至 F-005 的已选任务均已完成归档。F-004B2 已阻塞归档；F-004C Step 0–5 已完成，是当前唯一活动任务。Step 6 已获单独批准并执行三层交付与归档；F-006 不得自动启动。

## B-000：项目与工程基线

- 状态：`DONE`
- 结果：文档、前后端健康骨架、依赖锁定、离线测试、统一门禁和 CI 配置已由 PR #1 交付；PR #2 完成归档收口，最终 `main` CI 通过。
- 归档任务卡：[B-000 project baseline](../archive/task-cards/B-000-project-baseline.md)。
- 非目标仍未实现：旅行规划业务、真实 provider 调用、SQLite 业务 Schema和正式产品 UI。

## 推荐首个垂直切片

### F-001：单城市双日旅行计划垂直切片

- 状态：`DONE`（产品验收状态：`PARTIAL`）
- 推荐原因：用最小的日期和地理范围同时验证真实数据、模型编排、确定性校验、来源、预算和 Web UI，能最快暴露架构是否成立；
- 用户输入：一个中国大陆城市、连续两天、同行人数、总预算、偏好、交通要求、住宿区域或 POI、用户提供的住宿价格；
- 外部数据：高德地理编码/基础 POI/市内路线，和风天气预报/预警，DeepSeek 结构化规划；
- 输出：两日结构化计划、交通段、天气提示、全部费用类别、来源、更新时间、未知项和冲突；
- 确定性校验：日期、活动时间、路线衔接、费用状态、已知预算和必要来源；
- 降级：至少覆盖一个 provider 不可用或数据缺失的 `partial` 结果；
- UI：轻量输入、分阶段处理、计划结果、来源/未知项和错误重试；
- 酒店边界：只使用基础 POI、用户输入价格或明确估算，不接实时库存和预订；
- 数据边界：首切片可不持久化正式计划，但输出模型必须为 F-002 的 Repository 保留稳定边界；
- 非目标：跨城市、局部重规划、自动预订、复杂地图、图片、PDF 和多 Agent。
- 当前交付状态：D-009/F-001-CR1 已由 PR #5 先合并至功能分支，再由 PR #4 合并至 `main`；独立 review、Windows CI 和 Step 45T 真实 UAT 通过。Step 45T 形成完整双日、仅因非关键 unknown 为 `partial` 的计划，Step 45M 历史 `FAIL` 保留。F-001 已交付并归档，但产品状态仍为 `PARTIAL`；门票等 unknown 不按 0 处理，混合交通 fallback 仅有离线证据；
- 范围处置：用户已批准 F-001 作为一个完整垂直切片由单一 PR 交付，并接受截至 Step 41 的 120 个变更文件任务级范围例外；该例外不扩大产品范围，也不降低 review、CI 或安全门禁。Step 45H 采用 stacked PR，并获批新增 24–34 个文件影响；Step 45J–45V 的后续测试、可靠性和文档变更均有逐项批准。PR #4 最终相对 `main` 为 124 文件、`+34079/-584` 的累计差异，已在 Step 46 完成独立 review 和 CI 复验，不作为后续任务的自动范围授权。

F-001 的精确城市、日期限制、API 合约、调用预算、验收 case 和任务等级必须在独立任务卡中批准，roadmap 不代替该决策。

## 后续候选任务

### F-002：计划持久化、来源与版本

- 状态：`DONE`（PR #6 已合并至 `main`，合并提交 main CI 已通过，任务已归档）
- 目标：使用 SQLite 和 Repository 保存旅行请求、计划版本、费用、来源、trace 和 decision；
- 核心价值：关闭应用后仍能恢复计划，重规划和审计有稳定基线；
- 必须验证：Schema、迁移、事务、版本冲突、Decimal/时间往返、旧版本只读和临时数据库测试；
- 非目标：云同步、多用户、登录和生产数据库。
- 交付边界：已实现 SQLite 连接、migration runner、初始 schema、持久化 Repository、现有 POST/GET/retry API 装配、单计划 DELETE、job 级级联、migration 后有界 30 天清理、typed acceptance record 和隐私拒绝。attempt 1 标识保持兼容，retry 使用 attempt/trace 命名空间隔离 plan/source 标识；真实执行器 → SQLite → retry → 第二计划版本纵向离线回归和全量门禁通过。历史列表、版本比较/恢复、清空全部数据和前端历史能力仍不在范围内。
- 归档任务卡：[F-002 plan persistence, source and version](../archive/task-cards/F-002-plan-persistence-source-version.md)。

### F-003：局部重规划与影响确认

- 状态：`DONE`（PR #7、#10、#11 已合并，完整功能 main CI run `31939222646` 通过，任务已归档）
- 目标：支持替换、删除或调整某日活动，并基于依赖计算影响范围；
- 核心价值：当天内部修改可自动完成，高影响变更先由用户确认；
- 必须验证：same-day、adjacent-day、cross-city、accommodation、unknown、取消确认和版本 diff；
- 非目标：多人协作、自动购买替代票务和无确认跨日改写。
- 当前批准边界：保持单城市双日；支持替换、删除、调整时间和同日顺序，不新增活动、不修改城市/日期/住宿锚点；影响分析为确定性代码，replan lifecycle 独立于现有 PlanningJob status；高影响确认有效期 15 分钟；成功只追加新版本，不提供历史列表、任意版本比较或恢复；默认测试完全离线。
- Step 1 冻结结果：八类可组合 impact、十状态独立 lifecycle、三个窄 API、migration v2 两张新表、独立 ReplanRepository、分层测试矩阵和现有结果页内 UI 契约均已冻结；未实施代码或数据库。
- Step 2 实现结果：纯领域 command、impact、change set、预算重算和来源 reuse/refresh/drop 策略已由 35 项新增测试锁定；领域 178 项、后端全量 981 项和静态门禁通过，尚未进入 migration、Repository、API、Provider 或 UI。
- Step 3 实现结果：migration v2、独立 ReplanRepository、内存/SQLite adapter 和 typed Decision 已实现；API migration 基线、专项、相关回归和后端全量 963 项通过，尚未进入 application service、公开 API 或 UI。
- Step 4 实现结果：application replan、确认/取消/过期、provider-neutral 离线执行和 SQLite 原子版本提交已实现；同 baseline 并发只允许一个提交成功，失败路径保持原计划；专项 19 项、application+persistence 494 项和后端全量 1001 项通过，尚未进入公开 API、Provider adapter 或 UI。
- Step 5 实现结果：三个窄 replan API、严格 DTO、安全错误映射、background execution 快照和 completed result/change-set 投影已实现；专项 31 项、相关回归 571 项和后端全量 1016 项通过，尚未进入前端 UI。
- Step 6 实现结果：结果页内四种结构化修改、影响预览、确认/取消、completed diff、unknown/partial、安全失败和焦点恢复已实现；前端 73 项与静态/build 门禁通过。
- Step 7 验收结果：临时 SQLite 纵向、loopback 浏览器和独立安全/数据审查完成；trace 水合与 stale confirmation 问题已按最小授权修复。相关回归 219 项、后端全量 999 项、前端 73 项及静态/build 门禁通过；Schema、migration、公开 API、Provider、前端和隐私边界未改变。
- Step 8 交付结果：最终本地门禁通过后端 1007、前端 76、文档检查器 24 及全部静态、类型和 build 检查；loopback synthetic UAT 通过；stacked PR #7、#10、#11 按依赖顺序合并，main CI 通过；完整任务卡见 [F-003 archive](../archive/task-cards/F-003-local-replanning-impact-confirmation.md)。

### F-004A：单城市 2–7 日计划扩展

- 状态：`DONE`；Step 0–7 已完成，PR #13/#16/#17 已依序合并，完整功能 main CI run `32359762190` 通过；
- 目标：在保持单城市和一个住宿锚点的前提下，把旧双日规划扩展为连续 2–7 日；
- 核心价值：覆盖周末以外的常见短途行程，同时先验证日期、调用预算、天气和 UI 是否能安全扩展；
- 兼容：旧双日 API、请求指纹、已保存数据和 F-003 replan 边界不变；新请求使用严格 version 2 形状；
- 必须验证：可变日期/窗口、每日最多 2 项、确定性排程、预算按日/夜计算、天气缺日 partial、来源/unknown、重启恢复和旧数据回归；
- 数据与架构：继续使用 SQLite schema v2 和 typed JSON；没有关系型查询需求证据时不增加 migration v3；
- 非目标：多城市、同日跨城、跨夜活动、城际 Provider、版本比较/恢复、历史列表、登录/同步/公网和真实 Provider UAT；
- 交付：三层 stacked PR，squash 后从最新 main 建干净分支并只移植下一层，不 force-push 重写已审查历史。

### F-004B1：多城市领域、用户提供的城际段与离线约束

- 状态：`DONE`；Step 0–8 全部完成，完整任务卡见 [F-004B1 archive](../archive/task-cards/F-004B1-multicity-domain-user-intercity-offline.md)；
- 目标：支持中国大陆 2–3 个用户排序城市、每城独立住宿锚点、连续住宿夜数和用户提供的相邻城际段；
- 边界：总行程最多 7 日，每城至少一晚；同日最多一次跨城，转移日最多一项活动；不支持跨夜、第三城市、重复城市闭合往返或自驾；
- 数据与兼容：独立 V3 typed 变体，legacy/V2/fingerprint 不变，继续使用 schema v2 typed JSON，不增加 migration v3；
- Provider：城际 Provider 调用为 0，默认测试/UAT 完全离线；真实城际事实不在本任务；
- replan：全部 V3 replan 在 Provider、decision 和版本写入前拒绝；
- 交付：PR #19/#23/#24/#25 已依序 squash merge；#20/#21/#22 由 clean-restacked PR 替代并关闭；完整功能 main `c1fecb0`、CI `32384768085` 通过，全程无 force-push。

### F-005：外部服务韧性、时效与 Agent 评估

- 状态：`DONE`；Step 0–9 全部完成，完整任务卡见 [F-005 archive](../archive/task-cards/F-005-external-service-resilience-freshness-agent-eval.md)
- 目标：系统化处理 provider 超时、限流、鉴权失败、Schema 漂移、空数据、过期数据和模型失败；
- 核心价值：失败时用户仍知道哪些数据可信、哪些缺失、能否重试；
- 必须验证：统一错误映射、重试预算、fresh/stale/unknown-validity、提示注入、工具越权和固定回归 case；
- 已批准边界：Amap/QWeather 仅可重试类最多额外一次、DeepSeek 0 传输 retry、固定 attempt/deadline/freshness/隐私与离线 Agent eval 门禁；不新增 URI/JSON 键、Schema/migration、依赖、Provider 或真实调用；
- Step 1 冻结结果：逐能力失败/freshness 矩阵、显式 job-scoped attempt runtime、bounded proposal/repair、48-case 评分、同 shape API/UI 和分层测试已形成可实现契约；交付期经批准调整为五层 stack；未修改源码或测试；
- Step 2 实现结果：纯领域 ProviderError 安全 Retry-After、Provider/operation retry schedule、budget/deadline/jitter 决策、逐能力 freshness/失败处置和闭集诊断已由 TDD 实现；尚未接入 adapter/application runtime；
- Step 3 实现结果：显式 task-scoped attempt runtime、预算/deadline/取消/peer drain 和 Amap/QWeather 安全错误/Retry-After 输入已离线实现；adapter 仍为单次交换，runtime 尚未接入 legacy/V2/V3 application；
- Step 4 实现结果：显式 runtime 已接入 legacy/V2/V3 application；统一 deadline 前置拒绝、取消/peer drain、retry/fallback 停止顺序和同 shape data_stale/timeout 投影；stale route 不成计划，stale weather/alert 剔除，未进入 Agent eval 或前端；
- Step 5 实现结果：legacy/V2/V3 repair 改用 bounded `PlanRepairBrief`，generation/repair 对 Provider 文本实行双层 allowlist；固定 48-case 离线 eval 两次一致、加权分 100、五类硬门禁失败为 0；未进入前端且不构成真实 Provider/模型 UAT；
- Step 6 实现结果：前端只消费既有 status/retryable/errors/uncertainties/sources/attempt，完成鉴权配置、暂时失败、stale、unknown-validity、固定错误排序和恢复展示；全量 99 项与静态/build 通过，未进入 SQLite/browser；
- 交付：PR #27/#28/#29/#30/#31 已依序 squash merge；后续层直接改指向最新 main 后仍保持本层 tree diff，未创建替代 PR 或 force-push；完整功能 main `fddd4e5`、CI `32452988076` 通过；归档 PR #32 已合并，最终归档 main `96f73d9`、CI `32453988289` 通过；
- 非目标：生产高可用、分布式熔断、7×24 告警和公网 SLO。

### F-004B2：真实城际 Provider 与可信城际事实

- 状态：`BLOCKED / ARCHIVED`；Step 1 已完成审核，完整任务卡见 [F-004B2 BLOCKED archive](../archive/task-cards/F-004B2-real-intercity-provider-blocked.md)；
- 目标：为中国大陆 2–3 城相邻段提供独立 V4 的同日直达 rail 查询意图，并在正式授权边界内生成来源、时效和费用可信状态明确的参考事实；
- Gate：用户提供的高德回复允许非商用 Web API 与运行期内存临时保存，但明确禁止 SQLite 持久化，且没有授权 F-004B2 所需 rail 字段；正式结论为 `BLOCKED`；
- 实现前置：没有已选 Provider；Gate 未重新 PASS 前不得进入 contracts/domain/adapter/application/API/Repository/前端实现，不得注册账号、申请 Key、付费或真实调用；
- 不变量：legacy/V2/V3 兼容，V3/V4 replan 写前拒绝，SQLite schema v2/migration 1/2，unknown 金额为 `null`；
- 非目标：air、coach、跨夜、换乘、跨境、复杂优化、抓取/逆向、余票/库存承诺、预订/支付/出票、账号/同步/云数据库和公网部署。

### F-004C：用户已购铁路段与车次信息

- 状态：`ACTIVE`；Step 0–5 已完成，Step 6 三层交付与归档执行中；
- 目标：在不接入 Provider 的前提下，让用户为中国大陆 2–3 城相邻段录入已购铁路车次、发到站、发到时间和可选票价；
- 来源：固定为 `user_provided`、`unknown_validity` 和“用户提供，未核验”，不得表述为 Provider 核验、余票或库存保证；
- 兼容：独立 `request_version="4"`、`response_version="4"` 和 `plan_format_version="4"`；legacy/V2/V3 exact shape、fingerprint、旧记录和行为保持不变；继续使用 SQLite schema v2 typed JSON，不新增 migration；
- 版本决策：D-016 只替代 D-015 中未实现的 V4 Provider union 预留，不改变 F-004B2 `BLOCKED` 历史；未来真实城际 Provider 必须使用新的版本和决策，不得与 F-004C 共用 V4；
- 输入：每个相邻段必须提供规范化 `service_number`、发到站和发到时间，票价可选；unknown 金额保持 `null`，历时只由时间确定性计算；
- 隐私：不得保存姓名、证件、联系方式、订单号、座位、二维码、Cookie、截图、原始城际文本或自由备注；`service_number` 和原始城际文本不得进入 proposal/repair；
- Provider：不接入任何城际 Provider，城际 logical call 和 HTTP attempt 均为 0；
- 非目标：Provider 查询、12306 抓取/自动读取、真实 UAT、预订/支付/出票、余票/可售、账号/同步/公网；
- 隐私收口：Step 5A 已将 V4 preferences 收窄为 interests-only strict allowlist；非法自由文本/硬约束 422 且零 job/SQLite 写入，Agent context 与前端 sentinel 回归通过，两层独立复审无 finding；
- 交付：三层 stacked PR；Step 6 已批准，必须逐层独立 review/CI、顺序合并并以最终 main CI 和归档收口。

### F-006：MVP 体验收口与本地验收

- 状态：`CANDIDATE`
- 目标：统一输入、计划、预算、来源、冲突、重规划和恢复体验，完成 MVP 本地 UAT；
- 核心价值：真实用户可在本机完整完成旅行决策流程；
- 必须验证：桌面/窄屏、可访问性、加载/空/部分/错误/确认状态、安装与恢复文档、独立 QA；
- 非目标：品牌重塑、复杂地图、图片、PDF、公网部署和交易能力。

## 外部服务就绪门禁

F-001 的真实数据验收门禁包括：

- 创建高德开放平台账户、应用和适用的 Key；
- 创建和风天气账户和项目，按已批准的 JWT 方案准备项目 ID、凭据 ID、本地 Ed25519 私钥，并从控制台确认账户专属 API Host；
- 提供本项目独立的 DeepSeek Key，不复制 Agent1 的 `.env`；
- 确认三个服务的使用条款、所需 API 权限、配额、可能费用和测试用途；
- 将凭证只放入被 Git 忽略的本地配置，不写入文档、截图、fixture、日志或 CI；
- 同意执行范围受限、次数明确的 live smoke。

上述账户、凭证、条款确认和首次 live 授权已在 Step 37–38 满足，并取得一次三家 provider 的脱敏 live 契约证据。Step 45T 已取得完整双日 partial 的通过式真实计划 UAT；这不代表长期配额、费用或混合 fallback 质量永久有效，也不授权 Codex 登录、付费或再次调用真实 API。任何新的 live 回归仍须重新确认调用次数、费用和停止条件。

## MVP 完成边界

MVP 只有在 F-001 至 F-006 中被用户实际选择、批准并完成的必要任务共同满足以下结果时才完成：

- 中国大陆境内自由行需求可结构化输入；
- 真实天气、POI、地理和路线数据通过受控适配器进入计划；
- 结构化计划通过日期、时间、路线、预算和冲突校验；
- 住宿、城际交通、市内交通、门票、餐饮等费用完整表示，未知不按零处理；
- 计划、来源和版本可恢复；
- 局部重规划遵守当天自动、高影响确认边界；
- provider 失败、数据缺失和过期有明确降级；
- 用户能在轻量 Web UI 中完成完整流程；
- 默认测试离线，live 证据带时间和未覆盖范围。

## 非 roadmap 范围

以下方向不进入当前 MVP 候选任务：

- 自动预订、支付、出票和订单；
- 酒店、票务实时库存承诺；
- 登录、复杂用户系统和多人实时协作；
- 多 Agent；
- 公网部署和生产运维；
- 复杂地图、图片、PDF 和公开分享；
- 境外旅行。

新增这些方向前必须先变更产品范围、架构和风险边界并取得用户批准。

## 依赖关系

```text
B-000 工程基线
  ↓
外部服务就绪门禁 ─────┐
  ↓                    │
F-001 首个垂直切片 <───┘
  ↓
F-002 持久化与版本
  ↓
F-003 局部重规划
  ↓
F-004A 单城市 2–7 日
  ↓
F-004B1 多城市领域与用户提供段（DONE）
  ↓
F-005 韧性与评估（DONE）
  ↓
F-004B2 真实城际 Provider 与可信事实（BLOCKED / ARCHIVED）
  ↓
F-004C 用户已购铁路段与车次信息（ACTIVE；Step 0–5 DONE，Step 6 ACTIVE）
  ↓
F-006 MVP 收口
```

依赖图表达推荐顺序，不构成自动执行授权。用户可以调整候选任务、拆分范围或暂停项目。
