# 当前任务：F-004C 用户已购铁路段与车次信息

## 任务元数据

- 任务 ID：F-004C
- 等级：L
- 状态：ACTIVE
- 当前 Step：`Step 6 - 三层交付与归档（执行中）`
- 当前 Step 状态：ACTIVE
- 基线：main == origin/main == 577bdcbadf2e024022e59e52527d13edb0cbd659
- 前置：F-004B1、F-005、F-004B2 BLOCKED closure
- 长期决策：D-016
- 下一任务：F-006；不得自动进入

## 用户目标与价值

让用户为中国大陆 2–3 城行程中的每个相邻城市段录入已购铁路车次事实，系统据此完成确定性多城市排程、预算和来源披露。该能力只接收用户提供的信息，不查询、抓取或核验 12306 或任何城际 Provider。

“已购”只表示用户提供了自己的行程事实，不证明当前余票、可售状态、库存或 Provider 核验。

## 已批准产品范围

- 独立 request_version="4"、response_version="4" 和 plan_format_version="4"；
- 仅中国大陆境内、2–3 城、相邻城市、单向、同日、直达 rail；
- 每个相邻段都由用户提供，不支持 provider_query 或同段多来源；
- service_number 必填，trim 后转 uppercase，并按 ^[A-Z0-9]{1,12}$ 校验；
- 不维护车次前缀 allowlist，不验证车次真实存在；
- 用户提供出发站、到达站、出发时间、到达时间和可选票价；
- 历时由发到时间确定性计算，不作为请求字段或新增 JSON 字段；
- unknown 金额保持 null，不得按 0；
- 来源固定为 user_provided、unknown_validity 和“用户提供，未核验”，不得标为 provider_verified；
- 结果仅作旅行计划参考，不实现购票、预订、支付、出票、退改签、订单或库存承诺。

## D-016 与历史关系

- D-016 只替代 D-015 中未实现的 V4 user_provided/provider_query union 预留；
- F-004B2 继续保持 BLOCKED / ARCHIVED，不改变其 Provider/法律 Gate 历史；
- F-004C 不恢复或实现任何 Provider 查询；
- 未来真实城际 Provider 必须使用新的 request/response/plan format 版本和新的长期决策，不得复用 F-004C V4。

## 输入与领域规则

每个相邻铁路段必须包含：

- from_city_index 和 to_city_index；
- service_number；
- departure_station 和 arrival_station；
- departure_at 和 arrival_at，使用带 +08:00 offset 的绝对时间；
- 可选 fare：已知时为正数金额和 CNY，未知时 amount=null、confidence=unknown。

确定性规则：

- 城市索引必须严格相邻并与城市顺序一致；
- 发到站不得为空；
- 发到时间必须属于已批准行程范围，且到达晚于出发；
- 首版只接受同一自然日内的直达段；
- 历时只由规范化发到时间计算；
- 车次格式校验不等于真实性验证；
- 费用来源只允许 user_provided 或 unknown。

## Step 1 冻结设计

- V4 request 顶层 exact keys 与 V3 对应，tag 改为 `request_version="4"`；每段使用独立 `BookedRailIntercitySegmentV4`，字段精确为相邻索引、`mode="rail"`、`service_number`、发到站、发到时间和可空 fare；
- `service_number` 的唯一规范化顺序为 strict string → `strip()` → `upper()` → `^[A-Z0-9]{1,12}$`；不做前缀/真实性判断；
- V4 plan/response 使用 `plan_format_version="4"`、`response_version="4"`；计划段为 `PlanBookedRailSegmentV4`，只在 V3 段形状上增加规范化 service number 并收窄 rail；不新增 duration；
- V4 response 顶层 exact keys 与 V3 plural response 相同；summary 不回显 service number。V3/V4 tag 或 plan/result 不匹配、额外/缺失键和未知版本均 fail closed；
- source 复用 `provider=user/source_type=user_provided_intercity_segment`，record/URL/valid-until 为空，freshness 为 unknown-validity，固定显示“用户提供，未核验”；
- 用户段 unknown-validity 沿用 D-013 availability 排除，不单独强制 partial；unknown fare 和其他参与预算/排程的缺口继续阻止 ready；ready 也只能表述“代码校验通过”；
- V4 fingerprint 对规范化 typed dump 排除 `client_request_id` 后使用既有 canonical JSON + SHA-256；service number 变化必须变 digest，大小写/边缘空白等价；
- Repository 增加独立 V4 request/plan/result union member，Protocol 与 schema v2 JSON 路径不变；旧应用、未知 tag 和跨版本组合 fail closed；
- V3/V4 create-replan 在 reserve 前返回既有 422 scope；拒绝路径 decision/executor/Provider/runtime/lineage/plan write 均为 0；不存在的后续 replan 资源沿用既有安全 404；
- Agent 不接收 service number、完整 segment 或原始城际文本，只接收 allowlist 时间/缓冲约束；segment 在模型边界外确定性重建；
- V4 使用专用 strict preferences，只允许 `interests`；`free_text` / `hard_constraints` 属于额外字段并返回 422，legacy/V2/V3 preferences shape 和行为不变；
- 前端保留“自行填写交通段”为默认 V3，显式选择“填写已购铁路车次”才提交 V4；切换只清空段卡，V4 固定 rail 并显示车次、未核验和隐私提示；
- 精确 shape、架构、Agent/UI 和分层测试矩阵分别以 api-contract、architecture、agent-domain-spec、design-spec 和 testing-strategy 的 F-004C Step 1 章节为准。

## API、兼容与指纹

- 保持现有 POST/GET/retry/DELETE URI 和公开顶层 job/error shape；
- legacy/V2/V3 request、response、fingerprint、旧记录和行为保持 exact compatibility；
- V4 只增加批准的 version-specific nested keys；
- V4 fingerprint 包含规范化后的 service_number；
- client_request_id 继续排除在 fingerprint 之外；
- 不新增 URI、公开顶层错误码或未批准 JSON 键；
- V3 和 V4 replan 均在 reserve、decision、executor、Provider、lineage 和 plan write 前拒绝。

## Repository 与 SQLite

- 使用现有 SQLite schema version 2 typed JSON 和既有 planning job 生命周期；
- migration 仍只有 1/2；
- 不新增表、列、索引、Provider 枚举或 migration；
- 用户提供的规范化段可以随 planning job 保存；
- legacy/V2/V3 旧记录读取保持不变；
- 若实现需要 migration v3、关系型查询或旧记录改写，立即停止并重新批准。

## Agent、Provider、隐私与安全

- service_number 和用户城际段原文不得进入 proposal/repair；
- Agent 不生成、修复、选择或核验车次；
- 城际 Provider logical call 为 0，HTTP attempt 为 0；
- 不访问、抓取或自动读取 12306；
- 不调用高德、和风、DeepSeek 或任何城际 Provider；
- 不保存姓名、证件、手机号、邮箱、订单号、座位、二维码、Cookie、截图或自由备注；
- V4 请求只接受 interests，不接受或持久化 `free_text` / `hard_constraints`；前端 V4 不展示、提交或静默携带自由文本；
- 不读取 .env.local、秘密或本地 Provider 配置；
- 默认测试和 CI 阻断非 loopback 网络；
- 不新增账号、Key、合同、付费、遥测、云同步、公网服务或生产数据库。

## 测试与验收矩阵

- domain/contracts：V4 strict shape、2/3 城、1/2 个相邻段、service_number 规范化和边界、同日直达、时间与费用；
- compatibility/golden：legacy/V2/V3 exact shape、fingerprint、旧记录和 unknown/null；
- application：确定性历时、连续性、城市/站点顺序、调用预算为 0、五终态；
- Repository/API/SQLite：同 URI、幂等、retry、DELETE、schema v2 typed JSON 往返、重启恢复和旧记录；
- replan：V3/V4 在所有 reserve、decision、executor、Provider、lineage 和 plan write 前拒绝；
- frontend：V4 表单、车次/站点/时间/票价、错误焦点、结果来源与未核验披露、reload；
- browser/privacy：临时 SQLite、loopback desktop/390px、network/console/accessibility 和独立隐私安全审查；
- 默认测试完全离线，不执行真实 Provider UAT。

## 三层 stacked PR

1. feat/f-004c-booked-rail-domain-contracts
2. feat/f-004c-booked-rail-persistence-api
3. feat/f-004c-booked-rail-ui-delivery

前层合并后只允许从最新 main clean-restack 后续净层；不得 force-push 或改写已公开历史。

## 核心文件与受控相邻扩展

### Stack 1：domain/contracts

- backend/src/intelligent_travel_assistant/contracts/trip_planning.py
- backend/src/intelligent_travel_assistant/domain/multicity.py
- backend/src/intelligent_travel_assistant/domain/foundation.py
- domain 直接 export
- 对应 domain/contracts/golden/fingerprint 测试

### Stack 2：persistence/API/application compatibility

- backend/src/intelligent_travel_assistant/application/services/multicity_planning.py
- backend/src/intelligent_travel_assistant/application/services/provider_planning_jobs.py
- backend/src/intelligent_travel_assistant/adapters/persistence/repository.py
- backend/src/intelligent_travel_assistant/api/trip_plans.py
- backend/src/intelligent_travel_assistant/api/replans.py
- 对应 application/Repository/API/SQLite/replan/compatibility 测试
- schema.py 和 migrations.py 只允许作为不变门禁读取和测试，不允许修改

### Stack 3：UI/delivery

- frontend/src/tripRequest.ts
- frontend/src/tripPlanningApi.ts
- frontend/src/TripRequestForm.tsx
- frontend/src/MulticityTripPlanResult.tsx
- frontend/src/ResultEvidence.tsx
- 直接 component/parser/browser fixtures 与测试

受控相邻扩展仅限直接 export、factory/wiring、同层 typed model、对应测试/golden/synthetic fixture，以及当前状态和 evidence 文档。单 Step 超过 5 个未预期生产/测试文件时停止。

## 规模阈值

- 任一 stack 超过 18 个生产/测试文件或净新增 1400 行时停止并重新拆分；
- 任务累计超过 50 个生产/测试/fixture 文件或净新增 4000 行时停止并重新拆分；
- 文档、机械生成物和构建输出不得用于规避阈值；
- 任何跨 stack、Schema、依赖、隐私或 Provider 扩张都必须重新批准。

## Step 地图

| Step | 唯一目标 | 状态 |
| --- | --- | --- |
| Step 0 | 复核 closure 基线，激活 F-004C，建立 D-016、Step 0–6、三层 stack、核心文件和规模治理 | DONE |
| Step 1 | 冻结 V4 contracts、纯领域规则、兼容、fingerprint、replan、持久化和测试设计 | DONE |
| Step 2 | 以 TDD 实现 V4 纯领域与 contracts | DONE |
| Step 3 | 完成 application、Repository/schema v2、同 URI API 与 replan 写前拒绝 | DONE |
| Step 4 | 完成 V4 前端交互、来源/未核验展示和恢复 | DONE |
| Step 5 | 执行临时 SQLite、loopback desktop/390px、独立隐私安全审查和已批准的 Step 5A 修正 | DONE |
| Step 6 | 运行全量门禁，完成三层 stacked PR、合并、最终 main CI 和归档 | ACTIVE |

## 验收标准

- V4 strict contracts 和确定性规则完整；
- legacy/V2/V3 exact shape、fingerprint、旧记录和行为不变；
- service_number 规范化后参与 V4 fingerprint；
- 历时不成为请求或新增 JSON 字段；
- unknown 金额始终为 null；
- 来源始终为 user_provided / unknown_validity / 用户提供，未核验；
- 城际 Provider logical call 和 HTTP attempt 均为 0；
- schema 保持 version 2，migration 只有 1/2；
- V3/V4 replan 在所有写入、决策、执行和 Provider 边界前拒绝；
- 临时 SQLite、desktop/390px、network/console/accessibility 和隐私安全审查通过；
- 三层独立 review、CI、最终 main CI 与归档证据齐全。

## 停止条件

- 需要真实 Provider、12306 抓取/自动读取、账号、Key、合同、付费或真实 UAT；
- 需要修改 Schema、migration、依赖或 lockfile；
- 需要新增 URI、公开顶层错误码、未批准 JSON 字段或改变 legacy/V2/V3；
- 需要保存禁止的票务或个人信息，或把城际段原文交给模型；
- 需要验证车次真实存在、余票、可售、库存或交易状态；
- 需要支持 air、coach、跨夜、换乘、跨境或复杂路线优化；
- 触发文件数、净新增行或未预期文件阈值；
- 需要进入未获单独批准的下一 Step。

## 当前批准边界

Step 0–5 已完成，Step 6 已获单独批准并正在执行。只允许运行全量门禁、按批准的三层 topology 完成精确提交、push、stacked PR、独立 review、远程 CI、顺序合并、必要 clean-restack、最终 main CI 和归档；不得修改 Schema、migration、依赖或 lockfile，不得读取秘密或调用真实 Provider。

## 保留历史事实

- F-004B2 保持 BLOCKED / ARCHIVED，D-015 历史不变；
- F-001 PARTIAL、Step 45M FAIL、Step 45T PASS；
- unknown 金额保持 null，混合交通 fallback 只有离线证据；
- F-004A/F-004B1/F-005 无真实 Provider UAT；
- F-004B1 城际 Provider 调用为 0；
- F-005 离线 eval、MockTransport、synthetic fixture、loopback QA 不等于真实 UAT；
- SQLite schema version 2，migration 只有 1/2。
