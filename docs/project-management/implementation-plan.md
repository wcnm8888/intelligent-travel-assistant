# 最近关闭计划：F-004C 用户已购铁路段与车次信息

## 当前状态

当前无活动任务，因此没有正在执行的 Step。

- 当前任务：无
- 最近关闭：`F-004C DELIVERED / ARCHIVED`
- Step 0–6：全部 `DONE`
- 完整功能 main：`14c4deaf5acfc4b8e3ccfb18db172dfe910eb26e`
- 完整功能 main CI：run `32484789531`，`PASS`
- F-004B2：BLOCKED / ARCHIVED；不得恢复 Provider 查询
- 归档任务卡：[F-004C archive](../archive/task-cards/F-004C-booked-rail-user-provided.md)
- 下一候选：F-006；不得自动启动

## Step 0：激活与治理

唯一目标：复核 F-004B2 blocked closure 后的最终基线，激活 F-004C，并建立 D-016、Step 0–6、三层 stacked PR、核心文件、受控相邻扩展和规模阈值。

状态：`DONE`。仅完成治理文档、首层本地分支和本地门禁；没有进入 Step 1 或实现。

允许：

- 只读复核本地/远程 Git、PR、CI、归档和当前状态；
- 修改批准的当前治理与权威文档；
- 在确认 main 干净后创建首层本地分支。

禁止：

- 修改生产源码、测试、fixture、Schema、migration、依赖或 lockfile；
- 创建数据库；
- 读取 .env.local、秘密、本地 Provider 配置或凭证；
- 调用高德、12306、和风、DeepSeek 或其他 Provider；
- commit、push、PR、merge、远程 CI 或进入 Step 1。

完成门禁：

- main、origin/main、PR #33、最终 main CI、归档、无活动任务和干净基线事实一致；
- F-004C 是唯一 ACTIVE，F-004B2 保持 BLOCKED / ARCHIVED，F-006 保持 CANDIDATE；
- current-task、roadmap、implementation-plan、progress、evidence 和 D-016 一致；
- 文档检查器及其测试、git diff --check、范围和秘密模式审计通过；
- diff 只含批准的当前治理和权威文档，无源码、测试、数据库、历史 evidence 或归档任务卡改写；
- 首层本地分支存在且没有 commit 或远程写入。

## Step 1：设计冻结

唯一目标：冻结可实现的 V4 contracts、service_number、时间/历时、费用/来源、兼容、fingerprint、schema v2、replan、前端和测试设计。

状态：`DONE`。只修改权威设计/治理文档；未修改生产源码、测试、fixture、Schema、migration、依赖或 lockfile，也未进入 Step 2。

不得修改生产源码、测试、Schema、migration、依赖或 lockfile，不得进入 Step 2。

必须冻结：

- V4 request/response/plan exact shape 与 strict extra-field rejection；
- service_number 规范化、校验和错误语义；
- 同日直达、站点、时间、确定性历时和城市连续性；
- user_provided / unknown_validity / 未核验来源；
- unknown/null 费用；
- legacy/V2/V3 exact compatibility 与 V4 fingerprint；
- schema v2 typed JSON 往返和旧记录；
- V3/V4 replan 全链路写前拒绝；
- 城际 Provider logical/HTTP 调用 0；
- 三层文件归属、测试矩阵和停止阈值。

冻结结果：

- request/plan/response 分别使用独立 V4 strict tag；request 段精确增加规范化 service number 且 mode 固定 rail，plan 段增加同一规范化值，不新增 duration；
- strict normalization、同日 `+08:00`、transfer date、60/30 缓冲、positive/null fare、来源和五终态边界已冻结；
- V4 typed union、canonical fingerprint、schema v2 JSON hydration、same-URI API、V3/V4 replan 零写入和旧版本 fail-closed 已冻结；
- Agent payload 排除 service number/完整 segment/原始文本；城际 logical call/HTTP attempt 为 0；
- UI 以显式 V3/V4 城际信息类型选择保持 V3 默认不变；V4 parser/result/recovery、desktop/390px 和隐私文案已冻结；
- 三层核心文件、RED→GREEN 顺序、兼容/SQLite/browser/privacy 矩阵和原规模阈值已冻结；详细契约以五份领域权威文档的 F-004C Step 1 章节为准。

## Step 2：V4 纯领域与 contracts

唯一目标：先记录 RED，再以最小 GREEN 实现 V4 纯领域和 strict contracts。

状态：`DONE`。首次定向测试在 collection 阶段因 V4 领域与 contract export 尚不存在而按预期 RED；最小 GREEN、相邻兼容回归、全量后端测试和静态门禁均通过。

交付边界：本 Step 只提供可直接校验的 V4 领域与 concrete strict contracts；`PlanningRequest` / `PlanningPlan` / `PlanningResponse`、Repository/API/application union 接线和 fingerprint 留在 Step 3，避免越权修改 application/API。

允许范围：

- trip planning contracts；
- multicity/foundation 直接领域规则；
- 直接 export；
- domain/contracts/golden/fingerprint 测试；
- 当前状态与 evidence 文档。

不得接入 application、Repository、API、SQLite、Provider 或前端。

## Step 3：application、Repository 与 API

唯一目标：完成确定性 V4 planning 接线、Repository/schema v2 typed JSON、同 URI API、fingerprint/幂等及 V3/V4 replan 写前拒绝。

状态：`DONE`。首次定向测试在 collection 阶段因 `PlanningJobResultV4` 尚不存在而按预期 RED；最小 GREEN、schema v2 往返、同 URI API、replan 零写入、兼容回归和全量后端门禁均通过。

交付边界：V4 intercity 段由已验证 typed request 在 Agent 边界外确定性重建；proposal/repair payload 不含 `service_number` 或完整 segment。没有新增城际 Provider port、logical call 或 HTTP attempt；前端仍留在 Step 4。

必须保持：

- 不修改 schema.py、migrations.py、Schema 或 migration；
- 不新增 Provider port、adapter、logical call 或 HTTP attempt；
- 不读取 service_number 或用户段原文进入 proposal/repair；
- legacy/V2/V3 shape、旧记录、retry 和 DELETE 行为不变。

不得进入前端。

## Step 4：前端交互

唯一目标：实现 V4 已购铁路段输入、严格 parser、来源/未核验/unknown 展示和本机恢复。

状态：`DONE`。先以独立 V4 synthetic fixture 和 6 项直接测试记录 RED，随后补齐同 URI retry 与三城市双段覆盖，最终 8 项通过；已完成显式 V3/V4 选择、切换清段、service number 规范化/首错、V4 strict parser/result 与 reload pointer，legacy/V2/V3 全量前端回归通过。

前端不得：

- 核验车次真实性；
- 推导 Provider 状态、余票、库存或可售；
- 新增自由备注、截图、订单、乘客或证件字段；
- 自动访问 12306 或任何外部网络。

## Step 5：离线纵向验收

唯一目标：执行临时 schema v2 SQLite 纵向、loopback desktop/390px 浏览器 QA、network/console/accessibility 和独立隐私安全审查。

当前结论：`DONE / PASS`。SQLite、desktop/390px、仅 loopback 网络、console 和基础 accessibility 证据已完成；Step 5A 使用 interests-only strict V4 preferences、最小 application/frontend 投影、API 422、零 job/SQLite 写入、generation/repair context synthetic sentinel 和两层独立复审关闭原隐私 finding。不得自动进入 Step 6。

必须证明：

- create/read/restart/retry/delete 和旧记录兼容；
- 2/3 城、1/2 相邻段、service_number 规范化、unknown/null；
- 城际 Provider logical call 和 HTTP attempt 均为 0；
- 浏览器非 loopback 请求为 0；
- SQLite、日志、fixture、浏览器状态不含禁止票务或个人数据；
- 该 Step 不构成真实 Provider UAT。

## Step 6：三层交付与归档

唯一目标：运行全量门禁，按三层拓扑完成 commit、push、stacked PR、独立 review、远程 CI、依序合并、必要 clean-restack、最终 main CI、归档和任务关闭。

任何 merge、远程写入或归档动作都必须在 Step 6 获得单独批准；Step 0–5 不产生交付授权。

状态：`DONE / PASS`。

- 本地全量门禁：后端 `1360 passed`、前端 `107 passed`，全部静态、构建和文档门禁通过；
- PR #34/#35/#36 依序 squash merge；最终各层 CI run `32482782649`、`32483888878`、`32484329856` 均为 `success`；
- squash 后采用普通 merge restack 更新后续分支，没有 force-push；每次重定向到 main 后 diff 仍只包含当前层；
- 完整功能 main 为 `14c4deaf5acfc4b8e3ccfb18db172dfe910eb26e`，最终 main CI run `32484789531` 为 `success`；
- 独立逐层 review、隐私安全 review 均无未关闭 finding；任务已归档，当前无活动任务。

## 三层拓扑与核心文件

1. feat/f-004c-booked-rail-domain-contracts
   - contracts、multicity/foundation、直接 export 与 domain/contracts/golden/fingerprint 测试。
2. feat/f-004c-booked-rail-persistence-api
   - multicity/provider planning services、Repository、trip plans/replans API 与 application/SQLite/API/replan/compatibility 测试；schema/migrations 只读不改。
3. feat/f-004c-booked-rail-ui-delivery
   - tripRequest、tripPlanningApi、TripRequestForm、MulticityTripPlanResult、ResultEvidence 与直接 parser/component/browser 支撑。

受控相邻扩展仅限直接 export、factory/wiring、同层 typed model、对应测试/golden/synthetic fixture，以及当前状态和 evidence 文档。单 Step 超过 5 个未预期生产/测试文件时停止。

## 规模治理

- 任一 stack 超过 18 个生产/测试文件或净新增 1400 行时停止并重新拆分；
- 任务累计超过 50 个生产/测试/fixture 文件或净新增 4000 行时停止并重新拆分；
- Schema、migration、依赖、lockfile、Provider、隐私或公开顶层 API shape 变化不受相邻扩展覆盖，必须重新批准。

## 跨 Step 不变量

- D-016 只替代 D-015 中未实现的 V4 Provider union 预留；F-004B2 BLOCKED 历史保持；
- legacy/V2/V3 exact compatibility；
- V4 仅 user_provided 同日直达 rail；
- service_number 必填、规范化并参与 fingerprint，不声称真实性；
- 历时为确定性计算，不增加请求或 JSON 字段；
- unknown 金额保持 null，不按 0；
- schema version 2，migration 只有 1/2；
- V3/V4 replan 全链路写前拒绝；
- 城际 Provider logical call 和 HTTP attempt 均为 0；
- 默认测试和 CI 阻断非 loopback 网络；
- 未经单独批准不得进入下一 Step。
