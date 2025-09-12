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


def test_build_panel_cli(tmp_path):
    root = tmp_path / 'repo'
    tools_dir = root / 'tools'
    src = root / 'word_addin_dev'
    dest = root / 'contract_review_app' / 'contract_review_app' / 'static' / 'panel'
    assets = src / 'app' / 'assets'
    assets.mkdir(parents=True, exist_ok=True)
    for name in ['taskpane.html', 'taskpane.bundle.js', 'panel_selftest.html']:
        (src / name).write_text(f'{name} __BUILD_TS__')
    (assets / 'dummy.txt').write_text('x')

    # copy build_panel script
    tools_dir.mkdir(parents=True)
    script_path = tools_dir / 'build_panel.py'
    from pathlib import Path
    script_path.write_text(Path(bp.__file__).read_text())
    # write simple bump_build
    (root / 'bump_build.py').write_text(
        'from pathlib import Path\n'
        'def bump_build(root: Path | None = None):\n'
        '    root = Path(root or ".")\n'
        '    for name in ["taskpane.html","taskpane.bundle.js","panel_selftest.html"]:\n'
        '        p = root/"word_addin_dev"/name\n'
        '        p.write_text(p.read_text().replace("__BUILD_TS__", "123"))\n'
    )

    import subprocess, sys
    subprocess.check_call([sys.executable, 'tools/build_panel.py'], cwd=root)

    for name in ['taskpane.html', 'taskpane.bundle.js', 'panel_selftest.html']:
        out = (dest / name).read_text()
        assert '123' in out and '__BUILD_TS__' not in out
    assert (dest / 'app' / 'assets' / 'dummy.txt').exists()
