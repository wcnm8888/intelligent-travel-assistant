# F-001：单城市双日旅行计划垂直切片（归档）

## 归档元数据

- 任务等级：`L`
- 交付状态：`DELIVERED`
- 产品验收状态：`PARTIAL`
- 归档 Step：`Step 47`
- 主线合并提交：`d05e997dbeaa676702704ce791287eb036c80a6c`
- PR 顺序：[PR #5](https://github.com/wcnm8888/intelligent-travel-assistant/pull/5) → 功能分支 → [PR #4](https://github.com/wcnm8888/intelligent-travel-assistant/pull/4) → `main`

## 目标与范围

交付一个仅本地运行的中国大陆单城市双日旅行决策辅助垂直切片：接收日期、预算、偏好、交通和住宿要求，组合 DeepSeek、高德和和风天气的受控事实，生成带来源、时效、不确定性和确定性校验的结构化计划。

范围包括单编排 Agent、五种终态、进程内任务 Repository、FastAPI 任务 API、React Web UI、三家 provider adapter、离线 fake、确定性路线/时间/预算校验和受控真实 UAT。范围不包括自动预订、支付、库存、登录、多 Agent、公网部署、复杂地图、图片和 PDF。

## 关键交付结论

- D-009 已实施：LLM 负责 POI 选择、优先级、顺序建议和解释；确定性代码使用实际路线、固定时长和交通缓冲生成最终时间；
- Step 45T 真实 UAT `PASS`：唯一杭州双日任务形成完整可执行 `partial`，仅存在非关键 unknown 费用；
- Step 45M 历史真实 UAT `FAIL` 保留，不能被后续 PASS 覆盖；
- 门票等费用继续为 `unknown`，不得按 0 计入；混合交通 fallback 由离线纵向测试覆盖，但没有宣称真实质量已覆盖；
- PR #5 先合并至功能分支，PR #4 经独立 review 和 Windows CI 复验后合并至 `main`；main CI run `31881327869` 成功；
- F-001 已交付，但产品状态保持 `PARTIAL`，不等同于所有费用和所有 provider 分支均达到 `ready`。

## 证据入口

- 当前归档状态：[current-task.md](../../project-management/current-task.md)
- 进度：[progress.md](../../project-management/progress.md)
- 验收证据：[evidence.md](../../project-management/evidence.md)
- 路线图：[roadmap.md](../../project-management/roadmap.md)
- D-009 变更卡：[f-001-cr1-deterministic-scheduling.md](../../project-management/f-001-cr1-deterministic-scheduling.md)

后续任何 live 调用、门票价格能力、混合 fallback 真实质量扩展或产品范围变化，都必须从 roadmap 重新选择任务并取得单独批准。
