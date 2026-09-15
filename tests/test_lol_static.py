from __future__ import annotations

from app.lol.static import champion_frame, patch_key, rune_frame


def test_patch_key_matches_game_and_data_dragon_versions() -> None:
    assert patch_key("16.18.712.1234") == patch_key("16.18.1") == "16.18"


def test_static_frames_keep_patch_and_stable_ids() -> None:
    champions = champion_frame(
        {"data": {"Annie": {"key": "1", "id": "Annie", "name": "Annie", "tags": ["Mage"], "stats": {"hp": 560}}}},
        "16.18.1",
    )
    runes = rune_frame(
        [{"id": 8100, "name": "Domination", "slots": [{"runes": [{"id": 8112, "key": "Electrocute", "name": "Electrocute", "longDesc": "Damage"}]}]}],
        "16.18.1",
    )

    assert champions.iloc[0]["champion_id"] == 1
    assert champions.iloc[0]["base_hp"] == 560
    assert runes.iloc[0]["rune_id"] == 8112
    assert runes.iloc[0]["patch"] == "16.18.1"
