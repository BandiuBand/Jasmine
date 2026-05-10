# Graphiti memory integration

WasterWhisper now uses the local Graphiti memory service through HTTP, not by importing `graphiti-core` into the bot process.

## Why HTTP service

LM Studio can hold only one useful model at a time on this machine. The bot should keep LM Studio available for the main Jasmine response model. Graphiti service should run in service mode on Ollama plus a local embedder fallback.

Recommended Graphiti service config:

```dotenv
GRAPHITI_LLM_PROVIDER=ollama
GRAPHITI_LLM_BASE_URL=http://127.0.0.1:11434/v1
GRAPHITI_LLM_API_KEY=ollama
GRAPHITI_LLM_MODEL=qwen3.5-local:4b
GRAPHITI_SMALL_MODEL=qwen3.5-local:4b
GRAPHITI_EMBEDDER_BASE_URL=local://hash
GRAPHITI_EMBEDDER_API_KEY=local
GRAPHITI_EMBEDDER_MODEL=local-hash-embedder
GRAPHITI_EMBEDDING_DIM=768
```

This avoids loading a second LM Studio model for Graphiti.

## Start order

```bash
cd ~/PycharmProjects/WasterWhisper
python start_all.py
```

`start_all.py` checks `graphiti_memory.url + /health` before starting bot services. If Graphiti is
down and `graphiti_memory.auto_start_service=true`, it runs:

```bash
~/PycharmProjects/graphiti-local-memory/scripts/run_api.sh
```

The Graphiti run script also starts the `neo4j` Docker container if needed.

For manual Graphiti-only work:

```bash
cd ~/PycharmProjects/WasterWhisper
python graphiti_backfill.py --dry-run
python graphiti_backfill.py --mode queue
python jasmine_filter.py --process
python graphiti_ingest_worker.py --once
```

For long-running mode:

```bash
python jasmine_filter.py --watch
python graphiti_ingest_worker.py --watch --interval 30
```

## Runtime behavior

- Every new processed chat message is queued in `logs/graphiti_ingest_queue.jsonl` if `graphiti_memory.ingest_episodes=true`.
- `graphiti_ingest_worker.py` sends queued messages to Graphiti as episodes. This prevents the Telegram bot from blocking while Graphiti performs LLM extraction.
- `graphiti_backfill.py` imports existing `logs/YYYY/MM/DD/*.txt` history with sender nicknames and ISO timestamps.
- RAG context is fetched from `POST /search` if `graphiti_memory.use_for_rag=true`.
- If Graphiti is down or busy, the old JSON KG path remains as fallback when `fallback_to_legacy_kg=true`.

Config lives in `config.json` under `jasmine_filter.graphiti_memory`.

Service autostart config:

```json
"graphiti_memory": {
  "enabled": true,
  "url": "http://127.0.0.1:8088",
  "auto_start_service": true,
  "service_dir": "/home/bandiu/PycharmProjects/graphiti-local-memory",
  "startup_timeout_seconds": 90
}
```

## LM Studio Loaded-Model Fallback

`jasmine_filter.py` keeps LM Studio as the main response provider, but LM Studio can hold only one model. If the configured model fails to load, Jasmine now checks:

```text
GET <lm_studio_root>/api/v0/models
```

and temporarily uses the model whose `state` is `loaded`, ignoring embedding models.

Config:

```json
"lm_studio": {
  "url": "http://127.0.0.1:1234/v1/chat/completions",
  "model": "google/gemma-4-26b-a4b",
  "use_loaded_model_fallback": true
}
```

If the loaded model also fails, the existing Ollama fallback is used.

## Response Decision Logic

- Private chats: Jasmine answers without requiring the name "Жасмін".
- Group chats: explicit name still answers immediately, but non-explicit messages are evaluated by a local Ollama decision prompt using recent chat context plus Graphiti memory.
- If the decision model times out, question-like messages with enough contextual score still answer as a conservative fallback.
- New bot logs include chat type: `[text] [private] [sender] ...` or `[text] [group] [sender] ...`; old logs remain supported.

## Backfill Existing History

Preview:

```bash
python graphiti_backfill.py --dry-run
python graphiti_backfill.py --dry-run --chat "Сімейство інтелектуалів"
```

Queue all parsed history without blocking on LLM extraction:

```bash
python graphiti_backfill.py --mode queue
python graphiti_ingest_worker.py --watch --interval 30 --limit 5
```

Direct API mode is available but slower and will block on Graphiti extraction:

```bash
python graphiti_backfill.py --mode api --limit 10
```

Resume state is stored in `logs/graphiti_backfill_state.json`.
