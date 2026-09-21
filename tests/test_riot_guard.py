from __future__ import annotations

from pathlib import Path
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


@pytest.mark.asyncio
async def test_cached_match_does_not_call_riot_api(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(client, "settings", SimpleNamespace(environment="local", root=tmp_path))
    riot = client.RiotClient(api_key="RGAPI-test", key_kind="development")
    directory = tmp_path / "bronze" / "riot" / "matches" / "KR_1"
    directory.mkdir(parents=True)
    (directory / "match.json").write_text("{}", encoding="utf-8")
    (directory / "timeline.json").write_text("{}", encoding="utf-8")

    async def forbidden_get(*_args, **_kwargs):
        raise AssertionError("cached match should not call Riot")

    monkeypatch.setattr(riot, "get_json", forbidden_get)
    result = await riot.persist_match("KR_1")
    assert result["match"].is_file()
