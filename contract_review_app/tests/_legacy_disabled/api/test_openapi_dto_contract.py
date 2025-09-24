from contract_review_app.api.app import app


REF = "#/components/schemas/{}"


def test_openapi_dto_contract():
    schema = app.openapi()
    paths = schema["paths"]

    analyze = paths["/api/analyze"]["post"]
    assert analyze["requestBody"]["content"]["application/json"]["schema"][
        "$ref"
    ] == REF.format("AnalyzeRequest")
    assert analyze["responses"]["200"]["content"]["application/json"]["schema"][
        "$ref"
    ] == REF.format("AnalyzeResponse")

    p = "/api/citation/resolve"
    op = paths[p]["post"]
    assert op["requestBody"]["content"]["application/json"]["schema"][
        "$ref"
    ] == REF.format("CitationResolveRequest")
    assert op["responses"]["200"]["content"]["application/json"]["schema"][
        "$ref"
    ] == REF.format("CitationResolveResponse")

    if "/api/corpus/search" in paths:
        corpus = paths["/api/corpus/search"]["post"]
        assert corpus["requestBody"]["content"]["application/json"]["schema"][
            "$ref"
        ] == REF.format("CorpusSearchRequest")
        assert corpus["responses"]["200"]["content"]["application/json"]["schema"][
            "$ref"
        ] == REF.format("CorpusSearchResponse")

    comps = schema["components"]["schemas"]
    for name in ["Finding", "Span", "Segment", "SearchHit", "CitationInput"]:
        assert name in comps
