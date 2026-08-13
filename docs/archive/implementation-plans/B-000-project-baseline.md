# 已归档计划：B-000 Project Baseline

## 关联文档

- 归档任务卡：[B-000 task card](../task-cards/B-000-project-baseline.md)
- 当前项目状态：[progress.md](../../project-management/progress.md)
- 长期决策：[decisions.md](../../decisions.md)
- 文档地图：[docs/README.md](../../README.md)

## 总体策略

按一个 Step 一个可验证结果推进。当前项目文件在 Step 3 创建任务分支前保持未提交，避免把
B-000 变更直接提交到 `main`。外部服务、业务功能、远程 Git 操作和系统级工具修改不属于本计划。

状态值：`DONE`、`IN_PROGRESS`、`TODO`、`BLOCKED`。

## Step 0：复核项目事实与本机工具链

- 目标：确定项目目录、Git 边界和可用运行时。
- 修改文件：无。
- 验证：检查目录、Git、Python、uv、Node、Corepack、pnpm、PowerShell。
- 结果：目标目录为空且非仓库；Python 3.13.3 可由 uv 使用；Node.js 22.16.0 可用。
- 证据：当前任务卡“当前事实和能力缺口”。
- 状态：DONE。

## Step 1：建立本地 Git bootstrap

- 目标：建立可供任务分支使用的空 `main` 基线。
- 修改：初始化 `.git/`，创建不含文件的根提交。
- 验证：`git status --short --branch`、`git ls-tree -r --name-only HEAD`。
- 结果：提交 `4dfe6b2 chore: initialize repository`；提交树为空；工作树干净。
- 状态：DONE。

## Step 2：固化任务卡与运行时决策

- 目标：把已批准任务和运行时基线写入项目权威文档。
- 文件：
  - `docs/project-management/current-task.md`
  - `docs/project-management/implementation-plan.md`
  - `docs/project-management/progress.md`
  - `docs/decisions.md`
- 验证：Markdown 可读、相对链接存在、Git diff 只包含上述文件、没有敏感信息。
- 预期结果：后续会话无需依赖聊天历史即可恢复 B-000 当前状态。
- 状态：DONE。

## Step 3：创建任务分支

- 目标：把当前未提交的 B-000 文档带入独立任务分支。
- 文件：不新增文件，只改变 Git 分支状态。
- 操作方向：从 `main` 创建并切换到 `chore/b-000-project-baseline`。
- 验证：
  - 当前分支正确；
  - bootstrap 提交仍是共同基线；
  - Step 2 文档仍保持未提交且内容不变；
  - 未配置或写入远程。
- 结果：已切换到 `chore/b-000-project-baseline`；HEAD 仍为 `4dfe6b2`；4 份文档未暂存、未提交；无远程。
- 停止条件：分支已存在且指向不明，或工作树出现未解释文件。
- 状态：DONE。

## Step 4：建立项目规则、README 和文档地图

- 目标：建立唯一项目入口和文档权威关系。
- 计划文件：`AGENTS.md`、`README.md`、`docs/README.md`。
- 验证：所有当前文档从 `docs/README.md` 可定位，职责无重复。
- 结果：已建立项目级执行规则、真实能力入口和唯一文档地图；当前文档可定位，计划文档已标明创建 Step。
- 状态：DONE。

## Step 5：固化产品和架构规格

- 目标：将已批准的产品、架构、技术栈和 Agent 边界写成当前规格。
- 计划文件：
  - `docs/product-brief.md`
  - `docs/architecture.md`
  - `docs/tech-stack.md`
  - `docs/design-spec.md`
  - `docs/agent-domain-spec.md`
  - `docs/decisions.md`
- 验证：与 current-task 的范围、非目标和外部服务边界一致。
- 结果：已建立产品、架构、技术栈、轻量 Web UI 和单编排 Agent 当前规格，并在 decisions 中记录架构、数据可信和重规划确认取舍。
- 状态：DONE。

## Step 6：建立测试策略和项目路线入口

- 目标：固定测试分层、候选 roadmap 和证据职责。
- 计划文件：
  - `docs/testing-strategy.md`
  - `docs/project-management/roadmap.md`
  - `docs/project-management/evidence.md`
- 验证：roadmap 只包含已确认候选任务，B-000 是唯一活动任务。
- 结果：已建立风险驱动的离线测试策略、项目候选 roadmap 和最终证据记录契约；B-000 是唯一 `ACTIVE` 任务，后续任务均为未批准的 `CANDIDATE`。
- 状态：DONE。

## Step 7：建立根配置和密钥边界

- 目标：固定运行时、依赖管理、忽略规则和本地配置契约。
- 计划文件：`.gitignore`、`.env.example`、`.python-version`、`.node-version`、
  `.editorconfig`、`.gitattributes`、根 Node workspace 配置。
- 验证：Python 3.13.3 和 Node 22.16.0 明确；`.env.local`、缓存和构建产物被忽略。
- 停止条件：需要安装系统级工具或写入真实凭证。
- 结果：已固定 Python 3.13.3、Node 22.16.0、pnpm 11.19.0，建立根 Node workspace、空锁文件、编辑器/换行规则、Git 忽略和空凭证配置契约；未安装应用依赖。锁文件命令只生成两个被忽略的 `node_modules` workspace 元数据文件。
- 注意：当前裸 `pnpm` 来自 Codex bundled fallback 并使用 Node 24.19.0；空锁文件已另用系统 Node 22.16.0 和 Corepack 缓存的 pnpm 11.19.0 离线验证，后续项目命令不得依赖 bundled 路径。
- 状态：DONE。

## Step 8：创建 FastAPI 健康服务

- 目标：交付不依赖业务 Key 的本地健康 API。
- 计划范围：`backend/` 下的依赖、应用入口、配置、健康路由和测试。
- 验证：pytest、Ruff、mypy 和本地健康请求通过。
- 禁止：业务 Schema、外部 API 客户端、假旅行数据。
- 结果：已建立 Python 3.13.3 后端包、uv 锁文件、Pydantic 本地配置、FastAPI 应用工厂、`GET /api/health` 和离线测试；健康服务不读取 provider Key，不含外部客户端或旅行业务。Ruff format/check、mypy、7 项 pytest 及 `127.0.0.1:8000` 本地请求均通过。受控地把健康状态改为未批准值时，契约测试按预期失败；恢复实现后全套测试重新通过。
- 兼容性说明：当前 Starlette TestClient 已弃用旧 `httpx` 兼容路径，开发测试依赖使用 httpx2；该选择不预先决定后续 provider 传输客户端。
- 状态：DONE。

## Step 9：创建 React 健康界面

- 目标：交付前端与本地后端的最小可观察闭环。
- 计划范围：`frontend/` 下的 React/Vite 工程、健康客户端、状态组件和测试。
- 验证：Vitest、ESLint、Prettier、typecheck 和 build 通过。
- 禁止：正式旅行页面、复杂地图和视觉扩展。
- 结果：已建立 React/Vite 本地诊断页、严格健康响应校验、loading/success/error/retry/disabled 状态、仅回环地址的 Vite 代理和离线组件测试。Prettier、ESLint、TypeScript、8 项 Vitest、peer 检查和生产构建通过；受控移除重试触发后恢复测试按预期失败，恢复实现后全套门禁重新通过。
- 设计边界：采用本地旅行控制台的纸张、墨色和信号色视觉方向，无外部字体或图片请求；没有旅行表单、地图、景点、假数据或复杂动画。
- 状态：DONE。

## Step 10：验证本地前后端闭环

- 目标：证明 loading、success、error 和 retry 都可复现。
- 验证：本地浏览器 UAT，记录端口、步骤、实际结果和未覆盖范围。
- 结果：使用本地 Chromium 验证 `127.0.0.1:5173` 前端经 Vite 代理访问 `127.0.0.1:8000`。初始请求返回 200 并显示 success；受控延迟时显示 loading 且按钮 disabled；停止后端后重试返回 502 并显示 error；重启后端再重试返回 200 并恢复 success。完整请求清单只包含 `127.0.0.1:5173`，没有第三方网络访问。
- 视觉与可访问性：桌面和 390×844 窄屏截图已人工检查；窄屏 `scrollWidth` 与 viewport 均为 390，无水平溢出；Tab 可聚焦“重新检查”按钮。首次检查发现缺失 favicon 导致 404，已补本地 SVG 并复验为 200、干净控制台。
- 未覆盖：本 Step 只验证 Chromium 开发服务器路径，不替代多浏览器兼容测试、Step 13 独立 QA 或 Step 14 最终用户 UAT。截图和 Playwright 会话材料保存在被 Git 忽略的本地验收目录，不作为需提交的产品资产。
- 状态：DONE。

## Step 11：建立统一验证与文档门禁

- 目标：提供 Windows PowerShell 单入口验证。
- 计划文件：`scripts/verify.ps1`、`scripts/check_docs.py` 及必要测试。
- 验证：任一子门禁失败时脚本返回非零；文档断链可被检测。
- 结果：已建立 Windows PowerShell 5.1 统一入口，依次验证 Python/Node/pnpm 版本、前后端锁文件与依赖、Ruff、mypy、pytest、Prettier、ESLint、TypeScript、Vitest、Vite build、文档检查器测试和当前项目文档/安全契约。完整绿色运行通过，后端 7 项、前端 8 项、文档检查器 6 项测试均纳入同一退出码。
- 文档门禁：检查 15 份必需文档、全部当前 Markdown 相对链接和基础格式、Step 状态一致性、空凭证模板、私钥/Token 特征和关键 Git ignore 规则；主动跳过真实本地配置、依赖、缓存、构建与 Playwright 目录。
- 红绿证明：临时向 README 加入断链后，文档检查报告精确目标且统一入口返回 1；恢复 README 后再次运行全部门禁通过。临时错误未保留。
- 状态：DONE。

## Step 12：建立 CI

- 目标：在 GitHub Actions 中复现本地离线门禁。
- 计划文件：`.github/workflows/ci.yml`。
- 验证：workflow 使用锁文件、无真实 Secret、命令与本地门禁一致。
- 说明：无远程时只能完成配置审查，不能宣称远程 CI 已通过。
- 结果：已建立 `pull_request`、`main` push 和手动触发的 Windows workflow。Python 3.13.3 与 Node 22.16.0 从根版本文件读取，uv 固定为 0.6.14；workflow 只调用 `scripts/verify.ps1`，不复制门禁逻辑。
- 安全边界：仓库权限仅为 `contents: read`，checkout 不保留 Git 凭证；四个第三方 Action 均固定到官方发布标签对应的完整提交 SHA；DeepSeek、高德和和风天气凭证显式为空且不引用 GitHub Secrets。
- 验证结果：本地 CI 契约检查、10 项检查器单元测试和完整统一门禁通过；临时把 checkout 改为浮动标签时精确触发 `ci-action-pin` 并返回 1，恢复 SHA 后重新通过。
- 未覆盖：仓库没有 GitHub 远程，未 push、未创建 PR、未触发远程 runner，因此不能宣称远程 CI 通过。
- 状态：DONE。

## Step 13：全量门禁与独立 QA

- 目标：根据任务卡执行测试、构建、文档、敏感信息和范围审查。
- 验证：统一脚本、`git diff --check`、目标目录外状态复核、独立负向测试。
- 自动门禁：`scripts/verify.ps1` 在 Windows PowerShell 5.1 下全绿；Python 3.13.3、Node 22.16.0、pnpm 11.19.0、锁文件、Ruff、mypy、7 项 pytest、Prettier、ESLint、TypeScript、8 项 Vitest、Vite build、10 项文档/仓库检查器测试和实际契约均通过。
- 独立负向测试：5 项后端凭证/schema/404/非法端口测试、8 项前端精确 schema 与失败恢复测试，以及断链、非空凭证、CI Secret 和浮动 Action 引用测试均通过。
- 浏览器 QA：本地 Chromium 复现 `200 → 后端停止/502 → 后端重启/200`；390px 视口无水平溢出，Tab 可聚焦重试按钮。全部 33 条请求仅指向 `127.0.0.1:5173`，控制台只出现故障注入预期的 502 资源错误。
- 范围与安全：50 个未跟踪文件均属于已批准工程基线，0 个暂存文件、0 个远程、0 个允许文件符号链接；provider 凭证仅为空模板，运行时无 provider 客户端、旅行规划逻辑或包生命周期脚本。Agent1 与 `E:\Vibe coding` 目录时间戳早于本任务，且本 Step 未对目标目录外执行写入。
- 关注项：实际文件数 50 高于任务卡最初 25–35 个估算和 40 个停止阈值；该事实已在 Step 12 明确报告，用户随后批准 Step 13，因此本 Step 只验收既有文件且没有新增 QA 报告文件。远程 CI 和最终用户 UAT 不在本 Step 结论内。
- 状态：DONE。

## Step 14：用户 UAT 与本地提交

- 目标：用户确认本地运行和错误恢复，按意图精确暂存并提交。
- 验证：staged diff、提交拆分、敏感信息和 UAT 证据。
- 禁止：未经确认 push。
- 用户 UAT：用户确认成功、错误、重试恢复、文案和窄屏表现均符合预期，并明确授权精确暂存及创建本地提交。
- 交付边界：本 Step 只提交已批准的 50 个 B-000 工程基线文件；不配置远程、不 push、不创建 PR，也不进入 F-001。
- 验证结果：提交前统一门禁、staged diff、文件清单、空凭证、ignore 和敏感信息边界审查均通过；B-000 工程基线形成单一、本地交付提交。
- 状态：DONE。

## Step 15：GitHub 交付

- 目标：经授权 push、创建 PR、运行 CI 和完成 review。
- PR：`chore: establish Intelligent Travel Assistant project baseline` → `main`。
- 停止条件：没有远程、未授权、CI 失败或 diff 存在越界内容。
- 远程事实：已创建私有仓库 `wcnm8888/intelligent-travel-assistant`，bootstrap 提交为远程 `main`，任务分支已推送，Draft PR #1 指向 `main`。
- CI 事实：前两次 Windows 运行因 uv 冷启动版本探测失败；提交 `ec04215` 和 `c229233` 修复后，第三次运行 `31699542476` 通过。
- review 结果：构建依赖约束、健康请求超时、CI 安全契约、冷启动回归覆盖、前端失败契约和状态文档六项 finding 均已关闭；提交 `b1d7ce0` 的本地统一门禁与远程运行 `31701500542` 通过，最终复审无新阻塞问题。
- 状态：DONE。

## Step 16：合并后收口

- 目标：经授权合并，归档 B-000，重置 current-task 并压缩 progress/evidence。
- 禁止：自动创建或执行 F-001。
- 结果：PR #1 以 squash 方式合并为 `f10b1736b4f00386d653f430b24109e91fc888ec`；PR #2 完成任务卡和计划归档并合并为 `a21300c8c70764eb4aafc798bc54878373b5e3a0`；该归档提交的 `main` CI 运行 `31703994453` 通过，当前权威文档恢复为空闲状态。
- 状态：DONE。

## 关闭状态

B-000 已完成。不得从本历史计划自动开始 F-001；下一任务必须由用户从 roadmap 选择并批准。

## 回滚和暂停规则

- 不使用 `git reset --hard`、`git clean`、批量删除或覆盖。
- 文件错误使用小范围补丁修正。
- 需要删除、系统修改、外部服务、真实凭证或远程写入时暂停并请求授权。
- 任务范围变化时先更新并重新批准 current-task，不直接扩展计划。
