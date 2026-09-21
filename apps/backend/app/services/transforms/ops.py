"""Preprocessing operations. One function per operation; `OPERATIONS` is the dispatch registry."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pandas as pd

from ..datasets import read_frame

Config = dict[str, Any]


def _columns_exist(frame: pd.DataFrame, columns: list[str]) -> None:
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ValueError(f"존재하지 않는 컬럼: {', '.join(missing)}")


def op_select(frame: pd.DataFrame, config: Config) -> pd.DataFrame:
    columns = list(config.get("columns", []))
    _columns_exist(frame, columns)
    return frame[columns]


def op_rename(frame: pd.DataFrame, config: Config) -> pd.DataFrame:
    mapping = dict(config.get("mapping", {}))
    _columns_exist(frame, list(mapping))
    return frame.rename(columns=mapping)


_CASTS: dict[str, Callable[[pd.Series], pd.Series]] = {
    "number": lambda s: pd.to_numeric(s, errors="coerce"),
    "datetime": lambda s: pd.to_datetime(s, errors="coerce"),
    "string": lambda s: s.astype("string"),
    "category": lambda s: s.astype("category"),
}


def op_cast(frame: pd.DataFrame, config: Config) -> pd.DataFrame:
    column, dtype = config["column"], config["dtype"]
    _columns_exist(frame, [column])
    if dtype not in _CASTS:
        raise ValueError("지원하지 않는 변환 타입입니다.")
    frame[column] = _CASTS[dtype](frame[column])
    return frame


def op_fill_missing(frame: pd.DataFrame, config: Config) -> pd.DataFrame:
    column = config["column"]
    _columns_exist(frame, [column])
    method = config.get("method", "value")
    if method == "mean":
        frame[column] = frame[column].fillna(frame[column].mean())
    elif method == "median":
        frame[column] = frame[column].fillna(frame[column].median())
    elif method == "mode":
        frame[column] = frame[column].fillna(frame[column].mode().iloc[0])
    else:
        frame[column] = frame[column].fillna(config.get("value"))
    return frame


def op_drop_missing(frame: pd.DataFrame, config: Config) -> pd.DataFrame:
    columns = list(config.get("columns", []))
    _columns_exist(frame, columns)
    return frame.dropna(subset=columns or None)


def op_drop_duplicates(frame: pd.DataFrame, config: Config) -> pd.DataFrame:
    columns = list(config.get("columns", []))
    _columns_exist(frame, columns)
    return frame.drop_duplicates(subset=columns or None, keep=config.get("keep", "first"))


def op_filter(frame: pd.DataFrame, config: Config) -> pd.DataFrame:
    column, operator, value = config["column"], config["operator"], config.get("value")
    _columns_exist(frame, [column])
    comparisons = {
        "eq": frame[column].eq,
        "ne": frame[column].ne,
        "gt": frame[column].gt,
        "gte": frame[column].ge,
        "lt": frame[column].lt,
        "lte": frame[column].le,
    }
    if operator == "contains":
        mask = frame[column].astype(str).str.contains(str(value), regex=False, na=False)
    elif operator == "in":
        mask = frame[column].isin(value)
    elif operator in comparisons:
        mask = comparisons[operator](value)
    else:
        raise ValueError("지원하지 않는 필터 연산자입니다.")
    return frame.loc[mask]


def op_calculate(frame: pd.DataFrame, config: Config) -> pd.DataFrame:
    left, right, operator, target = config["left"], config["right"], config["operator"], config["target"]
    _columns_exist(frame, [left] + ([right] if isinstance(right, str) else []))
    rhs = frame[right] if isinstance(right, str) else right
    calculations: dict[str, Callable[[], Any]] = {
        "add": lambda: frame[left] + rhs,
        "subtract": lambda: frame[left] - rhs,
        "multiply": lambda: frame[left] * rhs,
        "divide": lambda: frame[left].div(rhs).replace([float("inf"), float("-inf")], pd.NA),
    }
    if operator not in calculations:
        raise ValueError("지원하지 않는 계산 연산자입니다.")
    frame[target] = calculations[operator]()
    return frame


def op_aggregate(frame: pd.DataFrame, config: Config) -> pd.DataFrame:
    group_by, metrics = list(config.get("group_by", [])), dict(config.get("metrics", {}))
    _columns_exist(frame, group_by + list(metrics))
    return frame.groupby(group_by, dropna=False).agg(metrics).reset_index()


def op_pivot(frame: pd.DataFrame, config: Config) -> pd.DataFrame:
    index, columns, values = config["index"], config["columns"], config["values"]
    _columns_exist(frame, [index, columns, values])
    return frame.pivot_table(
        index=index,
        columns=columns,
        values=values,
        aggfunc=config.get("aggfunc", "sum"),
        fill_value=config.get("fill_value", 0),
    ).reset_index()


_JOIN_VALIDATIONS = {None, "one_to_one", "one_to_many", "many_to_one", "many_to_many"}


def op_join(frame: pd.DataFrame, config: Config) -> pd.DataFrame:
    right_dataset_id = str(config["right_dataset_id"])
    left_on = list(config.get("left_on", []))
    right_on = list(config.get("right_on", left_on))
    how = config.get("how", "left")
    if not left_on or len(left_on) != len(right_on):
        raise ValueError("조인 키는 좌·우 데이터셋에 같은 개수로 지정해야 합니다.")
    if how not in {"left", "inner"}:
        raise ValueError("조인은 left 또는 inner 방식만 지원합니다.")
    _columns_exist(frame, left_on)
    right = read_frame(right_dataset_id)
    _columns_exist(right, right_on)
    validate = config.get("validate")
    if validate not in _JOIN_VALIDATIONS:
        raise ValueError("지원하지 않는 조인 카디널리티 검증입니다.")
    return frame.merge(
        right,
        how=how,
        left_on=left_on,
        right_on=right_on,
        suffixes=("", "_right"),
        validate=validate,
        sort=False,
    )


OPERATIONS: dict[str, Callable[[pd.DataFrame, Config], pd.DataFrame]] = {
    "select": op_select,
    "rename": op_rename,
    "cast": op_cast,
    "fill_missing": op_fill_missing,
    "drop_missing": op_drop_missing,
    "drop_duplicates": op_drop_duplicates,
    "filter": op_filter,
    "calculate": op_calculate,
    "aggregate": op_aggregate,
    "pivot": op_pivot,
    "join": op_join,
}


def apply_step(frame: pd.DataFrame, operation: str, config: Config) -> pd.DataFrame:
    handler = OPERATIONS.get(operation)
    if handler is None:
        raise ValueError("지원하지 않는 전처리 작업입니다.")
    return handler(frame.copy(), config)
