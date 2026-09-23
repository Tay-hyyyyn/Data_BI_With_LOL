from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from ..lol.client import Region

# Riot match ids look like "KR_7123456789". The pattern also keeps them safe to use as path segments.
MatchId = Annotated[str, StringConstraints(pattern=r"^[A-Z0-9]{2,5}_[0-9]{1,20}$")]

# Ranked Solo/Duo. The only queue this app's marts are designed to be pooled by (see docs/lol);
# ARAM/normals/flex have no `teamPosition` in the same sense and would corrupt lane comparisons.
RANKED_SOLO_QUEUE = 420

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


class LolStarterDashboardRequest(BaseModel):
    patch: str = Field(min_length=1, max_length=20)


class RiotAccountResolveRequest(BaseModel):
    game_name: str = Field(min_length=1, max_length=64)
    tag_line: str = Field(min_length=1, max_length=16)
    region: Region = "asia"


class RiotAccountSummary(BaseModel):
    puuid: str
    game_name: str
    tag_line: str


class RiotMatchCollectRequest(BaseModel):
    puuid: str = Field(min_length=20, max_length=128)
    count: int = Field(10, ge=1, le=100)
    start: int = Field(0, ge=0, le=1_000)
    queue: int | None = Field(RANKED_SOLO_QUEUE, ge=0, le=2_000)
    region: Region = "asia"


class RiotMatchProcessRequest(BaseModel):
    match_ids: list[MatchId] = Field(min_length=1, max_length=1_000)
    snapshot_minutes: list[int] = Field(default=[10, 15, 20], min_length=1, max_length=12)
    item_dataset_id: str | None = None
