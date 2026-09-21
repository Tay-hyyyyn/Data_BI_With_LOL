"""Query boundary: typed plans in, DuckDB-backed frames out."""

from .engine import materialize, run, scalar, schema_of
from .plan import Aggregate, Filter, QueryPlan, Sample

__all__ = ["Aggregate", "Filter", "QueryPlan", "Sample", "materialize", "run", "scalar", "schema_of"]
