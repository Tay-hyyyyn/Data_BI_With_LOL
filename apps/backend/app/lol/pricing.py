"""How many gold each item stat point is worth, estimated two ways plus a naive reference ratio.

This module intentionally does NOT attempt a bootstrap confidence interval. The item catalog is a
census of a designed, finite population (every purchasable item in one patch), not a random draw
from a superpopulation, and items are not independent (a component's price is literally embedded
in every item built from it) — resampling items and refitting gives a distribution over the
*resampling procedure*, not a valid interval for the true marginal price. `estimate_gold_values`
reports a cross-validated R² instead, which answers a real question ("does this model generalize
to held-out items at all?") rather than a fabricated one.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import nnls
from sklearn.linear_model import Ridge
from sklearn.model_selection import KFold

from .items import REFERENCE_ITEMS


def reference_prices(items: pd.DataFrame) -> dict[str, float]:
    """A single named reference item's gold-per-stat-unit ratio, e.g. Long Sword: 350g / 10 AD."""
    result: dict[str, float] = {}
    for stat, item_name in REFERENCE_ITEMS.items():
        row = items.loc[items["item_name"].eq(item_name)]
        if row.empty or float(row.iloc[0].get(stat, 0)) <= 0:
            continue
        result[stat] = float(row.iloc[0]["total_gold"] / row.iloc[0][stat])
    return result


def estimate_gold_values(items: pd.DataFrame, alpha: float = 10.0, seed: int = 42) -> pd.DataFrame:
    """Marginal gold price per stat unit, fit two ways on the same design matrix and target:

    - Ridge: L2-regularized, coefficients constrained non-negative, with an intercept absorbing
      base/combine cost and unmodeled passives.
    - NNLS: unregularized non-negative least squares. `scipy.optimize.nnls` has no intercept
      option, so one is added as an explicit ones-column in the design matrix — without it, NNLS
      is forced through the origin and ends up a different estimand than Ridge, inflated by
      exactly the omitted-variable bias Ridge's intercept absorbs.

    Both are fit on features scaled by their standard deviation (not centered — centering would
    break the non-negativity constraint's meaning). Raw stats span several orders of magnitude
    (`crit_chance` ~0.2, `hp` ~400); an L2 penalty applied to unscaled coefficients shrinks the
    small-scale stats far more than the large-scale ones for no principled reason. Coefficients
    are converted back to gold-per-original-unit before being returned.
    """
    stat_columns = [name for name in REFERENCE_ITEMS if name in items and items[name].fillna(0).abs().sum() > 0]
    model_data = items.loc[items["total_gold"] > 0, [*stat_columns, "total_gold"]].fillna(0)
    if len(model_data) < len(stat_columns) + 2:
        raise ValueError("회귀 모델을 계산할 아이템 표본이 부족합니다.")

    x = model_data[stat_columns].to_numpy(dtype=float)
    y = model_data["total_gold"].to_numpy(dtype=float)
    scale = x.std(axis=0)
    scale[scale == 0] = 1.0
    x_scaled = x / scale

    ridge = Ridge(alpha=alpha, positive=True, fit_intercept=True).fit(x_scaled, y)
    ridge_coefficients = ridge.coef_ / scale

    design_with_intercept = np.column_stack([np.ones(len(x_scaled)), x_scaled])
    nnls_raw, _ = nnls(design_with_intercept, y)
    nnls_intercept, nnls_coefficients = float(nnls_raw[0]), nnls_raw[1:] / scale

    cv_r2 = _cross_validated_r2(x_scaled, y, alpha, seed)

    references = reference_prices(items)
    return pd.DataFrame(
        {
            "stat": stat_columns,
            "reference_gold_per_unit": [references.get(name, np.nan) for name in stat_columns],
            "ridge_gold_per_unit": ridge_coefficients,
            "nnls_gold_per_unit": nnls_coefficients,
            "nnls_intercept_gold": nnls_intercept,
            "sample_items": len(model_data),
            "cv_r2": cv_r2,
        }
    )


def _cross_validated_r2(x_scaled: np.ndarray, y: np.ndarray, alpha: float, seed: int) -> float:
    """K-fold R² of the Ridge fit (K capped so each test fold keeps at least 2 samples — R² is
    undefined for a single point). A fit-quality diagnostic, not a confidence interval."""
    folds = min(5, len(y) // 2)
    if folds < 2:
        return float("nan")
    scores = []
    for train_idx, test_idx in KFold(n_splits=folds, shuffle=True, random_state=seed).split(x_scaled):
        fitted = Ridge(alpha=alpha, positive=True, fit_intercept=True).fit(x_scaled[train_idx], y[train_idx])
        scores.append(fitted.score(x_scaled[test_idx], y[test_idx]))
    return float(np.mean(scores))


def ridge_price_map(estimates: pd.DataFrame) -> dict[str, float]:
    """`stat -> ridge_gold_per_unit`, for feeding `item_efficiency`'s model-based column."""
    return dict(zip(estimates["stat"], estimates["ridge_gold_per_unit"], strict=True))


def item_efficiency(items: pd.DataFrame, reference: dict[str, float], model: dict[str, float] | None = None) -> pd.DataFrame:
    """Gold efficiency from named reference-item ratios, and — when `model` is given — from the
    regression's marginal prices too, as a separate column. The two are different questions
    ("what does one specific item charge for this stat" vs. "what does the market as a whole pay
    for it"); neither should be read as the other."""
    output = items.copy()
    output["estimated_stat_value"] = sum(output.get(stat, 0) * value for stat, value in reference.items())
    output["gold_efficiency_percent"] = np.where(output["total_gold"] > 0, output["estimated_stat_value"] / output["total_gold"] * 100, np.nan)
    output["passive_shadow_price"] = output["total_gold"] - output["estimated_stat_value"]
    if model:
        output["model_estimated_stat_value"] = sum(output.get(stat, 0) * value for stat, value in model.items())
        output["model_gold_efficiency_percent"] = np.where(
            output["total_gold"] > 0, output["model_estimated_stat_value"] / output["total_gold"] * 100, np.nan
        )
    return output
