from __future__ import annotations

from pydantic import BaseModel, Field

__all__ = [
    "LolStarterDashboardRequest",
    "LolStaticSyncRequest",
    "RiotAccountResolveRequest",
    "RiotAccountSummary",
    "RiotMatchCollectRequest",
    "RiotMatchProcessRequest",
]


class LolStaticSyncRequest(BaseModel):
    version: str | None = None
    bootstrap_samples: int = Field(200, ge=20, le=2_000)


class LolStarterDashboardRequest(BaseModel):
    patch: str = Field(min_length=1, max_length=20)


class RiotAccountResolveRequest(BaseModel):
    game_name: str = Field(min_length=1, max_length=64)
    tag_line: str = Field(min_length=1, max_length=16)


class RiotAccountSummary(BaseModel):
    puuid: str
    game_name: str
    tag_line: str


class RiotMatchCollectRequest(BaseModel):
    puuid: str = Field(min_length=20, max_length=128)
    count: int = Field(10, ge=1, le=100)


class RiotMatchProcessRequest(BaseModel):
    match_ids: list[str] = Field(min_length=1, max_length=1_000)
    snapshot_minutes: list[int] = Field(default=[10, 15, 20], min_length=1, max_length=12)
    item_dataset_id: str | None = None
