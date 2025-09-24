from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Optional

try:  # pragma: no cover - environment guards
    from pydantic import (
        BaseModel,
        ConfigDict,
        HttpUrl,
        field_validator,
    )
except Exception:  # pragma: no cover
    # minimal fallbacks for type-checking when pydantic v2 is absent
    BaseModel = object  # type: ignore
    ConfigDict = dict  # type: ignore

    def field_validator(*args, **kwargs):  # type: ignore
        def _decorator(fn):
            return fn

        return _decorator


__all__ = [
    "LegalSource",
    "JurisdictionCode",
    "CorpusDocMeta",
    "CorpusDocument",
    "OGL_V3",
]

# =============================================================================
# Literals / Enums
# =============================================================================
LegalSource = Literal["legislation", "case_law", "regulation", "other"]
JurisdictionCode = Literal["UK", "UA", "EU"]

OGL_V3: str = "OGL-v3"


# =============================================================================
# DTOs
# =============================================================================
class CorpusDocMeta(BaseModel):
    source: LegalSource
    jurisdiction: JurisdictionCode
    act: str
    section: str
    version: str
    updated_at: datetime
    url: HttpUrl
    rights: str
    lang: Optional[str] = None

    model_config = ConfigDict(extra="ignore", frozen=True)

    @field_validator("source", "jurisdiction", "act", "section", "version", "rights")
    @classmethod
    def _trim_non_empty(cls, v: str) -> str:
        if not isinstance(v, str):
            raise TypeError("must be a string")
        v = v.strip()
        if not v:
            raise ValueError("must be a non-empty string")
        return v

    @field_validator("lang")
    @classmethod
    def _trim_optional(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        return v or None

    @field_validator("updated_at", mode="before")
    @classmethod
    def _ensure_datetime(cls, v: datetime | str) -> datetime:
        if isinstance(v, str):
            v = datetime.fromisoformat(v)
        if not isinstance(v, datetime):
            raise TypeError("updated_at must be datetime")
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        else:
            v = v.astimezone(timezone.utc)
        return v


class CorpusDocument(BaseModel):
    meta: CorpusDocMeta
    content: str

    model_config = ConfigDict(extra="ignore", frozen=True)

    @field_validator("content")
    @classmethod
    def _trim_content(cls, v: str) -> str:
        if not isinstance(v, str):
            raise TypeError("content must be a string")
        v = v.strip()
        if not v:
            raise ValueError("content must be a non-empty string")
        return v
