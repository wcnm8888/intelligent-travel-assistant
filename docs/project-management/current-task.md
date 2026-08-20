# 当前任务

## 任务元数据

- 任务 ID：`F-004B1`
- 名称：多城市领域、用户提供的城际段与离线约束
- 等级：`L`
- 状态：`ACTIVE / APPROVED`
- 当前 Step：`Step 7 - 全量门禁与 stacked PR 交付`，状态 `TODO`，等待用户单独批准
- Step 0：`DONE`；只完成事实复核、任务激活、治理文档、状态漂移修正和首层本地分支创建
- Step 1：`DONE`；已冻结领域、V3 DTO/API、Repository/schema v2、Provider、测试和 UI 契约，未实现生产代码
- Step 2：`DONE`；已以 TDD 实现纯多城市领域与独立 V3 contracts，未接入 Repository/API、SQLite、Provider 或前端
- Step 3：`DONE`；已实现 V3 typed unions、内存/SQLite schema v2 往返、同 URI API 与全 V3 replan 写前拒绝，未进入 V3 planning/Provider 或前端
- Step 4：`DONE`；已实现离线 V3 planning、按城市复用现有 Provider ports、确定性排程与调用治理，未调用真实 Provider 或进入前端
- Step 5：`DONE`；已实现显式多城市编辑、严格 V3 parser、结果信息架构和本机 job 指针重启恢复，未进入临时 SQLite/浏览器纵向或独立审查
- Step 6：`DONE`；已完成临时 SQLite 纵向、loopback synthetic desktop/390px 浏览器 QA、网络/console/accessibility 和独立隐私兼容审查，未进入全量门禁或交付
- 基线提交：`1a3e0a050721c72a6e83941f0cb5b2077decb1c7`
- 当前本地分支：`feat/f-004b1-multicity-domain-contracts`
- 远程写入：未授权；当前未提交、不 push、不创建 PR

## 用户目标与工程价值

用户可以为中国大陆境内 2–3 个按顺序排列的城市，表达每城住宿、相邻城市间由用户提供的城际段和连续日期约束，并获得可离线保存、重启恢复、可追溯且不承诺实时票务的结构化计划。工程上以独立 version 3 typed 变体扩展多城市能力，继续复用现有确定性排程、Repository port、SQLite schema v2 typed JSON、来源、费用可信状态和五种终态，同时保证 legacy/V2 行为、指纹和已保存数据不变。

## 当前事实、缺口和前置条件

- B-000、F-001、F-002、F-003、F-004A 已交付归档；F-001 产品状态保持 `PARTIAL`；
- Step 45M 历史真实 UAT `FAIL`、Step 45T 真实 UAT `PASS` 均保留；
- 门票等非关键费用保持 `unknown`，金额为 `null`，不得按 0 处理；
- 混合交通 fallback 只有离线证据；F-004A 没有真实 Provider UAT；
- 当前 main、origin/main 和 F-004A 归档提交均为 `1a3e0a050721c72a6e83941f0cb5b2077decb1c7`，归档 main CI run `32360800884` 为 `success`；
- PR #13/#16/#17 为 F-004A 功能交付，PR #18 为归档；PR #14/#15 已由 clean-restack 的 #16/#17 替代并关闭；
- 当前能力是单城市连续 2–7 日、一个住宿锚点、每日最多 2 项活动、步行/公交、V2 typed request/plan/response 和 SQLite schema version 2 typed JSON；
- V2 恰好两日可复用 F-003 replan；V2 3–7 日以 `replan_scope_not_supported` 拒绝；
- 当前没有 migration v3；前端默认仍为单城市，只有用户显式选择多城市才进入 V3 有序停留/相邻段编辑；
- F-004B 已拆分为 F-004B1 离线领域与用户提供段，以及 F-004B2 真实城际 Provider；批准顺序为 F-004B1 → F-005 → F-004B2。

## 与 F-004A/F-003 的继承和隔离

- 继承 F-004A 的 2–7 日上限、逐日窗口、确定性时间排程、每日活动上限、预算/来源/unknown/partial 语义、Provider 适配器隔离和本地 SQLite；
- 继承 F-003 的独立 replan lifecycle、原子追加版本和 fail-closed 原则，但不扩大其操作范围；
- legacy 与 V2 DTO、响应 JSON、canonical fingerprint、已保存计划和 V2 replan 行为保持逐字节/逐形状兼容；
- V3 是独立 tagged typed 变体，不向 V2 注入大量 optional 字段；
- V3 的任何 replan 均在分析、Provider、decision、lineage 和 plan version 写入前拒绝；
- F-004B1 不修改历史 evidence 或归档任务卡，不把候选能力描述为已交付能力。

## 已批准产品范围

### 地理、城市与日期

- 仅支持中国大陆境内；
- 支持 2–3 个按用户指定顺序排列且互不重复的城市，不做全局路线优化；
- 总行程上限仍为连续 7 日；每个城市必须至少住宿一晚，因此 2 城行程最少 3 日，3 城行程最少 4 日；
- 每城住宿夜数之和必须等于总行程天数减 1，日期、住宿城市和相邻城市段必须连续；
- 首版支持单向/开放式行程；不支持通过重复首城表达闭合往返；
- 每个城市必须有独立住宿锚点，住宿锚点必须属于对应城市。

### 城际转移与活动

- 每个自然日最多一次城际转移，只允许从当前城市到城市序列中的下一城市；
- 转移日最多 1 项活动；非转移日继续最多 2 项活动；
- 不支持跨夜火车、航班或客运，不允许同一天经过第三个城市；
- 不支持在一个城际段内表达换乘城市或多段联程；
- 城际方式只允许 `rail`、`air`、`coach`；自驾不在 F-004B1 范围；
- 用户必须提供出发/到达城市、站点、出发/到达时间和方式，可选提供票价；系统不查询或承诺班次、票价、余票、库存、可预订性、支付或出票；
- 市内 POI 与车站/机场/客运站的衔接继续由市内路线边界表达，不把城际段冒充市内路线；
- 默认缓冲为：铁路出发前 60 分钟/到达后 30 分钟，航空 120/60 分钟，长途客运 45/30 分钟；
- 出发前活动必须在出发缓冲开始前结束，到达后活动必须在到达缓冲结束后开始；窗口不足进入确定性 conflict/needs_input，不压缩或虚构时间。

### 预算、来源和状态

- 住宿按各城市住宿夜数汇总，餐饮按旅行天数和人数汇总，市内交通保持现有规则；
- 城际票价只有用户提供时才以 `user_provided` 进入已知预算；未提供时为 `unknown`、金额 `null`，不得写成 0；
- F-004B1 不把估算票价、实时票价或 availability 与用户提供价格混合展示；
- 用户提供的班次、站点、时间和费用必须明确标记为用户输入，不伪造 Provider attribution、freshness 或实时性；
- `ready/partial/conflict/needs_input/failed` 沿用现有终态：关键字段缺失或歧义可为 needs_input，确定性连续性/窗口/预算冲突为 conflict，编排不可安全完成为 failed；
- unknown 或 freshness 缺口不能提升为 ready；可用但非关键事实缺失时保留 partial；
- 城市顺序冲突、日期断层、住宿断层、非相邻城市段、跨夜、同日多次跨城和第三城市经过必须 fail closed。

## 输入、输出与数据模型方向

### Version 3 请求

V3 使用严格 `request_version="3"`，至少包含：

- 连续 `start_date/end_date` 和与跨度精确一致的 `day_windows`；
- 2–3 个有序、唯一城市停留项：城市、住宿要求、住宿夜数；
- 相邻城市之间精确 `city_count - 1` 个用户提供的城际段；
- 城际段包含方式、出发/到达城市、站点、本地日期时间和可选用户提供费用；
- 现有 traveler、总预算、偏好、可访问性和市内交通要求按批准边界复用。

额外字段、未标记版本、模糊 union、重复城市、非相邻段、时间逆序或隐私字段均拒绝。

### Version 3 计划与响应

- V3 使用独立 `TripPlanRequestV3`、`TripPlanV3`、`TripPlanResponseV3` 和显式 format/version 标识；
- 每个 plan day 明确住宿城市，并在转移日明确出发城市、到达城市和唯一城际段引用；
- 每个城市有独立 resolved destination 与住宿锚点；每天只能引用当日合法城市的地点；
- 请求、计划、响应、来源和费用在持久化前及水合后都必须通过对应 typed model；
- 现有 11 个 PlanningStatus、attempt、trace、expected_version、retry、DELETE 和追加式 plan version 语义不变。

## API、Repository、SQLite 与兼容

- 继续复用现有 POST/GET/retry/DELETE URI；POST 以严格 tagged union 判别 legacy/V2/V3；
- GET/retry 根据持久化请求版本返回对应严格响应；legacy/V2 JSON 形状不增加字段；
- legacy/V2 canonical fingerprint 保持不变；V3 使用包含版本、城市顺序、住宿夜数、完整窗口和城际段的独立 canonical fingerprint；
- `PlanningJobRepository` 方法集合不变，typed request/result union 只显式增加 V3；SQLite 类型不得泄漏到 port；
- schema version 2 的 typed JSON 继续承载 V3；F-004B1 不增加 migration v3，不重写旧记录；
- 若需要新列、索引、关系实体、查询能力或 migration v3，立即停止；
- 旧应用读取 V3 记录只允许 fail closed，不得损坏、删除或错误投影；恢复方式是重新部署支持 V3 的代码；
- source、decision、acceptance record、单计划 DELETE、30 天 `expires_at` 和有界启动清理语义不变；
- V3 所有 replan 使用稳定 scope 错误在 Provider 和写入前拒绝，不创建 replan decision、lineage 或新 plan version。

## Provider、调用治理与隐私

- F-004B1 不新增或调用铁路、航空、长途客运 Provider；城际 Provider 调用上限为 0；
- 不读取 `.env.local`，不调用 DeepSeek、高德或和风天气进行真实验证；
- 后续实现可按城市复用现有 Provider 编排，但默认测试与验收完全离线，不新增 Provider 或依赖；
- 已批准预算方向：城市解析最多 `C` 次、POI 最多 `3C` 次、天气预报最多 `C` 次、预警最多 `C` 次、DeepSeek generation 1/repair 1、route 并发 2、route 调用最多 `min(28, 4D)`、城市 fan-out 并发 2、任务总 deadline 最多 180 秒；
- 任一新增调用、真实 UAT、费用、重试或数据留存需要独立批准；
- 只保存 allowlist 结构化请求、转换后的必要地点/路线/预算/天气字段、用户提供的城际字段和既有来源元数据；
- 不保存 Key、Token、JWT、私钥、Cookie、Authorization、完整 Prompt、Provider 原始响应、原始错误 body、完整日志或个人票务/证件信息；
- 不新增登录、同步、多用户、云数据库、公网部署、交易、库存或预订能力。

## 前端与离线体验

- 提供最小多城市编辑器：2–3 个有序城市停留卡、每城住宿锚点/夜数、相邻城际段卡和逐日窗口；
- 城市顺序由用户编辑，不实现自动路线优化；输入错误必须定位到具体城市或城际段；
- 结果页按日显示住宿城市，并在转移日显示出发/到达城市、用户提供段、缓冲和费用可信状态；
- 保持桌面与 `390×844` 可用、无水平溢出、键盘可达、可访问名称和明确焦点恢复；
- 已保存 V3 计划允许离线读取和应用重启恢复；不得把 unknown 显示为 ¥0，或把 partial 显示为 ready；
- 不新增复杂地图、图片、PDF、历史列表、版本比较/恢复或清空全部数据。

## 测试与验收矩阵

必须覆盖：

- legacy 双日请求、响应和固定 fingerprint 不变；
- V2 单城市 2/3/7 日请求、响应、持久化和 replan 边界不变；
- V3 2/3 城市的最小/最大合法行程，以及不可能的 2 日多城拒绝；
- 城市顺序、日期连续性、住宿夜数和住宿城市连续性；
- 城际段起终点与相邻城市顺序一致；
- 城际段与逐日窗口、出发前缓冲、到达后缓冲和活动数冲突；
- 跨夜、同日多次跨城、第三城市、重复城市和非相邻段拒绝；
- 缺少站点/时间、unknown 票价和用户提供费用；
- 来源 attribution/validity/freshness 不被虚构；
- ready/partial/conflict/needs_input/failed 的严格投影；
- 幂等、canonical fingerprint、expected_version、并发、retry 和 DELETE；
- schema v2 临时 SQLite 重启恢复、旧数据回归和旧应用读取 V3 fail closed；
- 30 天保留期和有界清理；
- 全部 V3 replan、V2 3–7 日 replan 和跨城市 replan 在 Provider/写入前拒绝；
- Provider 调用预算、并发、deadline、取消清理和 intercity provider 调用为 0；
- 隐私字段拒绝、默认测试不读取秘密、不访问真实 Provider或非 loopback 网络；
- 前端 2/3 城市、桌面和 390px、无水平溢出、键盘和可访问名称；
- unknown 不显示为 0，partial 不显示为 ready。

质量门禁包括 backend lock、format、lint、strict mypy、后端全量测试，frontend peer/format/lint/typecheck/test/build，文档检查器、`git diff --check`、范围审计、临时 SQLite 纵向和 loopback synthetic 浏览器验收。真实 Provider UAT 不属于 F-004B1。

## 文件与阶段治理

每个 Step 使用“核心文件清单 + 受控相邻扩展”：

- 核心文件是该 Step 的主要修改入口；
- 同一次 Step 批准自动覆盖同层直接依赖、对应测试与 fixture、机械门禁修复，以及 `current-task.md`、`implementation-plan.md`、`progress.md`、`evidence.md`、`docs/README.md` 五份状态文档；
- 不因普通传递依赖或状态收口逐文件索要授权；
- architecture、api-contract、agent-domain-spec、design-spec、testing-strategy、decisions 只在该 Step 已批准设计边界要求时同步；
- 不允许借“相邻扩展”改变冻结产品/API 语义、Schema/migration、依赖、数据/隐私边界、外部访问、Step 或 stack 归属。

真正停止条件：

- 需要改变已冻结产品或公开 API 语义；
- 需要 migration v3、新 Schema、新依赖、新 Provider 或隐私边界变化；
- 需要读取秘密、调用真实 Provider 或访问未批准外部服务；
- 需要跨 Step、跨 stack，或修改归档任务卡/历史 evidence；
- 单 Step 出现超过 5 个未预期生产/测试文件；
- 任一 stack 超过 30 个生产/测试文件或净新增 2500 行；
- 任务累计超过 90 个生产/测试文件或净新增 8000 行，必须重新切片；
- 连续三次遇到同一阻塞。

## Step 地图

| Step | 唯一目标 | 状态 |
| --- | --- | --- |
| Step 0 | 事实复核、任务激活、治理文档、状态漂移修正和首层本地分支 | DONE |
| Step 1 | 冻结 V3 领域、DTO/API、Repository/schema v2、Provider、测试和 UI 设计 | DONE |
| Step 2 | 以 TDD 实现多城市领域、V3 contracts、连续性、缓冲、预算和终态校验 | DONE |
| Step 3 | 实现 V3 Repository typed union、SQLite schema v2 往返、API 兼容与 replan 拒绝 | DONE |
| Step 4 | 实现离线多城市 planning、现有 Provider 按城市编排和调用治理 | DONE |
| Step 5 | 实现前端多城市编辑、严格 V3 解析、结果展示和离线恢复 | DONE |
| Step 6 | 完成临时 SQLite 纵向、loopback synthetic 浏览器 QA、隐私审查和独立 review | DONE |
| Step 7 | 完成本地全量门禁、四层 stacked PR 准备、clean-restack 与远程 CI | TODO |
| Step 8 | 按依赖合并、完整 main CI、归档和最终状态收口 | TODO |

每次只执行一个单独批准的 Step。Step 6 完成不构成 Step 7 授权。

## 分支与 stacked PR

批准的四层顺序：

1. `feat/f-004b1-multicity-domain-contracts`
2. `feat/f-004b1-multicity-persistence-api`
3. `feat/f-004b1-multicity-planning`
4. `feat/f-004b1-multicity-ui-delivery`

每层以直接前层为 base。前层 squash merge 后，从最新 main 创建干净后续分支，只移植该层净变更并重新验证；不得 force-push 重写已审查历史。归档 PR 仅在交付 Step 单独批准后可选创建。Step 0 只创建首层本地分支，不提交、不 push、不创建 PR。

## 文档更新契约

- 当前任务与范围：本文件；
- Step 计划与结果：`implementation-plan.md`；
- 当前摘要与下一动作：`progress.md`；
- 可复现证据：`evidence.md`；
- 优先级与拆分：`roadmap.md`；
- 产品、架构/API/Agent/UI/测试和长期决策在对应批准 Step 同步；
- 完成后完整任务卡进入 archive，当前权威文档只保留当前事实。

## 完成定义

- V3 多城市请求、计划和响应按批准范围端到端完成；
- legacy/V2 形状、指纹、持久化和 replan 行为无回归；
- 城市/日期/住宿/城际段/活动/缓冲连续性由确定性代码验证；
- unknown、partial、来源和用户提供费用不失真；
- schema 保持 v2，无 migration v3；临时 SQLite 重启恢复、并发和删除通过；
- 所有 V3 replan 在 Provider 与写入前拒绝；
- intercity Provider 调用为 0，默认测试和 UAT 完全离线；
- 前端 2/3 城市、桌面/390px、键盘与可访问性通过；
- 全部门禁、四层 stacked PR、CI、依序合并和归档在各自批准 Step 完成；
- F-001 `PARTIAL`、Step 45M `FAIL`、Step 45T `PASS`、unknown、混合交通 fallback 仅离线和 F-004A 无真实 Provider UAT 保持不变。

## 下一入口

等待用户审查 Step 6 证据并单独批准 F-004B1 Step 7。不得自动运行全量门禁、提交、push、创建 stacked PR 或触发远程 CI。
