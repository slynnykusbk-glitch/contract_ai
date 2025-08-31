from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

import yaml


DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "retrieval.yaml"


def _env_override(data: Dict[str, Any]) -> None:
    mapping = {
        "RETRIEVAL_EMBEDDING_DIM": (("vector",), "embedding_dim", int),
        "RETRIEVAL_EMBEDDING_VERSION": (("vector",), "embedding_version", str),
        "RETRIEVAL_CACHE_DIR": (("vector",), "cache_dir", str),
        "RETRIEVAL_RRF_K": (("fusion",), "rrf_k", int),
        "RETRIEVAL_FUSION_METHOD": (("fusion",), "method", str),
        "RETRIEVAL_WEIGHT_VECTOR": (("fusion", "weights"), "vector", float),
        "RETRIEVAL_WEIGHT_BM25": (("fusion", "weights"), "bm25", float),
        "RETRIEVAL_BM25_TOP": (("bm25",), "top", int),
    }
    for env, (sections, key, cast) in mapping.items():
        val = os.getenv(env)
        if val is None:
            continue
        target = data
        for sec in sections:
            target = target.setdefault(sec, {})
        target[key] = cast(val)


def load_config(path: str | None = None) -> Dict[str, Any]:
    """Load retrieval configuration.

    ``path`` overrides default lookup which checks ``RETRIEVAL_CONFIG``
    environment variable and finally ``config/retrieval.yaml``.
    Selected values can be overridden via specific environment variables.
    """

    cfg_path = path or os.getenv("RETRIEVAL_CONFIG") or DEFAULT_CONFIG_PATH
    with open(cfg_path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    _env_override(data)
    vec = data.get("vector", {})
    fusion = data.get("fusion", {})
    bm25 = data.get("bm25", {})
    vec["embedding_dim"] = int(vec.get("embedding_dim", 128))
    vec["embedding_version"] = str(vec.get("embedding_version", ""))
    vec["cache_dir"] = str(vec.get("cache_dir", ".cache/retrieval"))
    vec["backend"] = str(vec.get("backend", "inmemory"))
    fusion["method"] = str(fusion.get("method", "rrf"))
    weights = fusion.get("weights", {})
    weights["vector"] = float(weights.get("vector", 0.6))
    weights["bm25"] = float(weights.get("bm25", 0.4))
    fusion["weights"] = weights
    if "rrf_k" in fusion:
        fusion["rrf_k"] = int(fusion["rrf_k"])
    bm25["top"] = int(bm25.get("top", 10))
    return {"vector": vec, "fusion": fusion, "bm25": bm25}
