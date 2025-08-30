import json

from tools import doctor


ALLOWED_STATUSES = {"OK", "WARN", "MISSING"}


def _stub_gatherers(monkeypatch):
    monkeypatch.setattr(doctor, "gather_env", lambda: {"env": {"NO_RETENTION": "1"}})
    monkeypatch.setattr(doctor, "gather_git", lambda: {})
    monkeypatch.setattr(doctor, "gather_precommit", lambda: {"config_exists": True})
    monkeypatch.setattr(
        doctor,
        "gather_backend",
        lambda: {
            "endpoints": [
                {"path": "/api/analyze", "method": "POST"},
                {"path": "/api/gpt/draft", "method": "POST"},
                {"path": "/api/learning/item", "method": "GET"},
            ]
        },
    )
    monkeypatch.setattr(
        doctor,
        "gather_llm",
        lambda backend: {
            "providers_detected": ["mock"],
            "node_is_mock": True,
            "has_draft_endpoint": True,
        },
    )
    monkeypatch.setattr(doctor, "gather_service", lambda: {"exports": {"LLMService": True}})
    monkeypatch.setattr(doctor, "gather_api", lambda: {})
    monkeypatch.setattr(
        doctor,
        "gather_rules",
        lambda: {"python": {"count": 1, "samples": []}, "yaml": {"count": 0, "samples": []}},
    )
    monkeypatch.setattr(
        doctor,
        "gather_addin",
        lambda: {"manifest": {"exists": False}, "bundle": {"exists": False}},
    )
    monkeypatch.setattr(doctor, "gather_runtime", lambda: {})
    monkeypatch.setattr(doctor, "gather_inventory", lambda: {})
    monkeypatch.setattr(doctor, "gather_repo", lambda: {})
    monkeypatch.setattr(
        doctor,
        "gather_quality",
        lambda: {"ruff": {"status": "ok", "issues_total": 0}, "mypy": {"status": "ok", "errors_total": 0}},
    )
    monkeypatch.setattr(doctor, "gather_smoke", lambda: {})


def test_blocks_present_and_ids_unique():
    ids = [b["id"] for b in doctor.BLOCKS]
    assert len(ids) == 14
    assert ids == [f"B{i}" for i in range(14)]
    assert len(set(ids)) == 14


def test_json_structure_and_status_values(monkeypatch, tmp_path):
    _stub_gatherers(monkeypatch)
    prefix = tmp_path / "analysis"
    doctor.main(["--out", str(prefix), "--json", "--html"])
    data = json.loads(prefix.with_suffix(".json").read_text("utf-8"))
    assert "generated_at_utc" in data
    assert "overall_score" in data
    assert len(data["blocks"]) == 14
    scores = [b["score"] for b in data["blocks"]]
    assert data["overall_score"] == int(round(sum(scores) / len(scores)))
    for block in data["blocks"]:
        assert block["status"] in ALLOWED_STATUSES
        assert 0 <= block["score"] <= 100


def test_html_contains_all_block_names(monkeypatch, tmp_path):
    _stub_gatherers(monkeypatch)
    prefix = tmp_path / "analysis"
    doctor.main(["--out", str(prefix), "--json", "--html"])
    html = prefix.with_suffix(".html").read_text("utf-8")
    for block in doctor.BLOCKS:
        assert block["name"] in html


def test_scoring_determinism(monkeypatch, tmp_path):
    _stub_gatherers(monkeypatch)
    prefix = tmp_path / "analysis"
    doctor.main(["--out", str(prefix), "--json"])
    data = json.loads(prefix.with_suffix(".json").read_text("utf-8"))
    statuses = {b["id"]: b["status"] for b in data["blocks"]}
    assert statuses["B0"] == "OK"
    assert statuses["B3"] == "WARN"
    assert statuses["B9"] == "MISSING"
    scores = {b["id"]: b["score"] for b in data["blocks"]}
    expected = int(round(sum(scores.values()) / len(scores)))
    assert data["overall_score"] == expected
