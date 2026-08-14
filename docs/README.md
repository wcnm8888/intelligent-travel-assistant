# 项目文档地图

## 使用说明

本文件是 Intelligent Travel Assistant 的唯一文档地图，说明每份权威文档的职责、更新触发条件、历史规则和读取入口。同一事实只在一份当前权威文档中维护；本表中标为“计划”的文件尚未创建，不能作为已交付能力的证据。

## 当前工作入口

- 项目规则：[AGENTS.md](../AGENTS.md)
- 项目总览：[README.md](../README.md)
- 当前任务：[current-task.md](./project-management/current-task.md)
- 当前计划：[implementation-plan.md](./project-management/implementation-plan.md)
- 最近进度：[progress.md](./project-management/progress.md)
- 长期决策：[decisions.md](./decisions.md)
- 产品说明：[product-brief.md](./product-brief.md)
- 系统架构：[architecture.md](./architecture.md)
- API 契约：[api-contract.md](./api-contract.md)
- 验收样例：[acceptance-cases.md](./acceptance-cases.md)
- 技术栈：[tech-stack.md](./tech-stack.md)
- 交互设计：[design-spec.md](./design-spec.md)
- Agent 领域规格：[agent-domain-spec.md](./agent-domain-spec.md)
- 项目路线：[roadmap.md](./project-management/roadmap.md)
- 验收证据：[evidence.md](./project-management/evidence.md)
- 历史归档：[docs/archive/](./archive/)

## 推荐读取路径

开始或接手当前工作：

```text
AGENTS.md
→ docs/README.md
→ current-task.md
→ implementation-plan.md 中的当前 Step
→ progress.md
→ 当前 Step 直接涉及的领域文档
```

查产品范围时读取 [product-brief.md](./product-brief.md)；查架构与边界时读取 [architecture.md](./architecture.md) 和 [agent-domain-spec.md](./agent-domain-spec.md)；查版本与依赖时读取 [tech-stack.md](./tech-stack.md)；查交互状态时读取 [design-spec.md](./design-spec.md)；查测试和门禁时读取 [testing-strategy.md](./testing-strategy.md)。

## 权威文档映射

| 文档 | 状态 | 唯一职责 | 更新触发条件 | 历史规则 | 路径 |
| --- | --- | --- | --- | --- | --- |
| 项目规则 | 当前 | 仓库范围内的执行、安全、架构和交付约束 | 项目级工作规则变化 | 不保留历史正文 | [AGENTS.md](../AGENTS.md) |
| 项目 README | 当前 | 项目入口、当前真实能力、运行边界和文档导航 | 运行方式或交付事实变化 | 不保留历史正文 | [README.md](../README.md) |
| 文档地图 | 当前 | 文档职责、权威关系、入口和状态 | 文档新增、归档、改名或职责变化 | 不保留历史正文 | 本文件 |
| 产品说明 | 当前 | 用户、场景、目标、范围、成功标准和非目标 | 产品方向或范围获批准变更 | 不保留历史正文 | [product-brief.md](./product-brief.md) |
| 架构 | 当前 | 当前模块、依赖方向、数据流、部署和外部边界 | 架构边界获批准变更 | 不保留历史正文 | [architecture.md](./architecture.md) |
| API 契约 | 当前 | F-001 HTTP 路由、公开 DTO、状态、幂等和稳定错误码 | 公开 API、DTO 或错误语义变化 | 不保留历史正文 | [api-contract.md](./api-contract.md) |
| 验收样例 | 当前 | F-001 固定 synthetic 请求、代表性终态和禁止行为 | 验收 case、固定输入或预期结果变化 | 不保留历史正文 | [acceptance-cases.md](./acceptance-cases.md) |
| 技术栈 | 当前 | 运行时、框架、关键依赖及版本策略 | 技术选型或版本基线变化 | 不保留历史正文 | [tech-stack.md](./tech-stack.md) |
| 设计规格 | 当前 | 当前已批准的轻量 Web UI 流程和状态契约 | 用户流程或设计基线变化 | 不保留历史正文 | [design-spec.md](./design-spec.md) |
| F-001 UI 参考稿 | 已冻结 | Step 22 已批准的桌面/窄屏实现参考，不是生产 React 实现 | 用户批准设计变更或实现发现契约冲突 | 冻结结论和允许偏差由设计规格维护 | [f-001-ui-reference.html](./design/f-001-ui-reference.html) |
| Agent 领域规格 | 当前 | 编排 Agent、状态机、领域工具、人机确认和 MCP 边界 | Agent 职责或工具边界变化 | 不保留历史正文 | [agent-domain-spec.md](./agent-domain-spec.md) |
| 测试策略 | 当前 | 测试分层、替身策略、真实 API 隔离和质量门禁 | 风险或测试策略变化 | 不保留历史正文 | [testing-strategy.md](./testing-strategy.md) |
| 项目路线 | 当前 | 候选任务、优先级、依赖和阶段目标 | 用户确认优先级或范围变化 | 只保留短摘要 | [roadmap.md](./project-management/roadmap.md) |
| 当前任务 | 当前 | 唯一活动任务卡、批准范围、验收标准和 Step 地图 | 当前任务、批准状态或 Step 变化 | 不混入已关闭任务历史 | [current-task.md](./project-management/current-task.md) |
| 当前计划 | 当前 | 当前任务的可验证执行步骤、结果和停止条件 | 当前任务计划或 Step 结果变化 | 不追加逐轮日志 | [implementation-plan.md](./project-management/implementation-plan.md) |
| 项目进度 | 当前 | 当前状态、最近完成、阻塞和下一批准动作 | Step 收口或阻塞变化 | 只保留最近摘要 | [progress.md](./project-management/progress.md) |
| 验收证据 | 当前 | 可复现的最终验证结论、环境和命令索引 | 产生可保留的验收证据 | 允许按任务保留 | [evidence.md](./project-management/evidence.md) |
| 决策记录 | 当前 | 长期有效的重要决策、理由、取舍和后果 | 产生或废止重要决策 | 追加决策记录 | [decisions.md](./decisions.md) |
| 历史归档 | 当前 | 已关闭任务卡和确需保留的阶段材料 | 任务或阶段关闭 | 只读归档 | [docs/archive/](./archive/) |

## 当前事实与历史分离

- README、产品、架构、技术栈、设计、Agent 和测试文档只描述当前有效事实。
- `current-task.md` 只保存唯一活动任务；任务关闭后按收口 Step 迁入 archive。
- `implementation-plan.md` 保存当前任务的 Step 状态，不追加终端流水或聊天摘要。
- `progress.md` 只保存最近结果、当前阻塞和下一批准动作。
- `evidence.md` 只保存可复现结论、环境和命令，不保存完整原始日志或秘密。
- `decisions.md` 可以追加长期决策，但被替代的决策必须明确标记状态和替代关系。
- 聊天记录、Prompt 历史和一次性调试输出不是项目事实来源。

## 冲突处理

发生冲突时按以下顺序核对并校正：

```text
当前代码、测试、Schema 和 Git 事实
→ 用户批准的范围、任务卡和设计稿
→ 当前产品、架构、设计、Agent 和测试文档
→ roadmap、progress 和 evidence
→ archive、聊天记录和 Prompt 历史
```

代码或 Git 事实不能自行扩大已批准产品范围。若事实与批准范围冲突，应暂停实现、报告偏差并由用户决定修正方向。

## 当前状态

- 当前活动任务：`F-001 单城市双日旅行计划垂直切片`
- 最近完成：B-000 由 PR #1 交付、由 PR #2 完成归档收口；归档提交和对应 Windows CI 已通过
- 当前已完成 Step：F-001 Step 0 至 Step 43；最近完成 Step 42 长期文档/证据同步与 Step 43 本地单提交交付
- 当前明确未完成：通过式真实数据 UAT、推送、PR 与远程交付门禁；120 文件范围停止阈值已由用户批准本次单 PR 例外
- 当前产品 UI 已通过专用 synthetic executor 经真实本机 POST/GET/retry 严格渲染五种结果；三家配置齐备时任务 API 使用真实 provider 执行器，默认无凭证时执行器保持禁用，不会调用 provider
- Step 38 已完成：一个杭州双日真实计划触达三家 provider 且 live 契约通过；计划经确定性校验进入 `conflict`，同一预算内的高德公交路线窄探针通过，全程无原始响应、持久缓存或真实高德截图
- Step 39 已执行：唯一真实浏览器任务因 DeepSeek `provider_schema_invalid` 安全失败，失败态桌面/窄屏展示通过，但真实数据 UAT 结论为 `FAIL`，没有重试或第二次提交
- 下一步：等待用户批准执行 F-001 Step 44 推送功能分支并创建 Draft PR；任何 live 回归或远程写入仍需对应授权
