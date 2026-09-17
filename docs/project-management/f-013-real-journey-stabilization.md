# F-013 真实测试缺陷稳定化

## 当前状态

- 状态：`DONE / IMPLEMENTED / PASS / OFFLINE`
- 当前 Step：`Step 1 - 选点计数、多日地图与说明恢复（DONE）`
- 前置任务：F-012 `DONE / IMPLEMENTED / PASS / OFFLINE`
- 真实地图与 Provider：`NOT_EXECUTED / NOT_AUTHORIZED`
- Git 交付：`NOT_AUTHORIZED`

## 唯一业务目标

修复真实测试暴露的结果一致性与解释缺口：住宿、景点、已选中状态必须以颜色、图形和文字区分；每个独立地点都进入计划；二选一未采用地点有明确原因；每日地图图层与当日文字计划严格对应；受约束游览说明恢复且失败不污染确定性事实。

## 冻结边界

- 先断言 MapPlan 每日数据，再区分后端投影与前端图层替换根因。
- 前端地图实例只初始化一次，切日精确替换 Marker 和 Polyline。
- 预检和结果页显示已选择、实际安排、二选一未采用三个闭集计数。
- 三个独立地点必须全部安排；二选一只安排一个并显示未采用原因。
- DeepSeek 只生成与冻结停靠点等长、按日/序号映射的说明；不能增删地点、改日期、顺序、时间或路线。
- 经典文字规划仅做兼容回归；不恢复第二条主流程。
- 不新增依赖、数据库、浏览器持久化或真实调用。

## 允许职责

- 前端：`frontend/src/F009Map.tsx`、`F009Planner.tsx`、`f009Api.ts`、`styles.css` 及相邻测试。
- 后端：V5 MapPlan/solver/DeepSeek narrative 的既有 `application/f009`、`contracts/f009.py`、`f009_deepseek.py`、API 投影与直接测试。
- synthetic：F-009/F-010 浏览器 support 中与多地点、多日、narrative 对齐直接相关的最小变化。
- 治理、文档与 `output/f013/` 证据。

## 完成条件

- 三个独立地点：selected=3、planned=3、omitted=0；二选一：planned 少 1 且明确列出未采用地点与原因。
- 多日切换后文字、Marker、Polyline 的 location/route ID 集合逐日一致，无上一日残留。
- narrative 合法输出映射到冻结停靠点；错误长度、额外地点、空内容经一次 repair 后仍失败则仅降级说明。
- 定向、全量与 offline/loopback 浏览器验收通过；非 loopback 和真实 Provider 调用为 0。

## 完成结果

- 预检与结果页展示 selected/planned/omitted 闭集计数，三个独立地点完整进入计划，二选一未采用项明确说明原因。
- 地图实例只初始化一次，切日时精确替换当日 Marker 和 Polyline；地图与列表继续共用 location ID。
- narrative 改为按日、按停靠点序号的等长 Schema，模型不能回写日期或 UUID；失败仍保留确定性计划。
- F-016 最终 desktop/390px 纵向验收覆盖上述行为并通过；真实 Provider UAT 未执行。

## 停止条件

需要真实地图/Provider、秘密、新依赖、数据库迁移、改变 V5 确定性事实或 legacy/V2/V3/V4、范围外文件、破坏历史证据、Git 交付或破坏性操作时停止。
