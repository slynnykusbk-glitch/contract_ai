"""Utilities for retrieving UK legal references for contract analysis."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Dict, Any

import yaml

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "uk_regulations.yaml"


class UKRegulationRetriever:
    """Load a small knowledge base of UK regulations and retrieve entries.

    The data file contains dictionaries with keys:
    ``source``, ``source_type``, ``jurisdiction``, ``topics`` and ``excerpt``.
    Retrieval filters by ``jurisdiction='UK'`` and optional ``source_type`` values.
    """

    def __init__(self, data_file: Path = DATA_FILE) -> None:
        self.data_file = data_file
        with open(data_file, "r", encoding="utf-8") as fh:
            self.entries: List[Dict[str, Any]] = yaml.safe_load(fh) or []

    def retrieve(
        self, topic: str, source_types: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Return entries matching ``topic`` and optional ``source_types``.

        Parameters
        ----------
        topic:
            Topic keyword used for matching against the ``topics`` field of entries.
        source_types:
            Optional list of source type identifiers (e.g. ``["ICO", "FCA"]``).

        Returns
        -------
        List of matching entries sorted in the original order of the data file.
        """
        topic_lower = topic.lower()
        results: List[Dict[str, Any]] = []
        for entry in self.entries:
            if entry.get("jurisdiction") != "UK":
                continue
            if source_types and entry.get("source_type") not in source_types:
                continue
            topics = [t.lower() for t in entry.get("topics", [])]
            if topic_lower in topics:
                results.append(entry)
        return results
