from __future__ import annotations

from typing import Dict, List, Optional

from contract_review_app.core.schemas import AnalysisInput


def _sanitize_text(s: str) -> str:
    return (s or "").strip()


def normalize_for_rules(
    extracted: Dict[str, str],
    *,
    doc_id: Optional[str] = None,
    source: str = "intake.extractor",
) -> List[AnalysisInput]:
    """
    Перетворює {clause_type: text} → List[AnalysisInput] (Pydantic) у стабільному порядку.

    Примітка: оскільки у вашій схемі AnalysisInput немає полів doc_id/source,
    ми кладемо їх у metadata.
    """
    if not isinstance(extracted, dict) or not extracted:
        return []

    items = []
    for k, v in extracted.items():
        ct = (str(k or "")).strip().lower()
        tx = _sanitize_text(str(v or ""))
        if not ct or not tx:
            continue
        items.append((ct, tx))

    items.sort(key=lambda kv: kv[0])

    out: List[AnalysisInput] = []
    for idx, (ct, tx) in enumerate(items):
        meta = {
            "index": str(idx),
            "len": str(len(tx.split())),
            "char_count": str(len(tx)),
            "clause_type": ct,
        }
        if doc_id:
            meta["doc_id"] = doc_id
        if source:
            meta["source"] = source

        out.append(
            AnalysisInput(
                clause_type=ct,
                text=tx,
                metadata=meta,
            )
        )
    return out
