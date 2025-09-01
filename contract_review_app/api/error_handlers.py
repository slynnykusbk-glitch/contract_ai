import logging
import time
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .models import ProblemDetail
from .headers import apply_std_headers

logger = logging.getLogger(__name__)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(request: Request, exc: RequestValidationError):
        problem = ProblemDetail(title="Validation error", status=422)
        resp = JSONResponse(problem.model_dump(), status_code=422)
        apply_std_headers(resp, request, getattr(request.state, "started_at", time.perf_counter()))
        return resp

    @app.exception_handler(HTTPException)
    async def _handle_http_exception(request: Request, exc: HTTPException):
        if exc.status_code >= 500:
            logger.exception("HTTPException", exc_info=exc)
        title = exc.detail if isinstance(exc.detail, str) else "Error"
        problem = ProblemDetail(title=title, status=exc.status_code)
        resp = JSONResponse(problem.model_dump(), status_code=exc.status_code)
        apply_std_headers(resp, request, getattr(request.state, "started_at", time.perf_counter()))
        return resp

    @app.exception_handler(Exception)
    async def _handle_exception(request: Request, exc: Exception):
        logger.exception("Unhandled exception", exc_info=exc)
        problem = ProblemDetail(title="Internal Server Error", status=500)
        resp = JSONResponse(problem.model_dump(), status_code=500)
        apply_std_headers(resp, request, getattr(request.state, "started_at", time.perf_counter()))
        return resp
