from __future__ import annotations

import types


def test_load_clause_patterns_basic(monkeypatch):
    # Створюємо тимчасові дані config через monkeypatch
    fake_cfg = types.SimpleNamespace()
    fake_cfg.CLAUSE_KEYWORDS = {
        "Definitions": ["Definition", "SHALL MEAN", "means", "  "],
        "Payment": ["fees", "charges", "INVOICE", ""],
        "  ": ["x"],  # має бути відкинуто
    }
    fake_cfg.ALIASES = {
        "Definitions and interpretation": "Definitions",
        "Liability": "Limitation_of_Liability",  # canonical може бути відсутній і має відфільтруватися
        "  ": "Definitions",  # відкинути
    }

    import contract_review_app.intake.patterns as patterns

    monkeypatch.setattr(
        patterns, "CLAUSE_KEYWORDS", fake_cfg.CLAUSE_KEYWORDS, raising=False
    )
    monkeypatch.setattr(patterns, "ALIASES", fake_cfg.ALIASES, raising=False)

    # перезбирати не потрібно — функції працюють із значень у модулі
    keywords, aliases = patterns.load_clause_patterns()

    # Перевірка нормалізації ключових слів
    assert "definitions" in keywords and "payment" in keywords
    assert keywords["definitions"] == ["definition", "means", "shall mean"]
    assert "  " not in keywords  # відкинуто порожній ключ

    # Перевірка alias → lowercase, фільтрація невідомого canonical
    assert aliases.get("definitions and interpretation") == "definitions"
    assert "liability" not in aliases  # бо canonical відсутній серед keywords


def test_load_clause_patterns_det_order(monkeypatch):
    # Перевірка детермінованого порядку (sorted by key)
    fake_cfg = types.SimpleNamespace()
    fake_cfg.CLAUSE_KEYWORDS = {
        "b": ["y", "x"],
        "a": ["B", "a"],
    }
    fake_cfg.ALIASES = {"B-Alt": "b", "A-Alt": "a"}

    import contract_review_app.intake.patterns as patterns

    monkeypatch.setattr(
        patterns, "CLAUSE_KEYWORDS", fake_cfg.CLAUSE_KEYWORDS, raising=False
    )
    monkeypatch.setattr(patterns, "ALIASES", fake_cfg.ALIASES, raising=False)

    keywords, aliases = patterns.load_clause_patterns()
    assert list(keywords.keys()) == ["a", "b"]
    assert keywords["a"] == ["a", "b"]
    assert keywords["b"] == ["x", "y"]
    assert list(aliases.keys()) == ["a-alt", "b-alt"]
