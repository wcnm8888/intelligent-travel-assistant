# F-011 旅行约束易用化、结果页重构与模型说明恢复

## 当前状态

- 状态：`DONE / IMPLEMENTED / PASS / OFFLINE`
- 当前 Step：`Step 1 - Slice A–E 实现、验证与离线收口（DONE）`
- 基线：`output/f011/20260914-152229-baseline/`
- 长期决策：D-033
- 真实地图与 Provider UAT：`NOT_EXECUTED / NOT_AUTHORIZED`
- Git 交付：`NOT_AUTHORIZED`

## 业务目标

让普通用户通过地点名称表达二选一或一起游览关系，以自然语言选择住宿方式，并在时间轴结果中清楚看到住宿出发、活动、交通和返回住宿。模型说明失败只显示不影响计划的人话提示；用户可在不重算事实的前提下单独重试 AI 游览提示。

## 冻结切片

1. 地点关系易用化：内部 group ID 由前端确定性生成且不展示。
2. 住宿输入易用化：主选项为“大概区域 / 已确定酒店 / 地图上选择”。
3. 结果页重构：单一编号、按日时间轴、交通穿插、距离友好格式和地图失败完整列表。
4. 模型说明分层：人话优先，闭集技术诊断默认折叠。
5. narrative-only retry：V5 内存 job 上的独立幂等 action；DeepSeek generation 1 次、repair 最多 1 次，不触发其他 Provider 或确定性重算。

## 不变量

- 日期、地点、顺序、时间、路线、可行性和 MapPlan 仍由确定性程序拥有。
- legacy/V2/V3/V4、replan、SQLite Schema 和 migration 不变。
- 不新增依赖，不读取秘密，不调用真实 Provider，不加载真实地图。
- Provider 派生数据和模型原始输出不写 SQLite、浏览器持久存储、日志或文档。
- F-008/F-009/F-010 归档结论和证据保持只读。

## 验收

1. 用户不输入或看到 group ID，单成员、跨组、关系与优先级冲突在提交前被阻止。
2. 住宿主界面只使用用户语言，提交 DTO 保持兼容。
3. 结果页无重复编号，路线段正确穿插，住宿首尾和距离清楚可读。
4. `partial` 和内部模型诊断不在普通摘要出现，技术详情默认折叠。
5. narrative retry 不搜索 POI、不逆地理、不计算路线、不运行 solver/preflight，不改变确定性计划或 MapPlan。
6. 定向前后端测试、一次 Development 门禁和一批 loopback synthetic 浏览器验收在批准额度内通过。
7. 最终只能记为 `PASS / OFFLINE`；真实 UAT 保持未执行、未授权。

## 额度

- 同根因修复—复验：最多 2 轮。
- 前端定向测试：最多 2 次；后端定向测试：最多 2 次。
- 完整 Development 门禁：1 次。
- synthetic 浏览器：1 批，桌面 1 次、390px 1 次。
- 真实地图、高德、DeepSeek、和风 logical/HTTP：全部 0。

## 停止条件

需要秘密、真实 Provider、非 loopback 网络、新依赖、数据库变化、确定性事实改写、范围外文件、历史证据变化、Git 交付或超过任一额度时立即停止。

## Development 门禁阻塞

- 唯一 Development 门禁已于 2026-09-14 消费 `1/1`，在 `Frontend tests` 子门禁以 exit code 1、`explicit_error=true` 失败；门禁没有保留具体失败测试名。
- 失败前 readiness、运行时版本、依赖与锁、后端 format/lint/mypy/全量测试，以及前端 format、CI workflow format、lint、typecheck 均通过。
- 依照冻结停止规则，未修复、未重跑、未执行前端 build、文档检查器测试、仓库文档合同或最终 documentation contracts。
- `.env.local` 仅按存在性同卷临时改名，内容未读取；`finally` 已恢复原名，临时 hold 残留为 0。
- 阻塞证据：`output/f011/20260914-161507-closeout/`。F-011 不得标记为 `PASS / OFFLINE`；后续诊断、修复和新门禁额度均需独立授权。

## Step 1R 恢复授权

- 用户已授权：离线前端失败诊断 `1` 次、F-011 前端职责内修复 `1` 轮、修复后前端定向验证 `1` 次、新 Development 门禁 `1` 次、最终 documentation contracts `1` 次。
- 新增额度为 0：后端测试、synthetic 浏览器、真实地图以及高德、DeepSeek、和风 logical/HTTP 调用。
- 允许修改仅限 `F009Planner.tsx/test`、`F009Map.tsx/test`、`styles.css`、`f009Api.ts/test`，以及任务状态和证据文档；若根因落在其他业务文件立即停止。
- 恢复证据目录：`output/f011/20260914-163117-recovery/`。旧门禁失败证据保持只读，不重置或改写原 `1/1`。

## Step 1R 诊断结果

- 唯一离线前端诊断 `1/1` 已消费：16 个测试文件中 14 通过、2 失败；170 项中 168 通过、2 失败。
- 范围内失败：`frontend/src/F009Planner.test.tsx` 的完整离线旅程超过 Vitest 默认 5000 ms。
- 范围外失败：`frontend/src/multicityPlanning.red.test.tsx` 的 V3 提交流程同样超过 5000 ms。
- 当前只能提出待验证假设：并发全套运行下两条长流程共同触及默认超时；现有证据不足以决定优化单个 F-011 测试、调整全局 Vitest timeout，还是修改 V3 测试。
- 因第二个失败职责不在恢复授权内，修复 `0/1`、前端定向验证 `0/1`、新 Development 门禁 `0/1`、最终文档合同 `0/1` 均保持未消费并停止执行。

## Step 1R 根因隔离授权

- 新增根因隔离批次 `1` 个：按顺序单独运行 `F009Planner.test.tsx` 和 `multicityPlanning.red.test.tsx` 各 `1` 次；不得并发或追加第三次运行。
- 仅当本批证据确认需要时，可把 `frontend/src/multicityPlanning.red.test.tsx` 或 `frontend/vite.config.ts` 纳入既有唯一修复轮次；不得因此增加修复次数。
- 保留未消费额度：修复 `0/1`、前端定向验证 `0/1`、新 Development 门禁 `0/1`、最终 documentation contracts `0/1`。
- 后端测试、浏览器、真实地图及所有 Provider 调用新增额度仍为 `0`。

## Step 1R 根因确认与修复

- 隔离批次 `1/1` 已消费；`F009Planner.test.tsx` 单跑 1/1 通过（用例 2019 ms），`multicityPlanning.red.test.tsx` 单跑 8/8 通过（最慢用例 1863 ms）。
- 根因确认为全套并发 jsdom 负载使两条长流程触及 Vitest 默认 5000 ms 测试超时，而非产品断言或业务合同失败。
- 唯一修复 `1/1` 已消费：在 `frontend/vite.config.ts` 明确设置 `testTimeout: 10_000`；产品代码、断言和 Provider 边界均未改变。
- 修复后前端定向验证 `1/1` 已消费并通过：2 文件、9 测试全部通过；最慢用例 2255 ms，环境 hold 残留 0。
- 下一项仅为新增 Development 门禁 `1/1`；失败即停止，不自动修复或重跑。
- 首次门禁调用在 readiness 预检因状态词不属于既有闭集而拒绝，明确未创建正式批次；因此新增 Development 门禁仍为 `0/1`。权威状态已改为检查器接受的 `ACTIVE / IMPLEMENTATION_AUTHORIZED / OFFLINE_ONLY`。

## Step 1R Development 门禁结果

- 新增 Development 门禁 `1/1` 已消费：readiness、后端 lock/sync/format/lint/typecheck/tests、前端 install/peer/format/lint/typecheck/tests/build、文档检查器测试均通过。
- 最后一个 `Documentation and repository contracts` 子门禁 exit 1；门禁安全摘要未保留具体合同条目，故不能猜测根因。
- `.env.local` 已恢复，hold 残留 0；真实地图和所有 Provider 调用为 0。
- 依照失败即停止，最终 documentation contracts `0/1` 未执行，也未进行新诊断、修复或重跑。F-011 保持阻塞，真实 UAT 仍未执行、未授权。

## Step 1C 完成授权

- 用户已批准完成当前任务卡所需的必要本地授权；本 Step 仅用于取得文档合同具体失败、最小修复、定向验证、一个新 Development 门禁和最终文档合同。
- 有界额度：文档合同诊断 1 次、同根因文档修复最多 2 轮、定向文档验证最多 2 次、新 Development 门禁 1 次、状态更新后的最终文档合同 1 次。
- 不新增前后端定向测试或浏览器额度；真实地图和 Provider 调用仍为 0；不启动服务、不新增依赖/数据库变化、不执行 Git 交付。
- 文档合同诊断 `1/1` 已消费：仅有两个问题，均因状态投影使用检查器不支持的 `Step 1C`。最小修复 `1/2` 将当前 Step 恢复为正式数字 `Step 1`，不修改检查器。
- 修复后定向文档合同验证 `1/2` 已通过：17 份必需文档、35 个 Markdown 文件以及 CI、状态和安全合同有效。下一项为新 Development 门禁 `1/1`。

## 最终离线结论

- 完整 Development 门禁 `1/1` 通过：后端与前端全量测试、格式、lint、typecheck、前端 build、文档检查器测试及仓库文档合同均通过。
- Slice A–E 的既有定向与 synthetic 浏览器证据保持有效；没有新增浏览器批次或前后端定向测试。
- F-008/F-009/F-010 保护对象保持，真实地图和 Provider 调用为 0；真实 UAT 仍为 `NOT_EXECUTED / NOT_AUTHORIZED`。
- 结论为 `DONE / IMPLEMENTED / PASS / OFFLINE`；Git 交付未授权、未执行。
- 状态更新后的唯一 documentation contracts `1/1` 通过：17 份必需文档、35 个 Markdown 文件及 CI、状态、安全合同有效。
