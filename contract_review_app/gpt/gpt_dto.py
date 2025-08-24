from __future__ import annotations
from typing import Optional, Any
from pydantic import BaseModel

# ⚠️ Не імпортуємо AnalysisOutput як тип, щоб уникати циклічних імпортів під час runtime.
# Приймаємо dict-подібний об'єкт.

class GPTDraftResponse(BaseModel):
    """
    Уніфікований DTO-відповідь для фронтенду/Word.
    """
    clause_type: Optional[str] = None
    original_text: Optional[str] = None
    draft_text: str
    explanation: str
    score: int
    status: str = "ok"  # ok | warn | fail
    title: Optional[str] = None

    @property
    def draft(self) -> str:
        return self.draft_text

    @property
    def original(self) -> Optional[str]:
        return self.original_text


class GPTDraftRequest(BaseModel):
    """
    Запит на генерацію GPT-драфту (передаємо результат аналізу).
    """
    analysis: dict  # dict-подібний AnalysisOutput
    model: Optional[str] = "gpt-4"
