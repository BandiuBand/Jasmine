"""Graphiti V2 Memory Adapter for Jasmine v2.

Provides GraphitiV2MemoryAdapter to encapsulate memory operations
using the Graphiti HTTP client.
"""

from datetime import datetime

from jasmine_v2.memory.graphiti_http_client import GraphitiHttpClient
from jasmine_v2.memory.graph_scope import make_day_scope
from jasmine_v2.memory.retrieval_plan import RetrievalPlan, build_default_retrieval_plan
from jasmine_v2.memory.spaces import MemorySpace


class GraphitiV2MemoryAdapter:
    """Adapter for Graphiti memory operations in Jasmine v2.

    Encapsulates episode formatting, day group management, and search
    operations using the Graphiti HTTP client.
    """

    def __init__(self, client: GraphitiHttpClient | None = None):
        """Initialize the adapter.

        Args:
            client: Graphiti HTTP client instance. If None, creates default client.
        """
        self.client = client or GraphitiHttpClient()

    def get_day_group_id(self, space: MemorySpace, dt: datetime | str | None = None) -> str:
        """Get the day group ID for a space and datetime.

        Args:
            space: The memory space.
            dt: Datetime or ISO string. Defaults to current UTC time.

        Returns:
            The day scope graph ID.
        """
        return make_day_scope(space, dt).graph_id

    def build_retrieval_plan(
        self,
        primary_space: MemorySpace,
        extra_spaces: list[MemorySpace] | None = None,
        dt: datetime | str | None = None,
    ) -> RetrievalPlan:
        """Build a default retrieval plan for the given spaces.

        Args:
            primary_space: The primary memory space to retrieve from.
            extra_spaces: Optional list of additional spaces.
            dt: Datetime or ISO string for time-based scopes.

        Returns:
            A RetrievalPlan with configured memory group references.
        """
        return build_default_retrieval_plan(primary_space, extra_spaces, dt)

    def format_message_episode(
        self,
        text: str,
        space: MemorySpace,
        group_id: str,
        access_scope: str,
        timestamp: str | None = None,
        source: str = "telegram",
        chat_id: str | None = None,
        message_id: str | None = None,
        sender_id: str | None = None,
        sender_name: str | None = None,
        metadata: dict | None = None,
    ) -> str:
        """Format a message episode as structured text.

        Args:
            text: The message text content.
            space: The memory space.
            group_id: The group ID for the episode.
            access_scope: The access scope identifier.
            timestamp: ISO timestamp string. Optional.
            source: Source identifier. Default is "telegram".
            chat_id: Chat identifier. Optional.
            message_id: Message identifier. Optional.
            sender_id: Sender identifier. Optional.
            sender_name: Sender display name. Optional.
            metadata: Additional metadata dict. Optional.

        Returns:
            Structured episode body text.
        """
        lines = [
            "Telegram message",
            f"access_scope: {access_scope}",
            f"memory_space: {space.key}",
            f"group_id: {group_id}",
        ]

        if timestamp:
            lines.append(f"timestamp: {timestamp}")

        lines.append(f"source: {source}")

        if chat_id:
            lines.append(f"chat_id: {chat_id}")
        if message_id:
            lines.append(f"message_id: {message_id}")
        if sender_id:
            lines.append(f"sender_id: {sender_id}")
        if sender_name:
            lines.append(f"sender_name: {sender_name}")

        if metadata:
            for key, value in metadata.items():
                lines.append(f"{key}: {value}")

        lines.append("")
        lines.append(f"Text:\n{text}")

        return "\n".join(lines)

    def add_day_message_episode(
        self,
        text: str,
        space: MemorySpace,
        access_scope: str,
        timestamp: str | None = None,
        source: str = "telegram",
        chat_id: str | None = None,
        message_id: str | None = None,
        sender_id: str | None = None,
        sender_name: str | None = None,
        metadata: dict | None = None,
    ) -> dict:
        """Add a message episode to the day group.

        Raw message ingestion is written only to the day group.

        Args:
            text: The message text content.
            space: The memory space.
            access_scope: The access scope identifier.
            timestamp: ISO timestamp string. Optional.
            source: Source identifier. Default is "telegram".
            chat_id: Chat identifier. Optional.
            message_id: Message identifier. Optional.
            sender_id: Sender identifier. Optional.
            sender_name: Sender display name. Optional.
            metadata: Additional metadata dict. Optional.

        Returns:
            Response dict from the client.add_episode call.
        """
        # Build day group_id
        group_id = self.get_day_group_id(space, timestamp)

        # Format the episode body
        body = self.format_message_episode(
            text=text,
            space=space,
            group_id=group_id,
            access_scope=access_scope,
            timestamp=timestamp,
            source=source,
            chat_id=chat_id,
            message_id=message_id,
            sender_id=sender_id,
            sender_name=sender_name,
            metadata=metadata,
        )

        # Build name
        if chat_id and message_id:
            name = f"telegram:{chat_id}:{message_id}"
        else:
            name = f"telegram:{space.key}:{timestamp or 'unknown'}"

        # Call client.add_episode
        return self.client.add_episode(
            name=name,
            body=body,
            group_id=group_id,
            source_description="Jasmine v2 day memory",
            reference_time=timestamp,
        )

    def search_context(
        self,
        plan: RetrievalPlan,
        query: str,
        limit: int = 10,
        include_episodes: bool = True,
    ) -> list[dict]:
        """Search for context using a retrieval plan.

        Args:
            plan: The retrieval plan with group IDs to search.
            query: Search query string.
            limit: Maximum number of results. Default is 10.
            include_episodes: Whether to include episode content. Default is True.

        Returns:
            Normalized list of search result dicts.
        """
        response = self.client.search(
            query=query,
            group_ids=plan.group_ids,
            limit=limit,
            include_episodes=include_episodes,
        )

        return self._normalize_search_response(response)

    def _normalize_search_response(self, response: dict | list) -> list[dict]:
        """Normalize various search response formats to a list of dicts.

        Handles:
        - response["results"] if list
        - response["facts"] if list
        - response["episodes"] if list
        - response as list
        - otherwise returns empty list

        Args:
            response: Raw response from search API.

        Returns:
            Normalized list of result dicts with standard fields.
        """
        items = []

        if isinstance(response, dict):
            if isinstance(response.get("results"), list):
                items = response["results"]
            elif isinstance(response.get("facts"), list):
                items = response["facts"]
            elif isinstance(response.get("episodes"), list):
                items = response["episodes"]
        elif isinstance(response, list):
            items = response

        # Normalize each item
        normalized = []
        for item in items:
            if not isinstance(item, dict):
                continue

            normalized_item = {
                "text": item.get("text", item.get("body", item.get("content", ""))),
                "source": "graphiti",
                "group_id": item.get("group_id", ""),
                "score": item.get("score", item.get("relevance", 0.0)),
                "metadata": item,
            }
            normalized.append(normalized_item)

        return normalized
