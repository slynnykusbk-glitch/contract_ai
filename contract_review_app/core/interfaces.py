from typing import Protocol
from .schemas import AnalysisInput, AnalysisOutput


class ClauseValidator(Protocol):
    rule_name: str  # напр. "governing_law"

    def analyze(self, data: AnalysisInput) -> AnalysisOutput: ...
