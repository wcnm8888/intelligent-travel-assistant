# 最近关闭计划：F-004B2 真实城际 Provider 与可信城际事实

## 当前状态

当前无活动任务，因此没有正在执行的 Step。

- 最近关闭：`F-004B2 BLOCKED / ARCHIVED`
- 基线：`main == origin/main == 96f73d99c04a72e1e697172306d8f33d006419ec`
- Provider/法律 Gate：`BLOCKED`
- 当前未选定 Provider；没有账号、Key、合同、Schema、依赖或真实调用批准
- Step 0 已完成；Step 1 已审核用户提供的高德官方回复并判为 `BLOCKED`
- Step 2–10 未执行并保持关闭；完整任务卡见 [F-004B2 BLOCKED archive](../archive/task-cards/F-004B2-real-intercity-provider-blocked.md)
- 下一候选顺序：F-004C → F-006；均不得自动启动

## Step 0：条件式激活与治理收口

唯一目标：复核 F-005 最终归档基线，条件式激活 F-004B2，并建立 D-015、Step 0–10、五层 stack、核心文件和规模治理。

允许：

- 修改当前治理与权威文档；
- 只读复核本地/远程 Git、PR 和 CI 事实；
- 在确认 main 干净后创建首层本地分支。

禁止：

- 修改源码、测试、fixture、Schema、migration、依赖或 lockfile；
- 创建数据库，读取秘密或 Provider 配置；
- 注册账号、申请 Key、付费、调用 Provider、抓取网页或逆向接口；
- commit、push、PR、merge、远程 CI 或进入 Step 1。

完成门禁：

- Git/PR/CI、无活动任务和干净基线事实一致；
- Step 0 收口时 F-004B2 是唯一 ACTIVE，Provider/法律 Gate 明确待 Step 1 审核；
- current-task、roadmap、implementation-plan、progress、evidence 一致；
- 文档检查器和 `git diff --check` 通过；
- diff 只含获批治理文档，无历史 evidence/归档任务卡改写；
- 首层本地分支存在且没有 commit 或远程写入。

## Step 1：Provider 与法律 Gate

唯一目标：只审核用户提供的正式书面授权、合同、工单回复或官方控制台事实，对固定 Provider 边界作出一个 `PASS` 或 `BLOCKED`。

必须确认 Provider、endpoint/version、产品场景、字段语义、展示与 attribution、派生/第三方应用、保存字段与最长 30 天留存、删除、价格、配额、QPS、资质、真实 UAT、凭证与销毁规则，以及 schema v2 可行性。

正式结果：`BLOCKED`。

- 回复允许非商用个人开发 Web 服务 API 场景、建议高德来源声明，并允许仅运行期内存临时保存；
- 回复明确禁止 SQLite 持久化，与批准的最终 observation 最长 30 天持久化边界冲突；
- 回复没有授权车次、铁路站点、发到时间和历时等 rail 字段；
- 所提供证据没有固定 endpoint/version、数值配额/QPS/价格或真实 UAT 准入与销毁规则；
- 审核没有访问价格链接，不把未提供的网页内容推定为证据。

Step 2–10 全部由本 Gate 阻塞。只有补充书面授权同时满足 rail 字段与批准持久化边界，或另行批准架构变更后，才能重新审核；不得自行采用纯内存替代。

## Step 2：V4 纯领域与 contracts

唯一目标：以 TDD 实现同 URI、独立 `request_version="4"` 的严格城际 segment typed union，以及来源、费用、时间、freshness 和终态纯领域规则。

不得接入 adapter、application、API、Repository、前端或真实 Provider。

## Step 3：城际 Provider adapter

唯一目标：以 fake/MockTransport/synthetic fixture 实现已通过 Gate 的单一 rail Provider adapter、严格 schema 和安全错误归一化。

不得接入 application 编排、真实调用或保存原始响应。

## Step 4：application runtime

唯一目标：接入 F-005 task-scoped attempt runtime、城际逻辑预算、并发 1、确定性同日直达选择、终态和 cancel/drain。

不得进入 Repository/API/前端或真实 Provider UAT。

## Step 5：persistence 与 API

唯一目标：保持同 URI 和公开顶层 shape，完成 V4 fingerprint、幂等、retry、DELETE、schema v2 typed JSON 往返、最长 30 天 observation 边界和 V3/V4 replan 写前拒绝。

不得修改 schema/migration，不得保存候选列表或 Provider 原始内容。

## Step 6：前端交互

唯一目标：实现 V4 每段手工/Provider 查询选择、来源/时效/unknown/partial 展示，以及 Provider 失败后的显式手工重提交流程。

前端不得推导 freshness、终态或静默切换来源。

## Step 7：离线纵向验收

唯一目标：运行至少 16 个 F-004B2 synthetic eval、临时 schema v2 SQLite、loopback desktop/390px 浏览器 QA、network/console/accessibility 和独立隐私安全审查。

默认测试和 CI 必须阻断非 loopback 网络；该 Step 不等同真实 Provider UAT。

## Step 8：独立真实 Provider UAT

唯一目标：仅在再次明确批准后，按 Step 1 已通过的凭证、域名、次数、费用、字段、脱敏和销毁边界执行有上限的真实 UAT。

当前状态：`BLOCKED_BY_STEP_1`。只有 Step 1 Gate 通过后，才可再次请求独立 UAT 批准；没有该批准与 UAT PASS 时，F-004B2 不得标记完整完成。

## Step 9：五层 stacked PR 交付

唯一目标：运行本地全量门禁，按五层拓扑完成 commit、push、stacked PR、逐层独立 review 和远程 CI。

不得 merge、clean-restack、运行最终 main CI 或归档。

## Step 10：合并、最终 CI 与归档（未执行）

原唯一目标：按批准顺序依次合并，必要时 clean-restack，运行最终 main CI，归档任务卡并关闭 F-004B2。由于 Step 1 Gate `BLOCKED`，本实现交付 Step 未执行；本次只进行独立 documentation-only blocked closure。

## 五层拓扑与核心文件

1. `feat/f-004b2-intercity-domain-contracts`
   - contracts、multicity/foundation/provider_result/resilience、可选纯领域 intercity_provider、直接 export 和对应测试。
2. `feat/f-004b2-intercity-provider-adapter`
   - Provider ports/models、已批准单一 adapter、factory/config wiring、MockTransport/synthetic contract 测试。
3. `feat/f-004b2-intercity-application-runtime`
   - tooling governance/resilience、multicity/provider planning services、budget/cancel/drain/eval 测试。
4. `feat/f-004b2-intercity-persistence-api`
   - Repository、trip plans/replans API、fingerprint/compatibility/SQLite 测试；schema/migrations 只读不改。
5. `feat/f-004b2-intercity-ui-delivery`
   - request/API/form/result/evidence UI、直接 fixtures、component/parser/browser 测试。

受控相邻扩展仅限直接 export、factory/wiring、同层 typed model、对应测试/synthetic fixture/golden，以及当前状态和 evidence 文档。单 Step 超过 5 个未预期生产/测试文件时停止。

| Stack | 建议文件上限 | 建议净新增行 |
| --- | ---: | ---: |
| 1 | 14 | 1200 |
| 2 | 12 | 1000 |
| 3 | 16 | 1500 |
| 4 | 14 | 1200 |
| 5 | 16 | 1500 |

任一 stack 超过 20 个生产/测试文件或净新增 1800 行、任务累计超过 75 个生产/测试/fixture 文件或净新增 6500 行时停止并重新拆分。

## 跨 Step 不变量

- F-001 `PARTIAL`、Step 45M `FAIL`、Step 45T `PASS`；
- unknown 金额保持 `null`，混合交通 fallback 只有离线证据；
- F-004A/F-004B1/F-005 无真实 Provider UAT，F-004B1 城际 Provider 调用 0；
- F-005 offline eval、MockTransport、synthetic fixture、loopback QA 不等于真实 UAT；
- legacy/V2/V3 兼容，V3/V4 replan 写前拒绝；
- SQLite schema version 2，migration 只有 1/2；
- 未经单独批准不得进入下一 Step。
