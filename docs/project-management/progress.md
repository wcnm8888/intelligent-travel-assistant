# 项目进度

## 当前状态

- 当前任务：`F-001 单城市双日旅行计划垂直切片`
- 任务状态：`ACTIVE`
- 当前分支：`feat/f-001-single-city-two-day-plan`
- 已完成 Step：Step 0 至 Step 45
- 当前阻塞：真实 ready/partial 数据 UAT 尚未通过；范围停止阈值已由用户明确批准本次 120 文件单 PR 例外
- 下一批准动作：Step 46，经用户批准后决定是否合并；不得自动进行 live 回归、ready-for-review 或合并

## 最近完成

- 用户批准 F-001 的 L 级任务卡、十二项工程决策和完整风险边界；
- 模型明确固定为 `deepseek-v4-flash`，最多 3 次表示 HTTP 尝试预算；
- 餐饮费用改为用户可决定，UI 默认 100 元/人/天；
- Step 0 确认本地/远程 main 同步、工具链正确、最新远程 CI 成功和统一门禁通过；
- Step 1 创建功能分支，未修改文件、提交或推送；
- Step 2 固化任务卡、激活 roadmap，修正 B-000 收口后的文档漂移，并泛化活动任务文档检查规则。
- Step 3 新增 provider-neutral 的公开契约包和 `api-contract.md`，冻结 JSON Decimal、费用/来源、五种终态、状态转换、HTTP/幂等和稳定错误码；新增 8 项契约测试。
- Step 4 建立杭州双日 ready/partial/conflict/failed synthetic 验收集，补齐计划地点目录，并以 18 项测试冻结状态、预算、来源、地点引用、错误、禁止主张和凭证隔离。
- Step 5 以红绿测试建立纯标准库领域基础，覆盖金额/费用、来源、坐标/地点、路线、天气和计划引用不变量，并以 AST 测试锁定领域依赖边界；动态日期、排程、路线链和预算汇总仍留在后续 Step。
- Step 6 以显式评估时刻和上海 UTC+08:00 建立 D+1 至 D+5、连续双日、人数和文本/偏好输入约束；29 项新测试覆盖时区跨日、日期边界、跨月/跨年、严格类型和规范化重复值。
- Step 7 建立两日窗口、单日活动和重叠校验；23 项新测试覆盖 offset 集合、本地时间类型、时长顺序、窗口边界、日期归属、输入乱序、重叠、重复 ID 和 frozen synthetic 对齐。
- Step 8 建立住宿往返路线期望、链连续性、缺段和交通分钟裁决；15 项新测试覆盖完整/缺失/错绑/反向/额外链、分钟边界、零间隔、同地点和 ready/partial synthetic 对齐。
- Step 9 建立整数分精确累加、unknown 保留和三态预算裁决；16 项新测试覆盖一分钱边界、全部类别/可信状态、低精度 Decimal context、truth-state 负例及 ready/partial/conflict synthetic 重算。
- Step 10 建立 provider-neutral 三态结果、安全错误策略和显式时效裁决；39 项新测试覆盖字段组合、retryable、来源一致性、微秒边界、敏感警告拒绝及 ready/partial/failed synthetic 重算。
- Step 11 建立高德/和风/DeepSeek 三组异步窄端口和冻结 typed DTO；15 项新测试锁定五工具白名单、签名、候选无终态及无框架/传输/Secret/裸类型依赖。
- Step 12 建立三组完全离线的可编程 fake adapter；六个方法拥有独立有序脚本，记录冻结调用快照，配置时强制 synthetic/provider 边界，并以 17 项新测试覆盖三态、七类错误、脚本失败和零网络/环境/sleep 边界。
- Step 13 建立纯应用层显式状态机和冻结转换命令/结果；135 项新测试穷举 11×11 状态组合，并锁定终态、非法边及 retry/retryable 恢复守卫。
- Step 14 建立构造函数注入的离线编排器；9 项新测试覆盖六方法候选轨迹、关键失败、非关键降级、partial 保真、调用顺序、重复运行隔离和零 fake/网络/环境/sleep 生产依赖。
- Step 15 建立六能力白名单、阶段授权、独立逻辑预算、单次/总时限与路线 permit 并发治理，并接入全部编排调用；37 项新测试覆盖精确边界、拒绝不调用、不可变快照和非法时钟/permit。
- Step 16 将 DeepSeek 端口收紧为未信任文本边界，以本地严格 JSON/字段/引用/安全解析后才产生 typed 候选；可修复错误最多消耗一次独立 repair 预算，二次失败安全返回且不泄漏原文。新增严格解析、重复键、越权字段、虚构引用、提示控制、单次修复和剩余时限测试。
- Step 17 建立住宿往返完整路线补全和冻结最终校验摘要；代码按时间、路线、预算、POI/来源、天气覆盖与 freshness 裁决 ready/partial/conflict。缺失事实不伪造，硬冲突优先；新增 13 项路线/终态负向测试。
- Step 18 建立应用层 Repository 端口和单进程适配器；SHA-256 指纹排除 client ID，同 ID/同请求复用，同 ID/异请求冲突；不可变 job 通过状态机、乐观 version 和受控 retry 推进。12 项新测试覆盖 20 路并发单创建、attempt/trace/上限和安全错误。
- Step 19 建立三个进程内任务 API；POST/GET/retry 按冻结契约返回 202/200/404/409/422/500 和安全 envelope，重复创建、retry attempt/trace、上限及应用隔离均由 12 项离线测试证明；POST 尚不启动规划执行。
- Step 20 建立冻结终态结果快照和唯一 `record_result` 写入口；五种终态组合、请求一致性、来源/地点引用及敏感错误文本均由代码校验。新增 needs_input fixture，五类 GET 与 synthetic JSON 精确一致，retry 不保留陈旧结果。
- Step 21 起草“城市旅笺”自包含交互参考稿，覆盖输入、处理中和五种终态；来源/时效、费用可信状态、unknown、安全错误和恢复动作均为一等信息。桌面 1440×900 与窄屏 390×844 本地浏览器检查通过，390px 无水平溢出且控制台无错误；未修改生产 React 或调用 API/provider。
- Step 22 获得用户对桌面与窄屏参考稿的明确批准；以 SHA-256 固化资产，冻结“城市旅笺”方向、信息层级、七种视图、unknown、来源/时效、安全错误和恢复动作，允许生产实现做语义化、无障碍和连续窄屏适配。
- Step 23 实现“城市旅笺”React 旅行需求表单、前端校验和冻结 DTO 映射；餐饮默认 100 元可修改，unknown 费用为 null。有效提交只进入内存准备态，不调用 API；桌面/390px 浏览器 QA 与 18 项前端测试通过。
- Step 24 建立严格同源任务 API client、真实状态阶段 UI 和有界轮询；精确响应/错误码/日期时间 guard、任务标识与状态跃迁一致性、终态停止、15 次暂停、手动继续、取消及防重复提交由 36 项前端测试证明。真实本机 POST 返回 `draft`，15 次 GET 后按设计暂停，全部请求仅到 `/api`；未伪造阶段、未改后端、未调用 provider。
- Step 25 建立严格终态嵌套 DTO 和 ready/partial 结果页，展示双日活动、天气/预警、住宿往返路线、预算汇总和费用可信状态；前端不重算服务端裁决，unknown 无金额且显示为“未知”。43 项前端测试和构建通过；浏览器以冻结后端 synthetic JSON 验证桌面/390px、结果优先、无水平溢出和 0 console error/warning；未改后端或调用 provider。
- Step 26 对齐后端五种终态和来源引用不变量，新增来源/freshness、warnings、uncertainties、violations、conflict、needs_input 和 failed 安全界面。54 项前端测试和构建通过；浏览器以四个冻结后端终态验证桌面/390px、结果优先、无水平溢出和 0 console error/warning；retry 仍禁用并留给 Step 27。
- Step 27 接通严格 retry client 和任务 hook，只允许 retryable partial/failed 且 attempt 小于 3；重试复用 job/client ID，校验 attempt 加一和 trace 更换，清除旧终态并阻止双击重复请求。61 项前端测试和构建通过；Microsoft Edge 以 synthetic partial/failed 验证 retry、attempt 2、390×844 输入折叠、结果优先、焦点恢复、无水平溢出和 0 console error/warning。
- Step 28 实现注入式 DeepSeek Chat Completions adapter，固定正式 Base URL、`deepseek-v4-flash`、非 thinking JSON 输出和 35 秒客户端超时；每个端口调用只执行一次 HTTP 尝试，严格校验响应并映射安全错误。21 项离线 mock transport 测试覆盖请求、修复隔离、失败与畸形响应，未读取凭证或访问业务网络。
- Step 29 实现注入式高德城市解析和 POI 2.0 adapter，固定正式 Host、v3 geocode、v5 place text、城市强限制与 6 秒 timeout；城市级/直辖市、行政归属、稳定 POI UUID、缺坐标、partial 过滤和 HTTP/infocode 安全错误由 42 项离线测试覆盖。路线、环境装配和真实调用仍未进入。
- Step 30 在同一高德 adapter 实现 v5 步行与公共交通单路段路线；城市解析保留官方公共交通所需 citycode，F-001 编排显式传递同城 citycode。37 项离线测试覆盖精确参数、整数米/秒转换、超长数字、来源绑定、空/坏路线与安全错误；未读取 Key、访问高德或装配生产入口。
- Step 31 新增 JWT-only 和风 adapter，使用当前坐标路径的逐日预报和实时预警 API；7 天预报只映射请求双日，当前预警拒绝过期/坏记录并以最早失效时间裁定 freshness。51 项离线测试验证 Ed25519 签名、端点、部分/空结果与安全错误；未读取私钥文件、访问外网或装配生产入口。
- Step 32 建立凭证安全的本地组合根：三方配置组全空时保持 `disabled` 且健康可用，完整合法时本地构造为 `ready`，和风部分配置、相对/缺失/非法/超限私钥均安全拒绝启动。模板与 CI 已切换到 JWT 四字段并保持空值，废弃旧 API Key；未读取真实凭证或访问外网。
- Step 33 以 27 项真实 adapter MockTransport case 和 42 项 fake 编排注入 case 建立跨 provider 失败矩阵；覆盖成功、空数据、401/403、429、timeout、503、Schema 漂移、连接失败及七类项目错误。城市/POI/模型失败精确短路为 failed，天气/预警/路线失败保留计划并降级为 partial；所有调用单次尝试且敏感上游详情不进入结果。
- Step 34 建立 10 类 Agent 输出 scorecard、上下文目录顺序不变性和四终态重复运行评估；合法 JSON 10 次解析一致，九类非法/越权/提示控制输出全部精确拒绝，ready/partial/conflict/failed 各 10 次裁决完全一致。新增 15 项、专项相关 107 项通过，未发现生产实现缺陷。
- Step 35 新增窄任务执行端口和仅供验收的 synthetic executor，五终态均经真实 POST/GET、状态机、Repository 与后台调度进入浏览器；修复轮询漏采合法中间状态时的误拒绝。ready/partial+retry/conflict/needs_input/failed、桌面/390px、焦点、unknown、来源和安全错误均通过，动态请求只到本机且控制台 0 error/0 warning。
- Step 36 统一离线门禁一次通过：运行时与锁文件正确，后端 737 项、前端 62 项、文档检查器 23 项测试及全部格式、lint、strict mypy、TypeScript、Vite build 和文档契约绿色；未访问真实 provider 或读取凭证。
- Step 37 只读审计确认三家本地配置均为空。2026-08-14 现行价下完整 smoke 保守上界约 3.106 元；DeepSeek 已公告 2026-08-17 起启用峰谷价，同一预算高峰上界约 9.274 元、空闲约 4.666 元，因此原 5 元上限需重新约束且 provider 没有硬消费锁。审计时和风归因、DeepSeek AI 披露、高德许可和真实执行器均为前置；前三项代码缺口中的两项及执行器随后已关闭。
- Step 37 补充收口完成和风 `metadata.attributions` 的严格原样传递与 UI 归因、DeepSeek AI 生成披露，以及三家配置齐备才启用的真实任务执行器；新增离线执行闭环覆盖住宿锚点 POI、天气、候选、四段路线、预算和 Repository 终态。
- 用户随后自行创建三家账户与凭证；`.env.local` 保持 Git 忽略，无网络启动检查返回 DeepSeek、高德、和风和真实执行器全部 `ready`。用户批准把首次受控 smoke 总费用上限由 5 元提高到 12 元，并根据高德工程师电话沟通明确确认六项个人本地使用边界；前端补充固定高德来源归因及正反测试，Step 37 收口完成。
- Step 38 按授权执行一个杭州双日真实计划：三家 live 服务均通过鉴权与 Schema 解析，无配额、计费或许可异常；任务保留结构化计划但经确定性校验进入 `conflict`。候选冲突使正常路线补全按设计跳过，因此在同一高德预算内仅追加 1 次公交路线窄探针并通过；没有第二个计划或额外模型调用。
- Step 38 全程未保存原始响应、未持久缓存、未制作或保存真实高德截图，文档与终端摘要只记录脱敏状态、provider 计数和稳定错误码。
- Step 39 沿用一次计划和 12 元硬上限执行真实浏览器 UAT。唯一 POST 在 DeepSeek 严格 Schema 边界以 `provider_schema_invalid`、不可重试 `failed` 收口，高德和和风已有安全来源；触发停止条件后没有重试、第二次提交或额外 provider 调用。
- Step 39 的失败态在桌面和 `390×844` 下均无水平溢出，来源归因、安全失败文案、无来源不披露 AI、无重试入口、DOM 脱敏和 0 console error/warning 均符合预期；但没有 ready/partial 真实计划，UAT 结论为 `FAIL`。另记录页脚 Step 文案过期 finding。
- Step 40 完成工作区相对 `main` 的全量独立只读审查。已证实 `model_output_invalid` 被错误发布为 `provider_schema_invalid`、默认测试 app 会加载 `.env.local` 并可能装配真实执行器、DeepSeek 上下文与 repair Schema 不完整、时间窗口和天气地点存在语义缺陷；工作区 119 个文件、约 2.44 万净新增行已越过任务卡停止阈值。
- Step 40 未直接运行不安全的默认统一入口。通过进程内禁用 dotenv source 的护栏运行后端 744 项测试，另在冻结 Python 3.13.3、Node 22.16.0、pnpm 11.19.0 下完成前端 63 项、Ruff、mypy、Prettier、ESLint、TypeScript、Vite build、文档检查器 23 项和审查前文档契约，全部通过；该结果不能替代修复后的统一入口复验。按授权只同步四份项目管理文档后，文档契约仅因 `docs/README.md` 仍声明 Step 40 而失败，该状态地图留待后续允许写入的文档修复。
- Step 41 关闭默认测试读取本地 dotenv/误触真实 provider 的风险，拆分 DeepSeek provider Schema 与本地候选错误，增加安全诊断枚举，补齐生成/repair 上下文，收紧日期、时间窗、POI 来源、天气地点与 timeout 契约，并修复过期页脚。后端 756 项、前端 64 项及各自格式、lint、typecheck、测试和构建门禁通过；没有真实 provider 调用。
- Step 42 将 Step 41 的实现事实同步到 API、Agent、架构、测试、roadmap、决策和证据文档。用户批准 F-001 作为一个完整垂直切片由单一 PR 交付并接受当前 120 个变更文件的范围例外；该例外不授权新增能力或 live 调用，也不降低 review、CI、安全门禁。
- Step 43 在冻结 Python 3.13.3、Node.js 22.16.0、pnpm 11.19.0 下重跑统一离线门禁，后端 756 项、前端 64 项、文档检查器 23 项及全部静态、构建和文档契约通过；120 个批准文件经精确暂存和安全审查后形成单一本地提交，未调用真实 provider、推送或创建 PR。
- Step 44 将功能分支推送至私有仓库并创建面向 `main` 的 Draft PR #4；PR 正文保留真实 UAT `FAIL`、F-001 `PARTIAL`、120 文件范围例外及 live 回归需单独授权的说明。Windows offline verification 已触发，结果留待 Step 45。
- Step 45 等待并核对 Draft PR #4 的 Windows offline verification；运行 `31807998195` 在 4 分 45 秒内通过，没有失败检查或需要修复的 CI 阻塞。状态文档同步后，最终 PR head 由同一远程门禁复验通过；PR 仍保持 Draft。

## 当前能力边界

- 当前可运行能力包括 FastAPI 健康/任务资源 API、React 旅行需求表单、严格任务 API/retry client、有界轮询、真实处理阶段 UI，以及可消费五种冻结终态快照的计划、来源、冲突、错误和窄屏恢复界面；
- F-001 当前已有批准规格、严格 DTO/状态/错误/来源引用契约、五种 synthetic 验收终态、纯领域校验、provider result 模型、三个 provider 端口、离线可编程 fake、显式状态机、调用治理、DeepSeek 本地严格解析/单次修复、住宿往返路线补全、最终确定性裁决、进程内 Repository、终态结果快照、任务资源 API、已批准 UI 基线、产品表单、轮询阶段 UI、五种终态展示、受控 retry、按完整配置条件装配的三家 HTTP adapter，以及只有三家同时就绪才启用的真实规划执行器；
- 已在 Step 38 的一次性授权内调用 DeepSeek、高德和和风天气真实 API 并完成脱敏 live 契约验证；真实凭证仍只存在于 Git 忽略的本地配置和仓库外私钥文件中，未进入受版本控制文件；
- 和风天气 JWT、账户专属 Host、DeepSeek 模型鉴权及高德地理编码/POI/公交路线均获得一次成功 live 证据；该证据不承诺后续持续可用、数据质量或费用不变；
- Step 39 的具体任务终态为不可重试 `failed`；后续任何再次生成真实计划的行为仍需单独批准调用和费用边界。

## 最近基线证据

- 当前 Step 相关验证：Step 43 提交前统一离线门禁、120 文件 staged diff 和秘密边界检查已通过；Draft PR #4 最终 head 的 Windows offline verification 已通过；Step 39 真实失败态桌面/窄屏安全展示证据仍有效，但 ready/partial 真实 UAT 仍为 `FAIL`；当前等待 Step 46 单独批准；
- 最近离线门禁：测试组合明确不加载 `.env.local` 且拒绝非 loopback 网络；Python 3.13.3、Node.js 22.16.0、pnpm 11.19.0 下统一 `scripts/verify.ps1` 一次通过，包含后端 756 项 pytest、前端 64 项 Vitest、文档检查器 23 项，以及锁、依赖、peer、Ruff format/check、strict mypy、Prettier、ESLint、TypeScript、Vite build 和文档契约；
- 远程基线：`main` 提交 `50980887dadc0500d98dcd29966a5da2da74b2e2` 的 Windows CI 运行 `31704781850` 成功；
- 当前开放 Draft PR #4；功能分支已推送且远程 CI 通过，尚未标记 ready 或合并。

## 权威入口

- 文档地图：[../README.md](../README.md)
- 当前任务：[current-task.md](./current-task.md)
- 当前计划：[implementation-plan.md](./implementation-plan.md)
- roadmap：[roadmap.md](./roadmap.md)
- 验收证据：[evidence.md](./evidence.md)
- B-000 归档：[B-000 project baseline](../archive/task-cards/B-000-project-baseline.md)

本文件只保留当前状态和最近完成摘要，不追加逐轮对话或完整终端日志。
