from __future__ import annotations

from datetime import datetime
from typing import List

from pydantic import BaseModel


class RuleMetric(BaseModel):
    rule_id: str
    tp: int
    fp: int
    fn: int
    precision: float
    recall: float
    f1: float


class Coverage(BaseModel):
    rules_total: int
    rules_fired: int
    coverage: float


class Acceptance(BaseModel):
    applied: int
    rejected: int
    acceptance_rate: float


class Perf(BaseModel):
    docs: int
    avg_ms_per_page: float


class QualityMetrics(BaseModel):
    rules: List[RuleMetric]
    coverage: Coverage
    acceptance: Acceptance
    perf: Perf


class MetricsResponse(BaseModel):
    schema_version: str = "1.4"
    snapshot_at: datetime
    metrics: QualityMetrics
