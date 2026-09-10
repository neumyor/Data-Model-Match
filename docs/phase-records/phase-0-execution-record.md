# Phase 0 基线冻结与验收设计 执行记录

## Machine-Readable Governance Fields

```text
phaseId: PHASE-0
phase: Phase 0
status: BLOCKED
requirementSourceSha256: a2c4f4d2d53e7d1156f171b15f00def54f44b6ac89c761a9fae8eb0ee12dffa5
workPackageStatus: WP0-A=PENDING_SIGNED_BASELINE; WP0-B=BLOCKED_MISSING_REAL_BENCHMARK_MANIFEST; WP0-C=PENDING_SIGNED_BASELINE
verificationCommands: see Verification Log; current freeze verification exit code PENDING
workDirectory: /Users/yimingniu/Code/DataModelMatch
startedAt: 2026-09-09; exact time PENDING
finishedAt: PENDING
exitCode: 0_RECORDED_HISTORICAL_COMMANDS; CURRENT_FREEZE_VERIFIER_PENDING
environmentVersion: uv 0.12.10; Python 3.9.6; Bun 1.4.2; exact environment fingerprint PENDING
realModelSummary: historical MiniCPM-V-4.5 probe recorded; Phase 0 real-model acceptance summary PENDING_REDACTED
sanitizedEvidence: tests/semantic_contracts/; tests/semantic_benchmark/; tests/semantic_ui_acceptance/; docs/phase-records/P0.1-job-runtime-semantics-report.md
riskItems: missing real benchmark manifest; unsigned governance baseline; independent acceptor unassigned; current revision uncommitted
rollbackOrReopen: REOPEN_PHASE_0_ON_HASH_DRIFT_OR_GOVERNANCE_VERIFIER_FAILURE; no rollback executed
approvedAt: PENDING
sourceRequirementIds: [SRC-01, SRC-02, SRC-03, SRC-04, SRC-05, SRC-06, SRC-07, SRC-08, SRC-09, SRC-10, SRC-11, SRC-12, SRC-13, SRC-14, SRC-15, SRC-16, SRC-17, SRC-18, SRC-19, SRC-20, SRC-21, SRC-22, SRC-23]
derivedRequirementIds: [DER-01, DER-02, DER-03, DER-04, DER-05, DER-06, DER-07]
inputArtifacts: docs/dataset-management-ui-phased-acceptance.md@28e38cbd891751b08d2cb3d9f58bd945441de7ceae956b3081cd95c7da99bd1d; docs/semantic-requirements-ledger.md@5e4f1bd6ec6bccf2f787408965db17f1710996f8a4bddacad9bd37e474ed2689; docs/semantic-contracts/contract-manifest.json@5a21d7dfafb8909307067b7f103937d5ecbbcbcd481d9cf355a868f4bcba4ed5; docs/semantic-contracts/job-runtime-semantics-v1.json@9c16628857b0e2c402da5fba31ab0146487315615b2881421ecd0090dbab5adc; docs/semantic-ui-acceptance/UI-ACCEPTANCE-SPEC.md@14fd23630b6abc40627c561c16c340c7b34410f1941aea1c427c89a5e087f07d; docs/semantic-ui-acceptance/dom-fixture-manifest.json@e6a5317a7f7ee7b430a2d14658c0bc2d384531185c77b22907c468beeda5d946; docs/semantic-benchmark/benchmark-manifest.template.json@e3d50df4c647a467a9200fc1a6b2237b3d03bf0e664dee0220df166fab633ce3
outputArtifacts: docs/governance/governance-baseline.json@c5191b4802db9293da445a6e9649019ad91a5e655526e205bfe64dcdbb8869d5[BLOCKED_UNSIGNED]; docs/governance/ownership-manifest.json@cef21bde664f457c6d9fb4063bfc7d2fdd8a305caf91ecd6a66663f4c8412850[BLOCKED_UNSIGNED]; docs/governance/requirement-status-ledger.json@c1934d6665c3a6a3b59d9c8676ec09df6829f156e0e3955567572d55a10cb478[BLOCKED_UNSIGNED]; docs/semantic-benchmark/benchmark-manifest.json@PENDING_MISSING; docs/phase-records/phase-0-execution-record.md@PENDING_AFTER_THIS_EDIT
codeRevision: 3ab448b5c3449f4d14287076cc187591f2f8aa92
configurationFingerprint: PENDING_REDACTED; secret-bearing config fingerprint not recorded
evidencePaths: tests/semantic_contracts/; tests/semantic_benchmark/; tests/semantic_ui_acceptance/; docs/semantic-contracts/; docs/semantic-benchmark/; docs/semantic-ui-acceptance/; docs/governance/governance_verify.py; docs/phase-records/P0.1-job-runtime-semantics-report.md
startTime: 2026-09-09; exact time PENDING
endTime: PENDING
responsibleAgent: Main Agent
independentAcceptor: PENDING_UNASSIGNED
approvalStatus: BLOCKED
approvalTime: PENDING
blockers: missing real benchmark manifest; unsigned governance baseline/ownership/requirement ledger; governance verification not signed and accepted; independent acceptance unassigned; current revision not committed as the freeze baseline
signoff: PENDING
```

**状态：`BLOCKED`。公共契约与 P0.1 运行时 job 语义已通过，但当前没有完整真实 benchmark manifest、已签署的治理基线或共享路径 wiring；不得开始共享 `ResourceStore`、HTTP 或 SSE wiring。**

本记录是 `docs/dataset-management-ui-phased-acceptance.md` 第 5 节 Phase 0 的实施和验收证据索引。公共契约、治理协议和 UI 验收规格已于 2026-09-09 经主 Agent 审阅和独立验证；2026-09-09 的金标准审计随后发现基线工件、真实 benchmark manifest、工作包模板和契约一致性缺口，因此此前“冻结”表述仅代表历史候选，不能作为当前放行结论。P0.1 已冻结共享 runner 必须遵守的重试、退避/jitter、attempt、取消、恢复与重放语义，但它不证明生产 runner、HTTP、SSE 或 UI 已实现。Phase 4 的生产 VLM 实现和 Phase 7 的独立 pilot/浏览器回归仍是后续阶段门禁。

## 签署元数据

| 字段 | 当前值 |
| --- | --- |
| `phaseId` | `Phase 0` |
| 状态 | `BLOCKED` |
| 需求源 SHA-256 | `a2c4f4d2d53e7d1156f171b15f00def54f44b6ac89c761a9fae8eb0ee12dffa5` |
| 基线代码 revision | `3ab448b5c3449f4d14287076cc187591f2f8aa92`，当前治理整改尚未提交 |
| 工作目录 | `/Users/yimingniu/Code/DataModelMatch` |
| 责任人 | 主 Agent |
| 独立验收人 | `UNASSIGNED_INDEPENDENT_ACCEPTOR` |
| 配置指纹 | 未记录秘密；真实模型配置仍须在 Phase 3/4 按 DER-04 记录 |
| 批准时间 | 未签署 |
| 阻断项 | 完整 benchmark manifest、threshold Schema/状态机、governance baseline/ownership/requirement status 校验、所有 WP plan/report 结构化证据、独立验收人 |

## 范围

- 工作包：WP0-A 公共契约、WP0-B benchmark 与研究验收、WP0-C UI 验收规格。
- 非目标：不实现生产模块、不改动既有资源数据模型或 HTTP 路由、不启动任何依赖未冻结契约的下游工作包。
- 共享路径所有者：主 Agent。WP0 子 Agent 不得修改 `src/datamodelmatch/resource_types.py`、`src/datamodelmatch/resource_store.py`、`src/datamodelmatch/resource_cli.py`、`web/server.ts`、`web/app.js`、`web/index.html`、`web/styles.css` 或 `pyproject.toml`。

## VLM 配置决定与探测证据

冻结的 VLM 配置为 OpenAI Chat Completions 兼容的视觉模型，逻辑模型标识为 `MiniCPM-V-4.5`。文本 LLM 仍以根目录 `config.llm.json` 的 `endpoint`、`apiKey`、`model` 和 `stream` 为最高优先级；视觉配置只能作为其明确命名的 `vlm` 扩展，不能覆盖这些文本字段。

| 项目 | 决定或结果 |
| --- | --- |
| 传输 | 当前文本 LLM 的 HTTPS Chat Completions endpoint |
| 认证 | `config.llm.json.vlm.apiKey` 仅在内存构造 Authorization header；首个部署显式使用与文本服务相同的已忽略凭据，不存在代码回退 |
| 逻辑模型 | `MiniCPM-V-4.5` |
| 部署解析 | 调用受认证的 `/v1/models` 目录，以逻辑模型名解析当前 `START` 状态部署；部署 ID 不写入版本控制配置 |
| 图像输入 | OpenAI `messages[].content[]`，使用 `text` 加 `image_url`；仅允许已生成或经安全采样的受限媒体 |
| 最小成功探测 | 2026-09-09：16×16 红色 PNG 的 data URL，60 秒超时；响应返回 `{"imageAccepted":true,"dominantColor":"red"}` |
| 已知失败边界 | 同日 `qwen3-vl-plus` 在 30 秒内未返回；`MiniCPM-V-4.5` 对 1×1 PNG 返回可诊断的上游预处理 400。两类失败都必须纳入客户端错误分类和测试。 |
| 本地配置验证 | 已在被 Git 忽略的 `config.llm.json` 中写入符合 `vlm-configuration.schema.json` 的显式 `vlm` 对象，并完成无凭据输出的 Schema 校验。 |
| 日志要求 | 禁止记录 API Key、Authorization header、完整请求、完整媒体和完整模型原文响应；仅记录脱敏错误类别、逻辑模型、部署解析结果摘要、耗时、样本 ID 和响应结构校验结果。 |

版本化 VLM Schema/RFC 已冻结媒体格式、尺寸上限、超时、单阶段调用上限、费用上限、重试和脱敏规则。生产客户端必须在 Phase 4 按此契约执行并完成真实成功与失败路径测试。

## 验收项目

| ID | 项目 | 负责人 | 证据位置 | 验收状态 |
| --- | --- | --- | --- | --- |
| P0-01 | Dataset、Task、Match、Job、Error、SSE 的闭合 JSON Schema、Python/前端类型和契约 fixture | WP0-A | `docs/semantic-contracts/`、`tests/semantic_contracts/` | 主 Agent 通过并冻结 |
| P0-02 | VLM 配置优先级、媒体限制、失败分类和连通性协议 | WP0-A + 主 Agent | `docs/semantic-contracts/`、本记录 | 主 Agent 通过并冻结 |
| P0-03 | SSE 事件序列、断线重连、取消、幂等键、旧 revision winner 和迁移 RFC | WP0-A | `docs/semantic-contracts/` | 主 Agent 通过并冻结 |
| P0-04 | 15–30 数据集、4–6 任务族、50–100 查询的 manifest、Ground Truth、扰动、指标、RQ1–RQ4 与阈值标定协议 | WP0-B | `docs/semantic-benchmark/`、`tests/semantic_benchmark/` | 模板与指标协议通过；真实 benchmark manifest 尚未存在，Phase 0 阻断 |
| P0-05 | 详情页/任务检索 UI 状态、viewport、截图、DOM、键盘和 SSE 一致性规格 | WP0-C | `docs/semantic-ui-acceptance/`、`tests/semantic_ui_acceptance/` | 主 Agent 通过并冻结 |
| P0-06 | 需求源 1–15 节可追溯性与所有工作包边界 | 主 Agent | `docs/dataset-management-ui-phased-acceptance.md`、`docs/semantic-requirements-ledger.md` | 审计整改中：需要机器可读 requirement status、精确 ownership 和来源归属修正 |
| P0-07 | 基线回归 | 主 Agent | 测试日志 | 通过：既有 Python 69 tests + 5 subtests，Web 构建通过 |
| P0-08 | 配置与忽略规则 | 主 Agent | `.gitignore`、Git ignored 检查 | 已通过：`config.llm.json` 与 `.datamodelmatch/` 保持 ignored |
| P0-09 | job 运行时语义补充：retryable 映射、退避/jitter、attempt、取消竞态、worker 恢复、SSE retention/replay 与发布测试 | 主 Agent | `docs/semantic-contracts/job-runtime-semantics-v1.json`、`P0.1-job-runtime-semantics-report.md`、`tests/semantic_contracts/test_job_runtime_semantics.py` | 通过：25 passed、401 subtests；生产执行器仍须在后续集成中遵守并验证该策略 |

## 后续阶段硬门禁

1. Phase 4 必须实现 VLM 配置解析、媒体限制、预算执行与真实成功/超时/空响应/格式异常/媒体不支持/部分失败测试；没有这些证据，不能验收视觉内容语义。
2. Phase 7 必须按冻结的协议进行独立 pilot 标定，并在最终 benchmark 执行前提交并批准最终数值阈值。当前阈值 manifest 仅是明确标记的 pilot 候选，不能作为最终质量结论。
3. Phase 7 必须安装并版本锁定浏览器自动化 harness、浏览器二进制和截图基线；缺失时 UI 视觉验收失败，不能跳过。
4. P0.1 已通过。主 Agent 开始共享 ResourceStore、HTTP、SSE 或 job runner wiring 前，必须将本记录、P0.1 报告和策略文件提交并签署为同一冻结基线；生产执行器必须按该策略补齐集成和故障注入测试。

## Phase 0 放行判定

公共 Schema/治理子门禁只有满足以下全部条件才能签署为通过：

- 所有 P0-01 至 P0-09 均有可复核证据，完整真实 benchmark manifest 已通过 schema/引用校验，且 P0-07 不再受测试环境阻断。
- Schema、文档、样例和测试的字段、枚举、默认值、错误码、SSE 生命周期与迁移策略一致。
- VLM 配置合同包含成功、超时、空响应、格式错误、媒体不支持和部分样本失败的可执行测试计划。
- benchmark 的 pilot 标定方法、阈值 manifest 状态和“最终 benchmark 前审批”的不可变规则已冻结；最终数值阈值作为 Phase 7 的前置门禁执行。
- 主 Agent 已阅读所有 WP0 diff，运行聚焦验证及基线回归，并将审阅结论追加到本记录。
- `docs/governance/governance-baseline.json`、ownership manifest 和 requirement-status ledger 已在同一提交记录当前 SHA-256、批准时间和独立验收人，且 `governance-verify` 零退出码通过。

Phase 0 当前为 `BLOCKED`。只有上述治理与 benchmark 缺口关闭并完成签署后，才可将契约子门禁标为 `BACKEND_READY`；本记录在此之前不得被用于证明新 job API、SSE 或 ResourceStore wiring 已可验收。

## 主 Agent 审阅日志

| 时间 | 工作包 | 审阅范围 | 结果 |
| --- | --- | --- | --- |
| 2026-09-09 | WP0-C | `UI-ACCEPTANCE-SPEC.md`、DOM/fixture manifest、Bun manifest 验证 | 通过。独立执行 `bun test tests/semantic_ui_acceptance/test_manifest.test.mjs`，6 个测试通过、358 项断言通过。Phase 7 浏览器 harness 尚未安装，被正确记录为后续 UI 放行阻断项，未被伪装为已完成。 |
| 2026-09-09 | WP0-B | benchmark/Ground Truth Schema、模板、扰动、阈值治理、指标协议和确定性指标测试 | 通过。独立执行 `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src uv run --no-project --with pytest --with pyarrow pytest -q tests/semantic_benchmark/test_metrics.py`，8 个测试通过。经复核，15 个脱敏 dataset 槽位、4 个任务族和 50 个查询均在源方案范围内；最终阈值仅能在独立 pilot 后、最终 benchmark 前审批冻结。 |
| 2026-09-09 | 基线 | 既有 Python 测试、Web 构建、Git 忽略规则与名称专用逻辑扫描 | 通过。执行 `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src uv run --no-project --with pytest --with pyarrow pytest -q tests/test_*.py`，69 个测试及 5 个子测试通过；执行 `cd web && bun run build` 通过。`config.llm.json` 与 `.datamodelmatch/` 仍被 `.gitignore` 覆盖；扫描未发现 COCO、MOT17 或 VisDrone 名称专用的主流程分支。 |
| 2026-09-09 | WP0-A | 公共 JSON Schema、Python/前端类型、fixture、Schema/类型 parity、SSE/job/迁移/VLM RFC | 通过。独立执行 `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src uv run --no-project --with pytest --with pyarrow pytest -q tests/semantic_contracts`，10 个测试及 379 个子测试通过；复核后补齐了 Python 与前端类型契约，Schema catalog 的 15 个入口均有有效 fixture。 |
| 2026-09-09 | Phase 0 最终 | 全量 Python、UI manifest、Web 构建、JSON、VLM 本地配置和 Git 忽略 | 通过。执行 `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src uv run --no-project --with pytest --with pyarrow pytest -q tests`，87 个测试及 384 个子测试通过；根目录执行 UI manifest 测试，6 个测试及 359 项断言通过；`cd web && bun run build` 通过；所有治理 JSON 可解析，显式 `vlm` 对象符合冻结 Schema，且配置仍被 Git 忽略。 |

## 冻结工件摘要

以下 SHA-256 是 2026-09-09 审计前候选的历史记录。它们不能单独绑定当前冻结基线，因为本文件、需求台账、ownership/requirement-status manifest、实际 benchmark manifest 和后续整改工件未在此表中。当前权威指纹必须由 `docs/governance/governance-baseline.json` 在同一提交中重新生成；任一工件发生变化时，必须遵循验收文档第 13 节变更控制，并重新运行相应契约测试。

| 工件 | SHA-256 |
| --- | --- |
| `docs/semantic-contracts/contract-manifest.json` | `5a21d7dfafb8909307067b7f103937d5ecbbcbcd481d9cf355a868f4bcba4ed5` |
| `docs/semantic-contracts/schema-catalog.json` | `69fdb215e067fb9feb06e4a8e296fc256f9d481206044a0722c5a2027c6c04e4` |
| `docs/semantic-contracts/type-parity-manifest.json` | `5a049e140415e78ce75a2387d5ec05cab75e0111ca6a9c9381b0e8998153e936` |
| `docs/semantic-contracts/semantic-contract-rfc.md` | `d5f9fb49fed01f6d0b10485e66e45114c5676037bffab8f01a8403ac911e72d5` |
| `docs/semantic-contracts/job-runtime-semantics-v1.json` | `9c16628857b0e2c402da5fba31ab0146487315615b2881421ecd0090dbab5adc` |
| `docs/semantic-benchmark/benchmark-manifest.schema.json` | `dc020c44e07345a06106487423f357b5f3ca90f0d2f1ff7ece9f95ca74cc7f8e` |
| `docs/semantic-benchmark/ground-truth.schema.json` | `62da72df2e720260bd501cd4339fe0e2403b3b32eb78fa926d7f226c33cb0430` |
| `docs/semantic-benchmark/threshold-manifest.json` | `5cc3835eee1e0d8b11fd60f19d0f40f09b1803e405db1bad8ad46fdd01cee2e5` |
| `docs/semantic-ui-acceptance/dom-fixture-manifest.json` | `e6a5317a7f7ee7b430a2d14658c0bc2d384531185c77b22907c468beeda5d946` |
