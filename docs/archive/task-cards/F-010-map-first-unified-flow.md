# F-010 地图优先统一规划流程与 DeepSeek 安全降级

- 最终状态：`DONE / IMPLEMENTED / PASS / OFFLINE`
- 完成日期：2026-09-13
- 长期决策：D-032
- 实施记录：[保留任务卡](../../project-management/f-010-map-first-unified-flow.md)
- 证据索引：[F-010 离线收口](../../project-management/evidence.md#f010-offline-closeout-20260913)
- 浏览器证据：`output/f010/20260913-223829-offline-browser/`

## 已交付边界

默认前端使用一条地图/列表优先的 V5 旅程：选点、完善需求、保存 revision、空间预检、生成确定性计划并查看 MapPlan/完整列表。DeepSeek 只补充叙述；generation 和一次 repair 最终仍非法时，结果降级为 `partial`，确定性计划与地图数据保留。

地图配置或加载失败不清空选择，也不阻止列表完成预检和计划。legacy/V2/V3/V4 的 API、严格解析、持久化和终态语义保持兼容。

## 验收结论

完整本地 Development 门禁和三条 loopback-only synthetic 浏览器旅程通过。真实高德、真实地图、DeepSeek、和风及 Git 交付均未执行、未授权；离线完成不得表述为真实 Provider UAT PASS。
