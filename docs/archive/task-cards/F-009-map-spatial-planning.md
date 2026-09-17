# F-009 地图选点与空间可行旅行规划

## 当前执行状态

- 任务：`F-009 地图选点与空间可行旅行规划`
- 状态：`DONE / IMPLEMENTED / PASS / OFFLINE`
- 完成范围：`Step 0–9`
- 执行边界：本地离线开发；真实高德、DeepSeek、和风及真实地图加载均未授权
- 工作树边界：保留全部 F-008 tracked/untracked 内容；禁止 stash、reset、clean、删除或覆盖
- 基线证据：`output/f009/20260913-142327-baseline/`
- Git 交付：未授权 commit、push、PR、CI、merge 或 remote 修改
- 修复规则：同一根因最多两轮修复—复验；正式失败保留首次证据
- 未执行项：`Step 10 real_amap_provider_uat=NOT_EXECUTED / NOT_AUTHORIZED`

## 冻结目标

在单城市 2–7 日范围内提供经过验证的住宿与 POI 选点、生成前空间可行性预检、确定性分日与排序、受限 DeepSeek 说明，以及地图与完整列表结果。V5 数据使用应用级内存，不新增 SQLite Schema 或 migration。

## Step 状态

| Step | 业务切片 | 状态 |
| --- | --- | --- |
| Step 0 | 任务卡、范围、基线和决策 | DONE |
| Step 1 | 住宿与结构化 POI 选择合同 | DONE |
| Step 2 | POI 发现 API 与确定性过滤 | DONE |
| Step 3 | 地图与列表同步选点 | DONE |
| Step 4 | 路线预检与异常拒绝 | DONE |
| Step 5 | 分日、排序与不可达恢复 | DONE |
| Step 6 | DeepSeek 受限 V5 planning job | DONE |
| Step 7 | 最终地图、每日路线与完整列表 | DONE |
| Step 8 | 合成纵向与浏览器离线验收 | DONE |
| Step 9 | 完整本地门禁与文档同步 | DONE |
| Step 10 | 真实地图与 Provider UAT 独立准入 | BLOCKED |

## 不变量

- legacy/V2/V3/V4 的 URI、严格合同、持久化和终态语义不变。
- V5 最多 8 个用户候选地点、每天最多 4 个原子 POI；推荐开关默认关闭。
- 后端是 POI 身份、坐标、行政区、路线和可行性事实的唯一权威。
- must_visit 不得自动删除或替换；Provider 失败不得标成真实不可达。
- Provider 派生候选、坐标、路线和 polyline 不进入 SQLite、localStorage、日志或文档。
- 地图不是唯一控制面；地图失败时完整列表仍可完成选择、预检和查看计划。
- F-008 保持 `DONE / ARCHIVED`、R5=`PASS / OFFLINE`、Step 13=`DONE / INCONCLUSIVE`。

## 完成条件

Step 0–9、14 项离线验收、兼容回归、真实 loopback 浏览器和完整本地门禁已通过，任务记为 `IMPLEMENTED / PASS / OFFLINE`。真实地图和 Provider UAT 保持 `NOT_EXECUTED / NOT_AUTHORIZED`，只能经独立批准进入 Step 10。

## 最终离线结论

- V5 预规划、POI 身份过滤、结构化选择、确定性预检/求解、受限叙述、MapPlan 与列表降级均已实现。
- 完整开发门禁通过：后端 2605 项测试、前端测试与构建、格式、lint、mypy、TypeScript、依赖锁、文档及仓库合同全部通过。
- loopback-only Chromium 完成桌面与 390 px 主流程；地图 Loader 失败时列表、预检和结果继续可用，console error/warning 为 0，浏览器请求仅为 `127.0.0.1`。
- F-008 保护清单 365 项 SHA-256 复核无变化；staged 路径为 0，branch/HEAD 保持实施前值。
- 唯一 F-009 离线证据目录为 `output/f009/20260913-153600-offline/`；不得解释为真实 Provider 或真实地图 UAT。
