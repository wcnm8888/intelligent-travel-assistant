# F-010 地图优先统一规划流程与 DeepSeek 安全降级

## 当前执行状态

- 任务：`F-010 地图优先统一规划流程与 DeepSeek 安全降级`
- 状态：`DONE / IMPLEMENTED / PASS / OFFLINE`
- 当前 Step：`Step 6 - 完整本地门禁与文档收口（DONE）`
- 执行边界：本地离线开发；真实高德、DeepSeek、和风及真实地图加载均未授权
- 基线证据：`output/f010/20260913-221544-baseline/`
- Git 交付：未授权 commit、push、PR、CI、merge 或 remote 修改
- 修复规则：同一根因最多两轮修复—复验；第三轮停止并保留证据
- 历史边界：F-008、F-009 已归档结论及证据只读

## 冻结目标

把 F-009 从与经典规划互斥的第二套页面改为唯一、连续的地图优先 V5 用户旅程：地图与列表选点 → 完善需求 → 保存选择 → 空间预检 → 创建计划 → 地图与完整列表结果。地图失败只降级展示；DeepSeek 只生成冻结日程的叙述，叙述失败保留确定性计划并返回 `partial`。

## Step 状态

| Step | 业务切片 | 状态 |
| --- | --- | --- |
| Step 0 | 任务卡、基线和长期决策 | DONE |
| Step 1 | 统一 TripDraft 和步骤式界面 | DONE |
| Step 2 | 主流程接入唯一 V5 计划 | DONE |
| Step 3 | DeepSeek narrative 降级和安全诊断 | DONE |
| Step 4 | 地图配置提示和失败体验 | DONE |
| Step 5 | synthetic 浏览器纵向验收 | DONE |
| Step 6 | 完整本地门禁与文档收口 | DONE |

## 允许修改职责

- 前端：`App.tsx`、F-009 组件/API/测试、必要的共享草稿组件、相邻样式和严格解析测试。
- 后端：现有 F-009 application/provider/API 投影及其相邻测试；不得复制 solver 或 DTO。
- 文档：当前任务、计划、进度、roadmap、产品/架构/设计/API/测试/决策及无秘密配置模板。
- 工具：当前任务 readiness、文档检查和纯 loopback synthetic 支撑。

## 不变量

- legacy/V2/V3/V4 的 URI、严格解析、Repository、持久化和终态语义不变。
- 新默认前端只提交 V5 session/revision/feasibility；不得回退 legacy 生成。
- POI 身份、路线、排程和可行性由后端确定；DeepSeek 不决定事实。
- V5 Provider 派生数据、模型原始输出、坐标和 geometry 不进入 SQLite、localStorage、日志或文档。
- 不新增依赖，不修改数据库 Schema/migration，不读取秘密，不调用真实 Provider。
- F-008 保持 `DONE / ARCHIVED`；F-009 保持 `DONE / IMPLEMENTED / PASS / OFFLINE`，真实 UAT 未执行。

## 验收

1. 第一屏是地图与列表选点，不存在两套互斥生成方案。
2. 选择、详细需求、预检、V5 计划和结果使用同一内存草稿与 session revision。
3. 返回步骤、地图失败和 Loader 重试不清空选择。
4. DeepSeek generation/repair 非法只使 V5 叙述降级，确定性计划和 MapPlan 保留。
5. 安全诊断展示闭集 code、阶段、调用计数、保留结论和 retryable，不暴露原始内容。
6. 缺少 Web JS 配置时给出可操作提示，完整列表仍可完成。
7. desktop/390px synthetic 浏览器、legacy 回归和完整开发门禁通过，非 loopback 调用为 0。

## 停止条件

需要真实 Provider/地图、秘密、依赖、数据库变化、删除覆盖、历史改写或 Git 交付时必须创建新任务并重新取得授权。

## 离线收口

- 默认前端只呈现一条地图/列表选点 → 详细需求 → 空间预检 → V5 计划 → 地图/列表结果旅程；legacy 入口只保留测试兼容，不作为用户入口。
- DeepSeek generation/repair 的身份、日期、顺序或 Schema 非法时返回安全闭集诊断，V5 结果降级为 `partial`，确定性计划和 MapPlan 保留。
- synthetic 地图成功、顺序篡改和 Web JS 配置缺失三条真实浏览器旅程全部通过；网络仅 loopback，console error/warning 为 0，390px 无横向溢出。
- `scripts/verify.ps1 -Phase Development` 一次通过：Python 3.13.3、Node 22.16.0、pnpm 11.19.0、2608 项后端测试、169 项前端测试、构建、文档与仓库合同全绿。
- 证据：离线浏览器验收（本机历史证据：`output/f010/20260913-223829-offline-browser/README.md`）。真实地图与 Provider UAT 均未执行、未授权。
