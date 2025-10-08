"""turbopuffer-specific transformations and query handling."""

from __future__ import annotations

import json
from typing import Any

from raggy.vectorstores.tpuf import TurboPuffer  # type: ignore[reportMissingTypeStubs]
from turbopuffer import BadRequestError
from turbopuffer.types.row import Row as TurboPufferRow

from docs_mcp_server._settings import settings


def row_to_dict(row: TurboPufferRow | dict[str, Any]) -> dict[str, Any]:
    """normalize turbopuffer row objects to plain dictionaries."""

    if isinstance(row, dict):
        data = dict(row)
    else:
        data = row.model_dump(mode="python")
        if row.model_extra:
            data.update(row.model_extra)

    metadata = data.get("metadata")
    if isinstance(metadata, str):
        try:
            data["metadata"] = json.loads(metadata)
        except json.JSONDecodeError:
            pass

    return data


def normalize_score(value: Any) -> float | None:
    """coerce turbopuffer scores into floats when present."""

    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def run_query(
    *,
    query: str,
    top_k: int,
    include_attributes: list[str],
):
    """run a turbopuffer query with automatic retry on schema errors."""
    include_arg = include_attributes or None
    with TurboPuffer(namespace=settings.turbopuffer.namespace) as tpuf:
        try:
            return tpuf.query(
                text=query,
                top_k=top_k,
                include_attributes=include_arg,
            )
        except BadRequestError as exc:
            if include_arg is not None and "include_attributes" in str(exc).lower():
                # retry without extra attribute hints; schema likely lacks one of them
                return tpuf.query(text=query, top_k=top_k)
            raise
