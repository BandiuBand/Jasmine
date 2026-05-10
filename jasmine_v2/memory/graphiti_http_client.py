"""Graphiti Local Memory HTTP Client for Jasmine v2.

Provides a client to interact with the Graphiti local memory service via HTTP.
"""

import os
from datetime import datetime
from urllib.parse import quote

import requests


class GraphitiHttpClient:
    """HTTP client for Graphiti local memory service.

    Wraps the FastAPI service running at http://127.0.0.1:8088 (by default).
    """

    def __init__(self, base_url: str | None = None, timeout: float = 30.0):
        """Initialize the HTTP client.

        Args:
            base_url: Base URL for the Graphiti service. If not provided,
                     uses GRAPHITI_LOCAL_MEMORY_URL env var or default.
            timeout: Request timeout in seconds. Default is 30.0.
        """
        if base_url is None:
            base_url = os.environ.get(
                "GRAPHITI_LOCAL_MEMORY_URL",
                "http://127.0.0.1:8088"
            )

        # Remove trailing slash
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def health(self) -> dict:
        """Check service health.

        Returns:
            Health status dict from the service.

        Raises:
            requests.HTTPError: If the request fails.
        """
        response = requests.get(
            f"{self.base_url}/health",
            timeout=self.timeout
        )
        response.raise_for_status()
        return response.json()

    def config(self) -> dict:
        """Get service configuration.

        Returns:
            Configuration dict from the service.

        Raises:
            requests.HTTPError: If the request fails.
        """
        response = requests.get(
            f"{self.base_url}/config",
            timeout=self.timeout
        )
        response.raise_for_status()
        return response.json()

    def add_episode(
        self,
        name: str,
        body: str,
        group_id: str,
        source_description: str = "Jasmine v2 memory",
        reference_time: datetime | None = None,
    ) -> dict:
        """Add an episode to a group.

        Args:
            name: Episode name/title.
            body: Episode content/body.
            group_id: Target group ID. Must start with "jv2:".
            source_description: Source description for the episode.
            reference_time: Optional reference datetime. Defaults to current time.

        Returns:
            Response dict from the service.

        Raises:
            ValueError: If group_id doesn't start with "jv2:".
            requests.HTTPError: If the request fails.
        """
        if not group_id.startswith("jv2:"):
            raise ValueError(
                f"group_id must start with 'jv2:', got: {group_id!r}"
            )

        payload = {
            "name": name,
            "body": body,
            "group_id": group_id,
            "source_description": source_description,
        }

        if reference_time is not None:
            payload["reference_time"] = reference_time.isoformat()

        response = requests.post(
            f"{self.base_url}/episodes",
            json=payload,
            timeout=self.timeout
        )
        response.raise_for_status()
        return response.json()

    def search(
        self,
        query: str,
        group_ids: list[str],
        limit: int = 10,
        include_episodes: bool = True,
    ) -> dict:
        """Search episodes across groups.

        Args:
            query: Search query string.
            group_ids: List of group IDs to search. Cannot be empty.
            limit: Maximum number of results. Default is 10.
            include_episodes: Whether to include episode content. Default is True.

        Returns:
            Search results dict from the service.

        Raises:
            ValueError: If group_ids is empty.
            requests.HTTPError: If the request fails.
        """
        if not group_ids:
            raise ValueError("group_ids cannot be empty")

        payload = {
            "query": query,
            "group_ids": group_ids,
            "limit": limit,
            "include_episodes": include_episodes,
        }

        response = requests.post(
            f"{self.base_url}/search",
            json=payload,
            timeout=self.timeout
        )
        response.raise_for_status()
        return response.json()

    def list_episodes(
        self,
        group_id: str,
        limit: int = 200,
        offset: int = 0,
        order: str = "asc",
    ) -> dict:
        """List episodes in a group.

        Args:
            group_id: Group ID to list episodes from. Cannot be empty.
            limit: Maximum number of episodes to return. Default is 200.
            offset: Offset for pagination. Default is 0.
            order: Sort order ("asc" or "desc"). Default is "asc".

        Returns:
            Episodes list dict from the service.

        Raises:
            ValueError: If group_id is empty.
            requests.HTTPError: If the request fails.
        """
        if not group_id:
            raise ValueError("group_id cannot be empty")

        params = {
            "group_id": group_id,
            "limit": limit,
            "offset": offset,
            "order": order,
        }

        response = requests.get(
            f"{self.base_url}/episodes",
            params=params,
            timeout=self.timeout
        )
        response.raise_for_status()
        return response.json()

    def group_stats(self, group_id: str) -> dict:
        """Get statistics for a group.

        Args:
            group_id: Group ID to get stats for. Cannot be empty.

        Returns:
            Group statistics dict from the service.

        Raises:
            ValueError: If group_id is empty.
            requests.HTTPError: If the request fails.
        """
        if not group_id:
            raise ValueError("group_id cannot be empty")

        # URL-encode the group_id (safe="" ensures special chars are encoded)
        encoded_group_id = quote(group_id, safe="")

        response = requests.get(
            f"{self.base_url}/groups/{encoded_group_id}/stats",
            timeout=self.timeout
        )
        response.raise_for_status()
        return response.json()
