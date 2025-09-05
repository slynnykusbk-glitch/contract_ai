import pathlib

HTML = pathlib.Path('word_addin_dev/taskpane.html').read_text(encoding='utf-8')


def _exists(id_sel: str, role: str) -> bool:
    return (f'id="{id_sel}"' in HTML) or (f'data-role="{role}"' in HTML)


def test_clause_type_slot_exists():
    assert _exists('resClauseType', 'clause-type')


def test_findings_list_slot_exists():
    assert _exists('findingsList', 'findings')


def test_recommendations_list_slot_exists():
    assert _exists('recoList', 'recommendations')


def test_raw_json_toggle_slot_exists():
    assert _exists('toggleRaw', 'toggle-raw-json')


def test_raw_json_pre_slot_exists():
    assert _exists('rawJson', 'raw-json')


def test_btn_annotate_exists():
    assert _exists('btnAnnotate', 'annotate') or 'id="btnAnnotate"' in HTML


def test_btn_apply_tracked_exists():
    assert _exists('btnApplyTracked', 'apply-tracked') or 'id="btnApplyTracked"' in HTML


def test_btn_accept_reject_exist():
    assert 'id="btnAcceptAll"' in HTML and 'id="btnRejectAll"' in HTML
