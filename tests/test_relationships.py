from __future__ import annotations

import numpy as np
import pandas as pd

from app.schemas import RelationshipRequest
from app.services import relationships
from app.services.relationships import _cramers_v, _eta_squared


def test_cramers_v_detects_identical_categories() -> None:
    values = pd.Series(["a", "a", "b", "b"] * 50)
    assert _cramers_v(values, values) > 0.95


def test_eta_squared_detects_separated_groups() -> None:
    category = pd.Series(["a"] * 50 + ["b"] * 50)
    numeric = pd.Series(np.r_[np.zeros(50), np.ones(50) * 10])
    assert _eta_squared(category, numeric) > 0.95


def test_latest_entity_grain_uses_one_latest_row_per_entity(monkeypatch) -> None:
    entities = [f"player-{index}" for index in range(20)]
    frame = pd.DataFrame({
        "entity": [entity for entity in entities for _ in range(2)],
        "minute": [minute for _ in entities for minute in (10, 20)],
        "gold": [value for index in range(20) for value in (100 + index, 200 + index)],
        "ap": [value for index in range(20) for value in (10 + index, 20 + index)],
    })
    profile = type("Profile", (), {"row_count": len(frame), "columns": [
        type("Column", (), {"name": "entity", "semantic_type": "identifier", "unique_count": 20, "null_ratio": 0})(),
        type("Column", (), {"name": "minute", "semantic_type": "numeric", "unique_count": 2, "null_ratio": 0})(),
        type("Column", (), {"name": "gold", "semantic_type": "numeric", "unique_count": 3, "null_ratio": 0})(),
        type("Column", (), {"name": "ap", "semantic_type": "numeric", "unique_count": 3, "null_ratio": 0})(),
    ]})()
    monkeypatch.setattr(relationships, "get_profile", lambda _: profile)
    monkeypatch.setattr(relationships, "get_version", lambda _: {"id": "v1"})
    monkeypatch.setattr(relationships, "read_frame", lambda _: frame)

    result = relationships.analyze("dataset", RelationshipRequest(
        column="gold", entity_key="entity", time_column="minute", analysis_grain="latest", minimum_pair_samples=20,
    ))

    assert result.items[0].sample_size == 20
    assert "latest 단위" in result.items[0].reason


def test_numeric_relationship_accepts_boolean_outcome(monkeypatch) -> None:
    frame = pd.DataFrame({"gold": range(20), "win": [index % 2 == 0 for index in range(20)]})
    profile = type("Profile", (), {"row_count": len(frame), "columns": [
        type("Column", (), {"name": "gold", "semantic_type": "numeric", "unique_count": 20, "null_ratio": 0})(),
        type("Column", (), {"name": "win", "semantic_type": "numeric", "unique_count": 2, "null_ratio": 0})(),
    ]})()
    monkeypatch.setattr(relationships, "get_profile", lambda _: profile)
    monkeypatch.setattr(relationships, "get_version", lambda _: {"id": "v1"})
    monkeypatch.setattr(relationships, "read_frame", lambda _: frame)

    result = relationships.analyze("dataset", RelationshipRequest(column="gold", minimum_pair_samples=20))

    assert result.items[0].column == "win"
