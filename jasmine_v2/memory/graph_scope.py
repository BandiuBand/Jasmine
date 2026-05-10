"""Graph scope utilities for Jasmine v2 memory.

Provides MemoryGraphScope dataclass and helper functions to create
and manage graph scopes for different time levels.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from jasmine_v2.memory.spaces import MemorySpace
from jasmine_v2.memory.time_buckets import day_bucket, month_bucket, week_bucket


@dataclass(frozen=True)
class MemoryGraphScope:
    """Represents a memory graph scope with space, time level, and time ID.

    A graph scope uniquely identifies a temporal slice of memory within a space.
    The graph_id follows the format: jv2:{space_type}:{space_id}:{time_level}:{time_id}
    """

    space: MemorySpace
    time_level: Literal["day", "week", "month", "longterm"]
    time_id: str

    @property
    def graph_id(self) -> str:
        """Return the full graph ID in format 'jv2:{space_type}:{space_id}:{time_level}:{time_id}'."""
        return f"jv2:{self.space.space_type}:{self.space.space_id}:{self.time_level}:{self.time_id}"


def make_day_scope(space: MemorySpace, dt: datetime | str | None = None) -> MemoryGraphScope:
    """Create a day-level graph scope.

    Args:
        space: The memory space.
        dt: Datetime or ISO string. Defaults to current UTC time.

    Returns:
        MemoryGraphScope with time_level="day" and time_id=YYYY-MM-DD.
    """
    return MemoryGraphScope(
        space=space,
        time_level="day",
        time_id=day_bucket(dt),
    )


def make_week_scope(space: MemorySpace, dt: datetime | str | None = None) -> MemoryGraphScope:
    """Create a week-level graph scope.

    Args:
        space: The memory space.
        dt: Datetime or ISO string. Defaults to current UTC time.

    Returns:
        MemoryGraphScope with time_level="week" and time_id=YYYY-Www.
    """
    return MemoryGraphScope(
        space=space,
        time_level="week",
        time_id=week_bucket(dt),
    )


def make_month_scope(space: MemorySpace, dt: datetime | str | None = None) -> MemoryGraphScope:
    """Create a month-level graph scope.

    Args:
        space: The memory space.
        dt: Datetime or ISO string. Defaults to current UTC time.

    Returns:
        MemoryGraphScope with time_level="month" and time_id=YYYY-MM.
    """
    return MemoryGraphScope(
        space=space,
        time_level="month",
        time_id=month_bucket(dt),
    )


def make_longterm_scope(space: MemorySpace) -> MemoryGraphScope:
    """Create a longterm graph scope.

    Args:
        space: The memory space.

    Returns:
        MemoryGraphScope with time_level="longterm" and time_id="all".
    """
    return MemoryGraphScope(
        space=space,
        time_level="longterm",
        time_id="all",
    )


def get_active_scopes(space: MemorySpace, dt: datetime | str | None = None) -> list[MemoryGraphScope]:
    """Get all active graph scopes for a space at a given time.

    Returns scopes in order: day, week, month, longterm.

    Args:
        space: The memory space.
        dt: Datetime or ISO string. Defaults to current UTC time.

    Returns:
        List of MemoryGraphScope objects in priority order.
    """
    return [
        make_day_scope(space, dt),
        make_week_scope(space, dt),
        make_month_scope(space, dt),
        make_longterm_scope(space),
    ]


def get_active_group_ids(space: MemorySpace, dt: datetime | str | None = None) -> list[str]:
    """Get all active graph IDs for a space at a given time.

    Returns graph IDs in order: day, week, month, longterm.

    Args:
        space: The memory space.
        dt: Datetime or ISO string. Defaults to current UTC time.

    Returns:
        List of graph ID strings in priority order.
    """
    return [scope.graph_id for scope in get_active_scopes(space, dt)]
