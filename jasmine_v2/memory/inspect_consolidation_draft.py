"""CLI debug tool for inspecting Jasmine v2 memory consolidation draft.

Usage:
    python -m jasmine_v2.memory.inspect_consolidation_draft \
        --group-id jv2-chat-telegram_private_627630958-day-2026-05-11

    python -m jasmine_v2.memory.inspect_consolidation_draft \
        --space chat:telegram_private_627630958 \
        --date 2026-05-11
"""

import argparse
import sys

from jasmine_v2.memory.graph_scope import make_day_scope
from jasmine_v2.memory.graphiti_http_client import GraphitiHttpClient
from jasmine_v2.memory.spaces import MemorySpace


def parse_space(space_str: str) -> MemorySpace:
    """Parse a space string like 'chat:telegram_private_627630958' into MemorySpace."""
    if ":" not in space_str:
        raise ValueError(f"Space must be in format 'type:id', got: {space_str!r}")
    space_type, space_id = space_str.split(":", 1)
    return MemorySpace(space_type=space_type, space_id=space_id)


def resolve_group_id(
    group_id: str | None = None,
    space_str: str | None = None,
    date_str: str | None = None,
) -> str:
    """Resolve the group_id from direct input or space+date."""
    if group_id:
        return group_id

    if space_str:
        space = parse_space(space_str)
        return make_day_scope(space, date_str).graph_id

    raise ValueError("Either --group-id or --space must be provided.")


def format_text(text: str | None, max_chars: int) -> str:
    """Format text, truncating if necessary."""
    if text is None:
        return "(no text)"
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"... [truncated, total chars: {len(text)}]"


def inspect_consolidation_draft(
    group_id: str | None = None,
    space_str: str | None = None,
    date_str: str | None = None,
    episode_limit: int = 500,
    entity_limit: int = 500,
    edge_limit: int = 500,
    include_raw_episodes: bool = True,
    mode: str = "raw_to_summary",
    max_output_chars: int = 8000,
    include_snapshot_draft: bool = False,
    max_chars: int = 6000,
    client: GraphitiHttpClient | None = None,
) -> str:
    """Inspect consolidation draft and return formatted output string."""
    resolved_group_id = resolve_group_id(group_id, space_str, date_str)
    client = client or GraphitiHttpClient()

    result = client.consolidation_draft(
        resolved_group_id,
        mode=mode,
        episode_limit=episode_limit,
        entity_limit=entity_limit,
        edge_limit=edge_limit,
        include_raw_episodes=include_raw_episodes,
        max_output_chars=max_output_chars,
        include_snapshot_draft=include_snapshot_draft,
    )

    counts = result.get("counts", {})
    source = result.get("source", {})
    consolidation_text = result.get("consolidation_text", "")
    model = result.get("model", "n/a")
    draft_text = result.get("draft_text")

    lines = [
        f"group_id: {resolved_group_id}",
        f"mode: {mode}",
        f"model: {model}",
        "",
        "counts:",
        f"  episodes: {counts.get('episodes', 0)}",
        f"  entities: {counts.get('entities', 0)}",
        f"  edges: {counts.get('edges', 0)}",
        f"  mentions: {counts.get('mentions', 0)}",
        "",
        "source counts:",
        f"  episodes: {source.get('episodes', 0)}",
        f"  entities: {source.get('entities', 0)}",
        f"  edges: {source.get('edges', 0)}",
        f"  mentions: {source.get('mentions', 0)}",
        "",
        "consolidation_text:",
        format_text(consolidation_text, max_chars),
    ]

    if draft_text is not None:
        lines.append("")
        lines.append("snapshot_draft_text preview:")
        lines.append(format_text(draft_text, max_chars))

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Inspect Jasmine v2 memory consolidation draft")
    parser.add_argument(
        "--group-id",
        default=None,
        help="Group ID to inspect, e.g. jv2-chat-telegram_private_627630958-day-2026-05-11",
    )
    parser.add_argument(
        "--space",
        default=None,
        help='Memory space in format "type:id", e.g. chat:telegram_private_627630958',
    )
    parser.add_argument(
        "--date",
        default=None,
        help="Date in YYYY-MM-DD format. Defaults to today UTC.",
    )
    parser.add_argument(
        "--episode-limit",
        type=int,
        default=500,
        help="Maximum number of episodes to include. Default is 500.",
    )
    parser.add_argument(
        "--entity-limit",
        type=int,
        default=500,
        help="Maximum number of entities to include. Default is 500.",
    )
    parser.add_argument(
        "--edge-limit",
        type=int,
        default=500,
        help="Maximum number of edges to include. Default is 500.",
    )
    parser.add_argument(
        "--no-raw-episodes",
        action="store_true",
        help="Exclude raw episode content from consolidation.",
    )
    parser.add_argument(
        "--mode",
        default="raw_to_summary",
        help='Consolidation mode. Only "raw_to_summary" is supported. Default is raw_to_summary.',
    )
    parser.add_argument(
        "--include-snapshot-draft",
        action="store_true",
        help="Include snapshot draft text in response. Default is False.",
    )
    parser.add_argument(
        "--max-output-chars",
        type=int,
        default=8000,
        help="Maximum output characters for consolidation_text. Default is 8000.",
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        default=6000,
        help="Maximum characters of consolidation_text to display. Default is 6000.",
    )

    args = parser.parse_args(argv)

    if not args.group_id and not args.space:
        print("Error: Either --group-id or --space must be provided.", file=sys.stderr)
        parser.print_usage(sys.stderr)
        return 2

    if args.mode != "raw_to_summary":
        print("Error: mode must be 'raw_to_summary'", file=sys.stderr)
        return 2

    try:
        output = inspect_consolidation_draft(
            group_id=args.group_id,
            space_str=args.space,
            date_str=args.date,
            episode_limit=args.episode_limit,
            entity_limit=args.entity_limit,
            edge_limit=args.edge_limit,
            include_raw_episodes=not args.no_raw_episodes,
            mode=args.mode,
            max_output_chars=args.max_output_chars,
            include_snapshot_draft=args.include_snapshot_draft,
            max_chars=args.max_chars,
        )
        print(output)
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
