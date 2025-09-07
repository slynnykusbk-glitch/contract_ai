# contract_review_app/core/schemas.py
from __future__ import annotations

from typing import List, Optional, Dict, Literal, Any, Union
from pydantic import BaseModel, Field, AnyUrl, field_validator

# pydantic v2 compatibility shims
try:
    # v2
    from pydantic import ConfigDict, model_validator  # type: ignore
except Exception:  # pragma: no cover
    # v1 shims (minimal no-op fallbacks)
    ConfigDict = dict  # type: ignore

    def model_validator(*args, **kwargs):  # type: ignore
        def _decorator(fn):
            return fn

        return _decorator


# ============================================================================
# Public exports control (clean imports across project)
# ============================================================================
__all__ = [
    # constants
    "SCHEMA_VERSION",
    "RISK_ORDER",
    # enums/literals
    "Status",
    "RiskLevel",
    "Severity",
    "DraftMode",
    # primitives
    "Span",
    "Evidence",
    "Citation",
    "CrossRef",
    "TextPatch",
    # inputs
    "AnalysisInput",
    "AnalyzeIn",
    # building blocks
    "Finding",
    "Diagnostic",
    "Suggestion",
    "GPTDraftResponse",
    # clause/document
    "Clause",
    "AnalysisOutput",
    "DocIndex",
    "DocumentAnalysis",
    # responses (panel-compat legacy + combined)
    "Analysis",
    "AnalyzeResponse",
    "AnalyzeOut",
    # base-doc
    "BaseDoc",
    # Step 4 DTOs
    "DraftIn",
    "DraftOut",
    "SuggestIn",
    "SuggestOut",
    "SuggestEdit",
    "SuggestResponse",
    "AppliedChange",
    "DeltaMetrics",
    "QARecheckIn",
    "QARecheckOut",
    "ExplainRequest",
    "ExplainResponse",
    # trace
    "TraceOut",
    # helpers (both long and short names)
    "risk_to_ordinal",
    "ordinal_to_risk",
    "risk_to_ord",
    "ord_to_risk",
]

# ============================================================================
# Single Source Of Truth (schema version)
# ============================================================================
SCHEMA_VERSION: str = "1.3"

# ============================================================================
# Risk ordinal helpers (canonical for deltas/aggregation)
# ============================================================================
RiskLevel = Literal["low", "medium", "high", "critical"]

RISK_ORDER: Dict[RiskLevel, int] = {  # type: ignore[name-defined]
    "low": 0,
    "medium": 1,
    "high": 2,
    "critical": 3,
}


def risk_to_ordinal(r: RiskLevel | str) -> int:
    """
    Return ordinal for risk (unknown -> 1 == 'medium').
    """
    try:
        key = r if isinstance(r, str) else str(r)
        key_l = key.lower()
        return RISK_ORDER[key_l]  # type: ignore[index]
    except Exception:
        return 1


def ordinal_to_risk(o: int) -> RiskLevel:
    """
    Inverse mapping with clamping to bounds.
    """
    if o <= 0:
        return "low"
    if o == 1:
        return "medium"
    if o == 2:
        return "high"
    return "critical"


# Short aliases (convenient names used across the codebase)
risk_to_ord = risk_to_ordinal
ord_to_risk = ordinal_to_risk


# ============================================================================
# Base config (tolerant to extras; safe string length)
# ============================================================================
class AppBaseModel(BaseModel):
    """
    Base model with tolerant config to avoid breaking older producers.
    Note: str_max_length increased to handle large contracts comfortably.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        extra="ignore",  # tolerate unknown fields (legacy/producers)
        str_max_length=200_000,  # large documents supported
    )


# ============================================================================
# Enums / Literals
# ============================================================================
# [CHANGED]: расширили множество статусов для приема синонимов и "UNKNOWN"
Status = Literal[
    "OK", "WARN", "FAIL", "PASS", "UNKNOWN"
]  # accepts PASS (normalized to OK)

Severity = Literal["info", "minor", "major", "critical"]
DraftMode = Literal["friendly", "standard", "strict"]


# ============================================================================
# Inputs
# ============================================================================
class AnalysisInput(AppBaseModel):
    """
    Unified input for Rule Engine (per clause or text block).
    """

    clause_type: str
    text: str
    language: Optional[str] = None
    policy: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


# --- AnalyzeIn (replace) ---
class AnalyzeIn(AppBaseModel):
    """
    Public DTO for /api/analyze request.
    Adds optional segment context and output switches without breaking legacy.
    """

    document_name: Optional[str] = None
    text: str
    language: Optional[str] = None

    # segment context (optional; used by pipeline/template selection)
    jurisdiction: Optional[str] = None
    contract_type: Optional[str] = None
    user_role: Optional[str] = None

    # policy & switches
    policy: Dict[str, Any] = Field(default_factory=dict)
    return_legacy: bool = True  # keep analysis/results/clauses
    return_ssot: bool = True  # include document-level SSOT

    @model_validator(mode="after")
    def _validate_clean(self):
        if not isinstance(self.text, str) or self.text.strip() == "":
            raise ValueError("AnalyzeIn.text must be a non-empty string")
        self.text = self.text.strip()
        return self


# ============================================================================
# Value objects
# ============================================================================
class Span(AppBaseModel):
    """
    Text location anchor for UI annotations and cross-checks (absolute coords).
    """

    start: int = 0
    length: int = 0
    page: Optional[int] = None
    block: Optional[int] = None

    @field_validator("start", "length")
    @classmethod
    def _non_negative(cls, v: int) -> int:
        if v is None:
            return 0
        if v < 0:
            raise ValueError("Span.start and Span.length must be >= 0")
        return v


class Evidence(AppBaseModel):
    """Supporting evidence snippet for a citation."""

    text: str
    source: Optional[str] = None
    link: Optional[AnyUrl] = None


class Citation(AppBaseModel):
    """
    Legal citation item; url is validated if present.
    """

    system: Literal["UK", "UA", "EU", "INT"] = "UK"
    instrument: str
    section: str
    url: Optional[AnyUrl] = None
    title: Optional[str] = None
    source: Optional[str] = None
    link: Optional[str] = None
    score: Optional[float] = None
    evidence: Optional[Evidence] = None
    evidence_text: Optional[str] = None

    @field_validator("score", mode="before")
    @classmethod
    def _validate_score(cls, v):
        if v is None:
            return None
        try:
            fv = float(v)
        except Exception:
            return None
        return fv if 0.0 <= fv <= 1.0 else None

    @field_validator("link", mode="before")
    @classmethod
    def _link_str(cls, v):
        return None if v is None else str(v)

    @field_validator("evidence", mode="before")
    @classmethod
    def _coerce_evidence(cls, v):
        if v is None:
            return None
        if isinstance(v, Evidence):
            return v
        if isinstance(v, str):
            return Evidence(text=v)
        if isinstance(v, dict):
            return Evidence(**v)
        return None

    @model_validator(mode="after")
    def _sync_evidence_text(self):
        if self.evidence is None and self.evidence_text:
            self.evidence = Evidence(text=self.evidence_text)
        if self.evidence and not self.evidence_text:
            self.evidence_text = self.evidence.text
        return self


class CrossRef(AppBaseModel):
    """
    Relation between clauses (e.g., Termination depends on Notice).
    """

    source_clause_id: str
    target_clause_id: str
    relation: Literal["contradicts", "depends_on", "duplicates", "requires"] = (
        "depends_on"
    )


class TextPatch(AppBaseModel):
    """
    Normalised text patch for recheck:
      - Accepts range = {"start","length"} OR {"start","end"} and normalises
        to {"start","length"} with non-negative ints.
      - 'replacement' uses alias 'text' for back/forward compatibility.
    """

    span: Optional[Span] = None
    range: Optional[Dict[str, int]] = None
    replacement: str = Field(alias="text", default="")

    @model_validator(mode="after")
    def _normalise(self):
        # replacement must be str
        if not isinstance(self.replacement, str):
            self.replacement = "" if self.replacement is None else str(self.replacement)

        # normalise range to {"start","length"}
        if self.range is None:
            return self

        r = self.range
        start = r.get("start", 0)
        length = r.get("length")
        end = r.get("end")

        try:
            start = int(start)
        except Exception:
            start = 0

        if length is None and end is not None:
            try:
                end = int(end)
            except Exception:
                end = start
            length = max(0, end - start)
        elif length is None:
            length = 0
        else:
            try:
                length = int(length)
            except Exception:
                length = 0

        if start < 0 or length < 0:
            raise ValueError("TextPatch.range 'start' and 'length' must be >= 0")

        self.range = {"start": start, "length": length}
        return self


# ============================================================================
# Building blocks
# ============================================================================
class Finding(AppBaseModel):
    """
    Single rule finding; can be rendered to UI and used for scoring.
    """

    code: str
    message: str
    severity_level: Optional[Severity] = Field(
        default=None, alias="severity", description="SSOT severity enum"
    )
    risk: Optional[RiskLevel] = Field(default=None, description="SSOT risk enum")
    evidence: Optional[str] = None
    span: Optional[Span] = None
    citations: List[Citation] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    # Legacy support:
    legal_basis: List[str] = Field(default_factory=list)

    # Back-compat accessor: some rules may read .severity
    @property
    def severity(self) -> Optional[Severity]:
        return self.severity_level

    @field_validator("severity_level", mode="before")
    @classmethod
    def _normalize_severity_level(cls, v):
        """
        Accept common synonyms and normalize to: info | minor | major | critical.
        Unknown values fall back to 'major' (conservative).
        """
        if v is None:
            return None
        s = str(v).strip().lower()
        mapping = {
            "info": "info",
            "information": "info",
            "low": "minor",
            "minor": "minor",
            "med": "major",
            "medium": "major",
            "moderate": "major",
            "major": "major",
            "high": "critical",
            "severe": "critical",
            "critical": "critical",
        }
        return mapping.get(s, "major")

    @field_validator("legal_basis", mode="before")
    @classmethod
    def _coerce_legal_basis(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            return [v]
        if isinstance(v, list):
            return [str(x) for x in v]
        return [str(v)]

    @field_validator("citations", mode="before")
    @classmethod
    def _coerce_citations(cls, v):
        # Accept str | list[str] | list[dict] | list[Citation] | dict
        if v is None:
            return []
        if isinstance(v, list):
            out: List[Citation] = []
            for it in v:
                if isinstance(it, Citation):
                    out.append(it)
                elif isinstance(it, str):
                    out.append(Citation(instrument=it, section=""))
                elif isinstance(it, dict):
                    out.append(
                        Citation(
                            system=it.get("system", "UK"),
                            instrument=str(it.get("instrument", "")),
                            section=str(it.get("section", "")),
                            url=it.get("url"),
                            title=it.get("title"),
                            source=it.get("source"),
                            link=it.get("link"),
                            score=it.get("score"),
                            evidence=it.get("evidence"),
                            evidence_text=it.get("evidence_text"),
                        )
                    )
                else:
                    out.append(Citation(instrument=str(it), section=""))
            return out
        if isinstance(v, str):
            return [Citation(instrument=v, section="")]
        if isinstance(v, dict):
            return [
                Citation(
                    system=v.get("system", "UK"),
                    instrument=str(v.get("instrument", "")),
                    section=str(v.get("section", "")),
                    url=v.get("url"),
                    title=v.get("title"),
                    source=v.get("source"),
                    link=v.get("link"),
                    score=v.get("score"),
                    evidence=v.get("evidence"),
                    evidence_text=v.get("evidence_text"),
                )
            ]
        return [Citation(instrument=str(v), section="")]

    @model_validator(mode="after")
    def _derive_risk_from_severity(self):
        """
        If risk is missing, derive from severity_level:
          info->low, minor->medium, major->high, critical->critical
        """
        if self.risk is None and self.severity_level is not None:
            mapping: Dict[Severity, RiskLevel] = {  # type: ignore[type-arg]
                "info": "low",
                "minor": "medium",
                "major": "high",
                "critical": "critical",
            }
            self.risk = mapping.get(self.severity_level, "medium")
        return self


class Diagnostic(AppBaseModel):
    """
    Structured diagnostic record (engine trace; not a Finding).
    """

    rule: str
    message: str
    severity: Optional[Literal["info", "warn", "error"]] = "info"
    legal_basis: List[str] = Field(default_factory=list)

    @field_validator("severity", mode="before")
    @classmethod
    def _coerce_severity(cls, v):
        if v is None:
            return "info"
        s = str(v).strip().lower()
        mapping = {
            "medium": "info",
            "minor": "info",
            "notice": "info",
            "warning": "warn",
            "major": "warn",
            "critical": "error",
            "error": "error",
            "err": "error",
        }
        return mapping.get(s, s if s in {"info", "warn", "error"} else "info")

    @field_validator("legal_basis", mode="before")
    @classmethod
    def _coerce_legal_basis(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            return [v]
        if isinstance(v, list):
            return [str(x) for x in v]
        return [str(v)]


class Suggestion(AppBaseModel):
    """
    Human-readable suggestion for clause improvements.
    Accepts both `text=` and legacy `message=` (panel shape).
    """

    text: str = Field(alias="message")
    reason: Optional[str] = None
    span: Optional[Span] = None
    source: Optional[Literal["rule", "gpt"]] = None  # provenance


class GPTDraftResponse(AppBaseModel):
    """
    Minimal LLM/proxy draft response (used by /api/gpt-draft).
    """

    draft_text: str
    explanation: Optional[str] = None
    score: Optional[float] = None
    metadata: Dict[str, str] = Field(default_factory=dict)


# ----------------------------------------------------------------------------
# Clause (SSOT)
# ----------------------------------------------------------------------------
class Clause(AppBaseModel):
    """
    Extracted clause with location anchor.
    """

    id: str
    type: str
    text: str
    span: Span
    title: Optional[str] = None


# ----------------------------------------------------------------------------
# AnalysisOutput (SSOT, per clause) + legacy compat
# ----------------------------------------------------------------------------
class AnalysisOutput(AppBaseModel):
    """
    Unified result for rule functions (per clause).
    SSOT fields are provided while legacy panel-shape fields are kept for compat.
    """

    # Identity
    clause_id: Optional[str] = None
    clause_type: str
    text: str

    # Core status (safe default; invariants may upgrade to WARN/FAIL)
    status: Status = "OK"

    # Scoring (SSOT)
    score: int = Field(default=0, ge=0, le=100, description="0..100")
    risk: RiskLevel = "medium"
    severity_level: Severity = "minor"

    # Legacy compat (do not remove yet):
    risk_level: Optional[str] = None  # legacy textual risk
    severity: Optional[str] = None  # legacy textual severity (e.g., "medium")

    # Content
    findings: List[Finding] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    proposed_text: str = ""  # rule-synthesised alternative (if any)
    suggestions: List[Suggestion] = Field(default_factory=list)
    citations: List[Citation] = Field(default_factory=list)
    diagnostics: List[Diagnostic] = Field(default_factory=list)
    trace: List[str] = Field(default_factory=list)
    cross_refs: List[CrossRef] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    # Category/name (optional, for UI grouping)
    category: Optional[str] = None
    clause_name: Optional[str] = None

    # ---- Normalisers & invariants ------------------------------------------
    @field_validator("status", mode="before")  # [ADDED]
    @classmethod
    def _coerce_status_in(cls, v):
        """
        Accept case-insensitive and synonymic values:
          - 'pass' -> 'OK'
          - 'ok'   -> 'OK'
          - 'unknown' -> 'UNKNOWN'
          - otherwise keep WARN/FAIL as provided (case-insensitive)
        """
        if v is None:
            return "OK"
        s = str(v).strip().upper()
        if s == "PASS":
            return "OK"
        if s == "OK":
            return "OK"
        if s == "UNKNOWN":
            return "UNKNOWN"
        if s in {"WARN", "FAIL"}:
            return s
        # Any other value → fallback to OK (safe)
        return "OK"

    @field_validator("score", mode="before")
    @classmethod
    def _clamp_score(cls, v):
        if v is None:
            return 0
        try:
            iv = int(v)
        except Exception:
            iv = 0
        if iv < 0:
            return 0
        if iv > 100:
            return 100
        return iv

    @field_validator("diagnostics", mode="before")
    @classmethod
    def _coerce_diagnostics(cls, v):
        if v is None:
            return []
        out: List[Union[Diagnostic, dict, str]] = v if isinstance(v, list) else [v]
        normalized: List[Diagnostic] = []
        for item in out:
            if isinstance(item, Diagnostic):
                normalized.append(item)
            elif isinstance(item, str):
                normalized.append(Diagnostic(rule="ENGINE", message=item))
            elif isinstance(item, dict):
                normalized.append(
                    Diagnostic(
                        rule=str(item.get("rule", "ENGINE")),
                        message=str(item.get("message", "")),
                        severity=item.get("severity", "info"),
                        legal_basis=item.get("legal_basis", []),
                    )
                )
            else:
                normalized.append(Diagnostic(rule="ENGINE", message=str(item)))
        return normalized

    @field_validator("suggestions", mode="before")
    @classmethod
    def _coerce_suggestions(cls, v):
        if v is None:
            return []
        out: List[Union[Suggestion, dict, str]] = v if isinstance(v, list) else [v]
        normalized: List[Suggestion] = []
        for item in out:
            if isinstance(item, Suggestion):
                normalized.append(item)
            elif isinstance(item, str):
                normalized.append(Suggestion(text=item))
            elif isinstance(item, dict):
                msg = item.get("text", item.get("message", ""))
                normalized.append(
                    Suggestion(
                        text=msg,
                        reason=item.get("reason"),
                        span=item.get("span"),
                        source=item.get("source"),
                    )
                )
            else:
                normalized.append(Suggestion(text=str(item)))
        return normalized

    @field_validator("citations", mode="before")
    @classmethod
    def _coerce_citations(cls, v):
        # Accept str | list[str] | list[dict] | list[Citation] | dict
        if v is None:
            return []
        if isinstance(v, list):
            out: List[Citation] = []
            for it in v:
                if isinstance(it, Citation):
                    out.append(it)
                elif isinstance(it, str):
                    out.append(Citation(instrument=it, section=""))
                elif isinstance(it, dict):
                    out.append(
                        Citation(
                            system=it.get("system", "UK"),
                            instrument=str(it.get("instrument", "")),
                            section=str(it.get("section", "")),
                            url=it.get("url"),
                            title=it.get("title"),
                            source=it.get("source"),
                            link=it.get("link"),
                            score=it.get("score"),
                            evidence=it.get("evidence"),
                            evidence_text=it.get("evidence_text"),
                        )
                    )
                else:
                    out.append(Citation(instrument=str(it), section=""))
            return out
        if isinstance(v, str):
            return [Citation(instrument=v, section="")]
        if isinstance(v, dict):
            return [
                Citation(
                    system=v.get("system", "UK"),
                    instrument=str(v.get("instrument", "")),
                    section=str(v.get("section", "")),
                    url=v.get("url"),
                    title=v.get("title"),
                    source=v.get("source"),
                    link=v.get("link"),
                    score=v.get("score"),
                    evidence=v.get("evidence"),
                    evidence_text=v.get("evidence_text"),
                )
            ]
        return [Citation(instrument=str(v), section="")]

    @field_validator("risk", mode="before")
    @classmethod
    def _normalise_risk(cls, v, info):
        """
        If SSOT risk missing, derive from legacy risk_level or critical finding.
        """
        if isinstance(v, str) and v.lower() in {"low", "medium", "high", "critical"}:
            return v.lower()
        # try legacy:
        legacy = info.data.get("risk_level")
        if isinstance(legacy, str):
            lv = legacy.lower().strip()
            if lv in {"low", "medium", "high", "critical"}:
                return lv
        # fallback: if any critical finding => at least "high"
        findings: List[Finding] = info.data.get("findings", []) or []
        if any(f.severity_level == "critical" for f in findings):
            return "high"
        return "medium"

    @field_validator("severity_level", mode="before")
    @classmethod
    def _normalise_severity(cls, v, info):
        """
        If SSOT severity missing, derive from legacy severity string.
        """
        if isinstance(v, str) and v.lower() in {"info", "minor", "major", "critical"}:
            return v.lower()
        legacy = info.data.get("severity")
        if isinstance(legacy, str):
            lv = legacy.lower().strip()
            mapping = {
                "info": "info",
                "low": "minor",
                "minor": "minor",
                "medium": "major",
                "med": "major",
                "moderate": "major",
                "high": "critical",
                "critical": "critical",
            }
            return mapping.get(lv, "minor")
        # derive from strongest finding
        findings: List[Finding] = info.data.get("findings", []) or []
        order = {"info": 0, "minor": 1, "major": 2, "critical": 3}
        strongest = "minor"
        for f in findings:
            lvl = f.severity_level or "minor"
            if order[lvl] > order[strongest]:
                strongest = lvl
        return strongest

        @field_validator("status")  # mode=after by default
        @classmethod
        def _enforce_status(cls, v, info):
            """
            Invariants:
            - critical => FAIL
            - findings==[] and proposed_text=="" => status=OK
            - normalize PASS -> OK (already coerced in _coerce_status_in)
            """
            findings: List[Finding] = info.data.get("findings", []) or []
            proposed_text: str = info.data.get("proposed_text", "") or ""

            # 1) Invariant: any critical finding forces FAIL
            if any(f.severity_level == "critical" for f in findings):
                return "FAIL"

            # 2) Preserve explicit UNKNOWN from input/normaliser
            if v == "UNKNOWN":
                return "UNKNOWN"

            # 3) Preserve explicit WARN/FAIL/OK if already set
            if v in {"WARN", "FAIL", "OK"}:
                return v

            # 4) Default when nothing flagged and no proposed text
            if len(findings) == 0 and proposed_text == "":
                return "OK"

            # 5) Safe fallback
            return "OK"


# ============================================================================
# Legacy panel-compat DTO (do not break)
# ============================================================================
class Analysis(AppBaseModel):
    """
    Legacy panel-shape block used by the current taskpane JS.
    """

    clause_type: str
    findings: List[Finding] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    proposed_text: str = ""
    score: int = 0
    risk: str = "medium"
    severity: str = "medium"
    status: Status = "OK"


class AnalyzeResponse(AppBaseModel):
    """
    Legacy response shape expected by the Word panel today.
    """

    analysis: Analysis
    results: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    clauses: List[Dict[str, Any]] = Field(default_factory=list)


# ============================================================================
# Base document for SSOT document-level models
# ============================================================================
class BaseDoc(AppBaseModel):
    """
    Base SSOT document model with schema version.
    """

    schema_version: str = Field(default=SCHEMA_VERSION)


# ----------------------------------------------------------------------------
# Document-level SSOT
# ----------------------------------------------------------------------------
class DocIndex(AppBaseModel):
    """
    Document index with clause anchors for UI navigation.
    """

    document_name: Optional[str] = None
    language: Optional[str] = None
    clauses: List[Clause] = Field(default_factory=list)


class DocumentAnalysis(BaseDoc):
    """
    Aggregated document-level analysis (SSOT).
    """

    document_name: Optional[str] = None
    jurisdiction: Optional[str] = None
    policy: Dict[str, Any] = Field(default_factory=dict)

    # Aggregated scores/status
    summary_score: int = Field(default=0, ge=0, le=100)
    summary_risk: RiskLevel = "low"
    summary_status: Status = "OK"

    # Content
    residual_risks: List[Finding] = Field(default_factory=list)
    analyses: List[AnalysisOutput] = Field(default_factory=list)
    cross_refs: List[CrossRef] = Field(default_factory=list)
    index: DocIndex = Field(default_factory=DocIndex)

    # Observability / performance
    timings: Dict[str, float] = Field(
        default_factory=dict, description="ms timings per stage"
    )
    errors: List[str] = Field(
        default_factory=list, description="non-fatal errors/warnings during run"
    )

    # ---- Aggregation invariants --------------------------------------------
    @field_validator("summary_score", mode="before")
    @classmethod
    def _clamp_or_compute_summary_score(cls, v, info):
        """
        If value is not provided, compute mean of analyses[].score.
        Then clamp to [0..100].
        """
        analyses: List[AnalysisOutput] = info.data.get("analyses", []) or []
        if v is None and analyses:
            try:
                avg = sum(a.score for a in analyses) / max(1, len(analyses))
            except Exception:
                avg = 0
            v = int(round(avg))
        if v is None:
            v = 0
        try:
            iv = int(v)
        except Exception:
            iv = 0
        if iv < 0:
            return 0
        if iv > 100:
            return 100
        return iv

    @field_validator("summary_status")
    @classmethod
    def _derive_summary_status(cls, v, info):
        """
        Derive from analyses if present:
          if any FAIL -> FAIL
          elif any WARN -> WARN
          else OK
        """
        analyses: List[AnalysisOutput] = info.data.get("analyses", []) or []
        if analyses:
            if any(a.status == "FAIL" for a in analyses):
                return "FAIL"
            if any(a.status == "WARN" for a in analyses):
                return "WARN"
            return "OK"
        return v

    @field_validator("summary_risk")
    @classmethod
    def _derive_summary_risk(cls, v, info):
        """
        Summary risk = maximum risk among analyses by ordinal:
          low=0 < medium=1 < high=2 < critical=3
        """
        analyses: List[AnalysisOutput] = info.data.get("analyses", []) or []
        if analyses:
            max_ord = 0
            for a in analyses:
                max_ord = max(max_ord, risk_to_ordinal(getattr(a, "risk", "medium")))
            return ordinal_to_risk(max_ord)
        return v


# ----------------------------------------------------------------------------
# Combined analyze response (legacy + SSOT)
# ----------------------------------------------------------------------------
class AnalyzeOut(AppBaseModel):
    """
    Combined response for /api/analyze:
    - legacy panel-shape (analysis/results/clauses)
    - SSOT document-level block (document)
    - top-level schema version for legacy/e2e consumers
    """

    schema_version: str = Field(default=SCHEMA_VERSION)
    analysis: Analysis
    results: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    clauses: List[Dict[str, Any]] = Field(default_factory=list)
    document: DocumentAnalysis


# ============================================================================
# Step 4: Public DTOs for /api/gpt-draft, /api/suggest, /api/qa-recheck
# ============================================================================
class DraftIn(AppBaseModel):
    """
    Request DTO for /api/gpt-draft.
    At least one of (text, analysis) must be provided.
    If clause_type is missing, it is derived from analysis (if present).
    """

    text: Optional[str] = None
    analysis: Optional[Union[AnalysisOutput, Dict[str, Any]]] = None
    clause_type: Optional[str] = None
    mode: DraftMode = "friendly"
    jurisdiction: Optional[str] = None
    constraints: Optional[Dict[str, Any]] = None
    profile: Optional[Literal["smart", "vanilla"]] = None

    @model_validator(mode="after")
    def _require_text_or_analysis(self):
        if (
            self.text is None or str(self.text).strip() == ""
        ) and self.analysis is None:
            raise ValueError("DraftIn: either 'text' or 'analysis' must be provided")
        # derive clause_type if missing
        if self.clause_type is None and isinstance(self.analysis, AnalysisOutput):
            self.clause_type = self.analysis.clause_type
        if self.clause_type is None and isinstance(self.analysis, dict):
            ct = self.analysis.get("clause_type")
            if isinstance(ct, str) and ct.strip():
                self.clause_type = ct
        # normalise text
        if isinstance(self.text, str):
            self.text = self.text.strip()
        return self


class DraftOut(AppBaseModel):
    """
    Response DTO for /api/gpt-draft.
    """

    draft_text: str
    alternatives: List[str] = Field(default_factory=list)
    rationale: Optional[str] = None
    citations_hint: List[Citation] = Field(default_factory=list)
    model: str = "rule-based"
    # NEW (observability)
    elapsed_ms: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def citations(self) -> List[Citation]:
        # non-breaking convenience alias for UI
        return list(self.citations_hint)

    @field_validator("citations_hint", mode="before")
    @classmethod
    def _coerce_citations_hint(cls, v):
        if v is None:
            return []
        if isinstance(v, list):
            out: List[Citation] = []
            for it in v:
                if isinstance(it, Citation):
                    out.append(it)
                elif isinstance(it, str):
                    out.append(Citation(instrument=it, section=""))
                elif isinstance(it, dict):
                    out.append(
                        Citation(
                            system=it.get("system", "UK"),
                            instrument=str(it.get("instrument", "")),
                            section=str(it.get("section", "")),
                            url=it.get("url"),
                            title=it.get("title"),
                            source=it.get("source"),
                            link=it.get("link"),
                            score=it.get("score"),
                            evidence=it.get("evidence"),
                            evidence_text=it.get("evidence_text"),
                        )
                    )
                else:
                    out.append(Citation(instrument=str(it), section=""))
            return out
        if isinstance(v, str):
            return [Citation(instrument=v, section="")]
        if isinstance(v, dict):
            return [
                Citation(
                    system=v.get("system", "UK"),
                    instrument=str(v.get("instrument", "")),
                    section=str(v.get("section", "")),
                    url=v.get("url"),
                    title=v.get("title"),
                    source=v.get("source"),
                    link=v.get("link"),
                    score=v.get("score"),
                    evidence=v.get("evidence"),
                    evidence_text=v.get("evidence_text"),
                )
            ]
        return [Citation(instrument=str(v), section="")]


class SuggestIn(AppBaseModel):
    """
    Request DTO for /api/suggest.
    """

    clause_id: Optional[str] = None
    clause_type: Optional[str] = None
    text: str
    mode: DraftMode = "friendly"
    top_k: int = Field(default=3, ge=1, le=10)
    profile: Optional[Literal["smart", "vanilla"]] = None

    @model_validator(mode="after")
    def _validate_requirements(self):
        # text must be non-empty (strip)
        if not isinstance(self.text, str) or self.text.strip() == "":
            raise ValueError("SuggestIn: 'text' is required and must be non-empty")
        self.text = self.text.strip()

        # XOR: exactly one of clause_id or clause_type must be provided
        has_id = isinstance(self.clause_id, str) and self.clause_id.strip() != ""
        has_type = isinstance(self.clause_type, str) and self.clause_type.strip() != ""
        if has_id == has_type:  # both True or both False
            raise ValueError(
                "SuggestIn: provide exactly one of 'clause_id' or 'clause_type'"
            )
        return self


class SuggestOut(AppBaseModel):
    """
    Response DTO for /api/suggest.
    """

    suggestions: List[Suggestion]


class SuggestEdit(AppBaseModel):
    """Single edit suggestion for /api/suggest_edits."""

    span: Span
    insert: Optional[str] = None
    delete: Optional[str] = None
    rationale: str
    citations: List[Citation]
    evidence: Optional[List[str]] = None
    verification_status: Optional[
        Literal["verified", "partially_verified", "unverified", "failed"]
    ] = None
    flags: Optional[List[str]] = None
    operations: Optional[List[Literal["replace", "insertAfter", "comment"]]] = None

    @model_validator(mode="after")
    def _autofill_operations(self):
        if self.operations is None and (self.insert is not None or self.delete is not None):
            self.operations = ["replace"]
        return self


class SuggestResponse(AppBaseModel):
    """Response DTO for /api/suggest_edits."""

    suggestions: List[SuggestEdit]


class AppliedChange(AppBaseModel):
    """
    Item describing a change applied to a clause between analyses.
    (Legacy DTO kept for backward compatibility)
    """

    clause_id: str
    before: str
    after: str


class DeltaMetrics(AppBaseModel):
    """
    Delta metrics for QA recheck (score/risk/status deltas).
    risk_delta reflects ordinal difference using RISK_ORDER: low=0, medium=1, high=2, critical=3
    """

    score_delta: int = Field(default=0, ge=-100, le=100)
    risk_delta: int = Field(default=0, ge=-3, le=3)  # ordinal diff: now - prev
    status_from: Status = "OK"
    status_to: Status = "OK"


class QARecheckIn(AppBaseModel):
    """
    Request DTO for /api/qa-recheck.
    """

    document_name: Optional[str] = None
    text: str
    applied_changes: List[TextPatch] = Field(default_factory=list)
    profile: Optional[Literal["smart", "vanilla"]] = None

    @model_validator(mode="after")
    def _validate_text(self):
        if not isinstance(self.text, str) or self.text.strip() == "":
            raise ValueError("QARecheckIn.text must be a non-empty string")
        self.text = self.text.strip()
        return self


class QARecheckOut(AppBaseModel):
    """
    Response DTO for /api/qa-recheck.
    Flattened deltas with backward-compat for legacy `{'deltas': {...}}`.
    """

    score_delta: int = Field(default=0, ge=-100, le=100)
    risk_delta: int = Field(default=0, ge=-3, le=3)
    status_from: Status = "OK"
    status_to: Status = "OK"
    residual_risks: List[Finding] = Field(default_factory=list)

    # Backward compatibility: accept legacy {'deltas': {...}} payloads
    @model_validator(mode="before")
    @classmethod
    def _from_legacy(cls, data: Any):
        if (
            isinstance(data, dict)
            and "deltas" in data
            and isinstance(data["deltas"], dict)
        ):
            d = data.get("deltas") or {}
            # copy flat fields if not already present
            data.setdefault("score_delta", d.get("score_delta", 0))
            data.setdefault("risk_delta", d.get("risk_delta", 0))
            data.setdefault("status_from", d.get("status_from", "OK"))
            data.setdefault("status_to", d.get("status_to", "OK"))
        return data


# ============================================================================
# Explain endpoint
# ============================================================================
class ExplainRequest(AppBaseModel):
    """Request DTO for /api/explain."""

    finding: Finding
    text: Optional[str] = None
    citations: Optional[List[Citation]] = None


class ExplainResponse(AppBaseModel):
    """Response DTO for /api/explain."""

    reasoning: str
    citations: List[Citation] = Field(default_factory=list)
    evidence: List[Evidence] = Field(default_factory=list)
    verification_status: Literal["ok", "missing_citations", "invalid"] = "ok"
    trace: Optional[str] = None
    x_schema_version: str = Field(default=SCHEMA_VERSION, alias="x_schema_version")


# ============================================================================
# Trace export
# ============================================================================
class TraceOut(AppBaseModel):
    """Trace payload returned by /api/trace/{cid}."""

    cid: str
    created_at: str
    input: Dict[str, Any] = Field(default_factory=dict)
    analysis: Dict[str, Any] = Field(default_factory=dict)
    meta: Dict[str, Any] = Field(default_factory=dict)
    x_schema_version: str = Field(default=SCHEMA_VERSION, alias="x_schema_version")
    events: List[Dict[str, Any]] = Field(default_factory=list)

    @field_validator("cid")
    @classmethod
    def _validate_cid(cls, v: str) -> str:
        import re

        if not re.fullmatch(r"[0-9a-fA-F]{64}", v or ""):
            raise ValueError("invalid cid")
        return v
