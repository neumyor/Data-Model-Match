"""Data model matching powered by an OpenAI-compatible LLM endpoint."""

from .config import LLMConfig, load_llm_config
from .matcher import MatchError, match_models
from .models import DataModel, Entity, Field, ModelDocument, load_model, load_model_document
from .results import FieldRef, Match, MatchMeta, MatchResult, ResultValidationError

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
]
