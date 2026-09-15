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


@pytest.mark.asyncio
async def test_riot_id_path_is_encoded(monkeypatch) -> None:
    monkeypatch.setattr(client, "settings", SimpleNamespace(environment="local"))
    riot = client.RiotClient(api_key="RGAPI-test", key_kind="development")

    async def fake_get(url: str, attempts: int = 6):
        return {"url": url}

    monkeypatch.setattr(riot, "get_json", fake_get)
    result = await riot.account_by_riot_id("name space", "#KR1")
    assert result["url"].endswith("/name%20space/KR1")
