from __future__ import annotations

import math
from typing import Any


def json_safe(value: Any) -> Any:
    """Convert nested values to strict-JSON-compatible values.

    Financial pipelines often produce NaN when a window is too short. A report
    must represent that as null rather than emitting non-standard JSON tokens.
    """
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    # numpy scalar values expose item(); pandas timestamps are stringified.
    item = getattr(value, "item", None)
    if callable(item):
        try:
            return json_safe(item())
        except (TypeError, ValueError):
            pass
    iso = getattr(value, "isoformat", None)
    if callable(iso):
        try:
            return iso()
        except (TypeError, ValueError):
            pass
    return str(value)
