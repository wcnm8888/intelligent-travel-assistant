# F-012 真实验收交互缺陷修复：地图 Marker 语义与预检保存恢复

## 当前状态

- 状态：`DONE / IMPLEMENTED / PASS / OFFLINE`
- 当前 Step：`Step 1 - Marker 语义与预检保存恢复（DONE）`
- 基线：`output/f012/20260914-193721-baseline/`
- 真实地图与 Provider 复验：`NOT_EXECUTED`
- Git 交付：`NOT_AUTHORIZED`

## 业务目标

修复本地真实验收中已确认的两个用户阻断：地图 Marker 必须明确表达住宿、景点与选中状态；旅行信息两段保存必须在部分成功或 revision 冲突后保持最新 session，并在不覆盖他人选择的前提下安全恢复到空间预检。

## 已确认根因

1. `F009Map` 的普通候选没有 accommodation/visit 角色；所有无 `visit_order` 的 Marker 都显示“住”，并沿用高德默认蓝色。`selectedLocationIds` 只改变 zIndex。
2. `saveDetails` 先 `updateTrip` 再 `updateSelection`，但只在第二步也成功后更新 session；第二步失败会遗留旧 revision，再次保存触发 `selection_revision_conflict`。
3. Development 门禁中的 runner preflight 把 8000/5173 写死为唯一端口，用户已经运行本地验收服务时即使产品测试全绿也会失败。

## 冻结实现

- Marker：住宿“住”与景点“游”使用不同形状/颜色；选中态另加高对比边框和勾选；显示住宿、景点、已选中图例。地图、列表和提交继续共用 `location_id`。
- 保存：`updateTrip` 成功立即写入 session；API client 接入既有 GET session；revision 冲突最多读取一次，且仅在远端 trip 与本次值相同、selection 为空或相同时自动继续。
- 冲突：最新 selection 与当前选择不同则同步 session、停止写入，并要求用户重新确认；不得静默覆盖。
- 并发：同步 ref 锁阻止快速重复点击产生两条保存链。
- 反馈：按钮附近展示保存中、同步恢复和人话错误；内部错误码只能放在默认折叠的安全技术详情中。
- 前置校验：2–7 日、住宿、地点关系、偏好日和预计时长在请求前给出具体错误。

## 不变量

- 不修改后端、数据库、依赖、确定性地点/路线/排程/可行性和 DeepSeek 边界。
- legacy/V2/V3/V4、replan、F-011 时间轴和 narrative-only retry 保持兼容。
- 不读取秘密，不加载真实地图，不调用任何真实 Provider，不写浏览器持久存储。

## 允许文件

- 前端生产：`F009Map.tsx`、`F009Planner.tsx`、`f009Api.ts`、`styles.css`。
- 相邻前端测试；合成地图 loader 仅在必要时。
- 本任务治理文档与 `output/f012/` 证据。
- 恢复扩展：`scripts/run-local.ps1`、相邻 runner 合同测试和 `frontend/vite.config.ts` 的动态 loopback 代理端口接线；不得停止或接管既有服务。

## 额度与验收

- 修复—复验最多 2 轮；RED 1 次；GREEN 最多 2 次。
- typecheck、lint、build 的既有结果保留；Development 门禁累计 2 次，旧失败与新增恢复门禁分别留证。
- loopback synthetic 浏览器 1 批，桌面和 390px 各 1 次。
- 恢复新增：动态端口根因修复 1 轮、runner 定向验证 1 次、Development 门禁 1 次、最终 documentation contracts 1 次；旧失败证据不重置。
- 离线完成需定向、静态、完整门禁与浏览器批次全绿，保护对象不变，外部调用为 0。
- 最终结论最多为 `PASS / OFFLINE`；真实手工复验保持 `NOT_EXECUTED`。

## 停止条件

无法识别安全恢复、需要覆盖最新 selection、需要后端或 legacy 改动、发生非 loopback 请求、需要秘密/新依赖/范围外文件、保护散列变化、验证额度耗尽或需要 Git/破坏性操作时立即停止。

## 最终验证结果

- RED 1/1：15 项中新增 6 项按预期失败，覆盖 GET session、Marker 语义、部分保存、冲突恢复、并发锁和本地反馈。
- GREEN 2/2：最终 3 文件、15 测试通过；typecheck 与 build 通过。独立 lint 首次发现未使用 catch 变量，最小修正后已由 Development 门禁内 lint 通过复验。
- 首次 Development 1/1：后端全量、前端全量、前端 build、格式、lint 和 typecheck 均通过；Documentation checker tests 因本地 runner 固定端口 8000/5173 被既有用户服务占用而停止，证据保留于 `output/f012/20260914-195716-blocked/`。
- 恢复修复 1/1：runner 默认分配互不相同的动态 loopback 端口，显式端口仍严格拒绝冲突，Vite 代理只读取本进程注入端口；相邻合同测试 5/5 通过。
- 恢复 Development 1/1 完整通过：后端/前端全量、format、lint、typecheck、build、文档检查器和仓库合同均为 PASS。
- synthetic 浏览器 1/1：桌面与 390px 各 1 次；保存按钮一次点击进入空间预检，revision `0 -> 1`，未出现 `selection_revision_conflict`；控制台 0 error/0 warning，网络仅 loopback，localStorage/sessionStorage 均为空，390px 无横向溢出。
- F-008 至 F-011 共 537 个保护对象复核 0 mismatch；真实地图、高德、DeepSeek、和风调用均为 0。最终结论为 `PASS / OFFLINE`，真实 UAT 保持 `NOT_EXECUTED / NOT_AUTHORIZED`。
