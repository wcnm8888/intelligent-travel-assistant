# 当前任务

当前无活动任务。

以下为最近完成的 F-005 关闭摘要，完整任务卡已归档。

## 任务元数据

- 任务 ID：`F-005`
- 名称：外部服务韧性、数据时效与 Agent 评估
- 等级：`L`
- 状态：`DELIVERED / ARCHIVED`
- Step 0–9：全部 `DONE`
- 基线提交：`c5f07e12abdc37f977ee0f7181a5f2800f015066`
- 完整功能 main：`fddd4e5add5919f1751279de9b833a3192ea6338`
- 完整功能 main CI：run `32452988076`，`PASS`
- 远程交付：PR #27/#28/#29/#30/#31 已依序 squash merge；无需替代式 clean-restack，未 force-push
- 归档任务卡：[F-005 外部服务韧性、数据时效与 Agent 评估](../archive/task-cards/F-005-external-service-resilience-freshness-agent-eval.md)

## 已交付摘要

- 统一 Amap/QWeather/DeepSeek 安全错误、retry/attempt/deadline、取消、peer drain、terminal 零新调用和逐能力 freshness 裁决；
- legacy/V2/V3 与 F-003 继续复用既有 URI、公开 shape、SQLite schema v2 和 migration 1/2；
- proposal/repair 使用 bounded typed allowlist，Provider 不可信文本被隔离；
- 48 个固定 synthetic case 经过 legacy/V2/V3/F-003 各自真实离线 application 入口，五类硬门禁 100%，加权分 100%；
- 前端只消费服务端同 shape 的 `data_stale`、retryable、partial/failed 与恢复动作，不重算 freshness 或终态；
- 完成临时 SQLite、loopback desktop/390px QA、网络/console/accessibility 与独立隐私安全审查；
- 没有新增 Provider、Schema/migration、依赖、lockfile、账号、遥测、公网服务或真实 Provider UAT。

## 保留历史事实

- F-001 产品状态保持 `PARTIAL`；Step 45M 真实 UAT `FAIL`、Step 45T 真实 UAT `PASS`；
- unknown 金额保持 `null`，不得按 0 处理；混合交通 fallback 仍只有离线证据；
- F-004A/F-004B1 均无真实 Provider UAT，F-004B1 城际 Provider 调用仍为 0；
- Step 7 首次 Playwright CLI `npx` 探测可能查询 npm registry，后续浏览器请求均为 loopback；
- Step 8 Codex CLI 全局插件外连失败不构成真实 Provider UAT；两项过程偏差均已由用户接受。

## 下一入口

roadmap 推荐下一候选为 `F-004B2 真实城际 Provider`，其 Provider、条款、费用、隐私、Schema、依赖和真实调用边界仍须单独起草并批准任务卡；不得自动开始 F-004B2 或 F-006。
