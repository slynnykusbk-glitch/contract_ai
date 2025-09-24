from pathlib import Path
import shutil
import types
import tools.panel_dev_sync as pds


def test_panel_dev_sync_copies_and_bumps(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    src = root / "word_addin_dev" / "app" / "assets"
    dest = (
        root
        / "contract_review_app"
        / "contract_review_app"
        / "static"
        / "panel"
        / "app"
        / "assets"
    )
    src.mkdir(parents=True)
    (src / "api-client.js").write_text("client __BUILD_TS__")
    (src / "store.js").write_text("store __BUILD_TS__")
    taskpane = (
        root
        / "contract_review_app"
        / "contract_review_app"
        / "static"
        / "panel"
        / "taskpane.html"
    )
    taskpane.parent.mkdir(parents=True, exist_ok=True)
    taskpane.write_text('<script src="taskpane.bundle.js?b=__BUILD_TS__"></script>')

    fake_token = "build-20000101-000000"

    def fake_build_ts():
        pass

    def fake_build_panel_main():
        dest.mkdir(parents=True, exist_ok=True)
        for p in src.glob("*"):
            shutil.copy2(p, dest / p.name)
        for p in dest.rglob("*"):
            p.write_text(p.read_text().replace("__BUILD_TS__", fake_token))
        taskpane.write_text(taskpane.read_text().replace("__BUILD_TS__", fake_token))

    monkeypatch.setattr(pds, "build_ts", fake_build_ts)
    monkeypatch.setattr(pds, "ROOT", root)
    monkeypatch.setattr(
        pds, "build_panel", types.SimpleNamespace(main=fake_build_panel_main)
    )

    pds.main()

    assert (dest / "api-client.js").read_text() == f"client {fake_token}"
    assert (dest / "store.js").read_text() == f"store {fake_token}"
    assert fake_token in taskpane.read_text()
