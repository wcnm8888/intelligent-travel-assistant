# F-002：计划持久化、来源与版本（归档）

## 归档元数据

- 任务等级：`L`
- 交付状态：`DELIVERED`
- 验收结论：`PASS`
- 完成 Step：`Step 0–6`
- 功能分支：`feat/f-002-local-plan-persistence`
- 实施提交：`729119b9f583bfa80c421a9231f19694df38ab5f`
- 交付证据提交：`6b9f0ec44522502a334fef5d0b4e1b31e1d5000e`
- PR：[PR #6](https://github.com/wcnm8888/intelligent-travel-assistant/pull/6)
- 主线合并提交：`34fce5826db30ec30f7ae446ac2eb073a37cece9`
- 合并提交 main CI：run `31924066600` / job `95108718835`，`PASS`

## 用户目标与工程价值

将 F-001 的进程内临时任务和结果扩展为本地 SQLite 持久化能力，使单城市双日旅行计划可在应用重启后恢复，并保留任务、attempt、计划版本、来源、decision 和 acceptance 的可追溯结构，同时维持 Repository 隔离、unknown 语义和本地隐私边界。

## 已交付范围

- 标准库 SQLite 连接生命周期、PRAGMA 和项目自有 checksum migration runner；
- `schema_migrations`、`planning_jobs`、`planning_attempts`、`plan_versions`、`source_records`、`plan_version_sources`、`decision_records`、`acceptance_records`；
- 既有 `PlanningJobRepository` 的 SQLite adapter，保持幂等指纹、expected version、乐观锁和五种终态语义；
- 现有 POST/GET/retry API 默认装配本地 SQLite，保持公开契约兼容；
- 单计划 DELETE、job-owned 级联、30 天启动时有界清理和内部 typed acceptance record；
- retry attempt 2/3 使用 attempt/trace 稳定命名空间，attempt 1 标识保持兼容；
- 临时 SQLite 覆盖迁移、重启、幂等、并发、冲突、retry、版本、来源、删除、保留期、Decimal/时区 round-trip 和隐私拒绝。

## 数据与隐私边界

- 仅支持本地 SQLite，数据库实现隔离在 Repository adapter；
- 只保存 allowlist 结构化请求，以及完成计划所需的转换后地点、路线、预算、天气、来源、freshness、attribution 和安全链接；
- 不保存 Key、Token、JWT、私钥、Cookie、Authorization、完整 Prompt、provider 原始响应或原始错误 body；
- `unknown` 金额保持 `null`，不得转换为 0；`partial`、`conflict`、`needs_input` 和 `failed` 不得伪装为 `ready`；
- 测试只使用内存替身、fake 和临时 SQLite，不访问真实 Provider 或非 loopback 网络，不创建真实业务数据库。

## 明确非目标

- 历史计划列表 API、版本比较或恢复、清空全部本地数据；
- 前端历史计划页面；
- 登录、同步、多用户、云数据库或公网部署；
- 多城市、多日或局部重规划；
- provider 原始数据持久化和 F-001 进程内历史导入。

## 验收与交付证据

- 本地全量门禁：Ruff、strict mypy、后端 923 项、前端 65 项、文档检查器 23 项和 Vite build 通过；
- retry 纵向回归：真实生产 executor 配合离线 fake provider，经临时 SQLite 完成首次计划、retry 和第二计划版本，attempt 1 兼容且后续 attempt 标识不冲突；
- 实施提交 CI run `31923661440`、最终 PR head CI run `31923863259`、合并提交 main CI run `31924066600` 均通过；
- 最终审查无剩余 P0/P1。

## F-001 历史边界

- F-001 产品验收状态继续为 `PARTIAL`；
- Step 45M 历史真实 UAT `FAIL` 与 Step 45T 真实 UAT `PASS` 均保留；
- 门票等非关键费用继续为 `unknown`，不按 0 处理；
- 混合交通 fallback 仍只有离线证据。

## 后续入口

- 路线图：[roadmap.md](../../project-management/roadmap.md)
- 当前任务：[current-task.md](../../project-management/current-task.md)
- 实施计划：[implementation-plan.md](../../project-management/implementation-plan.md)
- 验收证据：[evidence.md](../../project-management/evidence.md)

当前无活动任务。F-003 仍为候选，不因 F-002 完成而自动启动。
