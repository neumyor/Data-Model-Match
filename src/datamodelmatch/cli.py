"""Command-line entry point."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

from .config import ConfigError, load_llm_config
from .llm import LLMClient, LLMError
from .matcher import MatchError, match_models
from .models import ModelError, load_model


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(description="Match fields between two JSON data models.")
    parser.add_argument("source", type=Path, help="Source model JSON file")
    parser.add_argument("target", type=Path, help="Target model JSON file")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config.llm.json"),
        help="LLM config JSON file (default: config.llm.json)",
    )
    parser.add_argument("--timeout", type=float, default=60.0, help="LLM request timeout in seconds")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """Run the model matching CLI."""
    args = build_parser().parse_args(argv)
    try:
        config = load_llm_config(args.config)
        source_model = load_model(args.source)
        target_model = load_model(args.target)
        result = match_models(source_model, target_model, LLMClient(config, args.timeout))
    except (ConfigError, ModelError, LLMError, MatchError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
