from tests.integration.test_trace_flag_bootstrap import (
    _build_client,
    _cleanup,
    _headers,
)


def test_trace_html_sections_present():
    client, modules = _build_client("1")
    try:
        response = client.post(
            "/api/analyze", headers=_headers(), json={"text": "Sample"}
        )
        assert response.status_code == 200
        cid = response.headers.get("x-cid")
        assert cid

        trace_html = client.get(f"/api/trace/{cid}.html")
        assert trace_html.status_code == 200
        body = trace_html.text
        assert ">Features<" in body
        assert ">Dispatch<" in body
        assert ">Constraints<" in body
        assert ">Proposals<" in body
    finally:
        _cleanup(client, modules)
