from pathlib import Path

def test_panel_selftest_defaults():
    html = (Path(__file__).resolve().parents[2] / "word_addin_dev" / "panel_selftest.html").read_text(encoding="utf-8")
    assert "https://127.0.0.1:9443" in html
    assert "/api/analyze" not in html
