# 项目进度

## 当前状态

- 当前任务：无
- 最近完成：`F-004A 单城市 2–7 日计划扩展`
- 任务状态：`DELIVERED / ARCHIVED`
- Step 状态：Step 0–7 全部 `DONE`
- 交付 PR：#13、#16、#17；#14/#15 被 clean-restacked PR 替代并关闭
- 完整功能 main：`583e9da34b0d45e84a65da620cbb5d5fa8330a3c`
- main CI：run `32359762190`=`PASS`
- 下一动作：等待用户从 roadmap 选择并批准下一任务卡

## Step 7 本地交付门禁

- 用户已批准修复 Step 7 范围内缺陷、复跑门禁和 UAT，并继续三层 stacked PR、CI、依序合并及归档；只有真正越过冻结边界时暂停；
- 修复并锁定 3–7 日 replan 在任何 reservation/decision/executor 写入前拒绝、proposal priority 顺序、V2 日数文案、SQLite retry/source 唯一性、五终态恢复、日期导航焦点和长文本窄屏换行；
- 最终统一门禁通过：后端 `1101 passed`、前端 `88 passed`、文档检查器 `24 passed`，并通过 Ruff、strict mypy、Prettier、ESLint、TypeScript、Vite build、依赖锁和文档契约；
- loopback synthetic UAT 覆盖 3 日 ready、7 日 partial/unknown 和 2 日 V2 ready/replan；`390×844` 无水平溢出，日期跳转焦点和可访问名称正确，控制台 0 error/0 warning；
- UAT 未调用真实 Provider、未读取秘密、未创建真实业务数据库；临时 SQLite 位于系统临时目录，进程和浏览器会话已按精确 PID/会话关闭；
- 三层已依序合并；#14/#15 因层间测试依赖和 squash ancestry 由 #16/#17 clean restack 替代，无 force-push；完整功能 main CI run `32359762190` 通过，任务卡已归档。

## Step 0 完成摘要

- B-000、F-001、F-002、F-003 归档事实已核对；F-001 仍为 `PARTIAL`；
- Step 45M 真实 `FAIL`、Step 45T 真实 `PASS`、unknown 不按 0 和混合交通 fallback 仅离线证据均未改变；
- F-002/F-003 数据已位于 schema version 2；F-004A 默认不做 migration v3；
- F-004 已拆为已激活的 F-004A 和仍为候选的 F-004B；多城市与城际 Provider 不在当前任务；
- 当前双日硬编码和可复用领域/Repository/SQLite/Provider/UI 边界已完成只读审计；
- 已修正 AGENTS 应用现状、F-003 design 状态、D-011 状态和过期 Git/CI 当前指针；
- F-004A 完整任务卡、Step 0–7、停止条件、阶段化允许文件和三层 clean-restack 规则已建立；
- Step 0 只修改获批治理/长期文档，没有源码、测试、数据库、依赖、环境或前端变化；
- 未读取 `.env.local` 或秘密，未调用真实 Provider，未访问非 loopback 网络，未创建分支或远程写入。

## 当前产品与技术边界

- 单城市、连续 2–7 日、每日最多 2 项、一个住宿锚点；
- 旧双日 request/response/fingerprint/计划数据/replan 必须兼容；新请求使用严格 version 2；
- schema v2 typed JSON；无关系型新需求证据时不增加 migration；
- unknown 金额保持空，partial 不伪装 ready，天气缺日按可用性降级；
- route 上限 `min(28, 4 × day_count)`、并发 2；DeepSeek generation/repair 各 1；
- 3–7 日 replan 在 Provider/decision/version 写入前拒绝；
- 无多城市、跨夜、城际 Provider、历史/恢复、登录/同步/公网或 live UAT。

## Step 1 完成摘要

- 冻结 legacy/V2 独立类型、2–7 日日期/窗口/计划不变量、每日最多 2 项和同一住宿锚点；
- 冻结同 URI callable discriminator/tagged union、V2 request/plan/response format 标识和未知版本 422；
- 冻结 legacy synthetic fingerprint golden；Repository 方法与 schema v2 不变，按 request version typed 水合；
- 冻结 legacy/V2 两日 replan 兼容和 3–7 日在 Provider/写入前 `replan_scope_not_supported`；
- 冻结 route、POI、天气、DeepSeek 和动态总期限策略；单次 timeout 和外部服务集合不变；
- 冻结结束日期、动态窗口/日卡、日导航、2/3/7 日和 390px UI；
- 冻结领域、contracts、Repository/SQLite、API、Provider、五终态、前端、浏览器和隐私测试矩阵；
- 未修改源码、测试、Schema、migration、依赖、环境或数据库，未读取秘密、调用 Provider或联网。

## Step 6 完成摘要

- V2 2/3/7 日已通过真实 API、executor、临时 SQLite、schema v2、重启、幂等和删除纵向；V2 create/retry 调度遗漏已在用户批准的最小范围内修复；
- 桌面两日、桌面三日和 `390×844` 七日 partial 浏览器闭环通过；末日可达并聚焦，3–7 日 replan 隐藏，unknown 门票显示“金额未知”且非 `¥0`，无横向溢出和 console warning/error；
- 所有动态浏览器请求仅访问 `127.0.0.1`，无真实 Provider；临时库仅含 migration 1/2，三日为 ready、七日为 partial/unknown_count=1；
- 独立审查的唯一 P1 已修复：browser SQLite 路径必须位于系统临时目录且启动前不存在；相关负向测试、48 项回归、Ruff、strict mypy 和 diff 检查通过。

## 当前阻塞和停止条件

- 当前无技术阻塞；Step 0–7 已全部完成，F-004A 已交付归档；
- 若同 URI 的严格兼容、schema v2 水合或冻结调用预算不能成立，必须停止并重新决策；
- 已将“未列文件即停止”修正为受控相邻扩展：同层直接依赖、对应测试/fixture、机械门禁修复和五份状态文档由一次 Step 批准覆盖并留痕；
- 若需改变冻结语义、新增依赖或 migration、扩大 Provider/外部调用、读取秘密、跨 Step/stack，或未预期生产/测试文件超过 5 个，必须停止并集中确认；
- 任一 stack 超过 35 个生产/测试文件或净新增 3000 行，必须重新拆分。

## 执行治理效率修正

- 原因：F-004A 原规则把核心文件清单当作绝对白名单，Step 1 的传递依赖遗漏导致正常 contract、测试和状态收口被拆成多次逐文件授权；
- 修正：后续 Step 批准覆盖已冻结目标的直接相邻实现、对应测试/fixture、机械门禁修复和状态文档；执行时先披露路径和理由，完成时统一列证据；
- 安全边界：产品/API 语义、Schema/migration、依赖、数据隐私、真实 Provider、秘密、数据库、远程 Git、跨 Step/stack 和规模阈值仍需新授权；
- 治理修正已在 Step 4 生效：已披露的相邻组合根 `bootstrap.py` 随同一 Step 完成并在 evidence 留痕，没有产生逐文件重复授权。

## Step 5 实现摘要

- 表单支持显式结束日期、2–7 日动态日窗口、D+1 至 D+5 开始边界、1/8 日拒绝和首错焦点；用户已编辑的结束日期不会被开始日期静默覆盖；
- 未显式编辑结束日期的双日提交继续生成原 legacy DTO；显式日期范围生成 tagged V2 DTO，既有 URI、轮询、retry 和终态流程不变；
- parser 严格校验 V2 response/plan 标签、连续日期和 2–7 日结构；结果页动态展示摘要、可访问日期导航与所有日卡；
- 3–7 日不显示可执行局部调整并明确范围，V2 恰好两日保留 replan；7 日 partial 继续显示天气缺失和 unknown 金额，不显示 `¥0`；
- 统一离线门禁通过后端 1088 项、前端 87 项、文档检查器 24 项及全部 format、lint、typecheck、build；未修改后端、Schema、migration、Provider、依赖、环境或数据库，未访问真实 Provider 或非 loopback 网络。

## Step 2 实现摘要

- TDD RED：多日请求、时间计划和预算函数尚不存在，三个测试模块在收集阶段按预期失败；
- 最小 GREEN：新增独立 2–7 日请求/时间模型，基础 offset 扩到 0–6，legacy 双日模型继续严格 `{0,1}`；
- scheduler 校验并遍历 2–7 日 proposal、窗口和每日 1–2 项，住宿往返路线最多 3 段/日；
- 餐饮按人数与天数、住宿按夜数计算，unknown 保持空；final validation 遍历全部日期、路线和天气覆盖；
- 专项 136 项与后端全量 1065 项通过；format、Ruff、strict mypy、文档检查和 diff 检查通过；
- 未修改 contracts、Repository、SQLite/schema/migration、API、Provider adapter、前端、依赖、环境或数据库；未读取秘密、调用真实 Provider、创建分支或远程写入。

## Step 3 实现摘要

- 以 callable discriminator 建立 legacy/V2 request、plan 和 response 联合；legacy JSON 与指纹 golden 不变，未知版本 422；
- 内存和 SQLite Repository 在方法集合、事务与 schema v2 不变的前提下持久化并严格水合 V2 typed JSON；损坏版本或 request/plan 不匹配 fail closed；
- 同一 trip-plan URI 支持 V2 创建、GET、幂等、删除和重启恢复；V2 草稿不调用 legacy executor；3–7 日 replan 在写入前拒绝；
- 增补 V2 两日 completed replan contract，序列化保留 response/plan 两层 V2 标签；
- 聚焦测试 26 项通过；统一门禁通过后端 1073 项、前端 76 项、文档检查器 24 项及全部 format、lint、strict mypy、TypeScript 和 build；
- schema/migration、Provider adapter、前端、依赖、环境和真实数据库未变化；未读取秘密、调用真实 Provider、创建分支或远程写入。

## Step 4 实现摘要

- DeepSeek V2 proposal 使用请求版本、完整日期和动态 2–7 日规则；legacy 双日行为保持不变；
- QWeather 一次 7 日预报映射完整请求日期，缺日返回 partial 且不补拉；
- Provider executor 以 N 日窗口、POI 上限、餐饮按天和住宿按夜生成 typed `TripPlanV2`，unknown 仍为 `None`；
- governor 按请求使用冻结 route cap、并发和 deadline；3/7 日 fake 纵向证明路线调用为 `2D` 且 active calls 归零；
- 专项 403 项和统一门禁通过：后端 1088 项、前端 76 项、文档检查器 24 项，以及 format、lint、strict mypy、TypeScript 和 build；
- `bootstrap.py` 是唯一预先披露的受控相邻生产文件；未修改 API、Repository、Schema、migration、前端、依赖、环境或数据库，未读取秘密或调用真实 Provider。

## 权威入口

- 当前任务：[current-task.md](./current-task.md)
- 当前计划：[implementation-plan.md](./implementation-plan.md)
- 路线图：[roadmap.md](./roadmap.md)
- 验收证据：[evidence.md](./evidence.md)
