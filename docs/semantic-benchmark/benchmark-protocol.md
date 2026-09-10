# Semantic Benchmark Protocol v1

## 1. Scope and freeze

This protocol is the Phase 0 evaluation contract for the raw-data-grounded visual dataset semantics system. The final benchmark uses 15--30 real datasets, 4--6 task families, and 50--100 task queries. The checked-in manifest contains only de-identified IDs and metadata; media and sensitive annotations remain outside Git in approved ignored storage.

The fixed execution tuple is:

`(manifestId, manifest revision, Ground Truth revision, perturbation revision, code revision, seed, model configuration fingerprint)`

Any result without this tuple is exploratory and cannot satisfy Phase 7.

## 2. Required manifest and Ground Truth

Each dataset record contains only the governance fields required by the DOCX protocol: license, source, fixed revision, acquisition method, task family, Ground Truth version, and perturbation versions. Each query records task family, query revision, Ground Truth version, and perturbation versions. The manifest also fixes the dataset/query counts, split, seed, and de-identification policy.

Ground Truth is field-level and reviewed. It must record the annotation protocol, de-identified annotator and reviewer IDs, dispute rule, expected values, status, confidence, review state, and rationale. `UNKNOWN` is a labeled outcome, not a missing row. A conflict must be represented by a Ground Truth rule or a separate perturbation, never silently resolved by the evaluator.

## 3. Metrics

All metrics are deterministic over a frozen run artifact. A prediction with no valid output is mapped to `UNKNOWN`; it is not dropped.

### 3.1 Structural Precision/Recall/F1

For each structural claim record, compare the predicted set `P_i` with the Ground Truth set `G_i`, after normalizing only the frozen enum representation:

- `TP = sum_i |P_i ∩ G_i|`
- `FP = sum_i |P_i - G_i|`
- `FN = sum_i |G_i - P_i|`
- `Precision = TP / (TP + FP)`; if the denominator is zero, the metric is invalid.
- `Recall = TP / (TP + FN)`; if the denominator is zero, the metric is invalid.
- `F1 = 2 * Precision * Recall / (Precision + Recall)`; if both are zero, F1 is zero once the dataset has valid labeled records.

The report includes micro totals and per-task-family breakdowns. `UNKNOWN` predictions contribute no TP and do contribute FN for non-empty Ground Truth; this preserves the cost of missing evidence.

### 3.2 Content Macro-F1 and UNKNOWN rate

For every required content field, calculate one-vs-rest F1 over the fixed value vocabulary plus the explicit abstention class `UNKNOWN`. `UNKNOWN` is not a semantic content value, but it is included in Macro-F1 so that missing evidence is penalized rather than hidden. `Content Macro-F1` is the arithmetic mean of all valid one-vs-rest class F1 values across fields; fields with no labeled support are reported invalid rather than silently removed from the benchmark.

`UNKNOWN rate = count(predicted field values equal UNKNOWN) / count(all evaluated content fields)`.

Both metrics keep failed calls, unsupported media, empty responses and insufficient coverage in their denominators after mapping them to `UNKNOWN`. For example, with field truth `[urban, rural]` and prediction `[urban, UNKNOWN]`, the per-field classes are `urban`, `rural`, and `UNKNOWN`, with F1 values `1`, `0`, and `0`; that field contributes `1/3` to Macro-F1 and `1/2` to UNKNOWN rate.

### 3.3 Profile consistency

Run the same frozen input at least three times per condition. For each field, compare the normalized claim including explicit `UNKNOWN`:

`Profile consistency = matching field values across adjacent repeated runs / (field_count * (repeat_count - 1))`.

The evaluator records both field-level and whole-profile exact-match rates. Whole-profile exact match is diagnostic and does not replace the field-level metric.

### 3.4 Retrieval

For each query, use the judged relevant dataset IDs and the returned ranking:

- `Hit@K = 1` when any relevant ID occurs in the first K positions, otherwise `0`; report the mean over all queries.
- `RR = 1 / rank(first relevant result)` or `0` when no relevant result occurs; `MRR = mean(RR)`.
- `DCG@K = sum_{r=1..K} (2^rel_r - 1) / log2(r + 1)`.
- `NDCG@K = DCG@K / IDCG@K`, with `0` when the query has no judged relevant item.

Only results with `COMPATIBLE` eligibility may enter the formal suitability ranking. Diagnostic comparisons for other compatibility states are reported separately and cannot improve Hit@K/MRR/NDCG.

### 3.5 Resource metrics

For every profile or query run, record elapsed milliseconds, selected sample count, input/output token counts when supplied by the provider, and LLM/VLM API call count:

- `latency_p95_ms`: nearest-rank 95th percentile over valid run latencies;
- `mean_samples`: total selected samples / valid runs;
- `mean_tokens`: total tokens / valid calls;
- `mean_api_calls`: total calls / valid runs.

Missing provider usage is an explicit `unavailable` field, not zero. Timeout latency is recorded as the configured timeout and flagged failed.

## 4. Frozen experiment matrix

| Research question | Primary comparison | Required perturbations | Primary metrics | Minimum conclusion |
| --- | --- | --- | --- | --- |
| RQ1: structural understanding | full structural agent vs deterministic metadata-only inspection | root/file rename, no documentation, irrelevant files, dropped metadata | Structural P/R/F1, UNKNOWN rate, profile consistency, latency/calls | Structure remains evidence-based under identity and documentation perturbations |
| RQ2: few-shot visual content | single random sample vs representative multi-sampling at matched budget | sample budget changes, media failure/partial observation | Content Macro-F1, UNKNOWN rate, consistency, samples, calls, latency | Representative sampling improves quality or stability without masking UNKNOWN |
| RQ3: retrieval effectiveness | metadata/description-only, Structure only, Visual only, Structure + Visual | no documentation, metadata drop, held-out/internal data | Hit@K, MRR, NDCG, compatibility error analysis | Full method improves ranking or clearly identifies its failure boundary |
| RQ4: two-layer decomposition | single relevance score vs Compatibility + Suitability | controlled required-field conflict, content ambiguity | ranking metrics, required-conflict precision, explanation evidence coverage | Required conflicts cannot be hidden by content preference score |

## 5. Ablations

Every ablation uses the same manifest, revisions, query split, seed schedule, provider budget and reporting formulas:

1. `structure_only`: deterministic facts plus structural reasoning; no visual observations.
2. `visual_only`: visual observations without structural evidence.
3. `structure_plus_visual`: complete system.
4. `single_random_sample`: one deterministic random sample per eligible unit.
5. `representative_multi_sampling`: frozen stratified/coverage-aware sample policy.
6. `with_documentation`: documentation available.
7. `without_documentation`: documentation removed by a checked-in perturbation.

The two research baselines are:

- `metadata_description_only`: metadata/description text and deterministic metadata fields only; it cannot inspect visual content.
- `single_relevance_score`: one relevance score over the same available evidence; it has no separate Compatibility gate and no formal Suitability eligibility filter.

No baseline may use dataset names, hidden adapter rules, extra samples, extra API calls or a different query set.

## 6. Pilot calibration and threshold governance

The numeric values in `threshold-manifest.json` are preliminary pilot floors/ceilings only. They are intentionally marked `preliminary_pending_independent_calibration`; they are not fabricated claims about final quality.

Before the final benchmark:

1. An independent calibrator selects the pilot subset using the manifest split, not final results.
2. Each condition runs at least three times with the frozen seed schedule.
3. The calibrator reports metric distributions, uncertainty, failure cases and cost distributions.
4. The main Agent approves or rejects the proposed final thresholds in a versioned change record.
5. The approved threshold manifest is committed before any final benchmark result is inspected.

Changing a threshold after final results are visible is a failed governance gate, even if the new value is more convenient.

## 7. Reproducibility and reporting

The final report must include the fixed execution tuple, per-task-family and aggregate metrics, validity denominators, UNKNOWN counts, latency/sample/token/API summaries, all ablation and baseline rows, confidence intervals or the approved repetition rule, failure analysis, and a statement answering RQ1--RQ4. It must not include raw media, private paths, credentials, full prompts, full model responses or unredacted source URLs.

The deterministic Phase 0 tests validate formula semantics only. They do not count as real LLM/VLM acceptance; Phase 3/4/7 must separately perform the real API tests required by `AGENTS.md` and the acceptance document.
