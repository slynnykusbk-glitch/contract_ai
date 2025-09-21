from contract_review_app.core.trace import TraceStore


def _payload(text: str) -> dict:
    return {"body": {"value": text}}


def test_trace_store_size_limit_evicts_lru():
    store = TraceStore(maxlen=10, max_size_bytes=60)

    store.put("cid-1", _payload("a" * 3))
    store.put("cid-2", _payload("b" * 3))

    assert "cid-1" in store.list()
    assert "cid-2" in store.list()

    store.put("cid-3", _payload("c" * 3))

    assert store.get("cid-1") is None
    assert store.list() == ["cid-2", "cid-3"]
