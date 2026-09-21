"""DuckDB access boundary.

`materialize` is the explicit escape hatch for pandas-shaped workloads (transforms, relationship
analysis, LoL marts). `run` and `scalar` execute a `QueryPlan` and are the migration target for the
BI layer, which still aggregates in pandas today.
"""

from __future__ import annotations

from collections.abc import Sequence

import duckdb
import pandas as pd

from .plan import QueryPlan
from .source import parquet_files, quote_identifier, quote_literal


def _relation(dataset_id: str) -> str:
    files = ",".join(quote_literal(path) for path in parquet_files(dataset_id))
    return f"read_parquet([{files}])"


def schema_of(dataset_id: str) -> dict[str, str]:
    """Column name -> DuckDB type of the current published version."""
    with duckdb.connect(":memory:") as connection:
        rows = connection.execute(f"DESCRIBE SELECT * FROM {_relation(dataset_id)}").fetchall()  # noqa: S608 - paths quoted by quote_literal
    return {row[0]: row[1] for row in rows}


def materialize(dataset_id: str, columns: Sequence[str] | None = None, limit: int | None = None) -> pd.DataFrame:
    """Load the current published version as a DataFrame, optionally projecting columns and limiting rows."""
    if columns is not None:
        known = schema_of(dataset_id)
        missing = [column for column in columns if column not in known]
        if missing:
            raise ValueError(f"존재하지 않는 컬럼: {', '.join(missing)}")
        projection = ", ".join(quote_identifier(column) for column in columns)
    else:
        projection = "*"
    query = f"SELECT {projection} FROM {_relation(dataset_id)}"  # noqa: S608 - identifiers validated above, paths quoted
    parameters: list[int] = []
    if limit is not None:
        query += " LIMIT ?"
        parameters.append(limit)
    with duckdb.connect(":memory:") as connection:
        return connection.execute(query, parameters).fetchdf()


def run(dataset_id: str, plan: QueryPlan) -> pd.DataFrame:
    raise NotImplementedError("Plan execution lands with the query-engine workstream.")


def scalar(dataset_id: str, plan: QueryPlan) -> float | None:
    raise NotImplementedError("Plan execution lands with the query-engine workstream.")
