from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[3]))

from tempfile import TemporaryDirectory

from contract_review_app.rules_v2 import PolicyPackLoader


def create_file(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def test_discovery_priority() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        pk1 = root / "pk1"
        pk1.mkdir()
        pk2 = root / "pk2"
        pk2.mkdir()

        create_file(pk1 / "ruleA.yaml", "title: A\n")
        create_file(
            pk1 / "ruleB.py",
            "def rule_main(ctx):\n    return []\n",
        )
        create_file(pk1 / "ruleC.yaml", 'python: "ruleC_impl.py"\n')
        create_file(
            pk1 / "ruleC_impl.py",
            "def rule_main(ctx):\n    return []\n",
        )
        create_file(pk1 / "ruleD.yaml", "title: D\n")
        create_file(
            pk1 / "ruleD.py",
            "def rule_main(ctx):\n    return []\n",
        )
        create_file(
            pk2 / "ruleX.py",
            "def rule_main(ctx):\n    return []\n",
        )

        loader = PolicyPackLoader(root)
        rules = loader.discover()

        key_map = {(r.pack, r.rule_id): r for r in rules}
        assert key_map[("pk1", "ruleA")].fmt == "yaml"
        assert key_map[("pk1", "ruleB")].fmt == "python"
        assert key_map[("pk1", "ruleC")].fmt == "hybrid"
        assert key_map[("pk1", "ruleD")].fmt == "python"

        pairs = [(r.pack, r.rule_id) for r in rules]
        assert pairs == sorted(pairs)
        assert len(pairs) == len(set(pairs))
