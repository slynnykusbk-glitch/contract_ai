import sys
import tarfile
import zipfile
import subprocess
from pathlib import Path
import importlib.util
import pytest

if importlib.util.find_spec("build") is None:  # pragma: no cover - optional dependency
    pytest.skip("python -m build not available", allow_module_level=True)


def test_packaging_manifest(tmp_path):
    subprocess.check_call(
        [sys.executable, "-m", "build", "--sdist", "--wheel", "--outdir", str(tmp_path)]
    )
    sdist = next(tmp_path.glob("*.tar.gz"))
    wheel = next(tmp_path.glob("*.whl"))

    policy_prefix = "contract_review_app/legal_rules/policy_packs"
    core_prefix = "core/rules"

    with tarfile.open(sdist, "r:gz") as tar:
        names = tar.getnames()
        assert any(policy_prefix in n and n.endswith(".yaml") for n in names)
        assert any(core_prefix in n and n.endswith(".yaml") for n in names)

    with zipfile.ZipFile(wheel, "r") as z:
        names = z.namelist()
        assert any(n.startswith(policy_prefix) and n.endswith(".yaml") for n in names)
        assert any(n.startswith(core_prefix) and n.endswith(".yaml") for n in names)
