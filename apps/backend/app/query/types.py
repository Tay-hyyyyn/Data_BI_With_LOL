"""DuckDB type helpers used by the compiler."""

from __future__ import annotations

import re

_NUMERIC = re.compile(
    r"^(TINYINT|SMALLINT|INTEGER|BIGINT|HUGEINT|UTINYINT|USMALLINT|UINTEGER|UBIGINT|UHUGEINT|FLOAT|REAL|DOUBLE|DECIMAL\(\d+,\s*\d+\))$"
)
_TEMPORAL = re.compile(r"^(DATE|TIMESTAMP(_S|_MS|_NS)?|TIMESTAMP WITH TIME ZONE)$")
# Types come from DuckDB's own DESCRIBE, but they are still embedded in SQL (CAST(? AS <type>)), so allow only a known shape.
_SAFE = re.compile(r"^[A-Z][A-Z0-9_ ]*(\(\d+(,\s*\d+)?\))?$")


def is_numeric(type_name: str) -> bool:
    return bool(_NUMERIC.match(type_name))


def is_temporal(type_name: str) -> bool:
    return bool(_TEMPORAL.match(type_name))


def is_boolean(type_name: str) -> bool:
    return type_name == "BOOLEAN"


def is_orderable(type_name: str) -> bool:
    """Dimensions whose natural order is meaningful (time axes, numeric axes); others rank by value."""
    return is_numeric(type_name) or is_temporal(type_name) or is_boolean(type_name)


def cast_target(type_name: str) -> str:
    if not _SAFE.match(type_name):
        raise ValueError(f"지원하지 않는 컬럼 타입입니다: {type_name}")
    return type_name
