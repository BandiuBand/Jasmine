"""Time bucket utilities for Jasmine v2 memory.

Provides functions to normalize datetime values and generate
time bucket strings for day, week, and month granularity.
"""

from datetime import datetime, timezone


def normalize_datetime(value: datetime | str | None = None) -> datetime:
    """Normalize various input types to a timezone-aware datetime.

    Rules:
    - None -> current UTC datetime
    - datetime with timezone -> return as-is
    - naive datetime -> treat as UTC
    - ISO string -> parse (with or without Z)

    Args:
        value: Input value to normalize. Can be datetime, ISO string, or None.

    Returns:
        Timezone-aware datetime in UTC.
    """
    if value is None:
        return datetime.now(timezone.utc)

    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    if isinstance(value, str):
        # Handle ISO string with Z suffix (convert to +00:00)
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        # Try parsing ISO format
        try:
            dt = datetime.fromisoformat(value)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError as e:
            raise ValueError(f"Invalid datetime string: {value}") from e

    raise TypeError(f"Expected datetime, str, or None, got {type(value).__name__}")


def day_bucket(value: datetime | str | None = None) -> str:
    """Generate day bucket string in YYYY-MM-DD format.

    Args:
        value: Input datetime or ISO string. Defaults to current UTC time.

    Returns:
        Day bucket string (e.g., "2026-05-11").
    """
    dt = normalize_datetime(value)
    return dt.strftime("%Y-%m-%d")


def week_bucket(value: datetime | str | None = None) -> str:
    """Generate week bucket string in YYYY-Www ISO week format.

    Args:
        value: Input datetime or ISO string. Defaults to current UTC time.

    Returns:
        Week bucket string (e.g., "2026-W19").
    """
    dt = normalize_datetime(value)
    return dt.strftime("%Y-W%V")


def month_bucket(value: datetime | str | None = None) -> str:
    """Generate month bucket string in YYYY-MM format.

    Args:
        value: Input datetime or ISO string. Defaults to current UTC time.

    Returns:
        Month bucket string (e.g., "2026-05").
    """
    dt = normalize_datetime(value)
    return dt.strftime("%Y-%m")
