# 技术栈与依赖基线

## 目的

本文件定义 Intelligent Travel Assistant 当前有效的运行时、框架、依赖管理和工程工具边界。根运行时与 pnpm 版本已在 B-000 Step 7 固化；后端健康服务依赖已在 Step 8 解析，前端依赖已在 Step 9 解析，并在 F-001 Step 23–26 不增加依赖地实现旅行需求表单、任务 API client、受控轮询和五种终态界面；现有依赖均已锁定并通过分项门禁。

## 运行时基线

| 范围 | 选择 | 管理方式 | 当前状态 |
| --- | --- | --- | --- |
| Python | CPython `3.13.3` | uv + `.python-version` | 本机与项目文件已验证 |
| Node.js | `22.16.0` | `.node-version` + `engines` | 本机与项目文件已验证 |
| Node 包管理 | pnpm `11.19.0` | Corepack + `packageManager` + lockfile | 前端依赖已锁定，peer 检查通过 |
| 操作系统 | Windows x64 | PowerShell 5.1 | 本地开发基线 |
| 服务监听 | `127.0.0.1:8000` | Pydantic Settings + Uvicorn | Step 8 已实现并完成本地请求验证 |

Python 命令统一通过 uv 执行，不依赖当前系统默认 `python` 指向的 CPython 3.11.0rc2，也不依赖失效的 Windows `py` 启动器。

Node workspace 命令统一使用 `corepack pnpm`。当前 Codex 环境中的裸 `pnpm` 来自 bundled fallback，并使用 Node 24.19.0；它不是项目运行时或未来脚本依赖。Step 7 已用系统 Node 22.16.0 和 Corepack 缓存的 pnpm 11.19.0 在禁网、禁脚本、frozen-lockfile 模式下验证空锁文件；本机缓存绝对路径不进入项目脚本或契约。

## 后端

| 类别 | 选择 | 职责 | B-000 边界 |
| --- | --- | --- | --- |
| Web 框架 | FastAPI | 本地 HTTP API、Schema 和依赖注入入口 | Step 8 只实现健康接口 |
| 数据建模 | Pydantic | API 与配置边界的类型和校验 | 不定义旅行业务 Schema |
| ASGI 服务 | Uvicorn | 本地开发服务 | 默认只监听回环地址 |
| HTTP 客户端与测试传输 | httpx2 | 三方 provider 异步传输、Starlette/FastAPI `TestClient` 和离线 mock transport | Step 28–31 固定 provider adapter 使用，领域与端口层不依赖 |
| Ed25519/JWT 签名 | cryptography | 解析和风 PKCS8 私钥并生成 Ed25519 签名 | Step 31 仅在和风 adapter 使用；不进入端口或领域层 |
| 单元测试 | pytest | 后端单元与离线集成测试 | Step 8 建立 |
| lint/format | Ruff | Python lint 与格式化 | Step 8/11 接入门禁 |
| 类型检查 | mypy | 后端静态类型检查 | Step 8/11 接入门禁 |

外部服务适配器优先使用稳定 HTTP 合约和项目自有端口模型。是否采用某个官方 SDK，必须在真实接入任务中根据维护状态、类型质量、错误暴露和替换成本决定；SDK 类型不得进入核心领域层。

当前直接后端依赖为 FastAPI `0.141.1`、Pydantic Settings `2.15.0`、Uvicorn `0.52.2`、httpx2 `2.10.0` 和 cryptography `46.0.7`；pytest `9.1.1`、Ruff `0.16.2`、mypy `2.3.0` 为开发依赖，完整传递版本以 `backend/uv.lock` 为准。Starlette TestClient 与三个 provider adapter 复用 httpx2；cryptography 只用于和风 Ed25519 JWT，生产传输和密码能力都不进入应用端口或领域层。

## 前端

| 类别 | 选择 | 职责 | B-000 边界 |
| --- | --- | --- | --- |
| 语言 | TypeScript | 前端类型边界 | 开启严格类型方向 |
| UI | React | 本地 Web UI | Step 27 已实现旅行需求表单、严格计划/retry client、受控轮询、五种终态、恢复动作和窄屏输入折叠 |
| 构建与开发 | Vite | 本地开发服务、构建和代理 | 后端代理仅用于本地开发 |
| 单元/组件测试 | Vitest | 组件与客户端逻辑测试 | Step 9 建立 |
| UI 测试 | React Testing Library | 从用户行为验证组件状态 | 不测试实现细节 |
| lint | ESLint | TypeScript/React 静态规则 | Step 9/11 接入门禁 |
| format | Prettier | 前端与通用文本格式化 | Step 9/11 接入门禁 |
| typecheck | TypeScript compiler | 严格类型检查 | Step 9/11 接入门禁 |

第一版不引入重量级前端状态库。组件局部状态用于瞬时交互；服务端计划和持久状态以 API 返回为事实来源。只有状态共享和更新复杂度实际出现时，才评估额外状态管理依赖。

Step 9 解析的核心直接前端依赖为 React `19.2.8`、Vite `8.2.1`、TypeScript `5.9.3`、Vitest `4.1.10`、ESLint `9.39.5` 和 Prettier `3.9.6`；完整开发依赖与传递版本以根 `pnpm-lock.yaml` 为准。Vite 8 要求 Node `22.12+`，当前固定的 Node `22.16.0` 位于支持范围内。初次解析得到的 TypeScript 7 不满足当前 `typescript-eslint` peer 范围，因此没有保留，改为经 peer 检查通过的 TypeScript 5.9.3。

## 数据与持久化

- MVP 数据库方向：SQLite。
- 访问边界：领域和应用层只依赖 Repository 端口，不直接依赖 SQLite 或 ORM 类型。
- 后续候选：SQLAlchemy 和 Alembic，但 B-000 不添加未使用依赖、业务 Schema、迁移或数据库文件。
- 金额使用十进制定点语义，不能使用二进制浮点作为最终预算计算依据。
- 时间数据保留当地日期、带时区时间或明确的时区上下文；不得用无时区字符串进行跨日判断。

数据库选型和第一个业务 Schema 必须在产生持久化用户价值的后续任务中再次验证。

## Agent 与模型

- 模型逻辑名称与 API model ID：`deepseek-v4-flash`。
- Base URL：`https://api.deepseek.com`。
- F-001 默认显式关闭 thinking；正式 Base URL 下使用 JSON Output/Tool Calls，并由本地严格 Schema 校验，不依赖需要 `/beta` 的服务端 strict 工具模式。
- 架构：单编排 Agent、多个简单领域工具、显式状态机。
- 第一版不选用多 Agent 框架，也不预先引入 LangChain、LangGraph 或 MCP SDK。
- 编排、状态转换、工具授权和结构化输出优先使用项目代码与显式 Schema 表达；只有成熟库能明显减少已出现的复杂度时才引入。

模型客户端隐藏在项目自有 `DeepSeekPort` 后。Step 28 选择 httpx2 直接实现 Chat Completions 合约，不引入 provider SDK；每个端口调用一次 HTTP 尝试，业务调用预算和最终重试策略仍由应用治理与 Step 33 失败矩阵约束。

## 外部服务

| 服务 | 职责 | 不负责 | 隔离方式 |
| --- | --- | --- | --- |
| DeepSeek | 需求理解、工具编排、计划提议、自然语言解释 | 真实天气、路线、价格事实和确定性校验 | `DeepSeekPort` + httpx2 adapter |
| 高德开放平台 | 地理编码、基础 POI、地点详情和路线 | 酒店实时价格/库存、天气、预算裁决 | `AmapPort` + httpx2 adapter |
| 和风天气 | 天气预报和预警 | POI、路线、价格和行程规划 | `QWeatherPort` + httpx2/cryptography adapter |

Step 37 初次审计时本地六项 provider 配置为空；用户随后自行创建三家账户与凭证，被 Git 忽略的本地配置经无网络检查确认三家 adapter 和真实执行器均可构造。2026-08-17 DeepSeek 峰谷价下，同一调用预算高峰保守上界约 9.274 元、空闲约 4.666 元；用户已批准把一次受控 smoke 总费用上限调整为 12 元。Step 38 已在该授权内完成一个杭州双日计划并触达三家 provider，另以 1 次高德公交路线窄探针补齐被候选冲突跳过的路线契约；live 契约通过，但计划终态为 `conflict`。后续 live 调用仍需重新批准和核价。

## 工程与质量工具

- Python 依赖：`backend/pyproject.toml` 声明运行与开发依赖，`backend/uv.lock` 固定完整解析；使用 `uv sync --project backend --frozen` 重建环境。
- Node workspace：根 `package.json`、`pnpm-workspace.yaml` + `pnpm-lock.yaml` 已建立；前端直接与传递依赖均由锁文件固定。
- Node 版本执行：`.npmrc` 开启严格 engine、精确保存和严格 peer dependency，包管理器通过 `packageManager` 固定。
- 编辑器基础：`.editorconfig`、`.gitattributes` 已建立。
- 本地统一入口：`scripts/verify.ps1` 固定检查运行时、锁文件、依赖同步、前后端门禁、构建和文档契约，并传播任一子门禁的非零退出码。
- Python 构建隔离：`backend/build-constraints.txt` 以精确版本和哈希约束 hatchling 及其构建传递依赖；统一验证通过 `UV_BUILD_CONSTRAINT` 应用该文件。
- 文档与仓库检查：`scripts/check_docs.py` 校验必需文档、Markdown 相对链接和基础格式、活动/空闲任务状态一致性、当前 provider 空凭证/JWT 路径模板、废弃和风 API Key、构建约束、敏感模式、Git 忽略规则及结构化 CI 契约；其 23 项单元测试位于 `scripts/tests/`。
- CI：`.github/workflows/ci.yml` 使用 `windows-latest` 复现本地统一门禁；Python 和 Node 分别读取根版本文件，uv 固定为 `0.6.14`，业务 provider 凭证保持为空。
- CI 供应链：`actions/checkout`、`actions/setup-python`、`actions/setup-node` 和 `astral-sh/setup-uv` 固定到完整提交 SHA 并保留版本注释；仓库权限仅为 `contents: read`，checkout 不保留 Git 凭证。

默认门禁不配置第三方 Secret，不访问 DeepSeek、高德或和风天气。依赖缓存缺失时可能访问软件包仓库或 GitHub Releases；live smoke 是后续独立、显式、默认关闭的验证类型。GitHub 私有远程 `origin` 已建立，B-000 的 PR、`main` Windows runner 和最新提交 `50980887dadc0500d98dcd29966a5da2da74b2e2` 均已有成功 CI 证据。

## 版本和升级规则

1. 运行时版本必须同时反映在版本文件、依赖元数据、锁文件、脚本和 CI；
2. 直接依赖由项目清单声明，完整传递依赖由锁文件固定；
3. 不在文档中预填未经解析的框架包版本；后端和前端 Step 分别解析、锁定并验证；
4. 升级前检查 Python 3.13.3、Node 22.16.0、Windows 和测试工具兼容性；
5. 运行时、框架或核心持久化方案变化需要更新本文件和 `decisions.md`；
6. 不依赖 Codex bundled runtime 的私有可执行路径作为项目契约。

## 当前不采用

- Docker 或容器编排：第一版只要求本地运行，当前没有部署价值；
- 云数据库和 Redis：MVP 使用 SQLite，尚无并发或分布式状态需求；
- 多 Agent 框架：已批准采用单编排 Agent；
- MCP 作为内部总线：MVP 没有跨进程、跨产品复用需求；
- 实时酒店、票务和支付 SDK：不在产品范围；
- 公网监控和生产 APM：不在本地运行边界。

以上不是永久禁用。只有真实需求出现、边界获批准并有相应测试与回滚方案时才重新评估。
