from typing import Any, Dict, List, Literal, Optional

from fastapi import HTTPException
from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
    field_validator,
    constr,
)

from contract_review_app.core.schemas import AppBaseModel


SCHEMA_VERSION = "1.4"


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
    language: str = "en-GB"
    mode: str | None = None
    risk: str | None = None
    clause_type: str | None = None
    schema_: str | None = Field(None, alias="schema")

    @field_validator("language", mode="before")
    @classmethod
    def _default_language(cls, v: str | None) -> str:
        """Ensure language has a sensible default."""
        if not v or not v.strip():
            return "en-GB"
        return v

    @field_validator("mode", "risk", "clause_type", mode="before")
    @classmethod
    def _blank_to_none(cls, v: str | None):
        if isinstance(v, str) and not v.strip():
            return None
        return v

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


class Context(_DTOBase):
    law: Literal["UK"] = "UK"
    language: Literal["en-GB"] = "en-GB"
    contractType: constr(strip_whitespace=True) = "unknown"


class Selection(_DTOBase):
    start: int
    end: int


class DraftFinding(_DTOBase):
    id: str
    title: str
    text: str


class DraftRequest(_DTOBase):
    """Input model for ``/api/gpt/draft``."""

    mode: Literal["friendly", "strict"]
    clause: constr(min_length=20)
    context: Context
    findings: List[DraftFinding] = Field(default_factory=list)
    selection: Optional[Selection] = None


class DraftResponse(_DTOBase):
    draft: str
    notes: List[str] = Field(default_factory=list)


class QARecheckIn(_DTOBase):
    """Input model for ``/api/qa-recheck``.

    ``rules`` accepts either a mapping of rule flags or a list of small
    dictionaries which will be merged into a single mapping for backward
    compatibility with legacy clients.
    """

    text: str
    rules: Dict[str, Any] = Field(default_factory=dict)
    language: str = "en-GB"

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


class QARecheckOut(_DTOBase):
    status: str
    qa: List[Any]
    meta: Dict[str, Any] | None = None


class SummaryIn(_DTOBase):
    """Input model for ``/api/summary``.

    Exactly one of ``cid`` or ``hash`` must be provided.
    """

    cid: str | None = None
    hash: str | None = None

    @model_validator(mode="after")
    def _one_of(cls, values):  # type: ignore[override]
        if (values.cid is None) == (values.hash is None):
            raise HTTPException(
                status_code=422,
                detail="Provide exactly one of cid or hash",
            )
        return values


class CitationInput(_DTOBase):
    instrument: str
    section: str


class QaFindingInput(_DTOBase):
    code: str | None = None
    message: str | None = None
    rule: str | None = None


class CitationResolveRequest(_DTOBase):
    """Request model for ``/api/citation/resolve``.

    Exactly one of ``findings`` or ``citations`` must be provided.  Both
    fields are optional to allow Pydantic to perform the exclusive-or check
    below.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"citations": [{"instrument": "Act", "section": "1"}]},
                {"findings": [{"code": "X", "message": "m"}]},
            ]
        }
    )

    findings: List[QaFindingInput] | None = None
    citations: List[CitationInput] | None = None

    @model_validator(mode="after")
    def _one_of(cls, values):  # type: ignore[override]
        if (values.findings is None) == (values.citations is None):
            raise HTTPException(
                status_code=400,
                detail="Exactly one of findings or citations is required",
            )
        return values


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
