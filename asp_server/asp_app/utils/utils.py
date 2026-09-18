import math
from typing import Any, Optional

def safe_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        if isinstance(value, float) and math.isnan(value):
            return None
        return int(value)
    except Exception:
        try:
            return int(float(value))
        except Exception:
            return None

def safe_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        if isinstance(value, float) and math.isnan(value):
            return None
        return float(value)
    except Exception:
        return None


def safe_bool(val):
    if val is None:
        return None
    return str(val).strip().lower() in ("true", "yes", "1")