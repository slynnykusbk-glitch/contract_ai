from pathlib import Path
from contract_review_app.api.app import app


def test_panel_route_and_bundle_exists():
    paths = {getattr(r, 'path', None) for r in app.routes}
    assert '/panel' in paths

    builds = sorted(Path('word_addin_dev/app').glob('build-*'))
    assert builds, 'no panel build found'
    latest = builds[-1]
    assert (latest / 'taskpane.bundle.js').exists(), 'bundle missing'
