from __future__ import annotations

import numpy as np
import pandas as pd
from app.lol.pricing import estimate_gold_values, item_efficiency, ridge_price_map


def test_gold_model_exposes_non_negative_ridge_and_nnls() -> None:
    items = pd.DataFrame(
        {
            "item_name": ["A", "B", "C", "D", "E", "F"],
            "total_gold": [100, 200, 300, 400, 500, 600],
            "ad": [1, 2, 1, 3, 2, 4],
            "ap": [2, 1, 3, 1, 4, 2],
        }
    )
    result = estimate_gold_values(items)
    assert (result["ridge_gold_per_unit"] >= 0).all()
    assert (result["nnls_gold_per_unit"] >= 0).all()


def test_nnls_has_an_intercept_so_it_is_the_same_estimand_as_ridge() -> None:
    """NNLS previously had no intercept (scipy.optimize.nnls has no such option), forcing the fit
    through the origin and absorbing base/combine cost into the stat coefficients instead —
    inflating them relative to Ridge's, which does have one."""
    items = pd.DataFrame({"item_name": ["A", "B", "C", "D"], "total_gold": [300.0, 400.0, 500.0, 600.0], "ad": [1.0, 2.0, 3.0, 4.0]})
    estimates = estimate_gold_values(items)
    assert "nnls_intercept_gold" in estimates.columns
    assert (estimates["nnls_intercept_gold"] >= 0).all()


def test_ridge_prices_are_not_crushed_by_unit_scale_asymmetry() -> None:
    """Regression: without scaling stats before fitting, an L2 penalty applied to raw
    coefficients punishes a stat that needs a large per-unit price (because its natural range is
    tiny, e.g. mana as a 0..1-ish fraction here) far more than one on a large-scale range (e.g.
    hp in the hundreds) for the same reduction in loss — crit_chance/attack_speed vs hp/mana in
    the real catalog is exactly this asymmetry."""
    rng = np.random.default_rng(0)
    n = 40
    small_scale = rng.uniform(0, 1, n)
    large_scale = rng.uniform(0, 400, n)
    true_small_price, true_large_price = 500.0, 1.0
    total_gold = 200 + true_small_price * small_scale + true_large_price * large_scale

    items = pd.DataFrame({"item_name": [f"item-{i}" for i in range(n)], "total_gold": total_gold, "mana": small_scale, "hp": large_scale})
    estimates = estimate_gold_values(items, alpha=10.0)

    mana_price = estimates.set_index("stat").loc["mana", "ridge_gold_per_unit"]
    assert mana_price > true_small_price * 0.5  # would be crushed toward ~0 without per-feature scaling


def test_cross_validated_r2_replaces_the_bootstrap_confidence_interval() -> None:
    """The bootstrap CI resampled items — a census of a finite designed population, not a random
    sample — which is not a valid basis for a confidence interval. cv_r2 answers a real question
    (does the fit generalize to held-out items) instead."""
    items = pd.DataFrame(
        {
            "item_name": [f"item-{i}" for i in range(10)],
            "total_gold": [100, 200, 300, 400, 500, 600, 150, 250, 350, 450],
            "ad": [1, 2, 3, 4, 5, 6, 1, 2, 3, 4],
        }
    )
    estimates = estimate_gold_values(items)
    assert "cv_r2" in estimates.columns
    assert "ci95_low" not in estimates.columns and "ci95_high" not in estimates.columns
    assert estimates["cv_r2"].notna().all()


def test_ridge_price_map_matches_the_estimates_frame() -> None:
    items = pd.DataFrame({"item_name": ["A", "B", "C"], "total_gold": [100.0, 200.0, 300.0], "ad": [1.0, 2.0, 3.0]})
    estimates = estimate_gold_values(items)
    prices = ridge_price_map(estimates)
    assert prices["ad"] == estimates.set_index("stat").loc["ad", "ridge_gold_per_unit"]


def test_item_efficiency_adds_a_model_based_column_when_given_model_prices() -> None:
    items = pd.DataFrame({"item_name": ["X"], "total_gold": [100.0], "ad": [10.0]})

    reference_only = item_efficiency(items, reference={"ad": 10.0})
    assert "model_gold_efficiency_percent" not in reference_only.columns

    both = item_efficiency(items, reference={"ad": 10.0}, model={"ad": 8.0})
    assert both.iloc[0]["gold_efficiency_percent"] == 100.0
    assert both.iloc[0]["model_gold_efficiency_percent"] == 80.0
