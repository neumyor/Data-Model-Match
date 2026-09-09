"""Deterministic and LLM-assisted dataset-to-model compatibility analysis.

The LLM is deliberately a constrained supplement: it may propose mappings and
transforms, but deterministic incompatibilities always remain blockers.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterable
from typing import Any

from .llm import LLMClient, LLMError
from .resource_types import CompatibilityDimension, CompatibilityReport


class CompatibilityError(ValueError):
    """Raised when a profile or an LLM compatibility response is invalid."""


_MAPPING_KINDS = {"exact", "semantic", "transform"}
_MAX_LLM_ANALYSIS_ATTEMPTS = 3
_TEXT_TYPES = {"string", "text", "utf8"}
_INTEGER_TYPES = {
    "int",
    "int8",
    "int16",
    "int32",
    "int64",
    "integer",
    "uint8",
    "uint16",
    "uint32",
    "uint64",
    "classlabel",
    "categorical",
}
_FLOAT_TYPES = {"float", "float16", "float32", "float64", "double", "number"}
_IMAGE_TYPES = {"image", "pixel", "pixels"}
_AUDIO_TYPES = {"audio", "waveform"}
_TASK_ALIASES = {
    "classification": "classification",
    "text-classification": "text-classification",
    "image-classification": "image-classification",
    "audio-classification": "audio-classification",
    "token-classification": "token-classification",
    "text-generation": "text-generation",
    "language-modeling": "text-generation",
    "causal-language-modeling": "text-generation",
    "sequence-to-sequence": "text-generation",
    "image-segmentation": "image-segmentation",
    "semantic-segmentation": "image-segmentation",
    "object-detection": "object-detection",
    "regression": "regression",
}


def analyze_compatibility(
    dataset_profile: dict,
    model_profile: dict,
    client: LLMClient,
    emit: Callable[[dict[str, Any]], None] | None = None,
) -> CompatibilityReport:
    """Analyze a dataset profile against a model input contract.

    The function is synchronous because ``LLMClient`` is synchronous. It emits
    small audit-safe stage events when ``emit`` is supplied; no prompt, model
    response, credential, or chain-of-thought content is emitted.
    """
    dataset = _validate_dataset(dataset_profile)
    model = _validate_model(model_profile)
    _emit(emit, "deterministic", "started")
    state = _deterministic_analysis(dataset, model)
    _emit(emit, "deterministic", "completed")

    terminal_blocker = any(
        dimension.name in {"task", "modality"} and dimension.status == "blocked"
        for dimension in state["dimensions"]
    )
    if terminal_blocker:
        _emit(
            emit,
            "llm",
            "skipped",
            message="已发现确定性阻断项，无需等待大语言模型补充分析。",
        )
    else:
        _emit(emit, "llm", "started")
        try:
            supplement = _request_valid_supplement(
                client,
                dataset,
                model,
                state,
                emit,
            )
            _apply_supplement(state, supplement, dataset, model)
            _emit(emit, "llm", "completed")
        except (LLMError, CompatibilityError, OSError) as exc:
            state["warnings"].append(f"LLM 补充分析不可用：{exc}")
            state["llm_failed"] = True
            _emit(emit, "llm", "failed", message="LLM 补充分析不可用，已保留确定性结果。")

    report = _build_report(state, dataset, model, client)
    _emit(emit, "result", "completed", reportStatus=report.status, score=report.score)
    return report


def _validate_dataset(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CompatibilityError("dataset_profile must be an object")
    required = ("resourceId", "name", "modalities", "taskHints", "features", "license")
    _require_keys(value, required, "dataset_profile")
    _required_text(value["resourceId"], "dataset_profile.resourceId")
    _required_text(value["name"], "dataset_profile.name")
    _string_list(value["modalities"], "dataset_profile.modalities")
    _string_list(value["taskHints"], "dataset_profile.taskHints")
    _required_text(value["license"], "dataset_profile.license")
    if not isinstance(value["features"], list):
        raise CompatibilityError("dataset_profile.features must be an array")
    for index, feature in enumerate(value["features"]):
        _validate_field(feature, f"dataset_profile.features[{index}]", ("semanticRole", "nullable"))
    return value


def _validate_model(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CompatibilityError("model_profile must be an object")
    required = ("resourceId", "name", "tasks", "frameworks", "inputContract", "license")
    _require_keys(value, required, "model_profile")
    _required_text(value["resourceId"], "model_profile.resourceId")
    _required_text(value["name"], "model_profile.name")
    _string_list(value["tasks"], "model_profile.tasks")
    _string_list(value["frameworks"], "model_profile.frameworks")
    _required_text(value["license"], "model_profile.license")
    contract = value["inputContract"]
    if not isinstance(contract, dict):
        raise CompatibilityError("model_profile.inputContract must be an object")
    _require_keys(contract, ("modalities", "fields", "preprocessing", "constraints"), "inputContract")
    _string_list(contract["modalities"], "inputContract.modalities")
    _string_list(contract["preprocessing"], "inputContract.preprocessing")
    _string_list(contract["constraints"], "inputContract.constraints")
    if not isinstance(contract["fields"], list):
        raise CompatibilityError("inputContract.fields must be an array")
    for index, field in enumerate(contract["fields"]):
        _validate_field(field, f"inputContract.fields[{index}]", ("required",))
    return value


def _validate_field(value: object, label: str, optional: tuple[str, ...]) -> None:
    if not isinstance(value, dict):
        raise CompatibilityError(f"{label} must be an object")
    _require_keys(value, ("name", "dataType"), label)
    _required_text(value["name"], f"{label}.name")
    _required_text(value["dataType"], f"{label}.dataType")
    if "shape" in value and not isinstance(value["shape"], list):
        raise CompatibilityError(f"{label}.shape must be an array")
    if "required" in optional and not isinstance(value.get("required", True), bool):
        raise CompatibilityError(f"{label}.required must be a boolean")
    if "nullable" in optional and not isinstance(value.get("nullable", True), bool):
        raise CompatibilityError(f"{label}.nullable must be a boolean")
    if "semanticRole" in optional and not isinstance(value.get("semanticRole", "unknown"), str):
        raise CompatibilityError(f"{label}.semanticRole must be a string")


def _deterministic_analysis(dataset: dict[str, Any], model: dict[str, Any]) -> dict[str, Any]:
    state: dict[str, Any] = {
        "dimensions": [],
        "field_mappings": [],
        "transforms": [],
        "blockers": [],
        "warnings": list(_string_list(dataset.get("warnings", []), "dataset_profile.warnings"))
        + list(_string_list(model.get("warnings", []), "model_profile.warnings")),
        "llm_failed": False,
        "llm_attempt_count": 0,
        "llm_deployment": "",
        "unresolved_required_fields": set(),
    }
    _check_task(dataset, model, state)
    _check_modality(dataset, model, state)
    _check_fields(dataset, model, state)
    _check_preprocessing(model, state)
    _check_labels(dataset, model, state)
    _check_license(dataset, model, state)
    _check_runtime(model, state)
    return state


def _check_task(dataset: dict[str, Any], model: dict[str, Any], state: dict[str, Any]) -> None:
    hints = {_canonical_task(item) for item in dataset["taskHints"] if _canonical_task(item)}
    tasks = {_canonical_task(item) for item in model["tasks"] if _canonical_task(item)}
    if not hints or not tasks:
        _dimension(state, "task", "unknown", 0.5, "数据集或模型未提供可识别的任务信息。")
    elif hints & tasks or _generic_task_overlap(hints, tasks):
        _dimension(state, "task", "compatible", 1.0, "数据集任务提示与模型任务一致。")
    else:
        message = (
            f"任务不匹配：数据集为{_task_names(hints)}，"
            f"模型为{_task_names(tasks)}。"
        )
        _dimension(state, "task", "blocked", 0.0, message)
        state["blockers"].append(message)


def _check_modality(dataset: dict[str, Any], model: dict[str, Any], state: dict[str, Any]) -> None:
    dataset_modalities = {_normalise(item) for item in dataset["modalities"] if _normalise(item)}
    model_modalities = {
        _normalise(item) for item in model["inputContract"]["modalities"] if _normalise(item)
    }
    if not dataset_modalities or not model_modalities:
        _dimension(state, "modality", "unknown", 0.5, "数据集或模型未提供模态信息。")
    elif model_modalities <= dataset_modalities:
        _dimension(state, "modality", "compatible", 1.0, "数据集包含模型要求的全部输入模态。")
    else:
        missing = sorted(model_modalities - dataset_modalities)
        message = f"数据集缺少模型要求的模态：{', '.join(missing)}。"
        _dimension(state, "modality", "blocked", 0.0, message)
        state["blockers"].append(message)


def _check_fields(dataset: dict[str, Any], model: dict[str, Any], state: dict[str, Any]) -> None:
    features = dataset["features"]
    fields = model["inputContract"]["fields"]
    feature_by_name = {_field_key(item["name"]): item for item in features}
    field_scores: list[float] = []
    type_scores: list[float] = []
    shape_scores: list[float] = []

    for field in fields:
        name = field["name"]
        feature = feature_by_name.get(_field_key(name))
        if feature is None:
            feature = _alias_feature(name, features)
        if feature is None:
            if field.get("required", True):
                candidates = [candidate for candidate in features if _type_relation(candidate["dataType"], field["dataType"]) != "blocked"]
                if not candidates:
                    message = f"缺少必需输入字段“{name}”，且没有类型可用的替代字段。"
                    state["blockers"].append(message)
                    field_scores.append(0.0)
                else:
                    state["warnings"].append(f"未找到“{name}”的确定性映射，等待 LLM 提供语义映射建议。")
                    state["unresolved_required_fields"].add(name)
                    field_scores.append(0.5)
            continue

        type_status = _type_relation(feature["dataType"], field["dataType"])
        shape_status = _shape_relation(feature.get("shape", []), field.get("shape", []))
        kind = "exact" if _field_key(feature["name"]) == _field_key(name) and type_status == "compatible" else "transform"
        state["field_mappings"].append(
            {
                "datasetField": feature["name"],
                "modelField": name,
                "kind": kind,
                "confidence": 1.0 if kind == "exact" else 0.8,
                "reason": "字段名和类型确定性匹配。" if kind == "exact" else "字段可通过确定性预处理适配。",
            }
        )
        field_scores.append(1.0 if kind == "exact" else 0.75)
        type_scores.append({"compatible": 1.0, "adaptable": 0.65, "blocked": 0.0}[type_status])
        shape_scores.append({"compatible": 1.0, "adaptable": 0.65, "blocked": 0.0}[shape_status])
        if type_status == "blocked":
            message = f"字段“{feature['name']}”的数据类型 {feature['dataType']} 无法满足模型字段“{name}”的 {field['dataType']}。"
            state["blockers"].append(message)
        elif type_status == "adaptable":
            state["transforms"].append(f"将“{feature['name']}”转换为模型输入“{name}”所需的数据类型。")
        if shape_status == "blocked":
            message = f"字段“{feature['name']}”的 shape 与模型输入“{name}”不兼容。"
            state["blockers"].append(message)
        elif shape_status == "adaptable":
            state["transforms"].append(f"调整“{feature['name']}”的 shape 以满足“{name}”。")

    _dimension(
        state,
        "input_fields",
        _aggregate_status(field_scores),
        _average(field_scores, 0.5),
        "已检查模型输入字段与数据集特征的确定性映射。",
    )
    _dimension(
        state,
        "data_types",
        _aggregate_status(type_scores),
        _average(type_scores, 0.5),
        "已检查确定性字段映射的数据类型。",
    )
    _dimension(
        state,
        "shape",
        _aggregate_status(shape_scores),
        _average(shape_scores, 0.5),
        "已检查确定性字段映射的张量 shape。",
    )


def _check_preprocessing(model: dict[str, Any], state: dict[str, Any]) -> None:
    preprocessing = model["inputContract"]["preprocessing"]
    if not preprocessing:
        _dimension(state, "preprocessing", "compatible", 1.0, "模型未声明额外预处理要求。")
        return
    for step in preprocessing:
        state["transforms"].append(f"执行模型要求的预处理：{step}。")
    _dimension(state, "preprocessing", "adaptable", 0.75, "模型要求的预处理已生成转换计划。")


def _check_labels(dataset: dict[str, Any], model: dict[str, Any], state: dict[str, Any]) -> None:
    classification = any("classification" in _canonical_task(task) for task in model["tasks"])
    labels = [
        feature for feature in dataset["features"]
        if _normalise(feature.get("semanticRole", "")) in {"label", "target"}
        or _field_key(feature["name"]) in {"label", "labels", "target", "class"}
    ]
    if not classification:
        _dimension(state, "labels", "compatible", 1.0, "模型任务不要求分类标签检查。")
    elif labels:
        _dimension(state, "labels", "compatible", 1.0, "发现可用于监督训练的标签字段。")
    else:
        _dimension(state, "labels", "adaptable", 0.5, "未发现明确标签字段；仅推理可用，监督训练前需补充标签。")
        state["warnings"].append("分类模型未发现标签字段，不能直接进行监督训练。")


def _check_license(dataset: dict[str, Any], model: dict[str, Any], state: dict[str, Any]) -> None:
    dataset_license = _normalise(dataset["license"])
    model_license = _normalise(model["license"])
    if "unknown" in {dataset_license, model_license, ""}:
        _dimension(state, "license", "unknown", 0.5, "数据集或模型许可证未知，需人工确认。")
        state["warnings"].append("许可证信息不完整，不能据此判断再分发或商业使用权限。")
    else:
        _dimension(state, "license", "compatible", 1.0, "已记录数据集和模型许可证；具体使用场景仍需法务确认。")


def _check_runtime(model: dict[str, Any], state: dict[str, Any]) -> None:
    frameworks = model.get("frameworks", [])
    if not isinstance(frameworks, list) or not frameworks:
        _dimension(state, "runtime", "unknown", 0.5, "模型未声明框架，无法完成运行环境检查。")
        return
    _dimension(state, "runtime", "unknown", 0.6, "已识别模型框架，但当前分析不探测本机运行环境。")
    state["warnings"].append("运行环境兼容性需要在隔离环境中另行验证。")


def _apply_supplement(
    state: dict[str, Any],
    supplement: dict[str, Any],
    dataset: dict[str, Any],
    model: dict[str, Any],
) -> None:
    features = {item["name"]: item for item in dataset["features"]}
    fields = {item["name"]: item for item in model["inputContract"]["fields"]}
    existing = {(item["datasetField"], item["modelField"]) for item in state["field_mappings"]}
    for mapping in supplement["fieldMappings"]:
        key = (mapping["datasetField"], mapping["modelField"])
        if key in existing:
            continue
        if key[0] not in features or key[1] not in fields:
            raise CompatibilityError(
                f"LLM field mapping references an unknown field: {key[0]} -> {key[1]}"
            )
        feature = features[mapping["datasetField"]]
        field = fields[mapping["modelField"]]
        if _type_relation(feature["dataType"], field["dataType"]) == "blocked":
            state["warnings"].append(
                f"忽略 LLM 建议的字段映射“{key[0]}”→“{key[1]}”：数据类型不兼容。"
            )
            continue
        state["field_mappings"].append(mapping)
        existing.add(key)
        state["unresolved_required_fields"].discard(key[1])
        pending_warning = f"未找到“{key[1]}”的确定性映射，等待 LLM 提供语义映射建议。"
        state["warnings"] = [
            warning for warning in state["warnings"]
            if warning != pending_warning
        ]
    state["transforms"].extend(supplement["transforms"])
    state["warnings"].extend(supplement["warnings"])
    state["summary_hint"] = supplement["summary"]
    if not state["unresolved_required_fields"] and state["field_mappings"]:
        relations = []
        shapes = []
        features_by_name = {item["name"]: item for item in dataset["features"]}
        fields_by_name = {
            item["name"]: item for item in model["inputContract"]["fields"]
        }
        for mapping in state["field_mappings"]:
            feature = features_by_name[mapping["datasetField"]]
            field = fields_by_name[mapping["modelField"]]
            relations.append(_type_relation(feature["dataType"], field["dataType"]))
            shapes.append(_shape_relation(feature.get("shape", []), field.get("shape", [])))
        _replace_dimension(
            state,
            "input_fields",
            "adaptable",
            0.85,
            "模型必需输入字段已通过确定性或语义映射覆盖。",
        )
        _replace_dimension(
            state,
            "data_types",
            _relation_status(relations),
            _relation_score(relations),
            "已验证最终字段映射的数据类型兼容性。",
        )
        _replace_dimension(
            state,
            "shape",
            _relation_status(shapes),
            _relation_score(shapes),
            "已验证最终字段映射的张量 shape 兼容性。",
        )


def _request_valid_supplement(
    client: LLMClient,
    dataset: dict[str, Any],
    model: dict[str, Any],
    state: dict[str, Any],
    emit: Callable[[dict[str, Any]], None] | None,
) -> dict[str, Any]:
    prompt = _system_prompt()
    last_error: CompatibilityError | None = None
    max_attempts = (
        _MAX_LLM_ANALYSIS_ATTEMPTS
        if type(client) is LLMClient
        else 1
    )
    for attempt in range(max_attempts):
        raw = client.complete_json(prompt, _user_prompt(dataset, model))
        transport_attempts = getattr(client, "attempt_count", 1)
        state["llm_attempt_count"] += (
            transport_attempts
            if isinstance(transport_attempts, int) and not isinstance(transport_attempts, bool)
            else 1
        )
        deployment = getattr(client, "last_model", "")
        if isinstance(deployment, str) and deployment:
            state["llm_deployment"] = deployment
        try:
            supplement = _parse_llm_supplement(raw)
            _validate_supplement_fields(supplement, dataset, model)
            return supplement
        except CompatibilityError as exc:
            last_error = exc
            if attempt + 1 >= max_attempts or not state["llm_deployment"]:
                raise
            rejected = state["llm_deployment"]
            client.reject_last_model()
            state["warnings"].append(
                f"模型部署 {rejected} 返回的结构无效，已切换同名部署重试。"
            )
            _emit(
                emit,
                "llm",
                "retrying",
                message="模型输出未通过结构校验，正在切换同名部署重试。",
            )
            prompt = (
                _system_prompt()
                + " 上一次输出未通过结构校验。必须为每个 fieldMappings 项提供非空且真实存在的"
                " datasetField 和 modelField；没有可靠映射时返回空数组。"
            )
    if last_error is not None:
        raise last_error
    raise CompatibilityError("LLM supplement validation failed")


def _validate_supplement_fields(
    supplement: dict[str, Any],
    dataset: dict[str, Any],
    model: dict[str, Any],
) -> None:
    features = {item["name"] for item in dataset["features"]}
    fields = {item["name"] for item in model["inputContract"]["fields"]}
    for mapping in supplement["fieldMappings"]:
        key = (mapping["datasetField"], mapping["modelField"])
        if key[0] not in features or key[1] not in fields:
            raise CompatibilityError(
                f"LLM field mapping references an unknown field: {key[0]} -> {key[1]}"
            )


def _parse_llm_supplement(value: object) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"summary", "fieldMappings", "transforms", "warnings"}:
        raise CompatibilityError("LLM result must contain exactly summary, fieldMappings, transforms, and warnings")
    _required_text(value["summary"], "LLM summary")
    if not isinstance(value["fieldMappings"], list):
        raise CompatibilityError("LLM fieldMappings must be an array")
    for index, mapping in enumerate(value["fieldMappings"]):
        if not isinstance(mapping, dict) or set(mapping) != {
            "datasetField", "modelField", "kind", "confidence", "reason"
        }:
            raise CompatibilityError(f"LLM fieldMappings[{index}] has an invalid schema")
        _required_text(mapping["datasetField"], f"LLM fieldMappings[{index}].datasetField")
        _required_text(mapping["modelField"], f"LLM fieldMappings[{index}].modelField")
        if mapping["kind"] not in _MAPPING_KINDS:
            raise CompatibilityError(f"LLM fieldMappings[{index}].kind is invalid")
        _score(mapping["confidence"], f"LLM fieldMappings[{index}].confidence")
        _required_text(mapping["reason"], f"LLM fieldMappings[{index}].reason")
    transforms = _normalise_llm_transforms(value["transforms"])
    warnings = _string_list(value["warnings"], "LLM warnings")
    return {
        "summary": value["summary"],
        "fieldMappings": value["fieldMappings"],
        "transforms": transforms,
        "warnings": warnings,
    }


def _normalise_llm_transforms(value: object) -> list[str]:
    if not isinstance(value, list):
        raise CompatibilityError("LLM transforms must be an array")
    transforms: list[str] = []
    for index, item in enumerate(value):
        if isinstance(item, str) and item.strip():
            transforms.append(item.strip())
            continue
        if not isinstance(item, dict) or not set(item) <= {
            "name", "appliesTo", "reason", "description"
        }:
            raise CompatibilityError(f"LLM transforms[{index}] has an invalid schema")
        name = _required_text(item.get("name"), f"LLM transforms[{index}].name")
        applies_to = item.get("appliesTo")
        reason = item.get("reason", item.get("description"))
        if applies_to is not None and not isinstance(applies_to, str):
            raise CompatibilityError(f"LLM transforms[{index}].appliesTo must be a string")
        if reason is not None and not isinstance(reason, str):
            raise CompatibilityError(f"LLM transforms[{index}].reason must be a string")
        label = name
        if isinstance(applies_to, str) and applies_to.strip():
            label += f"（{applies_to.strip()}）"
        if isinstance(reason, str) and reason.strip():
            label += f"：{reason.strip()}"
        transforms.append(label)
    return transforms


def _build_report(
    state: dict[str, Any],
    dataset: dict[str, Any],
    model: dict[str, Any],
    client: LLMClient,
) -> CompatibilityReport:
    dimensions = state["dimensions"]
    has_blocker = bool(state["blockers"])
    statuses = {dimension.status for dimension in dimensions}
    core_unknown = any(
        dimension.name in {"task", "modality"}
        and dimension.status == "unknown"
        for dimension in dimensions
    )
    if has_blocker:
        status = "blocked"
    elif core_unknown or state["unresolved_required_fields"]:
        status = "unknown"
    elif "adaptable" in statuses:
        status = "adaptable"
    else:
        status = "compatible"

    score = _average([dimension.score for dimension in dimensions], 0.0)
    if has_blocker:
        score = min(score, 0.49)
    summary = _summary(status, state)
    deployment = state.get("llm_deployment") or getattr(client, "last_model", "")
    if not isinstance(deployment, str):
        deployment = ""
    attempt_count = state.get("llm_attempt_count") or getattr(client, "attempt_count", 1)
    if not isinstance(attempt_count, int) or isinstance(attempt_count, bool):
        attempt_count = 1
    return CompatibilityReport(
        dataset_resource_id=dataset["resourceId"],
        model_resource_id=model["resourceId"],
        status=status,
        score=round(score, 3),
        summary=summary,
        dimensions=dimensions,
        field_mappings=_dedupe_mappings(state["field_mappings"]),
        transforms=_dedupe_text(state["transforms"]),
        blockers=_dedupe_text(state["blockers"]),
        warnings=_dedupe_text(state["warnings"]),
        model=client.config.model,
        deployment=deployment,
        attempt_count=attempt_count,
    )


def _system_prompt() -> str:
    return (
        "你是数据集与深度学习模型兼容性分析器。只补充语义字段映射、预处理转换和警告，"
        "不要推翻输入中给出的确定性检查。只返回一个 JSON 对象，且只能包含 summary、"
        "fieldMappings、transforms、warnings 四个键。fieldMappings 的每项只能包含 "
        "datasetField、modelField、kind、confidence、reason；kind 只能为 exact、semantic "
        "或 transform，confidence 必须是 0 到 1 的数字。不要虚构字段。"
        "transforms 和 warnings 必须是字符串数组；没有可靠建议时返回空数组。"
    )


def _user_prompt(dataset: dict[str, Any], model: dict[str, Any]) -> str:
    return json.dumps(
        {
            "dataset": {
                "name": dataset["name"],
                "modalities": dataset["modalities"],
                "taskHints": dataset["taskHints"],
                "features": dataset["features"],
                "license": dataset["license"],
            },
            "model": {
                "name": model["name"],
                "tasks": model["tasks"],
                "inputContract": model["inputContract"],
                "license": model["license"],
            },
        },
        ensure_ascii=False,
    )


def _dimension(state: dict[str, Any], name: str, status: str, score: float, reason: str) -> None:
    state["dimensions"].append(CompatibilityDimension(name, status, score, reason))


def _replace_dimension(
    state: dict[str, Any],
    name: str,
    status: str,
    score: float,
    reason: str,
) -> None:
    replacement = CompatibilityDimension(name, status, score, reason)
    state["dimensions"] = [
        replacement if dimension.name == name else dimension
        for dimension in state["dimensions"]
    ]


def _relation_status(values: list[str]) -> str:
    if "blocked" in values:
        return "blocked"
    if "adaptable" in values:
        return "adaptable"
    return "compatible" if values else "unknown"


def _relation_score(values: list[str]) -> float:
    scores = {"compatible": 1.0, "adaptable": 0.65, "blocked": 0.0}
    return _average([scores[value] for value in values], 0.5)


def _emit(emit: Callable[[dict[str, Any]], None] | None, stage: str, status: str, **extra: Any) -> None:
    if emit is not None:
        emit({"type": "stage", "stage": stage, "status": status, **extra})


def _type_relation(source: object, target: object) -> str:
    source_type, target_type = _normalise(str(source)), _normalise(str(target))
    if source_type == target_type:
        return "compatible"
    source_group, target_group = _type_group(source_type), _type_group(target_type)
    if source_group == target_group and source_group is not None:
        return "adaptable"
    if source_group == "integer" and target_group == "float":
        return "adaptable"
    if source_group == "text" and target_group == "integer":
        return "adaptable"
    return "blocked"


def _shape_relation(source: object, target: object) -> str:
    if not isinstance(source, list) or not isinstance(target, list) or not target:
        return "compatible"
    if source == target:
        return "compatible"
    if len(source) != len(target):
        return "adaptable"
    for actual, expected in zip(source, target):
        if expected in (None, -1, "*", "dynamic") or actual == expected:
            continue
        if isinstance(actual, int) and isinstance(expected, int) and actual > 0 and expected > 0:
            return "adaptable"
        return "blocked"
    return "compatible"


def _alias_feature(field_name: str, features: list[dict[str, Any]]) -> dict[str, Any] | None:
    aliases = {
        "inputids": {"text", "input", "tokens", "inputids"},
        "attentionmask": {"attentionmask", "mask"},
        "pixelvalues": {"image", "images", "pixelvalues"},
        "inputvalues": {"audio", "waveform", "inputvalues"},
    }
    desired = aliases.get(_field_key(field_name), set())
    matches = [item for item in features if _field_key(item["name"]) in desired]
    return matches[0] if len(matches) == 1 else None


def _type_group(value: str) -> str | None:
    if value in _TEXT_TYPES:
        return "text"
    if value in _INTEGER_TYPES:
        return "integer"
    if value in _FLOAT_TYPES:
        return "float"
    if value in _IMAGE_TYPES:
        return "image"
    if value in _AUDIO_TYPES:
        return "audio"
    if value in {"boolean", "bool"}:
        return "boolean"
    return None


def _canonical_task(value: object) -> str:
    normalised = _normalise(str(value))
    return _TASK_ALIASES.get(normalised, normalised)


def _task_names(values: set[str]) -> str:
    labels = {
        "classification": "分类",
        "text-classification": "文本分类",
        "image-classification": "图像分类",
        "audio-classification": "音频分类",
        "token-classification": "序列标注",
        "text-generation": "文本生成",
        "image-segmentation": "图像分割",
        "object-detection": "目标检测",
        "regression": "回归",
    }
    return "、".join(labels.get(value, value) for value in sorted(values))


def _generic_task_overlap(hints: set[str], tasks: set[str]) -> bool:
    return "classification" in hints and any("classification" in task for task in tasks) or (
        "classification" in tasks and any("classification" in hint for hint in hints)
    )


def _aggregate_status(scores: Iterable[float]) -> str:
    values = list(scores)
    if not values:
        return "unknown"
    if 0.0 in values:
        return "blocked"
    if min(values) < 1.0:
        return "adaptable"
    return "compatible"


def _summary(status: str, state: dict[str, Any]) -> str:
    hint = state.get("summary_hint")
    if status == "blocked":
        return f"存在确定性阻断项，当前数据集不能直接用于该模型。{hint or ''}".strip()
    if status == "adaptable":
        return f"数据集可经转换后用于该模型。{hint or ''}".strip()
    if status == "compatible":
        return f"数据集与模型的已知契约兼容。{hint or ''}".strip()
    return f"兼容性信息不足，需要进一步确认。{hint or ''}".strip()


def _normalise(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")


def _field_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.strip().lower())


def _score(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= float(value) <= 1:
        raise CompatibilityError(f"{label} must be a number between 0 and 1")
    return float(value)


def _required_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CompatibilityError(f"{label} must be a non-empty string")
    return value.strip()


def _string_list(value: object, label: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise CompatibilityError(f"{label} must be an array of strings")
    return value


def _require_keys(value: dict[str, Any], keys: Iterable[str], label: str) -> None:
    missing = [key for key in keys if key not in value]
    if missing:
        raise CompatibilityError(f"{label} is missing required keys: {', '.join(missing)}")


def _average(values: Iterable[float], default: float) -> float:
    values = list(values)
    return sum(values) / len(values) if values else default


def _dedupe_text(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(value.strip() for value in values if value.strip()))


def _dedupe_mappings(values: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: dict[tuple[str, str], dict[str, Any]] = {}
    for value in values:
        unique.setdefault((value["datasetField"], value["modelField"]), value)
    return list(unique.values())
