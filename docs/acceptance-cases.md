# F-001 验收样例

## 文档状态

本文件是 F-001 固定验收场景的唯一说明。机器可读数据位于 `backend/tests/fixtures/synthetic_hangzhou_*.json`，全部是手工构造、无网络、无真实凭证的 synthetic 数据，只用于验证项目契约和后续行为，不能作为 DeepSeek、高德或和风天气真实可用性的证据。

## 固定上下文

| 字段 | 值 |
| --- | --- |
| 固定当前时间 | `2026-08-13T10:00:00+08:00` |
| 时区 | `Asia/Shanghai` |
| 城市 | 杭州 |
| 日期 | 2026-08-15 至 2026-08-16，即 D+2/D+3 |
| 人数 | 2 |
| 总预算 | 4000 元 |
| 偏好 | 自然、历史、均衡节奏 |
| 交通 | 步行和公共交通 |
| 住宿 | 西湖附近，一晚费用由用户提供 700 元 |
| 城际往返 | 用户提供 1000 元 |
| 餐饮 | 用户可改，当前使用默认 100 元/人/天，共 400 元 |

共享请求：[synthetic_hangzhou_request.json](../backend/tests/fixtures/synthetic_hangzhou_request.json)

固定时钟只用于测试动态日期边界，不能被产品代码写死。

## Case 1：ready

文件：[synthetic_hangzhou_ready.json](../backend/tests/fixtures/synthetic_hangzhou_ready.json)

- 预期状态：`ready`；
- 计划存在且包含连续两天；
- 两天均有 synthetic POI、路线和天气；
- 已知费用 2140 元，未知费用 0，预算判断为 `within_budget`；
- 住宿和城际费用是 `user_provided`；餐饮和公交是 `estimated`；
- 零元门票只是本样例选择的规则结果，不代表高德提供实时票价或景点长期免费；
- 所有外部记录都带 synthetic 警告和来源 ID；不包含 provider URL。

禁止行为：不能显示实时库存、可预订或已验证酒店价格；不能把该样例当成真实天气、路线、开放状态或价格证据。

## Case 2：partial

文件：[synthetic_hangzhou_partial.json](../backend/tests/fixtures/synthetic_hangzhou_partial.json)

- 预期状态：`partial`，保留可用双日候选计划；
- synthetic 高德路线超时，因此路线列表为空，不能宣称交通时间已验证；
- 第二天天气缺失，不能宣称未来两天天气或预警完整；
- 门票为 `unknown`、金额为空；已知费用 2100 元，预算状态为 `budget_indeterminate`；
- 同时显示 `provider_timeout`、`budget_incomplete`、路线和天气不确定性；
- 由于路线超时可恢复，任务整体 `retryable=true`。

禁止行为：不能显示“路线已验证”“预算充足”或“未来两天无预警”；不能把未知门票显示为 0 元。

## Case 3：conflict

文件：[synthetic_hangzhou_conflict.json](../backend/tests/fixtures/synthetic_hangzhou_conflict.json)

- 预期状态：`conflict`；
- synthetic 用户住宿输入被设为 3100 元，使已知总费用达到 4500 元；
- 用户预算仍为 4000 元，预算状态必须为 `over_budget`；
- 返回 `known_cost_exceeds_budget` 硬违规和 `constraint_conflict`；
- 可以保留候选计划供解释，但不能宣称已经通过；
- `retryable=false`，用户必须修改输入，而不是重复同一调用。

禁止行为：不能自动放宽预算、隐藏超支或让 LLM 删除代码产生的冲突。

## Case 4：failed

文件：[synthetic_hangzhou_failed.json](../backend/tests/fixtures/synthetic_hangzhou_failed.json)

- 预期状态：`failed`；
- 城市已有 synthetic 解析结果，但 synthetic DeepSeek 规划能力不可用；
- `plan=null`，不返回伪计划；
- 返回安全的 `provider_unavailable`，provider 为 `deepseek`；
- 错误不包含原始响应、堆栈或凭证；
- 暂时不可用可恢复，因此 `retryable=true`。

禁止行为：不能自动换用未批准模型、用模板冒充计划，或向用户展示 provider 原始错误。

## Case 5：needs_input

文件：[synthetic_hangzhou_needs_input.json](../backend/tests/fixtures/synthetic_hangzhou_needs_input.json)

- 预期状态：`needs_input`；
- synthetic 住宿区域“西湖附近”在该场景中无法唯一定位，需要用户给出更具体区域或 POI；
- `plan=null`、`retryable=false`，不能盲目重试同一输入；
- 返回稳定 `input_invalid`，field 指向 `accommodation.area_or_poi`；
- 不调用高德、和风或 DeepSeek，也不自动选择住宿位置。

禁止行为：不能宣称已生成计划、已自动选择住宿或住宿位置已经确认。

## 机器验证

`backend/tests/test_acceptance_fixtures.py` 验证：

- 共享请求和五个 case 都通过 Step 3 严格 Schema；
- fixed clock 与 D+1 至 D+5 日期边界一致；
- 状态、是否有计划、retryable、费用合计、未知数、错误和不确定性符合预期；
- 每个被引用的来源 ID 都存在；
- 每个住宿、活动、路线和天气地点 ID 都能在计划地点目录中解析；
- fixture 目录只包含批准的六个 `synthetic_*.json`；
- 文件不包含 URL、API Key 或私钥标记。

这些测试只证明验收语言和数据契约稳定，不证明规划算法正确或真实 provider 可用。真实证据只能在 Step 38 经用户单独批准后产生。
