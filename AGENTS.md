# Intelligent Travel Assistant 项目规则

本文件适用于本仓库全部目录。用户明确指令、`E:\Vibe coding\AGENTS.md` 和已批准任务卡优先于本文件；子目录如有更具体的 `AGENTS.md`，只在其目录范围内补充规则，不得放宽安全边界。

## 开始工作前

1. 先阅读 [docs/README.md](./docs/README.md) 确定权威文档入口。
2. 阅读 [current-task.md](./docs/project-management/current-task.md) 确认唯一活动任务、范围和非目标。
3. 只读取 [implementation-plan.md](./docs/project-management/implementation-plan.md) 中与当前 Step 直接相关的部分，并用 [progress.md](./docs/project-management/progress.md) 核对最近状态。
4. 每次只执行一个已经用户批准的 Step；不得从候选 roadmap 自动开始新任务。
5. 发现文档与代码、测试或 Git 事实冲突时，先核对事实并修正文档，不依赖聊天历史继续执行。

## 项目与架构边界

- 本项目是 L 级综合项目，第一版面向中国大陆境内自由行，仅本地运行。
- 后端基线是 Python、FastAPI 和 SQLite；前端基线是 TypeScript、React 和 Vite。
- Agent 采用“单编排 Agent + 多个简单领域工具 + 显式状态机”，不得擅自拆分为多 Agent。
- LLM 负责需求理解、工具编排、规划和解释；日期、时间、路线、预算、费用状态和约束校验必须由确定性代码负责。
- 高德、和风天气和 DeepSeek 必须位于独立适配器边界之后。未获当前任务授权时，不实现真实调用、不调用真实 API，也不假定服务可用。
- 外部服务返回值是不可信输入，必须经过 Schema 校验、单位与时区转换、来源和更新时间记录后才能进入领域层。
- MCP 只用于确有复用价值的受控工具入口；不得为了使用 MCP 而把所有内部函数或第三方 API 直接暴露给 LLM。

## 当前工程基线

- Python 固定为 CPython `3.13.3`，通过 uv 管理；不要依赖系统默认 `python` 或 Windows `py` 启动器。
- Node.js 固定为 `22.16.0`；包管理使用 Corepack 和项目固定版本的 pnpm。
- 根版本文件和 workspace 锁文件已经建立；前后端依赖均已锁定，后续脚本和 CI 必须与其保持一致。
- Node 命令使用系统 Node 22.16.0；pnpm 使用 `corepack pnpm`。不要把当前 Codex 环境中可能指向捆绑 Node 24 的裸 `pnpm` 路径写入项目脚本或文档契约。
- 当前已有可本地运行的 FastAPI + React 业务应用，支持单城市双日计划、SQLite 持久化和受确认约束的局部重规划。不得把 synthetic、离线 fallback 或候选任务表述为真实 Provider 或已交付能力。

## 修改与安全规则

- 修改范围限于 `E:\Agent\comprehensive-cases\13-intelligent-travel-assistant`。
- 不修改、迁移、覆盖或删除 `E:\Agent\开发实践\Agent1-旅行推荐`；不得读取或复制其 `.env`、`.venv`、缓存和本地凭证。
- 不恢复或重建 `E:\Agent\zonghe-anli`，除非用户另行明确授权。
- 不删除源码、配置、测试、文档或资产；不使用 `git reset --hard`、`git clean`、批量覆盖或其他破坏性操作。
- 不创建外部账户、应用、Key，不登录、付费、部署公网或修改系统级配置。
- 不把真实 Key、Token、Cookie、密码、连接串或个人数据写入代码、文档、日志、提交信息和测试夹具。
- 本地服务默认只绑定 `127.0.0.1`。扩大到局域网或公网前必须重新评估并获得批准。

## 配置和测试替身

- 可提交的环境变量文件只能是无秘密的 `.env.example`；真实本地值使用被 Git 忽略的本地配置文件。
- 日志和错误信息只能报告变量名、服务名和脱敏状态，不输出秘密值。
- 单元测试、集成测试和默认 CI 使用内存替身、fixture 或录制后脱敏的数据，不访问真实外部服务。
- 真实 API 验证必须是显式、可选、默认关闭的独立门禁，并要求专用测试凭证、配额保护和结果脱敏。
- 未知费用必须保持 `unknown`，不得转换为 `0`；费用来源状态只允许 `verified`、`estimated`、`user_provided`、`unknown`。

## Git 与交付

- 一个任务对应一张任务卡和一套明确交付拓扑；默认使用一个功能分支和一个 PR，只有任务卡明确批准时才使用 stacked PR。
- 分支名、目标分支和当前 Step 以任务卡为准；不得直接向 `main` 写入任务变更。
- 精确暂存任务文件。提交、push、创建 PR、合并和远程写入分别以当前 Step 授权为准。
- 不修改或丢弃无法解释的用户变更；遇到范围外改动时暂停并报告。

## 验证与文档

- 修改后运行与风险相称的 format、lint、typecheck、test、build 和文档检查；尚无门禁脚本时执行最小可复现检查并说明限制。
- 不能运行的门禁必须记录原因、已完成检查和剩余风险，不得宣称通过。
- 当前事实写入其唯一权威文档；`progress.md` 只保留当前状态和最近结果，`evidence.md` 只保留可复现验收结论，历史任务进入 archive。
- 变更产品范围、架构、技术栈、测试策略或长期决策时，按 [docs/README.md](./docs/README.md) 的更新触发条件同步对应文档。
- Step 完成后只更新当前任务、实施计划和进度状态，不自动进入下一 Step。

## 停止条件

出现以下任一情况时停止并请求用户确认：需要扩大任务范围、使用真实凭证或外部服务、进行远程写入、修改系统环境、删除或覆盖材料、触及目标项目外文件，或连续三次遇到相同失败。
