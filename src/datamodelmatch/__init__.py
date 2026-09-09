"""Data model matching powered by an OpenAI-compatible LLM endpoint."""

from .config import LLMConfig, load_llm_config
from .matcher import MatchError, match_models
from .models import DataModel, Entity, Field, ModelDocument, load_model, load_model_document
from .results import FieldRef, Match, MatchMeta, MatchResult, ResultValidationError
from .resource_store import ResourceStore
from .resource_types import (
    CompatibilityDimension,
    CompatibilityReport,
    ContractField,
    DatasetFeature,
    DatasetProfile,
    DatasetSplit,
    Evidence,
    ModelContract,
    ModelProfile,
    ResourceRecord,
    SourceRef,
)

__all__ = [
    "DataModel",
    "Entity",
    "Field",
    "LLMConfig",
    "Match",
    "MatchError",
    "MatchMeta",
    "MatchResult",
    "ModelDocument",
    "FieldRef",
    "ResultValidationError",
    "load_llm_config",
    "load_model",
    "load_model_document",
    "match_models",
    "CompatibilityDimension",
    "CompatibilityReport",
    "ContractField",
    "DatasetFeature",
    "DatasetProfile",
    "DatasetSplit",
    "Evidence",
    "ModelContract",
    "ModelProfile",
    "ResourceRecord",
    "ResourceStore",
    "SourceRef",
]
