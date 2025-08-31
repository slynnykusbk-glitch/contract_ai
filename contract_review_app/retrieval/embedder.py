from __future__ import annotations

import hashlib
from typing import Iterable, List

import numpy as np


class HashingEmbedder:
    """Simple deterministic embedding based on token hashing.

    Each token is hashed with blake2b and mapped into embedding space.
    The resulting vector is a bag-of-words with counts per dimension.
    """

    def __init__(self, dim: int) -> None:
        self.dim = dim

    def embed(self, texts: Iterable[str]) -> np.ndarray:
        seq: List[str] = list(texts)
        vecs = np.zeros((len(seq), self.dim), dtype=np.float32)
        for i, text in enumerate(seq):
            for token in text.split():
                h = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
                idx = int.from_bytes(h, "little") % self.dim
                vecs[i, idx] += 1.0
        return vecs
