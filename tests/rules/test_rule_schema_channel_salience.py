from textwrap import dedent

from contract_review_app.legal_rules import loader


def _write_rule(tmp_path, content: str) -> None:
    (tmp_path / "pack.yml").write_text(dedent(content), encoding="utf-8")


def test_load_rule_without_channel_salience_keeps_defaults(tmp_path):
    _write_rule(
        tmp_path,
        """
        ---
        id: test.rule.default
        doc_types: [nda]
        jurisdiction: [us]
        severity: high
        triggers:
          regex:
            - regex: foo
        finding:
          message: Default rule
        """,
    )

    rules = loader.load_rules(base_dir=tmp_path)
    assert len(rules) == 1
    rule = rules[0]
    assert "channel" in rule
    assert rule["channel"] is None
    assert rule["salience"] == 50


def test_load_rule_with_channel_salience_passes_through(tmp_path):
    _write_rule(
        tmp_path,
        """
        ---
        id: test.rule.custom
        doc_types: [msa]
        jurisdiction: [uk]
        severity: low
        channel: presence
        salience: 15
        triggers:
          regex:
            - regex: bar
        finding:
          message: Custom rule
        """,
    )

    rules = loader.load_rules(base_dir=tmp_path)
    assert len(rules) == 1
    rule = rules[0]
    assert rule["channel"] == "presence"
    assert rule["salience"] == 15
