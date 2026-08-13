# Intelligent Travel Assistant

Intelligent Travel Assistant 是一个面向中国大陆境内自由行的本地旅行决策辅助工具。目标用户是个人和小型同行群体；系统将基于目的地、日期、预算、偏好、交通和住宿要求，组合真实外部数据，生成可校验、可局部重规划且能说明来源与不确定性的旅行计划。

## 当前状态

项目正在执行 `B-000：项目与工程基线`。当前已建立本地 Git 与文档基线、运行时和工作区配置，并交付 FastAPI 健康服务、React 健康诊断页、统一本地门禁和 GitHub Actions CI 配置；Step 13 全量门禁与独立 QA、Step 14 最终用户 UAT 和本地提交均已通过。Step 15 已创建私有 GitHub 仓库和 Draft PR #1，并在修复 Windows 冷启动版本探测后取得远程 CI 成功证据；当前正在处理最终 review 发现的问题。项目没有旅行规划业务，也没有真实外部服务调用；review 收口、merge 和任务归档尚未完成。

- 运行边界：仅本地运行，后续允许经显式配置访问外部 API。
- 当前活动任务：[B-000 任务卡](./docs/project-management/current-task.md)
- 当前实施步骤：[B-000 Implementation Plan](./docs/project-management/implementation-plan.md)
- 最近状态：[项目进度](./docs/project-management/progress.md)
- 全部文档职责与入口：[项目文档地图](./docs/README.md)

## 核心规格

- [产品说明](./docs/product-brief.md)：用户、场景、MVP、成功标准和非目标；
- [系统架构](./docs/architecture.md)：模块、依赖、数据流、状态机、错误和 MCP 边界；
- [技术栈](./docs/tech-stack.md)：运行时、框架、依赖管理和版本策略；
- [交互设计](./docs/design-spec.md)：轻量 Web UI 流程、状态和降级体验；
- [Agent 领域规格](./docs/agent-domain-spec.md)：编排 Agent、工具、确认、追踪和失败边界；
- [测试与质量策略](./docs/testing-strategy.md)：测试分层、失败矩阵、live smoke 隔离和门禁；
- [项目 Roadmap](./docs/project-management/roadmap.md)：当前活动任务、候选切片、依赖和外部就绪门禁；
- [验收证据](./docs/project-management/evidence.md)：最终可复现结论、人工验收和剩余风险入口；
- [决策记录](./docs/decisions.md)：长期有效的架构与工程决策及其取舍。

## 产品边界

MVP 计划提供：

- 采集目的地、日期、总预算、兴趣偏好、交通和住宿要求；
- 获取天气、预警、地理编码、POI 和路线信息；
- 生成结构化的逐日旅行计划；
- 用代码校验日期、路线、时间、预算和规划冲突；
- 支持当天内部的局部重规划；影响住宿城市、跨城交通或相邻日期时先征求确认；
- 展示数据来源、更新时间、费用可信状态和不确定性；
- 在外部 API 失败、数据缺失或约束冲突时提供明确的降级结果。

预算覆盖住宿、城际交通、市内交通、门票和餐饮等全部费用。费用必须标记为 `verified`、`estimated`、`user_provided` 或 `unknown`，未知费用不得按 `0` 处理。

## 计划架构

```text
React Web UI
    ↓
FastAPI Application API
    ↓
单编排 Agent + 显式状态机
    ├─ 需求与计划领域服务
    ├─ 日期 / 路线 / 时间 / 预算确定性校验
    ├─ Repository → SQLite
    └─ 外部服务端口
       ├─ DeepSeek：需求理解、编排、规划与解释
       ├─ 高德：地理编码、POI、地图与路线
       └─ 和风天气：天气预报与预警
```

LLM 不作为预算、日期、时间或路线约束的最终裁决者。外部服务由适配器隔离；默认测试不访问真实 API。

## 工程基线

- Python：CPython `3.13.3`，由 uv 管理；后端健康服务使用 FastAPI。
- Node.js：`22.16.0`；包管理使用 Corepack 和项目固定的 pnpm `11.19.0`。
- 前端：TypeScript、React、Vite。
- 持久化：MVP 使用 SQLite，通过 Repository 隔离。
- 运行环境：Windows x64、PowerShell 5.1，本地回环地址优先。

根版本文件已固定 Python `3.13.3`、Node.js `22.16.0` 和 pnpm `11.19.0`。后端依赖由 `backend/pyproject.toml` 声明、由 `backend/uv.lock` 锁定；前端依赖由 `frontend/package.json` 声明、由根 `pnpm-lock.yaml` 锁定。本地与 CI 共用 `scripts/verify.ps1`，不维护第二套门禁命令。

## 后端健康服务

在项目根目录执行：

```powershell
uv sync --project backend --frozen
uv run --directory backend --frozen ita-api
```

服务默认只监听 `http://127.0.0.1:8000`。另开终端验证：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
```

后端的分项门禁是：

```powershell
uv run --directory backend --frozen ruff format --check src tests
uv run --directory backend --frozen ruff check src tests
uv run --directory backend --frozen mypy
uv run --directory backend --frozen pytest
```

健康接口只报告进程可用性，不初始化 DeepSeek、高德或和风天气，也不代表旅行规划能力或外部服务可用。

## 前端健康诊断页

先按上节启动后端，再在项目根目录执行：

```powershell
corepack pnpm install --frozen-lockfile
corepack pnpm --filter @intelligent-travel-assistant/frontend dev
```

前端只监听 `http://127.0.0.1:5173`，并将 `/api` 代理到本机后端。前端分项门禁是：

```powershell
corepack pnpm --filter @intelligent-travel-assistant/frontend format:check
corepack pnpm --filter @intelligent-travel-assistant/frontend lint
corepack pnpm --filter @intelligent-travel-assistant/frontend typecheck
corepack pnpm --filter @intelligent-travel-assistant/frontend test
corepack pnpm --filter @intelligent-travel-assistant/frontend build
```

诊断页覆盖加载、连接成功、连接失败和手动重试。Step 10 已在本地 Chromium 中验证 `200 → 后端停止/502 → 后端重启/200` 恢复序列、390px 窄屏无水平溢出和键盘按钮聚焦；Step 14 用户 UAT 再次确认成功、错误、重试恢复、文案和窄屏表现符合预期。它不包含旅行输入、地图、景点或假数据。

## 统一验证

在项目根目录通过一个入口复现运行时、锁文件、前后端 format/lint/typecheck/test/build 以及文档和安全契约检查：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify.ps1
```

脚本会使用 frozen lockfile 同步依赖，然后执行全部本地门禁；任一子门禁失败时整体返回非零。依赖缓存缺失时，uv 或 pnpm 可能访问其已配置的软件包仓库，但验证过程不配置或调用 DeepSeek、高德、和风天气等业务外部服务。文档检查也可单独运行：

```powershell
uv run --project backend --frozen python scripts/check_docs.py --root .
```

## CI 基线

[GitHub Actions workflow](./.github/workflows/ci.yml) 在 pull request、`main` 分支 push 和手动触发时使用 Windows runner 调用同一个 `scripts/verify.ps1`。workflow 使用根版本文件和 frozen lockfile，仓库权限仅为 `contents: read`，checkout 不保留 Git 凭证，所有第三方 Action 固定到完整提交 SHA。

默认 CI 将 DeepSeek、高德和和风天气凭证显式保持为空，不引用 GitHub Secrets，也不执行 live smoke。依赖缓存缺失时，运行时安装和依赖同步可能访问 GitHub Releases 或已配置的软件包仓库；这不等于访问业务 provider。Draft PR #1 已在 Windows runner 上成功执行统一门禁；最终 review 修复仍需新的远程 CI 复验。

## 本地配置边界

- 可提交模板是 [`.env.example`](./.env.example)，其中第三方 Key 均为空；
- 真实本地值应写入被 Git 忽略的 `.env.local`，不得提交、截图或复制到文档；
- 健康检查必须在没有 DeepSeek、高德和和风天气 Key 时工作；
- 后端默认地址固定为 `127.0.0.1:8000`，不默认监听局域网；
- Node workspace 使用 `corepack pnpm`，不要依赖 Codex 捆绑运行时提供的裸 `pnpm` 路径。

## 外部服务状态

高德开放平台和和风天气的账户、应用及 Key 尚未创建，项目也尚未接入 DeepSeek、高德或和风天气。创建账户、配置真实凭证和执行真实 API 验证不属于当前 Step，后续必须单独授权并遵守配额、脱敏和失败隔离规则。

## 明确非目标

- 自动预订、支付、登录和复杂用户系统；
- 酒店实时库存、酒店实时价格承诺、票务库存或交易；
- 多 Agent 架构；
- 公网部署、复杂地图交互、图片展示和 PDF 导出；
- 直接复制 Agent1 的脆弱 Agent Loop、环境文件或本地缓存。

## 开发约定

开始修改前请先阅读 [AGENTS.md](./AGENTS.md) 和 [项目文档地图](./docs/README.md)。项目按“任务卡 → 用户批准 → 单 Step 实施 → 验证 → 状态同步”的流程推进；未经批准不自动进入下一 Step，不调用真实外部 API，也不执行远程 Git 写入。
