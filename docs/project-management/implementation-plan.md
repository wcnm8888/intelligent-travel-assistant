# 实施计划

当前无活动任务，因此没有正在执行的 Step。

- 最近完成：F-018 `DONE / IMPLEMENTED / PASS / OFFLINE`。

## F-018 实施顺序

1. 冻结真实测试问题、dirty-worktree preimage 和离线边界。
2. 让明确推荐意图先触发一次受控只读景点发现，并约束顾问先给候选、后给可选问题。
3. 把区域地点改成自动搜索、明确选择、可取消的路线锚点任务。
4. 让 V6 只返回各优化目标真实选中的不重复方案，并在卡片内展示每日地点与交通分布。
5. 依次执行相邻测试、Development、desktop/390px synthetic 和文档合同；失败即停止并保留首证据。

F-018 不改变确定性路线、时间和可行性事实，不新增依赖、数据库或真实 Provider 调用。

## F-017 已完成实施顺序

1. 建立独立基线、唯一 ACTIVE 任务和严格有界的顾问会话投影。
2. 将选点页重构为地点列表、地图、可折叠顾问抽屉；补齐快捷回答、已确认偏好和建议类型分层。
3. 在结果页明确标记旅行顾问建议，保持确定性地点、路线、时间和可行性事实不变。
4. 依次执行离线定向验证、一次 Development 门禁、desktop/390px synthetic 浏览器与设计 QA，再做文档收口。

F-017 未新增依赖、数据库、Provider 或第二条流程；本地验收中的真实地图、高德、DeepSeek 和和风调用均为 0。

## F-013 至 F-016 当前结果

- F-013：选点计数、多日地图图层和受约束说明稳定化，`PASS / OFFLINE`。
- F-014：V6 Advisor Session、需求访谈和地点策展确认闭环，`PASS / OFFLINE`。
- F-015：最多三个可行方案、类型化冲突恢复和 V6 计划创建，`PASS / OFFLINE`。
- F-016：固定 Agent 评测、desktop/390px synthetic 纵向验收、第 5 次完整 Development 门禁和状态更新后的 documentation contracts 均通过，任务为 `DONE / IMPLEMENTED / PASS / OFFLINE`。
- 最终证据：`output/f016/20260914-233459-offline-pass/`。
- 真实地图、高德 Web Service、DeepSeek、和风调用均未执行；Phase 2 仍需独立授权。

## 最近完成的 F-012 Step 1

- 状态：`DONE / IMPLEMENTED / PASS / OFFLINE`
- 基线：`output/f012/20260914-193721-baseline/`
- 顺序：任务激活 → RED 定向测试 → Marker 角色/选中态 → 部分保存与有界冲突恢复 → 本地反馈/前置校验 → GREEN 定向 → typecheck/lint/build → Development 门禁 → loopback synthetic 浏览器 → 离线收口。
- 文件职责、恢复安全条件和额度以 [F-012 任务卡](./f-012-real-acceptance-interaction-fixes.md) 为准。
- Provider：真实地图、高德、DeepSeek、和风调用全部为 0；自动浏览器不得操作当前真实验收页面。
- 完成：住宿/景点/选中态可同时区分；部分保存后不遗留旧 revision；真实并发选择不被覆盖；用户可进入空间预检。
- 停止：需要后端、秘密、真实 Provider、非 loopback、新依赖、范围外文件、保护对象变化、Git 交付或任一额度耗尽。
- 恢复执行：保留首个门禁失败证据；runner 改为动态 loopback 端口并将端口注入 Vite 代理，绝不停止既有用户服务。新增相邻定向验证 1 次、Development 门禁 1 次、最终 documentation contracts 1 次；synthetic 浏览器仍为 0/1。

## 最近完成的 F-011 Step 1

## Step 1：Slice A–E 离线实现与验收

- 状态：`DONE / IMPLEMENTED / PASS / OFFLINE`
- 基线：`output/f011/20260914-152229-baseline/`
- 顺序：任务治理 → 前端关系/住宿/结果/信息分层 → narrative-only retry → 定向测试 → 一次 Development 门禁 → 一批 loopback synthetic 浏览器验收 → 离线收口。
- 额度：同根因 2 轮；前端定向 2 次；后端定向 2 次；Development 1 次；synthetic 1 批（desktop 1、390px 1）。
- Provider：真实地图、高德、DeepSeek、和风调用全部为 0。
- 停止：秘密、真实 Provider、非 loopback、新依赖、数据库变化、确定性事实改写、范围扩大、历史保护变化、Git 交付或额度耗尽。
- 实际门禁：Development `1/1` 已消费；`Frontend tests` 子门禁失败。未执行 frontend build、门禁内文档检查器测试、仓库文档合同及最终 documentation contracts。
- Step 1R 顺序：一次离线前端诊断 → 根因成立后一次 F-011 前端职责内最小修复 → 一次前端定向验证 → 一次新 Development 门禁 → 状态收口 → 一次最终 documentation contracts。
- Step 1R 额度：诊断 1、修复 1、前端定向验证 1、新 Development 门禁 1、最终文档合同 1；后端测试、浏览器、真实地图和 Provider 均为 0。
- 停止：根因落在授权文件外、诊断无法复现、修复或任一验证失败、需要新增依赖/Provider/浏览器/后端测试或超过新额度。
- 实际诊断：前端诊断 `1/1` 复现两个 5000 ms 超时，其中 `multicityPlanning.red.test.tsx` 不在授权文件内，已在修复前停止。
- 已完成：隔离批次 1/1 中两个文件单跑均通过；确认全套并发 jsdom 负载触及默认 5000 ms 超时。修复 1/1 已在 `frontend/vite.config.ts` 设置 `testTimeout: 10_000`。
- 已通过：前端定向验证 1/1，2 文件、9 测试全绿。
- 已消费：新 Development 门禁 1/1；前端全量测试与 build 通过，最终文档与仓库合同子门禁失败。
- 未消费且不得执行：最终文档合同 0/1，需先获新的精确诊断/修复授权。
- Step 1C 顺序：文档合同诊断 1 次 → 根因确认后最小修复（最多 2 轮）→ 定向文档验证（最多 2 次）→ 新 Development 门禁 1 次 → 状态收口 → 最终文档合同 1 次。
- Step 1C 不新增产品功能、前后端定向测试、浏览器、真实地图、Provider 或 Git 交付。
- 文档诊断确认 `Step 1C` 不属于检查器支持的数字 Step 合同；当前投影已回归正式 `Step 1`，Step 1C 仅作为恢复段落标题保留。
- 定向文档合同验证 1/2 已通过；进入新 Development 门禁 1/1。
- 新 Development 门禁 1/1 已完整通过；F-011 进入最终状态更新后的唯一 documentation contracts 后置验证。
- 状态更新后的唯一 documentation contracts 1/1 已通过；F-011 离线收口完成。
- readiness 预检曾因非闭集状态词拒绝且明确未创建正式批次；状态规范化后仍只允许一个正式 Development 门禁。

## 历史实施记录
