from __future__ import annotations

from typing import Any, Dict, List


def build_prompt(mode: str, grounding: Dict[str, Any]) -> str:
    """Build a deterministic prompt using the grounding package."""
    lines: List[str] = []
    lines.append(f"mode: {mode}")
    lines.append(f"question: {grounding.get('question', '')}")
    lines.append(f"context: {grounding.get('context', '')}")
    evidence = grounding.get("evidence") or []
    if evidence:
        lines.append("EVIDENCE:")
        for ev in evidence:
            src = ev.get("source", "")
            lines.append(f"> [{ev.get('id')}] {ev.get('text')} ({src})")
    return "\n".join(lines)
