# F-020 地图选点操作修复

状态：ACTIVE / LOCAL_FIX_VERIFIED / AWAITING_USER_REVIEW。

用户范围：修复住宿遮挡地图、景点加入弹框、移除入口隐藏、顾问加入无反馈，并检查相邻问题。实现限前端五文件：frontend/src/F009Planner.tsx、frontend/src/F019SelectionView.tsx、frontend/src/F019Advisor.tsx、frontend/src/f019-selection.css、frontend/src/F019Selection.test.tsx；另维护六份任务文档和独立离线证据。

已实现：住宿编辑留在左栏且地图可交互；区域景点在清单内确认经过核验的具体入口；已选景点可直接移除；顾问处理/成功/错误就地反馈，区域建议先确认入口再执行advisorAction→getSession；偏好确认保留本地未保存选择。补齐8项上限、原生地图高度、短窗口composer、手机长列表、搜索用途文案与隐藏编辑器技术计数。

验证：定向20/20，完整前端17文件203/203；TypeScript、ESLint、Prettier和synthetic构建通过；1440×900、1920×930、1536×744、390×844四视口通过。浏览器业务请求mock，外部请求阻断；外部0、未知0、非预期错误0，预期422注入4次。原生地图容器为离线SDK替身，不代表真实高德验收。

归属：隔离分支fix/f020-map-selection-interactions基于main 91f79aa；保留原工作区HEAD/index及历史dirty；五源文件按baseline/preimage/sha保护同步。未修改后端、依赖、环境、数据库或F019冻结材料；原修复阶段未提交；本次已授权提交和推送，PR/merge未授权。

失败边界：保存首次RED、首次GREEN断言措辞差异、两项旧地图测试初始状态假设和首轮浏览器误计预期422。均在本轮普通本地修复授权内定向复验；不重启历史冻结正式批次。同根因连续三次失败或范围扩大须停。

本地证据：output/f020/20260917-161754-interaction-repair/report.md（仓库根目录相对路径；output不随Git分发）。含命令日志、12张截图、browser-report.json、baseline.json、sync-intent.json和change-manifest.json。

待确认：用户复查交互效果；截图中的真实顾问请求未重放，确切服务端错误未确认。此次离线通过不构成真实Provider UAT、用户视觉批准或Git交付。

Git同步授权（2026-09-17）：用户要求“帮我最新的同步到git上面”。允许在fix/f020-map-selection-interactions精确提交本轮五源文件与六份任务文档，并推送origin同名分支；保留main与原工作区历史dirty，不强推、不创建PR或合并、不自动宣告视觉验收。提交和推送结果以远端分支为准，本机记录为output/f020/20260917-222621-git-sync/result.json。
