from __future__ import annotations

import numpy as np
import pandas as pd

from app.services.relationships import _cramers_v, _eta_squared


def test_cramers_v_detects_identical_categories() -> None:
    values = pd.Series(["a", "a", "b", "b"] * 50)
    assert _cramers_v(values, values) > 0.95


def test_eta_squared_detects_separated_groups() -> None:
    category = pd.Series(["a"] * 50 + ["b"] * 50)
    numeric = pd.Series(np.r_[np.zeros(50), np.ones(50) * 10])
    assert _eta_squared(category, numeric) > 0.95
