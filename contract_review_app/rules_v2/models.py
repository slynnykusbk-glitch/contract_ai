from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Literal

from dataclasses import field
from pydantic import field_validator
from pydantic.dataclasses import dataclass
from dataclasses import asdict

__all__ = ["FindingV2", "ENGINE_VERSION"]

ENGINE_VERSION = "2.0.0"


@dataclass
class FindingV2:
    """Dataclass- модель результата для rules v2."""

    # обязательные поля
    title: Dict[str, str]
    rule_id: str = ""
    message: Dict[str, str] = field(default_factory=lambda: {"en": ""})
    explain: Dict[str, str] = field(default_factory=lambda: {"en": ""})
    suggestion: Dict[str, str] = field(default_factory=lambda: {"en": ""})

    # опциональные идентификаторы
    id: str = ""
    pack: str = ""

    # атрибуты/данные
    severity: Literal["High", "Medium", "Low"] = "Medium"
    category: str = "General"

    # простые коллекции (адаптер отдаёт списки строк)
    evidence: List[str] = field(default_factory=list)
    citation: List[str] = field(default_factory=list)
    flags: List[str] = field(default_factory=list)

    # произвольные метаданные
    meta: Dict[str, Any] = field(default_factory=dict)

    # версия/время
    version: str = "2.0.0"
    engine_version: str = ENGINE_VERSION
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # --- Validators -----------------------------------------------------
    @field_validator("title", "message", "explain", "suggestion")
    @classmethod
    def _require_en(cls, v: Dict[str, str]) -> Dict[str, str]:
        if "en" not in v:
            raise ValueError("'en' locale required")
        if not all(isinstance(val, str) for val in v.values()):
            raise TypeError("locale values must be strings")
        return v

    # --- Helpers --------------------------------------------------------
    def dict(self) -> Dict[str, Any]:
        return asdict(self)

    def has_locale(self, locale: str) -> bool:
        return all(
            locale in d for d in (self.title, self.message, self.explain, self.suggestion)
        )

    def localize(self, prefer: str = "en") -> Dict[str, str]:
        from .i18n import resolve_locale

        return {
            "title": resolve_locale(self.title, prefer=prefer),
            "message": resolve_locale(self.message, prefer=prefer),
            "explain": resolve_locale(self.explain, prefer=prefer),
            "suggestion": resolve_locale(self.suggestion, prefer=prefer),
        }
