def test_security_import_smoke():
    __import__("contract_review_app.security")
    assert True
