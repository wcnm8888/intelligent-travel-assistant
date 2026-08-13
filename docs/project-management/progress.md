# 项目进度

## 当前目标

完成 `B-000：项目与工程基线`，建立可开发、可运行、可验证和可交接的本地工程底座。

## 当前状态

- 当前任务：`B-000`
- 当前阶段：工程基线启动
- 当前分支：`chore/b-000-project-baseline`
- 最近完成：Step 15 的私有仓库、bootstrap main、任务分支、Draft PR #1、远程 CI、六项 finding 修复和最终 review
- 当前阻塞：无；合并和任务归档需要 Step 16 单独授权
- 下一批准动作：Step 16，合并后收口；不得自动开始 F-001

## 已验证事实

- bootstrap 根提交：`4dfe6b2 chore: initialize repository`
- bootstrap 提交树为空
- Python 基线：3.13.3，由 uv 管理
- Node.js 基线：22.16.0
- 目标项目在 Step 2 前没有项目文件
- Agent1 未修改
- `E:\Agent\zonghe-anli` 当前不存在，本项目不恢复或重建

## 当前边界

- 任务分支已创建；B-000 项目文件已形成单一、本地交付提交
- 前后端健康骨架、依赖锁、统一门禁、本地 Chromium 闭环、CI 配置、独立 QA、最终用户 UAT、本地提交、私有远程、Draft PR、远程 CI 和最终 review 已完成；merge 与归档尚未完成
- 后端 Ruff format/check、mypy、7 项 pytest 和本地 `GET /api/health` 请求已通过；这些是 Step 8 实施验证，不替代 Step 13 独立 QA
- 前端 Prettier、ESLint、TypeScript、8 项 Vitest、peer 检查和生产构建已通过；这些是 Step 9 实施验证，不替代 Step 10 浏览器 UAT 或 Step 13 独立 QA
- Step 10 已验证 loading/disabled、success、error、retry recovery、390px 无水平溢出、键盘聚焦和仅本机请求；服务验证后已关闭，端口 5173/8000 已释放
- Step 11 统一入口已通过运行时、锁文件、后端、前端、构建、6 项文档检查器测试和实际文档契约；临时断链使整体返回 1，恢复后重新通过
- Step 12 workflow 使用 Windows runner、只读仓库权限、禁用 checkout 凭证持久化、空业务 provider 凭证和完整 Action SHA，只调用统一验证入口
- Step 12 将文档检查器扩展为 10 项测试；临时浮动 Action 标签触发 `ci-action-pin` 并返回 1，恢复后完整统一门禁通过
- Step 13 独立复跑统一入口全绿，并定向通过 5 项后端、8 项前端和 4 项文档/安全负向契约
- Step 13 Chromium 复现 `200 → 502 → 200`，390px 无水平溢出、Tab 聚焦重试按钮，全部 33 条请求仅指向本机
- Step 14 用户确认成功、错误、重试恢复、文案和窄屏表现均符合预期，并授权精确暂存及创建本地提交
- 50 个未跟踪文件均属于批准范围，但高于原 40 个停止阈值；用户在获知数量后批准本 Step，本 Step 未新增文件，只更新现有证据文档
- 裸 `pnpm` 在当前 Codex 环境中使用 bundled Node 24.19.0；后续项目命令必须通过 Corepack 使用 Node 22.16.0 和 pnpm 11.19.0
- 前端依赖已安装在被忽略的 `node_modules`，构建产物位于被忽略的 `frontend/dist`；未执行缓存清理
- 尚未调用任何真实外部 API
- 尚未创建高德或和风天气账户和 Key
- `origin` 已配置为私有仓库，`main` 和任务分支已推送，Draft PR #1 已创建；尚未 merge

## 权威入口

- 文档地图：[../README.md](../README.md)
- 当前任务：[current-task.md](./current-task.md)
- 当前计划：[implementation-plan.md](./implementation-plan.md)
- 长期决策：[../decisions.md](../decisions.md)

本文件只保留当前状态和最近结果，不追加逐轮对话或完整终端日志。
