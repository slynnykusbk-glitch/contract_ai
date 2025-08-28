from __future__ import annotations
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, HttpUrl


class CitationIn(BaseModel):
    system: Optional[str] = None
    instrument: Optional[str] = None
    section: Optional[str] = None
    url: Optional[HttpUrl] = None
    title: Optional[str] = None
    source: Optional[str] = None


class DraftRequest(BaseModel):
    question: str = Field(default="")
    context_text: str = Field(default="")
    citations: List[CitationIn] = Field(default_factory=list)


class SuggestEditsRequest(BaseModel):
    question: str = Field(default="")
    context_text: str = Field(default="")
    citations: List[CitationIn] = Field(default_factory=list)


class LLMResponse(BaseModel):
    provider: str
    model: str
    result: str
    prompt: str
    verification_status: Optional[str] = None
    grounding_trace: Dict[str, Any] = Field(default_factory=dict)
    usage: Dict[str, int] = Field(default_factory=dict)
