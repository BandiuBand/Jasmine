# Jasmine v2 Memory DB Contract

## Backend

Jasmine v2 uses the external local service `graphiti-local-memory`.

Default URL:

`http://127.0.0.1:8088`

The service is a FastAPI wrapper around `graphiti-core`, backed by Neo4j, and supports group-scoped memory through Graphiti `group_id`.

## Required API

Jasmine v2 depends on:

- `GET /health`
- `GET /config`
- `POST /episodes`
- `POST /search`
- `GET /episodes`
- `GET /groups/{group_id}/stats`

## Memory group format

Every Jasmine v2 memory graph is mapped to one Graphiti `group_id`.

Format:

`jv2:{space_type}:{space_id}:{time_level}:{time_id}`

Allowed `space_type`:

- `chat`
- `user`
- `family`
- `project`
- `custom`
- `system`

Allowed `time_level`:

- `day`
- `week`
- `month`
- `longterm`

`time_id` formats:

- day: `YYYY-MM-DD`
- week: `YYYY-Www`
- month: `YYYY-MM`
- longterm: `all`

## Isolation

All Jasmine v2 groups must start with `jv2:`.

Jasmine v2 must not write to legacy groups like `family`.

## Raw message ingestion

Raw messages are written only to the current day group of the primary memory space.

Example:

`jv2:chat:telegram_family_main:day:2026-05-10`

Raw messages must not be written directly to week/month/longterm groups.

## Retrieval

Default retrieval for active context uses:

1. current day group
2. current week group
3. current month group
4. longterm group

For a primary space `chat:telegram_family_main` on `2026-05-10`:

- `jv2:chat:telegram_family_main:day:2026-05-10`
- `jv2:chat:telegram_family_main:week:2026-W19`
- `jv2:chat:telegram_family_main:month:2026-05`
- `jv2:chat:telegram_family_main:longterm:all`

## Episode write request

Jasmine v2 writes through `POST /episodes`.

Payload:

```json
{
  "name": "telegram_message_123",
  "body": "structured episode text",
  "source_description": "Jasmine v2 Telegram day memory",
  "group_id": "jv2:chat:telegram_family_main:day:2026-05-10",
  "reference_time": "2026-05-10T14:22:00+00:00"
}