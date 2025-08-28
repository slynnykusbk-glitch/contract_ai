from contract_review_app.llm.verification import verify_output_contains_citations


def test_verification_all_ids_present():
    evidence = [{"id": "c1"}, {"id": "c2"}]
    text = "See [c1] and [c2] for details."
    assert verify_output_contains_citations(text, evidence) == "verified"


def test_verification_none_present():
    evidence = [{"id": "c1"}, {"id": "c2"}]
    text = "No markers here."
    assert verify_output_contains_citations(text, evidence) == "unverified"


def test_verification_partial():
    evidence = [{"id": "c1"}, {"id": "c2"}]
    text = "Only [c1] present."
    assert verify_output_contains_citations(text, evidence) == "partially_verified"


def test_verification_failed_if_empty():
    evidence = [{"id": "c1"}]
    assert verify_output_contains_citations(" ", evidence) == "failed"
