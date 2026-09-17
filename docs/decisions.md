# 项目决策记录

本文件保存D-001–D-030的长期技术裁决和按日期记录的决策沿革，不维护当前执行状态。当前切片、有效规模授权以 [任务卡](./project-management/current-task.md#当前执行状态) 为准；实施/批准历史与本次纠偏证据见 [evidence](./project-management/evidence.md#f008-governance-20260905)。下文旧额度/准入/“当前”表述均限定于各自记录时点，不替代任务卡现值。本轮未新增决策编号或改变技术契约。

本文件只保存长期有效的已批准决策、理由和后果。当前任务状态不在这里维护。

## D-001：采用 Python 3.13.3 和 Node.js 22.16.0 作为工程基线

- 状态：已批准
- 日期：2026-08-13
- 适用范围：B-000 及后续本地开发，直到出现新的已批准运行时决策

### 背景

初始规划建议 Python 3.12 和 Node.js 24。B-000 / Step 0 的本机审计发现：

- uv 已管理可用的 CPython 3.13.3；
- 默认 `python` 指向 CPython 3.11.0rc2，不适合作为项目基线；
- Windows `py` 启动器指向不存在的 Python 3.13 安装路径；
- 当前 Node.js 为 22.16.0；
- 本机没有 nvm、fnm 或 Volta，也没有 Node.js 24。

继续坚持 Python 3.12 和 Node.js 24 将要求下载或修改本机运行时，增加系统变更和环境漂移。

### 决策

- Python 固定为 CPython 3.13.3，并通过 uv 解析、创建环境和执行命令。
- 项目文档和脚本不依赖裸 `python` 或 Windows `py` 启动器。
- Node.js 固定为 22.16.0。
- Node 包管理通过 Corepack 固定 pnpm `11.19.0`，不依赖当前 Codex bundled runtime 的可执行路径。
- 版本约束将在 `.python-version`、`.node-version`、依赖清单、锁文件和 CI 中保持一致。

### 理由

- 两个运行时已经存在，可避免未经必要的系统安装和 PATH 修改。
- uv 可以绕开失效的 `py` 启动器和默认 Python 预发布版本。
- 固定文件与锁文件能让本地和 CI 使用相同版本边界。

### 取舍

- Python 3.13.3 比初始保守基线更新，后续选择依赖时必须验证兼容性。
- Node.js 22.16.0 不是初始建议的 Node.js 24；需要在依赖升级或官方支持边界变化时重新评估。
- 不修复系统 `py` 启动器，其他依赖它的本机项目仍可能遇到问题；该修复不属于本项目权限范围。

### 验证要求

- `uv run python --version` 必须解析为 Python 3.13.3。
- `node --version` 必须解析为 22.16.0。
- `corepack pnpm --version` 在依赖安装前必须解析为 11.19.0，且运行时 Node 必须符合 22.16.0；裸 `pnpm` 不作为项目验证入口。
- 本地统一验证和 CI 必须检查运行时版本，发现漂移时失败。
- 任何运行时升级必须更新本决策或新增后续决策记录。

### 替代方案

1. 安装 Python 3.12 和 Node.js 24：版本与初始建议一致，但会引入系统或用户级安装。
2. 使用默认 Python 3.11.0rc2：无需配置，但预发布运行时不可接受。
3. 使用 uv 的 Python 3.13.3 和现有 Node.js 22.16.0：不修改系统，已由用户批准。

## D-002：采用模块化单体、端口适配器和单编排 Agent

- 状态：已批准
- 日期：2026-08-13
- 适用范围：MVP 及后续架构，直到出现新的已批准架构决策

### 背景

项目需要组合 Web UI、旅行领域规则、大模型、地图、天气和本地持久化。Agent1 的开放式循环可以用来学习模型工具调用，但它没有稳定状态机、领域边界、来源模型、确定性校验和失败隔离，不能直接迁移为综合项目架构。

第一版只有一个本地应用和一条旅行规划主流程。此时拆成多个服务或多个 Agent 会先引入调度、权限、重复调用、状态同步和追踪成本，却没有独立部署或并行领域的现实收益。

### 决策

- 采用前后端分离的本地组合应用，后端内部使用模块化单体；
- 核心按 presentation、application、domain、ports、adapters/infrastructure 分层；
- 领域层不依赖 FastAPI、React、SQLite、第三方 SDK 或模型消息类型；
- 外部模型、地图、天气和 Repository 通过项目自有端口隔离；
- Agent 采用一个 `TravelPlanningOrchestrator`、多个简单领域工具和显式状态机；
- LLM 负责理解、编排、计划候选和解释；代码负责日期、时间、路线、预算、费用状态、影响范围和确认边界；
- MCP 不作为 MVP 内部总线，只在未来存在跨进程复用和明确权限收益时评估。

### 理由

- 模块化单体符合本地运行边界，部署和调试成本最低；
- 端口让第三方服务可替换，并阻止 SDK 类型污染领域；
- 单编排 Agent 更容易限制工具、追踪状态和构建回归测试；
- 显式状态机和确定性校验让模型不能自行宣布成功或绕过约束；
- 不预建 MCP 和多 Agent，避免为尚不存在的复用需求增加故障面。

### 取舍

- 后端进程内模块共享故障域，未来出现独立伸缩需求时可能需要拆分；
- 单 Agent 可能承载较多上下文，需要通过窄工具、领域模型和调用预算控制；
- 项目需要维护端口模型和适配转换，代码量高于直接调用 SDK；
- 不采用成熟 Agent 框架意味着状态机和编排代码由项目明确维护，但边界更透明。

### 后果

- 新 provider 只能通过新适配器接入，不能从领域层直接调用；
- Repository 保存由应用层授权，不能作为模型自由工具；
- 任何多 Agent、微服务或 MCP 扩展都需要新的架构评审和决策记录；
- 业务实现必须能够用离线端口替身验证状态、失败和确认路径。

### 替代方案

1. 复制 Agent1 循环：启动快，但缺少状态、来源、失败和校验边界，不采用。
2. 一开始拆成天气、景点、酒店和规划 Agent：职责看似清晰，但调度和一致性成本过早，不采用。
3. 使用微服务和远程 MCP 工具：有跨进程复用能力，但与当前本地单应用范围不匹配，不采用。

## D-003：外部事实必须携带来源，费用必须保留可信状态

- 状态：已批准
- 日期：2026-08-13
- 适用范围：所有外部数据、计划解释和预算计算

### 背景

天气、POI、路线和价格信息都有来源与时效差异。若系统只保存最终文字或金额，用户无法区分实时事实、规则估算、本人输入和缺失数据。把未知费用按零处理还会制造虚假的“预算充足”结论。

### 决策

- 外部端口结果必须包含 provider、获取时间、有效期或有效期未知说明、警告和 `SourceRecord`；
- provider 响应先转换为项目自有模型，再进入领域和 Agent；
- 费用状态只允许 `verified`、`estimated`、`user_provided` 和 `unknown`；
- `unknown` 的金额为空，不得使用 `0`；
- 总预算同时报告已知合计、未知项数量和预算是否可完整判定；
- LLM 解释只能引用已存在的来源和费用状态，不能自行升级可信等级。

### 理由

- 用户可以判断数据是否过期、缺失或只是估算；
- 领域校验可以基于稳定结构而不是自然语言；
- provider 失败时仍能保留并解释已验证的部分结果；
- 未知值保持未知，避免预算计算产生危险的假精确。

### 取舍

- 数据模型和 UI 比只保存最终文本更复杂；
- 每个适配器都要维护来源映射和时效规则；
- 存在未知费用时，产品不能总给出简单的“是否超预算”答案；
- 不同 provider 的时效和可信条件需要在真实集成后持续校准。

### 后果

- 缺少来源的外部事实不能作为 `verified` 数据进入最终计划；
- `partial` 和 `budget_incomplete` 成为正常业务结果，不是异常成功路径；
- 测试必须覆盖过期、缺失、冲突和 `unknown` 费用；
- UI 必须在计划附近展示来源、不确定性和未知项，不能只放统一免责声明。

### 替代方案

1. 只保存 provider 原始响应：信息完整但耦合、敏感且难以稳定校验，不采用。
2. 只保存最终金额和文字：实现简单但不可追溯，无法安全降级，不采用。
3. 未知费用按零计算：能给出总数但结论错误风险高，明确禁止。

## D-004：局部重规划按影响范围决定是否需要用户确认

- 状态：已批准
- 日期：2026-08-13
- 适用范围：所有基于既有计划版本的修改和重规划

### 背景

用户希望替换某一天或某个景点时，不应无理由重写整份行程。但一个看似局部的修改可能改变住宿城市、跨城交通或相邻日期。完全自动执行会破坏已确认安排；所有修改都询问确认又会让普通当天调整过于繁琐。

### 决策

- 影响范围由确定性代码基于计划版本和依赖关系计算；
- 只影响当天内部、且重新校验通过的修改可以自动执行；
- 影响住宿城市、跨城交通或相邻日期时必须先展示影响并征求用户确认；
- 无法可靠分类的影响按需要确认处理；
- 重规划创建新计划版本，保留旧版本和变更摘要；
- LLM 可以提出和解释修改，不能自行缩小影响范围或跳过确认。

### 理由

- 常见当天调整保持低摩擦；
- 高影响修改由用户掌握决定权；
- 新旧版本和影响摘要让失败可回滚、结果可审计；
- 代码影响分析可以建立明确的边界测试。

### 取舍

- 需要维护计划依赖关系和版本差异；
- 保守分类可能产生额外确认；
- 局部重规划必须处理来源过期和跨边界重新校验，不能只修改一段文字；
- 影响模型错误仍可能漏掉依赖，因此保存前需要再次检查变更范围。

### 后果

- 应用层必须拥有 `awaiting_confirmation` 和 `replanning`；F-003 将其落实为独立 replan lifecycle，不扩展既有 `PlanningJob.status`；
- 确认记录需关联 `trace_id`、基线版本、影响摘要和用户选择；
- 测试必须分别覆盖 same-day、adjacent-day、cross-city、accommodation 和 unknown；
- 取消确认不会改变原计划，确认后生成新版本而不是原地覆盖。

### 替代方案

1. 每次修改都整份重生成：简单但不可控，破坏已确认内容，不采用。
2. 所有修改都自动执行：交互快但高影响变更风险不可接受，不采用。
3. 所有修改都先确认：安全但当天小改动摩擦过高，不采用。

## D-005：provider 配置按原子组 fail-safe 装配

- 状态：已批准任务范围内实现
- 日期：2026-08-14
- 适用范围：本地后端启动、第三方凭证加载和 provider adapter 组合根

### 背景

本地健康服务必须能在没有任何第三方账户时运行，但部分填写的和风 JWT 配置、错误私钥或意外回显凭证又不能被当作可用能力。启动检查也不能通过探测真实服务来验证配置，因为默认开发和 CI 必须离线。

### 决策

- 每个 provider 使用原子配置组；全空为 `disabled`，完整且本地合法为 `ready`；
- 任一部分配置或本地结构非法都以稳定、无值错误码终止启动，不进行隐式降级；
- 和风私钥只以绝对本地路径引用，PEM 不进入环境变量、报告、异常、文档或仓库；
- 本地运行的 `Settings` 只自动读取 `.env.local` 与进程环境；`APP_ENV=test` 时禁用 dotenv source，敏感字段禁止进入 `repr`；
- 启动检查只做本地验证和 adapter 构造，不访问 provider。

### 后果

- 无账户的贡献者和 CI 可继续运行健康与离线门禁；
- 显式但错误的生产配置会尽早失败，避免任务运行到一半才发现配置残缺；
- `ready` 仅表示本地配置可构造，不能作为鉴权、配额、条款或 live 可用性的证据；
- 真实凭证和 live smoke 仍需独立授权门禁。

## D-006：首次 live smoke 总费用上限调整为 12 元

- 状态：用户已确认
- 日期：2026-08-14
- 适用范围：F-001 首次受控真实 API 冒烟

### 背景

DeepSeek 已公告 2026-08-17 起对 `deepseek-v4-flash` 启用峰谷价。按任务冻结的最大调用预算，三家 provider 在高峰时段的保守费用上界约为 9.274 元，原 5 元上限无法覆盖该边界。

### 决策

- 首次 live smoke 仍只允许一个完整规划任务；
- DeepSeek、高德和和风的最大 HTTP 尝试数继续分别为 3、16 和 4；
- 总费用停止上限从 5 元调整为 12 元；
- 执行前必须重新核对官方价格、账户余额和控制台配额；估算可能超过 12 元时不得启动；
- 该决定不授权充值、真实调用、持久缓存、截图、公开部署或后续重复运行。

### 后果

- 12 元覆盖当前约 9.274 元的高峰保守上界并保留余量；
- provider 没有项目侧精确人民币硬锁，因此调用次数、单任务限制、90 秒总时限和执行前核价共同构成停止边界；
- Step 38 仍需用户单独批准；高德使用边界由 D-007 记录。

## D-007：高德个人本地使用与数据保留边界

- 状态：用户明确确认
- 日期：2026-08-14
- 适用范围：F-001 高德 Web 服务 API 的本地使用、展示和数据生命周期

### 背景

高德公开协议对共同展示与脱离服务展示的边界存在解释空间。用户与高德工程师进行了电话沟通，并明确要求项目以其确认的六项边界为准。该记录不虚构为高德书面许可书。

### 决策

- 项目仅供本人、非商业、本地自用，可查询地理编码、POI、步行路线和公交路线；
- 必要结果可与天气和 AI 行程说明组合为本人查看的双日计划；
- 存在高德来源时页面固定标注“数据来源：高德地图”并提供官方链接；
- 不保存高德原始响应、不建立持久缓存；转换后的必要字段只存在本机进程内存中，程序重启后消失；
- 不公开部署、不向其他用户提供服务、不传播真实高德数据截图；
- 用户确认该范围属于个人开发者许可，无需另行购买企业技术服务许可。

### 后果

- 任何 SQLite 持久化、原始响应留存、截图证据、公开部署、多人使用或商业化都会超出本决定，必须停止并重新审计；
- live smoke 证据只能记录时间、调用计数、稳定状态和脱敏摘要，不保存真实高德响应或截图；
- 若高德后续书面通知与本决定冲突，以新的官方要求收紧项目边界。

## D-008：F-001 以单一完整垂直切片 PR 交付

- 状态：用户明确批准范围例外
- 日期：2026-08-14
- 适用范围：F-001 当前 120 个工作区变更文件的提交、预 PR review 和 PR 交付

### 背景

F-001 从领域模型、单 Agent 编排、三家 provider adapter、任务 API 到 React 五终态 UI 构成一个可独立验收的端到端垂直切片。Step 40–41 统计的工作区已达到 120 个变更文件并超过任务卡约 70 文件/5000 行停止阈值；在继续交付前必须由用户决定拆分或明确豁免。

### 决策

- 用户批准 F-001 作为一个完整垂直切片由单一 PR 交付，并明确接受当前 120 个变更文件的范围例外；
- 该例外只覆盖截至 Step 41 已审查并通过离线门禁的 F-001 文件，不授权新增产品范围、第二 Agent、持久化、公网、交易或额外 live 调用；
- Step 43 必须按批准文件清单精确暂存，在提交前复核无 `.env.local`、PEM、Key、Token、原始 provider 响应或范围外路径；
- Draft PR 必须把 diff 按契约/领域/应用/adapter/API/UI/测试/文档分类说明，并保留 Step 39 真实 UAT `FAIL` 与下一次 live 回归需单独授权的事实；
- 独立 review、统一门禁和远程 CI 仍是阻塞门禁，范围例外不降低质量、安全或验收标准。

### 后果

- 不再因 120 文件本身要求拆分或停止，Step 42 可完成文档收口并在用户批准后进入本地提交；
- 一个 PR 的审查负担较高，必须使用精确 staging、分类 diff 摘要、全量门禁和 Draft PR 降低漏审风险；
- 本决定不是后续任务突破文件/行数阈值的先例；新的任务超阈值仍需重新停止并取得明确批准。

## D-009：将精确时间骨架迁移给确定性代码

- 状态：`IMPLEMENTED_REVIEWED_AND_DELIVERED`；F-001-CR1 已在 stacked implementation branch 实现，PR #5 已按顺序合并至功能分支，PR #4 已复验并合并至 `main`；Step 45T live UAT 为 PASS，F-001 产品状态归档为 PARTIAL
- 日期：2026-08-15
- 适用范围：F-001 双日候选的活动时间责任边界

### 证据

- generation 与 repair 已共享冻结候选 Schema、完整两日窗口、住宿锚点和正数交通窗口规则；
- Step 45F 离线审查确认唯一可证实的传递缺口是 repair 只收到通用 `candidate_time_invalid`，现已用五类无值闭集诊断和静态提示最小修复；
- Step 45A、45C、45E 三次受控真实 UAT 仍未形成可验收的 ready/partial 真实计划，其中 Step 45E 在 generation 和唯一一次 repair 后都未通过时间可行性准入；
- 离线测试只能证明校验、诊断和单次 repair 契约，不能证明真实模型将稳定生成精确可行时刻。

### 决策边界

- 确定性代码基于用户日窗口、住宿锚点、候选活动时长和路线时间生成可验证的时间骨架与活动排程；
- LLM 负责需求理解、POI 选择、优先级与顺序建议、取舍理由和自然语言解释，不再独立决定最终精确开始/结束时间；
- `DailyRoutePlan`、实际路线时长、日期、重叠和最终确定性校验继续作为不可放宽的硬边界；
- 2026-08-15 用户已明确批准该职责迁移，并批准补充 Step 45G 先完成变更控制、详细设计和测试地图；Step 45G 不实施生产代码；
- 具体游览时长、交通缓冲、可选活动溢出、路线缺失和 PR 范围策略均已按 F-001-CR1 获批并在 Step 45H 实现。

### 当前后果

- 生产编排已迁移到 `PlanProposal → route facts → deterministic scheduler → PlanCandidate`；旧精确时间 parser 只保留迁移回归，不再是正常路径；
- 在 F-001-CR1 策略获批并完成实现、review 和受控 UAT 后，不再继续纯 Prompt 调优；新的 live 调用仍须单独授权；
- Step 46 已按“PR #5 合并到功能分支，再复验并合并 PR #4 到 `main`”完成；Step 47 已完成文档归档。F-001 保持产品状态 `PARTIAL`，后续 live 调用、门票价格能力或范围扩展必须重新批准。

批准的实施边界为：每日最多 2 项；时长 `60/120/180` 分钟且景区、博物馆缺省 120 分钟；步行/公交每段缓冲 10/15 分钟；每天最多移除一次最低优先级 optional 并公开 warning；required 容量不足为 conflict、unknown 时长为 needs_input；无可用路线为 failed，只有携带合法 `RouteLeg` 的 partial 数据可形成 partial 计划。交付采用 stacked PR，并批准 Step 45H 的 24–34 文件、1200–2200 行范围例外。详细设计见 [F-001-CR1 变更卡](./project-management/f-001-cr1-deterministic-scheduling.md)。

## D-010：F-002 仅本地 SQLite 的持久化边界

- 状态：`用户已确认；Step 1 已冻结设计；Step 2–5 已实现`
- 日期：2026-08-15
- 适用范围：F-002 本地计划、来源、版本、decision 和 acceptance 持久化

### 决策

- SQLite 只作为本地单应用存储，数据库实现必须隔离在 Repository adapter；domain、API 和 Agent 不直接依赖 SQLite；
- 使用项目自有升序 migration runner，记录 migration checksum，迁移在事务中执行；不支持自动 down migration、自动降级或导入 F-001 进程内状态；
- 保存经过 allowlist 和 typed model 校验的结构化请求、转换后计划字段、来源 freshness、内部版本和安全验收/decision 摘要；
- 不保存 Key、Token、JWT、私钥、Cookie、Authorization、provider 原始响应、原始错误 body 或完整 Prompt；
- 计划版本追加写入，不提供版本比较、恢复或历史列表 API；单计划删除和 migration 后一次最多 1000 条的 30 天过期清理由 Repository/maintenance port 实现，不支持清空全部数据；
- acceptance record 只接受 typed、代码化的 case/environment/status/check/limitation 摘要，不开放公开写入或查询 API，不保存完整日志、Prompt 或 provider body；
- `unknown` 费用必须保持 `amount=null`，`partial`、`conflict`、`needs_input` 和 `failed` 不得被持久化或投影为 `ready`；
- 默认测试使用临时 SQLite、内存/fake 和脱敏 fixture，不读取 `.env.local`，不访问真实 Provider。

### 后果

- F-002 后续实现必须维持既有 `PlanningJobRepository` 方法和幂等/version 语义；
- attempt 1 保持 F-001 原 job 级 UUIDv5 标识；retry attempt 2/3 使用由 job、attempt 和 trace 派生的稳定命名空间，确保追加式计划版本和来源在同一 job 内不发生标识冲突；
- schema、JSON、状态或来源不一致时读取必须 fail closed，不能返回未经 typed model 校验的数据库内容；
- F-001 的高德原始响应和进程内-only 决策不被持久化授权覆盖；只有转换后的必要结构化字段进入本地数据库；
- 任何云同步、多人、登录、公开部署、版本恢复、历史列表或原始响应留存都需要新的任务和用户确认。

## D-011：F-003 使用独立 replan lifecycle 和原子追加版本

- 状态：`已实现、验收并随 F-003 交付归档`
- 日期：2026-08-16
- 适用范围：F-003 单城市双日计划的结构化局部修改、影响确认和版本提交

### 决策

- 不修改 F-001/F-002 的 11 个 `PlanningJob.status`；重规划使用独立 replan aggregate 和
  `analyzing/awaiting_confirmation/replanning/completed/needs_input/conflict/failed/cancelled/expired/rejected`
  lifecycle；
- 只接受替换活动、删除活动、调整活动时间和同日重排四种 tagged command，不接受 JSON Patch、
  完整新计划、完整自然语言修改、跨城市、住宿锚点、日期或城市修改；
- 影响分类允许多值；只有精确 `same_day_low` 自动执行，adjacent/cross-day、住宿、预算、
  来源刷新和 unknown impact 必须先持久化影响快照并确认，cross-city 在 Provider 调用前拒绝；
- 确认有效期 15 分钟，只授权展示过的影响快照；重复同决定幂等，相反决定、过期确认和基线漂移
  返回稳定冲突；
- replan 不增加 planning attempt，不复用 retry 额度；每次 replan 使用独立 trace，并用 aggregate
  version、job expected version 和 baseline plan/version 做乐观并发控制；
- 成功 ready 或可执行 partial 在单事务中追加 plan version、来源、lineage、change set、decision
  和当前快照；失败、conflict、needs_input、cancelled、expired 不替换原计划；
- migration v2 只增加 `replan_requests` 和 `plan_version_lineage`，复用 typed
  `decision_records`；v1 数据无损保留，旧版本不伪造 lineage；
- 新增三个窄 replan API，不改变现有 POST/GET/retry/DELETE DTO；不新增历史列表、任意版本比较或恢复；
- UI 在当前结果页内提供局部调整面板和影响确认，不创建历史计划页面；默认测试与 CI 完全离线。

### 后果

- D-004 中“应用状态机包含确认/重规划”从本决定起解释为独立 replan 状态机，不是
  `PlanningStatus` 扩展；现有状态机、Repository contract 和前端严格 `TripPlanResponse` 解析保持兼容；
- confirmation 或重规划进行中，服务端和 UI 都继续把原 plan ID 作为当前可用计划；只有原子提交后
  才切换到新 plan ID；
- `unknown` 金额保持 `null`，来源 freshness 不因复用或确认而提升，`partial` 不得投影为 ready；
- 任何新增活动、多城市/多日、恢复旧版本、完整请求保存、依赖新增或真实 Provider 验收都需要新的批准。

## D-012：F-004 拆分并以兼容 version 2 扩展单城市 2–7 日

- 状态：`IMPLEMENTED_REVIEWED_AND_DELIVERED`；F-004A Step 0–7 已完成，PR #13/#16/#17 已依序合并，完整功能 main CI run `32359762190` 通过
- 日期：2026-08-18
- 适用范围：F-004A 单城市连续 2–7 日计划；F-004B 多城市与城际交通仍为候选

### 决策

- 将原 F-004 拆为 F-004A 单城市 2–7 日和 F-004B 多城市/城际交通；任务执行期只激活 F-004A，现 F-004A 已交付，F-004B 仍为未批准候选；
- 保持一个城市、一个住宿锚点、每日最多 2 项和现有步行/公交能力；不支持跨夜、跨城或新增 Provider；
- 旧 `TripPlanRequest`、旧响应 JSON、canonical fingerprint、已保存双日数据和 F-003 双日 replan 行为必须保持兼容；
- 新请求使用可严格判别的 `request_version="2"`、显式结束日期和 2–7 个窗口；优先复用现有 URI，若无法证明严格兼容则停止，不自行新增 `/api/v2`；
- schema version 2 的 typed JSON 足以承载新请求/计划时不增加 migration v3，不改写旧记录；新关系型需求必须重新批准；
- 餐饮按天数、住宿按夜数计算，unknown 金额保持 `null`；天气缺日或 freshness 不确定时保留可用计划并按规则进入 partial；
- route 并发保持 2，每任务上限为 `min(28, 4 × day_count)`；DeepSeek generation/repair 各 1，和风仍使用 7 日预报；
- `day_count > 2` 的 replan 在 Provider、decision 和 plan version 写入前以稳定 scope 错误拒绝；
- 默认测试完全离线，不读取秘密、不调用真实 Provider；真实 UAT 需要独立次数、费用和停止条件批准；
- 采用领域/contracts、application/Repository/API/Provider、UI/UAT/docs 三层 stacked PR；前层 squash 后从最新 main clean restack，不 force-push 重写已审查历史。
- legacy DTO 保持独立；V2 使用 `TripPlanRequestV2`、`TripPlanV2`、`TripPlanResponseV2` 和显式 request/plan/response format 标识，不通过 optional 字段混合版本；
- Repository 方法集合和 SQLite 表不变，按 request version 严格选择 typed model；legacy synthetic 请求 fingerprint 固定为 `f8e8a85d192745f703d968695945c2fa4200f224d4e8ae9162a69abd57bf7edd`；
- legacy/两日任务总期限保持 90 秒；V2 三至七日总期限为 `min(180, 90 + 18 × (day_count - 2))` 秒，单次 timeout 不变；POI 调用仍最多 3，候选上限为 `min(20, max(6, 2 × day_count + 2))`；
- V2 两日可经 typed 映射复用 F-003；任何 3–7 日 replan 在持久化和 Provider 前使用既有 `replan_scope_not_supported` 拒绝。

### 后果

- F-004A 必须先把所有生产双日常量收敛为受 2–7 日约束的显式模型，同时保留 legacy golden；
- 旧应用遇到 version 2 数据只允许 fail closed，不得损坏、删除或误投影；回滚不需要数据库 down migration；
- 版本比较/恢复、历史列表、多城市、城际 Provider、登录/同步/公网和 3–7 日局部重规划继续需要独立任务；
- 任一 stack 超过 35 个生产/测试文件或净新增 3000 行，或需要 migration v3/新依赖时必须停止并重新拆分。

## D-013：F-004B1 使用独立 V3 表达多城市与用户提供城际段

- 状态：`IMPLEMENTED_REVIEWED_AND_DELIVERED`；F-004B1 Step 0–8 已完成并归档，PR #26 已合并，最终 main CI `32386260285` 成功
- 日期：2026-08-20
- 适用范围：F-004B1 中国大陆 2–3 城、用户提供的相邻城际段和完全离线约束
- 替代关系：把 D-012 中尚未拆分的 F-004B 候选细分为 F-004B1 → F-005 → F-004B2；不改变 D-012 已交付的 F-004A 事实

### 决策

- F-004B1 只支持 2–3 个由用户排序且不重复的中国大陆城市；每城至少住宿一晚，每城有独立住宿锚点，总住宿夜数等于总天数减 1；2 城最少 3 日，3 城最少 4 日，总行程最多 7 日；
- 首版只支持单向/开放式路线，不用重复首城表达闭合往返；不做系统全局路线优化；
- 每自然日最多一次到下一城市的城际转移，转移日最多一项活动；不支持跨夜、第三城市、联程换乘或自驾；
- 城际方式只允许铁路、航空和长途客运。班次、站点、出发/到达时间和可选费用由用户提供；铁路/航空/客运 Provider 调用为 0，不承诺班次、票价、余票、库存、预订、支付或出票；
- 出发前/到达后缓冲分别为铁路 60/30 分钟、航空 120/60 分钟、长途客运 45/30 分钟，并由确定性代码影响逐日窗口和活动排程；
- 城际费用只有用户提供时才以 `user_provided` 进入已知预算，未提供时保持 `unknown`、`amount=null`；不得混合伪造的估算、实时价格或 availability；
- 新能力使用独立严格 `request_version="3"` request/plan/response typed 变体；不向 V2 添加大量 optional 字段，legacy/V2 JSON 形状、canonical fingerprint、已保存数据和行为保持兼容；
- 复用现有 POST/GET/retry/DELETE URI，通过严格 tagged union 判别版本；Repository 方法集合不变，typed union 只显式增加 V3；
- schema version 2 typed JSON 足以承载 V3 时不增加 migration v3、不改写旧记录；需要新列、索引、关系实体或查询能力时停止。旧应用读取 V3 只允许 fail closed；
- 全部 V3 replan 都在分析、Provider、decision、lineage 和 plan version 写入前以稳定 scope 错误拒绝；不扩大 F-003；
- 后续实现可按城市复用现有高德/和风/DeepSeek 适配器，但默认测试和 UAT 完全离线、不新增 Provider。调用治理方向为城市解析 ≤ C、POI ≤ 3C、forecast ≤ C、alert ≤ C、generation 1、repair 1、route 并发 2、route ≤ min(28, 4D)、城市 fan-out 并发 2、总 deadline ≤ 180 秒；
- 只保存 allowlist 转换字段和用户提供的必要城际字段；不保存秘密、完整 Prompt、Provider 原始响应、原始错误 body、完整日志或个人票务/证件信息；
- 提供最小多城市编辑器、每城住宿/夜数、相邻城际段、逐日结果和离线读取/SQLite 重启恢复；不新增登录、同步、多用户、云数据库、公网部署、历史列表、版本比较/恢复或交易能力；
- 交付使用四层 stacked PR：domain/contracts → persistence/API → planning → UI/delivery；前层 squash 后从最新 main clean restack，不 force-push；单层最多 30 个生产/测试文件或净新增 2500 行，任务累计超过 90 个生产/测试文件或净新增 8000 行时重新切片。

### Step 1 冻结细化

- V3 request 独立使用 `city_stays` 和 `intercity_segments`，不含单城市 `city/accommodation/intercity_transport_cost`；每段以相邻城市索引、三种 mode、站点、`+08:00` 同日 datetime 和可空 fare 表达；
- 转移日由累计住宿夜数唯一派生；plan day 显式记录出发、到达、当晚住宿城市索引和可空 segment ID，转移日最多一项活动，市内 RouteLeg 不得跨城市；
- V3 plan/response 独立使用 `city_adcodes`、`intercity_segments`、`resolved_destinations` 和三个 `"3"` format tag；内部新增 `PlanningJobResultV3` 并由 `PlanningResult` typed union 承载，legacy/V2 结果和公开键集合保持不变；
- 用户段来源标记 `provider=user`、`unknown_validity` 和固定未核验 warning；未核验 availability 本身不阻止 ready，但参与预算或执行判断的 fare/weather/route unknown 继续产生 partial；
- F-004B1 不新增顶层 HTTP error code；shape 错误为 422 `input_invalid`，所有 V3 replan 为既有 422 `replan_scope_not_supported`；多城市连续性、段、缓冲、fare 和未核验披露使用已冻结的安全 violation/uncertainty codes；
- 前端显式选择单/多城市，默认保持单城市；多城市卡顺序由键盘可达按钮控制，顺序变化后清空相邻段以防错绑；V3 永不展示 replan 入口；
- 分层 RED/GREEN、legacy/V2 golden、schema 1/2 不变、intercity provider call=0、临时 SQLite 和 loopback desktop/390px 门禁已写入测试策略。

### 后果

- Step 1 已冻结精确领域、API、Repository、Provider、测试和 UI 契约；Step 2–8 后续已依次实现、验证、交付并归档；
- F-005 在 F-004B1 后优先处理既有外部服务韧性、时效和 Agent 评估；真实城际 Provider 进入后续 F-004B2，并重新批准数据源、条款、费用、留存和 live UAT；
- 任一 migration v3、新依赖、新 Provider、隐私变化、真实调用或未批准外部服务都必须停止；
- F-001 `PARTIAL`、Step 45M `FAIL`、Step 45T `PASS`、unknown、混合交通 fallback 仅离线以及 F-004A 无真实 Provider UAT 不受本决定改变。

## D-014：F-005 统一外部服务韧性、数据时效与离线 Agent 评估

- 状态：`IMPLEMENTED_DELIVERED_AND_ARCHIVED`；F-005 Step 0–9 已完成，PR #27–#31 依序 squash merge，归档 PR #32 已合并；最终归档 main `96f73d9`、CI run `32453988289` success
- 日期：2026-08-21
- 适用范围：既有 DeepSeek、高德、和风天气适配器及 legacy/V2/V3 planning、F-003 replan 兼容、API/UI 失败体验和完全离线 Agent 评估
- 不适用：新 Provider、F-004B2、真实 Provider UAT、Schema/migration、依赖升级、生产高可用、遥测或公网服务

### 产品和终态决策

- `needs_input` 只用于用户能够修正的必要输入；`conflict` 只用于确定性硬约束；关键链路不能形成安全计划时为 `failed`；只有仍存在可执行计划时才能以 `partial` 保留非关键缺口；
- ready 必须通过关键数据、来源、时效和确定性校验。缺失、过期或参与决策的未验证事实不得提升为 ready；
- 鉴权、Provider Schema 漂移和空数据不自动重试。限流、timeout 和 5xx 在批准的自动重试耗尽后按关键性进入 failed 或 partial；
- DeepSeek generation/repair 继续各最多一次；唯一语义 repair 后仍无效为不可自动重试的 `model_output_invalid`；
- legacy/V2/V3 现有五终态、attempt 3 上限、同 URI API、F-003 replan lifecycle 和 V3 replan 前置拒绝不变。

### 数据时效决策

- 保留 `fetched_at` 作为来源获取/观测时间，不新增公开 `observed_at`；业务发生时间继续存在于具体 typed payload；
- `valid_until` 只有真实合约或确定性规则能够证明时才填写；不虚构统一 TTL 或 Provider TTL；
- freshness 由 `fetched_at`、`valid_until` 和显式 `evaluated_at` 计算；attribution 只证明来源，不证明 freshness、准确性或 availability；
- stale 的关键路线事实不得继续支持已验证排程；天气、预警、POI、城市和住宿事实按能力剔除或披露为 partial；unknown validity 不得冒充 fresh；
- D-013 已冻结的用户提供城际 availability 排除边界不变；用户来源不冒充 Provider 验证；unknown 金额继续为 `null`，不得按 0。

### Provider retry、deadline 和 fallback 决策

- Amap/QWeather 的幂等只读请求只对 timeout、5xx 和受控 429 最多额外尝试一次；DeepSeek 自动传输 retry 为 0；
- 每个可重试逻辑调用最多 2 个 HTTP attempt；Amap 额外 attempt 最多 3、QWeather 最多 1、任务额外总计最多 4；
- retry 使用注入式 full jitter `0–200ms`；合法 `Retry-After` 最多 2 秒；剩余任务 deadline 不足时不等待、不重试；
- HTTP attempt 计入独立 attempt 预算和总 deadline，不增加既有逻辑工具预算；终态、取消、deadline 或预算耗尽后不得启动新调用，active peer 必须 cancel/drain；
- 混合交通 fallback 只用于业务空结果或无 Provider error 的本地非法路线。auth、schema、timeout、rate limit、server 和 unknown 不触发 mode fallback；
- 不新增 Provider；F-004B1 城际 Provider 调用继续恒为 0。

### Agent 安全和评估决策

- legacy/V2/V3 proposal/repair 都只使用 bounded、typed、allowlist 输入；repair 不接收原始无效模型输出、完整自由文本、Provider 原始响应或敏感内容；
- Provider 内容先转换为项目自有类型；提示控制、非 allowlist 字段、tool/system 内容、目录外 POI/来源以及模型提供的终态、路线、费用可信状态和 Provider attribution 必须拒绝；
- 建立至少 48 个完全离线 synthetic Agent eval case，覆盖 legacy/V2/V3/F-003、正常/边界/冲突/Provider 失败/stale/unknown 和至少 12 个攻击 case；
- 安全、来源伪造、工具越权、预算超限和假 ready 为 100% 硬门禁；其余正确性、约束遵守、来源完整性、unknown/partial 真实性、工具预算、失败安全和重复确定性加权总分至少 95%；
- 不使用 LLM-as-judge，不调用真实模型；eval 不能替代真实 Provider UAT。

### API、隐私、测试与交付决策

- 不新增 URI、公开顶层错误码或 JSON 键；复用既有 `data_stale` 和安全 `diagnostic_code`；legacy/V2/V3 shape、fingerprint、Repository 方法和 SQLite schema v2 保持兼容；
- 诊断只允许结构化、脱敏、有限字段；不保存 Key/Token/Cookie/Authorization、完整 Prompt/自由文本、Provider 原始响应/错误 body、原始模型输出或异常堆栈；
- 诊断不进入 SQLite；CI 只输出聚合分数和失败 case ID，不上传 case payload artifact；不新增账号、云同步、遥测或公网服务；
- 必须覆盖 unit、contract、adapter、application、API、SQLite、frontend、browser 和安全测试，并使用 fake、MockTransport、synthetic fixture、临时 SQLite 和非 loopback 网络阻断；
- 必须执行临时 SQLite、loopback desktop/390px、网络/console/accessibility 和独立隐私安全审查；这些证据保持离线标记；
- 交付采用五层 stacked PR：`feat/f-005-resilience-domain-contracts` → `feat/f-005-provider-runtime` → `feat/f-005-application-agent-eval` → `feat/f-005-agent-eval-integration` → `feat/f-005-ui-delivery`；新增层仅允许 legacy/V2/V3/F-003 的固定 eval 经过各自真实离线 application 入口；前层 squash 后从最新 main clean-restack，不 force-push；
- 单 Step 超过 5 个未预期生产/测试文件、单 stack 超过 30 文件或净新增 2500 行、任务累计超过 90 文件或净新增 8000 行时停止并重新拆分。

### Step 1 冻结细化

- 实现分为纯 `domain/resilience.py` 政策、显式 job-scoped `application/tooling/resilience.py` runtime 和单次交换 Provider adapter；禁止全局/context-local attempt 预算。initial attempt 不占额外预算，Amap/QWeather 每个逻辑调用最多 2 个 HTTP attempt，高德/和风/任务额外预算分别为 3/1/4；DeepSeek transport attempt 仍为 1。
- timeout/5xx 使用注入式 `0–200ms` full jitter；429 只有合法 delta-seconds 或注入时钟可解析的 HTTP-date 且不超过 2 秒时可重试，最终 delay 不超过 2 秒。剩余 deadline 不足 delay 加完整单次 timeout 时不启动 retry；retry 保持同一逻辑 permit/并发槽。
- task runtime 在 terminal/cancel/deadline/budget close 后拒绝新 attempt，cancel/drain 所有 active peers 后才能投影结果；planning job 用户级 retry 创建新 runtime，但不增加 attempt 3 上限。route fallback 必须发生在 retry 完成后，且只接受业务空结果或无 Provider error 的本地非法路线。
- freshness 是 attempt 的评估快照：边界 `evaluated_at <= valid_until` 为 fresh，缺少有效期为 unknown；GET 原样返回持久化 snapshot，不按墙钟改写。stale 路线从排程候选移除，无替代时 failed；stale 天气/预警剔除，stale/unknown 地点事实最多 partial；归因和用户确认不能提升 freshness。
- API 复用既有 `data_stale`，capability 仅以 `route_source_stale`、`location_source_stale`、`weather_forecast_stale`、`weather_alert_stale` 安全诊断区分；unknown-validity 继续使用现有 source/uncertainty，不伪装成 stale/fresh。顶层 retryable 表达原因可重跑，UI 另与 `attempt < 3` 组合。
- generation 仅接收 strict typed allowlist context；Provider 原始响应和不受控文本不进入模型。repair 使用不含原始模型输出、自由文本、偏好、硬约束或 Provider observations 的 `PlanRepairBrief`，只携带日期/城市骨架、允许 location/source 目录、固定规则和稳定验证码。
- eval 基线固定为 48 case：legacy/V2/V3/F-003 各 12，每组正常/边界、Provider 失败、freshness/unknown、安全攻击各 3，并重复运行两次。权重固定为正确性 25、约束 20、来源 15、unknown/partial 15、工具/attempt 10、失败安全 15；总分至少 95%，提示注入、来源伪造、工具越权、预算超限和假 ready 零失败。
- 后端错误/时效投影与 Agent 输入安全归属 Stack 3；Stack 4 只负责真实离线 application eval 集成；Stack 5 只消费既有 shape 完成前端和交付验收。五层核心文件、测试矩阵、clean-restack 和原规模阈值以 current-task/testing-strategy 为准；任何端口公开化、Schema/依赖/API shape 或隐私变化都必须停止。

### 后果

- Step 0 只完成任务激活、治理、状态漂移修正和首层本地分支创建，不构成 Step 1 或任何实现授权；
- Step 1 已冻结精确能力矩阵、DTO/执行政策、eval case 格式、测试地图和 stack 归属；Step 2–8 已按批准边界完成实现、离线纵向审查和五层交付，Step 9 已完成依序合并、最终 main CI、归档和任务关闭；
- 任一新 Provider、真实调用、Schema/migration、依赖、公开 API shape、数据留存或隐私变化都必须停止并取得新批准；
- F-001 `PARTIAL`、Step 45M `FAIL`、Step 45T `PASS`、unknown 不按 0、混合交通 fallback 仅离线、F-004A/F-004B1 无真实 Provider UAT 和 F-004B1 城际 Provider 调用 0 均保持。

## D-015：F-004B2 真实城际 Provider 与可信城际事实条件式边界

- 状态：`PROVIDER_LEGAL_GATE_BLOCKED / TASK_ARCHIVED`
- 日期：2026-08-21
- 适用范围：中国大陆 2–3 城相邻段、单向同日直达 rail、独立 V4 contracts、获授权 Provider observation、F-005 runtime、同 URI API/Repository/UI 和独立真实 UAT Gate
- 不适用：air、coach、跨夜、换乘、跨境、复杂优化、网页抓取/逆向、余票/库存承诺、交易、账号/同步/云数据库、公网部署或生产高可用

### 产品、来源与兼容决策

- V4 每个相邻段只能是 `user_provided` 或 `provider_query`，同段不得双来源或静默覆盖；不同段可以混合两个 variant；
- Provider 事实只包括 Provider 记录 ID、车次、发到站和时间、历时、来源、`fetched_at`、可证明时的 `valid_until` 与 freshness；结果仅作信息参考；
- `user_provided`、`provider_verified`、`estimated` 和 `unknown` 严格区分；`provider_verified` 不证明余票、可售或库存；
- 费用只有在字段语义及展示/保存许可明确时才使用，否则 `amount=null`、`confidence=unknown`；unknown 不按 0；
- legacy/V2/V3、既有 POST/GET/retry/DELETE URI 和公开顶层 job/error shape 不变；V4 只增加批准的 version-specific nested keys；
- V3/V4 多城市 replan 都在 reserve、Provider、decision、lineage 和 plan write 前拒绝。

### Provider 与法律 Gate

- 当前没有选定 Provider。高德 Web 服务跨城公交路径规划只是优先待验证候选；12306 网页内部接口、Cookie、抓取和逆向禁止；TravelSky、VariFlight、Bus365 在正式合同、API、价格、配额和数据许可前阻塞；
- Step 1 只能审核用户提供的正式书面授权、合同、工单回复或官方控制台事实，并必须得出一个 `PASS` 或 `BLOCKED`；
- Gate 必须确认固定 Provider/endpoint/version、产品场景、字段语义、展示/attribution/派生/第三方应用许可、保存字段与最长 30 天留存、删除、价格、配额、QPS、资质和真实 UAT 边界；
- 只保存最终选中的规范化 observation，不缓存候选；Provider 原始响应、错误 body、候选列表、HTML、自由文本和完整 URL 不得进入模型、SQLite、fixture、日志或 CI artifact；
- Gate 未 PASS 前不得进入 Step 2–10 实现，不得注册账号、申请 Key、创建应用、提交商务合作、付费或调用真实 Provider；许可不允许批准的展示/保存边界时停止。

### 时效、选择与失败决策

- 班次由确定性 application policy 从 strict typed 候选中选择，不由 Agent 读取原始候选文本；
- stale 关键班次进入 `failed`；unknown-validity 最多 `partial`；缺失、过期、未验证或推断事实不得提升 ready；
- Provider 失败不自动改成用户提供段，不做 rail→air/coach fallback；只能由用户显式切换到手工段后重新提交；
- 鉴权、Schema、空数据和 unknown error 不做传输 retry；timeout、5xx 和带合法 Retry-After 的受控 429 最多额外尝试一次。

### 调用、数据、隐私与测试决策

- 复用 F-005 task-scoped attempt runtime：每个 `provider_query` 段最多 1 个 logical call、每任务最多 2 个、并发 1；每 logical call 最多 2 个 HTTP attempt，单 attempt timeout 6 秒；
- 如果最终选择 Amap，继续共享 Amap 额外 attempt 上限 3 和任务额外上限 4，不提高 V3 多城市 180 秒总 deadline；
- terminal、取消、deadline 或逻辑/attempt 预算耗尽后不启动新调用，active call 必须 cancel/drain；
- SQLite schema 必须保持 version 2，migration 只有 1/2；若 Provider 需要新枚举、表、索引或 migration v3，立即停止并重新批准；
- 不保存 Key、Token、Cookie、Authorization、完整 Prompt、个人票务信息或 Provider 原始内容；proposal/repair 只接收 bounded typed allowlist；
- 保留 F-005 固定 48 case，新增至少 16 个完全离线 F-004B2 synthetic case；默认测试和 CI 阻断非 loopback 网络；
- 必须执行临时 SQLite、loopback desktop/390px、network/console/accessibility 和独立隐私安全审查；
- 真实 Provider UAT 是独立、默认关闭且再次批准的 Step；没有 UAT PASS 时不得把 F-004B2 标记完整完成。

### 交付与停止决策

- 五层 stack：`feat/f-004b2-intercity-domain-contracts` → `feat/f-004b2-intercity-provider-adapter` → `feat/f-004b2-intercity-application-runtime` → `feat/f-004b2-intercity-persistence-api` → `feat/f-004b2-intercity-ui-delivery`；
- 受控相邻扩展仅限直接 export、factory/wiring、同层 typed model、对应测试/synthetic fixture/golden，以及当前状态/evidence 文档；
- 单 Step 超过 5 个未预期生产/测试文件、任一 stack 超过 20 个文件或净新增 1800 行、任务累计超过 75 个文件或净新增 6500 行时停止并重新拆分；
- Provider/许可/价格/配额/留存/UAT 边界不明，或需要抓取、逆向、Schema/migration、依赖、公开顶层 shape、未批准隐私边界或范围扩张时立即停止。

### 后果

- Step 0 只激活治理、同步当前事实和创建首层本地分支，不构成 Step 1 或实现授权；
- Step 1 只审核用户提供的高德官方书面回复并正式得出 `BLOCKED`：回复明确禁止 SQLite 持久化，没有明确授权车次、铁路站点、发到时间和历时等 rail 字段；任一项都不满足本决定 Gate；
- 回复只建立了非商用个人 Web API 场景、建议 attribution 和运行期内存临时保存许可；没有建立数值配额/QPS/价格、固定 endpoint/version 或真实 UAT 准入与销毁边界，回复中的价格链接未访问；
- 当前没有已选 Provider，Step 2–10 全部阻塞。不得把内存许可推定为持久化许可，也不得未经变更批准删除 30 天 observation 边界；
- 恢复 Gate 需要补充正式书面授权同时覆盖所需 rail 字段和批准的 SQLite 保存边界，或由用户另行批准产品/持久化架构变更；
- F-004B2 已以 documentation-only closure 归档；归档不把候选 Provider、未执行 V4 Provider union 或未执行 Step 2–10 表述为交付能力，未来恢复必须使用新的明确决策入口；
- F-001 `PARTIAL`、Step 45M `FAIL`、Step 45T `PASS`、unknown 不按 0、混合交通 fallback 仅离线、F-004A/F-004B1/F-005 无真实 Provider UAT、F-004B1 城际 Provider 调用 0，以及 F-005 离线证据不等于真实 UAT 均保持。

## D-016：F-004C 用户已购铁路段与车次信息

- 状态：`APPROVED / IMPLEMENTED / TASK_ARCHIVED`
- 日期：2026-08-21
- 适用范围：中国大陆境内 2–3 城、相邻城市、单向、同日、直达 rail 的用户已购铁路段；独立 V4 contracts、既有 application/API/Repository/SQLite schema v2 和本地 UI
- 不适用：任何 Provider 查询或核验、12306 自动读取/抓取、air、coach、跨夜、换乘、跨境、复杂优化、余票/可售/库存、交易、乘客/证件、账号/同步/云数据库、公网部署或真实 Provider UAT

### 版本、产品与领域决策

- F-004C 在 F-006 前执行，使用独立 `request_version="4"`、`response_version="4"` 和 `plan_format_version="4"`；
- D-016 只替代 D-015 中从未实现的 V4 Provider union 预留，不改变 F-004B2 的 `BLOCKED` 结论、归档或历史证据；未来真实城际 Provider 必须使用新的版本和新决策；
- V4 只支持中国大陆 2–3 城、相邻城市、单向、同日、直达 rail；每个相邻段都是用户提供的已购铁路段；
- 每段 `service_number` 必填，trim 后转换为 uppercase，并按 `^[A-Z0-9]{1,12}$` 校验；不维护车次前缀 allowlist，也不验证车次真实存在；
- 每段保留出发站、到达站、出发时间、到达时间和可选票价；历时由发到时间确定性计算，不作为请求字段或新增 JSON 字段；unknown 金额保持 `null`，不得按 0；
- 来源固定为 `user_provided`、`unknown_validity` 和“用户提供，未核验”；不得标记为 `provider_verified`，不得声称余票、可售或库存保证。

### API、Repository、兼容与 replan 决策

- 现有 POST/GET/retry/DELETE URI 和公开顶层 job/error shape 保持不变；V4 只增加批准的 version-specific nested keys；
- legacy/V2/V3 exact shape、canonical fingerprint、旧记录读取和既有行为保持不变；V4 fingerprint 包含规范化 `service_number`，排除 `client_request_id`；
- 继续使用现有 SQLite schema version 2 typed JSON 和 planning job 生命周期，不新增表、列、索引或 migration；migration 仍只有 1/2；
- 所有 V4 replan 必须在 reserve、decision、executor、Provider、lineage 和 plan write 前拒绝；不扩大 F-003；
- 任一需要 schema v3、migration、新依赖、新 URI、公开顶层 shape 或旧版本行为变化的实现均须停止并重新批准。

### Agent、隐私、Provider 与测试决策

- `service_number` 和用户城际段原文不得进入 proposal/repair；只允许 deterministic application/domain 校验和规划消费批准的 typed 字段；
- V4 使用只含 `interests` 的专用 strict preferences；`free_text` / `hard_constraints` 必须在 contract/API 边界 422，前端不得展示、提交或静默携带；legacy/V2/V3 preferences shape 和行为不变；
- 不保存姓名、证件、手机号、邮箱、订单号、座位、二维码、Cookie、截图、自由备注或用户城际段原文；
- F-004C 新增城际 Provider logical call 和 HTTP attempt 均为 0；不注册账号、申请 Key、调用高德/12306/和风/DeepSeek 或其他 Provider，也不复用 F-005 attempt runtime 发起城际调用；
- 默认测试和 CI 必须阻断非 loopback 网络；必须覆盖 legacy/V2/V3 exact-shape/fingerprint、V4 strict contracts、schema v2 typed JSON 往返、旧记录、API/retry/DELETE、V4 replan 前置拒绝、Provider 零调用、unknown/null 与隐私拒绝；
- 必须执行临时 SQLite、loopback desktop/390px 浏览器 QA、network/console/accessibility 检查和独立隐私安全审查；这些仍是本地离线证据，不等于真实 Provider UAT。

### 交付与停止决策

- 三层 stack：`feat/f-004c-booked-rail-domain-contracts` → `feat/f-004c-booked-rail-persistence-api` → `feat/f-004c-booked-rail-ui-delivery`；
- 核心文件按 contracts/domain、persistence/API/application、UI/delivery 分层；受控相邻扩展只允许直接 export、typed union/factory/wiring、对应测试/golden/synthetic fixture 及当前状态/evidence 文档；
- 单 Step 超过 5 个未预期生产/测试文件、任一 stack 超过 18 个文件或净新增 1400 行、任务累计超过 50 个文件或净新增 4000 行时停止并重新拆分；
- 任一需要 Provider、真实调用、Schema/migration、依赖/lockfile、秘密、敏感票务信息、未批准 API shape、隐私边界变化或范围扩张时立即停止。

### Step 1 冻结细化

- V4 使用独立 strict request/plan/response/result types；request 段为固定 rail 的 `BookedRailIntercitySegmentV4`，plan 段为 `PlanBookedRailSegmentV4`，只新增规范化 `service_number`，不新增 duration；
- service number 按 strict string → strip → uppercase → ASCII 字母数字 1–12 校验；known fare 为正数 user-provided，unknown 为 `null`；
- V4 response 复用 V3 plural 顶层键集合，source 复用既有 user intercity shape；用户来源 unknown-validity 不冒充 Provider 验证，其他 unknown/stale 仍按 D-014 裁决；
- fingerprint 对规范化 V4 typed dump 排除 client ID 后使用现有 canonical SHA-256；Repository/SQLite/API 只扩 strict typed union，schema v2/migration 1/2 和旧版本 exact behavior 不变；
- V3/V4 replan 在 reserve/decision/executor/Provider/runtime/lineage/plan write 前零写入拒绝；城际 Provider logical call/HTTP attempt 为 0；
- Agent 不接收 service number、完整 segment 或原始城际文本；前端保留 V3 默认，显式选择已购铁路才产生 V4；精确契约和测试矩阵由对应权威文档冻结。

### 后果

- Step 0 只激活任务卡、roadmap、实施计划、D-016、治理边界和首层本地分支，不构成 Step 1 或实现授权；
- F-004B2 保持 `BLOCKED / ARCHIVED`，其 Provider/法律 Gate、未实现事实和历史 evidence 均不改写；
- F-001 `PARTIAL`、Step 45M `FAIL`、Step 45T `PASS`、unknown 不按 0、混合交通 fallback 仅离线、F-004A/F-004B1/F-005 无真实 Provider UAT、F-004B1 城际 Provider 调用 0，以及 F-005 离线 evidence 不等于真实 UAT 均保持。

## D-017：F-006 MVP 体验收口与本地验收

- 状态：`APPROVED / IMPLEMENTED / LOCAL_ACCEPTANCE_PASS / TASK_ARCHIVED`
- 日期：2026-08-21
- 适用范围：现有本地 MVP 的用户模式、终态展示、恢复/DELETE、本地运行、组合式离线验收与四层交付
- 不适用：新产品版本、新 Provider、真实 UAT、公开 API/Schema 扩展、历史列表、运行中取消、设计系统重写、云端或生产高可用

### 产品状态与用户语言

- F-006 只收口本地 MVP 体验、恢复、本地运行和离线验收；不扩大产品、Provider、API 或数据范围；
- F-006 完成时使用 `DELIVERED / LOCAL_ACCEPTANCE_PASS / ARCHIVED`，但项目真实 Provider 就绪继续为 `PARTIAL`；F-001 产品状态保持 `PARTIAL`；
- 用户只看到“单城市”“多城市·自行填写交通段”“多城市·填写已购铁路车次”。legacy/V2/V3/V4 仍是内部兼容术语；单城市 2 日和多日继续由内部规则选择 legacy/V2；
- 只做局部 UX 收口：统一状态、结果摘要、预算、来源、冲突和恢复动作层级；允许少量语义 tokens 和共享组件，不做品牌、路由或设计系统重写。

### 无配置终态、API 与持久化

- 无凭证或 Provider 组合不完整时，复用既有 `configuration_missing`，让 job 安全进入同 shape `failed`；不得停留 `draft`，不得调用任何 Provider；
- 保持 POST/GET/retry/DELETE 和 replan URI、公开顶层 shape、错误码、strict contracts、fingerprint、旧记录行为；不新增 Provider readiness 健康字段、URI 或公开 JSON key；
- SQLite schema 保持 version 2，migration 只有 1/2；30 天生命周期和 job 级级联删除不变；
- V3/V4 replan 继续在 reserve、decision、executor、Provider、lineage 和 plan write 前拒绝。

### 恢复与删除

- 使用统一“上次本机任务”UUID pointer 覆盖 legacy/V2/V3/V4，并兼容读取旧 V3/V4 pointer；localStorage 不保存版本、请求、结果或敏感数据；
- pointer 指向的 job 不存在或已过期时，清除 pointer，不显示任何缓存结果；
- 前端复用既有 DELETE，只允许用户删除当前终态或已恢复任务；不实现历史列表、清空全部数据库或运行中取消 API。

### 安全、Provider 与真实性

- V4 interests-only preferences、Agent bounded allowlist、票务个人信息禁令和 `user_provided / unknown_validity / 用户提供，未核验` 保持；
- F-004B2 继续 `BLOCKED / ARCHIVED`；不恢复真实城际 Provider；F-004B1/F-004C 城际 Provider logical call 和 HTTP attempt 均为 0；
- F-004A/F-004B1/F-004C/F-005 均无真实 Provider UAT；F-005 offline eval、MockTransport、synthetic fixture 和 loopback QA 不等于真实 UAT；
- 核心 F-006 不执行真实 Provider UAT。任何 live 调用必须成为独立、默认关闭且另行批准的 Gate；
- unknown 金额继续为 `null`，不得按 0；Step 45M `FAIL`、Step 45T `PASS` 和混合交通 fallback 仅离线证据保持。

### 本地运行与验收

- 新增安全 PowerShell 本地运行入口，覆盖固定 Python/Node/pnpm 版本、端口冲突、loopback 绑定、健康等待、SQLite 错误和 Ctrl+C 精确子进程清理；不得杀死非本入口创建的进程；
- synthetic 只用于测试/验收，不作为产品模式；保留 F-005 固定 48-case eval，并另建 F-006 组合式完全离线 journey cases；
- desktop/390px 必须覆盖键盘、焦点恢复、label/description/error 关联、live region、44px 触控、颜色对比和零横向溢出；浏览器 network/console/privacy 必须有可复现结论；
- 干净检出安装验收只有在依赖缓存缺失时才允许访问项目已配置的软件包仓库；不得访问业务 Provider。

### 交付、文件与停止治理

- 四层 stack：`feat/f-006-local-runtime-compatibility` → `feat/f-006-mvp-ux-foundation` → `feat/f-006-mvp-journey-recovery` → `feat/f-006-local-acceptance-delivery`；
- 各层核心文件和受控相邻扩展以 current-task/implementation-plan 为准；受控扩展只涵盖直接 export/factory/wiring、同层 typed helper、对应测试/synthetic fixture/browser 支撑和当前状态/evidence 文档；
- 单 Step 超过 5 个未预期生产/测试文件、任一 stack 超过 20 个生产/测试/script 文件或净新增 1600 行、任务累计超过 65 文件或净新增 5200 行时停止并重新拆分；
- `styles.css` 净新增超过 600 行、替换约 30% 以上既有样式、或需要新 UI 框架/路由器/依赖时停止并重新批准；
- 任一需要新 URI/公开 key/错误码、Schema/migration、依赖/lockfile、Provider/真实调用、隐私/数据留存变化、历史列表/清库/运行中取消或范围扩张时停止。

### Step 1 冻结细化

- 必要 adapter 未全部装配时，production bootstrap 必须使用安全 unavailable executor。它保持 POST `202`，随后按对应版本写入 `draft → normalizing → failed` typed result：既有 `configuration_missing`、固定 message“本机服务配置不完整，无法生成旅行计划。”、固定安全 `required_provider_configuration_missing` diagnostic、`retryable=false`、无 plan/来源/调用；部分字段或非法配置仍由现有启动校验 fail closed；
- 不扫描或回填历史 `draft`，不改变 reservation、fingerprint、retry URI 或旧记录；API 的 optional executor 仅保留隔离测试/注入兼容，不成为 production 缺配置行为；
- 用户只见三种产品模式。手工多城市固定 V3，已购铁路固定 V4；单城市继续以“结束日期是否被显式编辑”选择 legacy/V2，不能改成仅按天数推导；
- canonical pointer 固定为 `ita.last-local-job`，只存 UUID；读取顺序为 canonical → 旧 V4 → 旧 V3，成功迁移后移除旧 key。非法 UUID 与 404/过期清理 pointer；暂时网络/服务/解析错误保留 pointer；localStorage 不可用不得阻断规划；
- DELETE 继续使用既有单任务 URI/204，只在前端权威终态显示，并采用 inline 两步确认和确定性焦点恢复；不得把 DELETE 表述为取消，返回修改只清 pointer 不删记录；
- PowerShell runner 固定 Python `3.13.3`、Node `22.16.0`、pnpm `11.19.0` 及 `127.0.0.1:8000/5173`；先检查端口，再启动精确子进程，按后端 health→前端 root 顺序各等待最多 30 秒，Ctrl+C/失败仅收口自身进程。runner 日常离线，不读取/输出秘密、不杀既有进程、不删数据库；
- UI 保持既有视觉，只收口层级与有限语义 tokens；状态不只靠颜色，desktop/390px 覆盖单一 live region、错误关联、键盘/焦点、44px、对比度、reduced motion 和零横向溢出；
- 新增至少 12 个完全离线组合式 journey，不做全笛卡尔积，但必须分层覆盖四版本无配置、三模式、五终态、processing/paused、pointer 迁移/失效、reload/retry/delete、legacy/V2 两日 replan、V2 3–7 日 scope 拒绝、V3/V4 写前拒绝、unknown/来源/隐私；F-005 48-case 原样保留；
- 四层归属固定为：Stack 1 无配置 runtime；Stack 2 产品语言与视觉 foundation；Stack 3 pointer/recovery/DELETE 和旅程行为；Stack 4 runner/组合验收/交付文档。跨层同文件只允许后层为动作 props/确认样式做最小追加，并计入后层阈值。

### 后果

- Step 0–8 已按逐步批准完成：无配置安全终态、三产品模式、全版本恢复/DELETE、安全 runner、离线本地验收、四层交付、依序合并、最终 main CI 和归档均已关闭；
- PR #38/#39/#40/#41 已依序 squash merge；#39/#40/#41 以普通 merge clean-restack 且无 force-push，完整功能 main 为 `d82ca5c6`，CI run `32691778088` success；
- 同 URI、同 shape、schema v2、旧版本兼容、V3/V4 replan 前置拒绝和默认非 loopback 网络阻断均保持；
- F-006 本地验收通过不能提升历史或当前真实 Provider 证据，也不能解除 F-004B2 阻塞。

## D-018：高德路径规划使用单进程共享、无突发的 paced-slot QPS limiter

- 日期：2026-08-30
- 状态：`APPROVED / DELIVERED / ARCHIVED / STEP_6_UAT_INCONCLUSIVE`
- 适用：F-007；`Provider.AMAP + ProviderOperation.CALCULATE_ROUTES`

### 背景与裁决

- 真实本地验收显示高德步行路径规划 2.0 的限制为 3 QPS、最高达到 6 QPS、超限 3 次；同期任务以 `provider_rate_limited`、`route_primary_unavailable` 和 `data_missing` 安全失败；
- 该证据独立记录为 `FAIL / AMAP_QPS_EXCEEDED`。月调用量没有显示总额度耗尽，因此 F-007 修复进程内 attempt 启动节奏，不修改账号、Key、配额、计费或 Provider；
- F-007 不扩大产品、Provider、API、Schema 或数据范围。

### Limiter policy 与所有权

- walking 与 public transit 共用同一 limiter，初次 attempt 和 retry 都必须经过它；
- 限速固定为最多 2 HTTP attempts/秒，以 0.5 秒 paced slot 实现；使用 monotonic clock、禁止 burst，时间窗口按半开区间计算；
- limiter 由 production bootstrap 创建并在单进程内跨所有 planning job/runtime 共享；禁止模块全局、`contextvars`、SQLite、Redis 或跨进程协调；
- 保持既有逻辑调用预算、HTTP attempt 预算、route concurrency=2 和最大 180 秒 deadline。

### 时序、deadline 与取消

- 固定顺序为 retry/backoff → QPS slot → deadline/terminal/cancel 复核 → HTTP attempt；
- limiter wait 计入总 deadline；只有 remaining 至少覆盖等待时间与完整 attempt timeout 才允许启动；
- terminal、取消、deadline、逻辑预算或 attempt 预算耗尽后不得等待或启动新请求；waiter 和 active peer 必须 cancel/drain。

### 兼容、错误与隐私

- 保持现有 POST/GET/retry/DELETE 和 replan URI、公开顶层 shape 与错误码；复用 `provider_rate_limited`、timeout/deadline 和安全 diagnostic；
- 不保存 Key、完整 URL、坐标、原始响应、原始错误 body 或高德 infocode；limiter 状态不进入 SQLite；
- 默认测试和 CI 阻断非 loopback 网络；Schema version 2、migration 1/2、依赖和 lockfile 保持不变。

### 测试、真实 UAT 与交付

- 先用 fake monotonic clock、MockTransport 和 synthetic fixture 验证节流、重试、deadline、cancel/drain、跨 job 竞争及 legacy/V2/V3/V4/F-005 兼容；
- 真实高德 UAT 固定为独立 Step 6；用户已批准不再执行新的真实 Provider UAT。Step 6 以 `UAT_NOT_FORMALLY_PASSED / INCONCLUSIVE` 收口，不能覆盖 Step 45M、Step 45T 或本次 F-007 FAIL；
- 两层 stack：`feat/f-007-amap-qps-policy-runtime` → `feat/f-007-amap-qps-integration-delivery`；
- 单 Step 超过 4 个未预期生产/测试文件、Stack 1 超过 12 文件或净新增 1000 行、Stack 2 超过 18 文件或净新增 1400 行、任务累计超过 30 文件或净新增 2200 行时停止并重新拆分。

### Step 1 冻结细化

- exact scope policy 位于 domain：只有 `(Provider.AMAP, ProviderOperation.CALCULATE_ROUTES)` 得到 0.5 秒 pacing；retry schedule 与所有其他 Provider/operation 不变；
- application limiter 只接收枚举 scope、共享 monotonic clock、async sleeper 与 task runtime 计算的 `latest_start_at`；不得接触路线 mode、坐标、URL、请求/响应或秘密；
- limiter 使用单一 async lock 和 `next_start_at`。`slot_at=max(now,next_start_at)`；空闲不积累 token；`slot_at > latest_start_at` 时不 sleep、不变更状态，等号允许；获准后按实际 monotonic start 设置下一 slot；
- initial 与 retry 都在 task runtime 内过 limiter；retry backoff 先完成。runtime 在排队前预检，并在 slot 后、HTTP 前以 reservation lock 复核 terminal/cancel/deadline/provider+task retry budget；retry extra attempt 只在该 postflight 点预留；
- limiter 等待和 active HTTP 都属于既有 runtime active task，可由 close/异常 cancel+drain；task runtime 关闭不得关闭 process limiter；已授予但未使用的 slot 不回收，以避免补发 burst；
- production bootstrap 在完整 adapter 路径创建一个 limiter并由 runtime factory 闭包共享；缺配置路径不创建；禁止 adapter 内 limiter、module singleton、`contextvars`、持久化或跨进程协调；
- Amap adapter 生产文件不在批准修改清单；实现若证明必须修改则停止并重新批准。

### 后果

- Step 0–8 已完成：Step 6 按实际证据收口，Step 7 完成两层 Draft PR、独立 review、规模/边界审计与逐层远程 CI，Step 8 完成 #43/#45 依序 squash merge、#44 clean-restack 替代关闭、完整功能 main CI 与正式归档；
- #43 merge commit 为 `6252193b8d3f3ed07498ff318e09b02edaca4889`；#45 merge commit/完整功能 main 为 `772e82628766e5e2659ae7c705ea9c6adade9abd`，main CI run `33382187643` success；
- 2026-08-31 的 0.50–0.52 秒间隔和未出现 `provider_rate_limited` 只作为积极补充证据；由于缺少同期高德控制台 QPS/超限记录，不能覆盖 2026-08-30 `FAIL / AMAP_QPS_EXCEEDED`，也不能宣称真实调用 QPS 已 PASS；
- F-006 `LOCAL_ACCEPTANCE_PASS` 保持，项目真实 Provider 就绪继续为 `PARTIAL`；其他历史产品、UAT、unknown、fallback、Provider、Schema/migration 事实均不变。

## D-019：F-008 重建任务卡、事实可信度分层与阶段 Gate

- 日期：2026-09-02
- 状态：`APPROVED / STEP_0_DONE / STEP_1_BLOCKED_BY_APPROVAL`
- 适用：F-008《真实 UAT 缺陷收口与计划事实可信度》的执行治理；不构成 Step 1 法律结论、产品实现或真实 Provider UAT 授权

### 权威基线与目标

- 由于旧 F-008 任务卡已由用户删除，用户明确批准本次“重建任务卡”作为新的权威任务基线；不得再把旧任务卡缺失作为 Step 0 阻塞，也不得根据标题或分支名补写超出重建卡的范围；
- F-008 只收口 replan 失败恢复、计划事实 grounding、Provider 质量表达和 UAT 可信度，使证据区分已核验、Provider 未交叉核验、用户提供且有效性未知、fallback、unknown/data_missing 及安全恢复动作；
- F-008 完成不要求所有真实 Provider UAT 为 PASS；真实 UAT 可以是 `PASS`、`FAIL` 或 `INCONCLUSIVE`，离线、synthetic、MockTransport、loopback 或缺少同期控制台证据不得表述为真实 PASS。

### 阶段与交付治理

- Step 0–12 的精确、单一目标、三层 stack、文件归属和规模阈值以 F-008 current task 为权威；
- 三层候选拓扑为 `feat/f-008-replan-error-recovery` → `feat/f-008-plan-grounding-provider-quality` → `feat/f-008-ux-uat-delivery`；Step 0 只创建首层本地分支；
- Step 1 是高德数据持久化法律/数据 Gate；未通过前禁止生产实现；Step 11 是唯一真实 Provider UAT Step 且需独立批准；Step 12 的 PR、CI、merge 和 archive 也需独立批准；
- 单 Step 上限为 10 个生产/测试/fixture/eval/script 文件、净新增 900 行、冻结清单外 3 文件；Stack 1 为 20 文件/1800 行，Stack 2 为 24/2200，Stack 3 为 22/2000，任务累计为 55 个唯一文件/5200 行；超过即停止；
- Schema version、migration、依赖/lockfile、公开 API shape/URI/error code、Provider request/parse/account/Key/QPS/quota/billing、Provider 持久化/法律边界、F-004B2 恢复或 F-009 均为无条件停止项。

### 尚未形成的决定

- 本决策不批准高德规范化 POI、坐标、路线、polyline 或诊断落盘；
- 不批准纯内存替代、部分字段持久化、Schema v3、migration、新依赖、公开 API shape、删除能力、walking 2km/30min 或 fallback 3km/45min 阈值；
- 不批准读取秘密、保存 Provider 原始响应、调用真实 Provider或执行真实 UAT；这些候选必须分别通过对应 Gate 与用户批准。

### 历史事实保持

- F-001 `PARTIAL`、Step 45M `FAIL`、Step 45T `PASS`、unknown 不按 0、混合交通 fallback 仅离线、F-004A/F-004B1/F-004C/F-005/F-006 无新增真实 Provider UAT均保持；
- F-004B1/F-004C 城际 Provider logical call 和 HTTP attempt 为 0；F-004B2 `BLOCKED / ARCHIVED`；F-006 `LOCAL_ACCEPTANCE_PASS` 不等于真实 Provider ready；
- SQLite schema version 2、migration 1/2 保持；F-007 `DONE / ARCHIVED`，Step 6 `UAT_NOT_FORMALLY_PASSED / INCONCLUSIVE`；2026-08-30 `FAIL / AMAP_QPS_EXCEEDED` 保持，2026-08-31 补充证据不构成 PASS。

## D-020：高德数据持久化法律/数据 Gate 当前阻塞

- 日期：2026-09-02
- 状态：`APPROVED GATE RESULT / BLOCKED`
- 适用：F-008 Step 1；规范化 POI、坐标、路线、polyline、来源、查询时间、时效与诊断的本地持久化边界
- 不适用：律师法律意见、高德新书面授权、纯内存架构批准、Schema/API 变更或真实 Provider UAT

### 审核证据

- [高德地图开放平台服务协议](https://developer.amap.com/pages/terms/) 更新时间为 2025-12-03。第 2.2 条把 POI、坐标经纬度、地址和路线规划等列为“相关内容”；第 3.5 条限制直接存储和缓存，脱离服务使用需提交工单评估；第 3.8 条要求未明示权利另行取得书面许可；
- 同一协议第 4.12.7 条限制未经许可生成衍生品，包括用于数据库；第 7.2、7.3 条进一步要求明确书面同意，并限制存储、缓存、修改与派生使用；
- [高德地图开放平台技术服务使用许可协议](https://lbs.amap.com/pages/authorization/) 只是服务协议的附加条款，许可限定在审核确认的使用场景，不自动扩大数据持久化权利；
- F-004B2 归档的高德官方书面回复明确：只允许程序运行期间内存临时保存，禁止 API 数据长期存储或持久化到本地 SQLite。该回复截至本次审核没有被更宽的新书面授权替代。

### Gate 判定

- 规范化 POI 名称/地址/类型、经纬度、路线距离/时长/方式、路线摘要、polyline、来源/查询时间/时效/诊断均没有覆盖当前本地 SQLite 方案的明确类别级授权；
- 保留期限、SQLite、本地离线使用、删除和导出要求均未获得足以实施的明确许可；attribution 或“仅供参考”展示要求不能推导出存储权利；
- 不保存原始响应、URL、Key、Cookie 或 Authorization 是必要的数据最小化边界，但不能消除对规范化或派生字段持久化本身的授权要求；
- F-008 Step 1 的七项 PASS 条件没有全部满足，且命中“官方限制持久化”和“没有可审计类别级授权”两个 BLOCKED 条件，因此唯一正式结论为 `BLOCKED`。

### 后果与恢复入口

- 不批准任何高德服务数据进入 SQLite；Step 2 及后续生产实现为 `BLOCKED_BY_STEP_1`；
- 若取得正式书面授权，必须逐项覆盖目标数据类别、本地 SQLite、保留期限、attribution、删除和导出，然后重新执行 Step 1；
- 纯内存或更小字段集是可能的替代方向，但会改变批准架构或体验，只能作为新的 `REQUIRES_SEPARATE_APPROVAL` Gate，不能由本决定自动采用；
- 本决定不修改 D-007、F-004B2、Schema version 2、migration 1/2 或任何历史 UAT 事实。

## D-021：真实 Provider 任务采用零持久化的纯内存方向

- 日期：2026-09-02
- 状态：`DIRECTION_APPROVED / PLAN_AMENDMENT_APPROVED / IMPLEMENTATION_NOT_AUTHORIZED`
- 适用：F-008 Step 1 恢复架构 Gate；真实 Provider planning job 与 replan aggregate 的 Repository 和恢复语义
- 不适用：高德 SQLite 授权、既有数据库扫描/清理、代码实现、Step 2、Schema/API 变化或真实 UAT

### 授权解释

- 用户明确授权项目寻求高德正式书面许可；该授权允许准备许可范围与工单材料，但不能替代高德作为数据权利方给出的书面许可，也不授权自动登录账号或提交外部工单；
- 用户同时批准“纯内存或更小字段集”的产品/架构变更 Gate。审核结果排除更小字段集，选择真实 Provider 派生内容零持久化的纯内存方向；
- D-020 的 SQLite `BLOCKED` 结论保持，不能被用户项目授权改写为 Provider 已授权。

### 只读架构事实

- 当前 production bootstrap 默认创建 `SqlitePlanningJobRepository`；只有 test 且未配置 SQLite 路径时使用 `InMemoryPlanningJobRepository`；
- schema v2 的 `plan_versions.plan_json` 保存完整计划，`source_records` 保存 Provider、记录 ID、时间、freshness、reference URL、attribution 和 warning；typed plan 还包含 POI 名称/地址/类型/坐标及路线距离/时长/方式；
- 已有 `InMemoryPlanningJobRepository` 和 `InMemoryReplanRepository` 遵守现有 Protocol，明确不跨进程持久化，因此纯内存方向不必新增 Schema、migration、依赖或公开 API shape；
- 但切换 production 组合会触及 bootstrap、可能的 settings/app、planning/replan Repository 一致性、前端恢复披露与直接测试，超出当前三层冻结文件归属，并改变 F-006 对真实 Provider 任务的重启恢复体验。

### 批准方向

- 任何启用真实 Provider 的整个 planning job 与 replan aggregate 只进入内存 Repository；Provider 派生计划、POI、坐标、路线、来源、时效、诊断、摘要或 hash 的 SQLite 写入均为 0；
- SQLite 只可保存完全不含真实 Provider 派生内容的离线、用户提供或系统自有任务；禁止以规范化、摘要、attribution 或哈希名义绕过边界；
- 真实 Provider job 只在当前进程内支持读取、retry、replan 和 delete；进程退出后不可恢复。canonical pointer 随后的 404 按现有安全语义清理并返回新建；
- UI 必须在调用前和结果页披露“真实数据结果仅本次运行可用，关闭本地服务后无法恢复”；不得把本地 SQLite 重启恢复承诺扩展到真实 Provider job；
- 既有本地数据库未读取、未扫描、未迁移、未删除。任何历史 Provider 数据处置必须单独批准。

### 后果

- 该方向只关闭“选择哪种替代架构”的 Gate，不授权实现；
- 原 Step 0–12 和三层文件归属没有为 bootstrap/persistence 隔离提供单一可验证 Step；D-022 已完成精确计划修订；
- 修订后的 Step 2 状态为 `TODO / BLOCKED_BY_APPROVAL`。用户单独批准前不得修改生产代码或测试；
- 高德正式书面许可仍是未来重新开放 SQLite Gate 的独立路径，届时必须重新执行 D-020 的逐类审核。

## D-022：F-008 纯内存隔离执行计划修订

- 日期：2026-09-02
- 状态：`APPROVED / GOVERNANCE_ONLY / STEP_2_NOT_STARTED`
- 适用：F-008 阶段地图、三层文件归属、测试矩阵和规模阈值
- 不适用：Step 2 设计执行、生产代码、测试实现、数据库、Provider 调用、真实 UAT 或交付

### 阶段修订

- 初始 Step 0–12 修订为 Step 0–14；Step 0–1 历史目标和结果不变；
- 新 Step 2 单独冻结 live Provider planning/replan 的纯内存 Repository、零 SQLite lifecycle/write、进程生命周期、恢复披露和 fail-closed 组合契约；
- 新 Step 3 以 TDD 实现该隔离，并证明完整 Provider 配置下不创建目录、不打开 SQLite、不运行 migration、不写 SQL；
- 原 Step 2–12 依次顺延为 Step 4–14；真实 Provider UAT 移至 Step 13，交付/merge/archive 移至 Step 14；
- Step 2–12 仍逐步单独批准；Step 13 和 Step 14 仍各自需要独立批准。

### 文件归属修订

- Stack 1 `feat/f-008-replan-error-recovery` 扩展为 Step 2–6，新增 `app.py`、`bootstrap.py`、必要时最小修改 `adapters/repositories/memory.py` 及其直接 bootstrap/configuration-missing/SQLite-zero-write/provider/replan 测试；
- `settings.py` 不得提供 live Provider→SQLite 逃生开关；Repository Protocol、SQLite repository/schema、migration、Provider adapters 和公开 contracts 默认只读；
- Stack 2 对应 Step 7–9，原 grounding/provider quality 文件归属不变；
- Stack 3 对应 Step 10–13，并承担 live 结果仅进程内可用的 UX 披露及 recovery/browser 测试；Step 14 仅加入交付治理文档。

### 测试矩阵修订

- 完整 Provider 组合必须选择内存 planning/replan Repository，SQLite lifecycle 对象为空且 open/migration/write 为 0；
- legacy/V2/V3/V4 使用 fake/MockTransport 完成同进程 GET/retry/replan/delete，新 app 对旧 live job 返回既有 404；
- 零/不完整 Provider 配置继续使用既有 SQLite + `configuration_missing` 零调用安全路径，offline/user/system-only SQLite 行为、schema v2、migration 1/2、30 天维护及旧 shape 保持；
- desktop/390px 必须披露 live 结果关闭服务后无法恢复，验证 pointer 404 清理与 offline SQLite 重启恢复并存；
- 默认测试继续阻断非 loopback 网络，不读取秘密或真实数据库，不调用真实 Provider。

### 规模修订

- 一般单 Step 保持 10 文件/净新增 900 行/冻结清单外 3 文件；Step 3 专项为 12 文件/1200 行；
- Stack 1 调整为 30 文件/2800 行；Stack 2 保持 24/2200；Stack 3 调整为 24/2200；任务累计调整为 68 个唯一文件/6500 行；
- `styles.css` 仍为净新增 400 行或替换 25% 停止；治理文档继续不计生产/测试文件数但单独报告；
- Schema/migration、依赖/lockfile、公开 API、Provider request/parse/account/Key/QPS/quota/billing、偏离 D-020/D-021、既有数据库读取/迁移/删除、F-004B2 或 F-009 均无条件停止。

### 后果

- 本决定只让计划重新可执行，不构成 Step 2 批准；
- 当前状态为 Step 2 `TODO / BLOCKED_BY_APPROVAL`；下一批准动作只能是设计冻结，不得直接进入 Step 3；
- D-019 的初始 Step 0–12 数字地图由本决定替代，其历史批准范围、事实保留和三层分支名称继续有效。

## D-023：F-008 真实 Provider 纯内存隔离契约

- 日期：2026-09-02
- 状态：`APPROVED / IMPLEMENTED / VERIFIED`
- 适用：production 自动组合根、planning/replan Repository 所有权、SQLite 零写入、生命周期、测试注入和 fail-closed 边界
- 不适用：生产/测试实现、公开 API 变化、Provider adapter 变化、Schema/migration、依赖、真实 Provider 调用、UAT 或交付

2026-09-03 状态补充：本条 IMPLEMENTED / VERIFIED 仅指已完成的内存隔离与受控 Repository 证明，不代表 production replan 已接通。下文“Step 5 接线”是原计划要求，实际 Step 5/6 保留显式注入；该未交付项现由 D-027 的 R1–R5 承接，旧历史证据不改写。

### 决策

- `create_app()` 必须先解析 Provider adapters 再选择 persistence。只有 DeepSeek/Amap/QWeather 三者全部存在才进入内部 `LIVE_MEMORY_ONLY`；零或有效但不完整组合进入 `SAFE_UNAVAILABLE_SQLITE`，只产生既有 `configuration_missing` 零调用终态；
- `LIVE_MEMORY_ONLY` 由一个 app-owned `PlanningPersistence` 同时持有 `InMemoryPlanningJobRepository` 与 `InMemoryReplanRepository` cohort；其 maintenance/database/database_path 均为空，lifespan 不创建目录、不打开/关闭 SQLite、不运行 migration/cleanup、不执行 SQL；
- Step 3 只建立 cohort 与 planning 自动组合，不提前启用 replan application service。Step 5 接线时必须使用同一 cohort，禁止 memory/SQLite planning 与 replan Repository 混合；
- live 请求、状态、计划、来源、POI、坐标、路线、诊断、摘要、hash 与 replan aggregate 全部只在当前 app 进程内存在。重启后旧 ID 返回既有 404；不得复制、迁移、导出或降级写入 SQLite；
- production 自动组合不得新增 live→SQLite 设置、环境变量或公开 API。完整 adapters 与显式非内存 planning Repository 必须以固定安全码 `live_provider_persistence_must_be_memory` 拒绝；live cohort 构造失败使用同一码并停止，不得 fallback；
- 既有显式 Repository/executor/adapters/replan service 注入只保留为测试 seam；显式 Repository 且无 executor 时继续不自动执行。module-level production app 不得使用注入 seam；
- `SAFE_UNAVAILABLE_SQLITE` 保持 schema v2、migration 1/2、30 天 cleanup、legacy/V2/V3/V4 shape 与 restart recovery；该路径的 `configuration_missing` 结果不含 Provider 派生内容；
- 内部 app state 可暴露非敏感 storage mode/replan repository 指针用于断言，但 health、OpenAPI、公开 URI、DTO、错误码、顶层 shape 和 Step 3 replan HTTP 行为必须零变化；
- Step 11 固定披露：“真实数据结果仅本次运行可用；关闭或重启本地服务后无法恢复。”调用前和结果页都必须可感知，旧 pointer 404 沿用安全清理。

### 失败与验证规则

- adapter 格式、私钥或启动校验错误沿用安全 `StartupConfigurationError`；不得包含凭证/路径、调用 Provider 或回退 SQLite；
- Step 3 RED/GREEN 必须覆盖完整 adapters 内存 cohort、零 SQLite lifecycle/write、四版本 fake/MockTransport、同进程 retry/delete、重启 404、零/不完整配置 SQLite 安全终态、显式注入兼容、混合组合拒绝、API/OpenAPI 零差异；
- Step 3 不修改 Repository Protocol、SQLite repository/schema/migration、Provider adapters、依赖或 lockfile；不读取秘密、不访问非 loopback 网络、不创建含 Provider 数据的数据库。

### 后果

- F-006 的 SQLite 重启恢复承诺继续只适用于不含真实 Provider 派生数据的安全 SQLite 路径，不适用于 live Provider job；
- Step 3 已把组合根调整为先解析 adapters 再选择 persistence，并以 `PlanningStorageMode`、app-owned memory cohort、混合注入拒绝和零 SQLite lifecycle 测试实现本决定；
- Step 3 的生产/测试范围为 3 文件、净新增 260 行；定向、后端全量、Ruff、mypy、文档和范围门禁均通过；Repository Protocol、SQLite schema/migration、Provider adapters、依赖和 lockfile 未变化；
- F-008 Step 3 为 `DONE / PASS`，Step 4 为 `TODO / BLOCKED_BY_APPROVAL`，不得自动进入 replan 契约或实现。

## D-024：F-008 replan 错误恢复与原计划保留契约

- 日期：2026-09-02
- 状态：`APPROVED / IMPLEMENTED / VERIFIED`
- 适用：replan terminal error 分类、公开安全投影、恢复动作、幂等、并发和原计划保留
- 不适用：新 API shape/endpoint、自动 Provider retry、生产实现、Schema/migration、依赖、真实 Provider 调用、UAT 或交付

### 决策

- 恢复动作只有 `RETRY_NEW_REQUEST`、`MODIFY_INPUT`、`REFRESH_PLAN`、`STOP`；不新增公开 recovery 字段，后续 UI 只从既有 status、`ApiError.code/retryable/diagnostic_code` 推导；
- transient Provider/data stale 和 execution/analysis cancel 可用新 request ID 重试；输入/预算缺失必须修改输入；version/baseline/change-scope/expiry 必须刷新当前计划；scope、配置、授权、schema/model invalid 和未知内部失败必须停止；
- 原 replan terminal 后不可重置。恢复必须先读取当前 planning job，再用新的 `replan_request_id` 和当前 `baseline_plan_id` 创建新资源；不得新增 retry endpoint 或自动重试；
- planning result、plan ID、job/plan version 只有原子 commit 成功才可变化；其他所有 terminal outcome 的 result/change_set/result_plan_version 为空，原计划逐字段保持；
- 同 request ID + 同 command/baseline 返回同一资源且不重执行；不同 payload 冲突。单 app 同一 replan executor 最多一次；跨 replan 竞争最多一个 commit，失败者 terminal 为 job-version conflict；
- terminal error 使用既有 public code 与固定安全 message，内部安全 code 放在既有 `diagnostic_code`；不得转发异常、Provider body、URL、坐标、请求或凭证。

### Step 5 实现边界

- 只允许 `domain/replanning.py`、`application/replanning/models.py`、`application/replanning/service.py`、`application/services/provider_replanning.py`、`api/replans.py`、必要时 `api/errors.py` 及其已冻结直接测试；
- 表驱动测试覆盖 closed mapping、原计划保留、无 plan planning result、cancel/exception/invalid result、幂等/decision、并发 execute/commit、lock cleanup、memory/SQLite contract 和 OpenAPI exact shape；
- Repository Protocol、SQLite schema/migration、Provider adapters、依赖/lockfile 和公开 contracts 默认只读；如确需改变，立即停止。

### 后果

- Step 5 已实现 planless safe error preservation、closed terminal projection、unknown fail-closed 和并发 lock lifecycle；原计划保留继续由 Repository commit/version 测试证明；
- F-008 的总体完成授权不降低真实 Provider UAT、远程交付、秘密、数据库和范围停止 Gate；
- Step 5 为 `DONE / PASS`；Step 6 为 `TODO / AUTHORIZED_BY_COMPLETION_GOAL`，只允许全离线纵向验收，不得进入 grounding 或真实 Provider。

Step 6 的纵向验收补充实现后果：live memory cohort 的 `InMemoryReplanRepository` 必须持有配对 planning Repository，并在 commit 成功时原子更新其当前 typed result/version；否则 completed replan 与普通 planning GET 会产生事实分叉。该内部配对不改变 Repository Protocol、公开 API 或 SQLite 实现。

## D-025：F-008 计划事实 grounding 与 Provider 质量契约

- 日期：2026-09-03
- 状态：`APPROVED / DESIGN_FROZEN`
- 适用：legacy/V2/V3/V4 的计划事实来源、Provider 质量、时效、unknown、fallback 与终态仲裁
- 不适用：Provider adapter/request/parse、公开 API shape、路线数值阈值、Schema/migration、依赖、真实 Provider 调用、UAT 或交付

### 决策

- 公开计划中的城市、POI 名称/类别/地址/坐标、路线端点/方式/距离/时长、天气与 Provider 费用只能来自本地校验通过的对应 Provider typed result；模型只允许选择既有 location ID、顺序、optional/required 和受控 duration class，不得把模型标题、解释或数值升级为外部事实；公开活动标题必须由已选 POI 的规范化名称重建；
- 每个公开事实引用的 `source_ids` 必须存在于最终 `sources[]`，且属于承载该事实的同一 typed result；route source 集必须与所选 route result 精确相等。缺失、悬空、跨结果借用、provider/endpoint/city/date/mode 不匹配均 fail closed，不得靠模型或系统补齐；
- 质量闭集保持 `OK / PARTIAL / UNAVAILABLE`：`OK` 只表示 Provider envelope 与本地结构校验通过，不表示交叉核验；`PARTIAL` 的可用 data 可继续使用，但最终计划至少为 `PARTIAL` 并保留固定安全 error/warning；`UNAVAILABLE` 无 data/source，required 事实导致 `FAILED`，optional 天气/预警只允许省略并形成 `PARTIAL`；
- required 事实为城市解析、住宿锚点、候选 POI、模型 proposal、所有最终采用的路线链；optional 事实仅为天气预报和当前预警。hard constraint 未核验、预算 unknown、Provider partial、可用来源有效期未知或 optional 事实缺失均不得产生 `READY`；已知超预算或结构/引用冲突优先为 `CONFLICT`；
- 时效必须用显式 `evaluated_at` 与每个 source 的 `fetched_at/valid_until` 确定计算：`fresh` 可用；`unknown_validity` 可用但最终至少 `PARTIAL`；stale required route/model 必须拒绝且 `FAILED`，stale optional weather/alert 必须省略且 `PARTIAL`，stale location 只可带 `data_stale` 明示降级为 `PARTIAL`。不得读取系统隐式时间或把 unknown 当 fresh；
- `unknown` 不按 0，也不得静默变成 verified。单城无已批准类别规则的 unknown duration 保持 `NEEDS_INPUT`；V3/V4 unknown duration 若使用既有项目固定 120 分钟规则，必须以 system `estimation_rule` 为来源并产生稳定 uncertainty，使结果至少 `PARTIAL`。unknown fare/price 保持 amount 为空、unknown_count 增加且预算为 indeterminate；
- fallback 只允许在用户已选择的 transport modes 内按既有顺序进行，且仅针对 primary 的 empty result 或结构无效结果；auth、schema、timeout、rate limit、server、deadline、budget、stale 或坐标缺失不得用 fallback 掩盖。采用 fallback 的每一段仍须通过完整 route grounding，并产生稳定 warning、最终至少 `PARTIAL`；不引入 walking 2km/30min 或 fallback 3km/45min 等未批准数值阈值；
- 最终仲裁优先级固定为 `CONFLICT > FAILED/NEEDS_INPUT > PARTIAL > READY`，但只有含可发布 plan 的降级结果可为 `PARTIAL`；不得为追求 PASS 删除 error、warning、uncertainty、source、unknown_count 或既有历史评分事实。

### Step 8 实现与测试边界

- 只允许 Stack 2 冻结文件及直接测试/eval；优先在 `candidate_resolution.py`、`final_validation.py`、`scheduling.py`、`offline_planning.py`、`provider_planning_jobs.py`、`multicity_planning.py` 内复用既有 enum/DTO；Provider adapter、公开 contracts、Repository、Schema/migration、依赖/lockfile 默认只读；
- RED 必须覆盖模型标题不能进入公开事实、V3/V4 unknown duration 的 system estimate + uncertainty、source 悬空/跨结果借用、OK/PARTIAL/UNAVAILABLE required/optional 矩阵、fresh/stale/unknown validity、fallback 允许/禁止矩阵、unknown cost/budget 以及 legacy/V2/V3/V4 shape 不变；
- 如实现需要新增公开字段/error code、修改 Provider request/parse、改变路线阈值或越过 10 文件/+900 行单 Step 阈值，立即停止。

### 后果

- Step 7 只完成设计冻结，生产/测试 diff 为 0；Step 8 可按总体完成授权进入本地 TDD；
- 现有 `ProviderResultStatus`、`SourceRecord`、`DataFreshness`、`ApiError`、warning/uncertainty 和 PlanningStatus 足以表达本契约，不新增公开 API shape；
- 真实 Provider 数据继续只在同进程内存使用；本决定不改变 D-020/D-021/D-023 的零 SQLite 持久化边界。
- Step 8 已按本决定实现并验证：公开活动标题由 typed POI 重建；V3/V4 unknown duration 规则带 system source、activity ref 和 uncertainty 并至少 PARTIAL；未改变公开 API、Provider adapter 或数据持久化边界。

## D-026：F-008 UX 可信度、纯内存生命周期与真实 UAT 协议

- 日期：2026-09-03
- 状态：`APPROVED / DESIGN_FROZEN`
- 适用：计划/replan 用户界面层级、恢复操作、来源事实标签、live memory 生命周期披露与 Step 13 真实 UAT 判定
- 不适用：新 API 字段/endpoint、Provider 调用实现、Schema/migration、依赖、路由阈值、真实 UAT 执行或远程交付

### 信息层级与生命周期

- 创建任务前必须在提交操作附近显示固定披露：“启用真实服务时，结果仅在本次本地服务运行期间可用；关闭或重启服务后无法恢复。”不得只藏在帮助页、来源折叠区或结果页；
- ready/partial/conflict 的结果标题区必须重复短版“真实服务结果仅本次运行可用”，且不能用“完整可用”“已验证”等文案暗示 Provider 事实被交叉核验；`READY` 只表示现有来源与确定性规则通过，仍须显示“Provider 提供，未交叉核验”；
- 信息顺序固定为：终态与生命周期 → 唯一主要恢复动作 → 行程/预算 → 来源可信度与时效 → errors/violations/uncertainties/warnings；partial/unknown/stale/conflict 必须用文字和图形表达，不能只靠颜色；
- localStorage 只保存 job pointer，不保存 Provider 计划内容。pointer 404 时清除旧 pointer并回到新建流程，显示“本地服务已重启或任务已不存在；真实服务结果无法恢复”；不得将其描述为网络失败或自动重建旧计划；
- SQLite 安全模式继续保持既有重启恢复；UI 的通用披露使用条件句，不虚构当前是否已启用真实 Provider，也不新增 storage mode API 字段。

### 来源与事实标签

- Amap/QWeather 来源显示“Provider 提供，未交叉核验”，并继续显示 fresh/stale/unknown validity；DeepSeek 显示“AI 仅做候选选择，公开地点/路线事实由 typed 来源重建”；user 显示“用户提供，未核验”；system 显示“项目固定估算规则，不是已核验事实”；
- `unknown_validity` 固定解释为“有效期未知，不代表当前有效”；unknown amount 固定显示“未知，未按 0 计算”；system duration estimate 必须能由 uncertainty 看到受影响引用和来源数量；
- Provider `OK`、attribution 或 `READY` 均不得显示为“真实准确”“官方核验”“UAT PASS”；来源 URL 仍只来自既有安全 typed source。

### planning 与 replan 恢复动作

- planning 保持现有服务端语义：retryable 且 attempt<3 才显示安全重试；needs_input/constraint/config/auth/non-retryable 均引导修改需求或检查配置；达到 3 次时不再显示重试；
- replan UI 从既有 status + `errors[].code/retryable/diagnostic_code` 推导且只显示一个主要动作：transient/cancel → `重新发起调整`（新 request ID）；needs_input → `修改调整内容`；conflict/expired/version → `刷新当前计划`；scope/config/auth/schema/model/unknown failure → `停止并保留原计划`；
- replan terminal 永不原地重置。任一非 completed 结果必须明确“原计划未改变”；completed 后只显示 baseline→result 的本次差异，不提供历史回滚假象；自动轮询暂停不等于失败，继续刷新只读取同一 replan；
- 键盘焦点必须进入新状态标题/错误标题，按钮有可见 focus，live region 不重复轰炸；desktop 与 390px 零横向溢出。

### Step 13 真实 Provider UAT 协议

- Step 13 仍须用户单独批准，并在开始前确认 live memory mode、全部离线/前端/隐私门禁通过、服务与端口范围、请求场景、最大 job/replan 次数、停止条件、测试时段及同期高德控制台 QPS/超限证据可取得；
- 只从现有本地秘密配置注入进程，不读取或回显 Key/Token/Cookie/Authorization、Provider raw response、完整 URL、真实坐标日志或控制台敏感内容；不创建 SQLite，不停止/重启用户既有服务；
- 最小有界场景为一个 planning job 与至多一个 replan recovery；任何 auth/schema/rate-limit/QPS/配额/费用/法律边界、非预期写盘、超出批准次数或无法确认服务归属时立即停止；
- `PASS` 必须同时满足：用户可完成场景、typed 事实/source/freshness/unknown/恢复动作正确、零 Provider 数据持久化、无安全/隐私偏差、同期 Provider 控制台证据可解释且无超限；`FAIL` 为任一产品/事实/安全/Provider 明确失败；缺少同期控制台或关键观测则为 `INCONCLUSIVE`。离线、MockTransport、loopback、浏览器或“未出现 rate-limit”单独均不能构成 PASS；
- UAT 证据只保存脱敏摘要、时间窗、请求计数、终态、安全诊断、控制台结论和零写盘证明；不得保存原始 Provider body、秘密或精确用户敏感行程。

### Step 11/12 边界

- Step 11 只复用既有 DTO/components/styles，实现上述披露、标签和恢复动作；不得新增 framework/router/依赖或改变 API；
- Step 12 只用 fake/synthetic、内存 Provider app 与 pytest 临时 schema v2 SQLite，完成 loopback desktop/390px、keyboard/focus/live-region、network/console/accessibility/privacy；不得调用真实 Provider；
- 如需新增 API shape、storage mode 字段、依赖、超过 10 文件/+900 行或 `styles.css` +400/替换 25%，立即停止。

2026-09-03 Step 12 限定批准：预期且已正确处理的 memory restart / GET 404 浏览器网络错误单列且保留，其他 console error/warning 仍为 0；只允许任务卡列明的 3 个跨层文件机械格式化并豁免对应范围，Step 12 文件上限为 11，净新增 900 行和 stack/累计边界不变。此例外不适用于其他 Step、其他文件、产品逻辑、API 或真实 UAT；复验完成后停止，不进入 Step 13/14。

### Step 11 落地核对

- 已按本契约实现提交前/结果页披露、来源可信度、pointer 404、closed replan 恢复和终态焦点；`刷新当前计划` 实际读取既有 planning GET 并更新可见 baseline，`修改调整内容` 返回结构化编辑，不以关闭弹层冒充恢复。
- 传输或响应解析失败不构成确定终态：创建响应丢失只允许读取当前计划，确认响应丢失继续读取既有 replan，不自动创建新请求，不宣称旧计划必定未改变。
- 本地 142 项前端测试（2 workers、无跳过/延长超时）及静态/build 通过；结果不是 Step 12 浏览器验收、真实 Provider UAT 或 production replan 自动装配证明。

## D-027：F-008 生产重规划接通计划修订

- 日期：2026-09-03。
- 状态：`APPROVED / PLAN_AMENDMENT_ONLY / IMPLEMENTATION_PENDING`。
- 用户授权仅限七份治理文档；不授权生产/测试修改、数据库、服务生命周期、真实 Provider、远程交付或归档。
- 关系：补充 D-023 的尚未落实生产接线义务；保持 D-024 恢复/提交不变量、D-025 grounding 和 D-026 UX/UAT 判定。Step 0–12 的已完成结果及离线证据边界不变；D-026 的 Step 12 例外不延伸至修复或 UAT。

### 决策

- 在 Step 12 与 Step 13 之间插入 R1 事实投影 → R2 四命令局部候选 → R3 adapter-backed concrete planner → R4 默认生产装配 → R5 正式入口全离线验收。每片单一目标、全部 TODO、逐片独立批准，不能从总体完成权限自动开始；真实 UAT 仍只在 Step 13，交付仍 Step 14。
- 保持单城双日 legacy/V2 和四种已支持命令，不扩大 V2 多日或 V3/V4 replan，也不以只做调时/恒失败/全量 planning 覆盖来缩小验收。复用现有领域规则和原子提交，新 planner 只生成校验后的候选，禁止在 commit 前写原 job。
- planning/replan 必须共用 app-owned memory cohort 与 route limiter；每次执行独立 Governor/attempt runtime，不新建互不知情的 limiter，不改既有 pacing/Provider adapter/公开 API。
- 正式组合证明只允许在外部 HTTP transport 使用 MockTransport及非秘密测试配置/时钟；不得注入业务 repository/adapters/service/executor/planner 或 patch 业务 factory 绕过默认装配。既有单元测试 seam 保留，但不能证明生产入口已可用。
- 未来文件归属、逐文件额度及测试矩阵以 current-task 为唯一权威。R1–R4/R5 后端入口归 Stack 1；R5 浏览器/前端归 Stack 3；Stack 2 保持只读。禁止为预算挪层或让前层依赖尚未交付后层修复。
- 预测新增唯一 8 文件/+2300，累计 40/+3913；Stack 1 17/+2607、Stack 2 5/+82、Stack 3 18/+1224。普通 Step 10/900/清单外 3、各 stack 30/2800、24/2200、24/2200、任务 68/6500 全不变；预测不是保证，任一硬上限预计超出即停止、重新请求计划批准。

### 未决与后果

- R3 的具体运行时 policy/deadline 是否复用既有双日上限须在其实施批准前确认；planning 代码常量不是 replan 或本轮 UAT 额度。
- R5 的 loopback/临时合成 SQLite 资源和可能的预期 404 判定须另批；验收发现生产缺陷，先停止并提出准确修复范围，不借验收改生产。
- Step 13 的城市/日期/完整输入、job、replan 首次/恢复/合计、用户重试、分 Provider logical call/HTTP attempt/deadline、费用、时间窗、服务归属、安全计数与同期高德控制台证据全部仍须确认。未给定的数值不可补写。
- 产品可恢复不等于 UAT 可继续：未独立批准时首次明确失败即停止并按 D-026 记录；auth/schema/rate-limit/QPS/配额/费用/法律/写盘/未知服务归属必须停止。后续成功不得擦除首轮 FAIL；缺少自然恢复场景记 NOT_OBSERVED/关键证据不足，不用故障注入冒充真实经历。
- 本 Gate 完成不等于 R1 已获实施批准，更不等于生产 replan ready、Step 13 PASS 或 F-008 完成。F-007 INCONCLUSIVE、2026-08-30 FAIL、2026-08-31 非 PASS 和所有既有 UAT/法律事实保持。

### R1 后续批准与核验记录（不新增实现决定）

2026-09-03 用户随后单独批准 R1 两文件实施。准入通过，但源码与纯领域诊断发现计划级成本归属、完整来源消费者、快照输入及身份/范围规则尚未冻结到可直接实施的程度；R1 为 `BLOCKED / CONTRACT_GAP / IMPLEMENTATION_NOT_STARTED`。具体事实与复现结果见 evidence；本记录不撤销原计划 Gate，也不把 R1 描述为仍未获授权。不修改既有领域或 executor、不选定新预算/身份政策、不扩大文件或规模范围；下一动作须先取得缺口处置设计批准，不能自动进入 R2–R5、真实 UAT 或交付。

## D-028：F-008 R1 完整事实投影内部契约

- 日期：2026-09-03；状态：`APPROVED / DESIGN_ONLY / IMPLEMENTATION_BLOCKED_BY_SIZE_AND_SCOPE`。用户只批准设计及七文档同步，未批准修订四文件实现或阈值变更；原 R1 两文件授权保留。
- 采用最小 application 适配，不修改领域/公开 DTO/Repository：typed projector 接收完整 result 与显式时刻，复用现有 impact/source/freshness/budget/diff/scope helper。executor 增加可选完整事实路径，旧四参数 seam 保留；新路径失败不得回落旧路径，R4 才装配生产。
- 成本 owner 与集合依赖分离：嵌套成本有唯一 activity/route owner，其他为 plan owner；TICKET/LOCAL_TRANSPORT 对活动/路线集合的依赖不等于逐项分摊。分析期未知采用既有 UNKNOWN 语义并需要确认，不冒充最终候选金额；关系冲突或不可证明时 fail closed。禁止 unknown=0、新报价公式或直接提交分析占位项。
- 来源图覆盖所有 typed 消费者，DROP 必须证明无保留消费者；共享刷新不能改写范围外事实。时效用显式时刻计算，unknown_validity 不升级 fresh；user/system 不通过 Provider 调用假造有效期。继续服从 D-025，不绕过 stale required/optional 和范围边界。
- 五类快照必须覆盖完整事实：保留 activity/route/cost/source 原 ID，schedule 使用不依赖 plan revision 的稳定 UUID5；完整 SourceRecord 与 owner/guard 校验不可用 source ID hash 或全计划 allowed refs 替代。新增实体 origin 必须能唯一证明来源于获准旧 root，无状态缓存；无法证明即拒绝。
- 精确规则、四文件分工、测试矩阵及实施批准点仅以 current-task 的“R1 内部契约缺口处置设计 Gate”为权威，避免建立两套细节。D-023–D-027 的纯内存、原子提交、历史证据及独立 UAT Gate 不变。
- 修订预测 R1 4/+760、R3 2/+570（原事实接线已纳入 R1，同层不重复），其余不变；最终 Stack 1 18/+2877，超原 2800 上限 77，任务去重 40/+4183。共享路径逐层计数校正不搬运原 diff。原硬阈值全部不变，规模处置及新增两文件授权均须用户另批；不得先实现再补豁免。

### R1 后续四文件与规模授权、执行状态

用户随后明确批准四文件实施，并仅把 Stack 1 净新增上限从 2800 改为 3000、文件仍 30；普通 Step 10/900/清单外 3、Stack 2/3 各 24/2200、任务 68/6500 全部不变。上文 2800/未批准四文件是设计 Gate 历史，不再是当前授权。技术契约不变；本次仅新增 398 行测试脚手架，初始 collection RED 后重估完整 R1 928/900、最终 Stack 1 3045/3000，按停止条件暂停。当前为 `APPROVED_SCOPE / IMPLEMENTATION_PARTIAL / BLOCKED_BY_SIZE`，不将设计或缺模块错误计为实现 PASS；没有批准继续增大阈值、减少矩阵或进入 R2。

### R1 规模处置候选（未批准，不是新技术决定）

用户随后要求先处置规模再实现与验证。只读细化确认旧 helper 不覆盖完整 owner/消费者/origin，原 928 不是可靠上界；最新四文件估算区间 1450–1900，上沿 850/750/110/190，任务卡记录依据和全部剩余预测。候选仅 R1 专项净新增 2000、Stack 1 净新增 4500，其他文件/层/任务上限及 D-028 技术范围不变；等待用户明确数值批准，有效 900/3000 未改。当前仍 IMPLEMENTATION_PARTIAL / BLOCKED_BY_SIZE；本轮无生产/测试修改，不新增实施切片，不以候选额度授权 R2–R5 或真实 UAT。

### R1 数值批准及实现收口（R1 完成时）

用户已明确批准仅 R1 净新增 2000、Stack 1 净新增 4500（文件 30 不变），其余 Step/stack/累计和四文件范围不变；上节待批状态是历史。当前 R1 DONE / PASS / OFFLINE：实际 1906 行，168 项定向/领域回归与四文件静态通过；不增加技术范围、领域或公开 DTO。可选 executor 路径在候选完成后取一次显式时刻评估完整 before/after，失败不回落；R4 才默认生产装配。当前停止等待 R2，真实 UAT/交付继续独立批准，历史结论不变。

### R2 单独批准及收口（R2 完成时）

用户随后单独批准 R2，现为 DONE / PASS / OFFLINE，仅两文件实际 792，普通 900/Stack 1 4500 及其他阈值不变。四命令构造内部未提交草稿，保留 baseline 类型、未影响实体及来源；route 缺口和旧边 origin 明示，地点事实更新不复用旧测量；分析预算不当最终报价。没有新产品/公开 API/领域/法律决定，R3 才补全并验证候选，R4 才生产装配。69 项候选测试、合并回归 270 项及两文件静态通过；加 R3–R5 剩余预测后 Stack 1 4415（余 85）、任务 5721（余 779），必须继续逐片复核。停止等待 R3 及运行时预算 Gate，真实 UAT/交付仍需独立批准。

### R3 运行时数值确认与准入停止（设计前历史；数值继续有效）

用户已明确批准 R3，并逐项确认单次 replan runtime：总 deadline 90s（含 retry/backoff/limiter wait）；logical call 上限 Amap 12（resolve1/search3/route8）、QWeather2（forecast1/alert1）、DeepSeek2（generation1/repair1）；每 logical HTTP attempt 为2/2/1，额外重试 Amap3/QWeather1/总4，理论总20；attempt timeout 为6/6/35s。复用已存在 policy，不新增必须发起的调用；独立 runtime、terminal/cancel/deadline/budget 后零新请求及 cancel/drain 不变。route 并发2、0.5s pacing 不变；R4才装配共享 app limiter。以上不授权真实调用、Provider 费用/账户边界、UAT 整场参数、服务操作或扩规模。

当前 R3 为 APPROVED / RUNTIME_BUDGET_CONFIRMED / BLOCKED_BY_CONTRACT_GAP / IMPLEMENTATION_NOT_STARTED。纯内存准入复现 D-025 optional weather 省略/刷新和安全降级诊断无法通过 D-028/R1 guards；不是本次有权放宽既有 guard，也不改写 R1/R2 已完成结果。候选最小处置是先单独批准 G1/G2 内部契约设计，再决定精确修复文件、矩阵和全量规模；本条仅登记阻塞，不批准天气范围、diagnostic append 规则或任何修复实现。原 R3 570 预测不含新修复，保留 R4/R5 Stack1 540后可容纳655，设计后须重估。七文档同步后停止，R4/R5/Step13/14/F-009 未进入。

## D-029：F-008 R3 天气与诊断内部证据衔接

- 日期：2026-09-03；技术状态DESIGN_FROZEN。用户明确批准R3-C2000、Stack1 7500、任务9000，文件上限及D-029设计不变；R3-C现为DONE / PASS / OFFLINE，四文件实际1862，561项定向/630项含R2回归及静态PASS；不是生产接通或真实UAT验收。
- 对 D-028 的限定补充：只有获准日级 schedule 内、经对应 typed forecast/alert envelope 证明的省略/刷新才允许变化；历史日级天气、来源共享、精确 origin/allowed refs 保护不解除。fresh 空 alerts 与 UNAVAILABLE/stale 分开，后者省略并 PARTIAL，不能当“验证无预警”；范围外过期需修改时安全失败，不扩大命令影响。
- 历史 errors/warnings/uncertainties 保留有序完整前缀，violations/resolved_destination 不变；新增诊断必须由闭集 typed 证据和现有 code/安全文案确定生成，前后精确核对。旧 PARTIAL 不因新增成功而抹去；未知费用非零，required 失败/硬冲突不得降级成可提交 PARTIAL；retryable 沿用任务卡精确规则，不触发额外调用。
- 选择仅内存、call-owned 的候选结果+证据包装：绑定 job/replan/baseline/command/candidate，由 executor 用候选完成时的同一显式时刻传给 projector 验证；无证据保留旧严格 guard，新路径失败不得退回旧 seam。证据复用领域 typed result，不含原始响应、不做全局缓存、不进入 Repository/日志/公开 API。它只证明本地映射一致性，不证明外部交叉核验。
- source consumer 图涵盖旧历史/计划级消费者和本次有证据的新局部诊断；新 source 必须有完整获准旧 root ancestry，DROP 需无保留消费者。不能给全部历史 uncertainty、deepseek/system provenance 或全 plan 放行。公开 uncertainty 不引入内部 schedule UUID，不通过空 refs 或任意 message 绕过范围。
- 最小拟实施 R3-C：replan_facts.py/test_replan_facts.py/provider_replanning.py/test_provider_replanning.py 四个既有文件，全部 Stack 1。两文件只放松比较不能构成证据传递闭环，故增加 executor 兼容传递及测试；不改领域/公开 DTO/Repository/service/adapter/fixture。精确字段、事件映射、完整测试矩阵与文件分工仅以 current-task 当前设计节为权威。
- 设计时的规模停止历史：代码/测试36/+4311；修复580–800、R3 880–1200、R4/R5 840。上沿最终Stack1 18/+5845、Stack2 5/+82、Stack3 18/+1224、任务40/+7151；当时R3超900达300、Stack1超4500达1345、任务超6500达651，因此停止而未实施。此历史保留，不能削减矩阵、拆片或移层来伪造准入。
- 执行状态补记（2026-09-07）：R3-C/R3-E/R3既有离线结果保持；R4原四文件已完成 `DONE / PASS / OFFLINE`，下一片R5仍需独立批准。默认app-owned内存cohort、共享route limiter与执行隔离已离线验证；当前执行授权/额度见任务卡，验证结果见evidence。本补记不改变D-023–D-030技术规则，也不构成R5或真实Provider UAT通过。

### R3 后续规模授权沿革（历史；被后续批准替代的字段不再生效）

- 用户仅批准R3净新增900→1500（不适用于其他片）、Stack1净新增4500→6500（文件30）、F-008累计净新增6500→8000（唯一文件68）。R3-C仍严格限D-029四文件/900；普通Step10/900/清单外3、R1专项2000、Stack2/3各24/2200、其他专项及全部安全边界不变。
- 重新核算实际36/+4311与全部剩余预测：R3-C 800、R3 1200、R4 250、R5 590（均取上沿/原完整预测），最终Stack1 5845/6500、任务7151/8000；R3 1200/1500，分别余655/849/300，规模准入PASS。若R3-C/R3用满900/1500且R4/R5预测不变，最终Stack1 6245、任务7551；后续增长仍须重新核算，不作完成保证。
- 仅七治理文档同步，不改技术设计、文件归属或测试矩阵，不实施、不调用Provider、不操作服务、不执行Git交付。R3已有实施/runtime授权保留，但恢复依赖R3-C PASS；本轮完成后等待单独批准R3-C四文件实施。规模批准不等于生产接通或真实UAT批准。

### R3-C 独立实施批准后的准入停止（900上限时历史，不是当前执行状态）

- 用户已批准D-029四文件实施；授权未撤回，技术设计/文件归属/完整矩阵及R3 runtime数值不变。本次逐项复核后R3-C估算885–1095（facts390–480、直接测试360–430、executor45–65、直接测试90–120），上沿超过本片900达195，按“预计超限立即停止”保留未实施状态。
- 估算不是新的硬阈值，也不是已证明900内不可能；源码/复用依据及完整剩余核算见current-task/evidence当前节。原580–800及其规模PASS是此前预测历史，不能替代本次详细准入。Stack1/任务预测上沿6140/7446符合6500/8000，不抵消单片超限；不借R3专项1500、不挪层、不拆片或缩矩阵。
- 当前只记录`APPROVED / BLOCKED_BY_SIZE / IMPLEMENTATION_NOT_STARTED`，没有生产/测试实施或新的产品/法律/架构决定。先取得完整≤900的可复核方案或单独规模授权，再重新准入；R3–R5、Step13/14与F-009未进入。

## D-030：F-008 R3-E1/E2 模型与城市内部证据覆盖

- R4状态补记（2026-09-07）：默认生产组合装配已按原四文件完成离线验证；planning/replan共用app-owned内存cohort及route limiter，每次执行保持独立runtime/Governor。正式组合入口纵向验收仍属于R5，真实Provider UAT仍属于Step13；本补记不修改本决定的证据范围或技术契约。
- 后续批准与验收补记（2026-09-04）：用户单独批准R3-E上限900→907，仅用于标准格式化/复验；两文件2/+907、968项及静态PASS，R3-E DONE / PASS / OFFLINE。本节以下为原设计及批准前估算，技术契约保持；不构成执行R3或真实UAT授权。
- 日期：2026-09-03；状态：DESIGN_FROZEN / DESIGN_ONLY。用户只批准本设计Gate；技术规则冻结不等于修复实施或规模准入通过。R3-E为待独立批准的E1/E2必要修复，不重开R3-C，不把R3的1500或R3-C剩余额度转借本片。
- 限定补充D-025/D-028/D-029：只补模型/城市来源及其安全质量诊断的内部证据通道；四命令仍为ReplaceActivity/DeleteActivity/AdjustActivityTime/ReorderActivities，支持范围仍legacy/V2单城市双日。原产品、Provider request/parse、公开API/领域/Schema/依赖/法律边界均不变。
- 最小修复仅Stack1的application/services/replan_facts.py及tests/application/test_replan_facts.py（完整路径见任务卡）。现有EvidencedReplanResult/ReplanEvidence已由provider_replanning.py完整传递，commit不保存证据，无需改executor；resolver已返回保留envelope元数据的ProviderResult[PlanProposal]，无需改resolver或adapter。若实施发现必须改这些只读文件，立即停止再审，不在本批准范围自动扩展。

### E1：模型选择证据不是外部事实

- 沿用EvidenceEvent/ReplanEvidence绑定，不新建公开DTO或第二套来源系统；闭集新增model_generate、model_repair、city。request内部union补PlanningContext、PlanRepairBrief、CityResolutionRequest；仅repair允许新增可选model_context: PlanningContext（默认None）。其他旧operation必须拒绝非空model_context，旧primary/city用途不泛化。
- model_generate要求request为实际PlanningContext、model_context/primary/city均None；model_repair要求request为实际PlanRepairBrief、model_context为同一次resolve使用的PlanningContext，primary/city均None。result为既有ProposalResolution.result的ProviderResult[PlanProposal]，provider=DeepSeek，source_type分别精确为model_plan_proposal/model_plan_proposal_repair；不接收ModelTextOutput、原始无效输出、完整Prompt或自定义解析替代物作为证据。
- 生成/修复绑定不靠布尔标记推定：复用DeepSeekProposalResolver、其纯parse/repair-brief规则及同一governor/runtime。R3可在自己的文件内以调用转发包装捕获实际generate/repair的typed请求，调用仍委托真实adapter，不另加重试/预算或返回业务替身；resolver最终envelope必须对应实际被采用阶段。repair brief必须等于同context按既有可修复validation_code生成的安全brief（既有affected_refs/command_category默认值不擅改），无前序generate、跨resolve/跨context、非可修复失败后repair或第二次repair均拒绝；调用顺序的真实性由R3真实adapter+MockTransport矩阵证明，不声称纯facts或fingerprint能认证一次外部调用。
- context的城市、日期、版本、day_windows、预算/人数及受控工具/地点/来源目录必须从当前job、baseline和本次已证明的POI结果导出。模型只能在原允许目录中选location、优先序、selection_kind、duration_class；复用既有纯解析/allowlist校验typed proposal，不能借内部dataclass跳过校验。完整双日context是只读输入，不产生全计划修改权限；未受影响部分不因模型新建议改变。
- 按日期及被实际采用selection到candidate实体的对应关系计算消费者，不信任event.refs自报权限：活动必须匹配同日location/选项及本命令的局部变换；路线只能作为采用相邻selection形成局部链的决策消费者，测量仍必须由对应route事件独立证明。未被采用的selection、仅作为context读入的实体、无可证明实际用途的模型结果不取得消费者。新模型source不得塞入location/route/cost/城市的事实source_ids，也不得替换POI事实来源；公开标题只取规范化POI名称，模型标题/解释不成为事实或新诊断。
- 非选择型命令可以复用有效baseline与R2确定性变换，不为凑矩阵强制调用模型；若使用模型则必须经过同一完整证据链。四命令的正向与安全拒绝仍全部验证，不能仅实现无需模型的命令或把正常unknown模型恒失败。模型新来源至少有一个精确的实际采用消费者，否则拒绝新增来源。

### E2：城市上下文与住宿事实分离

- city事件request精确为CityResolutionRequest(job.request.city)，result为AMAP的ProviderResult[CityResolution]、source_type=amap_geocode，primary/city/model_context均None。adcode须等于baseline单城市及后续POI/route/context；使用route的citycode时须与本次解析结果精确对应并满足既有数字校验，不通过route事件中的裸CityResolution冒充城市质量证据。
- 新city结果仅补本次局部计算需要的上下文，resolved_destination、旧城市来源、住宿锚点及其历史事实保持不变；不把城市中心坐标当住宿/POI坐标。消费者只可由本次经证据证明、实际使用该城市adcode/citycode的局部POI/route/model操作反向推导到实体；缺下游用途、跨城市、任意声明全日/全计划refs均拒绝。
- 同一城市解析/模型调用可服务多个受影响实体或日期，但每个日级事件仅是同一typed结果的视图；同source_id必须对应完全相同request/envelope/阶段，精确合并已证明消费者，不按视图次数伪造新logical call，也不重复追加相同诊断。相同source借给其他不对应operation、provider或请求即拒绝。
- 复用仅限baseline已保存、仍可证明的typed字段及原source/time，不反造ProviderResult或新fresh标签；baseline没有citycode等本次必需字段时必须真实解析（未来R3受已批resolve≤1约束），不能用adcode猜citycode。住宿仍复用不可变锚点与对应来源；现有location事件只允许在既有ownership范围内证明局部POI刷新，不借城市事件刷新共享住宿。若所需刷新将改写范围外/共享锚点则安全失败，不扩大本Gate。
- required城市/住宿/POI仍遵D-025：缺失或UNAVAILABLE不能发布候选；可用PARTIAL及unknown不得READY；stale location保留data_stale/location_source_stale与PARTIAL，若因此需要范围外改写则拒绝。stale model/route必须拒绝；不以城市来源是上下文为由省略其质量，也不将旧失败覆盖为成功。

### 精确来源、诊断及生命周期

- 先完成typed request/result、实际用途、binding和质量校验，再仅为before中不存在的新model/city source建立局部provenance消费者。只可替换该新来源由_catalog自动生成的无主provenance占位；任何旧source、历史uncertainty、destination/共享住宿/范围外消费者均不得删除或去全局化。旧deepseek/system来源仍按D-028/D-029保守保留；后续请求从baseline重投影时不追溯解锁这些旧来源。
- 对每个新来源s，C(s)必须非空且等于全部经对应事件实际证明的消费者；event.refs为该日C(s)投影的排序去重结果，不能手写扩大。origin(s)=并集parents(ref)，每个parents(ref)必须非空且属于before.roots(command)；现有allowed refs/快照守卫不扩大。若仍有不可解释全局消费者、遗漏合法消费者、交叉/悬空/身份碰撞或多结果共用ID，fail closed。旧来源DROP仍要求全消费者闭包为空；新增局部证明不影响旧DROP保护。
- _envelope/_public_sources及显式completed evaluated_at复用：provider、source_type、fetched_at、valid_until、source_ids与对应envelope逐项匹配；不接受缓存freshness标签。future/无效时刻拒绝，unknown允许但至少PARTIAL；stale模型必须显式拒绝，不能因新增来源改为局部消费者而绕过旧stale provenance防线。
- 诊断继续闭集：PARTIAL映射固定provider_degraded及安全_provider_errors；unknown映射source_validity_unknown；stale城市按既有location_source_stale/data_stale及source_stale。只复用既有code/message与容量20/50/50，不把模型输出或Provider任意文本追加为错误/警告。READY须无降级条件；历史三类列表（含重复）保留有序前缀，新增诊断按D-029确定性顺序精确去重，多条件同时保留，不能因修复成功删除历史失败。
- 同一ReplanEvidence绑定job/replan/baseline/version/command/candidate/events；repair上下文也被fingerprint/deepcopy覆盖。无证据、篡改、跨绑定重放、别名后改、重复事件不一致均拒绝；同输入/显式时刻结果确定且不修改任何输入。证据只在调用栈/进程内存，executor解包校验后丢弃，不入公开API、日志、Repository或SQLite；它是本地一致性证据，不是Provider认证或真实UAT PASS。

### 验收与停止

- 任务卡R3-E完整矩阵为实施冻结基线；R1/R2/R3-C既有矩阵和旧executor兼容回归必须保持。新增model/city fresh、PARTIAL、unknown正向与越界/无据负向必须同时通过；只跑旧回归不能验收新片。R3原真实adapter/MockTransport及runtime矩阵另行执行，不在纯计算片提前宣称已覆盖。
- 设计时规模判断（历史，已由后续数值批准与R3-E验收替代）：必要修复590–800、R3 1020–1400、R4 250、R5 590；上沿Stack1=7907、任务=9213，超7500/9000为407/213，故BLOCKED_BY_SIZE_AND_APPROVAL。估算不是新上限，也未证明现上限内不可能；本Gate不调整额度、不预记压缩收益，先有可复核完整可容纳方案或另获精确规模授权，再独立批准实施。
- 不增第三个生产/测试文件，不改公开shape/领域/Schema/migration/依赖/法律，不新建分支、不执行Git交付/服务/Provider/数据库操作；任何违反或完整预测超限立即停止。R3-E完成后仅只读判断R3准入，不自动执行R3/R4/R5/Step13/14/F-009。

### R3-E后续实施授权与规模提案（批准前历史；现行额度只查current-task）

- 用户随后已批准D-030两文件实施；当前因完整规模超限保持APPROVED / BLOCKED_BY_SIZE / IMPLEMENTATION_NOT_STARTED，不重复索取技术范围授权。本轮只完成规模处置提案，D-030技术契约及全部矩阵保持。
- 仅建议Stack1净新增7500→8500、任务累计9000→10000，文件上限30/68及其他数值不改；当前仍以7500/9000为有效上限。R3-E/R3各用满900/1500且R4/R5完整预测250/590不变时，8107/9413在候选额度下余393/587；不宣称任意后续增长已覆盖。
- 先有两项明确数值批准及重新准入，再按用户恢复指令沿用既有R3-E授权；候选本身不授权代码/Provider/服务/Git交付，R3及后续阶段不自动执行。完整核算与审批Prompt以current-task本轮规模处置节为准。
