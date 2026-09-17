# F-014 V6 顾问基础

## 状态

`DONE / IMPLEMENTED / PASS / OFFLINE`

## 业务结果

V6 引入单个 `TravelAdvisorAgent` 的需求访谈和地点策展角色。顾问只返回严格问题、偏好补丁和已验证 POI 建议，不直接修改用户选择；接受动作绑定 expected revision 与 client request ID，成功后才增加 session revision。

## 实现边界

- Advisor Session、建议和确认状态与预规划 Session 共用内存 TTL，不进入 SQLite 或浏览器持久化。
- 未确认 POI 不进入 selection、solver、模型计划输入或最终结果。
- 模型输入不包含地点 UUID、Provider 原始响应、秘密或思维链。
- 地图旁顾问面板提供接受、忽略和在地图查看；安全摘要只显示确认数量和待处理数量。
- V5 与 legacy/V2/V3/V4 合同保持不变。

## 验证

严格 DTO、幂等、stale revision、提示词注入作为数据、候选索引越界和显式确认路径均由离线测试覆盖；最终浏览器纵向验收通过。

真实 DeepSeek、高德、地图和和风调用均未授权、未执行。
