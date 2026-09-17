# F-008 可复现交付记录

此交付从 F-007 基点 3032d49c4f46167445650c71f7a570fc2c609f4a 恢复 F-008 已归档端点，包含77项候选（60修改、17新增）。来源为 F-009 启动前的独立备份及SHA-256清单；不将其冒称为本轮新实现或恢复不存在的中间提交。

## 验证

2026-09-17，本机 Windows、Python 3.13.3、Node 22.16.0，使用既有锁定依赖的隔离检出：Python格式/lint/mypy、前端格式/lint/TypeScript和synthetic构建通过；后端2574项、前端161项、机制55项、capture17项通过。先构建供后端StaticFiles测试使用；所有业务测试离线。

完整日志仅在原机器的 output/f019/20260917-140232-isolated-recovery 与 output/f019/20260917-142846-final-delivery 保留；文档中标为“本机历史证据”的路径不是随仓库交付的附件。原失败保留；本轮唯一业务源文件调整为空白行格式修正，无业务语义变化。

## 范围与限制

F-008 的历史正式结论仍为 INCONCLUSIVE，真实Provider UAT累计4/4；本次没有重启真实UAT或改判历史结果。新候选工程验证通过不等于真实高德、DeepSeek、和风或真实地图通过。

本批允许精确提交、PR和CI验证；最终合并事实以该提交对应PR为准。后续 F-009–F-018 使用联合端点交付，F-019 保持独立差异，不补造缺失的31项中间版本。

重现入口：项目规定运行时下执行 scripts/verify.ps1 -Phase RepositoryVerification（CI含锁定依赖安装）；离线复验可复用已有环境，先synthetic构建，再运行pytest、Vitest及scripts/tests中的Python/Node测试。禁止真实Provider凭证。

新增交付机制修正：CI明确使用RepositoryVerification完整门禁，保留开发/正式授权检查；构建先于需静态文件的pytest；Windows PowerShell5兼容；测试自建诊断目录；capture纳入门禁。5项新机制回归包含完整顺序、原授权拒绝与首失败停止。见 [验证摘要](./f008-validation.json)。
