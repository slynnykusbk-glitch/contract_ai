def test_engine_import_smoke():
    __import__("contract_review_app.engine")
    assert True
