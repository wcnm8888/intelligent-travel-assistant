# F-015 完整共同规划闭环

## 状态

`DONE / IMPLEMENTED / PASS / OFFLINE`

## 业务结果

确定性求解器为 V6 返回最多三个不重复的可行方案，分别强调交通更少、节奏更轻松和偏好覆盖更高；Agent 只解释差异，用户必须主动选择 option ID 后才能创建计划。

## 实现边界

- V6 feasibility set 绑定 session、revision 和一次性 option ID；选点或确认动作变化立即使旧方案失效。
- 类型化恢复动作只在用户确认后执行，包括换日、缩短时长、允许省略、删除可选项和解除组合关系。
- 天气只有存在覆盖行程日期的证据时才进入建议；远期或缺失数据统一为“天气尚不可核验”。
- narrative-only retry 不重新搜索 POI、调用路线、求解、预检或天气，不改变计划与 MapPlan。
- V6 仍为应用级内存数据，不新增数据库 Schema 或 migration。

## 验证

方案选择、revision 失效、恢复动作、V6 创建、MapPlan、narrative 降级/恢复和 replan 写前拒绝均由离线测试与最终浏览器旅程覆盖。

真实 Provider UAT 未执行。
