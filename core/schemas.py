"""Compatibility shim for core.schemas.
This module re-exports the schemas from contract_review_app.core.schemas
so tests can simply import `core.schemas`.
"""
from contract_review_app.core.schemas import *  # noqa: F401,F403
