# 项目文档地图

## 使用说明

本文件是 Intelligent Travel Assistant 的唯一文档地图，说明每份权威文档的职责、更新触发条件、历史规则和读取入口。同一事实只在一份当前权威文档中维护；本表中标为“计划”的文件尚未创建，不能作为已交付能力的证据。

## 当前工作入口

- 项目规则：[AGENTS.md](../AGENTS.md)
- 项目总览：[README.md](../README.md)
- 当前任务：[current-task.md](./project-management/current-task.md)（F-002，PR #6 已创建且首轮 CI 通过，等待最终 head CI 与合并授权）
- 当前计划：[implementation-plan.md](./project-management/implementation-plan.md)
- 当前架构变更卡：[F-001-CR1](./project-management/f-001-cr1-deterministic-scheduling.md)
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
| 当前任务 | 当前 | 当前/最近任务卡、批准范围、验收标准和 Step 地图 | 当前任务、批准状态或 Step 变化 | 关闭任务的完整卡片另存 archive | [current-task.md](./project-management/current-task.md) |
| 当前计划 | 当前 | 当前/最近任务的可验证执行步骤、结果和停止条件 | 当前任务计划或 Step 结果变化 | 不追加逐轮日志 | [implementation-plan.md](./project-management/implementation-plan.md) |
| F-001-CR1 变更卡 | 已实现、已审查、已交付 | D-009 确定性排程迁移的职责、DTO、算法、失败策略、范围和实施证据 | 变更交付状态或任务关闭 | 作为 F-001 任务内变更控制记录并保留归档入口 | [f-001-cr1-deterministic-scheduling.md](./project-management/f-001-cr1-deterministic-scheduling.md) |
| 项目进度 | 当前 | 当前状态、最近完成、阻塞和下一批准动作 | Step 收口或阻塞变化 | 只保留最近摘要 | [progress.md](./project-management/progress.md) |
| 验收证据 | 当前 | 可复现的最终验证结论、环境和命令索引 | 产生可保留的验收证据 | 允许按任务保留 | [evidence.md](./project-management/evidence.md) |
| 决策记录 | 当前 | 长期有效的重要决策、理由、取舍和后果 | 产生或废止重要决策 | 追加决策记录 | [decisions.md](./decisions.md) |
| 历史归档 | 当前 | 已关闭任务卡和确需保留的阶段材料 | 任务或阶段关闭 | 只读归档 | [docs/archive/](./archive/) |

## 当前事实与历史分离

- README、产品、架构、技术栈、设计、Agent 和测试文档只描述当前有效事实。
- `current-task.md` 保存当前或最近关闭任务的状态指针；完整任务卡在关闭后另存 archive。
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

- 当前活动任务：F-002 计划持久化、来源与版本（PR #6 已创建且首轮 CI 通过，等待最终 head CI 与合并授权）
- F-002 任务卡已由用户批准；Step 0–5 已完成。现有 POST/GET/retry API 默认装配本地 SQLite Repository，并新增单计划 DELETE；启动时完成 migration 和一次有界 30 天清理，内部可写入 typed acceptance record；临时数据库已覆盖重启、幂等、并发、冲突、删除、保留期和隐私边界
- F-001 已交付并归档；产品状态为 `PARTIAL`，等待用户从 roadmap 选择下一任务
- 最近完成：B-000 由 PR #1 交付、由 PR #2 完成归档收口；归档提交和对应 Windows CI 已通过
- 当前已完成 Step：F-001 Step 0 至 Step 47，以及补充 Step 45A–45X；D-009 已由 stacked PR #5 合并并由 PR #4 合并到 `main`，Step 45T 是最新 live UAT 且结论为 `PASS`
- 当前归档结论：F-001 已交付，但产品验收状态保留为 `PARTIAL`；门票等非关键费用保持 `unknown`，不按 0 处理。Step 45M 历史 `FAIL` 保留，混合交通 fallback 仍只有离线证据
- 当前产品 UI 已通过专用 synthetic executor 经真实本机 POST/GET/retry 严格渲染五种结果；三家配置齐备时任务 API 使用真实 provider 执行器，默认无凭证时执行器保持禁用，不会调用 provider
- Step 38 已完成：一个杭州双日真实计划触达三家 provider 且 live 契约通过；计划经确定性校验进入 `conflict`，同一预算内的高德公交路线窄探针通过，全程无原始响应、持久缓存或真实高德截图
- Step 45A 已执行：唯一真实任务因 DeepSeek 本地候选校验以 `model_output_invalid` 安全失败，失败态桌面/窄屏展示通过，但真实数据 UAT 结论仍为 `FAIL`，没有重试或第二次提交
- Step 45B 已离线修复候选阶段/类别诊断与 generation/repair 规则一致性，并建立 adapter → resolver → executor → API 纵向回归；没有调用真实 provider，也没有产生新的 live 通过证据
- Step 45C 的唯一真实任务生成完整双日候选，但最终两天各出现一项路线冲突，真实 UAT 仍为 `FAIL`
- Step 45D 已离线修复候选未预检住宿往返和跨地点正数交通窗口的问题；没有调用真实 provider，也不产生新的 live 通过证据
- Step 45E 的最后一次受控 live 回归在 generation 和唯一一次 repair 后仍以时间候选无效失败；没有计划或路线补全
- Step 45F 已离线细分五类安全时间诊断并确认原有 Prompt、上下文和规则完整；用户随后批准 D-009，将精确时间骨架和排程迁移给确定性代码
- Step 45H 已按 F-001-CR1 把生产编排迁移到无最终时间 proposal + 实际路线 + 确定性 scheduler；公开 API、Repository 和 UI Schema 未变化
- Step 45K–45L 已完成 stacked PR #5 提交、推送、成功 CI 和独立远程 review；随后 PR #5 已合并至功能分支，PR #4 已复验并合并至 `main`
- Step 45M 的唯一真实任务取得 proposal、天气和部分路线事实，但必要高德路线数据缺失后以无计划 `failed` 收口；静态复核同时发现双交通方式没有 fallback、路线错误缺少安全 diagnostic、前端状态边遗漏
- Step 45N 已离线实现公交首选、失败路段步行降级、8 次硬预算、五类安全路线诊断和前端 `planning → needs_input` 对齐；没有新的 live 证据
- Step 45O 发现 provider-wide fallback、deadline、数值和来源投影阻塞；Step 45P 已纯离线修复。Step 45Q 又发现混合批次停止与异常 peer 清理两个 P1，Step 45R 已完成最小离线修复；
- Step 45S 未发现 P0/P1 并完成 live 准入；Step 45T 已取得完整双日 partial 的真实 UAT `PASS`，但没有自然触发步行 fallback
- Step 45U 已把 fallback 批次 terminal、外部取消 peer 清理和架构 Step 归属固化为提交前离线证据；没有再次 live
- 下一步：等待用户批准执行 F-002 Step 6（Step 6 与 Git/PR 授权均已取得；该固定措辞供状态检查器识别）；PR #6 已创建，实施提交 `729119b` 的 Windows offline verification run `31923661440` 已通过。当前只等待交付证据提交的最终 CI；不自动合并，F-001 的 `PARTIAL` 产品状态保持不变
