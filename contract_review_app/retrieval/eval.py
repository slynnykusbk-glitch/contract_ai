from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Literal, Optional, TypedDict

import yaml

from contract_review_app.corpus.db import SessionLocal, get_engine, init_db
from contract_review_app.retrieval.config import load_config
from contract_review_app.retrieval.search import search_corpus


class ExpectedItem(TypedDict):
    jurisdiction: str
    act_code: str
    section_code: str


@dataclass
class QueryCase:
    query: str
    expected: List[ExpectedItem]


class SearchMeta(TypedDict, total=False):
    jurisdiction: str
    act_code: str
    section_code: str


class SearchResult(TypedDict, total=False):
    meta: SearchMeta


@dataclass
class RetrievalConfig:
    data: dict

    @classmethod
    def from_env_or_file(cls, path: str | None = None) -> "RetrievalConfig":
        cfg = load_config(path)
        return cls(cfg)


def load_golden(path: str) -> List[QueryCase]:
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or []
    cases: List[QueryCase] = []
    for item in data:
        cases.append(QueryCase(query=item["query"], expected=item.get("expected", [])))
    return cases


def _ensure_session():
    engine = get_engine()
    init_db(engine)
    SessionLocal.configure(bind=engine)


def run_search(
    query: str,
    method: Literal["bm25", "vector", "hybrid"],
    top_k: int,
    cfg: RetrievalConfig,
) -> List[SearchResult]:
    _ensure_session()
    with SessionLocal() as session:
        if method in {"bm25", "vector", "hybrid"}:
            return search_corpus(session, query=query, mode=method, top=top_k)
        raise ValueError(f"unknown method {method}")


def match(result: SearchResult, expected_item: ExpectedItem) -> bool:
    meta = result.get("meta", {})
    return (
        meta.get("jurisdiction") == expected_item["jurisdiction"]
        and meta.get("act_code") == expected_item["act_code"]
        and meta.get("section_code") == expected_item["section_code"]
    )


def evaluate(golden: List[QueryCase], method: str, k: int) -> dict:
    cfg = RetrievalConfig.from_env_or_file()
    cases_out = []
    hits = 0
    mrr_total = 0.0
    for case in golden:
        results = run_search(case.query, method, k, cfg)
        rank: Optional[int] = None
        for idx, res in enumerate(results, 1):
            if any(match(res, exp) for exp in case.expected):
                rank = idx
                break
        cases_out.append({"query": case.query, "found": rank is not None, "rank": rank})
        if rank is not None:
            hits += 1
            mrr_total += 1.0 / rank
    total = len(golden) if golden else 1
    recall = hits / total
    mrr = mrr_total / total
    return {
        "method": method,
        "k": k,
        "recall_at_k": recall,
        "mrr_at_k": mrr,
        "cases": cases_out,
    }


THRESHOLDS = {
    "hybrid": {"recall": 0.8, "mrr": 0.6},
    "bm25": {"recall": 0.6, "mrr": 0.5},
    "vector": {"recall": 0.6, "mrr": 0.5},
}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--golden", required=True)
    p.add_argument("--method", choices=["bm25", "vector", "hybrid"], required=True)
    p.add_argument("--k", type=int, default=5)
    args = p.parse_args()
    golden = load_golden(args.golden)
    res = evaluate(golden, args.method, args.k)
    print(json.dumps(res))
    thr = THRESHOLDS.get(args.method, {"recall": 0.0, "mrr": 0.0})
    ok = res["recall_at_k"] >= thr["recall"] and res["mrr_at_k"] >= thr["mrr"]
    return 0 if ok else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
