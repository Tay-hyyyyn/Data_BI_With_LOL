from __future__ import annotations

import pandas as pd
import pytest

from app.services import transforms


def test_join_recipe_reads_the_selected_right_dataset(monkeypatch) -> None:
    left = pd.DataFrame({"campaign_id": ["a", "b"], "spend": [100, 200]})
    right = pd.DataFrame({"campaign_key": ["a", "b"], "channel": ["search", "social"]})
    monkeypatch.setattr(transforms, "read_frame", lambda dataset_id: right if dataset_id == "channels" else left)

    result = transforms._apply(left, "join", {"right_dataset_id": "channels", "left_on": ["campaign_id"], "right_on": ["campaign_key"], "how": "left", "validate": "one_to_one"})

    assert result[["campaign_id", "channel"]].to_dict("records") == [
        {"campaign_id": "a", "channel": "search"}, {"campaign_id": "b", "channel": "social"}
    ]


def test_join_recipe_rejects_invalid_cardinality(monkeypatch) -> None:
    left = pd.DataFrame({"id": ["a"]})
    right = pd.DataFrame({"id": ["a", "a"]})
    monkeypatch.setattr(transforms, "read_frame", lambda _: right)

    with pytest.raises(Exception):
        transforms._apply(left, "join", {"right_dataset_id": "right", "left_on": ["id"], "how": "left", "validate": "one_to_one"})
