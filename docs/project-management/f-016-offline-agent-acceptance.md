# F-016 离线验收与真实 UAT 准入

## 状态

`DONE / IMPLEMENTED / PASS / OFFLINE`

## 业务结果

V6 顾问共同规划通过固定离线 Agent 评测与桌面/390px 纵向浏览器验收；真实地图和 Provider 仍保持独立 Phase 2 准入。

## 评测与浏览器结果

- Agent 定向评测 23 项通过，覆盖五类旅客、偏好提取、建议确认、注入隔离和说明对齐。
- synthetic narrative fixture 状态隔离直接测试 1 项通过。
- desktop 与 390px 均完成：三独立地点、顾问建议确认、三方案比较、选择轻松方案、计划生成、说明安全降级及单独恢复、天气未知和第二日地图切换。
- 两端 localStorage/sessionStorage 为空、无横向溢出、控制台 error 为 0、非 loopback 请求和拦截次数均为 0。

## 失败保留

- 首次批次因生产地图 Loader 被错误用于 synthetic 构建而发生外部地图资源请求，证据保留为 FAIL。
- 第二次批次因列表按钮与 synthetic Marker 定位器重名而停止。
- 第三次批次因 narrative fake 跨旅程共享累计状态导致 390px 等待降级按钮超时而停止。
- 修复采用 synthetic 专用 fail-closed 构建、浏览器导航前网络拦截、列表控制面定位和三调用周期隔离；失败历史未删除或改写。

## Phase 2 准入

真实高德 Web Service、Web JS 地图、DeepSeek 与和风均为 `NOT_EXECUTED / NOT_AUTHORIZED`。任何真实 UAT 必须重新批准配置、次数、预算、证据目录和首次失败停止规则。

## Step 状态

| Step | 目标 | 状态 |
| --- | --- | --- |
| Step 0 | F-012 离线恢复 | DONE |
| Step 1 | F-013 真实测试缺陷稳定化 | DONE |
| Step 2 | F-014 V6 顾问基础 | DONE |
| Step 3 | F-015 共同规划与 F-016 浏览器验收 | DONE |
| Step 4 | 最终 Development 门禁与文档收口 | DONE |

第 3 次门禁后的四文件 Frontend format 恢复通过。第 4 次完整 Development 门禁定位并修复 `F009Map.tsx` effect 状态复位与 `f009Api.ts` 未使用解构；第 5 次完整 Development 门禁全部通过。状态更新后的唯一 documentation contracts 通过后，F-016 完成离线收口。真实地图与 Provider UAT 仍为独立 Phase 2，未执行且未授权。
