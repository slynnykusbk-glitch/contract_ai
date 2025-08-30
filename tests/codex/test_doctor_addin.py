import json
import subprocess
import sys


def test_doctor_addin_section(tmp_path):
    prefix = tmp_path / "diag" / "analysis"
    prefix.parent.mkdir()
    cmd = [sys.executable, "tools/doctor.py", "--out", str(prefix), "--json"]
    rc = subprocess.call(cmd)
    assert rc == 0
    data = json.loads(prefix.with_suffix(".json").read_text(encoding="utf-8"))
    addin = data.get("addin", {})
    assert "manifest" in addin and "bundle" in addin

    manifest = addin["manifest"]
    assert "exists" in manifest
    if manifest["exists"]:
        assert manifest.get("id")
        assert manifest.get("version")
        assert manifest.get("source")
        assert manifest.get("permissions")

    bundle = addin["bundle"]
    assert "exists" in bundle
    if bundle["exists"]:
        assert isinstance(bundle.get("size"), int)
        assert bundle.get("size", 0) > 0
        assert isinstance(bundle.get("mtime"), str) and bundle.get("mtime")
