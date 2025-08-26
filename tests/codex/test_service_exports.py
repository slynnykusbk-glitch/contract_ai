def test_exceptions_available_both_places():
    from contract_review_app.gpt.interfaces import ProviderTimeoutError as A
    from contract_review_app.gpt.service import ProviderTimeoutError as B
    assert A is B
