"""Thin wrapper around prompt_builder_utils.build_prompt.
Provides backward-compatible functions for constructing GPT prompts.
"""

from __future__ import annotations

"""Thin wrapper exposing prompt_builder_utils.build_prompt."""

from typing import Any, Dict

from .prompt_builder_utils import build_prompt as _build_prompt_legacy


def build_prompt(analysis: Any) -> str:
    return _build_prompt_legacy(analysis)  # type: ignore[arg-type]


def build_prompt_text(analysis: Any, *_, **__) -> str:
    return build_prompt(analysis)


def build_prompt_parts(analysis: Any, *_, **__) -> Dict[str, str]:
    return {"prompt": build_prompt(analysis)}


def build_gpt_prompt(analysis: Any, *_, **__) -> Dict[str, str]:
    return build_prompt_parts(analysis)
