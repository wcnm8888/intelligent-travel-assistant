# 项目 Roadmap

## 使用规则

本文件是 Intelligent Travel Assistant 的项目级候选任务和优先级入口，不是任务批准记录。

- 执行期同一时刻最多只有一个 `ACTIVE` 任务；任务关闭、等待用户选择时允许没有活动任务；
- `CANDIDATE` 表示方向已进入路线图，不代表任务卡、范围或实现 Step 已批准；
- 用户必须从 roadmap 选择任务，再起草并批准 `current-task.md`；
- 不得因为前置任务完成而自动开始下一任务；
- 产品范围或架构边界变化时，先更新产品/架构文档并获得确认，再调整 roadmap；
- 已完成任务只保留一行结果摘要，完整任务卡进入 archive。

状态值：`ACTIVE`、`CANDIDATE`、`BLOCKED`、`DONE`、`DROPPED`。

## 当前阶段

目标：F-018 已关闭真实测试中暴露的顾问推荐、路线锚点和方案比较缺口；真实地图和 Provider UAT 保持独立 Gate。

| 顺序 | 任务 | 状态 | 用户价值 | 关键依赖 |
| --- | --- | --- | --- | --- |
| 0 | B-000 项目与工程基线 | DONE | 已建立可开发、可运行、可验证、可交接的本地工程底座；PR #1 已合并 | 无 |
| 1 | F-001 单城市双日旅行计划垂直切片 | DONE（产品状态 PARTIAL） | 用户能用真实天气、POI 和路线生成第一份可校验计划 | B-000、外部服务就绪门禁 |
| 2 | F-002 计划持久化、来源与版本 | DONE | 用户能保存、恢复和追踪计划版本及来源 | F-001 |
| 3 | F-003 局部重规划与影响确认 | DONE | 用户能调整当天，并在跨日/跨城影响前掌握决定权 | F-002 |
| 4 | F-004A 单城市 2–7 日计划扩展 | DONE | 用户可生成更长但仍可控、可追溯的单城市行程；PR #13/#16/#17 已依序合并 | F-003 |
| 5 | F-004B1 多城市领域、用户提供的城际段与离线约束 | DONE | 用户可表达 2–3 城顺序、住宿切换和用户提供的相邻城际段 | F-004A、D-013、归档任务卡 |
| 6 | F-005 外部服务韧性、时效与 Agent 评估 | DONE | provider 失败或数据过期时仍得到可信、可恢复结果 | F-001 至 F-004B1、D-014、归档任务卡 |
| 7 | F-004B2 真实城际 Provider 与可信城际事实 | BLOCKED | 经正式书面授权 Gate 后，为相邻城市段提供来源和时效可信的同日直达 rail 参考事实 | D-015 Step 1：SQLite 持久化禁止且 rail 字段授权不足 |
| 8 | F-004C 用户已购铁路段与车次信息 | DONE | 用户可录入已购票的相邻铁路段和车次事实，并继续按用户提供、未核验语义规划 | F-004B1、F-004B2 BLOCKED closure、D-016、归档任务卡 |
| 9 | F-006 MVP 体验收口与本地验收 | DONE | 用户可稳定完成完整本地旅行决策流程，并获得可恢复、可本地运行、可离线验收的 MVP | F-001 至 F-005、F-004C、D-017、归档任务卡 |
| 10 | F-007 高德路径规划 QPS 节流与真实调用稳定性 | DONE | 路径规划 attempt 使用单进程共享 0.5 秒 paced slot；真实 UAT 仍为 INCONCLUSIVE，不宣称 QPS PASS | F-005 attempt runtime、F-006、D-018、2026-08-30 FAIL、归档任务卡 |
| 11 | F-008 真实 UAT 缺陷收口与计划事实可信度 | DONE | 重规划恢复与计划事实能力完成离线验收；真实Provider UAT最终为INCONCLUSIVE | D-019–D-030；R5 PASS / OFFLINE；Step 13 DONE / INCONCLUSIVE，真实UAT 4/4；Step 14未执行；[归档](../archive/task-cards/F-008-real-uat-plan-fact-trust.md) |
| 12 | F-009 地图选点与空间可行旅行规划 | DONE | 用户可确认经过验证的住宿和景点，在生成前看到空间冲突，并以地图和完整列表查看确定性可行计划；离线门禁通过 | F-004A、F-007、D-031；[归档](../archive/task-cards/F-009-map-spatial-planning.md)；真实Provider UAT未授权 |
| 13 | F-010 地图优先统一规划流程与 DeepSeek 安全降级 | DONE | 用户在一条连续 V5 流程中先选点、再完善需求、预检并查看同一地图/列表计划；模型失败不丢失确定性结果 | F-009、D-032；[归档](../archive/task-cards/F-010-map-first-unified-flow.md)；真实地图与 Provider UAT 未授权 |
| 14 | F-011 旅行约束易用化、结果页重构与模型说明恢复 | DONE | 用户以地点名称建立约束、自然选择住宿，并在清晰时间轴中阅读或单独恢复 AI 游览提示 | `PASS / OFFLINE`；[任务卡](./f-011-travel-constraint-usability.md)；真实 UAT 未授权 |
| 15 | F-012 真实验收交互缺陷修复：地图 Marker 语义与预检保存恢复 | DONE | 用户能区分住宿、景点与选中点，并在部分保存或 revision 冲突后可靠进入空间预检 | `PASS / OFFLINE`；[任务卡](./f-012-real-acceptance-interaction-fixes.md)；真实 UAT 未授权 |
| 16 | F-013 真实测试缺陷稳定化 | DONE | 选点、实际安排、未采用原因与每日地图/说明严格一致 | [任务卡](./f-013-real-journey-stabilization.md)；`PASS / OFFLINE` |
| 17 | F-014 V6 顾问基础 | DONE | 用受约束顾问协助访谈偏好和策展地点，所有变更由用户确认 | [任务卡](./f-014-v6-advisor-foundation.md)；`PASS / OFFLINE` |
| 18 | F-015 完整共同规划闭环 | DONE | 比较最多三个可行方案并提供确认式冲突恢复和天气覆盖边界 | [任务卡](./f-015-joint-planning-loop.md)；`PASS / OFFLINE` |
| 19 | F-016 离线验收与真实 UAT 准入 | DONE | 固定 Agent 评测和纵向验收收口，真实 UAT 仍单独批准 | [任务卡](./f-016-offline-agent-acceptance.md)；`PASS / OFFLINE` |
| 20 | F-017 旅行顾问对话体验与上下文连续性 | DONE | 在地图旁通过有界对话、快捷回答和确认式建议协助旅客共同规划 | [任务卡](./f-017-advisor-conversation-experience.md)；`PASS / OFFLINE` |
| 21 | F-018 推荐优先、路线锚点闭环与方案有效对比 | DONE | 用户可先获得景点推荐、明确完成区域锚点选择并真正看懂可行方案差异 | [任务卡](./f-018-advisor-discovery-anchor-option-clarity.md)；`PASS / OFFLINE` |
| 22 | F-019 旅行顾问UI设计系统与核心旅程视觉重构 | DONE | 三栏选点与顾问、完整旅程状态及断点完成离线QA与最终确认 | [归档](../archive/task-cards/F-019-advisor-ui-design-system.md)；以本PR合并生效 |
| 23 | F-020 地图选点操作修复 | ACTIVE | 本地修复及203项测试通过，待用户复查住宿/入口/移除/顾问操作 | [任务卡](./f-020-map-selection-interactions.md) |

B-000 至 F-019已选任务的离线范围已收口；F-004B2保留原阻塞。当前活动任务为F-020。

## 当前任务入口

当前无活动任务；最近完成为 [F-018 推荐优先、路线锚点闭环与方案有效对比](./f-018-advisor-discovery-anchor-option-clarity.md)。
## 外部服务就绪门禁

F-001 的真实数据验收门禁包括：

- 创建高德开放平台账户、应用和适用的 Key；
- 创建和风天气账户和项目，按已批准的 JWT 方案准备项目 ID、凭据 ID、本地 Ed25519 私钥，并从控制台确认账户专属 API Host；
- 提供本项目独立的 DeepSeek Key，不复制 Agent1 的 `.env`；
- 确认三个服务的使用条款、所需 API 权限、配额、可能费用和测试用途；
- 将凭证只放入被 Git 忽略的本地配置，不写入文档、截图、fixture、日志或 CI；
- 同意执行范围受限、次数明确的 live smoke。

上述账户、凭证、条款确认和首次 live 授权已在 Step 37–38 满足，并取得一次三家 provider 的脱敏 live 契约证据。Step 45T 已取得完整双日 partial 的通过式真实计划 UAT；这不代表长期配额、费用或混合 fallback 质量永久有效，也不授权 Codex 登录、付费或再次调用真实 API。任何新的 live 回归仍须重新确认调用次数、费用和停止条件。

## MVP 完成边界

MVP 只有在 F-001 至 F-006 中被用户实际选择、批准并完成的必要任务共同满足以下结果时才完成：

- 中国大陆境内自由行需求可结构化输入；
- 真实天气、POI、地理和路线数据通过受控适配器进入计划；
- 结构化计划通过日期、时间、路线、预算和冲突校验；
- 住宿、城际交通、市内交通、门票、餐饮等费用完整表示，未知不按零处理；
- 计划、来源和版本可恢复；
- 局部重规划遵守当天自动、高影响确认边界；
- provider 失败、数据缺失和过期有明确降级；
- 用户能在轻量 Web UI 中完成完整流程；
- 默认测试离线，live 证据带时间和未覆盖范围。

## 非 roadmap 范围

以下方向不进入当前 MVP 候选任务：

- 自动预订、支付、出票和订单；
- 酒店、票务实时库存承诺；
- 登录、复杂用户系统和多人实时协作；
- 自主多 Agent 群；
- 公网部署和生产运维；
- 复杂地图、图片、PDF 和公开分享；
- 境外旅行。

新增这些方向前必须先变更产品范围、架构和风险边界并取得用户批准。

## 依赖关系

```text
B-000 工程基线
  ↓
外部服务就绪门禁 ─────┐
  ↓                    │
F-001 首个垂直切片 <───┘
  ↓
F-002 持久化与版本
  ↓
F-003 局部重规划
  ↓
F-004A 单城市 2–7 日
  ↓
F-004B1 多城市领域与用户提供段（DONE）
  ↓
F-005 韧性与评估（DONE）
  ↓
F-004B2 真实城际 Provider 与可信事实（BLOCKED / ARCHIVED）
  ↓
F-004C 用户已购铁路段与车次信息（DONE / ARCHIVED）
  ↓
F-006 MVP 收口（DONE / ARCHIVED）
  ↓
F-007 高德路径规划 QPS 节流（DONE / ARCHIVED）
  ↓
F-008（DONE / ARCHIVED；R5 PASS / OFFLINE；Step 13 DONE / INCONCLUSIVE；Step 14 NOT_EXECUTED）
  ↓
F-009 地图选点与空间可行旅行规划（DONE / IMPLEMENTED / PASS / OFFLINE；真实 UAT 未授权）
```

依赖图表达推荐顺序，不构成自动执行授权。用户可以调整候选任务、拆分范围或暂停项目。

Git同步授权（2026-09-17）：用户要求“帮我最新的同步到git上面”。允许在fix/f020-map-selection-interactions精确提交本轮五源文件与六份任务文档，并推送origin同名分支；保留main与原工作区历史dirty，不强推、不创建PR或合并、不自动宣告视觉验收。提交和推送结果以远端分支为准，本机记录为output/f020/20260917-222621-git-sync/result.json。
