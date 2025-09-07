from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Dict, Iterable, List, Set

from datetime import datetime

from .schemas import (
    Acceptance,
    Coverage,
    MetricsResponse,
    Perf,
    QualityMetrics,
    RuleMetric,
)
from .datasets import load_rule_gold


def _clamp(v: float) -> float:
    if v < 0.0:
        return 0.0
    if v > 1.0:
        return 1.0
    return v


def compute_confusion(gold: Dict[str, bool], pred: Dict[str, bool]) -> List[RuleMetric]:
    metrics: List[RuleMetric] = []
    keys = set(gold.keys()) | set(pred.keys())
    for rid in sorted(keys):
        g = bool(gold.get(rid))
        p = bool(pred.get(rid))
        tp = int(g and p)
        fp = int(p and not g)
        fn = int(g and not p)
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        denom = precision + recall
        f1 = 2 * precision * recall / denom if denom else 0.0
        metrics.append(
            RuleMetric(
                rule_id=rid,
                tp=tp,
                fp=fp,
                fn=fn,
                precision=_clamp(precision),
                recall=_clamp(recall),
                f1=_clamp(f1),
            )
        )
    return metrics


def compute_coverage(rules_inventory: Set[str], fired: Set[str]) -> Coverage:
    total = len(rules_inventory)
    fired_count = len(rules_inventory & fired)
    cov = fired_count / total if total else 0.0
    return Coverage(rules_total=total, rules_fired=fired_count, coverage=_clamp(cov))


def load_acceptance(jsonl_path: Path) -> Acceptance:
    applied = 0
    rejected = 0
    if jsonl_path.exists():
        with jsonl_path.open("r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                action = str(obj.get("action", ""))
                if action in {"applied", "accepted_all"}:
                    applied += 1
                elif action in {"rejected", "rejected_all"}:
                    rejected += 1
    alpha = 1.0
    rate = (applied + alpha) / (applied + rejected + 2 * alpha)
    return Acceptance(applied=applied, rejected=rejected, acceptance_rate=_clamp(rate))


def measure_perf(traces: List[Dict]) -> Perf:
    docs = len(traces)
    total_ms = 0.0
    total_pages = 0
    for t in traces:
        try:
            ms = float(t.get("ms_elapsed", 0.0))
            pages = int(t.get("pages", 0))
        except Exception:
            continue
        if pages > 0:
            total_ms += ms
            total_pages += pages
    avg = total_ms / total_pages if total_pages else 0.0
    return Perf(docs=docs, avg_ms_per_page=avg)


def collect_metrics() -> MetricsResponse:
    gold, pred = load_rule_gold()
    rule_metrics = compute_confusion(gold, pred)
    inventory = set(gold.keys())
    fired = {m.rule_id for m in rule_metrics if m.tp or m.fp}
    coverage = compute_coverage(inventory, fired)
    acceptance = load_acceptance(Path("contract_review_app/learning/replay_buffer.jsonl"))
    perf = measure_perf([])
    qm = QualityMetrics(
        rules=rule_metrics,
        coverage=coverage,
        acceptance=acceptance,
        perf=perf,
    )
    return MetricsResponse(snapshot_at=datetime.utcnow(), metrics=qm)


def to_csv(metrics: List[RuleMetric]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["rule_id", "tp", "fp", "fn", "precision", "recall", "f1"])
    for m in metrics:
        writer.writerow(
            [
                m.rule_id,
                m.tp,
                m.fp,
                m.fn,
                f"{m.precision:.4f}",
                f"{m.recall:.4f}",
                f"{m.f1:.4f}",
            ]
        )
    return buf.getvalue()
