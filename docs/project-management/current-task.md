# 当前任务

当前无活动任务。

## 最近关闭

- 任务：`F-004C 用户已购铁路段与车次信息`
- 状态：`DELIVERED / ARCHIVED`
- Step 0–6：全部 `DONE`
- 完整功能 main：`14c4deaf5acfc4b8e3ccfb18db172dfe910eb26e`
- 完整功能 main CI：run `32484789531`，`PASS`
- 远程交付：PR #34/#35/#36 已依序 squash merge
- Provider：未接入；城际 logical call 和 HTTP attempt 均为 0
- 完整任务卡：[F-004C archive](../archive/task-cards/F-004C-booked-rail-user-provided.md)

## 下一候选

roadmap 当前推荐 `F-006 MVP 体验收口与本地验收`。候选任务不构成激活或实现授权，必须先起草任务卡并单独批准 Step 0。

## 保留边界

- F-004B2 保持 `BLOCKED / ARCHIVED`，D-015 历史不变；未来真实城际 Provider 必须使用新版本和新决策；
- F-004C V4 只表示 `user_provided / unknown_validity / 用户提供，未核验`，不证明车次真实、余票、可售或库存；
- F-001 `PARTIAL`、Step 45M `FAIL`、Step 45T `PASS`；
- unknown 金额保持 `null`，混合交通 fallback 只有离线证据；
- F-004A/F-004B1/F-005/F-004C 无真实 Provider UAT，F-004B1/F-004C 城际 Provider 调用为 0；
- F-005 offline eval、MockTransport、synthetic fixture、loopback QA 不等于真实 UAT；
- SQLite schema version 2，migration 只有 1/2。
