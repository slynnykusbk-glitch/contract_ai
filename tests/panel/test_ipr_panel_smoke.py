from tests.panel.helpers import analyze_and_render


def test_ipr_comment_format():
    txt = (
        "Title to the Agreement Documentation shall vest in Company. "
        "Contractor grants a perpetual, irrevocable licence only for the duration of the Agreement."
    )
    panel = analyze_and_render(txt)
    assert "[HIGH]" in panel or "[LOW]" in panel
    assert panel.count("Agreement Documentation") >= 1
