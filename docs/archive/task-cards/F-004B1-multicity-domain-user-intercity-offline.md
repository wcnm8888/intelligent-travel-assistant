# F-004B1 多城市领域、用户提供的城际段与离线约束

## 任务元数据

- 任务：`F-004B1 多城市领域、用户提供的城际段与离线约束`
- 等级：`L`
- 状态：`DELIVERED / ARCHIVED`
- 执行日期：2026-08-20
- Step 0–8：全部 `DONE`
- 功能 main 提交：`c1fecb0e5545a25330aa179e7f25decd58c07139`
- 完整功能 main CI：run `32384768085`，`PASS`

## 用户目标与交付价值

用户可以为中国大陆境内 2–3 个按顺序排列的城市，表达每城住宿、连续住宿夜数、相邻城市间由用户提供的城际段、逐日窗口和预算，并获得可离线保存、重启恢复、可追溯且不承诺实时票务的结构化计划。

工程上以独立 version 3 typed 变体扩展多城市能力，复用现有确定性排程、Repository port、SQLite schema v2 typed JSON、来源、费用可信状态和五种终态，同时保持 legacy/V2 行为、指纹、已保存数据和 F-003/F-004A replan 边界兼容。

## 已交付产品范围

- 支持 2–3 个有序、唯一的中国大陆城市，总行程连续 3–7 日，每城至少住宿一晚；
- 每城具有独立住宿锚点，住宿夜数总和精确等于总日数减一；
- 相邻城市间恰有 `city_count - 1` 个用户提供段，只允许 `rail`、`air`、`coach`；
- 城际段包含相邻出发/到达城市、站点、同日 `+08:00` 时间、方式和可选用户票价；
- 同一自然日最多一次跨城，转移日最多一项活动；不支持跨夜、第三城市、联程中转、自驾或重复首城闭环；
- 铁路、航空、长途客运使用固定出发前/到达后缓冲，活动和市内路线必须落在安全窗口内；
- 用户票价标为 `user_provided`；未提供票价保持 `unknown`/`null`，不得写成 0；
- 用户输入不伪造 Provider attribution、freshness、availability、库存、可预订性、支付或出票能力；
- 继续使用 `ready/partial/conflict/needs_input/failed` 终态，unknown/freshness 缺口不得提升为 ready。

## Contracts、API、Repository 与兼容

- 新增严格 `TripPlanRequestV3`、`TripPlanV3`、`TripPlanResponseV3` 及城市停留、城际段、转移日和来源 DTO；
- legacy/V2/V3 通过严格 tagged union 判别；未知、模糊或额外字段 fail closed；
- 继续复用 POST/GET/retry/DELETE URI，按持久化请求版本投影严格响应；
- legacy/V2 JSON 形状及 canonical fingerprint 保持不变，V3 使用独立 fingerprint；
- `PlanningJobRepository` 方法集合不变，typed request/result union 显式增加 V3；
- 内存和 SQLite adapter 可 round-trip V3 request/result/source，继续使用 schema version 2 typed JSON；
- 没有 migration v3、新列、索引、关系实体或依赖变更；旧应用读取 V3 只会 fail closed；
- 全部 V3 replan 在 reserve、Provider、decision、lineage 和 plan version 写入前以稳定 scope 错误拒绝。

## 离线 planning 与调用治理

- 新增 provider-neutral 多城市编排器，按城市复用现有城市解析、POI、天气、模型和市内路线 ports；
- 一个全局 proposal 后由确定性代码注入城市连续性、用户城际段、缓冲、市内路线、活动时间、预算、来源和终态；
- 调用上限：resolve ≤ C、POI ≤ 3C、forecast/alert ≤ C、generation/repair 各 1、route ≤ `min(28,4D)`；
- 城市事实与 route 并发均为 2，任务总 deadline 为 180 秒；取消会 drain 在途 peer；
- repair 只接收安全诊断和脱敏结构上下文，不接收原始模型输出、自由文本、兴趣、硬约束或用户城际段原文；
- 城际 Provider 调用恒为 0；没有新增 Provider、真实 Provider UAT 或非 loopback 访问。

## 前端与离线恢复

- 默认保持单城市；用户显式选择后进入 2/3 城市卡、住宿/夜数和相邻段编辑；
- 城市顺序通过有可访问名称的上移/下移按钮控制，排序后相邻段清空并由 live region 披露；
- 严格 V3 parser 校验城市/日期/段/地点/source 引用和终态形状；任何 tag 或引用漂移 fail closed；
- 结果按日显示住宿城市、转移日、用户城际段、缓冲、市内路线、费用可信状态、来源和 partial/unknown；
- V3 不显示 replan 控件；修改需创建新任务；
- 本机 `localStorage` 只保存 job UUID，刷新/重启通过同源 GET 从 SQLite 读取权威快照；不保存请求、站点、时间、票价、Prompt 或 Provider 数据；
- desktop `1440×1000` 与 `390×844`、键盘、焦点恢复、可访问名称、无横向溢出和 console/network 隔离均通过。

## 数据与隐私边界

- SQLite 只保存 allowlist typed JSON、必要地点/路线/预算/天气、用户提供城际字段和既有来源元数据；
- 不保存 Key、Token、JWT、私钥、Cookie、Authorization、完整 Prompt、Provider 原始响应、原始错误 body、票号、订单号、证件或联系方式；
- 保留单计划 DELETE、30 天 `expires_at` 和启动有界清理；
- 全任务未读取 `.env.local`、秘密或本地 Provider 配置，未调用 DeepSeek、高德、和风或城际 Provider；
- 临时 SQLite 与 loopback synthetic 会话均在验证后按精确路径/进程清理。

## Step 结果

| Step | 结果 | 状态 |
| --- | --- | --- |
| 0 | 事实复核、任务激活、治理、状态漂移修正和首层分支 | DONE |
| 1 | 冻结 V3 领域/API/Repository/Provider/UI/测试设计 | DONE |
| 2 | TDD 实现纯多城市领域和独立 V3 contracts | DONE |
| 3 | V3 unions、Repository/SQLite schema v2、同 URI API 与 replan 写前拒绝 | DONE |
| 4 | 离线多城市 planning 与调用治理 | DONE |
| 5 | 前端多城市交互、严格解析与离线恢复 | DONE |
| 6 | 临时 SQLite、loopback desktop/390px QA 与独立隐私兼容审查 | DONE |
| 7 | 全量门禁、四层 stacked PR、review 与远程 CI | DONE |
| 8 | clean-restack、依序合并、main CI、归档和任务关闭 | DONE |

## 验证证据

- 最终本地统一门禁：Ruff format/lint、strict mypy 134 files、backend `1166 passed`、frontend `10 files / 95 passed`、Prettier、ESLint、TypeScript、Vite build、文档检查器 `24 passed` 与 repository contracts 全部通过；
- 临时 SQLite 覆盖 create/read/restart/retry/delete、幂等、2/3 城、五终态和 V3 replan 拒绝；
- loopback 浏览器覆盖 desktop/390px、刷新恢复、键盘焦点、横向 overflow 0、console error/warning 0、无效 ARIA 引用 0，58 条请求全部为 `127.0.0.1`；
- 独立隐私/兼容审查覆盖 36 个生产文件和 6 个信任面，coverage complete、finding 0；TAC advisory 因 connector 未登录保持未验证；
- 四层生产/测试净新增分别为 1679、1393、2120、2497，累计 7689，均在批准阈值内；
- 没有 Schema/migration、依赖/lockfile、秘密或城际 Provider 文件变化。

## GitHub 交付与 clean-restack

- Stack 1：PR #19，CI `32379371761`，squash merge `9f37e4f81f19da42003592fef43f80c01ce5b629`，main CI `32381619737`；
- Stack 2：原 PR #20 在父层 squash 后由 clean-restacked PR #23 替代并关闭；#23 CI `32382212012`，squash merge `712fd516358c80f1aa9a46aae3a0d88b2d9248f8`，main CI `32382625338`；
- Stack 3：原 PR #21 由 clean-restacked PR #24 替代并关闭；#24 CI `32383225699`，squash merge `ec499fb25151955aeca8805771edd2b594fd861d`，main CI `32383721748`；
- Stack 4：原 PR #22 由 clean-restacked PR #25 替代并关闭；#25 CI `32384318796`，squash merge `c1fecb0e5545a25330aa179e7f25decd58c07139`，完整功能 main CI `32384768085`；
- 所有替代 PR 都从最新 main 创建，只 cherry-pick 所属层净提交；没有 amend、rebase、force-push、历史删除或失败隐藏；
- Step 7 首轮 #19/#20 CI failures `32377941830`/`32378099288` 继续保留在 evidence，修正后才进入合并。

## 保留边界与非目标

- F-001 产品状态保持 `PARTIAL`；Step 45M 真实 `FAIL` 与 Step 45T 真实 `PASS` 均保留；
- 门票和未提供城际票价等非关键费用保持 `unknown`，不按 0 处理；
- 混合交通 fallback 仍只有离线证据；F-004A 与 F-004B1 均没有真实 Provider UAT；
- 不包含真实城际 Provider、实时班次/票价/余票、预订/支付/出票、自驾、跨夜、境外、版本恢复、登录/同步、云数据库、公网部署、复杂地图、图片或 PDF；
- F-005 与 F-004B2 仍是候选任务，不因本任务完成而自动启动。
