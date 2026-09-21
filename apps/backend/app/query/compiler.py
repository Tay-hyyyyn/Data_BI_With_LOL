"""Compile a `QueryPlan` into parameterized DuckDB SQL.

Safety rules, in order of importance:
1. Every column name must exist in the dataset schema; it is then quoted, never trusted.
2. Aliases are matched against a strict identifier pattern.
3. Filter values are always bound parameters, cast to the *column's* type, so `region_id = 1` matches a
   DOUBLE column instead of comparing the strings "1" and "1.0".
4. Nothing user-controlled is interpolated except quoted identifiers and validated integers.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from .plan import Aggregate, Bucket, Filter, QueryPlan
from .source import quote_identifier
from .types import cast_target, is_boolean

_ALIAS = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_COMPARISON = {"eq": "=", "ne": "<>", "gt": ">", "gte": ">=", "lt": "<", "lte": "<="}
_SCALAR = (str, int, float, bool)


def _column(name: str, schema: dict[str, str]) -> str:
    if name not in schema:
        raise ValueError(f"존재하지 않는 컬럼: {name}")
    return quote_identifier(name)


def _alias(name: str) -> str:
    if not _ALIAS.match(name):
        raise ValueError(f"잘못된 별칭입니다: {name}")
    return name


def _bind(value: Any) -> Any:
    if isinstance(value, date):  # datetime and pandas.Timestamp are date subclasses; DuckDB casts the ISO string
        return value.isoformat()
    if not isinstance(value, _SCALAR):
        raise ValueError("필터 값은 문자열·숫자·불리언이어야 합니다.")
    return value


def _filter_sql(item: Filter, schema: dict[str, str], params: list[Any]) -> str:
    column = _column(item.column, schema)
    if item.operator == "not_null":
        return f"{column} IS NOT NULL"
    target = cast_target(schema[item.column])
    if item.operator == "in":
        values = item.value if isinstance(item.value, list) else [item.value]
        if not values:
            return "FALSE"
        params.extend(_bind(value) for value in values)
        return f"{column} IN ({', '.join(f'CAST(? AS {target})' for _ in values)})"
    if item.operator not in _COMPARISON:
        raise ValueError(f"지원하지 않는 필터 연산자입니다: {item.operator}")
    params.append(_bind(item.value))
    return f"{column} {_COMPARISON[item.operator]} CAST(? AS {target})"


def _aggregate_sql(item: Aggregate, schema: dict[str, str], params: list[Any]) -> str:
    alias = _alias(item.alias)
    if item.func == "count":
        expression = "COUNT(*)" if item.column is None else f"COUNT({_column(item.column, schema)})"
        return f"{expression} AS {alias}"
    if item.column is None:
        raise ValueError("이 집계에는 column이 필요합니다.")
    column = _column(item.column, schema)
    value = f"CAST({column} AS INTEGER)" if is_boolean(schema[item.column]) and item.func in {"sum", "mean", "quantile"} else column
    if item.func == "sum":
        return f"CAST(SUM({value}) AS DOUBLE) AS {alias}"
    if item.func == "mean":
        return f"AVG({value}) AS {alias}"
    if item.func == "min":
        return f"MIN({value}) AS {alias}"
    if item.func == "max":
        return f"MAX({value}) AS {alias}"
    if item.func == "quantile":
        if item.q is None or not 0 <= item.q <= 1:
            raise ValueError("분위수는 0과 1 사이여야 합니다.")
        params.append(float(item.q))
        return f"quantile_cont({value}, ?) AS {alias}"
    raise ValueError(f"지원하지 않는 집계입니다: {item.func}")


def _bucket_sql(item: Bucket, schema: dict[str, str], params: list[Any]) -> str:
    if item.bins < 1:
        raise ValueError("구간 수는 1 이상이어야 합니다.")
    column = _column(item.column, schema)
    width = (item.high - item.low) / item.bins
    if width <= 0:
        raise ValueError("구간 폭이 0보다 커야 합니다.")
    params.extend([float(item.low), float(width)])
    return f"LEAST(CAST(FLOOR((CAST({column} AS DOUBLE) - ?) / ?) AS INTEGER), {int(item.bins) - 1}) AS {_alias(item.alias)}"


def compile_plan(plan: QueryPlan, relation: str, schema: dict[str, str]) -> tuple[str, list[Any]]:
    """Return `(sql, params)` for `plan` over `relation` (a trusted `read_parquet([...])` expression)."""
    if plan.sample and (plan.aggregates or plan.buckets):
        raise ValueError("표본 추출은 집계와 함께 쓸 수 없습니다.")

    # Parameters are collected in the order their `?` appear in the final SQL text: select list, then WHERE.
    select_params: list[Any] = []
    where_params: list[Any] = []

    select_items = [_column(name, schema) for name in plan.dimensions]
    select_items += [_bucket_sql(item, schema, select_params) for item in plan.buckets]
    select_items += [_aggregate_sql(item, schema, select_params) for item in plan.aggregates]
    if not select_items:
        raise ValueError("조회할 컬럼이나 집계가 필요합니다.")

    where = [_filter_sql(item, schema, where_params) for item in plan.filters]
    inner = f"SELECT * FROM {relation}" + (f" WHERE {' AND '.join(where)}" if where else "")  # noqa: S608 - relation is trusted, filters are bound

    group_keys: list[str] = []
    if plan.aggregates:
        group_keys = [_column(name, schema) for name in plan.dimensions] + [_alias(item.alias) for item in plan.buckets]

    sql = f"SELECT {', '.join(select_items)} FROM ({inner}) AS source"  # noqa: S608 - identifiers validated/quoted, values bound
    if plan.sample:
        sql += f" USING SAMPLE reservoir({int(plan.sample.limit)} ROWS) REPEATABLE ({int(plan.sample.seed)})"
    if group_keys:
        sql += " GROUP BY " + ", ".join(group_keys)

    if plan.order_by:
        known = set(plan.dimensions) | {item.alias for item in plan.aggregates} | {item.alias for item in plan.buckets}
        parts = []
        for name, ascending in plan.order_by:
            if name not in known:
                raise ValueError(f"정렬할 수 없는 컬럼: {name}")
            key = quote_identifier(name)
            parts.append(f"{key} {'ASC' if ascending else 'DESC'} NULLS LAST")
        sql += " ORDER BY " + ", ".join(parts)
    if plan.limit is not None:
        sql += f" LIMIT {int(plan.limit)}"
    return sql, select_params + where_params
