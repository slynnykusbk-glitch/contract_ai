from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


LocaleDict = Dict[str, str]


class Produce(BaseModel):
    evidence: List[str] = Field(default_factory=list)
    citation: List[str] = Field(default_factory=list)
    flags: List[str] = Field(default_factory=list)


class CheckItem(BaseModel):
    when: str | bool
    any_of: Optional[List[str]] = None
    all_of: Optional[List[str]] = None
    produce: Optional[Produce] = None


class RuleYaml(BaseModel):
    id: str
    pack: str
    severity: str
    category: str
    title: LocaleDict
    message: Optional[LocaleDict] = None
    explain: Optional[LocaleDict] = None
    suggestion: Optional[LocaleDict] = None
    evidence: List[str] = Field(default_factory=list)
    citation: List[str] = Field(default_factory=list)
    flags: List[str] = Field(default_factory=list)
    version: str
    engine_version: str
    checks: List[CheckItem]

    @field_validator("title")
    def _title_has_en(cls, v: LocaleDict) -> LocaleDict:
        if "en" not in v:
            raise ValueError("title must include 'en'")
        return v

    @field_validator("message", "explain", "suggestion")
    def _locale_has_en(cls, v: Optional[LocaleDict]) -> Optional[LocaleDict]:
        if v is not None and "en" not in v:
            raise ValueError("locale dict must include 'en'")
        return v

    @field_validator("severity")
    def _severity_valid(cls, v: str) -> str:
        if v not in {"High", "Medium", "Low"}:
            raise ValueError("invalid severity")
        return v

    @field_validator("version", "engine_version")
    def _non_empty(cls, v: str) -> str:
        if not v:
            raise ValueError("must be non-empty")
        return v
