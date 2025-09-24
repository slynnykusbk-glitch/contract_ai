from __future__ import annotations

import re
from pathlib import Path

from bump_build import bump_build


def test_build_token_injected(tmp_path):
    token = bump_build()

    assert re.fullmatch(r"build-\d{8}-\d{6}", token)

    manifest = Path("word_addin_dev/manifest.xml").read_text(encoding="utf-8")
    assert f"b={token}" in manifest
    assert f"v={token}" in manifest

    html = Path(
        "contract_review_app/contract_review_app/static/panel/taskpane.html"
    ).read_text(encoding="utf-8")
    assert f"taskpane.bundle.js?b={token}" in html

    token_file = Path(
        "contract_review_app/contract_review_app/static/panel/.build-token"
    )
    assert token_file.read_text(encoding="utf-8").strip() == token
