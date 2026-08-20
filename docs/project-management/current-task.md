# 当前任务

当前无活动任务。

## 最近完成

- `F-004A 单城市 2–7 日计划扩展` 已完成 `Step 0–7`，通过本地全量门禁、loopback synthetic UAT、三层 stacked PR CI、clean restack、依序合并和完整功能 main CI；
- 交付 PR：#13、#16、#17；PR #14/#15 分别因层间测试依赖和 squash ancestry 由等价干净 PR 替代并关闭；
- 主线功能提交：`583e9da34b0d45e84a65da620cbb5d5fa8330a3c`；完整功能 main CI run `32359762190` 为 `PASS`；
- 完整任务卡：[F-004A 单城市 2–7 日计划扩展](../archive/task-cards/F-004A-single-city-multiday-plan.md)。

## 历史边界

- F-001 产品验收状态保持 `PARTIAL`；
- Step 45M 历史真实 UAT `FAIL` 和 Step 45T 真实 UAT `PASS` 均保留；
- 门票等非关键费用继续为 `unknown`，不按 0 处理；
- 混合交通 fallback 仍只有离线证据；
- F-002/F-003/F-004A 已归档；SQLite schema version 保持 2，无 migration v3；
- F-004A 未调用真实 Provider；多日预算、天气和路线质量只具备离线/synthetic 证据。

## 下一入口

下一任务尚未批准。候选任务及优先级以 [roadmap.md](./roadmap.md) 为准；不得自动启动 F-004B、F-005、F-006 或任何实现 Step。
