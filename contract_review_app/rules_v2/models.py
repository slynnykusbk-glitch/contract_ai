from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

=======
# contract_review_app/rules_v2/models.py
"""Finding model for rules v2."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal

from pydantic import BaseModel, field_validator

try:  # pragma: no cover - pydantic v1 fallback
    from pydantic import ConfigDict
except Exception:  # pragma: no cover
    ConfigDict = dict  # type: ignore[misc, assignment]

__all__ = ["FindingV2", "ENGINE_VERSION"]

ENGINE_VERSION = "2.0.0"


class FindingV2(BaseModel):
    """Result produced by rule evaluation."""

    id: str
    pack: str
    severity: str
    category: str
    title: Dict[str, str]
    message: Optional[Dict[str, str]] = None
    explain: Optional[Dict[str, str]] = None
    suggestion: Optional[Dict[str, str]] = None
    evidence: List[str] = Field(default_factory=list)
    citation: List[str] = Field(default_factory=list)
    flags: List[str] = Field(default_factory=list)
    version: str
    engine_version: str = ENGINE_VERSION
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
=======
    """Minimal Finding model used by rules v2."""

    model_config = ConfigDict(extra="forbid")

    id: str
    pack: str
    rule_id: str
    title: Dict[str, str]
    severity: Literal["High", "Medium", "Low"]
    category: str
    message: Dict[str, str]
    explain: Dict[str, str]
    suggestion: Dict[str, str]
    evidence: List[str] = []
    citation: List[str] = []
    flags: List[str] = []
    meta: Dict[str, Any] = {}
    version: str
    created_at: datetime
    engine_version: str

    @field_validator("title", "message", "explain", "suggestion")
    @classmethod
    def _ensure_en(cls, v: Dict[str, str]) -> Dict[str, str]:
        if "en" not in v:
            raise ValueError("missing 'en' localization")
        return v