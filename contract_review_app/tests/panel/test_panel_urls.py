from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SELFTEST = ROOT / "word_addin_dev" / "panel_selftest.html"


def test_panel_selftest_default_backend_is_https9443():
    html = SELFTEST.read_text(encoding="utf-8")
    assert "https://127.0.0.1:9443" in html


def test_panel_selftest_uses_unified_ls_key():
    html = SELFTEST.read_text(encoding="utf-8").lower()
    assert "panel:backendurl".lower() in html


def test_normbase_forces_https_for_9443():
    html = SELFTEST.read_text(encoding="utf-8")
    # must contain the http->https replace for localhost:9443 like taskpane
    assert (
        "replace(/^http:\/\/(127\\.0\\.0\\.1|localhost)(:9443)" in html
    ), "normBase must force https for :9443"
