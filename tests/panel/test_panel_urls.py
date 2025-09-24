from pathlib import Path
import subprocess

from fastapi.testclient import TestClient

from contract_review_app.api.app import CATALOG_DIR, app


def _ensure_catalog_manifest() -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    src_manifest = repo_root / "word_addin_dev" / "manifest.xml"
    assert src_manifest.is_file(), "Source manifest is missing"

    CATALOG_DIR.mkdir(parents=True, exist_ok=True)
    dest_manifest = CATALOG_DIR / "manifest.xml"
    dest_manifest.write_text(src_manifest.read_text(encoding="utf-8"), encoding="utf-8")
    return dest_manifest


def test_panel_selftest_defaults():
    html = (
        Path(__file__).resolve().parents[2] / "word_addin_dev" / "panel_selftest.html"
    ).read_text(encoding="utf-8")
    assert "https://127.0.0.1:9443" in html
    assert "/api/analyze" not in html


def test_https_endpoints_available(monkeypatch):
    manifest_path = _ensure_catalog_manifest()
    assert manifest_path.is_file()

    repo_root = Path(__file__).resolve().parents[2]
    launcher = repo_root / "tools" / "start_onedclick.ps1"
    assert launcher.is_file(), "Launcher script is missing"

    recorded: dict[str, object] = {}

    class _DummyProcess:
        returncode = 0

        def wait(self, timeout=None):  # pragma: no cover - compatibility shim
            return self.returncode

        def poll(self):  # pragma: no cover - compatibility shim
            return self.returncode

    def _fake_popen(cmd, *args, **kwargs):
        recorded["cmd"] = list(cmd)
        recorded["kwargs"] = kwargs
        return _DummyProcess()

    monkeypatch.setattr(subprocess, "Popen", _fake_popen)

    remove_after = False
    try:
        manifest_path.relative_to(repo_root)
        remove_after = True
    except ValueError:
        remove_after = False

    try:
        process = subprocess.Popen(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(launcher),
                "-SkipBrowser",
            ]
        )
        assert isinstance(process, _DummyProcess)
        assert recorded["cmd"][0].lower().endswith("powershell.exe")
        assert (
            str(launcher) in recorded["cmd"]
        ), "Expected launcher path in PowerShell command"

        with TestClient(app) as client:
            health = client.get("/health")
            assert health.status_code == 200

            catalog = client.get("/catalog/manifest.xml")
            assert catalog.status_code == 200
            assert "Contract AI" in catalog.text

            panel = client.get("/panel/taskpane.html")
            assert panel.status_code == 200
    finally:
        if remove_after:
            manifest_path.unlink(missing_ok=True)
