"""Standard response envelope for the HookForms API."""

from typing import Any, Sequence


def paginated_response(
    items: Sequence[Any],
    total: int,
    limit: int,
    offset: int,
) -> dict:
    return {
        "data": items,
        "meta": {
            "total": total,
            "limit": limit,
            "offset": offset,
        },
    }


def single_response(item: Any) -> dict:
    return {"data": item}
