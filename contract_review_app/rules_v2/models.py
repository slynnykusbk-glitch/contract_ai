# contract_review_app/rules_v2/models.py
"""Finding model for rules v2 (B3 unified)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal

from pydantic import BaseModel, Field, field_validator

try:  # pragma: no cover - pydantic v1 fallback
    from pydantic import ConfigDict
except Exception:  # pragma: no cover
    ConfigDict = dict  # type: ignore[misc, assignment]

__all__ = ["FindingV2", "ENGINE_VERSION"]

ENGINE_VERSION = "2.0.0"


class FindingV2(BaseModel):
    """Result produced by rule evaluation (deterministic, i18n-aware)."""

    model_config = ConfigDict(extra="forbid")

    # identity & grouping
    id: str = ""
    pack: str = ""
    rule_id: str = ""

    # i18n text
    title: Dict[str, str]
    message: Dict[str, str] = Field(default_factory=lambda: {"en": ""})
    explain: Dict[str, str] = Field(default_factory=lambda: {"en": ""})
    suggestion: Dict[str, str] = Field(default_factory=lambda: {"en": ""})

    # classification
    severity: Literal["High", "Medium", "Low"] = "Low"
    category: str = "General"

    # evidence & refs
    evidence: List[str] = Field(default_factory=list)
    citation: List[str] = Field(default_factory=list)
    flags: List[str] = Field(default_factory=list)

    # misc/meta
    meta: Dict[str, Any] = Field(default_factory=dict)
    version: str = "2.0.0"
    engine_version: str = ENGINE_VERSION
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("title", "message", "explain", "suggestion")
    @classmethod
    def _ensure_en(cls, v: Dict[str, str], info) -> Dict[str, str]:
        if "en" not in v or not isinstance(v["en"], str):
            raise ValueError("missing 'en' localization")
        if info.field_name == "title" and not v["en"].strip():
            raise ValueError("missing 'en' localization")
        return v

    def localize(self, prefer: str = "en") -> Dict[str, str]:
        from .i18n import resolve_locale

        return {
            "title": resolve_locale(self.title, prefer=prefer),
            "message": resolve_locale(self.message, prefer=prefer),
            "explain": resolve_locale(self.explain, prefer=prefer),
            "suggestion": resolve_locale(self.suggestion, prefer=prefer),
        }

    def has_locale(self, lang: str) -> bool:
        return all(lang in d for d in (self.title, self.message, self.explain, self.suggestion))
