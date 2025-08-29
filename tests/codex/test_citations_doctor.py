import json
from contract_review_app.core.schemas import AnalysisInput, Citation
from contract_review_app.legal_rules import legal_rules


def test_confidentiality_citations_present():
    text = (
        "Confidential Information means any information provided by one party"
        " to the other that is marked as confidential."
    )
    out = legal_rules.analyze(AnalysisInput(clause_type="confidentiality", text=text))

    assert out.findings, "expected at least one finding"
    first_finding = out.findings[0]
    assert first_finding.citations and isinstance(first_finding.citations[0], Citation)

    assert out.citations and isinstance(out.citations[0], Citation)

    for c in [*out.citations, *first_finding.citations]:
        assert isinstance(c.title, str) and c.title
        assert c.source_type is None or isinstance(c.source_type, str)
        assert c.source_id is None or isinstance(c.source_id, str)
        assert c.meta == {} or isinstance(c.meta, dict)

    data = json.loads(out.model_dump_json())
    assert data["citations"], "citations missing from JSON output"
    assert data["findings"][0][
        "citations"
    ], "finding citations missing from JSON output"
