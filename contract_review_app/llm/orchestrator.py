from __future__ import annotations

from collections.abc import Mapping, Iterator
from dataclasses import dataclass
from typing import Any, Dict, Optional

from .provider.base import LLMConfig, LLMProvider
from .provider.proxy import ProxyProvider
from .prompt_builder import build_prompt
from .citation_resolver import make_grounding_pack
from .verification import verify_output_contains_citations


@dataclass
class OrchestratorResult(Mapping[str, Any]):
    text: str
    provider: str
    model: str
    usage: Dict[str, Any]
    prompt: str
    verification_status: str
    grounding_trace: Dict[str, Any]

    def __getitem__(self, key: str) -> Any:  # pragma: no cover - Mapping protocol
        return getattr(self, key)

    def __iter__(self) -> Iterator[str]:  # pragma: no cover - Mapping protocol
        return iter(
            [
                "text",
                "result",
                "provider",
                "model",
                "usage",
                "prompt",
                "verification_status",
                "grounding_trace",
            ]
        )

    def __len__(self) -> int:  # pragma: no cover - Mapping protocol
        return 8

    @property
    def result(self) -> str:
        return self.text


class Orchestrator:
    """Deterministic LLM orchestrator."""

    def __init__(
        self,
        provider: Optional[LLMProvider] = None,
        config: Optional[LLMConfig] = None,
    ) -> None:
        self.provider = provider or ProxyProvider()
        self.config = config or LLMConfig()

    def _run(self, mode: str, *, question: str = "", context_text: str = "", citations: Any = None) -> OrchestratorResult:
        gp = make_grounding_pack(question, context_text, citations)
        prompt = build_prompt(mode, gp)
        res = self.provider.generate(prompt, self.config)
        status = verify_output_contains_citations(res.text, gp.get("evidence") or [])
        return OrchestratorResult(
            text=res.text,
            provider=getattr(res, "provider", ""),
            model=getattr(res, "model", ""),
            usage=getattr(res, "usage", {}),
            prompt=prompt,
            verification_status=status,
            grounding_trace={
                "citations": gp.get("citations", []),
                "evidence": gp.get("evidence", []),
            },
        )

    def draft(self, question: str = "", context_text: str = "", citations: Any = None) -> OrchestratorResult:
        return self._run("draft", question=question, context_text=context_text, citations=citations)

    def suggest_edits(self, question: str = "", context_text: str = "", citations: Any = None) -> OrchestratorResult:
        return self._run("suggest_edits", question=question, context_text=context_text, citations=citations)
