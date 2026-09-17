# 项目文档地图

交付补充：[恢复来源、验证与边界](./delivery/parent-delivery.md)。原文所称Git未执行为历史端点状态；本次交付按对应PR的实际状态确认。

## 使用说明

本文件是 Intelligent Travel Assistant 的唯一文档地图，说明每份权威文档的职责、更新触发条件、历史规则和读取入口。同一事实只在一份当前权威文档中维护；本表中标为“计划”的文件尚未创建，不能作为已交付能力的证据。

## 当前工作入口

- 当前活动任务：[F-020 地图选点操作修复](./project-management/f-020-map-selection-interactions.md)，本地修复已验证，待用户复查。
- 最近完成：[F-019归档](./archive/task-cards/F-019-advisor-ui-design-system.md)，离线QA及最终确认完成，归档以对应PR合并生效。
- 当前状态：[current-task](./project-management/current-task.md)；[计划](./project-management/implementation-plan.md)；[进度](./project-management/progress.md)。
- 最终证据：[F-019交付报告](./delivery/f019-delivery.md)；[设计/运行图](./design/f019/README.md)。
- 前置交付：[F008](./delivery/f008-delivery.md)；[F009–F018联合父基线](./delivery/parent-delivery.md)。
- 产品、架构、API、测试、决策文档见下方权威映射；原始本机output不随仓库分发。

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
| API 契约 | 当前 | 旅行计划与局部重规划 HTTP 路由、公开 DTO、状态、幂等和稳定错误码 | 公开 API、DTO 或错误语义变化 | 不保留历史正文 | [api-contract.md](./api-contract.md) |
| 验收样例 | 当前 | F-001 固定 synthetic 请求、代表性终态和禁止行为 | 验收 case、固定输入或预期结果变化 | 不保留历史正文 | [acceptance-cases.md](./acceptance-cases.md) |
| 技术栈 | 当前 | 运行时、框架、关键依赖及版本策略 | 技术选型或版本基线变化 | 不保留历史正文 | [tech-stack.md](./tech-stack.md) |
| 设计规格 | 当前 | 当前已批准的轻量 Web UI 流程和状态契约 | 用户流程或设计基线变化 | 不保留历史正文 | [design-spec.md](./design-spec.md) |
| F-001 UI 参考稿 | 已冻结 | Step 22 已批准的桌面/窄屏实现参考，不是生产 React 实现 | 用户批准设计变更或实现发现契约冲突 | 冻结结论和允许偏差由设计规格维护 | [f-001-ui-reference.html](./design/f-001-ui-reference.html) |
| Agent 领域规格 | 当前 | 编排 Agent、状态机、领域工具、人机确认和 MCP 边界 | Agent 职责或工具边界变化 | 不保留历史正文 | [agent-domain-spec.md](./agent-domain-spec.md) |
| 测试策略 | 当前 | 测试分层、替身策略、真实 API 隔离和质量门禁 | 风险或测试策略变化 | 不保留历史正文 | [testing-strategy.md](./testing-strategy.md) |
| 项目路线 | 当前 | 候选任务、优先级、依赖和阶段目标 | 用户确认优先级或范围变化 | 只保留短摘要 | [roadmap.md](./project-management/roadmap.md) |
| 当前任务 | 当前 | 唯一活动任务、有效授权、验收标准和 Step 状态地图 | 当前任务、批准状态或 Step 变化 | 不保留逐轮历史，关闭任务的完整卡片另存 archive | [current-task.md](./project-management/current-task.md#当前执行状态) |
| 当前计划 | 当前 | 当前任务执行依赖、可验证目标和验证入口，状态/额度引用任务卡 | 当前任务计划变化 | 不追加逐轮日志 | [implementation-plan.md](./project-management/implementation-plan.md) |
| F-001-CR1 变更卡 | 已实现、已审查、已交付 | D-009 确定性排程迁移的职责、DTO、算法、失败策略、范围和实施证据 | 变更交付状态或任务关闭 | 作为 F-001 任务内变更控制记录并保留归档入口 | [f-001-cr1-deterministic-scheduling.md](./project-management/f-001-cr1-deterministic-scheduling.md) |
| 项目进度 | 当前 | 当前状态、最近完成、阻塞和下一批准动作 | Step 收口或阻塞变化 | 只保留最近摘要 | [progress.md](./project-management/progress.md) |
| 验收证据 | 当前 | 可复现的最终验证结论、环境和命令索引 | 产生可保留的验收证据 | 允许按任务保留 | [evidence.md](./project-management/evidence.md) |
| 决策记录 | 当前 | 长期有效的重要决策、理由、取舍和后果 | 产生或废止重要决策 | 追加决策记录 | [decisions.md](./decisions.md) |
| 历史归档 | 当前 | 已关闭任务卡和确需保留的阶段材料 | 任务或阶段关闭 | 只读归档 | [docs/archive/](./archive/) |

## 项目管理文档合同

本表约束 `docs/project-management/` 的内容归属。检查到篇幅或历史混入时先生成迁移清单，不因整理提醒暂停已经授权的业务开发；权威状态、授权或证据冲突仍属于阻断问题。

| 文档 | 必须记录 | 禁止记录 | 更新方式 | 历史去向 | 当前健康判断 |
| --- | --- | --- | --- | --- | --- |
| `roadmap.md` | 候选任务、总体状态、优先级、依赖、一行完成摘要 | 当前 Step 细节、逐轮失败、运行日志、执行授权全文 | 产品优先级变化时覆盖 | 已关闭任务细节进入 archive/evidence | 当前篇幅可用 |
| `current-task.md` | 前40行状态面板、唯一任务、当前Step、授权/额度、阻塞、唯一下一项、证据链接 | 已结束Step全文、历史测试矩阵、长期架构、详细Stack计划、旧Prompt和日志 | 状态变化时覆盖 | 完整历史进入archive；证据进入evidence或独立目录 | `WARNING`：783行/约96.8KB，历史参考约75% |
| `implementation-plan.md` | 当前任务的Step顺序、依赖、文件职责、验证和完成条件 | 逐轮执行结果、旧授权、历史门禁流水 | 计划变化时覆盖 | 关闭任务时随任务卡归档 | 当前含历史Stack/长期边界，后续归属审查 |
| `progress.md` | 当前Step、最近完成、阻塞、唯一下一批准动作 | 日期流水、完整证据、设计正文 | 每次收口压缩覆盖 | 重要结果由evidence/archive保留 | 当前简短可用 |
| `evidence.md` | 结论、适用环境、版本/命令、证据目录链接和未覆盖范围 | 完整控制台日志、重复任务正文、秘密、无限机器事件 | 追加索引；按任务/阶段拆分 | 原始产物留独立证据目录，关闭阶段进入archive | `WARNING`：3675行/约632KB，应拆分索引 |
| `f-001-cr1-deterministic-scheduling.md` | 该变更的稳定职责、契约、决策和最终结果 | F-008当前状态、无关执行流水 | 仅在该变更事实变化时更新 | 任务关闭后只读归档 | 应评估是否已具备归档条件 |

更新这些文件前先列：`变化事实 → 本表唯一目标文档 → 覆盖/压缩/追加索引 → 其他文件只链接或无需修改`。

## 当前事实与历史分离

- README、产品、架构、技术栈、设计、Agent 和测试文档只描述当前有效事实。
- `current-task.md` 保存唯一活动任务与执行合同；完整任务卡在关闭后另存 archive，当前无任务时明确空闲。
- `implementation-plan.md` 保存当前任务执行依赖和验证入口；Step 状态/额度引用任务卡，不追加终端流水或聊天摘要。
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

## 当前任务导航

当前无活动任务；F-019归档及交付状态见上述入口。后续真实UAT与新功能另起任务。

当前 Step 1：F-020 用户交互复查；实现与离线核验已完成。

Git同步授权（2026-09-17）：用户要求“帮我最新的同步到git上面”。允许在fix/f020-map-selection-interactions精确提交本轮五源文件与六份任务文档，并推送origin同名分支；保留main与原工作区历史dirty，不强推、不创建PR或合并、不自动宣告视觉验收。提交和推送结果以远端分支为准，本机记录为output/f020/20260917-222621-git-sync/result.json。
