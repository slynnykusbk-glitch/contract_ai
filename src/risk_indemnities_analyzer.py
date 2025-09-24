import re
from typing import Dict, Any, Optional

# helper to ensure deterministic quoting in yaml output
try:
    import yaml  # type: ignore

    class _QuotedString(str):
        pass

    def _quoted_presenter(dumper, data):
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style='"')

    yaml.add_representer(_QuotedString, _quoted_presenter)
except Exception:  # pragma: no cover - yaml not available in minimal runtime

    class _QuotedString(str):
        pass


DOCX_HINT = re.compile(r"</w:t>", re.I)

PATTERNS = {
    "indemnify_defend_hold_harmless": re.compile(
        r"defend,\s*indemnify,\s*release,\s*and\s*hold\s*harmless", re.I
    ),
    "conseq_header": re.compile(r"\bConsequential\s+Loss\b", re.I),
    "conseq_profit": re.compile(
        r"loss\s+of\s+(?:or\s+deferment\s+of\s+)?revenue|profit|anticipated\s+profit",
        re.I,
    ),
    "conseq_production": re.compile(
        r"loss\s+(?:and\s*or\s*deferral\s+of\s+)?production", re.I
    ),
    "conseq_use": re.compile(r"loss\s+of\s+use", re.I),
    "conseq_revenue": re.compile(r"loss\s+or\s+deferment\s+of\s+revenue", re.I),
    "conseq_opportunity": re.compile(r"business\s+opportunity", re.I),
    "conseq_goodwill": re.compile(r"goodwill", re.I),
    "conseq_carveouts": re.compile(
        r"liquidated\s+damages|defence\s+costs|third[-\s]?party\s+judgments|confidentiality",
        re.I,
    ),
    "goods_accept_after_inspect": re.compile(
        r"shall\s+not\s+be\s+deemed\s+to\s+have\s+accepted\s+any\s+Goods\s+until.*reasonable\s+time\s+to\s+inspect.*following\s+delivery",
        re.I | re.S,
    ),
    "defend_term": re.compile(r"\bdefend\b", re.I),
}


def _normalize(txt: str) -> str:
    # collapse whitespace deterministically
    return re.sub(r"\s+", " ", txt).strip()


def _docx_to_text(path: str) -> str:
    # minimal, deterministic parser: python-docx when available, otherwise unzip fallback
    try:
        import docx  # type: ignore

        doc = docx.Document(path)
        return "\n".join(p.text for p in doc.paragraphs)
    except Exception:
        import zipfile

        with zipfile.ZipFile(path) as z:
            xml = z.read("word/document.xml")
        text = re.sub(rb"<w:tab[^>]*>", b"\t", xml)
        text = re.sub(rb"<[^>]+>", b" ", text)
        return text.decode("utf-8", errors="ignore")


def analyze(text: Optional[str] = None, path: Optional[str] = None) -> Dict[str, Any]:
    assert text or path, "provide text or path"
    if path and not text:
        text = _docx_to_text(path)
    t = _normalize(text)

    conseq_hits = sum(
        bool(PATTERNS[k].search(t))
        for k in [
            "conseq_profit",
            "conseq_production",
            "conseq_use",
            "conseq_revenue",
            "conseq_opportunity",
            "conseq_goodwill",
        ]
    )

    out: Dict[str, Any] = {
        "risk_indemnities": {
            "knock_for_knock_personnel": {"present": bool(False)},  # optional in v1
            "knock_for_knock_property": {"present": bool(False)},  # optional in v1
            "pollution_split": {"present": bool(False)},  # optional in v1
            "third_party_fault_based": {"present": bool(False)},  # optional in v1
            "defence_mechanics": {"present": bool(PATTERNS["defend_term"].search(t))},
            "flow_down_subcontracts": {"present": bool(False)},  # optional in v1
            "goods_risk_until_acceptance": {
                "present": bool(PATTERNS["goods_accept_after_inspect"].search(t))
            },
            "goods_rejection_risk_reverts": {"present": bool(False)},  # optional in v1
            "consequential_loss_defined": {
                "present": bool(
                    PATTERNS["conseq_header"].search(t) and conseq_hits >= 4
                )
            },
            "consequential_loss_list": [
                "profit",
                "production",
                "use",
                "revenue",
                "opportunity",
                "goodwill",
            ],
            "consequential_loss_carveouts_present": {
                "present": bool(PATTERNS["conseq_carveouts"].search(t))
            },
            "indemnify_defend_hold_harmless": {
                "present": bool(PATTERNS["indemnify_defend_hold_harmless"].search(t))
            },
        },
        "meta": {
            "parser": "docx" if path else "plain",
            "version": _QuotedString("1.0.0"),
        },
    }
    return out
