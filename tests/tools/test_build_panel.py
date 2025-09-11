from tools import build_panel as bp

def test_build_panel_copies_and_substitutes(tmp_path, monkeypatch):
    root = tmp_path / 'repo'
    src = root / 'word_addin_dev'
    dest = root / 'out'
    assets = src / 'app' / 'assets'
    assets.mkdir(parents=True)
    (assets / 'dummy.txt').write_text('x')
    for name in ['taskpane.html', 'taskpane.bundle.js', 'panel_selftest.html']:
        (src / name).write_text(f'build {name} __BUILD_TS__')

    monkeypatch.setattr(bp, 'ROOT', root)
    monkeypatch.setattr(bp, 'SRC', src)
    monkeypatch.setattr(bp, 'DEST', dest)

    def fake_bump(path):
        for file in ['taskpane.html', 'taskpane.bundle.js', 'panel_selftest.html']:
            p = src / file
            p.write_text(p.read_text().replace('__BUILD_TS__', '123'))
    monkeypatch.setattr(bp, 'bump_build', fake_bump)

    bp.main()

    for name in ['taskpane.html', 'taskpane.bundle.js', 'panel_selftest.html']:
        out = (dest / name).read_text()
        assert '123' in out and '__BUILD_TS__' not in out
    assert (dest / 'app' / 'assets' / 'dummy.txt').exists()
