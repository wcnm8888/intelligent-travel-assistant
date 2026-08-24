# 当前任务

当前无活动任务。

## 最近关闭

- 任务：`F-006 MVP 体验收口与本地验收`
- 状态：`DELIVERED / LOCAL_ACCEPTANCE_PASS / ARCHIVED`
- Step 0–8：全部 `DONE`
- 完整功能 main：`d82ca5c65794749932be65724455aca146a7cbca`
- 完整功能 main CI：run `32691778088`，`PASS`
- 远程交付：PR #38/#39/#40/#41 已依序 squash merge；#39/#40/#41 以普通 merge clean-restack，无 force-push
- 完整任务卡：[F-006 archive](../archive/task-cards/F-006-mvp-local-acceptance.md)

## 下一入口

roadmap 当前没有新的 `CANDIDATE`。后续工作必须先起草并批准新的任务卡或路线图变更；不得自动恢复 F-004B2 或执行新的真实 Provider 调用。

## 保留边界

- F-006 本地 MVP 状态为 `DELIVERED / LOCAL_ACCEPTANCE_PASS / ARCHIVED`，但项目真实 Provider 就绪继续为 `PARTIAL`；
- F-004B2 保持 `BLOCKED / ARCHIVED`，D-015 历史不变；
- F-001 `PARTIAL`、Step 45M `FAIL`、Step 45T `PASS`；
- unknown 金额保持 `null`，混合交通 fallback 只有离线证据；
- F-004A/F-004B1/F-004C/F-005/F-006 没有新增真实 Provider UAT，F-004B1/F-004C 城际 Provider 调用为 0；
- F-005 offline eval、MockTransport、synthetic fixture、loopback QA 和 F-006 local acceptance 不等于真实 UAT；
- SQLite schema version 2，migration 只有 1/2。
