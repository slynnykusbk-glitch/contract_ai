# 1. Константы приоритета групп
AGENDA_ORDER: dict[str, int] = {
    "presence": 10,
    "substantive": 20,
    "policy": 30,
    "law": 30,  # считаем на одном уровне с policy
    "drafting": 40,
    "grammar": 50,
    "fixup": 60,
}

# 2. Дефолтные salience по группам (если нет в finding/spec)
DEFAULT_SALIENCE: dict[str, int] = {
    "presence": 95,
    "substantive": 80,
    "policy": 70,
    "law": 70,
    "drafting": 40,
    "grammar": 20,
    "fixup": 10,
}

SALIENCE_MIN, SALIENCE_MAX = 0, 100


# 3. Нормализация канала → группа
def map_to_agenda_group(finding: dict) -> str:
    # приоритет источников: finding.channel → spec.channel → _infer_channel → fallback
    ch = (
        finding.get("channel")
        or finding.get("_spec_channel")  # опционально, если движок приклеит
        or finding.get("_inferred_channel")  # если уже computed
        or None
    )

    ch = str(ch).lower() if ch else ""

    # жёсткая нормализация
    if ch in ("presence",):
        return "presence"
    if ch in ("substantive", "substance"):
        return "substantive"
    if ch in ("policy", "law"):
        return ch
    if ch in ("drafting", "style"):
        return "drafting"
    if ch in ("grammar", "spelling", "typo"):
        return "grammar"
    if ch in ("fixup", "fix-ups", "fix"):
        return "fixup"

    # эвристика fallback по rule_id/тегам, если канал неизвестен
    rid = str(finding.get("rule_id", "")).lower()
    if rid.startswith(("presence_", "missing_", "must_have_")):
        return "presence"
    if rid.startswith(("draft_", "style_", "typo_")):
        return "drafting"
    # по умолчанию — substantive (самый безопасный юридический дефолт)
    return "substantive"


# 4. Разрешение salience
def resolve_salience(finding: dict) -> int:
    # 1) явный салинс
    if "salience" in finding:
        try:
            return max(SALIENCE_MIN, min(SALIENCE_MAX, int(finding["salience"])))
        except Exception:
            pass
    # 2) из spec (если движок проставил)
    if "_spec_salience" in finding:
        try:
            return max(SALIENCE_MIN, min(SALIENCE_MAX, int(finding["_spec_salience"])))
        except Exception:
            pass
    # 3) дефолт по группе
    grp = map_to_agenda_group(finding)
    return DEFAULT_SALIENCE.get(grp, 50)


# 5. Ключ сортировки
def agenda_sort_key(f: dict) -> tuple:
    grp = map_to_agenda_group(f)
    sal = resolve_salience(f)
    anchor = f.get("anchor") or {}
    start = int(anchor.get("start", 0))
    rid = str(f.get("rule_id", ""))
    return (AGENDA_ORDER.get(grp, 999), -sal, start, rid)


# 6. IoU пересечения диапазонов
def span_iou(a: tuple[int, int], b: tuple[int, int]) -> float:
    (as_, ae), (bs, be) = a, b
    inter = max(0, min(ae, be) - max(as_, bs))
    if inter == 0:
        return 0.0
    union = max(ae, be) - min(as_, bs)
    return inter / union if union > 0 else 0.0


# 7. Решение конфликта по overlap (оставить “сильнейший”)
def stronger(f1: dict, f2: dict) -> dict:
    return min((f1, f2), key=agenda_sort_key)
