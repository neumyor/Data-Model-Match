# DOCX 方案一致性与金标准就绪度审计

## 审计范围

| 项目 | 值 |
| --- | --- |
| 审计对象 | `docs/dataset-management-ui-phased-acceptance.md` v1.5 及其引用的台账、契约、benchmark、UI 和治理工件 |
| 唯一功能需求源 | `/Users/yimingniu/Downloads/视觉数据集语义理解与任务匹配原型方案.docx` |
| 需求源 SHA-256 | `a2c4f4d2d53e7d1156f171b15f00def54f44b6ac89c761a9fae8eb0ee12dffa5` |
| 审计日期 | 2026-09-09 |
| 审计结论 | `CANDIDATE_CONFORMANT_NOT_FROZEN` |

本文只审核 DOCX 的功能计划是否被完整保留，以及现有治理资料是否足以作为多 Agent 派发基线。DOCX 中的功能、研究范围和非目标是需求权威；安全、现有产品兼容、真实模型、UI、并发与并行开发治理属于明确标记的派生约束。

## DOCX 覆盖结论

| DOCX 内容 | 可追溯需求 | 验收文档锚点 | 结论 |
| --- | --- | --- | --- |
| 第 1 节与第 15 节的原始资产闭环、内部数据冷启动和定义性能力 | `SRC-01`、`SRC-22` | 第 1、5、9 节 | 已覆盖 |
| 第 2 节范围、八类任务与明确非目标 | `SRC-02`、`SRC-03` | 第 3 节、Phase 2/4/7 | 已覆盖；未把格式转换、KG、训练或专用 adapter 混入交付 |
| 第 3 节 EVAPORATE、Pneuma、KATS、OpenForge 的设计来源与非复现边界 | `SRC-23` | 第 6 节、Phase 0/7 | 已覆盖；仅保留设计映射和归属审计 |
| 第 4 节对 KATS 的 raw-data-grounded、VLM 和双层匹配差异 | `SRC-04` | 第 1、3、5、11 节 | 已覆盖；匿名化和无 README 测试为硬门禁 |
| 第 5 节架构和职责边界 | `SRC-05` | 第 3.3、Phase 2–6 | 已覆盖；固定 DAG、事实/开放语义边界和工具 allowlist 已冻结 |
| 第 6 节 Dataset Semantic Profile 与结构/内容语义 | `SRC-06`、`SRC-07` | 第 4.2、Phase 1/5 | 已覆盖；Evidence、状态、UNKNOWN、冲突和任务特异语义均为契约要求 |
| 第 7 节 Survey、inspection、结构分析、采样、VLM、聚合、融合 | `SRC-08` 至 `SRC-13` | Phase 2–5 | 已覆盖；样本到数据集聚合、视频时间基和失败路径不得省略 |
| 第 8 节 Task Semantic Profile | `SRC-14` | 第 4.3、Phase 6 | 已覆盖；required/preferred 和任务判别偏好为闭合类型 |
| 第 9 节 Compatibility 与 Suitability | `SRC-15` | 第 4.3、Phase 6 | 已覆盖；结构硬约束、正式评分和默认排序资格已分离 |
| 第 10 节模块边界与主流程 | `SRC-16` | 第 5、7、8、14 节 | 已覆盖；主 Agent 独占 wiring，孤立模块不算产品交付 |
| 第 11 节 benchmark、Ground Truth、扰动、指标与消融 | `SRC-17` | 第 5.7、第 11 节 | 已覆盖；真实 benchmark、五项消融、两条研究基线和规模档位均为硬门禁 |
| 第 12 节实施节奏 | `SRC-18` | Phase 0–7、WP0–WP8 | 已覆盖；依赖波次和合并顺序已固定 |
| 第 13 节实施约束 | `SRC-19` | 第 3.3、13 节 | 已覆盖；名称捷径、样本升级、UNKNOWN 隐藏和语义混合均被禁止 |
| 第 14.1 节 RQ1–RQ4 | `SRC-20` | 第 5.7、第 11 节 | 已覆盖；阈值、重复/置信规则和失败分析是最终验收项 |
| 第 14.2 节后续扩展 | `SRC-21` | 第 3.2、Phase 4/6 | 已覆盖；保留版本化扩展点，不将其伪称为本轮完成 |

`docs/semantic-requirements-ledger.md` 将以上内容拆为 23 条 `SRC-*` 记录；`docs/governance/requirement-status-ledger.json` 包含相同的 23 条源需求和 7 条 `DER-*` 派生需求。审计未发现 DOCX 功能、非目标、研究问题或任务族被静默删除或降级。

## 金标准就绪度

下列条件已具备：

- 公共 Schema、类型投影、SSE、错误、并发和 VLM 配置有版本化契约与测试。
- 结构与内容、Compatibility 与 Suitability、样本 observation 与数据集 claim 的边界已明确。
- Phase 0–7 的执行记录与 WP0–WP8 的计划/报告均已存在，且含机器可定位字段。
- 共享路径、专属路径、模型等级、依赖波次、主 Agent wiring 和独立验收职责已定义。
- 需求、契约、UI、benchmark 与治理 artifact 均有 hash、变更控制和验证入口。

下列条件尚未具备，因此当前文档**不能**标记为 `FROZEN` 或作为产品工作包派发依据：

1. `docs/semantic-benchmark/benchmark-manifest.json` 尚不存在；必须是 15–30 个真实数据集、4–6 个任务族、50–100 条查询的脱敏清单，并以 ignored identity registry 提供可复核的许可证、来源、修订和获取证据。
2. 所有受控 artifact 和治理基线尚未在同一分支 revision 提交，且未取得独立复核签署。
3. 基线状态仍是 `CANDIDATE`，因此 `governance-verify` 的冻结校验不可为零。
4. 预基线语义模块只是实验工件；尚未经过冻结输入、主 Agent wiring、独立验收、真实模型与 UI 产品级测试。

## 审计后的执行规则

- 在 `CANDIDATE_REMEDIATION` 模式，只可完成文档、契约、真实 benchmark 资料核验和治理整改；不得派发或合并产品实现。
- 产品并行开发只能从 `FROZEN_PRODUCT_DELIVERY` 开始，并且每一工作包只能消费已 `ACCEPTED` 的上游 artifact。
- `governance-verify` 在候选期只能包含验收文档第 0.1 节列明的冻结阻断码；任何 hash 漂移、路径所有权、契约覆盖或需求台账错误都应立即阻断整改。
- Phase 7 才能宣布整体完成；所有前置 Phase 的 `BACKEND_READY`、预基线测试或子 Agent 自述均不是最终验收。
