from __future__ import annotations

from typing import Iterable

from sqlalchemy.types import UserDefinedType


class VectorType(UserDefinedType):
    """Minimal pgvector column type for SQLAlchemy."""

    cache_ok = True

    def __init__(self, dimensions: int) -> None:
        self.dimensions = dimensions

    def get_col_spec(self, **kw) -> str:  # noqa: ARG002
        return f"vector({self.dimensions})"

    @staticmethod
    def _to_vector_literal(values: Iterable[float]) -> str:
        normalized = ",".join(f"{float(value):.10g}" for value in values)
        return f"[{normalized}]"

    def bind_processor(self, dialect):  # type: ignore[override]
        def process(value):
            if value is None:
                return None
            return self._to_vector_literal(value)

        return process

    def result_processor(self, dialect, coltype):  # type: ignore[override]  # noqa: ARG002
        def process(value):
            if value is None:
                return None
            if isinstance(value, str):
                stripped = value.strip().strip("[]")
                if not stripped:
                    return []
                return [float(item.strip()) for item in stripped.split(",")]
            return [float(item) for item in value]

        return process
