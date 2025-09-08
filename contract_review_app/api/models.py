from typing import Any, Dict, List, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator, field_validator

from contract_review_app.core.schemas import AppBaseModel


SCHEMA_VERSION = "1.3"


class _DTOBase(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ProblemDetail(AppBaseModel):
    type: str = "/errors/general"
    title: str
    status: int
    detail: str | None = None
    instance: str | None = None
    code: str | None = None
    extra: dict[str, Any] | None = None


class AnalyzeRequest(_DTOBase):
    """Public request model for ``/api/analyze``.

    ``text`` is required; legacy producers may still send ``clause`` or
    ``body`` which are accepted as aliases and mapped to ``text``.
    """

    text: str = Field(validation_alias=AliasChoices("text", "clause", "body"))
    language: str = "en"
    mode: str | None = None
    risk: str | None = None

    @model_validator(mode="after")
    def _strip(self):
        txt = (self.text or "").strip()
        if not txt:
            raise ValueError("text is empty")
        self.text = txt
        return self


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


class QaRecheckRequest(_DTOBase):
    """Request model for ``/api/qa-recheck``.

    ``rules`` accepts either a mapping of rule flags or a list of small
    dictionaries which will be merged into a single mapping for backward
    compatibility with legacy clients.
    """

    text: str
    rules: Dict[str, Any] = Field(default_factory=dict)
    profile: str | None = "smart"

    @field_validator("text")
    @classmethod
    def _ensure_text(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("text is empty")
        return v

    @field_validator("rules", mode="before")
    @classmethod
    def _normalize_rules(cls, v):
        if v is None:
            return {}
        if isinstance(v, list):
            merged: Dict[str, Any] = {}
            for item in v:
                if isinstance(item, dict):
                    merged.update(item)
            return merged
        if isinstance(v, dict):
            return v
        raise TypeError("rules must be dict or list of dicts")


class CitationInput(_DTOBase):
    instrument: str
    section: str


class QaFindingInput(_DTOBase):
    code: str | None = None
    message: str | None = None
    rule: str | None = None


class CitationResolveRequest(_DTOBase):
    findings: List[QaFindingInput] | None = None
    citations: List[CitationInput] | None = None


class CitationResolveResponse(_DTOBase):
    citations: List[CitationInput]


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
