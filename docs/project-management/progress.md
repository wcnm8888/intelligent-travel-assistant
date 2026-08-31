# 项目进展

## 当前状态

- 当前任务：无
- 最近完成：F-007 Step 0–8 `DONE / ARCHIVED`；完整功能 main `772e82628766e5e2659ae7c705ea9c6adade9abd`，CI run `33382187643` success；
- PR 状态：#43 与 clean-restack #45 已合并；原 #44 已由 #45 替代并关闭；没有开放或未处置的 F-007 功能 PR；
- UAT 事实：2026-08-30 `FAIL / AMAP_QPS_EXCEEDED` 保持；Step 6 为 `UAT_NOT_FORMALLY_PASSED / INCONCLUSIVE`；2026-08-31 的 0.50–0.52 秒间隔和未出现 `provider_rate_limited` 只是积极补充证据，不构成 PASS；
- 历史事实：F-001 `PARTIAL`、Step 45M `FAIL`、Step 45T `PASS`、unknown 不按 0、混合交通 fallback 仅离线证据、F-006 `LOCAL_ACCEPTANCE_PASS` 不等于真实 Provider ready；
- 数据与工程边界：SQLite schema version 2、migration 只有 1/2；依赖、lockfile、公开 API shape 与 Provider 数据边界未变化；
- 下一批准动作：用户选择并单独批准后续任务；F-008 与 F-009 当前均未激活。

完整 F-007 任务卡见 [F-007 archive](../archive/task-cards/F-007-amap-qps-policy-runtime.md)。
