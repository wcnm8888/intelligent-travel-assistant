# 当前任务：B-000 项目与工程基线

## 任务元数据

- 任务编号：`B-000`
- 任务等级：L
- 状态：`ACTIVE`
- 当前 Step：`Step 16 - 合并后收口（待批准）`
- 当前分支：`chore/b-000-project-baseline`
- 目标分支：`chore/b-000-project-baseline`
- 目标 PR：`chore: establish Intelligent Travel Assistant project baseline`
- 环境边界：`local`
- 批准状态：用户已批准目标、范围、非目标、验收标准、风险边界和工程决策
- 批准日期：2026-08-13

本文件是项目唯一活动任务卡。Step 的详细状态和验证要求以
[implementation-plan.md](./implementation-plan.md) 为执行入口。

## 用户目标

项目开发者需要一个结构清晰、可在本地运行、能自动验证、能安全接入后续外部服务的
Intelligent Travel Assistant 工程底座。

## 工程价值

完成 B-000 后，开发者应能完成以下闭环：

```text
安装依赖
→ 启动 FastAPI
→ 启动 React
→ 在浏览器查看前后端健康状态
→ 运行 lint / format / typecheck / test / build
→ 在 CI 中重复执行同一组门禁
→ 从 docs/ 恢复项目目标、架构、任务和证据
```

本任务交付“可开发、可运行、可验证、可交接”的工程能力，不交付旅行规划业务功能。

## 当前事实和能力缺口

### 已有事实

- 项目路径：`E:\Agent\comprehensive-cases\13-intelligent-travel-assistant`。
- 本地 Git 仓库已初始化，默认分支为 `main`。
- bootstrap 根提交为 `4dfe6b2 chore: initialize repository`，提交树为空。
- 私有远程仓库：`wcnm8888/intelligent-travel-assistant`；`origin` 已配置。
- Agent1 保留在 `E:\Agent\开发实践\Agent1-旅行推荐`，只作学习基线。
- `E:\Agent\zonghe-anli` 当前不存在；本任务不恢复、不重建、不追查无关文件。
- 高德和和风天气账户、应用和 Key 尚未创建。

### 工具链事实

- Python 基线：CPython `3.13.3`，由 `uv` 显式管理。
- 不使用默认 `python` 指向的 CPython `3.11.0rc2`。
- 不依赖当前失效的 Windows `py` 启动器。
- Node.js 基线：`22.16.0`。
- Node 包管理：Corepack + 项目固定版本的 pnpm。
- 当前可用工具：uv `0.6.14`、Corepack `0.32.0`、pnpm `11.19.0`、Git `2.49.0`。
- 运行系统：Windows x64、PowerShell 5.1。

### 当前缺口

- 任务分支已经创建，B-000 本地工程基线已形成单一交付提交。
- 项目规则、根 README 和唯一文档地图已经建立。
- 产品、架构、技术栈、交互和 Agent 领域规格已经固化。
- 测试策略、项目 roadmap 和验收证据入口已经建立。
- 根运行时版本、Node workspace、空锁文件、忽略规则和本地密钥契约已经建立。
- 前后端依赖声明和锁文件、健康骨架、测试、统一门禁及本地可审查的 CI 配置已经建立。
- Step 13 独立 QA和 Step 14 最终用户 UAT、本地提交已通过。
- Step 15 已创建 Draft PR #1；前两次 CI 暴露 Windows 冷启动版本探测问题，提交 `c229233` 后第三次 CI 通过；提交 `b1d7ce0` 关闭六项 review finding 后第四次 CI 通过，最终复审无新阻塞问题。
- 尚未创建或验证真实外部服务配置。

## 已批准项目决策

- 项目是 L 级综合项目，执行 SDD、质量门禁、独立 QA 和验收证据流程。
- 产品范围是中国大陆境内自由行，面向个人和小型同行群体。
- 第一版仅本地运行，但允许经明确配置访问外部 API。
- 后端采用 Python + FastAPI，前端采用 TypeScript + React。
- MVP 使用 SQLite，并通过 Repository 隔离数据访问。
- Agent 架构采用单编排 Agent、多简单领域工具和显式状态机，不采用多 Agent。
- LLM 使用 `deepseek-v4-flash`，Base URL 为 `https://api.deepseek.com`。
- 地图、POI、地理编码和路线使用高德开放平台。
- 天气预报和预警使用和风天气。
- MVP 包含轻量 Web UI。
- 费用覆盖住宿、城际交通、市内交通、门票和餐饮等全部类别。
- 费用状态区分 `verified`、`estimated`、`user_provided` 和 `unknown`；未知费用不得按 0 处理。
- 酒店第一版只使用高德基础 POI、用户输入价格或明确标注的估算，不接实时库存和预订。
- 局部重规划只影响当天内部时可以自动执行；影响住宿城市、跨城交通或相邻日期时必须先确认。
- 不做自动预订、支付、登录、酒店库存、复杂地图、图片或 PDF。
- 保留 Agent1，不复制其 `.env`、`.venv`、缓存或脆弱 Agent Loop。
- 运行时基线调整为 Python `3.13.3` + Node.js `22.16.0`，避免修改现有系统工具链。

运行时决策理由和后果见 [../decisions.md](../decisions.md)。

## 范围

B-000 允许建立：

- 根目录项目规则和基础配置；
- 唯一 `docs/` 文档体系；
- 产品、架构、技术栈、测试和 Agent 边界文档；
- roadmap、current-task、implementation-plan、progress 和 evidence；
- Python/FastAPI 工程骨架；
- React/TypeScript/Vite 工程骨架；
- 后端健康 API 和前端健康诊断页面；
- 单元测试、组件测试和离线集成验证；
- lint、format、typecheck、test、build 和文档检查；
- Windows 本地统一验证入口；
- GitHub Actions CI 配置；
- `.env.example` 和密钥保护规则；
- Git 初始化、任务分支、本地提交和一个 PR 的交付目标；
- 外部服务端口的文档契约，不包含真实实现。

## 非目标

B-000 明确不做：

- 旅行需求理解和行程规划；
- Agent 编排运行时代码；
- 预算、日期、路线和冲突校验；
- SQLite 业务 Schema、迁移或业务数据；
- DeepSeek、高德或和风天气真实适配器；
- 任何真实外部 API 调用；
- 外部服务账号、应用或 Key 创建；
- 酒店、机票和火车票实时库存或价格；
- 登录、预订、支付；
- 多 Agent；
- 复杂产品 UI、地图、图片和 PDF；
- 公网部署；
- 旧目录迁移或重建；
- Agent1 代码或凭证复制；
- 未经授权的远程仓库创建、push、PR、merge 或发布。

## 输入与输出

### 输入

- 用户已批准的产品和技术决策；
- `E:\Vibe coding` 方法论；
- 当前本地 Git 仓库；
- Step 0 获取的本机工具链事实。

### 输出

- 一条 B-000 任务分支；
- 唯一项目文档体系；
- 前后端工程骨架；
- 锁定的依赖；
- 本地健康检查闭环；
- 测试、质量门禁和 CI 配置；
- 最终验证证据；
- 一个 PR 交付目标。

### 状态变化

```text
空 Git 仓库
→ 已固化任务卡
→ 任务分支
→ 可运行工程
→ 本地门禁通过
→ 独立 QA 与 UAT 通过
→ 等待或完成 GitHub 交付
```

## 数据影响

- 本任务只新增项目源码、配置、文档、锁文件、测试和 Git 元数据。
- 不新增真实旅行数据、用户数据、API 响应或生产数据。
- 不创建 SQLite 业务数据库、业务表或占位迁移。
- SQLAlchemy、Alembic 和第一个真实 Schema 延后到产生持久化用户价值的任务。
- 本任务不涉及事务、并发、幂等和数据迁移。

## 权限与安全边界

- 第一版只有本机用户，无登录、角色和部门权限。
- 后端默认绑定 `127.0.0.1`，不得默认绑定 `0.0.0.0`。
- `.env`、`.env.local`、数据库文件、日志、缓存和构建产物必须被 Git 忽略。
- `.env.example` 只能包含变量名、非敏感默认值和空占位。
- 不读取、复制或引用 Agent1 的 `.env`。
- API Key 不得出现在 UI、日志、异常、截图、fixture、证据或 Git diff。
- CI 不配置真实第三方 Secret。
- 默认测试和 CI 必须离线，不得访问 DeepSeek、高德或和风天气。
- push、PR、merge 和远程仓库创建均需对应步骤的明确授权。

## UI 与交互状态

B-000 只建立工程诊断页，不建立正式旅行产品 UI。

- `loading`：正在检查后端状态；
- `success`：前端可用且后端已连接；
- `error`：后端不可用，显示可理解错误；
- `retry`：允许用户重新检查；
- `disabled`：检查进行中禁用重复重试；
- `empty`、`permission denied`、`submitting`：不适用；
- 状态文案不能只依赖颜色；
- 常见桌面和窄屏下不得发生内容溢出。

该诊断页不触发 Figma 门禁；正式旅行 UI 在后续用户价值任务中执行设计与视觉验收。

## 推荐工程结构

```text
AGENTS.md
README.md
.editorconfig
.gitattributes
.gitignore
.env.example
.python-version
.node-version
package.json
pnpm-workspace.yaml
pnpm-lock.yaml
scripts/
backend/
frontend/
docs/
  README.md
  product-brief.md
  architecture.md
  tech-stack.md
  design-spec.md
  agent-domain-spec.md
  testing-strategy.md
  decisions.md
  project-management/
    roadmap.md
    current-task.md
    implementation-plan.md
    progress.md
    evidence.md
  archive/task-cards/
.github/workflows/ci.yml
```

只在存在实际内容时创建目录，不为空目录占位。

## 技术栈与依赖边界

- Python `3.13.3`，由 uv 解析和执行；使用 `pyproject.toml` 与 `uv.lock`。
- 后端：FastAPI、Pydantic、Uvicorn；测试使用 pytest 和 FastAPI TestClient（当前 httpx2 后端）；门禁使用 Ruff 和 mypy。
- Node.js `22.16.0`；通过 Corepack 固定 pnpm；使用 `package.json` 与 `pnpm-lock.yaml`。
- 前端：React、TypeScript、Vite；测试使用 Vitest 和 React Testing Library；门禁使用 ESLint、Prettier 和 TypeScript。
- CI 使用 GitHub Actions，默认测试不配置外部服务凭证。
- SQLite、SQLAlchemy Repository 和 Alembic 是后续持久化方向，B-000 不添加未使用依赖。

## 本地配置和密钥隔离

`.env.example` 规划变量：

```text
APP_ENV=local
API_HOST=127.0.0.1
API_PORT=8000
DATABASE_URL=
DEEPSEEK_API_KEY=
DEEPSEEK_MODEL=deepseek-v4-flash
DEEPSEEK_BASE_URL=https://api.deepseek.com
AMAP_API_KEY=
QWEATHER_API_KEY=
QWEATHER_API_HOST=
```

- 缺少业务 API Key 不得阻止健康检查。
- `DATABASE_URL` 在业务持久化任务中再赋正式本地默认值。
- 和风天气 API Host 在创建账户后按控制台事实确认。
- 配置对象不得在日志中直接序列化。

## 前后端最小骨架边界

后端只实现应用创建、配置加载、`GET /api/health`、明确响应 schema、基础错误边界及测试。

建议健康响应：

```json
{
  "status": "ok",
  "service": "intelligent-travel-assistant-api"
}
```

前端只实现 React 启动、本地 `/api/health` 调用、loading/success/error/retry、Vite 本地代理和组件测试。
不得创建假旅行数据、景点卡片或行程页面。

## 外部服务适配器边界

B-000 只在架构文档中定义端口，不创建返回假成功的运行时占位实现：

- `LLMPort`：结构化响应和工具调用；
- `MapPort`：地理编码、POI 搜索、POI 详情和路线；
- `WeatherPort`：预报和预警；
- `PlanRepository`：计划版本持久化；
- `TraceRepository`：trace、工具调用和来源记录。

统一结果方向：

```text
status: ok | partial | unavailable
data
provider
fetched_at
valid_until
warnings
error_code
retryable
source_records
```

禁止工具隐藏决策、吞掉错误、返回假成功或让第三方 SDK 类型污染核心领域模型。

## 测试替身与真实 API 隔离

- 默认测试和 CI 完全离线。
- 外部服务通过端口和依赖注入隔离。
- fixture 必须脱敏、最小化并注明 schema 版本。
- 测试替身只能验证失败路径和编排，不能证明真实 API 可用。
- live smoke 必须使用独立标记和显式命令。
- B-000 不创建外部服务 fixture，因为尚未取得真实合约响应。

## 验收标准

1. Given 空项目，when 按 README 安装依赖并启动服务，then 前后端均可在本地运行。
2. Given 后端运行，when 请求 `GET /api/health`，then 返回 HTTP 200 和固定 schema。
3. Given 后端可用，when 打开前端，then 显示连接成功。
4. Given 后端不可用，when 打开前端，then 显示错误并允许重试。
5. Given 未配置第三方 Key，when 启动健康检查，then 不调用外部 API 且健康检查仍可运行。
6. Given 创建 `.env.local`，when 检查 Git 忽略规则，then 文件不会进入暂存范围。
7. Given 健康契约被破坏，when 运行测试，then 对应测试失败。
8. Given 新开发者只读取 `docs/README.md`，when 查找目标、架构、roadmap 和当前任务，then 能定位唯一权威来源。
9. Given 执行统一验证，when 所有门禁正常，then lint、format、typecheck、test、build 和文档检查全部通过。
10. Given 审查 diff，then 不存在真实凭证、外部调用、旅行业务逻辑或 Agent1 修改。

## 测试与门禁矩阵

| 风险或行为 | 测试或门禁 | 失败证明 | 验收角色 |
| --- | --- | --- | --- |
| 后端健康接口不可用 | FastAPI API 测试 | 删除或改变路由后测试失败 | 实现者 + 独立 QA |
| 响应 schema 漂移 | schema 断言 | 修改字段或状态值后失败 | 独立 QA |
| 前端状态缺失 | Vitest + Testing Library | 移除 loading/error/retry 后失败 | 实现者 + 独立 QA |
| Python 类型或规范错误 | mypy、Ruff | 引入错误类型或格式后失败 | CI |
| TypeScript 类型或规范错误 | TypeScript、ESLint、Prettier | 引入类型或格式错误后失败 | CI |
| 前端无法构建 | Vite build | 无效导入或配置导致失败 | CI |
| 文档漂移 | Markdown lint、相对链接和必需文档检查 | 缺文件或断链时失败 | 独立 QA |
| 凭证泄漏 | ignore、diff 和敏感模式检查 | `.env.local` 未忽略时失败 | 实现者 + 独立 QA |
| 外部服务被误调用 | 离线测试和代码审查 | 出现未批准外部客户端调用时阻塞 | 架构审查 |
| 修改目标目录外文件 | Git diff 与路径复核 | 越界修改时阻塞 | 独立 QA |
| 浏览器流程不可用 | 本地 UAT | success/error/retry 无法操作时阻塞 | 用户 |

## 文件影响范围

允许修改：

- 目标项目根目录工程文件；
- `.git/`；
- `docs/`；
- `backend/`；
- `frontend/`；
- `scripts/`；
- `.github/workflows/ci.yml`。

明确禁止修改：

- `E:\Agent\开发实践\Agent1-旅行推荐\**`；
- `E:\Agent\zonghe-anli`，当前不存在也不重建；
- `E:\Vibe coding\**`；
- 项目目录之外的用户文件；
- 系统级 Python、Node、Git 和安全配置；
- 生产或第三方服务配置。

## 文档更新契约

- 当前任务入口：本文件。
- 当前执行计划：[implementation-plan.md](./implementation-plan.md)。
- 最近状态：[progress.md](./progress.md)。
- 长期决策：[../decisions.md](../decisions.md)。
- Step 4 建立 `docs/README.md` 后，由它承担唯一文档地图职责。
- 验收时更新 `evidence.md`，只记录可复现结论和证据位置。
- 任务关闭后归档到 `docs/archive/task-cards/B-000-project-baseline.md`。
- 关闭后把本文件重置为“当前无活动任务，等待用户从 roadmap 选择”。
- 不把聊天记录、完整终端日志或旧 Step 过程追加到权威文档。

## 风险与回滚

主要风险：

- GitHub 远程、push、Draft PR 和一次成功远程 CI 已完成；review 修复复验和 merge 尚未完成。
- `zonghe-anli` 的消失属于外部状态变化，原因未知。
- 默认 `python` 和 `py` 启动器不符合基线，必须统一使用 uv。
- 当前 pnpm 来自 Codex bundled runtime，项目必须通过 Corepack 固定版本，不能依赖该路径。
- B-000 不能证明 SQLite、真实 Agent 或第三方 API 可用。
- 工程诊断页不能作为产品视觉基线。

回滚规则：

- 优先使用可审查的反向提交或 `git revert`。
- 不使用 `git reset --hard`、`git clean` 或批量删除。
- 如需放弃分支或删除文件，必须先说明影响并获得确认。
- Agent1 和目标目录外文件不属于回滚范围。

停止条件：

- 发现目标目录出现无法解释的用户文件或修改；
- 需要安装或修改系统级工具；
- 需要真实外部服务或凭证；
- 需要扩大到旅行规划业务或正式产品 UI；
- 新增文件超过 40 个；
- 连续三次遇到相同失败；
- 需要未经授权的远程写入或删除操作。

## Step 地图

| Step | 目标 | 当前状态 |
| --- | --- | --- |
| Step 0 | 复核项目事实和本机工具链 | DONE |
| Step 1 | 建立本地 Git bootstrap | DONE |
| Step 2 | 固化已批准任务卡和运行时决策 | DONE |
| Step 3 | 创建 `chore/b-000-project-baseline` 任务分支 | DONE |
| Step 4 | 建立项目规则、README 和文档地图 | DONE |
| Step 5 | 固化产品、架构、技术栈、Agent 与设计规格 | DONE |
| Step 6 | 建立测试策略、roadmap 和证据入口 | DONE |
| Step 7 | 建立根配置、依赖版本和密钥边界 | DONE |
| Step 8 | 创建 FastAPI 健康服务和测试 | DONE |
| Step 9 | 创建 React 健康界面和测试 | DONE |
| Step 10 | 验证本地前后端闭环 | DONE |
| Step 11 | 建立统一验证和文档门禁 | DONE |
| Step 12 | 建立 CI 配置 | DONE |
| Step 13 | 执行全量门禁和独立 QA | DONE |
| Step 14 | 用户 UAT 和本地提交 | DONE |
| Step 15 | 经授权完成 push、PR、CI 和 review | DONE |
| Step 16 | 经授权合并并完成文档收口 | TODO |

## Git 与 PR 目标

- 当前分支：`chore/b-000-project-baseline`。
- 任务分支已经基于 bootstrap 提交 `4dfe6b2` 创建。
- 默认不直接向 `main` 提交 B-000 项目文件。
- B-000 工程基线文件已在 Step 14 精确暂存并形成单一、本地、可审查的交付提交。
- PR 标题：`chore: establish Intelligent Travel Assistant project baseline`。
- PR 目标分支：`main`。
- push、PR 和 merge 分别需要明确授权。

## 上下文与预算

- 预计新增文件：25–35 个。
- 每次只执行一个已批准 Step。
- 当前事实写入权威文件，不依赖聊天历史。
- `progress.md` 只保留当前状态，不记录逐轮日志。
- `evidence.md` 只保存结论、环境和复现命令。
- 超过停止条件时暂停并重新切片。

## 完成定义

- [x] B-000 任务卡已经用户批准。
- [x] Step 0 工具链事实已核对。
- [x] Step 1 Git bootstrap 已完成。
- [x] 任务卡和 Python 3.13.3 / Node.js 22.16.0 决策已固化。
- [x] 任务分支已建立。
- [x] `docs/README.md` 能定位全部当前权威文档，并标明计划文档的创建 Step。
- [x] 产品、架构、技术栈、交互和 Agent 领域规格与已批准边界一致。
- [x] README、roadmap、current-task、progress 与当前 Git 事实一致。
- [x] FastAPI 健康接口可运行并通过测试。
- [x] React 健康页面覆盖 loading、success、error 和 retry。
- [x] 前后端 lint、format、typecheck、test 和 build 通过。
- [x] 文档 lint 和链接检查通过。
- [x] `.env*`、数据库、缓存和构建产物正确忽略，`.env.example` 明确保留。
- [x] 当前文件没有真实 Key、Token、Cookie 或连接串。
- [x] 没有调用真实外部 API。
- [x] 没有旅行规划业务实现。
- [x] Agent1 和目标目录外没有变化。
- [x] 独立 QA 完成。
- [x] 用户 UAT 完成。
- [x] diff、提交和证据可审查。
- [ ] 经授权完成 push、PR、CI、review 和 merge。
- [ ] 合并后文档已收口，B-000 已归档。
- [ ] 未自动开始 F-001。
