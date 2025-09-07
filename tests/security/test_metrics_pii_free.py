from __future__ import annotations

import re
from importlib import reload

from fastapi.testclient import TestClient


def test_metrics_pii_free(monkeypatch):
    monkeypatch.setenv("FEATURE_METRICS", "1")
    import contract_review_app.api.app as api_app
    reload(api_app)
    client = TestClient(api_app.app)
    contents = [
        client.get("/api/metrics").text,
        client.get("/api/metrics.csv").text,
        client.get("/api/metrics.html").text,
    ]
    pii = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+|\d{3}-\d{2}-\d{4}")
    for c in contents:
        assert not pii.search(c)
