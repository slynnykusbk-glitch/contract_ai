from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[3]))

from datetime import datetime
from tempfile import TemporaryDirectory

import pytest

from contract_review_app.rules_v2 import ENGINE_VERSION, PolicyPackLoader


def create_file(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def test_execute_python_and_hybrid() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        pk1 = root / "pk1"
        pk1.mkdir()

        create_file(pk1 / "ruleA.yaml", "title: A\n")
        create_file(
            pk1 / "ruleB.py",
            (
                "from contract_review_app.rules_v2 import ENGINE_VERSION, FindingV2\n"
                "from datetime import datetime\n"
                "def rule_main(ctx):\n"
                "    return [FindingV2(id='1', pack='pk1', rule_id='ruleB', title={'en':'t'}, severity='Low',"
                " category='cat', message={'en':'m'}, explain={'en':'e'}, suggestion={'en':'s'},"
                " version='0', created_at=datetime.utcnow(), engine_version=ENGINE_VERSION)]\n"
            ),
        )
        create_file(pk1 / "ruleC.yaml", 'python: "ruleC_impl.py"\n')
        create_file(
            pk1 / "ruleC_impl.py",
            (
                "def rule_main(ctx):\n"
                "    return [{'id':'2','pack':'pk1','rule_id':'ruleC','title':{'en':'t'},"
                "'severity':'High','category':'cat','message':{'en':'m'},'explain':{'en':'e'},"
                "'suggestion':{'en':'s'},'version':'0','created_at':ctx['now'],'engine_version':ctx['engine_version']}]\n"
            ),
        )

        loader = PolicyPackLoader(root)
        rules = loader.discover()
        ctx = {"now": datetime.utcnow(), "engine_version": ENGINE_VERSION}
        py_rules = [r for r in rules if r.fmt != "yaml"]
        findings = loader.execute(py_rules, ctx)

        assert findings
        f = findings[0]
        assert f.pack == "pk1"
        assert f.severity in {"High", "Medium", "Low"}
        assert isinstance(f.created_at, datetime)
        assert f.engine_version == ENGINE_VERSION

        yaml_rule = [r for r in rules if r.fmt == "yaml"]
        with pytest.raises(NotImplementedError):
            loader.execute(yaml_rule, ctx)
