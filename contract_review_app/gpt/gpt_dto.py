from __future__ import annotations
from typing import Optional, Any
from pydantic import BaseModel
from contract_review_app.core.schemas import (
    GPTDraftResponse as CoreGPTDraftResponse,
)

# ⚠️ Не імпортуємо AnalysisOutput як тип, щоб уникати циклічних імпортів під час runtime.
# Приймаємо dict-подібний об'єкт.


class GPTDraftResponse(CoreGPTDraftResponse):
    """Розширений варіант :class:`core.schemas.GPTDraftResponse`.

    Додає кілька полів, корисних для фронтенду/Word, але зберігає сумісність
    з базовим класом, що використовується у тестах.
    """

    clause_type: Optional[str] = None
    original_text: Optional[str] = None
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
