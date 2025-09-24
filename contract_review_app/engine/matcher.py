from __future__ import annotations
from typing import Any, Dict, List
import re

# Public API:
#   split_headings(text) -> [{"title": str, "start": int, "end": int}]
#   classify_sections(text) -> [{"clause_type": str, "title": str, "span": {"start": int, "length": int}}]

# -------------------- patterns: oil & gas oriented --------------------
try:
    # Prefer user/project-provided patterns if available
    from contract_review_app.engine import patterns_oilgas as _p  # type: ignore

    _RAW_PATTERNS = getattr(_p, "PATTERNS", None) or getattr(_p, "patterns", None)
except Exception:
    _RAW_PATTERNS = None

if not isinstance(_RAW_PATTERNS, dict):
    # Fallback minimal-yet-practical patterns (oil & gas + common commercial clauses)
    _RAW_PATTERNS = {
        "definitions": [r"\bdefinitions\b", r"\binterpretation\b"],
        "parties": [
            r"\bparties\b",
            r"\bthe parties\b",
            r"\bcontract(?:ing)? parties\b",
        ],
        "scope": [
            r"\bscope of (?:work|supply|services)\b",
            r"\bdeliverables?\b",
            r"\bstatement of work\b",
            r"\bSOW\b",
        ],
        "payment": [
            r"\bpayment\b",
            r"\bfees?\b",
            r"\bprice\b",
            r"\bconsideration\b",
            r"\binvoice\b",
        ],
        "warranty": [r"\bwarrant(?:y|ies)\b", r"\bguarantee\b"],
        "liability": [r"\blimitation of liability\b", r"\bliability\b"],
        "indemnity": [r"\bindemnif(?:y|ication)\b", r"\bhold harmless\b"],
        "confidentiality": [
            r"\bconfidentialit(?:y|ies)\b",
            r"\bnon[- ]disclosure\b",
            r"\bnda\b",
        ],
        "ip": [r"\bintellectual property\b", r"\bIP rights?\b", r"\blicen[cs]e\b"],
        "force_majeure": [r"\bforce majeure\b", r"\bFM\b"],
        "termination": [
            r"\btermination\b",
            r"\bterm (?:and|&) termination\b",
            r"\bend of (?:agreement|contract)\b",
        ],
        "governing_law": [
            r"\bgoverning law\b",
            r"\blaw and jurisdiction\b",
            r"\bjurisdiction\b",
        ],
        "dispute_resolution": [
            r"\bdispute resolution\b",
            r"\barbitration\b",
            r"\bmediation\b",
        ],
        "assignment": [r"\bassignment\b", r"\bnovat(?:e|ion)\b", r"\btransfer\b"],
        "change_control": [
            r"\bchange control\b",
            r"\bvariation\b",
            r"\bchange order\b",
        ],
        "subcontracting": [r"\bsubcontract(?:ing)?\b"],
        "insurance": [r"\binsurance\b", r"\binsured\b"],
        "audit": [r"\baudit\b", r"\binspection\b"],
        # Oil & Gas specifics
        "hsse": [
            r"\bHSE\b",
            r"\bHSSE\b",
            r"\bhealth(?:,?\s*safety)?(?:,?\s*security)?(?:,?\s*environment)?\b",
        ],
        "decommissioning": [r"\bdecommission(?:ing)?\b"],
        "drilling": [r"\bdrilling\b", r"\bwell operations?\b", r"\bBOP\b"],
        "psa_joa": [
            r"\bproduction sharing\b",
            r"\bPSA\b",
            r"\bJOA\b",
            r"\bjoint operating agreement\b",
        ],
        "unitisation": [r"\bunitis(?:e|ation)\b", r"\bunit agreement\b"],
        "gas_balancing": [
            r"\bgas balancing\b",
            r"\btake[- ]or[- ]pay\b",
            r"\bgas[- ]lift\b",
        ],
        "pipeline_transport": [
            r"\bpipeline\b",
            r"\btransport(?:ation)?\b",
            r"\btariff[s]?\b",
            r"\bincoterms\b",
        ],
        "offtake": [
            r"\boff[- ]?take\b",
            r"\blifting\b",
            r"\bnomination\b",
            r"\ballocation\b",
        ],
        "royalties": [r"\broyalt(?:y|ies)\b", r"\bprofit oil\b", r"\bcost oil\b"],
        "quality": [r"\bquality\b", r"\bQA\b", r"\bQC\b", r"\bspecifications?\b"],
        "delivery": [r"\bdelivery\b", r"\blogistics?\b", r"\bshipping\b"],
    }

# Compile regex patterns deterministically
_COMPILED_PATTERNS: Dict[str, List[re.Pattern]] = {}
for ctype in sorted(_RAW_PATTERNS.keys(), key=lambda s: s.lower()):
    pats = _RAW_PATTERNS[ctype] or []
    _COMPILED_PATTERNS[ctype] = [re.compile(p, re.IGNORECASE) for p in list(pats)]

# -------------------- heading detection --------------------
# ALLCAPS heading (allow digits/punct but no lowercase), and numbered headings like "1. TITLE"
_RE_ALLCAPS = re.compile(
    r"^(?P<title>(?=.*[A-Z])[A-Z0-9][A-Z0-9\s\-\(\)&/.,:]{2,})\s*$", re.MULTILINE
)
_RE_NUMBERED = re.compile(r"^(?P<title>\d+\.\s+[A-Z][^\n]*)$", re.MULTILINE)


def _line_end(text: str, start: int) -> int:
    pos = text.find("\n", start)
    return len(text) if pos == -1 else pos


def split_headings(text: str) -> List[Dict[str, int | str]]:
    text = text or ""
    candidates: Dict[int, str] = {}

    for m in _RE_ALLCAPS.finditer(text):
        s = m.start()
        # ensure we match a full line (avoid mid-paragraph uppercase)
        line_start = text.rfind("\n", 0, s) + 1
        if line_start == -1:
            line_start = 0
        if line_start != s:
            continue
        title = m.group("title").strip()
        if title:
            candidates.setdefault(s, title)

    for m in _RE_NUMBERED.finditer(text):
        s = m.start()
        line_start = text.rfind("\n", 0, s) + 1
        if line_start == -1:
            line_start = 0
        if line_start != s:
            continue
        title = m.group("title").strip()
        if title:
            candidates.setdefault(s, title)

    # Sort by start asc
    starts = sorted(candidates.keys())
    if not starts:
        return []

    sections: List[Dict[str, int | str]] = []
    for i, s in enumerate(starts):
        title = candidates[s]
        e = starts[i + 1] if i + 1 < len(starts) else len(text)
        e = max(s, min(e, len(text)))
        sections.append({"title": title, "start": s, "end": e})
    return sections


# -------------------- classification --------------------
def _context_window(text: str, start: int, span_end: int, radius: int = 300) -> str:
    a = max(0, start - radius)
    b = min(len(text), max(start, min(span_end, start + radius)))
    return text[a:b]


def _first_best_match(title: str, ctx: str) -> str:
    # Prefer title match; then context; deterministic order by clause_type asc, then pattern index asc
    for clause_type in sorted(_COMPILED_PATTERNS.keys(), key=lambda s: s.lower()):
        patterns = _COMPILED_PATTERNS[clause_type]
        for pat in patterns:
            if pat.search(title):
                return clause_type
    for clause_type in sorted(_COMPILED_PATTERNS.keys(), key=lambda s: s.lower()):
        patterns = _COMPILED_PATTERNS[clause_type]
        for pat in patterns:
            if pat.search(ctx):
                return clause_type
    return "unknown"


def classify_sections(text: str) -> List[Dict[str, Any]]:
    text = text or ""
    heads = split_headings(text)
    # If no headings, return single "unknown" section covering full text
    if not heads:
        start = 0
        end = len(text)
        return [
            {
                "clause_type": "unknown",
                "title": "DOCUMENT",
                "span": {"start": start, "length": max(0, end - start)},
            }
        ]

    out: List[Dict[str, Any]] = []
    for h in heads:
        start = int(h["start"])
        end = int(h["end"])
        start = max(0, min(start, len(text)))
        end = max(start, min(end, len(text)))
        title = str(h["title"]).strip()
        ctx = _context_window(text, start, end, 300)
        clause_type = _first_best_match(title, ctx)
        out.append(
            {
                "clause_type": clause_type,
                "title": title,
                "span": {"start": start, "length": max(0, end - start)},
            }
        )

    # Stable order: by start, then clause_type
    out.sort(key=lambda d: (int(d["span"]["start"]), str(d["clause_type"]).lower()))
    return out
