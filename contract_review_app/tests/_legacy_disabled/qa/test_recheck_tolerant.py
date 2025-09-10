from contract_review_app.api.app import _top3_residuals


class DummyFinding:
    def __init__(self, code, message, severity):
        self.code = code
        self.message = message
        self.severity = severity


def test_recheck_tolerant_mixed_list():
    mixed = [
        {"code": "A", "message": "dict", "severity": "high"},
        DummyFinding("B", "obj", "low"),
    ]
    out = _top3_residuals({"analysis": {"findings": mixed}})
    assert len(out) == 2
    assert out[0]["code"] == "A"
    assert out[1]["code"] == "B"
