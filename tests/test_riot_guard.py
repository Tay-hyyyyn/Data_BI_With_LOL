from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.lol import client


def test_development_key_is_blocked_in_production(monkeypatch) -> None:
    monkeypatch.setattr(client, "settings", SimpleNamespace(environment="production"))
    with pytest.raises(client.RiotKeyError, match="Development API Key"):
        client.RiotClient(api_key="RGAPI-test", key_kind="development")


def test_production_key_is_allowed_in_production(monkeypatch) -> None:
    monkeypatch.setattr(client, "settings", SimpleNamespace(environment="production"))
    assert client.RiotClient(api_key="RGAPI-test", key_kind="production").key_kind == "production"
