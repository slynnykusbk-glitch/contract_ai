from __future__ import annotations

from typing import Dict, Optional

from pydantic import BaseModel, validator

from .i18n import resolve_bundle, validate_locale_dict


class FindingV2(BaseModel):
    """Simplified finding model with localized fields."""

    rule_id: Optional[str] = None
    clause_type: Optional[str] = None
    severity: Optional[str] = None
    start: Optional[int] = None
    end: Optional[int] = None
    snippet: Optional[str] = None

    title: Dict[str, str]
    message: Dict[str, str]
    explain: Dict[str, str]
    suggestion: Dict[str, str]

    # validators ensure 'en' exists and keys/values are strings
    @validator("title", "message", "explain", "suggestion")
    def _validate_locale(cls, v: Dict[str, str]) -> Dict[str, str]:
        validate_locale_dict(v)
        return v

    def localize(self, prefer: str = "uk", fallback: str = "en") -> Dict[str, str]:
        """Return dict with resolved title/message/explain/suggestion strings."""
        return resolve_bundle(
            {
                "title": self.title,
                "message": self.message,
                "explain": self.explain,
                "suggestion": self.suggestion,
            },
            prefer=prefer,
            fallback=fallback,
        )

    def has_locale(self, lang: str) -> bool:
        """Return True if all locale fields have a non-empty value for ``lang``."""
        for field in (self.title, self.message, self.explain, self.suggestion):
            if not isinstance(field, dict):
                return False
            val = field.get(lang)
            if not isinstance(val, str) or not val.strip():
                return False
        return True
