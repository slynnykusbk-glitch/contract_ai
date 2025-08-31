from typing import Any

from contract_review_app.core.schemas import AppBaseModel


class ProblemDetail(AppBaseModel):
    type: str = "/errors/general"
    title: str
    status: int
    detail: str | None = None
    instance: str | None = None
    code: str | None = None
    extra: dict[str, Any] | None = None
