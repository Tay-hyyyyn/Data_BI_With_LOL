"""Resolve a dataset id to its published Parquet files (the only place that knows the storage layout)."""

from __future__ import annotations

from ..database import db
from ..storage import manifest_files


def parquet_files(dataset_id: str) -> list[str]:
    """Paths of the current published version's Parquet files. Raises KeyError for unknown datasets."""
    with db() as connection:
        row = connection.execute(
            """SELECT v.manifest_path FROM dataset_versions v
            JOIN datasets d ON d.current_version_id=v.id WHERE d.id=?""",
            (dataset_id,),
        ).fetchone()
    if not row:
        raise KeyError(dataset_id)
    return [str(path) for path in manifest_files(row["manifest_path"])]


def quote_identifier(name: str) -> str:
    """Quote a column name for DuckDB. Callers must still validate it against `schema_of`."""
    return '"' + name.replace('"', '""') + '"'


def quote_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"
