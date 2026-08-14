# Intelligent Travel Assistant

Intelligent Travel Assistant 是一个面向中国大陆境内自由行的本地旅行决策辅助工具。目标用户是个人和小型同行群体；系统将基于目的地、日期、预算、偏好、交通和住宿要求，组合真实外部数据，生成可校验、可局部重规划且能说明来源与不确定性的旅行计划。

## 当前状态

`B-000：项目与工程基线` 已由 [PR #1](https://github.com/wcnm8888/intelligent-travel-assistant/pull/1) 交付，并由 [PR #2](https://github.com/wcnm8888/intelligent-travel-assistant/pull/2) 完成任务归档和文档收口。项目已具备本地 Git 与文档基线、固定运行时和工作区配置、FastAPI 健康服务、统一本地门禁和 GitHub Actions CI。当前活动任务是 `F-001：单城市双日旅行计划垂直切片`；进程内任务 Repository、五种终态结果快照、POST/GET/retry、单编排 Agent、三家 provider adapter、按全量配置条件启用的真实规划执行器，以及 React 旅行需求和结果工作台均已实现。synthetic 五终态浏览器闭环和 Step 41 全量离线门禁已通过；Step 38 取得一次脱敏 live 契约证据，但 Step 39 尚未取得 ready/partial 真实计划 UAT。

- 运行边界：仅本地运行，后续允许经显式配置访问外部 API。
- 当前任务状态：[current-task.md](./docs/project-management/current-task.md)
- 当前实施计划：[implementation-plan.md](./docs/project-management/implementation-plan.md)
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

## 前端旅行需求工作台

在项目根目录执行：

```powershell
corepack pnpm install --frozen-lockfile
corepack pnpm --filter @intelligent-travel-assistant/frontend dev
```

前端只监听 `http://127.0.0.1:5173`，并将 `/api` 代理到本机后端。当前页面会把通过校验的单城市双日请求 POST 到同源 `/api/trip-plans`，随后按 `job_id` 有界轮询并显示服务端真实阶段；15 次自动刷新后暂停，用户可手动继续。三家 provider 配置齐备时，后端会在进程内执行真实规划并发布确定性终态；任一配置缺失时不会调用 provider，任务保持安全的本地状态。前端分项门禁是：

```powershell
corepack pnpm --filter @intelligent-travel-assistant/frontend format:check
corepack pnpm --filter @intelligent-travel-assistant/frontend lint
corepack pnpm --filter @intelligent-travel-assistant/frontend typecheck
corepack pnpm --filter @intelligent-travel-assistant/frontend test
corepack pnpm --filter @intelligent-travel-assistant/frontend build
```

旅行需求表单覆盖城市、开始日期、人数、总预算、兴趣、节奏、市内交通、住宿区域/POI、可选住宿费用、餐饮预算和补充要求；餐饮默认 `100 元/人/天` 且可修改，未知住宿与城际费用映射为 `null`，不会按 0 处理。Step 23–25 已验证输入、轮询、严格终态 DTO，以及 ready/partial 的双日活动、天气、路线和预算卡；Step 26 已展示来源/freshness、warnings、uncertainties、violations、conflict、needs_input 和 failed 安全状态；Step 27 已接通 partial/failed 受控 retry、三次上限、防重复请求和窄屏输入折叠；Step 28–31 已实现 DeepSeek、高德和和风 HTTP adapter，Step 32 已把它们纳入凭证安全的本地启动组合根。预算和路线裁决完全来自服务端快照，前端不重算；unknown 费用显示为“未知”且无金额。桌面与 390px 本地浏览器闭环只访问本机资源。B-000 健康客户端和测试仍保留，但健康诊断页已让位于产品工作台。

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

默认 CI 将 DeepSeek、高德和和风天气凭证显式保持为空，不引用 GitHub Secrets，也不执行 live smoke。依赖缓存缺失时，运行时安装和依赖同步可能访问 GitHub Releases 或已配置的软件包仓库；这不等于访问业务 provider。PR #1、收口 PR #2 及其归档提交 `a21300c` 均已在 Windows runner 上通过统一门禁。

## 本地配置边界

- 可提交模板是 [`.env.example`](./.env.example)，其中第三方凭证与私钥路径均为空；
- 真实本地值应写入被 Git 忽略的 `.env.local`，不得提交、截图或复制到文档；
- DeepSeek 和高德各使用一个后端 Key；和风只接受账户专属 Host、项目 ID、凭据 ID和绝对 Ed25519 私钥路径，不接受旧 `QWEATHER_API_KEY`；
- 三方配置全空时 provider 状态为 `disabled` 且健康接口可用；配置完整且本地校验通过时为 `ready`；部分配置或非法私钥以稳定错误码拒绝启动，不回显值或路径；
- 健康检查必须在没有 DeepSeek、高德和和风天气 Key 时工作；
- 后端默认地址固定为 `127.0.0.1:8000`，不默认监听局域网；
- Node workspace 使用 `corepack pnpm`，不要依赖 Codex 捆绑运行时提供的裸 `pnpm` 路径。

## 外部服务状态

用户已自行创建 DeepSeek、高德和和风天气账户及本项目专用凭证；真实凭证只存在于 Git 忽略的 `.env.local` 与仓库外私钥文件中。项目已把三家 adapter 按全量配置条件接入任务执行器，并在 Step 38 的一次性授权内完成脱敏 live 契约验证。Step 39 的唯一真实浏览器任务因 DeepSeek `provider_schema_invalid` 安全失败，失败态桌面/窄屏展示有效，但尚无通过式真实数据 UAT。任何后续真实调用仍须单独授权并遵守配额、attribution、脱敏、费用和失败隔离规则。

## 明确非目标

- 自动预订、支付、登录和复杂用户系统；
- 酒店实时库存、酒店实时价格承诺、票务库存或交易；
- 多 Agent 架构；
- 公网部署、复杂地图交互、图片展示和 PDF 导出；
- 直接复制 Agent1 的脆弱 Agent Loop、环境文件或本地缓存。

## 开发约定

开始修改前请先阅读 [AGENTS.md](./AGENTS.md) 和 [项目文档地图](./docs/README.md)。项目按“任务卡 → 用户批准 → 单 Step 实施 → 验证 → 状态同步”的流程推进；未经批准不自动进入下一 Step，不调用真实外部 API，也不执行远程 Git 写入。
