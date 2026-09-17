# F-017 旅行顾问对话体验与上下文连续性

## 状态

`DONE / IMPLEMENTED / PASS / OFFLINE`

## 业务结果

把地图上方的工程化顾问表单重构为地图旁可折叠的共同规划抽屉，让旅客看见“我说了什么、顾问理解了什么、哪些建议等待确认”，同时保持地点、路线、时间和可行性只由现有确定性合同决定。

## 冻结范围

- 桌面端采用地点列表、地图、顾问抽屉三栏工作区；抽屉可折叠，地图仍是主要空间画布。
- 390px 下改为单栏可折叠顾问区，不遮挡地点列表和地图控制。
- 顾问快照新增最多 12 条有界对话投影；DeepSeek 只接收最近上下文、已确认偏好和已验证候选索引。
- 提供快捷回答、已确认偏好的人话标签、偏好调整入口、偏好建议与地点建议的清晰类型区分。
- 结果页把受约束文字明确标为“旅行顾问建议”，与确定性地点、路线和时间分层展示。
- 不新增 Provider、依赖、数据库、浏览器持久化、自治多 Agent 或第二条规划流程。

## Step

| Step | 目标 | 状态 |
| --- | --- | --- |
| Step 1 | 治理、基线与严格会话合同 | DONE |
| Step 2 | 顾问抽屉和结果页信息分层 | DONE |
| Step 3 | 离线定向验证、浏览器设计 QA 与收口 | DONE |

定向结果：后端 11 项通过；前端 14 项通过；Ruff 与 TypeScript 检查通过。首个 TypeScript 字面量推断失败已在 F-017 新测试内完成 1 次最小修复并复验通过。

首次 Development 的所有代码子门禁通过，最终文档合同失败；修复 Step 投影后独立文档检查通过。首次 desktop synthetic 完成完整产品路径，但脚本在结果页检查选点页文本而失败；截图另发现三栏 class 误放目的地页。两处已最小修正。用户已批准恢复额度：synthetic 重新构建 1 次、desktop/390px 浏览器验收 1 批、新 Development 门禁 1 次、最终 documentation contracts 1 次；必须顺序执行且失败即停止。

恢复构建 `1/1` 通过。恢复浏览器批次 `2/2` 在 desktop 加载验收脚本时失败：`SyntaxError: Unexpected token ';'`；产品旅程未开始，390px 未启动。依照失败即停止，未诊断或修复脚本，Development 恢复额度与最终 documentation contracts 均未消费。

用户随后授权完成任务卡所需恢复。对照已成功运行的相邻 F-016 脚本，确认 `playwright-cli run-code --filename` 所需函数表达式末尾不能包含额外分号；仅删除该分号并执行新的 synthetic 浏览器批次，不重新构建。

新的 synthetic 浏览器批次 `3/3` 已通过：desktop 与 390px 各完成一次完整旅程。对话、已确认偏好、抽屉折叠/恢复、三地点完整安排、两日地图和 narrative-only retry 均通过；控制台错误、浏览器存储、横向溢出和非 loopback 请求均为 0。

第二次 Development 在完整后端测试和前端 format/lint 通过后停止于 Frontend typecheck：命令 exit 0、无错误位置，但验证器给出 `explicit_error=true`。直接 typecheck 复验 exit 0；根因为 Windows PowerShell 将正常原生 stderr 包装并按终端宽度换行，使 `RemoteException` 的后半段误中行首错误正则。验证器改为先提取 `ErrorRecord.Exception.Message` 再应用同一错误策略，并新增正常 stderr 的通过自检。

首次运行更新后的 gate self-test 时，旧 `zero-error` 夹具的嵌套 PowerShell 引号在当前终端进入交互提示，已立即终止。夹具机械改为无交互的 `cmd.exe /d /c` 固定输出，覆盖范围不变。

更新后的 gate self-test 最终通过，确认非零退出、显式错误、超时和诊断样例仍 fail closed，正常 stderr 不再误报。第三次 Development 完整通过 readiness、依赖、后端 format/lint/typecheck/全量测试、前端 format/CI format/lint/typecheck/全量测试/build、文档检查器测试和仓库合同。设计 QA 对照 desktop 与 390px 截图通过，无 P0/P1/P2 遗留。

## 最终额度与结论

- 根因修复：`2/2`；后端定向：`1/2`；前端定向：`2/2`。
- synthetic 重新构建：`1/1`；synthetic 浏览器：累计 `3/3`，最终批 desktop 与 390px 均通过。
- 浏览器脚本解析诊断/修复：`1/1`、`1/1`；验证器误报修复：`1/1`。
- Development：累计 `3/3`，最终一次完整通过；最终 documentation contracts：`1/1`。
- 真实地图、高德、DeepSeek、和风调用均为 0；真实 UAT 保持 `NOT_EXECUTED / NOT_AUTHORIZED`。
- 未执行 stage、commit、push、PR、CI、merge、stash、reset、clean 或 remote 修改。

## 验证与额度

- 同根因修复最多 2 轮；保留首次失败，不以改目录重置计数。
- 后端与前端定向验证最多各 2 次。
- 完整 Development 门禁累计 2 次（首次已消费，恢复批次 1 次待执行）。
- synthetic 浏览器验收累计 2 批（首次失败已保留，恢复批次 desktop 1 次、390px 1 次待执行）。
- synthetic 恢复构建 1 次。
- 最终 documentation contracts 1 次。
- 真实地图、高德、DeepSeek、和风调用全部为 0。

## 完成条件

1. 顾问区不再把地图整体向下推移；折叠和移动端状态可键盘操作。
2. 对话历史、当前问题、快捷回答、已确认偏好和待确认建议均可理解。
3. 重复 `client_request_id` 不重复追加对话；历史最多 12 条，旧 revision 在模型调用前拒绝。
4. 未确认地点不能进入 selection、solver、Prompt 允许集合或结果。
5. 结果页清楚区分确定性事实与旅行顾问建议。
6. 定向测试、Development、desktop/390px synthetic 和设计 QA 通过；网络仅 loopback。
7. 最终只能记为 `PASS / OFFLINE`；真实 UAT 保持 `NOT_EXECUTED / NOT_AUTHORIZED`。

## 停止条件

需要真实 Provider、读取秘密、新依赖、数据库或浏览器持久化、修改确定性 solver/路线事实、覆盖既有 dirty 内容、删除旧证据、第二个 ACTIVE 任务、非 loopback 请求或 Git 交付时立即停止。
