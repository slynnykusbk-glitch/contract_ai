import logging
from contract_review_app.report.i18n import get_translator


def test_i18n_basic_translation_en():
    t = get_translator("en")
    assert t("report.title") == "Contract Analysis Report"
    assert t("summary.ok") == "OK"


def test_i18n_basic_translation_uk():
    t = get_translator("uk")
    assert t("report.title") == "Звіт аналізу договору"
    assert t("summary.ok") == "ОК"  # локалізований варіант


def test_i18n_fallback_to_en():
    t = get_translator("uk")
    # штучний ключ — існує лише в EN
    # додамо перевірку fallback (використаємо наявний ключ EN, який є однаковим у обох,
    # але для стабільності створимо вигаданий)
    missing_key = "only.en.key"
    # емулюємо ситуацію: напряму викликаємо t з неіснуючим ключем
    val = t(missing_key)
    # очікуємо повернення самого ключа, оскільки його нема ні в UK, ні в EN
    assert val == missing_key


def test_i18n_logs_missing_key(caplog):
    t = get_translator("uk")
    with caplog.at_level(logging.WARNING):
        val = t("non.existent.key")
        assert "missing key" in caplog.text
        assert val == "non.existent.key"


def test_i18n_formatting():
    t = get_translator("en")
    # Додамо тимчасовий форматний ключ через monkeypatch таблиці — або перевіримо на існуючих
    # Тут використаємо загальний механізм format:
    key = "format.example"
    from contract_review_app.report.messages_en import MESSAGES as EN

    EN[key] = "Hello, {name}!"
    assert t(key, name="World") == "Hello, World!"
    # при відсутності параметра форматування не впаде, бо ми передаємо kwargs лише коли є


def test_all_used_keys_exist_in_some_locale():
    # мінімальна перевірка: ключі, які ми точно використовуємо в шаблонах RG1-5
    keys = [
        "report.title",
        "report.subtitle",
        "summary.overview",
        "summary.total",
        "summary.ok",
        "summary.warn",
        "summary.fail",
        "summary.note",
        "toc.title",
        "clause.type",
        "clause.score",
        "clause.risk_level",
        "clause.severity",
        "clause.issues",
        "clause.recommendations",
        "clause.law_refs",
        "clause.back_to_original",
        "footer.app_name",
    ]
    from contract_review_app.report.messages_en import MESSAGES as EN
    from contract_review_app.report.messages_uk import MESSAGES as UK

    for k in keys:
        assert (k in EN) or (k in UK), f"Missing i18n key: {k}"
