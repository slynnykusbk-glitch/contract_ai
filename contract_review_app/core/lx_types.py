from typing import Dict, List, Optional

from pydantic import BaseModel


class LxSegmentRef(BaseModel):
    segment_id: int
    start: int
    end: int
    level: str  # "section" | "clause" | "sentence"


class LxFeatureSet(BaseModel):
    labels: List[str] = []
    parties: List[str] = []
    company_numbers: List[str] = []
    amounts: List[str] = []
    durations: Dict[str, int] = {}
    law_signals: List[str] = []
    jurisdiction: Optional[str] = None
    liability_caps: List[str] = []
    carveouts: List[str] = []


class LxDocFeatures(BaseModel):
    by_segment: Dict[int, LxFeatureSet] = {}
