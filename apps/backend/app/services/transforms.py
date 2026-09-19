from __future__ import annotations

from typing import Any

import pandas as pd

from ..schemas import TransformRequest, TransformResult
from .datasets import publish_new_version, read_frame


def _columns_exist(frame: pd.DataFrame, columns: list[str]) -> None:
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ValueError(f"존재하지 않는 컬럼: {', '.join(missing)}")


def _apply(frame: pd.DataFrame, operation: str, config: dict[str, Any]) -> pd.DataFrame:
    output = frame.copy()
    if operation == "select":
        columns = list(config.get("columns", [])); _columns_exist(output, columns)
        return output[columns]
    if operation == "rename":
        mapping = dict(config.get("mapping", {})); _columns_exist(output, list(mapping))
        return output.rename(columns=mapping)
    if operation == "cast":
        column, dtype = config["column"], config["dtype"]; _columns_exist(output, [column])
        converters = {"number": lambda s: pd.to_numeric(s, errors="coerce"), "datetime": lambda s: pd.to_datetime(s, errors="coerce"), "string": lambda s: s.astype("string"), "category": lambda s: s.astype("category")}
        if dtype not in converters: raise ValueError("지원하지 않는 변환 타입입니다.")
        output[column] = converters[dtype](output[column]); return output
    if operation == "fill_missing":
        column = config["column"]; _columns_exist(output, [column])
        method = config.get("method", "value")
        if method == "mean": output[column] = output[column].fillna(output[column].mean())
        elif method == "median": output[column] = output[column].fillna(output[column].median())
        elif method == "mode": output[column] = output[column].fillna(output[column].mode().iloc[0])
        else: output[column] = output[column].fillna(config.get("value"))
        return output
    if operation == "drop_missing":
        columns = list(config.get("columns", [])); _columns_exist(output, columns)
        return output.dropna(subset=columns or None)
    if operation == "drop_duplicates":
        columns = list(config.get("columns", [])); _columns_exist(output, columns)
        return output.drop_duplicates(subset=columns or None, keep=config.get("keep", "first"))
    if operation == "filter":
        column, operator, value = config["column"], config["operator"], config.get("value"); _columns_exist(output, [column])
        operators = {"eq": output[column].eq, "ne": output[column].ne, "gt": output[column].gt, "gte": output[column].ge, "lt": output[column].lt, "lte": output[column].le}
        if operator == "contains": mask = output[column].astype(str).str.contains(str(value), regex=False, na=False)
        elif operator == "in": mask = output[column].isin(value)
        elif operator in operators: mask = operators[operator](value)
        else: raise ValueError("지원하지 않는 필터 연산자입니다.")
        return output.loc[mask]
    if operation == "calculate":
        left, right, operator, target = config["left"], config["right"], config["operator"], config["target"]
        _columns_exist(output, [left] + ([right] if isinstance(right, str) else []))
        rhs = output[right] if isinstance(right, str) else right
        operations = {"add": lambda: output[left] + rhs, "subtract": lambda: output[left] - rhs, "multiply": lambda: output[left] * rhs, "divide": lambda: output[left].div(rhs).replace([float("inf"), float("-inf")], pd.NA)}
        if operator not in operations: raise ValueError("지원하지 않는 계산 연산자입니다.")
        output[target] = operations[operator](); return output
    if operation == "aggregate":
        group_by, metrics = list(config.get("group_by", [])), dict(config.get("metrics", {})); _columns_exist(output, group_by + list(metrics))
        return output.groupby(group_by, dropna=False).agg(metrics).reset_index()
    if operation == "pivot":
        index, columns, values = config["index"], config["columns"], config["values"]; _columns_exist(output, [index, columns, values])
        return output.pivot_table(index=index, columns=columns, values=values, aggfunc=config.get("aggfunc", "sum"), fill_value=config.get("fill_value", 0)).reset_index()
    if operation == "join":
        right_dataset_id = str(config["right_dataset_id"])
        left_on = list(config.get("left_on", []))
        right_on = list(config.get("right_on", left_on))
        how = config.get("how", "left")
        if not left_on or len(left_on) != len(right_on):
            raise ValueError("조인 키는 좌·우 데이터셋에 같은 개수로 지정해야 합니다.")
        if how not in {"left", "inner"}:
            raise ValueError("조인은 left 또는 inner 방식만 지원합니다.")
        _columns_exist(output, left_on)
        right = read_frame(right_dataset_id)
        _columns_exist(right, right_on)
        validate = config.get("validate")
        allowed_validations = {None, "one_to_one", "one_to_many", "many_to_one", "many_to_many"}
        if validate not in allowed_validations:
            raise ValueError("지원하지 않는 조인 카디널리티 검증입니다.")
        return output.merge(
            right,
            how=how,
            left_on=left_on,
            right_on=right_on,
            suffixes=("", "_right"),
            validate=validate,
            sort=False,
        )
    raise ValueError("지원하지 않는 전처리 작업입니다.")


def run_recipe(dataset_id: str, request: TransformRequest) -> TransformResult:
    frame = read_frame(dataset_id)
    for step in request.steps:
        frame = _apply(frame, step.operation, step.config)
    result = publish_new_version(dataset_id, frame, request.name, [step.model_dump() for step in request.steps])
    return TransformResult(**result)
