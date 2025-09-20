from decimal import Decimal
from typing import ClassVar, Dict, List, Optional, Tuple

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class LxSegmentRef(BaseModel):
    segment_id: int
    start: int
    end: int
    level: str  # "section" | "clause" | "sentence"


class LxSegment(BaseModel):
    """Lightweight representation of a parsed segment for L1 dispatch."""

    segment_id: int
    text: str = ""
    heading: Optional[str] = None
    clause_type: Optional[str] = None

    def combined_text(self) -> str:
        heading = self.heading or ""
        if heading:
            return f"{heading}\n{self.text or ''}"
        return self.text or ""


class LxFeatureSet(BaseModel):
    labels: List[str] = Field(default_factory=list)
    parties: List[str] = Field(default_factory=list)
    company_numbers: List[str] = Field(default_factory=list)
    amounts: List[str] = Field(default_factory=list)
    durations: Dict[str, int] = Field(default_factory=dict)
    law_signals: List[str] = Field(default_factory=list)
    jurisdiction: Optional[str] = None
    liability_caps: List[str] = Field(default_factory=list)
    carveouts: List[str] = Field(default_factory=list)


class LxDocFeatures(BaseModel):
    by_segment: Dict[int, LxFeatureSet] = Field(default_factory=dict)


class SourceRef(BaseModel):
    clause_id: Optional[str] = None
    span: Optional[Tuple[int, int]] = None
    note: Optional[str] = None


class Money(BaseModel):
    amount: Decimal
    currency: str

    _symbol_map: ClassVar[Dict[str, str]] = {"$": "USD", "£": "GBP", "€": "EUR"}

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        if not isinstance(value, str):
            raise TypeError("currency must be a string")
        cleaned = value.strip()
        normalized = cls._symbol_map.get(cleaned, cleaned).upper()
        if len(normalized) != 3 or not normalized.isalpha():
            raise ValueError("currency must be an ISO 4217 code")
        return normalized


class Duration(BaseModel):
    days: int
    kind: Literal["calendar", "business"] = "calendar"


class ParamGraph(BaseModel):
    payment_term: Optional[Duration] = None
    contract_term: Optional[Duration] = None
    grace_period: Optional[Duration] = None
    governing_law: Optional[str] = None
    jurisdiction: Optional[str] = None
    cap: Optional[Money] = None
    contract_currency: Optional[str] = None
    notice_period: Optional[Duration] = None
    cure_period: Optional[Duration] = None
    survival_items: set[str] = Field(default_factory=set)
    cross_refs: List[Tuple[str, str]] = Field(default_factory=list)
    parties: List[Dict] = Field(default_factory=list)
    signatures: List[Dict] = Field(default_factory=list)
    sources: Dict[str, SourceRef] = Field(default_factory=dict)
