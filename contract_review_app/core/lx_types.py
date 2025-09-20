from typing import Dict, List, Optional

from pydantic import BaseModel, Field


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
