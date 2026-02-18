"""Shared utilities for Prefect client modules."""

from typing import Any


def is_detail_query(filter: dict[str, Any] | None) -> bool:
    """Check if a filter is targeting specific IDs (detail mode).

    When a user filters by a small number of specific IDs, they're looking at
    particular items and want full detail. Otherwise they're browsing and get
    a compact response with heavy fields stripped.
    """
    if not filter:
        return False
    id_filter = filter.get("id", {})
    if isinstance(id_filter, dict) and "any_" in id_filter:
        ids = id_filter["any_"]
        return isinstance(ids, list) and 0 < len(ids) <= 5
    return False
