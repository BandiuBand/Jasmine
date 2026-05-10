# WasterWhisper 1.x — Architecture Documentation

**Branch:** `legacy-1.x`  
**Status:** Stable, frozen for 2.0 development  
**Last updated:** 2026-05-10

---

## Overview

WasterWhisper is a Ukrainian-speaking family chatbot "Жасмін" (Jasmine) with:
- Speech-to-text (Whisper)
- Local LLM inference (LM Studio primary, Ollama fallback)
- Knowledge Graph memory (Graphiti)
- Free web search (DuckDuckGo + Wikipedia)
- Text-to-speech (Ukrainian TTS)

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           Telegram API                                  │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                            bot.py                                       │
│  - Receives messages from Telegram                                      │
│  - Sends text/voice responses                                           │
│  - CLI: --send <chat_id> <message>                                      │
│  - HTTPXRequest with custom timeouts (30s read/write)                 │
│  - Retry with exponential backoff (3 attempts)                          │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        start_all.py (orchestrator)                      │
│  - Launches all services in correct order                               │
│  - Manages subprocesses: bot, whisper server, admin, kg_watch,         │
│    jasmine_filter, graphiti_service, graphiti_worker, kg_cleanup      │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
        ▼                           ▼                           ▼
┌───────────────┐        ┌─────────────────┐        ┌──────────────────┐
│  kg_watch.py  │        │ jasmine_filter.py│        │ whisper server  │
│  (KG monitor) │        │  (core logic)    │        │  (faster-whisper)│
└───────────────┘        └─────────────────┘        └──────────────────┘
                                │
                ┌───────────────┼───────────────┐
                │               │               │
                ▼               ▼               ▼
        ┌───────────┐   ┌──────────┐   ┌──────────────┐
        │  Ollama   │   │ LM Studio│   │  Graphiti    │
        │  (fallback)│   │ (primary)│   │  (memory)    │
        │  :11434   │   │  :1234   │   │   :8088      │
        └───────────┘   └──────────┘   └──────────────┘
```

---

## Core Components

### 1. bot.py
**Purpose:** Telegram bot interface  
**Key features:**
- Voice message transcription via Whisper server
- Text/voice response sending
- CLI mode for jasmine_filter integration (`--send`)
- Custom HTTPXRequest timeouts to prevent "Timed out" errors
- Retry mechanism with exponential backoff

**Dependencies:** `python-telegram-bot`, `HTTPXRequest`

---

### 2. jasmine_filter.py
**Purpose:** Message filtering, classification, and LLM response generation  
**Key features:**
- **Message classification:** Determines if message needs Jasmine's response
- **LLM fallback chain:**
  1. Primary LM Studio model (configurable)
  2. Any currently loaded LM Studio model
  3. Ollama fallback (phi4-mini or configurable)
- **RAG (Retrieval-Augmented Generation):**
  - Graphiti memory search (primary)
  - Legacy Knowledge Graph fallback
- **Web search integration:**
  - Auto-triggered by keywords
  - DuckDuckGo + Wikipedia (free, no API keys)
  - Results injected into LLM prompt with source URLs
- **Anti-hallucination measures:**
  - Stop sequences: `\n[20`, `\n[BandiuB`, `\n[ЮРІЙ`, `\n[Жасмін]:`
  - Critical format rules in system prompt
  - Message chunking for Telegram 4096 char limit

**Key functions:**
- `send_to_lm_studio()` — Main response generation
- `get_rag_context()` — Graphiti/KG context retrieval
- `get_web_search_context()` — Web search trigger & results
- `should_answer()` — Classification logic

---

### 3. web_search.py
**Purpose:** Free web search without API keys  
**Sources:**
- **DuckDuckGo:** Primary via `ddgs` library, HTTP fallback
- **Wikipedia:** REST API (uk → en fallback)

**Trigger keywords:**
- Web: `пошукай`, `знайди`, `новини`, `погода`, `що сталося`, `доступ до інтернету`...
- Wiki: `хто такий`, `що таке`, `столиця`, `біографія`...

**Auto-detection:** `should_search(text)` returns `'web'`, `'wiki'`, or `None`

---

### 4. kg/graphiti_client.py
**Purpose:** HTTP client for Graphiti memory service  
**Operations:**
- `add_episode()` — Store conversation context
- `search()` — Semantic search with embeddings
- `ingest_mode`: "queue" (async via worker) or "direct"

---

### 5. graphiti_ingest_worker.py
**Purpose:** Background worker for Graphiti episode ingestion  
**Features:**
- Processes queue in batches (default 20 items)
- Dead-letter queue for failed items (max 3 failures)
- JSONL queue persistence

---

### 6. start_all.py
**Purpose:** Service orchestrator  
**Launches:**
1. Whisper server (port 8005)
2. Telegram bot
3. Admin interface (port 8001)
4. Knowledge Graph watcher (optional)
5. Jasmine filter (optional)
6. Graphiti service auto-start (optional)
7. Graphiti ingest worker (optional)
8. KG cleanup (optional)

---

## Configuration (config.json)

### jasmine_filter section
```json
{
  "enabled": true,
  "check_interval_seconds": 30,
  "last_n_messages": 50,
  "ollama": {
    "url": "http://127.0.0.1:11434/api/chat",
    "model": "qwen3.5-local:4b",
    "fallback_model": "phi4-mini:latest"
  },
  "lm_studio": {
    "url": "http://127.0.0.1:1234/v1/chat/completions",
    "model": "google/gemma-4-26b-a4b",
    "use_loaded_model_fallback": true
  },
  "web_search": {
    "enabled": true,
    "mode": "auto",
    "source": "auto",
    "max_results": 5,
    "max_context_chars": 2000
  },
  "graphiti_memory": {
    "enabled": true,
    "url": "http://127.0.0.1:8088",
    "auto_start_service": true,
    "service_dir": "/home/bandiu/PycharmProjects/graphiti-local-memory",
    "startup_timeout_seconds": 90,
    "timeout_seconds": 120,
    "max_results": 5,
    "ingest_episodes": true,
    "ingest_mode": "queue",
    "queue_path": "logs/graphiti_ingest_queue.jsonl",
    "dead_letter_path": "logs/graphiti_ingest_dead_letter.jsonl",
    "max_ingest_failures": 3,
    "use_for_rag": true,
    "fallback_to_legacy_kg": true
  }
}
```

---

## External Services

| Service | Port | Purpose | Fallback |
|---------|------|---------|----------|
| LM Studio | 1234 | Primary LLM | Loaded model → Ollama |
| Ollama | 11434 | Fallback LLM + Embeddings | None |
| Graphiti | 8088 | Memory/RAG | Legacy KG |
| Whisper | 8005 | STT | — |
| Admin | 8001 | Web admin | — |

---

## Data Flow

### Message Processing
```
Telegram → bot.py → logs/chat_*.log
                           ↓
                    jasmine_filter.py (polls logs)
                           ↓
              ┌────────────┼────────────┐
              ↓            ↓            ↓
       classification   RAG context   Web search
              ↓            ↓            ↓
              └────────────┼────────────┘
                           ↓
                   LM Studio / Ollama
                           ↓
                   Response generation
                           ↓
              ┌────────────┼────────────┐
              ↓            ↓            ↓
       Graphiti store   Telegram send   TTS (optional)
```

---

## Known Limitations (1.x)

1. **LM Studio model loading:** JIT loading can cause "Operation canceled" errors under load
2. **Embedding model:** Must be manually loaded in LM Studio or use Ollama
3. **Graphiti startup:** Service auto-start can fail if port 8088 is busy
4. **Telegram timeouts:** Network issues require retry logic (implemented in 1.x final)
5. **Context window:** Large RAG + web search context can exceed model limits

---

## Version History

| Commit | Description |
|--------|-------------|
| `9bcebc7` | Graphiti dead-letter queue, LM Studio LLM + Ollama embeddings |
| `c33d3df` | Telegram retry logic, anti-hallucination prompts |
| `5eba7eb` | Free web search (DuckDuckGo + Wikipedia) |
| `1531a81` | Graphiti memory integration |

---

## Migration to 2.0

This branch (`legacy-1.x`) is frozen. All 2.0 development happens on `master` or `dev-2.0`.

**Before 2.0:**
- [x] Create legacy-1.x branch
- [x] Document architecture
- [x] Verify bot starts
- [ ] Merge to master for 2.0 baseline

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set environment
export BOT_TOKEN="your_token"
# or create tockenBot.txt

# 3. Start all services
python start_all.py

# 4. Or start individually:
python bot.py                    # Telegram bot
python server.py                 # Whisper server
python jasmine_filter.py         # Filter only
```

---

## Authors & License

Maintained by BandiuBand.  
Internal family project — not for public distribution.
