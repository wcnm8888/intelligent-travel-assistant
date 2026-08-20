# 项目进度

## 当前状态

- 当前任务：`F-004B1 多城市领域、用户提供的城际段与离线约束`
- 任务状态：`ACTIVE / APPROVED`
- 当前 Step：`Step 8 - 合并、main CI 与归档`，状态 `TODO`
- Step 0–7：`DONE`
- 当前分支：`feat/f-004b1-multicity-ui-delivery`
- 当前基线：`1a3e0a050721c72a6e83941f0cb5b2077decb1c7`
- 下一批准动作：Step 8；不得自动进入

## Step 0 完成摘要

- 已复核 `main == origin/main == HEAD`，基线为 F-004A 归档提交 `1a3e0a0`，修改前工作区干净；
- 已复核 PR #13/#16/#17/#18 合并、PR #14/#15 clean-restack 替代关闭，以及 main CI run `32360800884` 成功；
- 已确认激活前 current-task 没有活动任务；
- 已写入已批准 F-004B1 完整任务卡和 Step 0–8 计划；
- roadmap 已按 F-004B1 → F-005 → F-004B2 拆分排序，且只有 F-004B1 为 ACTIVE；
- product-brief 和 api-contract 的 F-004A 当前状态漂移已修正；
- 已新增 D-013 决策入口，并建立“核心文件清单 + 受控相邻扩展”治理；
- 已从干净 main 创建本地首层分支；
- 未提交、push、创建 PR 或 merge；未修改源码、测试、Schema、migration、依赖、lockfile、fixture 或数据库；
- 未读取 `.env.local`、秘密或本地 Provider 配置，未调用真实 Provider 或访问未批准外部服务。

## 当前产品与技术边界

- F-004A 已交付单城市连续 2–7 日、单住宿锚点、V2 typed contracts、schema v2 typed JSON 和 V2 恰好两日 replan；
- F-004B1 的纯领域/contracts、Repository/API/SQLite schema v2 往返、离线 V3 planning/调用治理及前端多城市交互/恢复已在 Step 2–5 实现；
- 城际 Provider 调用为 0；铁路/航空/长途客运真实数据源属于 F-004B2；
- 推荐顺序为 F-004B1 → F-005 → F-004B2；
- F-001 产品状态保持 `PARTIAL`；
- Step 45M 历史真实 UAT `FAIL`、Step 45T `PASS` 均保留；
- unknown 保持 `null`，混合交通 fallback 只有离线证据；
- F-004A 没有真实 Provider UAT。

## Step 1 完成摘要

- 已冻结独立 `request_version/plan_format_version/response_version="3"`，V3 不继承或污染 legacy/V2 字段集合；
- 已冻结 2–3 城、3–7 日、每城至少一晚、累计夜数派生转移日、相邻用户段、三种 mode、同日时间和方式缓冲；
- 已冻结 V3 每日出发/到达/住宿城市、转移日最多一项活动、市内 RouteLeg 不跨城、用户 fare/unknown 和安全来源披露；
- 已冻结同 URI 严格三分支、V3 canonical fingerprint、Repository typed union、schema v2 typed JSON、旧应用 fail closed 和无 migration v3；
- 已冻结全部 V3 replan 在 reserve/Provider/write 前 422 拒绝；
- 已冻结按城市 Provider 调用上限、全局模型 1+1、route/城市并发、180 秒 deadline 和城际 Provider 调用 0；
- 已冻结前端显式模式、城市/段卡、字段错误、结果/离线恢复、V3 无 replan 和 desktop/390px 门禁；
- 已冻结 Step 2–7 分层 RED/GREEN 与兼容、SQLite、Provider、隐私和浏览器测试矩阵；
- 未实现生产代码或测试，未修改 Schema/migration/依赖，未读取秘密或调用 Provider。

## Step 2 完成摘要

- TDD 首轮 RED 证明多城市领域类型与 V3 contracts 缺失；第二轮证明跨日城市连续性和 summary 夜数派生转移日绑定缺失；第三轮证明 ready 终态可错误携带 error；三轮均完成最小 GREEN；
- 纯领域覆盖 2–3 城、3–7 日、每城至少一晚、累计夜数、相邻用户段、+08:00 同日时间、rail/air/coach 缓冲、普通/转移日活动、同城市内路线、逐城住宿、用户 fare/unknown 和五终态；
- 独立 V3 contracts 覆盖 request/plan/response、城市/段/日 DTO、住宿/站点/活动/路线引用、跨日连续性、用户来源和终态 final validation；
- V3 没有加入现有 Planning unions，Repository/API/SQLite 集成留给 Step 3；
- 定向回归 `102 passed`，全仓 Ruff format/lint 与 strict mypy 通过，legacy/V2 fingerprint 保持；
- 未修改 Repository/API、SQLite/schema/migration、Provider、前端、依赖或 lockfile；未创建数据库、读取秘密、调用外部服务或执行远程 Git 写入。

## Step 3 完成摘要

- TDD 首轮 RED 证明 V3 无 Repository result variant；补充 RED 证明无 plan 终态可绕过 request/result 版本匹配；均以最小 typed union 和 fail-closed 修复转绿；
- 三组 planning unions 已严格扩为 legacy/V2/V3；新增 `PlanningJobResultV3`/`PlanningResult`，Repository port 方法集合不变；
- 内存与 SQLite schema v2 覆盖 V3 fingerprint、幂等、record_result、重启水合、retry、DELETE、30 天有界清理、损坏 plan fail closed 和旧 models 读取 V3 失败；
- 同 URI API 覆盖 POST/GET/retry/DELETE、三分支 OpenAPI、非法 tag 422、V3 draft/partial 投影和不调度 V3 executor；
- V3 replan 的 API/service create、decide、execute 均在 reserve/lookup/decision/executor/write 前拒绝；SQLite replan/decision/lineage 为 0，job version/status 不变；
- Step 3 新增集合 `31 passed`，相关 Repository/API/replan 回归 `170 passed`，Provider 相邻纯离线回归 `33 passed`，SQLite API 回归 `17 passed`；全仓 Ruff/strict mypy 通过；
- schema/migration、依赖、lockfile、前端均未修改；临时 SQLite 仅位于系统临时目录；未读取秘密、调用真实 Provider 或执行远程 Git 写入。

## Step 4 完成摘要

- 两轮真实 RED 分别证明缺少多城市编排/governor，以及 proposal parser 仍只接受 V2 日期上下文；最小修复后转绿；
- 独立 V3 编排器按城市复用既有 Provider ports，生成一个全局 proposal，并由确定性代码注入城市连续性、用户段、缓冲、市内路线、活动时间、预算、来源和终态；
- 调用预算为 resolve ≤ C、POI ≤ 3C、forecast/alert ≤ C、generation/repair 各 1、route ≤ min(28,4D)，城市事实与 route 并发均为 2，总 deadline 180 秒；
- 取消测试证明两条在途 route peer 均被 drain、active 归零且第三条未启动；deadline 测试证明首个 Provider call 前拒绝；
- V3 repair 只接收安全诊断与脱敏结构上下文，不接收原始模型输出、自由文本、兴趣、硬约束或用户城际段原文；intercity Provider 调用恒为 0；
- 新增集合 `9 passed`；application `505 passed`，API/contracts/持久化相关 `141 passed`，bootstrap `22 passed`，DeepSeek/parser `102 passed`；Ruff、strict mypy 和 diff 检查通过；
- 未修改 schema/migration、Repository 方法集合、依赖、lockfile 或前端；未读取秘密、调用真实 Provider、创建业务数据库或执行远程 Git 写入。

## Step 5 完成摘要

- RED 先证明旧 parser 拒绝严格 V3 response 且表单没有多城市入口；当时既有前端 88 项保持通过；
- 默认单城市和 legacy/V2 请求保持；显式多城市模式支持 2/3 城、夜数平衡、相邻段、+08:00 派生转移日、三种缓冲、用户排序/删除和字段首错；
- 城市排序只由用户按钮触发，排序后相邻段全部清空并通过 live region 披露；第三城删除只移除相邻派生段并恢复焦点；
- V3 parser/结果覆盖城市路线、逐日城市连续性、独立城际段、缓冲、用户来源、unknown/partial 和 V3 无 replan；unknown 费用明细不显示为 `¥0`；
- V3 job UUID 仅作为本机恢复指针保存；重启通过同源 GET 读取权威快照，不保存请求、站点、票价或 Provider 数据；
- 专项 `7 passed`、前端全量 `95 passed`，format/lint/typecheck/build 通过；依赖/lockfile、schema/migration 与后端无本 Step 修改；
- 未读取 `.env.local`/秘密，未调用 Provider、创建数据库、访问外部服务或执行远程 Git 写入；Node 24.19.0 对项目声明 22.16.0 产生 engine warning，但命令均成功。

## Step 6 完成摘要

- 临时 SQLite 纵向覆盖 V3 create/read/restart/retry/delete、幂等、2/3 城、五终态和 V3 replan 拒绝；相关 legacy/V2/V3 回归 `45 passed`；
- browser-only synthetic executor 在 retry attempt 2 生成 job 唯一 source/plan identity，保持 schema v2、migration 1/2 和 Repository 冲突语义不变；
- 真实 loopback Vite → FastAPI → SQLite → synthetic 链在 desktop `1440×1000` 与 `390×844` 通过，刷新恢复成功，横向溢出 0、console error/warning 0，58 条请求全部指向 `127.0.0.1`；
- 键盘/无障碍验证覆盖第三日、skip link、第三城删除/新增焦点；发现新增第三城焦点丢失后以 RED/GREEN 修复，新输入获得焦点；DOM 审计 duplicate id、无效 ARIA 引用和无名称交互项均为 0；
- 前端全量 `95 passed`，ESLint 与 TypeScript 通过；触及后端文件 Ruff 与 strict mypy 通过；
- 独立安全/隐私/兼容 diff scan `efd6640a-731a-47ce-b4e8-58bf3931d5dc` 完整覆盖 36 个生产文件 review item 和 6 个信任面，0 finding；TAC advisory 因 connector 未登录保持未验证；
- 本轮创建的两份 synthetic 临时 SQLite 已在精确进程关闭后从系统临时目录删除；未读取秘密、调用真实 Provider/非 loopback 服务、修改 schema/migration/依赖/lockfile 或执行远程 Git 写入；
- F-001 `PARTIAL`、Step 45M `FAIL`、Step 45T `PASS`、unknown、混合交通 fallback 仅离线和 F-004A 无真实 Provider UAT 均保持。

## Step 7 完成摘要

- 最终累计全量门禁通过：strict mypy 134 files、backend `1166 passed`、frontend `95 passed`、build 与 24 项文档检查器均成功；
- Draft PR #19/#20/#21/#22 按 domain → persistence/API → planning → UI/docs 的直接 base 拓扑创建；最终 CI runs `32379371761`、`32379662820`、`32379802803`、`32379941695` 全部成功；
- 首轮 #19/#20 CI 失败未隐藏；V3 union、测试辅助模块和 fail-closed 兼容被校正到所属层，并以普通追加提交逐层传播，无 force-push；
- 四层生产/测试净新增 1679/1393/2120/2497，累计 7689；每层 ≤30 文件且净新增 ≤2500，累计未超过 8000；
- diff/range/依赖/秘密复核通过，无 migration、Schema、依赖、lockfile 或城际 Provider 文件变更；review 无阻塞 finding；
- 四个 PR 保持 Draft；未 merge、未运行 main CI、未归档、未读取秘密或调用真实 Provider。

## 阻塞与停止条件

当前没有事实冲突或技术阻塞。Step 8 尚未授权。

如需改变已批准 merge/clean-restack 拓扑、migration v3、新依赖、新 Provider、隐私边界变化、真实外部调用，或出现无法解释的 CI/文档事实冲突，立即停止并请求确认。

## 权威入口

- 完整任务卡：[current-task.md](./current-task.md)
- Step 0–8 计划：[implementation-plan.md](./implementation-plan.md)
- 路线与优先级：[roadmap.md](./roadmap.md)
- 验收证据：[evidence.md](./evidence.md)
- 长期决策：[D-013](../decisions.md)
