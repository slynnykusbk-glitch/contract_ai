from typing import Optional
from contract_review_app.core.schemas import AnalysisOutput
from contract_review_app.gpt.prompt_builder_utils import build_prompt
from contract_review_app.gpt.gpt_proxy_api import call_gpt_api
from contract_review_app.gpt.gpt_dto import GPTDraftResponse


def generate_clause_draft(output: AnalysisOutput) -> GPTDraftResponse:
    """
    ✅ Основна точка входу: генерує GPT-драфт клаузули на основі rule-based аналізу.
    
    Args:
        output (AnalysisOutput): Результат rule-engine для однієї клаузули.

    Returns:
        GPTDraftResponse: Об’єкт з новим текстом клаузули, reasoning (опціонально) і metadata.
    """
    prompt = build_prompt(output)

    # Trace можна додати в output.metadata['prompt'] при бажанні
    return call_gpt_api(
        clause_type=output.clause_type,
        prompt=prompt,
        output=output
    )


def parse_gpt_response(response_dict: dict) -> GPTDraftResponse:
    """
    ✅ Преобразує JSON/dict відповідь від GPT (через API) у GPTDraftResponse.

    Args:
        response_dict (dict): Словник з ключами "draft", "reasoning", "metadata".

    Returns:
        GPTDraftResponse: Об’єкт редакції GPT, готовий до рендеру/звіту/інтерфейсу.
    """
    return GPTDraftResponse(**response_dict)
