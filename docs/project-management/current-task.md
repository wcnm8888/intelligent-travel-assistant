# 当前任务

当前无活动任务。

## 最近关闭

- 任务：`F-004B2 真实城际 Provider 与可信城际事实`
- 状态：`BLOCKED / ARCHIVED`
- Step 0：`DONE`
- Step 1 Provider/法律 Gate：`DONE / BLOCKED`
- 结论：高德官方回复禁止将 API 数据持久化到 SQLite，且没有明确授权 F-004B2 所需的 rail 字段；两项分别都足以阻塞 D-015
- Provider：未选定；不得恢复 Provider 查询或进入 Step 2–10
- 完整任务卡：[F-004B2 BLOCKED archive](../archive/task-cards/F-004B2-real-intercity-provider-blocked.md)

## 下一候选

roadmap 推荐顺序为：

1. `F-004C 用户已购铁路段与车次信息`
2. `F-006 MVP 体验收口与本地验收`

候选任务不构成激活或实现授权。F-004C 必须先单独批准 Step 0；F-006 不得自动开始。

## 保留边界

- F-004B2 的 `BLOCKED` 历史和 D-015 保持，不得改写为已实现、已选 Provider 或真实 UAT；
- F-001 `PARTIAL`、Step 45M `FAIL`、Step 45T `PASS`；
- unknown 金额保持 `null`，混合交通 fallback 只有离线证据；
- F-004A/F-004B1/F-005 无真实 Provider UAT，F-004B1 城际 Provider 调用为 0；
- F-005 offline eval、MockTransport、synthetic fixture、loopback QA 不等于真实 UAT；
- SQLite schema version 2，migration 只有 1/2。
