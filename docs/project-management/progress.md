# 项目进度

## 当前状态

- 当前任务：`F-004C 用户已购铁路段与车次信息`，唯一 `ACTIVE`
- 当前 Step：`Step 6 - 三层交付与归档（执行中）`
- 当前 Step 状态：`ACTIVE`
- 基线：`main == origin/main == 577bdcbadf2e024022e59e52527d13edb0cbd659`
- 当前分支：`feat/f-004c-booked-rail-domain-contracts`
- 最近关闭：F-004B2 `BLOCKED / ARCHIVED`；不得恢复其 Provider 查询或 Step 2
- 下一候选：F-006；不得自动启动

## F-004C Step 0

- 已复核 F-004B2 documentation-only closure：PR #33 已合并，最终 main CI run `32463645980` 为 `success`，归档任务卡存在；
- 已复核 Step 0 开始前 `main == origin/main == 577bdcbadf2e024022e59e52527d13edb0cbd659`、工作区干净、没有活动任务或开放 PR；
- 已从该干净 main 基线创建首层本地分支 `feat/f-004c-booked-rail-domain-contracts`；HEAD 未增加提交；
- 已激活 D-016：独立 V4 只承载用户已购铁路段，F-004B2 继续 `BLOCKED / ARCHIVED`，未来真实城际 Provider 必须使用新版本和新决策；
- 已建立 Step 0–6、三层 stacked PR、核心文件、受控相邻扩展和规模阈值；
- 本 Step 只修改当前治理与权威文档，不修改源码、测试、fixture、Schema、migration、依赖、lockfile、数据库、历史 evidence 或归档任务卡；
- 本 Step 不读取秘密，不调用 Provider，不 commit、push、创建 PR 或触发远程 CI，也不进入 Step 1。
- Step 0 状态：`DONE`；文档门禁、`git diff --check` 和范围审计通过。

## 当前边界与下一入口

F-004C V4 只支持中国大陆 2–3 城相邻、单向、同日、直达 rail 的用户提供段。`service_number` 必填并规范化，来源固定为 `user_provided / unknown_validity / 用户提供，未核验`；城际 Provider logical call 和 HTTP attempt 均为 0。legacy/V2/V3、SQLite schema v2 与 migration 1/2 保持不变。

Step 0–5 已完成。Step 5A 已将 V4 preferences 收窄为 interests-only strict allowlist，补齐 API 422、零 job/SQLite 写入、generation/repair context 和前端 synthetic sentinel，并经 Codex Security 与独立只读复审确认无 finding。Step 6 已获单独批准，当前正在执行全量门禁与三层交付；尚未宣称任务归档完成。

## F-004C Step 1

- 状态：`DONE`；已冻结独立 V4 request/plan/response exact shape、service number 规范化、同日 `+08:00`/60–30 缓冲、positive/null fare 和 user/unknown 来源；
- 已冻结 canonical fingerprint、V4 typed union、SQLite schema v2 JSON 往返、同 URI API、V3/V4 replan 写前拒绝及旧版本 exact compatibility；
- 已冻结 Agent allowlist：service number、完整 segment 和原始城际文本不进入 proposal/repair；城际 logical call/HTTP attempt 均为 0；
- 已冻结显式 V3/V4 前端选择、V4 车次/隐私/来源展示、strict parser/recovery，以及 domain→SQLite/API→UI/browser 的分层测试矩阵；
- 三层核心文件和规模阈值不变；本 Step 只修改权威文档，没有修改源码、测试、fixture、Schema、migration、依赖或 lockfile，没有读取秘密、调用 Provider 或执行 Git 交付；
- Step 2 已完成；当前不得自动进入 Step 3。

## F-004C Step 2

- 状态：`DONE`；RED 首次因 V4 domain/contracts 直接 export 不存在而 collection 失败，随后以最小 GREEN 实现；
- 领域：新增 strict service number 规范化、固定 rail、同日 `+08:00`、派生 duration/transfer date、positive/null fare 和 60/30 分钟缓冲；
- contracts：新增独立 V4 request/plan/response concrete strict models，额外/票务越权字段、跨 tag、非 rail、错误时间与费用 fail closed；duration 只作 Python 派生属性，不进入 JSON；
- 来源：继续只允许 `user / user_provided_intercity_segment / unknown_validity / 用户提供 / 未核验班次、票价、余票或库存`，unknown fare 保持 null 并阻止 ready；
- 兼容：全量后端 `1344 passed`；legacy/V2/V3 union、shape 与既有行为未接线改动。V4 的全局 union、fingerprint、Repository/API/application 接线明确留给 Step 3；
- 静态门禁：Ruff format/check 与 mypy 全部通过；本 Step 6 个预期生产/测试文件、净新增约 1145 行，未触发阈值；
- 未执行：无数据库、Schema/migration、依赖/lockfile、外部调用、秘密读取、Git 交付或 Step 3 修改。

## F-004C Step 3

- 状态：`DONE`；三个新纵向测试模块首次因 `PlanningJobResultV4` 不存在而 collection RED，随后最小 GREEN；
- application：复用 V3 城市事实与离线规划路径，但在 Agent 边界前移除 service number，并在结果侧从原始 typed V4 request 确定性重建 `PlanBookedRailSegmentV4`；没有新增城际 Provider 能力或调用；
- Repository/SQLite：新增 V4 request/result/plan typed union、跨版本匹配、canonical fingerprint、memory/SQLite schema v2 hydration、restart/retry/delete；migration 仍精确为 1/2；
- API/replan：沿用 POST/GET/retry/DELETE URI 和顶层 envelope，OpenAPI 增为第四个严格 request 分支；V3/V4 replan 在 reserve/lookup/decision/executor 和持久化写入前拒绝；
- 验证：Step 3 定向 `9 passed`，相邻 V4/V3 application/Repository/API/contracts `73 passed`，全后端 `1353 passed`，Ruff/mypy 通过；
- 规模：Step 3 为 15 个预期生产/测试文件、净新增约 740 行；Stack 2 未超过 18 文件/1400 净行，任务累计未超过 50 文件/4000 净行；
- 未执行：无前端、浏览器、真实 Provider、Schema/migration、依赖/lockfile、秘密读取、Git 交付或 Step 4 修改。

## F-004C Step 4

- 状态：`DONE`；首批 6 项独立 V4 前端测试首次为 `1 passed / 5 failed`，随后补入同 URI retry 与三城市双段覆盖，最终 8 项全部通过；
- 表单：V3“自行填写交通段”仍为默认，显式选择“填写已购铁路车次”才生成 V4；切换清空段卡，V4 固定 rail，车次 trim/uppercase/格式校验并参与首错焦点；
- parser/result：V4 request/response/plan tags、segment exact keys 与 canonical service number fail closed；结果显示铁路车次、确定性格式化历时、用户提供/未核验、unknown-validity 和 null 金额，不推导服务端终态或声称可售/已出票；
- 恢复：沿用同 POST/GET/retry/DELETE URI；V4 使用独立本机 job UUID pointer，reload 只读 authoritative job，retry 只接受 attempt 2/3 的清空快照；V3 pointer 和旧版本行为保持；
- 验证：V4 定向 `8 passed`，全量前端 `107 passed`，Prettier、ESLint、TypeScript 和 Vite build 通过；
- 规模：Step 4 为 13 个预期生产/测试/fixture 文件、净新增约 802 行；Stack 3 未超过 18 文件/1400 净行，任务累计约 34 文件/2687 净行，未触发停止阈值；
- 未执行：无临时 SQLite、browser QA、真实 Provider、Schema/migration、依赖/lockfile、秘密读取、Git 交付或 Step 5 操作。

## F-004C Step 5

- 状态：`DONE / PASS`；SQLite、desktop/390px、仅 loopback 网络、console 和基础 accessibility 证据已完成；
- 原 finding：首次独立审查发现 V4 复用通用 preferences，可使 `free_text` / `hard_constraints` 进入 SQLite 和 generation context；Step 5 当时正确阻塞，历史证据保留；
- Step 5A 修正：V4 改用只含 `interests` 的 strict preferences；非法字段返回 422 且不创建 job，内部 projection 只复制 interests，前端 V4 清空并隐藏自由文本、serializer 只提交 interests；
- 回归：contracts/application/API/SQLite/Agent/frontend synthetic sentinel 全部通过；legacy/V2/V3 继续使用既有 preferences shape；后端全量 `1360 passed`、前端全量 `107 passed`，Ruff、mypy、Prettier、ESLint、TypeScript 与 Vite build 通过；
- 审查：Codex Security working-tree scan 为 0 findings，独立只读复审为 `NO FINDINGS`；原 privacy finding 已关闭；
- 规模：Step 5A 为 5 个批准生产文件和 4 个对应测试文件；按 Git numstat 复算，任务累计 35 个生产/测试/fixture 文件、净新增 3182 行，未触发 50 文件/4000 行停止阈值；Schema/migration、依赖/lockfile diff 为 0；
- 当前入口：Step 6 已获单独批准并执行中；只允许三层 commit/push/stacked PR、独立 review/CI、顺序合并、必要 clean-restack、最终 main CI 和归档。

## 保留历史事实

- F-001 产品状态为 `PARTIAL`；
- Step 45M 真实 UAT 为 `FAIL`，Step 45T 真实 UAT 为 `PASS`；
- unknown 金额不按 0；混合交通 fallback 只有离线证据；
- F-004A、F-004B1、F-005 均无真实 Provider UAT；
- F-004B1 城际 Provider 调用为 0；
- SQLite schema 保持 version 2，migration 只有 1/2。

## 权威入口

- [当前任务](./current-task.md)
- [实施计划](./implementation-plan.md)
- [路线图](./roadmap.md)
- [证据](./evidence.md)
- [D-016](../decisions.md#d-016f-004c-用户已购铁路段与车次信息)
- [D-015](../decisions.md#d-015f-004b2-真实城际-provider-与可信城际事实条件式边界)
- [F-004B2 BLOCKED archive](../archive/task-cards/F-004B2-real-intercity-provider-blocked.md)
- [F-005 archive](../archive/task-cards/F-005-external-service-resilience-freshness-agent-eval.md)
