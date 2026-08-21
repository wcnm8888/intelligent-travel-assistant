# 项目进度

## 当前状态

- 当前任务：无
- 最近关闭：`F-004B2 真实城际 Provider 与可信城际事实`，状态 `BLOCKED / ARCHIVED`
- Step 1：`DONE / BLOCKED`
- Provider/法律 Gate：`BLOCKED`
- 当前 Provider：未选定；高德候选因持久化与 rail 字段许可不足而阻塞
- 当前授权：不得进入 Step 2 或实现
- 下一候选顺序：F-004C → F-006；均不得自动启动

## F-004B2 Step 0

- 已只读复核 `main == origin/main == 96f73d99c04a72e1e697172306d8f33d006419ec` 和 Step 0 开始前的干净工作区；
- 已确认 PR #27/#28/#29/#30/#31 依序 squash merge，归档 PR #32 已合并；
- 已确认最终归档 main CI run `32453988289` 为 `success`；
- 已确认 Step 0 开始前没有活动任务或开放 PR；
- 已条件式激活 F-004B2，建立 D-015、Step 0–10、五层 stacked PR、核心文件、受控相邻扩展和规模阈值；
- Provider/法律 Gate 尚未 PASS：Step 1 只能审核用户提供的正式书面授权、合同、工单回复或官方控制台事实；
- 本 Step 不修改源码、测试、fixture、Schema、migration、依赖、lockfile、数据库或归档任务卡，不读取秘密，不调用 Provider，不进行远程 Git 写入。
- 已从已复核的干净 main 基线创建首层本地分支 `feat/f-004b2-intercity-domain-contracts`；没有 commit、push、PR 或远程 CI。

## F-004B2 Step 1

- 用户已批准只审核其提供的高德官方书面回复；没有访问回复中的价格链接或其他外部资料；
- 回复确认非商用个人开发 Web 服务 API 场景原则上允许，建议来源声明，且只允许运行期内存临时保存；
- 回复明确禁止 SQLite 持久化，与 D-015 的最终 observation 最长 30 天保存边界直接冲突；
- 回复没有明确授权车次、铁路站点、发到时间、历时等 rail 字段；
- 数值配额/QPS/价格、固定 endpoint/version 和真实 UAT 准入/销毁条件也未由所提供证据建立；
- 正式 Gate 结果为 `BLOCKED`，Step 2–10 全部停止。

## 最近完成：F-005

- F-005 Step 0–9 已完成并归档；
- PR #27/#28/#29/#30/#31 已依序 squash merge，完整功能 main 为 `fddd4e5add5919f1751279de9b833a3192ea6338`，CI run `32452988076` 为 `success`；
- 归档 PR #32 已合并，最终归档 `main == origin/main == 96f73d99c04a72e1e697172306d8f33d006419ec`；
- 最终归档 main CI run `32453988289` 为 `success`；
- F-005 没有真实 Provider UAT；离线 eval、MockTransport、synthetic fixture 和 loopback QA 不等同真实 UAT。

## 当前阻塞与下一入口

当前没有活动任务。F-004B2 已以 `BLOCKED` 状态归档；只有在补充正式书面授权明确允许所需 rail 字段和批准的 SQLite 保存边界，或用户另行批准改变产品/持久化架构后，才能起草新的恢复决策，不得恢复 Step 2。

roadmap 下一候选为 F-004C：用户已购铁路段与车次信息，之后为 F-006。F-004C 仍未激活或实现，必须先单独批准 Step 0。

## 保留历史事实

- F-001 产品状态为 `PARTIAL`；
- Step 45M 真实 UAT 为 `FAIL`，Step 45T 真实 UAT 为 `PASS`；
- unknown 金额不按 0；混合交通 fallback 只有离线证据；
- F-004A、F-004B1、F-005 均无真实 Provider UAT；
- F-004B1 城际 Provider 调用为 0；
- SQLite schema 保持 version 2，migration 只有 1/2。

## 权威入口

- [当前任务](./current-task.md)
- [实施计划](./implementation-plan.md)
- [路线图](./roadmap.md)
- [证据](./evidence.md)
- [D-015](../decisions.md#d-015f-004b2-真实城际-provider-与可信城际事实条件式边界)
- [F-004B2 BLOCKED archive](../archive/task-cards/F-004B2-real-intercity-provider-blocked.md)
- [F-005 archive](../archive/task-cards/F-005-external-service-resilience-freshness-agent-eval.md)
