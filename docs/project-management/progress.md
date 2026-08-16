# 项目进度

## 当前状态

- 当前任务：`F-002 计划持久化、来源与版本`
- 状态：`ACTIVE`；任务卡已批准
- 当前 Step：`Step 6` 本地交付审查通过，Git/PR 交付执行中
- 下一批准动作：Step 6（Step 6 与 Git/PR 授权均已取得）；当前执行提交、PR 和远程 CI 验证
- 当前分支：`feat/f-002-local-plan-persistence`
- 当前提交：`38340dfed5c169911dc12042f4a90a5e042284c4`
- `main` 与 `origin/main` 一致
- Step 0–5 已完成；SQLite 基础设施、Repository/API 装配、单计划删除、30 天启动清理、acceptance record 和隐私边界已实现，前端历史能力仍不在范围内

## Step 0 结果

- 已核对指定项目文档、Git 基线和 F-001 归档事实。
- F-001 产品验收状态仍为 `PARTIAL`；Step 45M 历史真实 UAT `FAIL`；Step 45T 真实 UAT `PASS`。
- 门票等非关键费用仍为 `unknown`，不按 0 处理；混合交通 fallback 只有离线证据。
- F-002 已确认仅本地 SQLite、结构化字段 allowlist、来源与 freshness、内部版本、单计划删除、30 天保留期、项目自有 migration runner、现有 API 兼容和离线读取边界。
- 未读取 `.env.local`，未读取或输出秘密，未调用真实 Provider。

## Step 1 结果

- 已只读审计现有 Repository Protocol、内存 adapter、任务/结果/来源模型、状态机、API、架构和测试策略。
- 已冻结 8 张 SQLite 表、字段 nullable 语义、外键/唯一约束、索引、typed JSON 边界和 30 天清理字段。
- 已冻结升序 checksum migration、事务/rollback、SQLite PRAGMA、5 秒 busy timeout、Repository 条件 version 更新和 append-only plan version 语义。
- 已冻结 ready、partial、conflict、needs_input、failed、unknown/freshness、删除、重启、隐私和临时数据库测试矩阵。
- 未修改生产代码、Repository、API、前端或依赖；未创建数据库；未调用真实 Provider。

## Step 3 结果

- 已实现既有 `PlanningJobRepository` 的 SQLite adapter、typed hydration、job/attempt/trace、幂等指纹、乐观 version、结果 metadata、追加式 plan version 和 source records/link 映射。
- 已通过 28 项 persistence 测试、后端全量 904 项、前端 65 项、文档检查器 23 项及统一 format、lint、strict mypy、build 和文档门禁。
- 五种终态、unknown 金额 null、Decimal/时区/freshness、重启、retry、并发、版本冲突、事务回滚、损坏数据和隐私拒绝均有离线证据。
- 未修改 Repository Protocol、API、前端、Provider、依赖、Schema 或 migration；未创建真实数据库，未读取秘密，未访问真实 Provider。

## Step 4 结果

- 本地应用默认装配 SQLite Repository；lifespan 在服务请求前完成 migration，失败时 fail closed，并在关闭时释放连接。测试注入与无显式数据库路径的 test 模式继续使用内存替身。
- 临时 SQLite API 测试覆盖应用重启恢复、重复 POST、异请求幂等冲突、16 路并发创建、retry 乐观冲突和高版本数据库停止启动；Step 4 新增 9 项测试。
- 统一门禁通过：91 个 Python/脚本文件 format、Ruff、strict mypy，后端 913 项、前端 65 项、文档检查器 23 项和前端 build 全部通过。
- 公开路由/DTO、Repository Protocol、Schema、migration、前端、Provider 和依赖未改变；未创建真实业务数据库，未读取秘密，未访问真实 Provider 或非 loopback 网络。

## Step 5 结果

- 单计划 DELETE 返回 204，并级联移除 job-owned 数据；缺失/非法 ID 保持安全 404，删除后 client request ID 可复用。
- 启动在 migration 后执行一次最多 1000 条的过期清理；精确边界删除 `expires_at <= now`，保留任何尚未到期记录。
- acceptance record 仅保存 typed、代码化摘要并校验 attempt/plan version；完整日志、Prompt、provider body 和秘密字段无法进入该模型。
- 定向 80 项通过；统一门禁中后端 922 项、前端 65 项、文档检查器 23 项、Ruff、strict mypy 和 build 已通过；未访问真实 Provider、秘密或真实业务数据库。

## 当前阻塞与停止条件

- 原文件清单曾禁止 Step 2 所需的 SQLite/migration 基础设施和临时测试；本次已仅修复阶段化执行边界。
- Step 3 原文件清单冲突已修复并通过文档门禁，Step 3 实现和状态收口均已完成。
- Step 4 已完成并通过统一门禁；当前没有实现阻塞。
- Step 2 已获用户批准并完成实现验证；本次未修改生产源码以外的范围、未创建真实本地业务数据库、未读取 `.env.local` 或任何秘密。
- 用户已明确批准修改 `docs/README.md` 与 `roadmap.md`；Step 2 状态已完成同步并正式收口为 `DONE`。
- Step 2 的 12 项基础设施测试继续通过；Step 3 新增 16 项 Repository 测试后 persistence 共 28 项，后端全量共 904 项。
- Step 5 已完成；用户已批准 Step 6 和 retry 标识最小修复。
- retry attempt 2/3 已使用 job/attempt/trace 派生的稳定命名空间，attempt 1 标识、Schema、migration 和公开 API 保持不变。
- 纵向红测先复现第二 attempt `failed`，修复后成功追加第二计划版本；专项 53 项通过，统一门禁通过后端 923 项、前端 65 项、文档检查器 23 项及全部静态、类型和构建门禁。
- 最终本地复审无剩余 P0/P1；未访问真实 Provider、秘密、非 loopback 网络或真实业务数据库。
- 用户已授权创建指定功能分支、精确暂存、提交、推送、PR 和远程 CI 验证；仍不授权自动合并或提前归档。
- 若发现边界变更需求、秘密访问需求、真实 Provider 调用需求或超出允许文件清单，必须停止并请求用户确认。

## 权威入口

- 当前任务：[current-task.md](./current-task.md)
- 当前计划：[implementation-plan.md](./implementation-plan.md)
- 路线图：[roadmap.md](./roadmap.md)
- 验收证据：[evidence.md](./evidence.md)
