from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


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
