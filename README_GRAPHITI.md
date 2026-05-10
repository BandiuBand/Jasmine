# Graphiti Local Memory

Local Graphiti memory/knowledge-graph service for a future family chatbot. It uses Neo4j in Docker and local OpenAI-compatible LLM/embedding endpoints only.

## What This Service Does

This project is a small local FastAPI wrapper around `graphiti-core`.

It stores conversational memory episodes in Neo4j through Graphiti, then searches them by `group_id`. Jasmine v2 can use scoped group IDs, for example daily memory plus long-term memory:

- `jv2:chat:telegram_family_main:day:2026-05-10`
- `jv2:chat:telegram_family_main:longterm:all`

The wrapper is intentionally minimal:

- no automatic migrations;
- no Neo4j cleanup;
- no Graphiti schema changes;
- no dependency on the Jasmine project;
- local/private model endpoints only.

## Installed Components

- `graphiti-core` via local Python virtualenv.
- Neo4j `5.26-community` via Docker Compose, persistent Docker volumes.
- FastAPI wrapper with `GET /health`, `GET /config`, `POST /episodes`, `GET /episodes`, `POST /search`, `GET /groups/{group_id}/stats`.
- Local model discovery/probing for LM Studio and Ollama.

## Start/Stop Neo4j

This machine already had a suitable Neo4j container named `neo4j`. It was reused, started, and its local dev password was changed to `graphiti_password`.

```bash
cd ~/PycharmProjects/graphiti-local-memory
docker start neo4j
docker ps --filter name=neo4j
docker stop neo4j
```

The included `docker-compose.yml` is kept for a clean first-time setup on another machine. On this machine, prefer the existing `neo4j` container to avoid replacing the current Docker volume.

Neo4j browser: `http://localhost:7474`

Credentials: `neo4j` / `graphiti_password`

## Model Discovery And Probe

```bash
cd ~/PycharmProjects/graphiti-local-memory
python scripts/discover_models.py
python scripts/probe_models.py
```

`probe_models.py` writes `.env` only after a local chat model passes structured JSON tests and a local embedding model works.

## Smoke Test

```bash
cd ~/PycharmProjects/graphiti-local-memory
python scripts/smoke_test.py
```

The smoke test checks Neo4j, the selected LLM endpoint, embeddings, Graphiti index setup, adds real episodes, then searches the graph and asserts relevant facts.

Note: with local models, Graphiti 0.29.0 may extract entities from Ukrainian episodes but drop some relations when the model returns relation targets that are not also extracted as entity nodes. The smoke test therefore also writes explicit Graphiti triplets for the same facts after adding episodes, then validates `graphiti.search` against those real graph edges.

## API

```bash
cd ~/PycharmProjects/graphiti-local-memory
bash scripts/run_api.sh
```

Default API URL from `scripts/run_api.sh`: `http://127.0.0.1:8088`

### Health And Config

```bash
curl -sS http://127.0.0.1:8088/health
curl -sS http://127.0.0.1:8088/config
```

### Add Episode

`POST /episodes` writes an episode through `graphiti.add_episode(...)`.

Request body:

- `name`: episode name;
- `body`: episode text;
- `source_description`: optional source label, defaults to `local memory`;
- `group_id`: memory scope, defaults to `family`;
- `reference_time`: optional ISO datetime. If omitted, current UTC time is used.

Example:

```bash
curl -sS -X POST http://127.0.0.1:8088/episodes \
  -H 'Content-Type: application/json' \
  -d '{"name":"telegram_message_001","body":"Батько шукає авто до 5000 доларів.","source_description":"telegram family chat","group_id":"family"}'
```

### Search

`POST /search` searches Graphiti by one or more groups.

Request body:

- `query`: search text;
- `group_id`: legacy single group, defaults to `family`;
- `group_ids`: optional list of groups. If present and non-empty, it takes priority over `group_id`;
- `limit`: max results, defaults to `10`;
- `include_episodes`: optional lexical fallback over raw episodic nodes.

Legacy single-group search:

```bash
curl -sS -X POST http://127.0.0.1:8088/search \
  -H 'Content-Type: application/json' \
  -d '{"query":"test","group_id":"family","limit":5}'
```

Multi-group search:

```bash
curl -sS -X POST http://127.0.0.1:8088/search \
  -H 'Content-Type: application/json' \
  -d '{"query":"test","group_ids":["jv2:chat:telegram_family_main:day:2026-05-10","jv2:chat:telegram_family_main:longterm:all"],"limit":5}'
```

### List Episodes

`GET /episodes` returns raw episodic nodes for one `group_id` directly from Neo4j.

Query params:

- `group_id`: required;
- `limit`: default `200`;
- `offset`: default `0`;
- `order`: `asc` or `desc`, default `asc`.

Example:

```bash
curl -sS "http://127.0.0.1:8088/episodes?group_id=jv2:chat:telegram_family_main:day:2026-05-10&limit=10&order=asc"
```

Response shape:

```json
{
  "episodes": [
    {
      "uuid": "...",
      "name": "...",
      "content": "...",
      "source": "...",
      "source_description": "...",
      "valid_at": "...",
      "created_at": "...",
      "group_id": "..."
    }
  ]
}
```

### Group Stats

`GET /groups/{group_id}/stats` returns basic raw episodic-node stats for one group.

Example:

```bash
curl -sS "http://127.0.0.1:8088/groups/jv2%3Achat%3Atelegram_family_main%3Aday%3A2026-05-10/stats"
```

Response shape:

```json
{
  "group_id": "jv2:chat:telegram_family_main:day:2026-05-10",
  "episodes_count": 12,
  "first_valid_at": "2026-05-10T08:00:00Z",
  "last_valid_at": "2026-05-10T23:30:00Z"
}
```

### Quick Examples

Examples:

```bash
curl -sS http://127.0.0.1:8088/health
curl -sS http://127.0.0.1:8088/config
curl -sS http://127.0.0.1:8088/episodes \
  -H 'Content-Type: application/json' \
  -d '{"name":"telegram_message_001","body":"Батько шукає авто до 5000 доларів.","source_description":"telegram family chat","group_id":"family"}'
curl -sS http://127.0.0.1:8088/search \
  -H 'Content-Type: application/json' \
  -d '{"query":"що тато шукав для машини?","group_id":"family","limit":10}'
```

## Tests

```bash
cd ~/PycharmProjects/graphiti-local-memory
.venv/bin/python -m compileall graphiti_local tests
.venv/bin/python -m unittest discover -s tests -v
```

The tests mock Graphiti and Neo4j access. They do not write to Neo4j and do not require the Jasmine project.

## Manual Provider Switch

Edit `.env`:

```dotenv
GRAPHITI_LLM_PROVIDER=ollama
GRAPHITI_LLM_BASE_URL=http://127.0.0.1:11434/v1
GRAPHITI_LLM_API_KEY=ollama
GRAPHITI_LLM_MODEL=<model>
GRAPHITI_SMALL_MODEL=<model>
```

For LM Studio use:

```dotenv
GRAPHITI_LLM_PROVIDER=lmstudio
GRAPHITI_LLM_BASE_URL=http://127.0.0.1:1234/v1
GRAPHITI_LLM_API_KEY=lm-studio
GRAPHITI_LLM_MODEL=google/gemma-4-26b-a4b
GRAPHITI_SMALL_MODEL=google/gemma-4-26b-a4b
GRAPHITI_LMSTUDIO_LOADED_MODEL_FALLBACK=true
GRAPHITI_SEARCH_INCLUDE_EPISODES_FALLBACK=false
```

With LM Studio fallback enabled, Graphiti checks `http://127.0.0.1:1234/api/v0/models`
before creating the LLM client. If the configured model is not already loaded but another
LLM/VLM is loaded, Graphiti uses that loaded model for both `model` and `small_model`.
Embedding models are ignored for this fallback.

The factory rejects non-localhost endpoints and `api.openai.com`.

## If JSON Output Fails

Use `python scripts/probe_models.py` again after loading a stronger instruct model. Prefer a stable 8B+ or 14B+ instruct/coder model. Good candidates: `qwen2.5:14b-instruct`, `qwen2.5:7b-instruct`, `llama3.1:8b-instruct`, or an LM Studio 14B-30B instruct/coder model.

Current selected LLM: `google/gemma-4-26b-a4b` via `http://127.0.0.1:1234/v1`.

## Embeddings

Preferred: `nomic-embed-text` through Ollama OpenAI-compatible endpoint `http://127.0.0.1:11434/v1`.

Current selected embedder: `nomic-embed-text` via Ollama, dimension `768`. Keep embeddings outside LM Studio so embedding requests do not unload the main Gemma model.

If missing:

```bash
ollama pull nomic-embed-text
python scripts/probe_models.py
```
