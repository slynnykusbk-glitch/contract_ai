import yaml
from pathlib import Path
from datetime import datetime
from types import SimpleNamespace

from contract_review_app.rules_v2.loader import PolicyPackLoader
from contract_review_app.rules_v2.models import FindingV2, ENGINE_VERSION


def _write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def _ctx(obj):
    if isinstance(obj, dict):
        return SimpleNamespace(**{k: _ctx(v) for k, v in obj.items()})
    return obj


def test_crosscheck_packs(tmp_path):
    glaw_dir = tmp_path / "governing_law_vs_jurisdiction"
    glaw_dir.mkdir()
    _write(
        glaw_dir / "glaw_juris.yaml",
        """
id: "glaw_juris"
pack: "governing_law_vs_jurisdiction"
severity: "High"
category: "CrossCheck"
title: { en: "Governing law vs Jurisdiction conflict" }
message: { en: "Governing law and forum selection appear misaligned." }
explain: { en: "When governing law and chosen courts differ, clarify alignment." }
suggestion:{ en: "Align governing law with jurisdiction or add clear forum selection." }
version: "2.0.0"
engine_version: "2.0.0"
checks:
- when: "context.meta.governing_law != context.meta.jurisdiction"
  produce:
    evidence: ["GLaw != Jurisdiction"]
    citation: ["GLaw/Juris best practice"]
    flags: ["crosscheck","yaml"]
""",
    )

    gdpr_dir = tmp_path / "confidentiality_gdpr_crossref"
    gdpr_dir.mkdir()
    _write(
        gdpr_dir / "conf_gdpr.yaml",
        """
id: "conf_gdpr"
pack: "confidentiality_gdpr_crossref"
severity: "Medium"
category: "DataProtection"
title: { en: "Confidentiality mentions personal data; add DPA terms" }
message: { en: "Personal data referenced without clear data protection terms." }
explain: { en: "If personal data appears, ensure separate UK GDPR/DPA terms." }
suggestion:{ en: "Add data processing, roles, SCCs if transfers, etc." }
version: "2.0.0"
engine_version: "2.0.0"
python: "conf_gdpr_impl.py"
checks:
- when: "context.text contains 'personal data'"
  produce:
    flags: ["hybrid","gdpr"]
""",
    )

    _write(
        gdpr_dir / "conf_gdpr_impl.py",
        """from datetime import datetime, timezone
from contract_review_app.rules_v2.models import FindingV2, ENGINE_VERSION

def rule_main(context):
    text = (context or {}).get("text") or ""
    meta = (context or {}).get("meta") or {}
    if "personal data" in text.lower() and not bool(meta.get("data_terms")):
        return [FindingV2(
            id="conf_gdpr",
            pack="confidentiality_gdpr_crossref",
            rule_id="conf_gdpr",
            title={"en":"Confidentiality mentions personal data; add DPA terms"},
            severity="Medium",
            category="DataProtection",
            message={"en":"Personal data referenced without clear data protection terms."},
            explain={"en":"If personal data appears, ensure separate UK GDPR/DPA terms."},
            suggestion={"en":"Add data processing, roles, SCCs if transfers, etc."},
            evidence=["PD detected"],
            citation=["UK GDPR / DPA 2018"],
            flags=["hybrid"],
            meta={},
            version="2.0.0",
            created_at=datetime.now(timezone.utc),
            engine_version=ENGINE_VERSION,
        )]
    return []
""",
    )

    _write(gdpr_dir / "conf_gdpr.py", "def rule_main(context):\n    return []\n")
    _write(
        gdpr_dir / "conf_gdpr_alt.yaml",
        """id: "conf_gdpr"
pack: "confidentiality_gdpr_crossref"
severity: "Low"
category: "DataProtection"
title: { en: "alt" }
message: { en: "alt" }
version: "2.0.0"
engine_version: "2.0.0"
checks: []
""",
    )

    loader = PolicyPackLoader(tmp_path)
    rules = loader.discover()
    ids = {(r.pack, r.id) for r in rules}
    assert len(ids) == len(rules)
    conf_rule = next(r for r in rules if r.id == "conf_gdpr")
    assert conf_rule.type == "hybrid"

    ctx_glaw_conflict = {"text": "Any", "meta": {"governing_law": "UK", "jurisdiction": "US"}}
    ctx_pd_missing = {"text": "Includes personal data", "meta": {"data_terms": False}}

    glaw_rules = [r for r in rules if r.pack == "governing_law_vs_jurisdiction"]
    gdpr_rules = [r for r in rules if r.pack == "confidentiality_gdpr_crossref"]

    glaw_findings = loader.execute(glaw_rules, ctx_glaw_conflict)
    assert glaw_findings
    fg = glaw_findings[0]
    assert fg.severity == "High"
    assert "en" in fg.title and "en" in fg.message
    assert fg.engine_version == ENGINE_VERSION
    assert isinstance(fg.created_at, datetime)
    assert fg.version

    gdpr_findings = loader.execute(gdpr_rules, ctx_pd_missing)
    assert gdpr_findings
    fp = gdpr_findings[0]
    assert "hybrid" in fp.flags
    assert fp.category == "DataProtection"
