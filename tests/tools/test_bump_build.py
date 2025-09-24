from pathlib import Path
from bump_build import bump_build, PLACEHOLDER


def test_bump_build_limits_paths(tmp_path):
    repo = tmp_path / "repo"
    panel = repo / "contract_review_app" / "contract_review_app" / "static" / "panel"
    other = repo / "other"
    panel.mkdir(parents=True)
    other.mkdir(parents=True)
    (panel / "taskpane.html").write_text(PLACEHOLDER)
    (other / "file.txt").write_text(PLACEHOLDER)

    token = bump_build(root=repo, paths=[panel])

    assert (panel / "taskpane.html").read_text() == token
    # other file remains untouched
    assert (other / "file.txt").read_text() == PLACEHOLDER
