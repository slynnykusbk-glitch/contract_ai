import pytest
from contract_review_app.core.schemas import (
    AnalyzeOut, Analysis, DocumentAnalysis, AnalysisOutput,
    SuggestIn, DraftOut, QARecheckIn, QARecheckOut, TextPatch,
    Finding, Status
)

def test_suggestin_xor_and_defaults():
    # missing both -> error
    with pytest.raises(ValueError):
        SuggestIn(text="foo")
    # clause_id only -> ok
    s1 = SuggestIn(text="foo", clause_id="C1")
    assert s1.mode == "friendly" and 1 <= s1.top_k <= 10
    # clause_type only -> ok
    s2 = SuggestIn(text="bar", clause_type="termination", top_k=10)
    assert s2.top_k == 10
    # text trimmed
    s3 = SuggestIn(text="  baz  ", clause_id="C2")
    assert s3.text == "baz"

def test_qarecheckin_applied_changes_textpatch_normalization():
    # range with end -> length derived
    p1 = TextPatch(range={"start": 7, "end": 9}, text="X")
    assert p1.range == {"start": 7, "length": 2}
    # explicit length kept, non-negative
    p2 = TextPatch(range={"start": 0, "length": 0}, text="")
    assert p2.range == {"start": 0, "length": 0}
    # wiring inside QARecheckIn
    model = QARecheckIn(text="abc", applied_changes=[{"range":{"start":1,"end":1},"text":"Z"}])
    assert isinstance(model.applied_changes[0], TextPatch)

def test_qarecheckout_flat_fields_and_legacy_acceptance():
    # flat ok
    out = QARecheckOut(score_delta=5, risk_delta=-1, status_from="WARN", status_to="OK")
    assert out.score_delta == 5 and out.risk_delta == -1
    # legacy {"deltas":{...}} coerced
    legacy = QARecheckOut(deltas={"score_delta": 3, "risk_delta": -2, "status_from":"WARN","status_to":"OK"})
    assert legacy.score_delta == 3 and legacy.risk_delta == -2
    assert legacy.status_from == "WARN" and legacy.status_to == "OK"

def test_analyzeout_shape_still_legacy_compatible():
    an = Analysis(clause_type="termination", score=75, risk="medium", severity="major", status="OK")
    doc = DocumentAnalysis(analyses=[AnalysisOutput(clause_type="t", text="x", score=75)])
    out = AnalyzeOut(analysis=an, results={}, clauses=[], document=doc)
    d = out.model_dump()
    for k in ("analysis","results","clauses","document","schema_version"):
        assert k in d

def test_draftout_has_elapsed_and_metadata():
    d = DraftOut(draft_text="ok")
    assert hasattr(d, "elapsed_ms") and hasattr(d, "metadata")

def test_status_unknown_kept_as_unknown_in_analysisoutput():
    a = AnalysisOutput(clause_type="termination", text="t", status="unknown")
    assert a.status == "UNKNOWN"
