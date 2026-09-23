"""Regression (B6): a game that ended before a requested snapshot minute used to still emit a
row for it, copying the last available frame's values — inflating sample counts and biasing
later-minute stats toward short games."""

from __future__ import annotations

from app.lol.timeline import normalize_match


def _match(game_duration_s: int) -> dict:
    return {
        "metadata": {"matchId": "KR_1"},
        "info": {
            "gameVersion": "1.2.3",
            "queueId": 420,
            "gameDuration": game_duration_s,
            "participants": [
                {"participantId": 1, "puuid": "player", "championId": 10, "championName": "Test", "teamId": 100, "teamPosition": "MID", "win": True}
            ],
        },
    }


def _timeline_ending_at(seconds: int) -> dict:
    return {
        "info": {
            "frames": [
                {"timestamp": 0, "participantFrames": {"1": {"totalGold": 500, "currentGold": 500, "level": 1, "xp": 0, "minionsKilled": 0, "jungleMinionsKilled": 0}}, "events": []},
                {
                    "timestamp": seconds * 1000,
                    "participantFrames": {"1": {"totalGold": 4000, "currentGold": 100, "level": 8, "xp": 4000, "minionsKilled": 90, "jungleMinionsKilled": 2}},
                    "events": [],
                },
            ]
        }
    }


def test_no_snapshot_row_for_a_minute_after_the_game_ended() -> None:
    match = _match(game_duration_s=12 * 60)  # 12-minute stomp
    timeline = _timeline_ending_at(12 * 60)

    _, states, _ = normalize_match(match, timeline, [10, 15, 20])

    assert sorted(states["minute"].tolist()) == [10]  # only the minute that actually happened


def test_a_snapshot_row_is_still_emitted_for_a_minute_the_game_reached() -> None:
    match = _match(game_duration_s=25 * 60)
    timeline = _timeline_ending_at(25 * 60)

    _, states, _ = normalize_match(match, timeline, [10, 15, 20])

    assert sorted(states["minute"].tolist()) == [10, 15, 20]


def test_boundary_minute_exactly_at_game_end_is_kept() -> None:
    match = _match(game_duration_s=20 * 60)
    timeline = _timeline_ending_at(20 * 60)

    _, states, _ = normalize_match(match, timeline, [20])

    assert states["minute"].tolist() == [20]
