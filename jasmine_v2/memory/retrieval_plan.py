"""Retrieval plan for Jasmine v2 memory system.

Provides data structures and functions to define and build retrieval plans
that specify which memory groups to query and their priorities.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from jasmine_v2.memory.graph_scope import (
    make_day_scope,
    make_longterm_scope,
    make_month_scope,
    make_week_scope,
)
from jasmine_v2.memory.spaces import MemorySpace


MemoryGroupRole = Literal["primary", "secondary", "historical", "longterm", "system"]


@dataclass(frozen=True)
class MemoryGroupRef:
    """Reference to a memory group with role and weight for retrieval.

    Attributes:
        group_id: The unique identifier of the memory group.
        role: The role of this group in retrieval (primary, secondary, etc.).
        weight: The weight/priority of this group (0.0 to 1.0).
        reason: Optional reason for including this group.
    """

    group_id: str
    role: MemoryGroupRole
    weight: float
    reason: str | None = None


@dataclass(frozen=True)
class RetrievalPlan:
    """A plan defining which memory groups to retrieve and their priorities.

    Attributes:
        primary_space: The primary memory space for retrieval.
        groups: List of memory group references in priority order.
    """

    primary_space: MemorySpace
    groups: list[MemoryGroupRef]

    @property
    def group_ids(self) -> list[str]:
        """Return list of group IDs in the plan."""
        return [group.group_id for group in self.groups]


def build_default_retrieval_plan(
    primary_space: MemorySpace,
    extra_spaces: list[MemorySpace] | None = None,
    dt: datetime | str | None = None,
) -> RetrievalPlan:
    """Build a default retrieval plan for the given spaces.

    For the primary space, includes all time levels:
    - day: role="primary", weight=1.0
    - week: role="primary", weight=0.9
    - month: role="primary", weight=0.75
    - longterm: role="longterm", weight=0.65

    For extra spaces, includes only longterm:
    - longterm: role="secondary", weight=0.4

    Groups are ordered: primary day -> primary week -> primary month ->
    primary longterm -> extra longterms...

    Args:
        primary_space: The primary memory space to retrieve from.
        extra_spaces: Optional list of additional spaces (only longterm included).
        dt: Datetime or ISO string for time-based scopes. Defaults to current UTC.

    Returns:
        A RetrievalPlan with configured memory group references.
    """
    groups: list[MemoryGroupRef] = []

    # Primary space groups in order: day, week, month, longterm
    groups.append(
        MemoryGroupRef(
            group_id=make_day_scope(primary_space, dt).graph_id,
            role="primary",
            weight=1.0,
        )
    )
    groups.append(
        MemoryGroupRef(
            group_id=make_week_scope(primary_space, dt).graph_id,
            role="primary",
            weight=0.9,
        )
    )
    groups.append(
        MemoryGroupRef(
            group_id=make_month_scope(primary_space, dt).graph_id,
            role="primary",
            weight=0.75,
        )
    )
    groups.append(
        MemoryGroupRef(
            group_id=make_longterm_scope(primary_space).graph_id,
            role="longterm",
            weight=0.65,
        )
    )

    # Extra spaces: only longterm, role=secondary
    if extra_spaces:
        for space in extra_spaces:
            groups.append(
                MemoryGroupRef(
                    group_id=make_longterm_scope(space).graph_id,
                    role="secondary",
                    weight=0.4,
                )
            )

    return RetrievalPlan(primary_space=primary_space, groups=groups)
