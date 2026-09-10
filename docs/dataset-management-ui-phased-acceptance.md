# 视觉数据集管理与任务匹配 阶段性验收文档

**文档控制**

| 项目 | 固定值 |
| --- | --- |
| 需求源 | `视觉数据集语义理解与任务匹配原型方案.docx` |
| 需求源修改时间 | 2026-09-09T19:44:21+0800 |
| 需求源 SHA-256 | `a2c4f4d2d53e7d1156f171b15f00def54f44b6ac89c761a9fae8eb0ee12dffa5` |
| 本文版本 | 1.5 |
| 文档状态 | `CANDIDATE`；在提交、全量治理校验和独立签署完成前，不得作为产品工作包的派发依据 |
| 文档所有者 | 主 Agent |
| 适用分支 | `codex/dataset-management-ui` |
| 关联需求台账 | `docs/semantic-requirements-ledger.md` |
| 关联执行记录 | `docs/phase-records/phase-<N>-execution-record.md` |
| 变更规则 | Phase 0 冻结后的公共契约、枚举、事件、默认值、验收阈值均须走第 13 节变更控制；未经主 Agent 批准不得改变。 |

## 0. 文档权威、发布与冲突处理

本文定义开发范围、阶段门禁、派工治理和最终验收，不以摘要示例取代机器可执行契约。源方案是功能目标和研究范围的权威来源；现有产品兼容性、安全边界、真实模型测试和 UI 交付要求属于派生产品约束，必须在需求台账中明确标记为 `DERIVED_PRODUCT_REQUIREMENT`，不得伪称为源方案原文。

下列资料发生冲突时，按从高到低的顺序处理；上层资料只在其明确覆盖的范围内优先：

1. 已批准且尚未回滚的第 13 节变更记录；
2. 已签署的 `docs/governance/governance-baseline.json` 和其引用的 ownership、requirement-status、contract、benchmark、UI manifest；
3. 版本化 JSON Schema 和受其约束的机器可读 manifest；
4. 已批准的接口 RFC、Benchmark 协议和 UI 验收规格；
5. 本验收文档；
6. 阶段或工作包执行记录、示例和 Agent 汇报。

执行记录只能证明实施和测试，不能修改公共语义。每次合并前必须验证引用资料的版本和 SHA-256 与执行记录一致；不一致即为阻断项。本文成为 `FROZEN` 基线的条件是：当前版本及关联台账、完整 benchmark manifest、contract/UI/ownership/requirement-status manifest 被提交到分支；`docs/governance/governance-baseline.json` 记录其 SHA-256、基线 commit、批准时间、主 Agent 和独立复核人；`governance-verify` 在该 commit 以零退出码通过。模板、历史报告或口头确认均不能代替冻结基线。

所有阶段使用以下状态：`PLANNED`、`IN_PROGRESS`、`BACKEND_READY`、`INTEGRATION_READY`、`PASSED`、`BLOCKED`、`SUPERSEDED`。`BACKEND_READY` 或子 Agent 的“完成”不等于阶段通过；`INTEGRATION_READY` 仅表示共享运行路径和用户可达入口已完成主 Agent wiring，仍须完成本阶段的独立验收才可为 `PASSED`。若后续审计发现冻结输入、测试或实现不再满足门禁，主 Agent 必须将阶段重开为 `BLOCKED` 或 `IN_PROGRESS`，不能保留“通过”标签。

`CANDIDATE` 期间只允许治理、契约审计和不改变已冻结公共语义的修复；不得派发或合并新的产品工作包。当前分支上已有的语义模块、测试和阶段报告一律视为**预基线实验工件**：在基线成为 `FROZEN`、输入 artifact 获 `ACCEPTED`、路径所有权复核通过且主 Agent 重新验收前，不能作为下游输入、不能标记为阶段能力，也不能接入共享 `ResourceStore`、HTTP、SSE 或 UI 路径。

### 0.1 候选期整改与冻结后派发

为消除“治理校验必须通过”与“基线尚未冻结”之间的歧义，执行模式严格分为两类：

| 模式 | 允许工作 | 禁止工作 | 校验结论 |
| --- | --- | --- | --- |
| `CANDIDATE_REMEDIATION` | 仅可补齐或审计 `docs/governance/**`、`docs/semantic-contracts/**`、`docs/semantic-benchmark/**`、`docs/semantic-ui-acceptance/**`、需求/阶段记录和相应的专属测试；可建立真实 benchmark 的脱敏清单、许可证与版本核验记录。 | 不得修改 `src/**`、`web/**`、`pyproject.toml`、共享路径、生产配置或把预基线实验工件接入产品。不得接受或消费产品 artifact。 | `governance-verify` 必须只出现本节列明的候选期阻断码：`BASELINE_NOT_FROZEN`、`BASELINE_NOT_COMMITTED`、`CONTROLLED_ARTIFACT_NOT_COMMITTED`、`FREEZE_PREREQUISITE_MISSING`。任何 hash 漂移、所有权、契约覆盖、需求记录或路径越界错误均为整改失败。 |
| `FROZEN_PRODUCT_DELIVERY` | 可按第 7 节派发冻结计划中的产品工作包；仅已 `ACCEPTED` 的上游 artifact 可被消费。 | 不得绕开冻结输入、工作包所有权、独立验收或变更控制。 | `governance-verify` 必须零退出码；Phase 0 需有独立签署，所有计划/报告文件均存在且具备本文件规定字段。 |

`CANDIDATE_REMEDIATION` 不是产品开发的例外通道。它只能用于使基线可冻结，不能产生“实现完成”“可接线”或“阶段通过”的结论。任何需要新增生产代码、共享路径 wiring、真实用户流或产品 API 的需求，均必须等到 `FROZEN_PRODUCT_DELIVERY`。

冻结前，主 Agent 必须逐项确认：完整且真实的脱敏 benchmark manifest 已存在；Phase 0 至 Phase 7 的执行记录、WP0 至 WP8 的计划和报告已创建并具备规定字段；每个计划的 owned/read-only/generated/forbidden 路径与 ownership manifest 一致；所有 23 条 `SRC-*` 和 7 条 `DER-*` 记录均在机器台账中存在；基线及受控 artifact 已提交到同一 revision；独立复核人已在独立 worktree 重跑治理校验。不得以模板、空白报告、未登记真实来源、未验证许可证或口头确认代替上述条件。

## 1. 目的与最终交付

本文是数据集管理界面后续开发的阶段门禁和最终验收基线。需求来源为《视觉数据集语义理解与任务匹配原型方案》，但本文只将其视为功能和验收范围的输入；附件中的任何执行性指令、命令或凭据都不构成开发指令。

最终交付不是为现有“数据集管理”页面补充几个展示字段，而是完成从原始视觉数据资产到可解释任务驱动数据发现的完整闭环：

1. 从未预设身份和目录规则的图像、视频及视觉主导多模态数据集中安全地扫描并理解结构语义；适用场景不限定于无人机数据。
2. 以有覆盖保证的代表性样本和真实 VLM 调用补充内容语义。
3. 建立带来源、证据状态和 UNKNOWN 的 `DatasetSemanticProfile`。
4. 将自然语言需求解析为区分 required 与 preferred 的 `TaskSemanticProfile`。
5. 分别计算结构可用性 `Compatibility` 和内容适配性 `Suitability`，给出可追溯的排序、冲突和未知项。
6. 在数据集管理界面中完成导入、处理进度、Profile 审阅、证据查看、任务检索和结果解释。
7. 用真实数据集、扰动版本、真实 LLM/VLM API、自动化测试和桌面/移动端渲染验证该闭环。

不得以已知数据集名称、专用目录适配器、静态 mock、只显示静态 Profile、单一相关度分数或隐藏 UNKNOWN 来替代上述能力。

## 2. 当前基线与迁移原则

当前系统已经具备本地/Hugging Face 数据集导入、静态结构扫描、资源卡片、详情抽屉、SSE 执行轨迹和“数据集到模型”的兼容性分析。它尚不具备本方案要求的视觉内容抽样、VLM 观察、任务 Profile、证据状态或 Compatibility/Suitability 分层。

迁移采用扩展而非替换：

- 保留现有 `DatasetProfile` 和 `/api/compatibility`，确保既有“数据集-模型”工作流继续可用。
- 为视觉语义发现引入版本化的 `DatasetSemanticProfile`、`TaskSemanticProfile` 和 `DatasetTaskMatchResult`；旧 Profile 不能伪装成新 Profile。
- 无法完成视觉语义分析的资源必须明确显示为“结构 Profile 已就绪、视觉语义未完成”或失败原因，不得填充臆测值。
- 任何 Profile 重新生成、采样或匹配均使用资源的固定快照和 `resolvedRevision`，并保留时间、配置摘要和证据引用。

## 3. 范围、非目标与不变量

### 3.1 覆盖的视觉任务

产品契约、解析器和测试 fixture 必须覆盖图像分类、目标检测、多目标跟踪、语义或实例分割、姿态或关键点、动作/视频理解、视频异常检测，以及 Re-ID/检索。Phase 7 的真实 benchmark 按源方案选择其中 4 至 6 个任务族和 15 至 30 个数据集；未进入首轮 benchmark 的任务族仍必须有 schema、确定性/失败路径 fixture 和扩展兼容测试，不能被删除或降为未支持。

任务覆盖不能只证明“数据集能被归类为此任务”。每一任务族还必须存储并验收其最小特有语义：

| 任务族 | 必需结构语义 | 必需内容或任务特异语义 |
| --- | --- | --- |
| 图像分类 | 类别/层级标签 | 对象或场景分布、长尾程度、域特征 |
| 目标检测 | `bbox`、类别 | 对象、尺度、密度、遮挡、场景 |
| 多目标跟踪 | `frame_id`、`track_id`、`bbox` | 时序连续性、对象、遮挡、目标/相机运动、视角 |
| 语义/实例分割 | pixel/instance mask | 场景、边界复杂度、小目标比例、类别覆盖 |
| 姿态/关键点 | keypoints/skeleton | 姿态、视角、遮挡、关键点可见性 |
| 动作/视频理解 | clip/video label、temporal segment | 动作类别、场景、时间动态、相机运动 |
| 视频异常检测 | video/clip/frame anomaly label | 正常/异常场景分布、时间稀疏性、异常类型 |
| Re-ID/检索 | identity/pair/ranking supervision | 身份多样性、跨相机/跨域变化、视角和光照 |

### 3.2 本轮明确不做

以下内容不作为本原型的交付项，且不能被悄然加入主流程：

- 图片/视频物理格式转换、bbox 表达转换或目录重组；
- 高精度时间同步、跨传感器标定与复杂时空对齐；
- 本体库、复杂知识图谱、全局概率推理；
- 模型训练、微调、VVA 仿真或下游效能优化；
- 以 COCO、MOT17、VisDrone 等已知名称为依据的主流程专用适配器。

### 3.3 全阶段不变量

1. 确定性事实只能由扫描和 inspection 工具产生；LLM/VLM 不能猜测 FPS、分辨率、文件数、行数或标注字段是否真实存在。
2. VLM 的每条输出只能是样本级 observation；只有聚合器可以形成数据集级内容语义。
3. 每个高价值语义结论必须具有 `VERIFIED`、`SUPPORTED`、`OBSERVED` 或 `UNKNOWN` 状态，以及可定位的 evidence。
4. 结构语义与内容语义分别存储；Compatibility 与 Suitability 分别计算。
5. 不确定时必须保留 `UNKNOWN`，不能用默认“匹配”掩盖证据不足。
6. 不执行导入资源中的代码、不安装其依赖、不读取模型权重；不得修改 `_reference_only/`。
7. `config.llm.json`、资源快照、临时样本和测试日志继续保持 Git ignored，且任何日志、页面、测试快照均不得泄露 API Key 或完整 Authorization header。
8. Profile job 是固定、受限的 DAG：Survey -> inspection 后，Structural Agent 与事实性采样准备可并行；VLM observation 依赖受控 SampleRef，aggregation 依赖 observation，fusion 仅在结构与聚合 artifact 均已接受后执行。结构结果可以作为后续采样策略的可选优化输入，但不得成为基础采样的隐式启动依赖。Agent 只能调用 allowlist inspection，不能执行任意命令、读取未授权路径、重写数据集或自行扩展处理阶段。
9. 从视频派生 Frame/Clip 仅用于受控抽样和 VLM 输入准备；必须保留时间基与 provenance，不能修改源数据、成为通用格式转换服务，或以派生帧替代原视频的时序证据。
10. 视觉主导多模态资源与 RGB 图像/视频同属范围。`thermal`、`depth`、`event` 和 `multimodal` 必须在 Schema、Survey/inspection、结构解析与失败路径 fixture 中受支持；真实 benchmark 至少包含一个视觉主导多模态数据集或明确记录其获取受阻并以同等可复核的真实替代数据集补齐。
11. 向外部 LLM/VLM 发送样本前，必须验证资源的数据分类、外发批准标识和允许的提供方；未获批准、包含受限个人数据，或无法确认提供方保留策略的样本必须被拒绝并形成可审计的 UNKNOWN/拒绝 evidence，不得发送。

职责边界必须按下表执行：

| 组件 | 可以产生 | 不得产生 |
| --- | --- | --- |
| 确定性工具 | 目录、媒体 metadata、表格/结构化文件字段、精确计数、采样与路径安全事实 | 场景、对象、视角、任务或标注开放语义结论 |
| LLM | 任务需求、标注字段语义、资源角色/关系、受证据约束的结构解释和融合建议 | FPS、分辨率、文件数、行数或未检查字段等确定性事实 |
| VLM | 受固定 observation Schema 约束的对象、环境、视角、尺度、密度、遮挡、光照和可观察运动 | annotation schema 判断、资源关系判断或把单一样本升级为数据集结论 |
| Aggregator/Fusion | 可复核的分布、状态、冲突、UNKNOWN 与数据集级 claim | 未有满足证据规则的值、对原始 evidence 的覆盖或删除 |

## 4. 先行接口设计门禁

阶段 1 的实现开始前，主 Agent 必须评审并冻结下列公开契约。字段使用明确的枚举、数组或有界对象；不得以无约束 `any` 或隐式字符串约定替代。

### 4.1 版本化的公共契约

Phase 0 的产物必须是可执行的 JSON Schema、Python 类型、前端类型、契约样例和契约测试，而不是下列示意 JSON 本身。所有对象必须定义必填性、枚举全集、默认值、数值范围和版本迁移；禁止使用无约束对象，包括 `object`、`dict[str, Any]`、`Record<string, unknown>` 或开放 JSON。

`UNKNOWN` 是明确的枚举值，不等同于 `null`、空数组、缺失字段或请求失败。未知原因以受控枚举表达，例如 `NO_EVIDENCE`、`INSUFFICIENT_SAMPLE_COVERAGE`、`UNSUPPORTED_MEDIA`、`MODEL_FAILURE`、`CONFLICTING_EVIDENCE`。

### 4.2 DatasetSemanticProfile

```json
{
  "version": 1,
  "resourceId": "dataset_xxx",
  "snapshotRevision": "fixed-revision",
  "generator": {
    "profileBuilderVersion": "1.0.0",
    "samplingPolicyVersion": "1.0.0",
    "aggregationRuleVersion": "1.0.0",
    "configurationFingerprint": "sha256:..."
  },
  "structuralSemantics": {
    "tasks": ["multi_object_tracking"],
    "modalities": ["RGB"],
    "sampleOrganization": "image_sequence",
    "temporalStructure": "sequence",
    "supervision": ["bbox", "track"],
    "annotationSemantics": ["claim_annotation_track_id"],
    "resourceRoles": [],
    "resourceRelations": []
  },
  "contentSemantics": {
    "objectCategories": ["claim_object_vehicle"],
    "environments": ["claim_environment_urban_road"],
    "viewpoints": ["claim_viewpoint_aerial"],
    "targetScale": "claim_target_scale",
    "objectDensity": "claim_object_density",
    "occlusion": "claim_occlusion",
    "illumination": ["claim_illumination_daylight"],
    "cameraMotion": "claim_camera_motion",
    "targetMotion": "claim_target_motion",
    "taskSpecificSemantics": ["task_specific_tracking"]
  },
  "observations": ["observation_frame_001"],
  "samplingSummary": "sampling_summary_001",
  "claims": ["claim_object_vehicle", "claim_annotation_track_id"],
  "evidence": ["evidence_readme_001", "evidence_sample_001"],
  "unresolved": [],
  "generatedAt": "ISO-8601"
}
```

下列强类型实体是 Profile 的最小组成，关系均通过稳定 ID 表示：

| 实体 | 最小字段与约束 |
| --- | --- |
| `Evidence` | `id`、`kind`（README/inspection/sample/LLM/VLM/aggregation）、`sourceRef`、`locator`、`stage`、`summary`、`snapshotRevision`；文本证据含文件和行/段定位，媒体证据含 `SampleRef`。 |
| `SampleRef` | `id`、`kind`（image/frame/clip）、相对文件路径、媒体内容哈希；视频样本必须另有 `videoPath`、`startMs`、`endMs`、`frameStart`、`frameEnd`、采样帧率或等价时间基。 |
| `VisualObservation` | `id`、`sampleRef`、`objectCategories`、`environments`、`viewpoints`、`targetScale`（UNKNOWN/tiny/small/medium/large/mixed）、`objectDensity`（UNKNOWN/low/medium/high/mixed）、`occlusion`（UNKNOWN/rare/moderate/frequent）、`illumination`、`cameraMotion`（UNKNOWN/static/moving）、`targetMotion`（UNKNOWN/slow/moderate/fast/mixed）、`vlmModel`、`configurationFingerprint`、`status`、`evidenceRefs`。任何空响应、格式错误、超时或不支持媒体均以 observation failure 记录，不能被静默忽略。 |
| `SemanticClaim` | `id`、`field`、`scope`（structural/content/task-specific）、`value` 或受控值分布、`status`、`evidenceRefs`、`aggregationRef`、`unknownReason`、`conflictRefs`。`VERIFIED` 必须关联确定性或显式文档证据；`SUPPORTED` 必须关联满足规则的多证据；`OBSERVED` 仅能引用样本。 |
| `ValueDistribution` | `value`、`observationCount`、`eligibleObservationCount`、`proportion`、`isDominant`、`evidenceRefs`。以此表达 `dominant` 与 `observed`，不允许把单一 observation 直接提升为数据集结论。 |
| `SamplingSummary` | `strategy`、`strata`、`candidateCount`、`selectedCount`、`successfulObservationCount`、`failedObservationCount`、`coverage`、`selectionSeed`、`selectionEvidenceRefs`。 |
| `TaskSpecificSemantic` | 使用任务判别联合类型，不允许开放扩展字段；字段至少覆盖第 3.1 节对应的长尾/域、边界复杂度/小目标、关键点可见性、动作/异常类型和时间稀疏性、身份多样性/跨相机跨域变化。 |

所有 `contentSemantics` 字段都必须追溯至 observation、聚合规则和 evidence。`unresolved` 是 `UnresolvedField[]`，每项含字段、原因、已尝试证据、下一步可执行 inspection 或采样动作。

### 4.3 TaskSemanticProfile 和 DatasetTaskMatchResult

```json
{
  "version": 1,
  "task": {"value": "multi_object_tracking", "importance": "required"},
  "required": {
    "modalities": ["vision"],
    "temporalStructure": "sequence",
    "supervision": ["tracking_ground_truth"]
  },
  "preferred": {
    "objectCategories": ["vehicle", "pedestrian"],
    "environments": ["urban_road"],
    "viewpoints": ["aerial"],
    "targetScale": ["small"],
    "objectDensity": ["high"],
    "occlusion": ["frequent"],
    "illumination": ["daylight", "night"],
    "cameraMotion": ["moving"],
    "targetMotion": ["moderate", "fast"],
    "taskSpecificPreferences": ["tracking_occlusion_challenge"]
  }
}
```

```json
{
  "datasetResourceId": "dataset_xxx",
  "taskProfileId": "task_xxx",
  "compatibility": "COMPATIBLE",
  "suitabilityScore": 0.84,
  "satisfiedRequirements": [],
  "matchedPreferences": [],
  "conflicts": [],
  "unknowns": [],
  "explanation": "",
  "evidenceRefs": []
}
```

`TaskSpecificPreference` 同样是与第 3.1 节一致的任务判别联合类型。Compatibility 枚举固定为 `COMPATIBLE`、`PARTIALLY_COMPATIBLE`、`INCOMPATIBLE`、`UNKNOWN`。`DatasetTaskMatchResult` 还必须包含匹配规则版本、Profile revision、Task Profile revision、权重配置指纹和结果生成时间。

Compatibility 与 Suitability 的决策表如下；这是排序和 UI 展示的硬规则：

| Compatibility | 触发条件 | 是否计算正式 Suitability | 是否进入默认排序 | UI 处理 |
| --- | --- | --- | --- | --- |
| `COMPATIBLE` | 每个 required 结构条件有正向证据且无冲突 | 是 | 是 | 显示分数、命中偏好、冲突与 UNKNOWN 内容项 |
| `PARTIALLY_COMPATIBLE` | 有已知缺失或未完全满足的 required 条件，但不存在确定性阻断 | 否，`suitabilityScore=null` | 否 | 单独显示，列出缺口；不允许高内容分数掩盖结构风险 |
| `INCOMPATIBLE` | 任一 required 条件有确定性冲突 | 否，`suitabilityScore=null` | 否 | 单独显示阻断证据 |
| `UNKNOWN` | required 条件没有冲突但证据不足 | 否，`suitabilityScore=null` | 否 | 单独显示缺失证据和建议的下一步检查 |

允许为 `PARTIALLY_COMPATIBLE` 生成内部诊断性内容比较，但它必须单独标为 diagnostic，不能写入正式结果、分数或默认排序。

### 4.4 生命周期、SSE、并发和接口兼容

- 新 API 固定为 `POST /api/dataset-semantic-profiles/jobs`、`GET /api/dataset-semantic-profiles/jobs/:jobId`、`GET /api/dataset-semantic-profiles/jobs/:jobId/events`、`POST /api/dataset-semantic-profiles/jobs/:jobId/cancel`、`POST /api/task-profiles`、`POST /api/dataset-task-matches/jobs`、`GET /api/dataset-task-matches/jobs/:jobId`、`GET /api/dataset-task-matches/jobs/:jobId/events`。它们不得复用语义不同的既有 `/api/match` 或 `/api/compatibility`。
- Profile 构建和任务匹配 job 通过 SSE 返回 `stage`、`progress`、`evidence`、`warning`、`result`、`error`、`end`。每个事件必须含 `jobId`、递增 `eventId`、时间戳和 schema version；事件顺序、结束状态、断线重连和最终结果读取方式在 Phase 0 写入协议测试。
- 每个 job 具有 `queued`、`running`、`partially_completed`、`completed`、`failed`、`cancelled`、`superseded` 状态。状态迁移、超时归属、重试次数和取消后保留/清理的产物均须明确。
- Profile 构建以 `(resourceId, snapshotRevision, profileSchemaVersion, configurationFingerprint)` 作为幂等键。相同键并发请求复用同一 job；不同快照并发时，仅与当前 `resolvedRevision` 一致的成功 job 可原子发布，旧 job 标记为 `superseded`，不得覆盖新版本。
- 失败或部分成功仅可保存为 job artifact 和失败 observation，不能覆盖最后一个完整 Profile，也不能被标记为 ready。
- 新的视觉 Profile API 与既有资源 API 使用显式版本字段；旧客户端读取不到新字段时必须仍能正常展示既有资源。
- 新的任务匹配 API 不替换既有模型兼容性 API。接口命名、请求、响应、错误码、SSE 生命周期、迁移和契约测试在 Phase 0 评审后冻结，依赖方才允许并行实现。

### 4.5 VLM 服务和真实模型测试决策

方案要求真实 VLM。公共 Schema/RFC 保持 provider 和部署无关；当前运行环境的首个已批准部署决策记录在 `docs/phase-records/phase-0-execution-record.md`，逻辑模型为 `MiniCPM-V-4.5`，使用 OpenAI Chat Completions 兼容的视觉消息 `messages[].content[]`，其内容为 `text` 加 `image_url`。该运行决策不修改公共接口，也不能被示例或 Agent 口头说明替代。v1 视频输入固定为 `frames_only`：视频只允许由受控抽帧/Clip 预处理转换为图像样本后发送，不能假定或暴露 native video 支持。

2026-09-09 的非业务 16×16 PNG 连通性探测在 60 秒限制内成功返回可校验 JSON；同日 `qwen3-vl-plus` 的 30 秒探测超时，`MiniCPM-V-4.5` 对 1×1 PNG 返回可诊断 400。这些只是历史部署选择的复核线索，不是 Phase 4 的验收证据。Phase 4 必须以当期配置重新执行脱敏 availability probe，并在执行记录中登记配置指纹、逻辑模型、经认证目录解析的部署摘要、输入媒体哈希、响应 Schema 校验、耗时、调用数、费用或费用不可得原因，以及成功和失败类别；不得保存凭据、原始敏感媒体、完整 prompt 或完整模型回复。

该选择不表示可从文本模型字段隐式继承视觉设置。VLM 配置必须以根目录 `config.llm.json` 中显式的 `vlm` 对象保存，并符合冻结的版本化配置 Schema：其 `endpoint`、`apiKey`、`model`、图片/视频输入限制、超时、单阶段调用上限、费用上限、重试和脱敏策略只能用于 VLM 请求。首个部署可以显式填写与文本服务相同的 endpoint 和凭据，但不能通过代码回退、环境变量或默认值静默继承；部署 ID 通过受认证模型目录按逻辑模型名解析，不能固化到版本控制文件。

文本 LLM 始终从根目录 `config.llm.json` 优先读取 `endpoint`、`apiKey`、`model`、`stream`。VLM 配置扩展必须有显式的优先级、解析器和敏感字段脱敏规则，且不得静默覆盖这些文本 LLM 字段。每个真实 LLM/VLM 阶段的最小测试集合为：成功、超时、空响应、格式异常、工具请求错误和部分样本失败；开始前校验配置存在、合法且字段非空，结束后校验配置仍处于 Git ignored 状态。每次真实调用还必须记录不含秘密和原始媒体的请求指纹，至少包含 prompt/template、工具/响应 Schema、采样参数、seed、timeout、retry policy、解析后的模型版本和非敏感配置。缺少配置、凭据、受认证模型目录、可用部署或外发批准时只能标记为 `BLOCKED`，不得用 mock、文本模型、文件名或历史探测报告计为通过。

## 5. 阶段计划与验收门禁

源方案的 Phase 1 至 Phase 7 表示能力建设顺序。为了避免把“独立模块测试通过”误称为产品完成，本文件另区分能力门禁与产品接入门禁：Phase 1 至 Phase 4 可以先达到 `BACKEND_READY`，但其中列出的页面、SSE 和用户可见状态必须由 WP7 接入并通过第 12 节 UI 规格后，才可达到 `INTEGRATION_READY` 或 `PASSED`。Phase 5 至 Phase 7 的最终通过同样依赖这些 UI 接入结果。任何执行记录必须分别列出已通过的后端行、待 WP7 交付的 UI 行和最终阶段状态。

除明确为未来扩展的项目外，每个 Phase 的验收记录必须包含入口条件、输出契约版本及 SHA-256、责任工作包、独立验收人、阻断项、验收命令与退出码、脱敏证据路径、代码 revision、配置指纹、开始/结束时间和签署结论。缺少任一字段不得标记为 `PASSED`。

### Phase 0 基线冻结与验收设计

**目标**：将原型方案转为可开发的公开契约、验收数据和 UI 信息架构。

**实现内容**

- 完成第 4 节的三个数据契约、枚举、错误码、SSE 事件和版本兼容策略。
- 明确 VLM 配置及真实 API 测试方式；配置默认优先级仍以根目录 `config.llm.json` 为准，任何扩展均不得静默覆盖现有 endpoint、apiKey、model 或 stream。
- 发布本文件第 6 节规定的全量需求追踪矩阵，覆盖源方案第 1 至 15 节，并对研究背景与后续扩展明确“实现/验收/非交付”的处置。
- 发布接口 RFC、JSON Schema、请求/响应样例、错误码表、SSE 协议、迁移方案、契约测试、benchmark manifest 格式、Ground Truth 格式、扰动规则和 UI 验收规格。
- 确定数据集详情页的四个固定审阅区域：结构语义、内容语义、样本与聚合、证据与未解决问题；确定任务检索工作区的输入、过滤、排序和解释区。
- 冻结指标公式、计算范围、随机种子、最小重复次数、pilot 标定协议和阈值 manifest 的状态机。若没有独立历史基线，Phase 0 只能冻结 `preliminary_pending_independent_calibration` 候选阈值；独立 pilot 后必须在任何最终 benchmark 结果可见前生成并批准 `final_approved` 阈值 manifest。状态枚举、迁移和审批字段必须由版本化 Schema 校验；阈值不得在看到最终结果后追溯调整。
- 冻结 job 运行时语义补充：错误码到 `retryable` 的映射、最大尝试次数、退避与 jitter 规则、attempt 计数、取消与完成竞态、worker 崩溃恢复、SSE 重放窗口过期行为、Profile 与 Match 的完整幂等键、最终原子发布语义及其契约测试。未完成该补充前，不得将 job runner 接入共享 `ResourceStore`、HTTP 或 SSE 路径。

**验收证据**

- 架构/接口评审记录、JSON 示例、契约测试用例清单和错误处理矩阵。
- VLM 连通性检查不会输出凭据；`config.llm.json` 存在、字段有效且继续被 Git 忽略。
- 所有已有 Python 测试和 Web 构建均通过，证明基线没有退化。
- 全量需求台账、工作包边界、共享文件所有权、合并波次和每个工作包的验证命令已经审批，并由 `governance-verify` 机械校验。

**阻断条件**

- VLM 服务、字段语义、版本迁移或 UNKNOWN 处理未明确。
- 新接口试图复用旧 `DatasetProfile` 字段而无法区分静态描述与语义推断。
- 阈值 manifest 被误标为最终阈值，或 job 运行时语义仍只停留在“后续明确”。

### Phase 1 统一语义 Schema 与持久化

**目标**：使管理系统可以安全地保存、读取、校验和展示版本化视觉语义 Profile。

**实现内容**

- 实现强类型 `DatasetSemanticProfile`、`TaskSemanticProfile`、`DatasetTaskMatchResult`、Evidence 和 Claim Status 契约。
- 将视觉 Profile 作为现有资源快照的关联产物持久化，不修改或污染原始数据快照。
- 提供 Profile 状态、版本、生成时间、固定 revision、失败原因和重新生成入口。
- 数据集详情页增加“视觉语义”入口及空、处理中、失败、已完成状态；未完成时不能展示伪造的内容语义。

**验收标准**

- 正常、缺字段、非法枚举、无效分数、跨资源引用、版本不兼容和空证据均有契约测试。
- 旧资源能继续在数据集列表、详情和模型匹配工作台中使用。
- 用户可在详情页区分静态 Profile 与视觉语义 Profile，且可查看各自的生成状态。
- 页面状态行由 WP7 接入并通过第 12 节固定 fixture、SSE 与桌面/移动验收；在此之前本 Phase 最多为 `BACKEND_READY`。

### Phase 2 Dataset Survey 与确定性 Inspection

**目标**：从任意安全的原始视觉数据目录中形成可复核的 `DatasetSketch` 和 inspection facts。

**实现内容**

- 扩展安全扫描以识别目录模式、文件类型分布、代表路径、README/说明文件、RGB/视觉主导多模态图像与视频候选、标注候选和结构化元数据候选。
- 为媒体、表格、JSON/JSONL/XML/Parquet 等增加只返回事实的 inspection 工具：格式、尺寸、帧数、字段、类型、样本数量、标注结构和资源关系线索。
- 数据集管理界面显示扫描范围、跳过项、候选资源和确定性证据；对超限、损坏、不支持文件和敏感文件显示可操作警告。

**验收标准**

- 可对无 README、重命名目录、混入无关文件、损坏标注和大文件限制返回可诊断结果，不崩溃、不越界扫描。
- 事实字段均可定位到文件或工具输出；不产生“城市道路”“航拍”等开放语义结论。
- 在至少一个分类、检测、跟踪、分割、视频和视觉主导多模态样本集上确认扫描结果与人工清点一致。
- Survey 不能以“扫描”名义遍历全部媒体内容。契约必须冻结目录项数、文件数、单文件读取字节数、annotation 行数、媒体 metadata/解码次数、总耗时和取消检查点的上限；证据中记录实际计量、跳过原因和终止条件。
- 候选资源与确定性 evidence 的页面状态由 WP7 接入并验证；在此之前本 Phase 最多为 `BACKEND_READY`。

### Phase 3 结构语义理解

**目标**：以 Dataset Sketch、文档、少量 annotation sample 和 inspection facts 推断任务、监督和资源关系。

**实现内容**

- 实现 Structural Agent：允许提出有限次后续 inspection 请求，工具只返回事实，Agent 再更新结构假设。
- 提取 tasks、modalities、sample organization、temporal structure、supervision、annotation semantics、resource roles 和 relations。
- 结构语义 UI 以字段、值、状态、证据和未知原因呈现，支持展开到 README 片段、标注字段和 inspection 结果。

**验收标准**

- 使用根目录 `config.llm.json` 完成至少一次真实 LLM 成功调用，并记录逻辑模型、实际部署、调用次数和脱敏错误信息。
- 至少覆盖 detection、tracking、segmentation 三类数据集；每类分别验证正确推断、UNKNOWN、结构冲突三个路径。
- 删除 README、匿名化根目录和重命名文件后，基础任务/监督结论保持可解释；证据不足时降为 `UNKNOWN`，不可借助数据集名称补全。
- LLM 响应格式异常、空响应、超时和无效 inspection 请求均被拒绝或明确失败，不会写入部分伪 Profile。
- 结构语义页面的字段、证据和 UNKNOWN 展示由 WP7 接入并验证；在此之前本 Phase 最多为 `BACKEND_READY`。

### Phase 4 代表性视觉采样、真实 VLM 与聚合

**目标**：由真实视觉样本得到受固定 schema 约束的 observation，并严格聚合为数据集级内容语义。

**实现内容**

- 实现图像分层抽样、视频“代表视频 + 时间均匀 Frame/Clip”抽样；大数据集保留可升级的覆盖式采样接口。
- V1 对超大数据集必须使用可计量的结构分层与确定性替代策略，记录候选数、每层配额、种子、覆盖损失和不可用原因。已有 metadata 可用于分组；embedding 聚类、coverage optimization 和 active sampling 是源方案第 14.2 节的后续扩展，V1 只要求保留版本化、可插拔的策略接口，不得将其伪称为已交付或静默退化为不受控随机抽样。
- 实现固定 `VisualObservation` schema：对象类别、环境、视角、目标尺度、密度、遮挡、光照、相机运动和目标运动。
- 实现 VLM 客户端、图像/视频输入准备、响应校验、超时与成本限制；每次 observation 绑定 sample ID。
- 实现聚合器，输出频次、dominant/observed 语义、样本数、覆盖维度、置信边界和 UNKNOWN。
- 对被 Phase 7 选入真实 benchmark 的每个任务族，完成其第 3.1 节任务特异语义的采集或可诊断 UNKNOWN 路径、聚合规则、Task Profile 偏好映射和 Ground Truth 字段；未被首轮 benchmark 选择的任务族至少完成 Schema、fixture 和失败路径验收。
- 数据集详情页展示样本集合、抽样理由、每个样本 observation 与聚合摘要；单个样本结论不得以数据集事实样式显示。

**验收标准**

- 使用已确认的真实 VLM API 完成至少一个成功请求；测试不打印图片原始敏感内容、完整请求或凭据。
- 至少在图像、视频/序列和视觉主导多模态三个真实样本集验证抽样分层、空候选、损坏媒体、VLM 超时、格式错误和部分样本失败。
- 聚合测试证明单个“urban/aerial” observation 不会直接成为 dataset-level `SUPPORTED` 结论；频次、阈值和状态符合已冻结规则。
- 随机单样本与代表性多样本两条路径均可运行，并产出可比较的覆盖和稳定性指标。
- 视频 Observation 的 SampleRef 可复核到视频、Clip 时间范围、帧区间和采样时间基；动作、异常和运动结论不得只依据脱离时间上下文的单帧。
- 样本、observation 与聚合页面由 WP7 接入并验证；在此之前本 Phase 最多为 `BACKEND_READY`。

### Phase 5 语义融合、证据和审阅体验

**目标**：产生完整、可审计、可保守表达的 Dataset Semantic Profile。

**实现内容**

- 融合文档、确定性 inspection、LLM 结构解释和 VLM 聚合，保留每项 claim 的来源、状态和冲突。
- 实现 `VERIFIED`、`SUPPORTED`、`OBSERVED`、`UNKNOWN` 规则和冲突检测，不覆盖原始证据。
- 完成数据集管理详情页：总览、结构语义、内容语义、抽样摘要、证据链、冲突/未解决项、完整执行轨迹及重新分析操作。
- 列表卡片只显示经过定义的摘要和状态；不得以“完整度”代替证据状态或掩盖未解决项。

**验收标准**

- 一个 Profile 能从任意关键结论导航至源文件、README 定位、inspection 记录或样本 observation。
- 文档与视觉观察矛盾时，界面和 API 同时显示冲突及证据，不选择性隐藏。
- 不支持的模态、无媒体数据集或样本不足的资源可完成结构 Profile，但内容字段保持 UNKNOWN 并有原因。
- 桌面与移动视图对长路径、长证据、空列表、失败和处理状态均无内容遮挡或不可达控件。

### Phase 6 自然语言任务解析与双层语义匹配

**目标**：实现 task-driven dataset discovery，而不是只保留现有数据集-模型兼容性。

**实现内容**

- 实现 Task Agent，将自然语言转换为有 required/preferred 重要性区分的 `TaskSemanticProfile`，支持用户审阅和必要的结构化编辑。
- 实现基于显式规则的 Compatibility：任务、模态、时序和监督条件为硬约束。
- 实现可配置的 Suitability：对象、环境、视角、尺度、密度、遮挡、光照与运动为可解释加权偏好。
- 建立任务检索工作区：输入任务、展示解析后的条件、选择资源范围、查看排序、筛选结构状态、展开命中/冲突/未知/证据。

**验收标准**

- `required` 不满足时必然为 `INCOMPATIBLE` 或 `PARTIALLY_COMPATIBLE`，不能由高内容分数抵消。
- 两个均满足 tracking 结构的数据集能因城市/自然、目标尺度、密度或视角产生不同 Suitability 和清晰原因。
- 匹配结果必含已满足条件、偏好命中、冲突、UNKNOWN 和 evidence refs；没有充分内容证据时不会以高分排序。
- 真实 LLM 测试至少覆盖一次任务解析成功及空响应、格式错误、超时或工具调用失败路径。
- 原有数据集-模型匹配工作台和新任务检索工作区均可独立使用，互不改变结果语义。

### Phase 7 Benchmark、稳健性、消融与最终 UI 回归

**目标**：以真实数据证明系统不是靠数据集名称、说明文本或单个偶然样本工作。

**实现内容**

- 建立 15 至 30 个真实数据集、4 至 6 个任务族、50 至 100 条任务查询的可复现实验清单；记录许可、获取版本和人工 Ground Truth。首轮 benchmark 之外的任务族按第 3.1 节保留契约和 fixture 验收。
- 建立 Structural Ground Truth 与 Content Ground Truth，覆盖任务、模态、时序、监督、标注语义、对象、环境、视角、尺度、密度、遮挡、光照和运动；对进入真实 benchmark 的每个任务族，还必须覆盖其第 3.1 节任务特异语义、UNKNOWN/冲突判定与人工复核规则。
- 增加匿名化根目录、文件/目录重命名、加入无关文件、删 README/部分 metadata、采样数量变化及内部/新数据集的扰动版本。
- 完成消融：Structure only、Visual only、Structure + Visual、single random sample vs representative multi-sampling、with vs without documentation。
- 增加两条研究基线：metadata/description-only retrieval，以及不做 Compatibility/Suitability 分解的单一 relevance score；它们与完整方案使用相同资源快照、任务查询、调用预算和排序评估协议。
- 对数据集管理、详情、任务检索、SSE 进度和错误状态完成桌面与移动端自动化渲染回归。

**验收标准**

- 报告 Structural Precision/Recall/F1、Content Macro-F1 与 UNKNOWN rate、Profile consistency、Hit@K/MRR/NDCG、LLM/VLM 调用次数、sample count 和延迟。
- 每项消融都有相同输入、固定版本和可复现命令。无模型的 metadata/description-only、Structure only 或单一 relevance 基线可以作为研究对照，但不得满足真实 Agent 系统验收；真实 LLM 与真实 VLM 路径必须在单独的成功和失败测试中通过。
- RQ1 至 RQ4 均有明确的实验、对照基线、指标、通过阈值、置信区间或重复规则、失败分析和版本控制报告；只报告运行结果而未回答研究问题不能通过。
- 冷启动与扰动测试未发现基于数据集名称的分支；代码审查和测试均证明无 `if dataset == ...` 类主流程逻辑。
- 所有阶段测试、Web 构建、API 契约测试、真实 API 测试和 UI 截图检查通过；失败用例均保留脱敏诊断证据。

## 6. 需求可追溯矩阵

本表是高层索引，不是逐项验收台账。`docs/semantic-requirements-ledger.md` 是人工可读的源文出处、业务意图和验收解释；唯一可用于签署的 Requirement Record 是 `docs/governance/requirement-status-ledger.json`。每项必须包含 `requirementId`、来源类型（`SOURCE_REQUIREMENT` 或 `DERIVED_PRODUCT_REQUIREMENT`）、状态、责任人、独立验收人、输入/输出 artifact 的 SHA-256 状态和验收证据。Markdown 台账与机器台账必须双向可追溯；任一缺失、ID 不一致或 hash 漂移均为阻断项。

Requirement Record 只能引用本文件已定义的 Phase 0 至 Phase 7 和 WP0 至 WP8。引用未定义阶段或工作包的记录无效，必须先完成本文件的版本化变更并定义目标、输入、输出、责任、门禁和证据。

| ID | 源方案 | 处置与交付 | 阶段/工作包 | 验收证据 |
| --- | --- | --- | --- | --- |
| RQ-01 | 1 执行摘要 | 实现完整 raw-data-grounded、多模态、可解释发现闭环 | 全部 | 最终 E2E 报告 |
| RQ-02 | 2 问题边界与任务范围 | 实现 8 类任务覆盖；不交付列明的格式转换、复杂时空对齐、KG、训练 | 0、2、4、7 | 任务覆盖与非目标审计 |
| RQ-03 | 3 方案来源 | 研究背景，不复制外部实现；记录 EVAPORATE/Pneuma/KATS/OpenForge 的设计映射 | 0、7 | 设计说明与 RQ 报告 |
| RQ-04 | 4 与 KATS 的差异 | 实现原始资产冷启动、样本 VLM、双层匹配，不依赖文献或名称 | 2–7 | 匿名化/无 README 测试 |
| RQ-05 | 5 总体架构与原则 | 实现 Survey、结构分析、视觉采样、融合和匹配主流程 | 1–7 | 架构测试和 E2E |
| RQ-06 | 6 Dataset Semantic Profile | 实现强类型 Profile、结构/内容分离、证据和 UNKNOWN | 1、5 | Schema/迁移/契约测试 |
| RQ-07 | 7 数据集语义理解流程 | 实现 Sketch、inspection、结构 Agent、抽样、VLM、聚合和融合 | 2–5 | 文件级证据和真实模型测试 |
| RQ-08 | 8 Task Semantic Profile | 实现 required/preferred 和任务特异偏好 | 1、6 | Task Profile 契约与解析测试 |
| RQ-09 | 9 语义匹配 | 实现规则 Compatibility、加权 Suitability、解释和排序隔离 | 1、6 | 决策表、排序和冲突测试 |
| RQ-10 | 10 实施设计 | 按模块、职责边界和主流程完成 wiring | 1–7 | 主 Agent 集成检查 |
| RQ-11 | 11 Benchmark 与评估 | 实现真实 benchmark、Ground Truth、扰动、指标和消融 | 0、7、WP8 | 固定 manifest 和评估报告 |
| RQ-12 | 12 推荐实施节奏 | 用本文件 Phase 和工作包波次执行 | 0–7、WP0–WP8 | 阶段门禁记录 |
| RQ-13 | 13 实施约束 | 作为全阶段不变量执行 | 全部 | 代码审查、安全审计 |
| RQ-14 | 14.1 RQ1–RQ4 | 作为最终研究验收，比较结构、内容、检索与双层分解 | 7、WP8 | RQ 对照实验报告 |
| RQ-15 | 14.2 后续扩展 | 非本轮交付；仅保留兼容扩展点，不得冒充完成 | 0、1、4、6 | 非目标审计 |
| RQ-16 | 15 结论 | 实现 task-oriented visual dataset discovery 的定义性能力 | 全部 | 最终验收清单 |

## 7. 多 Agent 并行开发治理

本节是大规模并行开发的强制执行规范。未经 Phase 0 接口冻结，不得启动依赖公共契约的工作包；没有主 Agent 的 wiring、独立 diff 审阅和验证，子 Agent 工作不得直接视为完成。`CANDIDATE` 期间产生的预基线实验工件不改变此规则，必须在冻结后按相同计划重新进行所有权、输入 hash 和独立验收，才可重新标记为 `ASSIGNED`、`IMPLEMENTED` 或 `ACCEPTED`。

### 7.1 工作包模板

每个工作包必须在派发前以以下格式记录：工作包 ID、目标、非目标、输入契约及版本/SHA-256、输出契约及版本/SHA-256、前置依赖、精确 `ownedPaths`、`readOnlyPaths`、`generatedPaths`、禁止修改路径、责任 Agent、指定模型等级、基线 revision、验证命令、验收交付物、风险、回退策略和交接对象。目录级“可写”描述无效；只能使用明确文件或无歧义的专属 glob。工作包没有这些字段，不允许派发。

工作包状态必须区分 `ASSIGNED`、`IMPLEMENTED`、`REPORT_SUBMITTED`、`ACCEPTED`、`INTEGRATED`、`BLOCKED`、`REJECTED`。只有 `ACCEPTED` 的输出 artifact 才可被下游工作包消费；只有主 Agent 完成共享路径 wiring 后才可标记 `INTEGRATED`。任何 Agent 发现输入契约、基线 revision 或所有权不一致时必须停止该工作包并标记 `BLOCKED`，不能以兼容分支、未记录 prompt 或临时字段自行修补。

### 7.2 文件所有权与工作包

下表的“写入范围”是并行期间的专属范围。任何未列路径及共享路径只允许主 Agent 修改；需要调整共享路径时，子 Agent 只提交建议或邻接模块，由主 Agent 统一集成。

| 工作包 | 目标和输出 | 依赖 | 写入范围类别 | 模型 |
| --- | --- | --- | --- | --- |
| WP0 | 公共 Schema、JSON Schema、错误码、SSE 协议、契约样例和迁移 RFC | 无 | 新增契约文档与契约 fixture | Terra Medium |
| WP1 | 语义 Profile 持久化、job 状态、原子发布、版本迁移 | WP0 已接受 artifact | 新增语义存储/作业模块及专属测试 | Terra Medium |
| WP2 | Dataset Survey、确定性媒体/表格/结构化文件 inspection | WP0 已接受 artifact | 新增 survey/inspection 模块及专属测试 | Luna Medium 或 Terra Medium |
| WP3 | Structural Agent、有限 inspection loop、真实 LLM 测试 | WP0、WP2 已接受 artifact | 新增 structural agent/prompt/测试模块 | Terra Medium |
| WP4 | 抽样、媒体准备、VLM 客户端、Observation 校验、聚合 | WP0、WP2、已批准 VLM 运行决策；WP3 结构 artifact 可作为后续策略优化输入 | 新增 sampling/vision/aggregation 模块及专属测试 | Luna Medium 或 Terra Medium |
| WP5 | Claim、Evidence、Semantic Fusion、冲突与 UNKNOWN | WP0、WP1、WP3、WP4 已接受 artifact | 新增 evidence/fusion 模块及专属测试 | Terra Medium |
| WP6 | Task Agent、Compatibility、Suitability、解释和排序 | WP0、WP5 已接受 artifact | 新增 task/matching 模块及专属测试 | Terra Medium |
| WP7 | HTTP/SSE 路由、取消/重连、数据集详情和任务检索 UI | WP0、WP1、WP5、WP6 已接受 artifact | 新增 API adapter、专属前端模块、E2E fixture | Terra Medium |
| WP8 | Benchmark manifest、Ground Truth、扰动、消融、E2E 和视觉回归 | WP2–WP7 已集成能力 | 新增 benchmark/测试/报告与忽略测试产物 | Luna Medium 或 Terra Medium |

以下为共享路径，任何时刻仅由主 Agent 修改：`src/datamodelmatch/resource_types.py`、`src/datamodelmatch/resource_store.py`、`src/datamodelmatch/resource_cli.py`、`web/server.ts`、`web/app.js`、`web/index.html`、`web/styles.css`、`pyproject.toml`。主 Agent 在工作包合并后负责将邻接模块接入这些共享路径。`docs/governance/ownership-manifest.json` 是唯一的精确路径所有权来源；本表仅为工作内容索引，不能替代 manifest。所有未在派工记录中明确登记的配置、构建、锁文件、测试注册、基线截图、生成物和文档索引也默认为主 Agent 所有。

派工前主 Agent 必须记录每个 worktree 的基线 revision 和工作树状态。合并前必须运行 `governance-verify`，检查冻结基线、需求/WP 状态迁移、依赖闭包、路径所有权、禁止路径、敏感文件模式、变更记录和验收证据；任何非零退出码均为合并阻断。随后检查 diff 仅触及 `ownedPaths` 或经批准的 `generatedPaths`，且不含密钥、原始敏感媒体、模型完整输出或未登记生成物。路径越界、契约漂移或合并冲突只能由主 Agent 裁决；失败工作包不得阻塞无依赖的工作，但其输出不得进入下游。

### 7.3 并行波次与合并顺序

1. Wave 0：WP0。接口 RFC、Schema、错误码、SSE 协议、测试 fixture 和迁移策略批准后冻结。
2. Wave 1：WP1 与 WP2 并行。它们只能使用已冻结的 WP0 输入输出。
3. Wave 2：WP3 与 WP4 并行。WP3 依赖 WP2 的 inspection，WP4 依赖 WP2 的 Survey；二者不修改对方模块。
4. Wave 3：WP5，主 Agent 先验证 WP1/WP3/WP4 的接口和 artifact。
5. Wave 4：WP6，随后 WP7；API/UI 不得抢先定义未冻结的业务语义。
6. Wave 5：WP8 和全量主 Agent 集成验收。

每个工作包使用独立 `codex/` 前缀分支或工作树。合并顺序固定为 `WP0 -> WP1/WP2 -> WP3/WP4 -> WP5 -> WP6 -> WP7 -> WP8`。下游启动条件不是“上游已汇报完成”，而是输入 artifact 已 `ACCEPTED`、版本/SHA-256 已写入派工记录且契约测试通过。禁止两个 Agent 同时修改共享路径，禁止为通过自己的测试而改变其他工作包的公共行为。

### 7.4 主 Agent wiring 清单

主 Agent 在每次合并后必须确认：类型和序列化、ResourceStore 读写、CLI 注册、HTTP 路由、SSE 生命周期、取消和重连、配置读取、错误码、权限/路径安全、前端状态、空/失败状态、旧 API 回归和测试 fixture 已连接。只存在独立模块而未接入用户可达主流程，视为未完成。

## 8. 每阶段提交与主 Agent 验收要求

每个 Phase 必须有一个 `docs/phase-records/phase-<N>-execution-record.md`。文件开头的 `Governance Fields` 代码块必须使用可机械定位的 `key: value` 行，至少包含：`phaseId`、`status`、`requirementSourceSha256`、`inputArtifacts`、`codeRevision`、`workPackageStatus`、`responsibleAgent`、`independentAcceptor`、`verificationCommands`、`workDirectory`、`startedAt`、`finishedAt`、`exitCode`、`environmentVersion`、`configurationFingerprint`、`realModelSummary`、`sanitizedEvidence`、`riskItems`、`blockers`、`rollbackOrReopen` 和 `approvedAt`。独立验收人不得等于实现 Agent、提交作者或本次共享路径 wiring 作者，且必须在独立 worktree 自行复跑验收。缺少这些字段，或证据不可重放/不可定位时，不构成验收证据。

每个阶段结束时，负责实现的 Agent 必须汇报：

1. 修改的文件、模块和用户可见能力；
2. 公开接口、存储格式、迁移策略和兼容影响；
3. 正常路径、边界条件、失败路径和 UI 渲染验证结果；
4. 是否执行真实 LLM/VLM 测试，以及使用的非敏感配置摘要；
5. 未覆盖风险、成本限制、依赖条件和下一阶段阻断项。

主 Agent 必须阅读关键 diff，独立运行相关测试，验证 API wiring、SSE 生命周期、配置读取、错误处理和页面接入。没有完成这些检查，阶段不能通过；子 Agent 的自述不构成验收证据。

真实 LLM/VLM 验收必须使用可重复的、受限次数的命令或测试入口。报告必须记录逻辑模型、经认证目录解析的部署摘要、调用次数、总耗时、成本或成本不可得原因、配置指纹和脱敏错误类别。缺少 `config.llm.json`、无效凭据、无部署或网络不可用时，测试可以标记为 `BLOCKED` 或依项目约定 `SKIPPED`，但绝不能被计为成功或替代真实模型验收。

每项失败或回退必须给出最小重现命令和下一步责任人。取消、超时、部分样本失败、格式异常、配置错误、路径拒绝、旧 revision、SSE 重连和并发幂等冲突是本系统的正式失败路径，不能只在日志中出现而不进入测试和执行记录。

## 9. 最终验收清单

最终版本只有在以下事项全部成立时才可宣告完成：

- [ ] 所有 Phase 0 至 Phase 7 的门禁和证据已通过。
- [ ] 导入未知或内部视觉数据集后，系统能从原始资产生成结构、内容、证据和 UNKNOWN 明确的 Dataset Semantic Profile。
- [ ] 系统未依赖数据集名称或专用 benchmark adapter 形成主流程结论。
- [ ] 用户可以在数据集管理界面审阅 Profile、样本、聚合、来源、冲突和未解决项。
- [ ] 用户可以输入自然语言任务并获得结构 Compatibility、内容 Suitability、排序和可解释证据。
- [ ] 结构不兼容不会被内容偏好分数掩盖；内容证据不足不会被伪造成匹配。
- [ ] 真实 LLM 与真实 VLM 均完成成功和失败路径测试，且配置和日志均未泄露凭据。
- [ ] 15–30 数据集、50–100 task query、扰动集、五项消融、metadata/description-only 基线和单一 relevance 基线已完成并形成可复现评估报告。
- [ ] 每个 RQ1–RQ4 都有预先冻结的通过阈值、重复/置信规则、失败分析和版本化报告。
- [ ] 每项公共契约、SSE job、并发 winner 规则、取消和迁移均已通过契约与集成测试。
- [ ] 工作包按第 7 节隔离实现，主 Agent 完成共享路径 wiring 和独立验收；冻结 commit 上的 `governance-verify` 为零退出码。
- [ ] 现有数据集-模型兼容性流程、资源导入与安全边界未退化。
- [ ] `_reference_only/` 未被修改，`config.llm.json`、`.datamodelmatch/` 和临时产物仍被 Git 忽略。

## 10. 已知前置风险

- VLM 首个提供方、逻辑模型和图像消息格式已完成连通性探测，但生产配置解析器、媒体预处理、预算执行和失败路径实现尚未存在；它们仍是 Phase 4 的硬依赖，不能以 mock 规避。
- 视频抽帧、媒体解码和多模态输入支持需要在 Phase 2/4 根据运行环境验证；不支持时应明确报错和记录 UNKNOWN，而不是静默降级。
- Benchmark 中的真实数据集受许可证、体积、网络和费用约束。验收数据清单必须在 Phase 0 固定；限制采样量和调用量，但不能取消真实 API 与扰动验证。
- 现有前端为原生 HTML/CSS/JavaScript。后续实现应延续此技术栈和现有 SSE 模式，除非单独评审证明替换是完成完整交付所必需。

## 11. Benchmark 与研究验收协议

Phase 0 必须将 benchmark 固定为版本控制的脱敏 `benchmark-manifest.json`，而非仅有模板。每一数据集记录许可、来源、固定 revision、获取方式、任务族、Ground Truth 版本和扰动版本；原始数据、媒体和含敏感样本仍保留在 Git ignored 位置。人工 Ground Truth 必须记录标注规范、标注人、复核人、争议解决规则和字段级置信状态。Content Ground Truth 的每个字段必须同时关联人工浏览 evidence 与官方说明 evidence；两者缺失或冲突时必须按冻结规则标记 `UNKNOWN` 或争议。每个已选择任务族的 Ground Truth 还必须包含第 3.1 节任务特异字段、UNKNOWN/冲突标签和所用 evidence locator。

指标规格必须定义 Precision/Recall/F1、Macro-F1、UNKNOWN rate、Profile consistency、Hit@K、MRR、NDCG、延迟、样本数、token 数和 LLM/VLM 调用数的公式、分母、任务范围、聚合方式和有效数据条件。它还必须定义至少两个资源规模档位或等价的受控 scan/sample 上限，并报告吞吐、资源消耗、限额触发与降级行为，以验证能否扩展到较大资产库。`preliminary_pending_independent_calibration` manifest 只能用于 pilot，不能满足最终质量门禁；独立 calibrator 完成 pilot、生成校准报告并由主 Agent 批准后，必须在任何最终结果可见前提交状态为 `final_approved` 的 manifest。所有放行阈值、随机种子、数据集/查询切分、调用预算和重复次数均由该最终 manifest 冻结；任何例外必须记录为未通过风险，不能在结果出现后修改门槛。

| 研究问题 | 对照与实验 | 最小结论 |
| --- | --- | --- |
| RQ1 结构理解 | 异构目录、无 README、重命名与 annotation 扰动 | Structural Agent 在结构 Ground Truth 上满足已冻结的准确性、保守性与稳定性门槛 |
| RQ2 少样本视觉内容 | 单随机样本、代表性多样本、不同样本预算 | 多样本策略在同预算或明确成本范围内改善内容质量/稳定性，且 UNKNOWN 不被压低为臆测 |
| RQ3 检索效果 | metadata/description-only、Structure only、Visual only、Structure + Visual | 完整方案在固定 task query 和预算下达到预先批准的排序优势或明确解释失败边界 |
| RQ4 双层分解 | 单一 relevance score、Compatibility + Suitability | 双层结果对结构冲突和内容偏好给出更准确、可复核的排序/解释，不能以总分掩盖 required 缺口 |

## 12. UI 验收规格

Phase 0 必须冻结桌面和移动 viewport、自动化工具、截图比对容差、场景 fixture、关键 DOM 测试选择器和失败归档路径。固定值以 `docs/semantic-ui-acceptance/UI-ACCEPTANCE-SPEC.md` 和 `docs/semantic-ui-acceptance/dom-fixture-manifest.json` 为准；该规格要求版本锁定的 Playwright 兼容 harness、浏览器二进制、baseline SHA-256、DPR、运行命令和离线 fixture。缺少 harness、浏览器二进制或 baseline 是 Phase 7 UI 验收的阻断失败，不得作为 skipped pass。详情页和任务检索页至少覆盖以下状态：未开始、排队、运行中、部分成功、完成、失败、取消、旧 revision、无权限、媒体不支持、无样本、UNKNOWN、冲突、结构不兼容和网络断线重连。

UI 验收必须检查：键盘可达性、焦点可见性、语义标签、长路径/长证据换行、表格/列表窄屏可用性、样本与 dataset-level 结论视觉区分、排序资格说明、取消和重试操作、错误信息可诊断性，以及所有动态结果在 SSE 重连后的一致性。桌面与移动端截图及其差异报告是验收证据；不通过截图检查不得以“功能接口已通”放行。

## 13. 契约变更控制

Phase 0 冻结后，任何 Profile 字段、枚举、默认值、错误码、SSE 事件、兼容性判定、排序资格、聚合规则、VLM 配置、benchmark 阈值或 UI 状态的变化均须在合并前提交 `docs/governance/change-records/CR-<id>.json` 唯一变更记录。记录至少包含变更 ID、当前/目标版本、兼容性分类（兼容、不兼容、紧急）、提出者、独立审阅人、主 Agent 批准人、批准时间、生效范围、变更原因、受影响 Requirement ID、受影响 artifact SHA-256、调用方/持久化/测试影响、迁移策略、迁移完成证据、回退策略、回退演练或不可演练理由、测试计划和重新验收范围。

变更未审批前，依赖原契约的 Agent 继续以冻结版本开发；不得通过口头约定、未记录的 prompt 变更或前端兼容分支改变公共语义。紧急变更仅限安全隔离或服务恢复，不得改变 Schema、枚举、排序、提示词、模型配置或阈值；合并前仍须登记 CR ID、影响 hash 和临时回退措施。任何版本化输入、Schema、RFC、manifest、类型、fixture、UI selector 或执行记录的 hash 漂移都必须触发受影响范围的重新验收。

## 14. 金标准派工与证据协议

每份工作包计划必须放在 `docs/phase-records/WP<N>-plan.md`，执行报告必须放在 `docs/phase-records/WP<N>-report.md`。计划至少包含下列可复制字段：

```text
workPackageId:
phase:
status:
goal:
nonGoals:
sourceRequirementIds:
inputArtifacts:
  - path:
    version:
    sha256:
outputArtifacts:
  - path:
    version:
    sha256WhenAccepted:
dependencies:
ownedPaths:
readOnlyPaths:
generatedPaths:
forbiddenPaths:
baseRevision:
responsibleAgent:
modelTier:
verificationCommands:
acceptanceDeliverables:
failureAndRollback:
handoffConsumer:
```

执行报告必须以同一 `workPackageId` 关联计划，并补充实际 revision、实际修改路径、每条验证的命令/退出码/时间/环境、真实模型调用的脱敏摘要、artifact SHA-256、未覆盖项和主 Agent 审阅结论。执行报告不能通过“全部完成”“测试通过”等无定位表述代替这些字段。

派发、整合和验收按以下规则执行：

1. 主 Agent 先建立或更新 `docs/governance/requirement-status-ledger.json`、工作包计划、`docs/governance/ownership-manifest.json` 和输入 artifact 指纹，再派发 Agent。`governance-verify` 必须在派发和合并前通过。
2. 子 Agent 只能在 `ownedPaths` 内工作，不得修改共享路径、其他工作包的专属路径、`_reference_only/`、真实数据或 `config.llm.json`。若需要共享路径变更，只能提交适配建议和验证证据。
3. 主 Agent 在任何合并前独立审阅 diff，重新运行该工作包的聚焦验证，并验证输入/输出契约、异常路径和路径所有权。
4. 主 Agent 负责唯一的 wiring：依赖注入、模块注册、ResourceStore、CLI、HTTP、SSE、配置读取、错误处理、生命周期、UI 接入和旧流程回归。任何未接入用户可达流程的模块均不是产品交付。
5. 任务中的真实模型、UI 自动化和 benchmark 不共享“通过”结论：真实模型通过证明外部模型路径；UI 通过证明渲染与交互；benchmark 通过证明质量与稳健性。三者缺一不可，且任何一个都不能由 mock、静态 fixture 或子 Agent 自述替代。
