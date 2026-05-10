"""Memory spaces for Jasmine v2 memory system."""

import re
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class MemorySpace:
    """Represents a memory space with type and ID."""

    space_type: Literal["chat", "user", "family", "project", "custom", "system"]
    space_id: str

    @property
    def key(self) -> str:
        """Return the full key in format 'space_type:space_id'."""
        return f"{self.space_type}:{self.space_id}"


def sanitize_space_id(value: str) -> str:
    """
    Sanitize a space ID according to the rules:
    - lowercase
    - strip whitespace
    - spaces -> "_"
    - ":" -> "_"
    - "/", "\", "#", "?", "&", "=" -> "_"
    - all non-letter/digit/_/- characters -> "_"
    - multiple "_" in a row -> single "_"
    - trim "_" from start/end
    - if empty after cleaning -> "unknown"
    """
    # lowercase and strip
    result = value.lower().strip()

    # replace specific characters with "_"
    result = result.replace(" ", "_")
    result = result.replace(":", "_")
    result = result.replace("/", "_")
    result = result.replace("\\", "_")
    result = result.replace("#", "_")
    result = result.replace("?", "_")
    result = result.replace("&", "_")
    result = result.replace("=", "_")

    # all non-letter/digit/_/- characters -> "_"
    result = re.sub(r"[^a-z0-9_-]", "_", result)

    # multiple "_" in a row -> single "_"
    result = re.sub(r"_+", "_", result)

    # trim "_" from start/end
    result = result.strip("_")

    # if empty after cleaning -> "unknown"
    if not result:
        return "unknown"

    return result


def make_chat_space(chat_key: str) -> MemorySpace:
    """Create a chat memory space."""
    return MemorySpace(space_type="chat", space_id=sanitize_space_id(chat_key))


def make_user_space(user_key: str) -> MemorySpace:
    """Create a user memory space."""
    return MemorySpace(space_type="user", space_id=sanitize_space_id(user_key))


def make_family_space(family_key: str = "main") -> MemorySpace:
    """Create a family memory space."""
    return MemorySpace(space_type="family", space_id=sanitize_space_id(family_key))


def make_project_space(project_key: str) -> MemorySpace:
    """Create a project memory space."""
    return MemorySpace(space_type="project", space_id=sanitize_space_id(project_key))


def make_custom_space(custom_key: str) -> MemorySpace:
    """Create a custom memory space."""
    return MemorySpace(space_type="custom", space_id=sanitize_space_id(custom_key))


def make_system_space(system_key: str = "jasmine") -> MemorySpace:
    """Create a system memory space."""
    return MemorySpace(space_type="system", space_id=sanitize_space_id(system_key))
