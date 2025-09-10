from __future__ import annotations

from typing import Any, Dict, List, Optional, Literal
from pydantic import BaseModel, Field

# Base model from core to keep tolerant config
try:
    from contract_review_app.core.schemas import AppBaseModel
except Exception:
    AppBaseModel = BaseModel  # fallback


class Party(AppBaseModel):
    role: Optional[str] = None
    name: Optional[str] = None


class TermInfo(AppBaseModel):
    mode: Literal["fixed", "auto_renew", "unknown"] = "unknown"
    start: Optional[str] = None
    end: Optional[str] = None
    renew_notice: Optional[str] = None


class LiabilityInfo(AppBaseModel):
    has_cap: bool
    cap_value: Optional[float] = None
    cap_currency: Optional[str] = None
    notes: Optional[str] = None


class ConditionsVsWarranties(AppBaseModel):
    has_conditions: bool
    has_warranties: bool
    explicit_conditions: List[str] = Field(default_factory=list)
    explicit_warranties: List[str] = Field(default_factory=list)


class DocumentSnapshot(AppBaseModel):
    type: str = "unknown"
    type_confidence: float = 0.0
    type_source: Optional[str] = None
    parties: List[Party] = Field(default_factory=list)
    dates: Dict[str, Optional[str]] = Field(default_factory=dict)
    term: TermInfo = Field(default_factory=TermInfo)
    governing_law: Optional[str] = None
    jurisdiction: Optional[str] = None
    signatures: List[str] = Field(default_factory=list)
    liability: LiabilityInfo = Field(default_factory=lambda: LiabilityInfo(has_cap=False))
    exclusivity: Optional[bool] = None
    currency: Optional[str] = None
    carveouts: Dict[str, Any] = Field(default_factory=lambda: {"has_carveouts": False, "carveouts": []})
    conditions_vs_warranties: ConditionsVsWarranties = Field(
        default_factory=lambda: ConditionsVsWarranties(has_conditions=False, has_warranties=False)
    )
    hints: List[str] = Field(default_factory=list)
    rules_count: int = 0
    debug: Dict[str, Any] | None = None
