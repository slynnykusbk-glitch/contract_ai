from __future__ import annotations

import io
from pathlib import Path
from textwrap import dedent

import pytest

from tools import rules_lint


def _write_yaml(path: Path, content: str) -> None:
    path.write_text(dedent(content).strip() + "\n", encoding="utf-8")


def test_rules_lint_reports_counts_and_issues(tmp_path: Path) -> None:
    file_path = tmp_path / "pack.yml"
    _write_yaml(
        file_path,
        """
        - rule_id: rule.ok
          channel: presence
          salience: 10
        - rule_id: rule.no_channel
          salience: 30
        - rule_id: rule.invalid_channel
          channel: weird
          salience: 55
        - rule_id: rule.no_salience
          channel: policy
        - rule_id: rule.invalid_salience
          channel: substantive
          salience: 200
        - rule_id: rule.duplicate
          channel: drafting
          salience: 42
        - rule_id: rule.duplicate
          channel: drafting
          salience: 42
        """,
    )

    result = rules_lint.lint_rules([tmp_path])

    assert result.total_rules == 7
    assert result.channel_count == 5
    assert result.salience_count == 5

    assert {rec.rule_id for rec in result.missing_channel} == {"rule.no_channel"}
    assert {rec.rule_id for rec in result.invalid_channel} == {"rule.invalid_channel"}
    assert {rec.rule_id for rec in result.missing_salience} == {"rule.no_salience"}
    assert {rec.rule_id for rec in result.invalid_salience} == {"rule.invalid_salience"}
    assert set(result.duplicates) == {"rule.duplicate"}


@pytest.mark.parametrize("strict", [True, False])
def test_run_respects_strict_mode(tmp_path: Path, strict: bool) -> None:
    file_path = tmp_path / "pack.yml"
    _write_yaml(
        file_path,
        """
        - rule_id: rule.one
          channel: presence
        - rule_id: rule.one
          channel: presence
        """,
    )

    buffer = io.StringIO()
    exit_code = rules_lint.run([tmp_path], strict=strict, stream=buffer)

    output = buffer.getvalue()
    assert "Duplicate rule_id" in output
    if strict:
        assert exit_code == 1
    else:
        assert exit_code == 0
