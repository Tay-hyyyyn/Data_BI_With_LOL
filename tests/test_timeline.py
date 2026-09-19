from __future__ import annotations

from app.lol.timeline import normalize_match


def test_timeline_builds_snapshot_and_inventory(monkeypatch) -> None:
    monkeypatch.setenv("DATA_BI_PUUID_PEPPER", "test")
    match = {"metadata": {"matchId": "KR_1"}, "info": {"gameVersion": "1.2.3", "queueId": 420, "gameDuration": 1200, "participants": [{"participantId": 1, "puuid": "player", "championId": 10, "championName": "Test", "teamId": 100, "teamPosition": "MID", "win": True}]}}
    timeline = {"info": {"frames": [{"timestamp": 0, "participantFrames": {"1": {"totalGold": 500, "currentGold": 500, "level": 1, "xp": 0, "minionsKilled": 0, "jungleMinionsKilled": 0}}, "events": []}, {"timestamp": 600000, "participantFrames": {"1": {"totalGold": 3500, "currentGold": 500, "level": 7, "xp": 3000, "minionsKilled": 80, "jungleMinionsKilled": 0, "position": {"x": 10, "y": 20}}}, "events": [{"type": "ITEM_PURCHASED", "participantId": 1, "itemId": 1001, "timestamp": 300000}]}]}}
    participants, states, events = normalize_match(match, timeline, [10])
    assert participants.iloc[0]["puuid_hash"] != "player"
    assert states.iloc[0]["match_participant_key"] == "KR_1:1"
    assert states.iloc[0]["inventory"] == "1001"
    assert events.iloc[0]["event_type"] == "ITEM_PURCHASED"
