# 项目进度

## 当前状态

- 当前任务：`F-003 局部重规划与影响确认`
- 任务状态：`ACTIVE`；任务卡已批准
- 当前 Step：`Step 8`，状态 `ACTIVE`；用户已明确批准
- 下一动作：推送并创建三层 stacked PR，验证 CI 后按依赖顺序合并，再核验 main CI 和归档
- 当前分支：`feat/f-003-local-replanning-confirmation`；本地三层 stack 已建立
- Git 基线：`main` 与 `origin/main` 均为 `c836138240473f079565527b13a0d53516235c45`
- CI 基线：main run `31924427372` 通过

## 最近完成

- B-000、F-001、F-002 均已交付并归档；
- F-003 L 级任务卡及产品、影响分级、确认、数据、API、migration、UI 和隐私决策已获用户批准；
- Step 0 已核对文档、代码、Schema、Git 和 CI，并清除 F-002 的当前状态残留；
- F-003 Step 1 已完成领域、lifecycle、API、migration v2、Repository、测试矩阵和 UI 设计冻结；
- F-003 Step 2 已用 TDD 实现纯领域 command、impact、change set、预算和来源策略；35 项新增测试、178 项领域回归和 981 项后端全量测试通过；
- Step 3 已实现 migration v2、`replan_requests`、`plan_version_lineage`、独立 ReplanRepository port、内存替身、SQLite adapter 和 typed Decision 映射；
- Step 3 的 API SQLite 生命周期 8 项、专项 12 项、相关回归 81 项和后端全量 963 项通过；Ruff、format 与 strict mypy 通过；
- API 测试已明确验证 migration 1/2，并以 version 3 保持未来数据库 fail-closed；Step 3 已完成并收口；
- Step 4 已实现 application replan service、确认/取消/过期、provider-neutral 离线执行、Repository outcome/commit 和 SQLite 原子版本提交；
- Step 4 专项 19 项、application+persistence 回归 494 项、后端全量 1001 项通过；Ruff、format、strict mypy、文档与 diff 门禁通过；
- 同 baseline 并发只允许一个提交成功；失败、conflict、取消和过期保持原计划，unknown 不转为 0，partial 不伪装 ready；
- Step 5 已实现三个窄 replan API、严格 DTO、安全错误映射、后台执行快照和 completed result/change-set 投影；
- Step 5 专项 31 项、相关回归 571 项和后端全量 1016 项通过；108 文件 format、Ruff 与 61 source files strict mypy 通过；
- 既有 POST/GET/retry/DELETE API 形状保持不变；未修改 Provider adapter、前端、依赖、环境、Schema/migration 或连接层，未创建真实业务数据库；
- Step 6 已实现四种结构化前端入口、影响与来源预览、确认/取消、执行状态、completed 差异、unknown/partial、安全失败和焦点恢复；前端 73 项测试及 lint/typecheck/format/build 通过；
- Step 7 已新增临时 SQLite 纵向测试并执行桌面/`390×844` synthetic 浏览器 QA；浏览器 completed、failed、expired、version conflict 均保留原计划且无横向溢出；
- Step 7 独立安全审查覆盖 33/33 个变更源/测试文件，确认 stale confirmation 未绑定 captured job version 的 medium finding；两个其他候选已由 rollback probe 和威胁边界反证排除；
- Step 7 已按后续明确授权修复 planning/replan trace 错配与 stale confirmation version 绑定：旧确认在 executor 前冲突，并发失败持久化为 conflict，成功提交可重启恢复；
- Step 7 聚焦 18 项、相关回归 219 项、后端全量 999 项和前端 73 项通过；Ruff、format、strict mypy、ESLint、TypeScript 和 build 通过；浏览器 completed/failed/version conflict 复验通过，390px 无横向溢出且仅 loopback 资源；
- 未读取秘密、调用真实 Provider、访问非 loopback 网络、创建分支或执行远程写入。
- Step 8 独立复审发现并关闭重复执行、异常悬挂、确认 TTL、旧版本元数据串版、unknown→ready 和前端确认恢复等阻塞；最终统一入口通过后端 1007、前端 76、文档检查器 24 及全部静态、类型和 build 门禁；
- Step 8 synthetic UAT 已复验影响预览、确认、completed 新版本/change set、状态焦点和 390px 零溢出；全部业务请求为 loopback，控制台 0 error/0 warning；一次缺失公开夹具日期变量的无效运行不计通过证据；
- 已建立领域、持久化/应用、API/前端/验收三层本地 stack，共四个代码主题提交；尚未 push、创建 PR、合并或归档。

## 已批准边界摘要

- 单城市双日；四种结构化活动修改；不新增活动，不改城市、日期或住宿锚点；
- same-day low impact 自动，高影响确认，cross-city 拒绝；
- 独立 replan lifecycle，确认有效期 15 分钟；
- conflict/failed/取消/过期保持原计划；
- 成功追加新版本，不支持历史列表、任意版本比较或恢复；
- migration v2 方向；默认完全离线，live UAT 另行限次授权；
- unknown 不按 0，partial 不伪装 ready。

## 当前阻塞和停止条件

- 当前无新增产品决策或技术阻塞；Step 8 已进入，等待远程 CI、依赖顺序合并和归档；
- F-003 累计变更涉及 48 个生产/测试文件、12 个文档和 2 个文档检查脚本，当前 diff 为 `+10488/-602`，已超过 35 文件/3,000 行停止阈值；用户已明确选择 stacked PR，范围决策阻塞解除；
- D-004 已由 D-011 解释为独立 replan lifecycle，PlanningJob 11 状态保持不变；
- migration、API、UI 或文件规模需要改变批准边界时必须停止；
- 预计超过 35 个生产/测试文件或净新增 3000 行时必须重新决定单 PR 或 stacked PR。

## 权威入口

- 当前任务：[current-task.md](./current-task.md)
- 当前计划：[implementation-plan.md](./implementation-plan.md)
- 路线图：[roadmap.md](./roadmap.md)
- 验收证据：[evidence.md](./evidence.md)
