from __future__ import annotations

import hashlib
import json
import math
from datetime import UTC, datetime, timedelta
from typing import Literal

import numpy as np
import pandas as pd
from scipy import stats

from ..database import db
from ..schemas import RelationshipItem, RelationshipRequest, RelationshipResponse
from .datasets import get_profile, get_version, read_frame


def _direction(score: float, signed: bool = True) -> Literal["positive", "negative", "none"]:
    if not signed or abs(score) < 1e-12:
        return "none"
    return "positive" if score > 0 else "negative"


def _cramers_v(x: pd.Series, y: pd.Series) -> float:
    table = pd.crosstab(x, y)
    if table.empty or min(table.shape) < 2:
        return 0.0
    chi2 = stats.chi2_contingency(table, correction=False)[0]
    n = table.values.sum()
    phi2 = chi2 / n
    r, k = table.shape
    correction = ((k - 1) * (r - 1)) / max(n - 1, 1)
    phi2_corr = max(0.0, phi2 - correction)
    r_corr = r - ((r - 1) ** 2) / max(n - 1, 1)
    k_corr = k - ((k - 1) ** 2) / max(n - 1, 1)
    denom = min(k_corr - 1, r_corr - 1)
    return math.sqrt(phi2_corr / denom) if denom > 0 else 0.0


def _eta_squared(category: pd.Series, numeric: pd.Series) -> float:
    total_mean = numeric.mean()
    denominator = ((numeric - total_mean) ** 2).sum()
    if denominator == 0:
        return 0.0
    numerator = sum(len(values) * (values.mean() - total_mean) ** 2 for _, values in numeric.groupby(category))
    return float(numerator / denominator)


def _chart(selected: str, candidate: str, relation: str, selected_type: str) -> dict:
    if relation == "numeric_numeric":
        return {"type": "scatter", "x": selected, "y": candidate}
    if relation == "categorical_categorical":
        return {"type": "heatmap", "x": selected, "y": candidate, "aggregate": "count"}
    if relation == "datetime_numeric":
        date_col, value_col = (selected, candidate) if selected_type == "datetime" else (candidate, selected)
        return {"type": "line", "x": date_col, "y": value_col, "aggregate": "mean", "time_grain": "day"}
    category, numeric = (selected, candidate) if selected_type == "categorical" else (candidate, selected)
    return {"type": "boxplot", "category": category, "value": numeric}


def analyze(dataset_id: str, request: RelationshipRequest) -> RelationshipResponse:
    profile = get_profile(dataset_id)
    metadata = {item.name: item for item in profile.columns}
    if request.column not in metadata:
        raise KeyError(request.column)
    selected_meta = metadata[request.column]
    if selected_meta.semantic_type in {"identifier", "text"}:
        raise ValueError("식별자와 자유서술 컬럼은 기본 관계 추천 대상이 아닙니다.")
    candidates = [
        item for item in profile.columns
        if item.name != request.column and item.semantic_type not in {"identifier", "text"}
        and item.unique_count > 1 and item.null_ratio < 0.8
    ]
    candidates.sort(key=lambda item: (item.null_ratio, item.unique_count == profile.row_count, -item.unique_count))
    candidates = candidates[: request.candidate_limit]
    frame = read_frame(dataset_id)
    if request.entity_key:
        if request.entity_key not in frame.columns:
            raise ValueError("entity_key가 데이터셋에 없습니다.")
        grain = request.analysis_grain or "mean"
        if grain == "latest":
            if not request.time_column or request.time_column not in frame.columns:
                raise ValueError("latest 분석 단위에는 데이터셋의 time_column이 필요합니다.")
            frame = frame.sort_values(request.time_column, kind="stable").drop_duplicates(request.entity_key, keep="last")
        else:
            aggregations = {
                column: ("mean" if pd.api.types.is_numeric_dtype(frame[column]) else "first")
                for column in frame.columns if column != request.entity_key
            }
            frame = frame.groupby(request.entity_key, dropna=False, as_index=False).agg(aggregations)
    elif request.analysis_grain:
        raise ValueError("analysis_grain에는 entity_key가 필요합니다.")
    sampled = len(frame) > request.sample_limit
    if sampled:
        frame = frame.sample(request.sample_limit, random_state=request.seed)
    items: list[RelationshipItem] = []
    for candidate in candidates:
        pair = frame[[request.column, candidate.name]].dropna()
        n = len(pair)
        if n < request.minimum_pair_samples:
            continue
        a, b = selected_meta.semantic_type, candidate.semantic_type
        if a == "numeric" and b == "numeric":
            numeric_pair = pair.astype(float)
            if numeric_pair.iloc[:, 0].nunique() < 2 or numeric_pair.iloc[:, 1].nunique() < 2:
                score, pearson = 0.0, 0.0
            else:
                score = float(stats.spearmanr(numeric_pair.iloc[:, 0], numeric_pair.iloc[:, 1]).statistic or 0.0)
                clipped = numeric_pair.copy()
                for column in clipped.columns:
                    low, high = clipped[column].quantile([0.01, 0.99])
                    clipped[column] = clipped[column].clip(low, high)
                pearson = float(stats.pearsonr(clipped.iloc[:, 0], clipped.iloc[:, 1]).statistic or 0.0)
            relation, method, signed = "numeric_numeric", "Spearman", True
        elif a == "categorical" and b == "categorical":
            if max(pair.iloc[:, 0].nunique(), pair.iloc[:, 1].nunique()) > 30:
                continue
            score = _cramers_v(pair.iloc[:, 0], pair.iloc[:, 1])
            relation, method, signed = "categorical_categorical", "Bias-corrected Cramer's V", False
        elif {a, b} == {"categorical", "numeric"}:
            category = pair.iloc[:, 0] if a == "categorical" else pair.iloc[:, 1]
            numeric = pair.iloc[:, 1] if a == "categorical" else pair.iloc[:, 0]
            if category.nunique() > 30:
                continue
            score = _eta_squared(category, numeric)
            relation, method, signed = "categorical_numeric", "Eta squared", False
        elif {a, b} == {"datetime", "numeric"}:
            date_values = pd.to_datetime(pair.iloc[:, 0] if a == "datetime" else pair.iloc[:, 1], errors="coerce")
            numeric_values = pd.to_numeric(pair.iloc[:, 1] if a == "datetime" else pair.iloc[:, 0], errors="coerce")
            trend = pd.DataFrame({"date": date_values.dt.floor("D"), "value": numeric_values}).dropna().groupby("date")["value"].mean()
            score = float(stats.spearmanr(np.arange(len(trend)), trend.to_numpy()).statistic or 0.0) if len(trend) >= 3 else 0.0
            relation, method, signed = "datetime_numeric", "Daily trend Spearman", True
        else:
            continue
        if not math.isfinite(score):
            score = 0.0
        grain_note = f"{request.entity_key} 기준 {request.analysis_grain or 'mean'} 단위로 정리한 " if request.entity_key else ""
        reason = f"{grain_note}유효 표본 {n:,}개에서 {method} 값이 {score:.3f}입니다."
        if relation == "numeric_numeric":
            reason += f" 상·하위 1% 윈저라이징 Pearson 보조값은 {pearson:.3f}입니다."
        items.append(RelationshipItem(
            column=candidate.name, relation_type=relation, method=method,
            score=round(score, 6), direction=_direction(score, signed), sample_size=n,
            null_ratio=round(1 - n / max(len(frame), 1), 6), reason=reason,
            chart_spec=_chart(request.column, candidate.name, relation, a),
        ))
    items.sort(key=lambda item: abs(item.score), reverse=True)
    counts: dict[str, int] = {}
    limited: list[RelationshipItem] = []
    for item in items:
        count = counts.get(item.relation_type, 0)
        if count >= request.result_limit:
            continue
        limited.append(item)
        counts[item.relation_type] = count + 1
    version = get_version(dataset_id)
    return RelationshipResponse(
        dataset_id=dataset_id, version_id=version["id"], selected_column=request.column,
        compared_candidates=len(candidates), sampled=sampled, items=limited,
    )


def analyze_cached(dataset_id: str, request: RelationshipRequest) -> RelationshipResponse:
    version = get_version(dataset_id)
    material = json.dumps({"version": version["id"], **request.model_dump()}, sort_keys=True, ensure_ascii=False)
    cache_key = hashlib.sha256(material.encode("utf-8")).hexdigest()
    now = datetime.now(UTC)
    with db() as connection:
        row = connection.execute(
            "SELECT result_json, expires_at FROM relationship_cache WHERE cache_key=?", (cache_key,)
        ).fetchone()
        if row and datetime.fromisoformat(row["expires_at"]) > now:
            connection.execute("UPDATE relationship_cache SET accessed_at=? WHERE cache_key=?", (now.isoformat(), cache_key))
            return RelationshipResponse.model_validate_json(row["result_json"])
    result = analyze(dataset_id, request)
    expires = now + timedelta(hours=24)
    with db() as connection:
        connection.execute(
            """INSERT OR REPLACE INTO relationship_cache
            (cache_key,dataset_version_id,result_json,accessed_at,expires_at) VALUES(?,?,?,?,?)""",
            (cache_key, version["id"], result.model_dump_json(), now.isoformat(), expires.isoformat()),
        )
        connection.execute("DELETE FROM relationship_cache WHERE expires_at < ?", (now.isoformat(),))
    return result
