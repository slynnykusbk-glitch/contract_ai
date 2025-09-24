from tests.panel.helpers import analyze_and_render


def test_title_comment_format_and_no_spam():
    txt = (
        "Title to the Agreement Documentation shall vest in Company upon payment. "
        "Company may enter supplier premises on insolvency to recover Company Property."
    )
    panel = analyze_and_render(txt)
    assert "[" in panel
    assert panel.count("vest in Company") <= 1
