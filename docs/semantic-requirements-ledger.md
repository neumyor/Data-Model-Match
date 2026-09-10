# 视觉语义需求可追溯台账

## 文档控制

| 项目 | 固定值 |
| --- | --- |
| 状态 | 审计后冻结候选；与阶段性验收文档一并提交和签署后生效 |
| 需求源 | `视觉数据集语义理解与任务匹配原型方案.docx` |
| 需求源 SHA-256 | `a2c4f4d2d53e7d1156f171b15f00def54f44b6ac89c761a9fae8eb0ee12dffa5` |
| 上位治理文档 | `docs/dataset-management-ui-phased-acceptance.md` v1.5 |
| 用途 | Phase 0 至 Phase 7 及 WP0 至 WP8 的唯一逐项签署台账 |

本台账将源方案要求与当前产品必须具备的派生约束分开记录。`SOURCE_REQUIREMENT` 必须完整实现或按源方案明确列为非交付/后续扩展；`DERIVED_PRODUCT_REQUIREMENT` 是为现有数据集管理产品、安全边界、真实模型测试、严格排序、研究归属和多 Agent 并行开发增加的交付治理，不得声称为源方案原文。唯一可签署的机器可读状态、artifact hash、责任人与独立验收人位于 `docs/governance/requirement-status-ledger.json`；本文件保留源文出处、业务意图和验收解释。

每条记录的 `证据` 指向最终应存在的工件类别。实际阶段签署还必须在 `docs/phase-records/phase-<N>-execution-record.md` 中记录具体命令、SHA-256、时间、退出码和独立验收结论。

## SOURCE_REQUIREMENT

### SRC-01 原始资产驱动的完整闭环

- 来源：第 1 节执行摘要和第 15 节结论。
- 处置：实现。
- 阶段/工作包：Phase 1 至 Phase 7；WP1 至 WP8。
- 输入：受管资源快照、固定 revision、自然语言任务需求。
- 输出：可解释的 Dataset Semantic Profile、Task Semantic Profile、DatasetTaskMatchResult 和用户可达的发现工作流。
- 依赖：SRC-02 至 SRC-19。
- 验证：未知数据集端到端导入、Profile 构建、任务检索、证据追溯、旧流程回归。
- 证据：最终 E2E 报告、Phase 7 benchmark、UI 自动化报告。
- 非目标：只展示静态字段、仅以名称/README/关键词检索、单一 relevance 分数。

### SRC-02 问题范围与任务覆盖

- 来源：第 2.1 节和第 2.3 节。
- 处置：实现。
- 阶段/工作包：Phase 0、2、4、7；WP0、WP2、WP4、WP8。
- 输入：原始图像、视频和视觉主导多模态资产。
- 输出：图像分类、检测、跟踪、语义/实例分割、姿态/关键点、动作/视频理解、视频异常检测、Re-ID/检索的 Schema、fixture、失败路径；首轮真实 benchmark 覆盖其中 4 至 6 类。
- 依赖：SRC-07、SRC-10、SRC-11、SRC-17。
- 验证：任务族契约测试；每个首轮任务族的 Ground Truth、任务特异字段、UNKNOWN/冲突路径；未入选任务族的 Schema/fixture/扩展兼容测试。
- 证据：任务覆盖表、Schema catalog、benchmark manifest、Phase 7 报告。
- 非目标：把未进入首轮真实 benchmark 的任务族静默删除或标记为不支持。

### SRC-03 明确非目标

- 来源：第 2.2 节。
- 处置：非交付，强制审计。
- 阶段/工作包：全部；主 Agent。
- 输入：任何实现、依赖引入或用户界面设计。
- 输出：无图片/视频物理转换服务、bbox 转换、目录重组、高精度同步、跨传感器标定、复杂时空对齐、本体/KG/全局概率推理、模型训练/微调/VVA/utility optimization。
- 依赖：无。
- 验证：代码审查、依赖审计、API 和 UI 路由审计。
- 证据：最终非目标审计。
- 非目标：受控视频抽帧仅作为临时 VLM 采样准备，不改变源媒体或提供格式标准化能力。

### SRC-04 不依赖已知数据集身份

- 来源：第 1 节、第 3.1 节、第 4 节和第 13 节。
- 处置：实现。
- 阶段/工作包：Phase 2 至 Phase 7；WP2 至 WP8。
- 输入：匿名化根目录、重命名路径、无 README、内部或新数据集。
- 输出：不依赖 benchmark 名称或 dataset-specific adapter 的结构/内容/匹配结论。
- 依赖：SRC-08 至 SRC-17。
- 验证：名称扫描、匿名化与重命名扰动、无 README、内部数据集测试。
- 证据：扰动报告、代码审查记录、Phase 7 报告。
- 非目标：`if dataset == COCO/MOT17/...` 或等价名称分支。

### SRC-05 处理图和语义边界

- 来源：第 5 节和第 10.2 节。
- 处置：实现。
- 阶段/工作包：Phase 2 至 Phase 6；WP2 至 WP6。
- 输入：资源快照、Dataset Sketch、inspection facts、受控视觉样本、任务需求。
- 输出：Survey -> inspection -> Structural Agent -> sampling -> VLM observation -> aggregation -> fusion -> matching 的固定处理图。
- 依赖：SRC-08 至 SRC-16。
- 验证：模块契约、允许工具清单、无任意命令执行、每阶段 artifact/evidence 连接测试。
- 证据：架构测试、工具调用测试、主 Agent wiring 检查。
- 非目标：复杂自主 Agent 编排、任意工具调用或未定义的推理阶段。

### SRC-06 Dataset Semantic Profile

- 来源：第 6 节。
- 处置：实现。
- 阶段/工作包：Phase 0、1、5；WP0、WP1、WP5。
- 输入：结构语义、内容聚合、sampling summary、evidence、unresolved。
- 输出：版本化 DatasetSemanticProfile，分离 structuralSemantics、contentSemantics、claims、observations、samplingSummary、evidence 和 unresolved。
- 依赖：SRC-08 至 SRC-13。
- 验证：Schema/type parity、版本迁移、跨资源引用、状态与 evidence 完整性、Profile 持久化。
- 证据：契约测试、存储测试、Phase 5 审阅记录。
- 非目标：用旧 DatasetProfile 或无版本静态 metadata 伪装语义 Profile。

### SRC-07 Structural 与 Content 语义及状态

- 来源：第 6.1 节、第 6.2 节、第 6.3 节和第 7.6 节。
- 处置：实现。
- 阶段/工作包：Phase 0、3、4、5；WP0、WP3、WP4、WP5。
- 输入：确定性/文档证据、LLM 结构解释、VLM observation、aggregation。
- 输出：任务、模态、组织、时序、监督、标注、资源角色/关系；对象、环境、视角、尺度、密度、遮挡、光照和运动；对已形成的 claim 保留证据来源、保守状态与不确定性。
- 依赖：SRC-09、SRC-11、SRC-12、SRC-13。
- 验证：事实与开放语义分离、冲突、不确定性和单样本不得升级为数据集结论。四态状态枚举、证据定位和强制覆盖率属于 DER-06 的派生质量门禁。
- 证据：Claim/Evidence Schema、fusion 测试、详情页 fixture。
- 非目标：将 VLM prose 或单 observation 直接保存为 dataset-level fact。

### SRC-08 Dataset Survey 与确定性 Inspection

- 来源：第 7.1 节和第 10.1 节。
- 处置：实现。
- 阶段/工作包：Phase 2；WP2。
- 输入：安全的原始数据根目录和受管资源 snapshot。
- 输出：directory patterns、file type distribution、representative paths、documentation/media/annotation/metadata candidates 和只返回事实的 inspection。
- 依赖：SRC-04、SRC-05。
- 验证：路径越界、符号链接、敏感文件、损坏输入、大文件、无 README、目录/文件数和读取/解码预算、取消检查点。
- 证据：Survey/inspection 测试、人工清点对照、Phase 2 计量记录。
- 非目标：遍历全部媒体内容或输出城市道路、航拍等开放语义。

### SRC-09 Structural Semantic Understanding

- 来源：第 7.2 节。
- 处置：实现。
- 阶段/工作包：Phase 3；WP3。
- 输入：Dataset Sketch、README/说明文本、少量 annotation sample、inspection facts。
- 输出：受限 inspection loop 后的 tasks、modalities、organization、temporal structure、supervision、annotation semantics、resource roles/relations 和 evidence/status。
- 依赖：SRC-08。
- 验证：受限 inspection loop、确定性事实不可臆测、格式错误/无效工具请求被拒绝，以及 detection/tracking/segmentation 的正确、不确定和冲突路径。
- 证据：Structural Agent 测试、Phase 3 记录。真实 API 成功/失败、配置与凭据治理由 DER-04 验收。
- 非目标：由 LLM 猜测确定性事实或开放式无限循环。

### SRC-10 代表性视觉采样

- 来源：第 7.3 节和表 10。
- 处置：实现；embedding 聚类、coverage optimization 和 active sampling 为后续扩展。
- 阶段/工作包：Phase 4；WP4。
- 输入：Survey、固定 snapshot、采样策略版本和 seed；已接受 Structural Agent artifact 可作为可选优化输入。
- 输出：图像分层样本；代表视频及时间均匀 Frame/Clip；SampleRef、strata、coverage、采样理由和时间基。
- 依赖：SRC-08。
- 验证：图像、视频/序列、视觉主导多模态；空候选、损坏媒体、覆盖计量、随机单样本与代表多样本比较。
- 证据：sampling 测试、真实样本记录、Phase 4 报告。
- 非目标：不受控随机抽样、全量媒体读取或源数据格式转换。源文第 7.3 节将 clustering/metadata 列为超大集采样思路而第 14.2 节又将 embedding clustering、coverage optimization 和 active sampling 列为后续扩展；本轮决议为 V1 使用可计量结构分层和确定性 fallback，只保留版本化可插拔接口。

### SRC-11 VLM Sample-level Semantic Extraction

- 来源：第 7.4 节和第 10.2 节。
- 处置：实现。
- 阶段/工作包：Phase 0、4；WP0、WP4。
- 输入：受控 SampleRef、显式 VLM 配置、固定 VisualObservation Schema。
- 输出：对象、环境、视角、尺度、密度、遮挡、光照、相机/目标运动的样本级 observation，含状态、sample ID、配置指纹和 evidence。
- 依赖：SRC-10。
- 验证：固定 observation Schema、样本级边界、视频时序上下文和失败 observation 可复核。
- 证据：Observation/aggregation 测试、Phase 4 记录。真实 VLM 成功/失败、预算和配置治理由 DER-04 验收。
- 非目标：annotation schema 判断、单样本 dataset fact、mock 代替真实 VLM 验收。

### SRC-12 Sample 到 Dataset 聚合

- 来源：第 7.5 节。
- 处置：实现。
- 阶段/工作包：Phase 4；WP4。
- 输入：已校验 VisualObservation、sampling summary、aggregation rule version。
- 输出：频次、observed/dominant 分布、样本数、覆盖、置信边界、UNKNOWN 和可引用 aggregation evidence。
- 依赖：SRC-10、SRC-11。
- 验证：单个 urban/aerial observation 不升级为 SUPPORTED；失败 observation 计数正确；阈值和分母正确。
- 证据：aggregation 测试、Phase 4 报告。
- 非目标：从单一 observation 得出全数据集的环境、视角或运动事实。

### SRC-13 Semantic Fusion 与 Evidence

- 来源：第 7.6 节、OpenForge 启发和第 13 节。
- 处置：实现。
- 阶段/工作包：Phase 5；WP5。
- 输入：文档、inspection facts、Structural Agent、VLM aggregation 和原始 evidence。
- 输出：完整 Profile claim、来源、status、conflict、unresolved 和可审阅 evidence chain。
- 依赖：SRC-06、SRC-07、SRC-09、SRC-12。
- 验证：文档与视觉矛盾、无媒体、媒体不支持、样本不足、冲突和 UNKNOWN。
- 证据：fusion 测试、API/UI evidence traversal、Phase 5 记录。
- 非目标：复杂概率图模型或选择性隐藏冲突。

### SRC-14 Task Semantic Profile

- 来源：第 8 节。
- 处置：实现。
- 阶段/工作包：Phase 0、6；WP0、WP6。
- 输入：自然语言任务需求与用户审核/结构化编辑。
- 输出：带 required/preferred、task-specific preferences、ID、revision 和创建时间的 TaskSemanticProfile。
- 依赖：SRC-02、SRC-07。
- 验证：任务解析成功及失败路径；required/preferred 语义、类型约束、编辑重校验和 revision。
- 证据：Task Profile 契约、真实 LLM 脱敏测试、任务检索 UI fixture。
- 非目标：把所有条件当成同等权重或用自由文本替代结构化 Profile。

### SRC-15 Compatibility 与 Suitability

- 来源：第 9 节。
- 处置：实现。
- 阶段/工作包：Phase 6；WP6。
- 输入：DatasetSemanticProfile revision、TaskSemanticProfile revision、匹配规则和权重配置。
- 输出：Compatibility、Suitability、命中、冲突、不确定项、explanation 和 evidence refs。
- 依赖：SRC-06、SRC-07、SRC-13、SRC-14。
- 验证：结构条件先于内容偏好；同结构 tracking 数据集因内容差异产生不同 Suitability；结果包含可解释的冲突和不确定项。默认排序资格、`null` 分数和 diagnostic 隔离由 DER-06 验收。
- 证据：Compatibility/Suitability 单元与集成测试、任务检索 UI、Phase 6 记录。
- 非目标：embedding-only relevance 替代硬约束，或以内容分数掩盖结构风险。

### SRC-16 模块边界与主流程 wiring

- 来源：第 10.1 节、第 10.3 节和第 10.4 节。
- 处置：实现。
- 阶段/工作包：Phase 1 至 Phase 7；WP1 至 WP7；主 Agent。
- 输入：所有已接受的模块 artifact。
- 输出：Survey、inspection、Structural Agent、Sampler、VLM Analyzer、Aggregator、Fusion、Task Agent、Matcher、evidence 的可达主流程。
- 依赖：SRC-08 至 SRC-15。
- 验证：ResourceStore、CLI、HTTP、SSE、配置、错误处理、生命周期、旧 API/页面回归。
- 证据：主 Agent wiring 清单、E2E、Phase 执行记录。
- 非目标：孤立模块、未注册路由或仅在测试内可调用的产品能力。

### SRC-17 Benchmark、Ground Truth、稳健性和消融

- 来源：第 11 节。
- 处置：实现。
- 阶段/工作包：Phase 0、7；WP0、WP8。
- 输入：15 至 30 个真实数据集、4 至 6 个任务族、50 至 100 条任务查询、版本化 Ground Truth、扰动版本和预批准阈值；Content Ground Truth 的人工浏览与官方说明 evidence。
- 输出：Structural/Content Ground Truth、扰动、指标、五项消融、两条研究基线、至少两个资源规模档位或等价受控上限的扩展性报告，以及可复现评估报告。
- 依赖：SRC-02、SRC-04、SRC-07、SRC-10 至 SRC-15。
- 验证：Precision/Recall/F1、Macro-F1/UNKNOWN rate、consistency、Hit@K/MRR/NDCG、效率与规模档位指标、RQ1 至 RQ4。
- 证据：benchmark manifest、Ground Truth、threshold manifest、calibration report、最终报告。
- 非目标：只运行 mock、只报告单次结果、在看见最终结果后调整阈值。

### SRC-18 推荐实施节奏

- 来源：第 12 节和表 15。
- 处置：实现。
- 阶段/工作包：Phase 1 至 Phase 7；WP1 至 WP8。
- 输入：冻结接口和上游已接受 artifact。
- 输出：Schema、Survey/Skills、Structural Understanding、Visual Sampling/VLM、Fusion、Task/Matching、Benchmark 的有序交付。
- 依赖：第 7 节波次和 artifact 接受状态。
- 验证：Phase execution record、依赖指纹、主 Agent 集成复核。
- 证据：Phase 0 至 Phase 7 记录。
- 非目标：未接受上游契约即并行定义下游公共语义。

### SRC-19 实施不变量

- 来源：第 13 节。
- 处置：实现，强制审计。
- 阶段/工作包：全部。
- 输入：所有实现、配置、测试、UI 和 benchmark。
- 输出：无名称捷径、工具事实优先、sample/dataset 分离、evidence、UNKNOWN、结构/内容分离、Compatibility/Suitability 分离。
- 依赖：SRC-04 至 SRC-15。
- 验证：静态扫描、契约、aggregation、matching、扰动、审计。
- 证据：代码审查、测试、Phase 7 报告。
- 非目标：为“完整性”引入本体、KG、复杂编排或数据格式转换。

### SRC-20 研究问题

- 来源：第 14.1 节。
- 处置：验收。
- 阶段/工作包：Phase 7；WP8。
- 输入：完整方案、消融、研究基线、固定预算和 Ground Truth。
- 输出：对 RQ1 结构理解、RQ2 少样本内容、RQ3 检索、RQ4 双层分解的预注册结论和失败分析。
- 依赖：SRC-17。
- 验证：每项 RQ 的实验、对照、指标、重复/置信规则和最终阈值。
- 证据：版本化 RQ 报告。
- 非目标：仅展示结果表而不回答研究问题。

### SRC-21 后续扩展

- 来源：第 14.2 节。
- 处置：非本轮交付，保留兼容扩展点。
- 阶段/工作包：Phase 0、1、4、6；WP0、WP1、WP4、WP6。
- 输入：版本化策略/规则接口。
- 输出：sampling policy、aggregation rule、matching weight 的显式版本和可替换边界；后续的 embedding clustering、coverage optimization、active sampling、OpenForge 式全局约束、Target View materialization（从能匹配到可直接加载）、utility feedback、视觉-语言和视觉-时序传感器多模态方向。
- 依赖：SRC-06、SRC-10、SRC-15。
- 验证：接口不将 embedding clustering、coverage optimization、active sampling、全局约束、Target View materialization、utility feedback、视觉-语言或视觉-时序传感器伪称为已完成。
- 证据：非目标审计、接口版本记录。
- 非目标：提前交付后续研究功能。

### SRC-22 定义性能力

- 来源：第 15 节。
- 处置：验收。
- 阶段/工作包：全部；主 Agent。
- 输入：SRC-01 至 SRC-21。
- 输出：基于数据集内在语义的 task-oriented visual dataset discovery。
- 依赖：全部源需求。
- 验证：最终验收清单和 Phase 7 端到端报告。
- 证据：最终签署记录。
- 非目标：仅从论文、名称或人工 metadata 建立数据集-任务关系。

### SRC-23 相关工作映射与非复现边界

- 来源：第 3 节和表 5。
- 处置：研究背景与设计映射，不复制外部实现。
- 阶段/工作包：Phase 0、7；WP0、WP8。
- 输入：EVAPORATE、Pneuma、KATS、OpenForge 的公开概念与项目自己的实现。
- 输出：稳定目标 Schema、代表性样本、Task-driven retrieval、Evidence/Status/UNKNOWN 四项设计映射及其评估说明。
- 依赖：SRC-05、SRC-07、SRC-10、SRC-13、SRC-15、SRC-20。
- 验证：设计报告说明各映射的本项目实现与源工作的边界。
- 证据：Phase 0 设计说明、Phase 7 RQ 报告。许可证/归属审计由 DER-07 验收。
- 非目标：宣称直接复现任一外部系统，或通过修改 `_reference_only/` 获得产品行为。

## DERIVED_PRODUCT_REQUIREMENT

### DER-01 现有产品兼容与版本迁移

- 来源：现有 DataModelMatch 产品基线和 AGENTS.md。
- 处置：实现。
- 阶段/工作包：Phase 0、1、6、7；WP0、WP1、WP6、WP7。
- 输入：旧 DatasetProfile、资源导入、`/api/compatibility` 和既有前端工作流。
- 输出：新旧 Profile/API 语义隔离、迁移、旧客户端可用和旧流程回归。
- 依赖：SRC-06、SRC-15、SRC-16。
- 验证：旧资源导入、列表、详情、模型匹配和 API 回归。
- 证据：契约/迁移/集成测试。
- 非目标：替换或重命名旧数据集-模型匹配语义。

### DER-02 异步 job、SSE、并发与发布安全

- 来源：现有产品 SSE 轨迹、AGENTS.md 和本验收文档第 4 节。
- 处置：实现。
- 阶段/工作包：Phase 0、1、7；WP0、WP1、WP7；主 Agent。
- 输入：Profile/Match 请求、snapshot revision、配置指纹、idempotency key。
- 输出：状态机、SSE、取消、重连、幂等、old revision winner、原子发布和受控错误。
- 依赖：SRC-06、SRC-15、SRC-16。
- 验证：并发等价请求、取消竞态、过期重放、worker 恢复、失败/部分成功不覆盖 complete Profile。
- 证据：RFC、契约测试、集成/E2E 测试。
- 非目标：未版本化的后台任务或静默覆盖最新 Profile。

### DER-03 数据集管理 UI 与任务检索 UI

- 来源：用户目标、现有产品 UI、UI 验收规格。
- 处置：实现。
- 阶段/工作包：Phase 1 至 Phase 7；WP7。
- 输入：版本化 Profile、job SSE、Task Profile、Match Result、UI fixture。
- 输出：四个 Profile 审阅区域、样本/聚合区分、证据/冲突/UNKNOWN、任务输入/审核/筛选/排序/解释。
- 依赖：SRC-06、SRC-13 至 SRC-16、DER-02。
- 验证：固定 DOM fixture、键盘、焦点、桌面/移动截图、断线重连和错误操作。
- 证据：UI acceptance manifest、Playwright 兼容报告、截图差异归档。
- 非目标：把新工作台伪装为现有数据集-模型兼容性页面。

### DER-04 安全、隐私、配置与真实模型测试

- 来源：AGENTS.md 和本验收文档第 3、4、8 节。
- 处置：实现，强制审计。
- 阶段/工作包：全部；主 Agent 和所有工作包。
- 输入：`config.llm.json`、本地数据、模型 endpoint、日志和测试产物。
- 输出：显式配置优先级、Git ignored 凭据/临时数据、脱敏日志、真实 LLM/VLM 成功与失败测试、安全路径边界。
- 依赖：SRC-08、SRC-09、SRC-11。
- 验证：配置合法且 ignored、无敏感信息扫描、成功/超时/空响应/格式异常/工具错误/部分失败、样本数据分类/外发批准/提供方 allowlist，以及不含秘密的请求语义指纹。
- 证据：脱敏测试报告、Git ignored 检查、Phase 记录。
- 非目标：环境变量覆盖 `config.llm.json`、打印 API Key、原始敏感媒体、完整 prompt 或模型回复。

### DER-05 多 Agent 派工、所有权与独立验收

- 来源：AGENTS.md 和本验收文档第 7、8、13、14 节。
- 处置：实现，强制治理。
- 阶段/工作包：全部；主 Agent。
- 输入：Requirement Record、工作包计划、artifact hash、worktree 基线。
- 输出：文件级所有权、artifact 接受状态、隔离 worktree、主 Agent wiring、独立测试与签署，以及可机械执行的 baseline/ownership/requirement-status 校验。
- 依赖：所有工作包。
- 验证：`governance-verify`、越界 diff 检查、依赖 SHA-256 检查、主 Agent 独立复跑、执行记录完整性。
- 证据：WP plan/report、Phase execution record、合并审阅。
- 非目标：依据子 Agent 自述完成验收，或让多个 Agent 并发修改共享路径。

### DER-06 严格匹配排序和证据质量门禁

- 来源：现有产品排序风险、AGENTS.md 和本验收文档第 3、4、6 节。
- 处置：实现，强制审计。
- 阶段/工作包：Phase 0、4、5、6、7；WP0、WP4、WP5、WP6、WP7、WP8。
- 输入：结构/内容 claim、证据状态、匹配规则和权重配置。
- 输出：四态 claim/evidence 定位规则；只有 `COMPATIBLE` 结果拥有正式 Suitability 分数和默认排序资格；其他状态的诊断比较不污染正式结果。
- 依赖：SRC-07、SRC-12、SRC-13、SRC-15。
- 验证：单样本不得升级、证据不足不产生高分、结构缺口不被内容分数掩盖、公共结果与诊断 artifact 隔离。
- 证据：契约、aggregation、matching、UI 和 benchmark 测试。
- 非目标：将这些严格产品规则伪称为 DOCX 第 9 节的逐字要求。

### DER-07 研究归属和许可证治理

- 来源：AGENTS.md、`_reference_only` 只读规则和项目安全规范。
- 处置：实现，强制审计。
- 阶段/工作包：Phase 0、7；WP0、WP8；主 Agent。
- 输入：相关工作引用、参考仓库、benchmark 数据和第三方素材。
- 输出：不直接复现的边界、许可证/归属审计、参考代码只读证明和 benchmark 数据许可记录。
- 依赖：SRC-17、SRC-23。
- 验证：许可证记录、引用与归属审计、`_reference_only` Git 状态检查。
- 证据：Phase 0 设计说明、Phase 7 benchmark 报告、许可证审计。
- 非目标：将研究背景或许可证流程误标为 DOCX 的功能性产品能力。
