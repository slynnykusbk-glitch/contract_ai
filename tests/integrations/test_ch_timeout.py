import importlib

import httpx
import pytest


def test_companies_house_timeout(monkeypatch):
    monkeypatch.setenv("CONTRACTAI_API_TIMEOUT_S", "3")
    monkeypatch.setenv("CH_TIMEOUT_S", "1")

    from contract_review_app.api import limits as limits_module

    importlib.reload(limits_module)
    from contract_review_app.integrations.companies_house import client as ch_client

    importlib.reload(ch_client)

    recorded_timeouts = []

    def fake_get(url, headers=None, auth=None, timeout=None):
        recorded_timeouts.append(timeout)
        raise httpx.TimeoutException("timeout")

    monkeypatch.setattr(ch_client.httpx, "get", fake_get)

    with pytest.raises(ch_client.CHTimeout):
        ch_client.search_companies("acme")

    assert recorded_timeouts
    assert recorded_timeouts[0] == pytest.approx(limits_module.CH_TIMEOUT_S)
    assert limits_module.CH_TIMEOUT_S < limits_module.API_TIMEOUT_S
