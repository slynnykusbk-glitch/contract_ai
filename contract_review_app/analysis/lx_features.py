# contract_review_app/analysis/lx_features.py
from __future__ import annotations

from typing import Dict, List, Optional, Any
import re

from contract_review_app.core.lx_types import LxDocFeatures, LxFeatureSet
# Переиспользуем существующие регексы из текущего кода (ничего не меняем в них)
from .extract import (
    _COMP_NO_RE,
    _DURATION_RE,
    _JURIS_RE,
    _LAW_RE,
    _MONEY_RE,
)

# Лёгкие паттерны для многометочной классификации клауз
_LABEL_PATTERNS: Dict[str, re.Pattern[str]] = {
    "Payment": re.compile(r"\b(payment|remuneration|invoice)\b", re.I),
    "Term": re.compile(r"\bterm\b|\bremain in force\b", re.I),
    "Liability": re.compile(r"\bliabilit", re.I),
    "Confidentiality": re.compile(r"\bconfidential", re.I),
    "Indemnity": re.compile(r"\bindemnif", re.I),
    "GoverningLaw": re.compile(r"\bgoverning law\b", re.I),
    "Jurisdiction": re.compile(r"\bjurisdiction\b", re.I),
    "Dispute": re.compile(r"\bdispute\b", re.I),
    "IP": re.compile(r"\bintellectual property\b|\bIP\b", re.I),
    "Notices": re.compile(r"\bnotice(s)?\b", re.I),
    "Taxes": re.compile(r"\btax(es)?\b", re.I),
    "SetOff": re.compile(r"set[-\s]?off", re.I),
    "Interest": re.compile(r"\binterest\b", re.I),
    "Price": re.compile(r"\bprice\b|\bpricing\b", re.I),
    "SLA": re.compile(r"service level agreement|\bSLA\b", re.I),
    "KPI": re.compile(r"key performance indicator|\bKPI\b", re.I),
    "Acceptance": re.compile(r"\bacceptance\b", re.I),
    "Boilerplate": re.compile(r"\bthis agreement\b|\bhereby\b|\bthereof\b", re.I),
}


def _detect_labels(text: str) -> List[str]:
    labels: List[str] = []
    for name, pat in _LABEL_PATTERNS.items():
        if pat.search(text):
            labels.append(name)
    return labels


def _norm_parenthetical_numbers(text: str) -> str:
    # "sixty (60) days" -> "sixty  60  days" (чтобы _DURATION_RE увидел число)
    return re.sub(r"\((\d+)\)", r" \1 ", text)


def extract_l0_features(doc_text: str, segments: Any) -> LxDocFeatures:
    """
    Лёгкий L0-экстрактор:
    - НЕ меняет публичный ответ /api/analyze (результат уходит только во внутренние структуры/TRACE)
    - Использует существующие сегменты (list[dict|obj] с полями id/text).
    - Возвращает LxDocFeatures(by_segment=...).
    """
    by_segment: Dict[int, LxFeatureSet] = {}

    for seg in segments or []:
        # безопасно читаем id/text из dict или объекта
        if isinstance(seg, dict):
            seg_id = int(seg.get("id", 0))
            text = str(seg.get("text", "") or "")
        else:
            seg_id = int(getattr(seg, "id", 0) or 0)
            text = str(getattr(seg, "text", "") or "")

        fs = LxFeatureSet()  # из core.lx_types с дефолтами

        # 1) Метки (multi-label)
        fs.labels = _detect_labels(text)

        # 2) Сроки (durations) — берём первый встреченный per unit (days/weeks/months/years)
        durations: Dict[str, int] = {}
        for source in (text, _norm_parenthetical_numbers(text)):
            for m in _DURATION_RE.finditer(source):
                try:
                    val = int(m.group(1))
                except Exception:
                    continue
                unit = (m.group(2) or "").lower()
                if unit.endswith("s"):
                    unit = unit[:-1]
                key = f"{unit}s"  # нормализуем к множественному числу
                if key not in durations:
                    durations[key] = val
        fs.durations = durations  # Dict[str, int]

        # 3) Компании (UK company numbers)
        fs.company_numbers = [m.group(1) for m in _COMP_NO_RE.finditer(text)]

        # 4) Суммы — оставляем строковым представлением (без изменения извлекателей)
        amounts: List[str] = []
        for m in _MONEY_RE.finditer(text):
            cur = m.group(1) or ""
            raw = (m.group(2) or "").replace(",", "")
            amounts.append(f"{cur}{raw}")
        fs.amounts = amounts

        # 5) Нормы права / юрисдикция (первое попадание)
        law_m = _LAW_RE.search(text)
        if law_m:
            fs.law_signals = [law_m.group(1).strip()]
        juris_m = _JURIS_RE.search(text)
        if juris_m:
            fs.jurisdiction = juris_m.group(1).strip()

        # Остальные поля LxFeatureSet (parties/liability_caps/carveouts) остаются дефолтными

        by_segment[seg_id] = fs

    return LxDocFeatures(by_segment=by_segment)
