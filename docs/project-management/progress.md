# 项目进展

交付补充：[恢复来源、验证与边界](../delivery/parent-delivery.md)。原文所称Git未执行为历史端点状态；本次交付按对应PR的实际状态确认。

## 当前摘要

- 当前任务：无
- 最近完成：F-018 推荐优先、路线锚点闭环与方案有效对比
- 状态：`DONE / IMPLEMENTED / PASS / OFFLINE`
- 已完成：轻量景点推荐优先、偏好可跳过、区域锚点自动搜索/取消/完成反馈，以及只展示真实不同方案的每日对比。
- 验证：定向测试、desktop/390px synthetic、恢复 Development 和最终文档合同通过；真实 Provider 调用为 0。
- 基线：`output/f018/20260916-143834-baseline/`；最终证据：`output/f018/20260916-151500-final-closeout/`。
- 最近完成：F-017 旅行顾问对话体验与上下文连续性，`PASS / OFFLINE`。
- 已完成：地图旁三栏顾问抽屉、390px 单栏重排、有界对话、快捷回答、已确认偏好、确认式建议和结果页“旅行顾问建议”分层。
- 已通过：后端定向 11 项、前端定向 14 项、Ruff、TypeScript、synthetic desktop/390px 完整旅程、验证器 fail-closed 自检、完整 Development 与设计 QA。
- 恢复结论：浏览器脚本末尾分号和 Windows PowerShell stderr 换行误报均已最小修复；最终门禁完整通过。
- 最近完成：F-016 固定 Agent 评测、synthetic fail-closed 构建、desktop/390px 纵向验收和完整 Development 门禁。
- Agent 评测：23 项通过；fixture 状态隔离测试 1 项通过。
- 浏览器：两端三地点完整安排、V6 方案选择、说明降级/恢复、天气未知和逐日地图通过；控制台、存储、横向溢出、非 loopback 请求均为 0。
- 失败保留：三次恢复前失败分别记录外部地图资源误载、定位器歧义和 fake 跨旅程状态串扰，均未改写为 PASS。
- 最终证据：`output/f016/20260914-233459-offline-pass/`。
- 真实手工复验：`NOT_EXECUTED / NOT_AUTHORIZED`。
- Development：第 5 次完整门禁全部通过，包括完整后端/前端测试、格式、lint、类型检查、构建、文档检查器测试和仓库文档合同。
- 最终文档合同：状态更新后唯一一次执行通过；当前没有自动进入的下一任务。
- 当前权威：[F-018 任务卡](./f-018-advisor-discovery-anchor-option-clarity.md) 与 [current-task](./current-task.md)；当前无活动任务。

## 最近完成

- F-012 保持 `DONE / IMPLEMENTED / PASS / OFFLINE`；任务卡和全部既有证据只读。
- F-013 至 F-016 完成 V6 受约束顾问共同规划；V5、legacy/V2/V3/V4 和 replan 兼容边界保持。
