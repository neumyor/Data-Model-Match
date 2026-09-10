# WP0-B 计划：语义 Benchmark 治理

## 目标

在 Phase 0 冻结一套不依赖真实媒体、凭据或数据集名称逻辑的 benchmark 治理资产，作为 Phase 7 实验和多智能体验收的唯一输入契约。交付物必须能够：

- 记录 15--30 个真实数据集、4--6 个任务族和 50--100 条任务查询；
- 记录每个数据集的许可证、来源、固定 revision、获取方式、任务族、Ground Truth 版本和扰动版本；
- 用脱敏 ID 关联 Structural/Content Ground Truth；
- 以固定公式计算结构、内容、Profile、一致性、排序和资源成本指标；
- 冻结 pilot 校准流程和“初步、待独立校准”的数值门槛；
- 明确 RQ1--RQ4、全部要求的消融实验和两条研究基线；
- 为后续 Agent 提供可执行 JSON Schema、模板和确定性契约测试。

## 非目标

- 不下载、提交或处理任何真实数据集、媒体、README、模型权重或用户数据。
- 不填写真实数据集名称、真实来源 URL、凭据、Authorization header 或可反推出身份的路径。
- 不实现 Dataset Survey、LLM/VLM 客户端、Profile 生成、HTTP/SSE、UI 或共享源代码 wiring。
- 不把 pilot 数值当作最终验收阈值；最终阈值必须经过独立校准、主 Agent 审批和变更记录。
- 不使用数据集名称分支、专用 adapter 或隐藏 UNKNOWN 的统计方式。

## 公共契约

| 资产 | 路径 | 用途 |
| --- | --- | --- |
| Benchmark manifest schema | `docs/semantic-benchmark/benchmark-manifest.schema.json` | 验证规模、数据集元信息、查询、切分和版本关联 |
| Benchmark manifest template | `docs/semantic-benchmark/benchmark-manifest.template.json` | 不含真实数据的脱敏填写模板 |
| Ground Truth schema/template | `docs/semantic-benchmark/ground-truth.schema.json`、`ground-truth.template.json` | 验证字段级人工标注和复核信息 |
| Perturbation rules | `docs/semantic-benchmark/perturbation-rules.json` | 固定扰动种类、输入范围、保持/改变的语义和随机种子 |
| Metric/protocol specification | `docs/semantic-benchmark/benchmark-protocol.md` | 公式、分母、实验矩阵、消融、基线和运行规则 |
| Threshold manifest | `docs/semantic-benchmark/threshold-manifest.json` | 明确 preliminary/pending 独立校准的数值门槛 |
| Threshold manifest schema | `docs/semantic-benchmark/threshold-manifest.schema.json` | 约束 preliminary/final 状态、校准证据和批准字段 |
| Mechanical asset validator | `tests/semantic_benchmark/benchmark_validator.py` | 校验跨字段计数、ID、split 闭包和引用闭包 |
| Deterministic metric tests | `tests/semantic_benchmark/test_metrics.py` | 对核心指标做无网络、无凭据、可重复验证 |

## 依赖

- 输入依赖：`docs/dataset-management-ui-phased-acceptance.md` 第 3、5、9、11 节以及源 DOCX 要求的规模与研究问题。
- 运行依赖：Python 3.11+ 标准库；测试不得依赖 `config.llm.json`、网络或真实媒体。
- 下游依赖：WP1--WP7 只能消费冻结后的 manifest、Ground Truth 和指标语义；任何字段或阈值变更必须按 Phase 0 变更控制记录。

## 允许与禁止修改路径

允许新增：

- `docs/semantic-benchmark/`
- `tests/semantic_benchmark/`

禁止修改：

- `pyproject.toml`
- `src/`
- `web/`
- `config.llm.json`
- 现有 `tests/` 文件
- `_reference_only/`

## 接口与失败语义

- 所有 ID 必须是脱敏稳定标识；schema 拒绝 URL 查询凭据、绝对本地路径和真实媒体引用。
- manifest 的 `datasetCount`、`taskFamilyCount`、`taskQueryCount` 必须与数组长度一致，并满足 15--30、4--6、50--100。
- `datasets[*].datasetId`、`taskQueries[*].queryId` 必须唯一；`split.datasetIds` 与 `split.queryIds` 的三个分组必须非空、两两互斥，并且并集精确覆盖对应数组的全部 ID。
- 每个 `groundTruthVersion` 必须在调用方提供的 Ground Truth 版本目录中解析；每个 `perturbationVersions[*]` 必须解析到 `perturbation-rules.json` 的 `ruleId`。合法字符串格式不等于已解析引用。
- 机械校验器的输入接口为 `validate_benchmark_manifest(manifest, ground_truth_versions, perturbation_rule_ids)`，返回稳定排序的错误字符串；非空即拒绝。校验器不得自行猜测目录、下载资源或把 placeholder 当作真实证据。
- 阈值状态机支持 `preliminary_pending_independent_calibration -> final_approved`。初步态必须为 pending 校准/批准且证据字段为 `null`；最终态必须有独立校准报告 ID、SHA-256、完成时间、批准人、批准时间和变更记录 ID。状态迁移由后续变更记录驱动，不能在查看最终结果后回填或改阈值。
- `benchmark-manifest.template.json` 保持候选模板，不是冻结 manifest；由于其 split 仍为占位不完整状态，机械校验必须拒绝它。不得新增伪造的 `benchmark-manifest.json` 或宣称 Phase 7 已完成。
- 结构/内容预测若没有可用标注，必须计入 `UNKNOWN`，不能从分母删除。
- 排序指标只对 Compatibility 为 `COMPATIBLE` 的正式结果计分；`PARTIALLY_COMPATIBLE`、`INCOMPATIBLE`、`UNKNOWN` 不进入默认 suitability 排名。
- 缺少有效样本、无效预测或缺失运行成本数据时，指标返回显式无效状态；测试覆盖这些规则。

## 验证命令

```sh
python3 -m unittest discover -s tests/semantic_benchmark -p 'test_*.py' -v
python3 -m json.tool docs/semantic-benchmark/benchmark-manifest.schema.json >/dev/null
python3 -m json.tool docs/semantic-benchmark/benchmark-manifest.template.json >/dev/null
python3 -m json.tool docs/semantic-benchmark/ground-truth.schema.json >/dev/null
python3 -m json.tool docs/semantic-benchmark/ground-truth.template.json >/dev/null
python3 -m json.tool docs/semantic-benchmark/perturbation-rules.json >/dev/null
python3 -m json.tool docs/semantic-benchmark/threshold-manifest.schema.json >/dev/null
python3 -m json.tool docs/semantic-benchmark/threshold-manifest.json >/dev/null
git diff --check
```

完成标准是上述文件全部存在、JSON 可解析、测试不访问网络/凭据且验证核心公式；未完成真实 benchmark，不宣称 Phase 7 通过。
