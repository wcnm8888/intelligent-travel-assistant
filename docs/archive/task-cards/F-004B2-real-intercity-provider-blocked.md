# F-004B2 真实城际 Provider 与可信城际事实

## 任务元数据

- 任务 ID：`F-004B2`
- 等级：`L`
- 状态：`BLOCKED / ARCHIVED`
- 当前 Step：`Step 1 - Provider 与法律 Gate（已审核）`
- 当前 Step 状态：`DONE / BLOCKED`
- 基线：`main == origin/main == 96f73d99c04a72e1e697172306d8f33d006419ec`
- 前置：F-004B1、F-005、D-013、D-014
- 长期决策：D-015
- 下一候选顺序：F-004C → F-006；均不得自动进入

## 用户目标与业务价值

在中国大陆 2–3 城行程中，让用户可以为相邻城市段选择手工提供事实，或在获正式授权的官方 Provider 边界内查询同日直达铁路事实。结果必须清楚区分用户来源、Provider 核验、估算和 unknown，披露来源与时效，并在 Provider 失败或事实不可信时给出确定性终态和显式恢复入口。

本任务完成后，用户获得的是带来源和时效说明的行程参考，不是预订、支付、出票、余票或库存承诺。

## 已批准产品范围

- 仅中国大陆境内、2–3 城、相邻城市、单向、同日、直达 rail；
- 不支持 air、coach、跨夜、换乘、跨境、复杂路线优化或后台持续刷新；
- Provider 事实只包括 Provider 记录 ID、车次、出发/到达站、发到时间、历时、来源、`fetched_at`、可证明时的 `valid_until` 和 freshness；
- 费用只有在字段语义及展示/保存许可明确时才使用，否则保持 `amount=null`、`confidence=unknown`；
- 不实现余票、可售、舱位库存或库存承诺；
- 结果只作为信息参考，不实现预订、支付、出票、退改签、订单、乘客或证件。

## Provider 与法律 Gate

高德 Web 服务跨城公交路径规划只是优先待验证候选，不是已选定 Provider。12306 网页内部接口、Cookie、抓取和逆向明确禁止；TravelSky、VariFlight、Bus365 在没有正式合同、API、价格、配额和数据许可前保持阻塞。

Step 1 只能审核用户提供的正式书面授权、合同、工单回复或官方控制台事实，并必须给出一个可审计的 `PASS` 或 `BLOCKED`。Gate 至少确认：

- 官方 Provider、固定 endpoint/version 和允许的产品场景；
- 展示、attribution、派生、商业/非商业使用和第三方应用边界；
- 允许保存的规范化字段、最长 30 天留存和删除要求；
- 明确禁止保存或传入模型的字段；
- 账号/资质、价格、免费额度、超额价格、QPS 和配额口径；
- 真实 UAT 是否允许，以及凭证、次数、费用、脱敏和销毁条件；
- Provider 能否在不新增数据库 Provider 枚举、表、索引或 migration v3 的前提下使用 schema v2。

### Step 1 正式结论

`BLOCKED`。审核仅使用用户提供的高德官方书面回复，没有访问回复中的价格链接或其他外部资料。

- 使用场景：回复确认所述非商用个人开发 Web 服务 API 场景原则上属于许可范围；
- attribution：回复建议展示“数据来源于高德地图，仅供参考”，路径规划结果跳转 App/H5 不强制；
- 内存：仅程序运行期间临时保存允许；
- 持久化：回复明确禁止将 API 数据长期存储或持久化到本地 SQLite，直接不满足 D-015 的“最终选中 observation 最长随 planning job 保存 30 天”边界；
- rail 字段：回复只涉及 POI 名称、经纬度、路线距离和预计时间，没有明确授权 Provider 记录 ID、车次、铁路发到站和时间、历时等 F-004B2 rail 字段；
- 价格/配额：只给出免费配额页面并要求不超过限制，没有在所提供证据中明确数值、QPS、产品计费项或超额价格；
- UAT：没有明确 endpoint/version、凭证、允许域名、次数、费用、脱敏、留存或销毁条件。

SQLite 持久化禁止和 rail 字段授权不足任一项都足以使 Gate 失败；两项同时存在。当前没有已选 Provider，高德仍只是被审核后阻塞的候选。不得把“允许内存临时保存”解释为允许 schema v2 持久化，也不得擅自改变 D-015 已批准架构。

本任务已以 documentation-only blocked closure 归档，当前无活动任务。

Gate 未重新取得 `PASS` 前禁止进入 Step 2–10 的任何实现，不注册账号、不申请 Key、不提交商务合作、不付费、不读取秘密、不调用真实 Provider。

## 输入、输出与兼容边界

- legacy/V2/V3 request、response、fingerprint、旧记录和行为保持兼容；
- 新能力使用相同 POST/GET/retry/DELETE URI 和独立 `request_version="4"`；
- V4 每个相邻段是严格 typed union：`user_provided` 或 `provider_query`；同一段不能双来源，不能静默覆盖；
- 不同相邻段可以混合两个 variant；
- `provider_query` 只表达批准的 rail、城市索引、转移日和 bounded 查询约束；班次选择由确定性 application policy 完成，不由 Agent 读取原始候选文本；
- V3/V4 多城市 replan 都在 reserve、Provider、decision、lineage 和 plan write 前拒绝；
- 既有公开顶层 job/error shape 不变；V4 只增加已批准的 version-specific nested keys。

## 来源、费用与时效

- `user_provided`、`provider_verified`、`estimated`、`unknown` 必须严格区分；
- `provider_verified` 只表示获授权 Provider 响应经过 strict schema 和来源校验，不等于余票、可售或库存保证；
- `estimated` 不得用于车次、发到时间、余票、可售或库存；
- unknown 金额继续为 `null`，不得按 0；
- `fetched_at` 是获取/观察时间；`valid_until` 只有正式合约或确定性规则能证明时才填写；attribution 不证明 freshness 或 availability；
- stale 关键班次进入 failed；unknown-validity 最多 partial；缺失、过期、未验证或推断事实不得提升 ready；
- 只保存最终选中的规范化 observation，最长随 planning job 保留 30 天；不缓存候选列表；许可不允许时任务停止。

## 终态和恢复语义

- `needs_input`：查询约束缺失或站点映射不明确，用户能够修正；
- `conflict`：合法查询下没有满足已批准硬约束的同日直达班次，或 segment variant/城市/日期发生确定性冲突；
- `failed`：鉴权、Schema、timeout/429/5xx retry 耗尽、unknown Provider error、关键班次 stale 或关键字段缺失；
- `partial`：关键班次可用但 unknown-validity，或费用等非关键事实缺失/被剔除；
- `ready`：所有参与排程的关键事实 fresh、来源完整且既有确定性校验通过；
- Provider 失败不自动变为用户提供段，不做 rail→air/coach fallback；前端只允许显式切换到手工段后重新提交。

## 调用治理

- 复用 F-005 task-scoped attempt runtime；
- 新 capability 为城际铁路查询，每个 `provider_query` 段最多 1 个 logical call，每任务最多 2 个，首版并发固定为 1；
- 每个 logical call 最多 2 个 HTTP attempt，单 attempt timeout 6 秒；
- timeout、5xx 和带合法 Retry-After 的受控 429 最多额外尝试一次；鉴权、Schema、空数据和 unknown error 不做传输 retry；
- 如果最终选择 Amap，继续共享 Amap 额外 attempt 上限 3 和任务额外 attempt 上限 4，不提高 V3 多城市 180 秒总 deadline；
- 城际 logical call 与市内 route logical budget 分离；
- terminal、取消、deadline、逻辑预算或 attempt 预算耗尽后不得启动新调用，active call 必须 cancel/drain；
- Provider 错误不触发跨 mode fallback。

## Agent、隐私与安全

- Provider 原始响应、原始错误 body、候选列表、HTML、自由文本和完整 URL 都是不可信输入；
- 上述内容不得进入 proposal/repair、SQLite、fixture、日志或 CI artifact；
- proposal/repair 最多接收选中段的 bounded typed allowlist，不接收候选列表或 Provider 原始文本；
- Provider attribution 只能由 adapter/application 生成，模型无权创建或改写；
- 不保存 Key、Token、Cookie、Authorization、完整 Prompt、个人票务信息、乘客、证件或联系方式；
- 不新增账号系统、云同步、遥测、公网服务或生产数据库。

## 测试与验收矩阵

- domain/contracts：V4 union、相邻段、同日直达、来源/费用闭集、时区、fresh/stale/unknown-validity、strict extra-field rejection；
- adapter：fake/MockTransport/synthetic fixture 覆盖 auth、429、timeout、5xx、Schema、empty、unknown、响应大小和不可信文本；
- application/runtime：确定性选择、1/2 段、混合 user/provider、逻辑预算、HTTP attempt、deadline、cancel/drain、fallback 禁止和终态；
- API/Repository/SQLite：同 URI、幂等、fingerprint、retry、DELETE、30 天过期、schema v2 roundtrip、旧记录和 V3/V4 replan 写前拒绝；
- Agent/eval：保留 F-005 固定 48 case，另建至少 16 个完全离线 F-004B2 synthetic case；
- frontend/browser：手工/Provider variant、loading/empty/error/partial/ready、显式恢复、desktop/390px、键盘、无障碍和 reload；
- 安全/隐私：默认测试和 CI 阻断非 loopback 网络；临时 SQLite、日志、fixture、artifact 和模型输入不得含禁止数据；
- 独立真实 Provider UAT 是 Step 8，默认关闭并须再次批准；没有 UAT PASS 时不得把任务记为完整完成。

## 五层 stacked PR

1. `feat/f-004b2-intercity-domain-contracts`
2. `feat/f-004b2-intercity-provider-adapter`
3. `feat/f-004b2-intercity-application-runtime`
4. `feat/f-004b2-intercity-persistence-api`
5. `feat/f-004b2-intercity-ui-delivery`

前层合并后只允许从最新 main clean-restack 后续净层；不得 force-push 或改写已公开历史。

## 核心文件与受控相邻扩展

### Stack 1：domain/contracts

- `backend/src/intelligent_travel_assistant/contracts/trip_planning.py`
- `backend/src/intelligent_travel_assistant/domain/multicity.py`
- `backend/src/intelligent_travel_assistant/domain/foundation.py`
- `backend/src/intelligent_travel_assistant/domain/provider_result.py`
- `backend/src/intelligent_travel_assistant/domain/resilience.py`
- 可新增一个纯领域 `domain/intercity_provider.py`
- 直接 export 与对应 domain/contracts/golden/fingerprint 测试

### Stack 2：Provider adapter

- `backend/src/intelligent_travel_assistant/application/ports/providers.py`
- `backend/src/intelligent_travel_assistant/application/ports/models.py`
- 独立城际 Provider adapter、直接 factory/config wiring
- 对应 adapter contract、MockTransport 和 synthetic schema/error 测试

### Stack 3：application/runtime

- `backend/src/intelligent_travel_assistant/application/tooling/governance.py`
- `backend/src/intelligent_travel_assistant/application/tooling/resilience.py`
- `backend/src/intelligent_travel_assistant/application/services/multicity_planning.py`
- `backend/src/intelligent_travel_assistant/application/services/provider_planning_jobs.py`
- 对应 application、budget、cancel/drain 与 eval 测试

### Stack 4：Repository/API

- `backend/src/intelligent_travel_assistant/adapters/persistence/repository.py`
- `backend/src/intelligent_travel_assistant/api/trip_plans.py`
- `backend/src/intelligent_travel_assistant/api/replans.py`
- 对应 Repository/API/SQLite/fingerprint/compatibility 测试
- `schema.py`、`migrations.py` 只允许作为不变门禁读取和测试，不允许修改

### Stack 5：UI/delivery

- `frontend/src/tripRequest.ts`
- `frontend/src/tripPlanningApi.ts`
- `frontend/src/TripRequestForm.tsx`
- `frontend/src/MulticityTripPlanResult.tsx`
- `frontend/src/ResultEvidence.tsx`
- 直接 fixtures、component/parser 和 browser 支撑测试

受控相邻扩展只包括直接 export、factory/wiring、同层 typed model、对应测试/synthetic fixture/golden，以及当前状态和 evidence 文档。单 Step 出现超过 5 个未预期生产/测试文件时立即停止。

## 规模阈值

| Stack | 建议文件上限 | 建议净新增行 |
| --- | ---: | ---: |
| Stack 1 | 14 | 1200 |
| Stack 2 | 12 | 1000 |
| Stack 3 | 16 | 1500 |
| Stack 4 | 14 | 1200 |
| Stack 5 | 16 | 1500 |

任一 stack 超过 20 个生产/测试文件或净新增 1800 行、任务累计超过 75 个生产/测试/fixture 文件或净新增 6500 行时停止并重新拆分。

## Step 地图

| Step | 唯一目标 | 状态 |
| --- | --- | --- |
| Step 0 | 复核最终基线，条件式激活任务，建立 D-015、治理、五层 stack 与首层本地分支 | DONE |
| Step 1 | 审核用户提供的正式 Provider/法律/价格/配额/保存/UAT 证据并作出 PASS 或 BLOCKED | BLOCKED |
| Step 2 | 以 TDD 实现独立 V4 纯领域与 contracts | BLOCKED_BY_STEP_1 |
| Step 3 | 以完全离线替身实现单次城际 Provider adapter 和安全错误归一化 | BLOCKED_BY_STEP_1 |
| Step 4 | 接入 F-005 runtime、调用预算与多城市 application 确定性选择 | BLOCKED_BY_STEP_1 |
| Step 5 | 完成同 URI V4 API、fingerprint、Repository/schema v2 roundtrip 和 replan 写前拒绝 | BLOCKED_BY_STEP_1 |
| Step 6 | 完成 V4 前端查询意图、来源/时效/unknown 展示和显式手工恢复 | BLOCKED_BY_STEP_1 |
| Step 7 | 完成离线 eval、临时 SQLite、loopback desktop/390px 和独立隐私安全审查 | BLOCKED_BY_STEP_1 |
| Step 8 | 在独立批准后执行有上限的真实 Provider UAT | BLOCKED_BY_STEP_1 |
| Step 9 | 运行全量门禁并完成五层 commit/push/stacked PR/review/CI | BLOCKED_BY_STEP_1 |
| Step 10 | 依序合并、必要 clean-restack、最终 main CI、归档与任务关闭 | BLOCKED_BY_STEP_1 |

## 验收标准

- legacy/V2/V3 exact shape、fingerprint、旧记录和行为不变；
- V4 strict union、来源、费用、freshness、终态和恢复动作可离线复现；
- unknown 金额始终 `null`；关键 stale 不成计划，unknown-validity 不提升 ready；
- 每任务城际 logical call ≤ 2、每调用 HTTP attempt ≤ 2；terminal/cancel/deadline/budget 后新调用 0、active peer 0；
- Provider 错误不触发 mode fallback，原始内容不进入模型、SQLite、fixture、日志或 artifact；
- schema 仍为 v2、migration 只有 1/2，V3/V4 replan 在任何写入或 Provider 调用前拒绝；
- 默认测试和 CI 非 loopback 请求为 0；F-005 48 case 保持，F-004B2 独立 eval 通过；
- 临时 SQLite、desktop/390px、console、accessibility、隐私安全审查通过；
- 独立真实 Provider UAT PASS；否则任务不得标记完整完成；
- 五层独立 review、CI、最终 main CI 和归档证据齐全。

## 停止条件

- Provider 授权、endpoint、字段、展示、留存、价格、配额、QPS、UAT 或销毁边界不明确；
- 需要网页抓取、Cookie、逆向、私有 endpoint 或来源不明数据；
- 需要 migration v3、新表/列/索引、Schema 变化、新依赖或 lockfile；
- 需要新增 URI、公开顶层错误码或未批准 JSON shape；
- 需要把 Provider 原始响应、错误或不可信文本交给模型或持久化；
- 需要扩大到 air/coach、跨夜、换乘、跨境、交易、库存承诺、账号、云同步、遥测或公网；
- 默认测试/CI 需要真实外网，或真实 UAT 超出批准次数、费用、域名或数据边界；
- 触发文件数/净新增行阈值，或同一阻塞连续出现三次。

## 当前批准边界

Step 1 已按用户批准完成审核并正式判为 `BLOCKED`。恢复只允许两种入口：获得补充正式书面证据，同时明确覆盖 rail 字段和批准的 SQLite 最长 30 天保存边界；或由用户另行起草并批准改变产品/持久化架构的变更卡。不得自动进入 Step 2、F-006 或任何实现。

## 保留历史事实

- F-001 `PARTIAL`、Step 45M `FAIL`、Step 45T `PASS`；
- unknown 金额保持 `null`，混合交通 fallback 只有离线证据；
- F-004A/F-004B1/F-005 无真实 Provider UAT，F-004B1 城际 Provider 调用 0；
- F-005 offline eval、MockTransport、synthetic fixture、loopback QA 不等于真实 UAT；
- SQLite schema version 2，migration 只有 1/2。
