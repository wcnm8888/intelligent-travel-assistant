# 项目决策记录

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
