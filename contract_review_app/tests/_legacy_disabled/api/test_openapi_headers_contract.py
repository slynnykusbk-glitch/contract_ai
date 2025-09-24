import importlib
import os

os.environ.setdefault("CONTRACTAI_LLM_API", "1")
app = importlib.reload(importlib.import_module("contract_review_app.api.app")).app


def test_openapi_headers_contract():
    schema = app.openapi()
    headers = schema.get("components", {}).get("headers", {})
    assert "XSchemaVersion" in headers
    assert "XLatencyMs" in headers
    assert "XCid" in headers
    for path in ["/api/analyze", "/api/gpt-draft"]:
        op = schema["paths"][path]["post"]
        resp_headers = op["responses"]["200"]["headers"]
        assert (
            resp_headers["x-schema-version"]["$ref"]
            == "#/components/headers/XSchemaVersion"
        )
        assert resp_headers["x-latency-ms"]["$ref"] == "#/components/headers/XLatencyMs"
        assert resp_headers["x-cid"]["$ref"] == "#/components/headers/XCid"
