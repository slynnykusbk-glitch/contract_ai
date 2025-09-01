from typing import Any, Dict, List, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from contract_review_app.core.schemas import AppBaseModel


SCHEMA_VERSION = "1.3"


class _DTOBase(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class ProblemDetail(AppBaseModel):
    type: str = "/errors/general"
    title: str
    status: int
    detail: str | None = None
    instance: str | None = None
    code: str | None = None
    extra: dict[str, Any] | None = None


class AnalyzeRequest(_DTOBase):
    text: str


class Span(_DTOBase):
    start: int = Field(ge=0)
    end: int = Field(ge=0)

    @model_validator(mode="after")
    def _check_order(self):  # type: ignore[override]
        if self.start >= self.end:
            raise ValueError("start must be < end")
        return self


class Finding(_DTOBase):
    span: Span
    text: str
    lang: Literal["latin", "cyrillic"]

    @property
    def message(self) -> str:
        return self.text

    @property
    def code(self) -> str:
        return ""


class Segment(_DTOBase):
    span: Span
    lang: Literal["latin", "cyrillic"]


class AnalyzeResult(_DTOBase):
    findings: List[Finding]
    segments: List[Segment] | None = None


class _AnalyzeResults(_DTOBase):
    analysis: AnalyzeResult


class AnalyzeResponse(_DTOBase):
    results: _AnalyzeResults
    analysis: AnalyzeResult | None = None
    status: str | None = None
    clauses: List[Any] | None = None
    document: Dict[str, Any] | None = None
    summary: Dict[str, Any] | None = None
    schema_version: str | None = None


class Citation(_DTOBase):
    instrument: str
    section: str


class CitationResolveRequest(_DTOBase):
    findings: List[Finding] | None = None
    citations: List[Citation] | None = None


class CitationResolveResponse(_DTOBase):
    citations: List[Citation]


SearchMethod = Literal["hybrid", "bm25", "vector"]


class CorpusSearchRequest(_DTOBase):
    q: str
    k: int = 10
    method: SearchMethod = "hybrid"
    jurisdiction: str | None = None
    source: str | None = None
    act_code: str | None = None
    section_code: str | None = None


class SearchHit(_DTOBase):
    doc_id: str
    score: float
    span: Span
    snippet: str | None = None
    title: str | None = None
    text: str | None = None
    meta: Dict[str, Any] | None = None
    bm25_score: float | None = None
    cosine_sim: float | None = None
    rank_fusion: int | None = None


class Paging(BaseModel):
    page: int
    page_size: int
    total: int
    pages: int


class CorpusSearchResponse(_DTOBase):
    hits: List[SearchHit]
    paging: Paging | None = None
