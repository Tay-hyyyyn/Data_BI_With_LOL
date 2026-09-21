from __future__ import annotations

import asyncio
import json
import os
import random
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

from ..config import settings


class RiotKeyError(RuntimeError):
    pass


class RiotClient:
    def __init__(self, api_key: str | None = None, key_kind: str | None = None) -> None:
        self.api_key = api_key or os.getenv("RIOT_API_KEY")
        self.key_kind = (key_kind or os.getenv("RIOT_API_KEY_KIND") or "development").lower()
        if settings.environment == "production" and self.key_kind != "production":
            raise RiotKeyError("공개 production 환경에서는 Development API Key를 사용할 수 없습니다.")
        if not self.api_key:
            raise RiotKeyError("RIOT_API_KEY가 설정되지 않았습니다.")
        self._rate_lock = asyncio.Lock()
        self._last_request_at = 0.0

    async def _throttle(self) -> None:
        # Development key의 장기 한도(100회/2분)를 넘지 않는 보수적 간격이다.
        minimum_interval = 1.21 if self.key_kind == "development" else 0.025
        async with self._rate_lock:
            now = asyncio.get_running_loop().time()
            wait = minimum_interval - (now - self._last_request_at)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request_at = asyncio.get_running_loop().time()

    async def get_json(self, url: str, attempts: int = 6) -> Any:
        async with httpx.AsyncClient(headers={"X-Riot-Token": self.api_key or ""}, timeout=30) as client:
            for attempt in range(attempts):
                await self._throttle()
                response = await client.get(url)
                if response.status_code == 429:
                    await asyncio.sleep(float(response.headers.get("Retry-After", "1")))
                    continue
                if response.status_code in {401, 403}:
                    raise RiotKeyError("Riot API Key가 만료되었거나 권한이 없습니다. 키 갱신 후 같은 작업을 재개하세요.")
                if response.status_code >= 500:
                    await asyncio.sleep(min(30, 2**attempt) + random.random())
                    continue
                response.raise_for_status()
                return response.json()
        raise RuntimeError("Riot API 재시도 예산을 모두 사용했습니다.")

    async def account_by_riot_id(self, game_name: str, tag_line: str) -> dict[str, Any]:
        game = quote(game_name.strip(), safe="")
        tag = quote(tag_line.strip().lstrip("#"), safe="")
        return await self.get_json(f"https://asia.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{game}/{tag}")

    async def match_ids(self, puuid: str, start: int = 0, count: int = 20) -> list[str]:
        url = f"https://asia.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?start={start}&count={min(count, 100)}"
        return await self.get_json(url)

    async def persist_match(self, match_id: str) -> dict[str, Path]:
        root = settings.root / "bronze" / "riot" / "matches" / match_id
        paths = {"match": root / "match.json", "timeline": root / "timeline.json"}
        if all(path.is_file() for path in paths.values()):
            return paths
        base = f"https://asia.api.riotgames.com/lol/match/v5/matches/{match_id}"
        match, timeline = await asyncio.gather(self.get_json(base), self.get_json(f"{base}/timeline"))
        root.mkdir(parents=True, exist_ok=True)
        for key, payload in (("match", match), ("timeline", timeline)):
            temp = paths[key].with_suffix(".json.tmp")
            temp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            os.replace(temp, paths[key])
        return paths


async def fetch_data_dragon(version: str | None = None) -> tuple[str, dict[str, Any]]:
    async with httpx.AsyncClient(timeout=30) as client:
        if version is None:
            versions = (await client.get("https://ddragon.leagueoflegends.com/api/versions.json")).json()
            version = versions[0]
        response = await client.get(f"https://ddragon.leagueoflegends.com/cdn/{version}/data/en_US/item.json")
        response.raise_for_status()
        return version, response.json()


async def fetch_data_dragon_bundle(version: str | None = None, locale: str = "en_US") -> tuple[str, dict[str, Any]]:
    async with httpx.AsyncClient(timeout=30) as client:
        if version is None:
            response = await client.get("https://ddragon.leagueoflegends.com/api/versions.json")
            response.raise_for_status()
            version = response.json()[0]
        base = f"https://ddragon.leagueoflegends.com/cdn/{version}/data/{locale}"
        item_response, champion_response, rune_response = await asyncio.gather(
            client.get(f"{base}/item.json"),
            client.get(f"{base}/champion.json"),
            client.get(f"{base}/runesReforged.json"),
        )
        for response in (item_response, champion_response, rune_response):
            response.raise_for_status()
        return version, {
            "items": item_response.json(),
            "champions": champion_response.json(),
            "runes": rune_response.json(),
        }
