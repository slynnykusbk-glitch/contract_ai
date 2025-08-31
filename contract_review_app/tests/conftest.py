import pytest


@pytest.fixture(autouse=True)
def _reset_analyze_idempotency_cache():
    try:
        from contract_review_app.api.cache import clear_cache
        clear_cache()
    except Exception:
        # silently ignore if module or function is not available yet
        pass
