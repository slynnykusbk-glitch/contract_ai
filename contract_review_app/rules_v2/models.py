from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

__all__ = ["FindingV2", "ENGINE_VERSION"]

ENGINE_VERSION = "2.0.0"

@dataclass
class FindingV2:
    """
    Dataclass- модель результата для rules v2.

    Важно: поля и их типы соответствуют ожиданиям adapter.py и тестов.
    """

    # идентификаторы
    id: str
    pack: str
    rule_id: str

    # локализованные тексты
    title: Dict[str, str]
    message: Dict[str, str]
    explain: Dict[str, str]
    suggestion: Dict[str, str]

    # атрибуты/данные
    severity: str = "Medium"             # "High" | "Medium" | "Low" (строка)
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