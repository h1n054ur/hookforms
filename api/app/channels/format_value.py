"""
Smart value formatter for webhook payloads.

When a value is a nested dict (common with GitHub, Stripe, GitLab webhooks etc.)
we try to extract a human-readable display name instead of showing the raw repr.

Priority order for display-name extraction:
  full_name > name > login > title > label > email > url > id
"""

import json
from typing import Any

# Keys we look for (in priority order) when extracting a display name from a dict.
DISPLAY_KEYS = (
    "full_name",
    "name",
    "login",
    "title",
    "label",
    "email",
    "html_url",
    "url",
    "id",
)


def format_value(val: Any, max_len: int = 300) -> str:
    """
    Format a single value into a human-readable string.

    - Primitives are returned via ``str(val)``.
    - Lists of primitives are joined with ", ".
    - Dicts are inspected for well-known display keys; if found we return that.
    - Otherwise we return compact JSON (truncated to *max_len* chars).
    """
    if val is None:
        return ""

    # Primitives
    if not isinstance(val, (dict, list)):
        return str(val)

    # Lists
    if isinstance(val, list):
        if len(val) == 0:
            return "(empty)"
        # If every element is a primitive, join them
        if all(not isinstance(v, (dict, list)) for v in val):
            return ", ".join(str(v) for v in val)
        # List of dicts -- try to extract display names from each
        items = [format_value(v, 80) for v in val]
        joined = ", ".join(items)
        return f"{joined[:max_len]}..." if len(joined) > max_len else joined

    # Dicts -- try display-name extraction
    for key in DISPLAY_KEYS:
        if key in val and val[key] is not None and not isinstance(val[key], (dict, list)):
            return str(val[key])

    # Fallback: compact JSON (truncated)
    try:
        dumped = json.dumps(val, default=str)
        return f"{dumped[:max_len]}..." if len(dumped) > max_len else dumped
    except (TypeError, ValueError):
        return "[complex value]"
