#!/usr/bin/env python3
"""
Jasmine Filter - фільтрує повідомлення для сімейного чат-бота Жасмін.

Використовує локальну Ollama для класифікації повідомлень:
- Чи це звернення до Жасмін
- Чи це питання, де може допомогти 20Б модель

Відфільтровані повідомлення направляються до "мізків Жасмін" (LM Studio на 3090).
"""

import argparse
import json
import os
import re
import sys
import time
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _BASE_DIR)
from kg.store import KnowledgeGraph
from kg.embeddings import get_embedding
from kg.graphiti_client import (
    GraphitiMemoryClient,
    append_episode_queue,
    format_graphiti_context,
    graphiti_group_id,
    message_reference_time,
)
from web_search import web_search, should_search, format_search_context
_CONFIG_FILE = os.path.join(_BASE_DIR, "config.json")
_LOGS_DIR = os.path.join(_BASE_DIR, "logs")
_PROCESSED_FILE = os.path.join(_BASE_DIR, "jasmine_processed.json")
_CONTEXT_STATE_FILE = os.path.join(_BASE_DIR, "jasmine_context_state.json")

# Matches old: [HH:MM:SS] [type] optional:[sender] text
# Matches new: [HH:MM:SS] [type] [private|group|supergroup|channel] optional:[sender] text
_LINE_RE = re.compile(
    r"^\[(\d{2}:\d{2}:\d{2})\]\s+\[(\w+)\](?:\s+\[([^\]]+)\])?(?:\s+\[([^\]]+)\])?\s+(.+)$"
)

_STOPWORDS = {
    "і", "й", "та", "або", "що", "це", "як", "для", "але", "бо", "чи", "не",
    "на", "в", "у", "з", "до", "по", "про", "за", "над", "під", "від", "при",
    "the", "a", "an", "to", "in", "of", "is", "are"
}

_GREETING_RE = re.compile(r"^(привіт|добр(ий|ого)|hello|hi|йо|салют)\b", re.IGNORECASE)


def load_processed_messages() -> set:
    """Завантажує набір ідентифікаторів оброблених повідомлень"""
    if os.path.exists(_PROCESSED_FILE):
        try:
            with open(_PROCESSED_FILE, encoding="utf-8") as f:
                return set(json.load(f))
        except Exception as e:
            print(f"[Jasmine] Error loading processed messages: {e}")
    return set()


def save_processed_messages(processed: set):
    """Зберігає набір ідентифікаторів оброблених повідомлень"""
    try:
        with open(_PROCESSED_FILE, "w", encoding="utf-8") as f:
            json.dump(list(processed), f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[Jasmine] Error saving processed messages: {e}")


def load_context_state() -> Dict:
    """Завантажує стан контексту розмов по чатах."""
    if os.path.exists(_CONTEXT_STATE_FILE):
        try:
            with open(_CONTEXT_STATE_FILE, encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception as e:
            print(f"[Jasmine] Error loading context state: {e}")
    return {"chats": {}}


def save_context_state(state: Dict):
    """Зберігає стан контексту розмов по чатах."""
    try:
        with open(_CONTEXT_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[Jasmine] Error saving context state: {e}")


def get_message_id(msg: Dict) -> str:
    """Генерує унікальний ідентифікатор для повідомлення"""
    # Використовуємо комбінацію chat_id, timestamp та тексту
    import hashlib
    key = f"{msg['chat_id']}_{msg['timestamp']}_{msg['text'][:100]}"
    return hashlib.md5(key.encode('utf-8')).hexdigest()


def load_config() -> dict:
    """Завантажує конфігурацію з config.json"""
    if os.path.exists(_CONFIG_FILE):
        with open(_CONFIG_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {
        "jasmine_filter": {
            "enabled": True,
            "check_interval_seconds": 30,
            "last_n_messages": 50,
            "ollama": {
                "url": "http://127.0.0.1:11434/api/chat",
                "model": "llama3.2:3b"
            },
            "lm_studio": {
                "url": "http://127.0.0.1:1234/v1/chat/completions",
                "model": "openai/gpt-oss-20b",
                "use_loaded_model_fallback": True
            },
            "tts_url": "http://127.0.0.1:8002/tts",
            "tts_enabled": False,
            "tts_voice": "Tetiana",
            "use_llm_tts": False,  # Використовувати ЛЛМ для розпізнавання TTS запитів
            "response_decision_timeout_seconds": 90,
            "bot_name": "Жасмін",
            "bot_name_variations": ["жасмін", "jasmine", "jasmine", "жасміна"],
            "graphiti_memory": {
                "enabled": True,
                "url": "http://127.0.0.1:8088",
                "timeout_seconds": 450,
                "max_results": 5,
                "ingest_episodes": True,
                "ingest_mode": "queue",
                "queue_path": "logs/graphiti_ingest_queue.jsonl",
                "use_for_rag": True,
                "fallback_to_legacy_kg": True,
                "source_description": "telegram family chat"
            }
        }
    }


def get_rag_context(text: str, chat_id: str, config: dict, max_results: int = 5) -> str:
    """
    Отримує релевантний контекст з Knowledge Graph через RAG.
    
    Args:
        text: текст повідомлення для пошуку
        chat_id: ідентифікатор чату
        config: конфігурація
        max_results: максимальна кількість результатів
        
    Returns:
        Рядок з контекстом з БЗ або порожній рядок
    """
    graphiti_config = config.get("jasmine_filter", {}).get("graphiti_memory", {})
    graphiti = GraphitiMemoryClient(graphiti_config)
    if graphiti.enabled and graphiti_config.get("use_for_rag", True):
        results = graphiti.search(
            text,
            group_id=graphiti_group_id(chat_id),
            limit=max_results or graphiti.max_results,
        )
        context = format_graphiti_context(results)
        if context:
            print(f"[Jasmine] Знайдено {len(results)} результатів у Graphiti")
            return context
        if not graphiti.fallback_to_legacy_kg:
            return ""

    try:
        # Отримуємо налаштування для embeddings
        embed_url = os.getenv("EMBED_URL", "http://127.0.0.1:1234/v1/embeddings")
        embed_model = os.getenv("EMBED_MODEL", "text-embedding-nomic-embed-text-v1.5")
        graph_path = os.path.join(_BASE_DIR, "kg", "graph.json")
        
        # Ініціалізуємо Knowledge Graph
        kg = KnowledgeGraph(graph_path, embed_url, embed_model)
        
        # Отримуємо ембедінг для запиту
        query_embedding = get_embedding(text, embed_url, embed_model)
        if not query_embedding:
            print("[Jasmine] Не вдалося отримати ембедінг для RAG")
            return ""
        
        # Отримуємо numeric chat_id для фільтрації
        numeric_chat_id = get_numeric_chat_id(chat_id)
        
        # Шукаємо релевантний контекст
        rag_results = kg.search_rag(
            query_embedding=query_embedding,
            chat_id=numeric_chat_id,
            min_similarity=0.70,
            max_results=max_results
        )
        
        if not rag_results:
            return ""
        
        # Формуємо контекстний рядок
        context_lines = []
        for result in rag_results:
            context_lines.append(
                f"- [{result['type'].upper()}] {result['value']} "
                f"(схожість: {result['similarity']:.2f}, згадок: {result['mentions']})"
            )
        
        context_str = "Контекст з бази знань:\n" + "\n".join(context_lines)
        print(f"[Jasmine] Знайдено {len(rag_results)} релевантних записів в БЗ")
        return context_str
        
    except Exception as e:
        print(f"[Jasmine] Помилка RAG: {e}")
        return ""


def get_web_search_context(text: str, config: dict, max_results: int = 5) -> str:
    """
    Виконує веб-пошук (DuckDuckGo + Wikipedia) якщо в тексті є тригери
    або якщо явно увімкнено в конфізі. Повертає форматований контекст для LLM.
    """
    ws_config = config.get("jasmine_filter", {}).get("web_search", {})
    if not ws_config.get("enabled", False):
        return ""

    mode = ws_config.get("mode", "auto")  # auto | always | off
    if mode == "off":
        return ""

    source = ws_config.get("source", "auto")  # auto | web | wiki | both
    limit = int(ws_config.get("max_results", max_results))
    max_chars = int(ws_config.get("max_context_chars", 2000))

    if mode == "auto":
        decision = should_search(text)
        if not decision:
            return ""
        if source == "auto":
            source = decision

    try:
        results = web_search(text, source=source, max_results=limit)
        ctx = format_search_context(results, max_chars=max_chars)
        if ctx:
            print(f"[Jasmine] 🌐 Веб-пошук: знайдено {len(results)} результатів (source={source})")
        return ctx
    except Exception as exc:
        print(f"[Jasmine] Web search error: {exc}")
        return ""


def add_message_to_graphiti(msg: Dict, config: dict, msg_id: str) -> bool:
    """Best-effort ingestion of a Telegram log message into Graphiti memory."""
    graphiti_config = config.get("jasmine_filter", {}).get("graphiti_memory", {})
    if not graphiti_config.get("enabled", False) or not graphiti_config.get("ingest_episodes", True):
        return False

    payload = {
        "name": f"{graphiti_group_id(msg.get('chat_id', 'unknown'))}_{msg_id}",
        "body": msg.get("text", ""),
        "group_id": graphiti_group_id(msg.get("chat_id", "unknown")),
        "sender": msg.get("sender", "unknown"),
        "reference_time": message_reference_time(msg),
    }

    if graphiti_config.get("ingest_mode", "queue") == "queue":
        queue_path = graphiti_config.get("queue_path", "logs/graphiti_ingest_queue.jsonl")
        if not os.path.isabs(queue_path):
            queue_path = os.path.join(_BASE_DIR, queue_path)
        append_episode_queue(queue_path, payload)
        return True

    graphiti = GraphitiMemoryClient(graphiti_config)
    return graphiti.add_episode(**payload)


def get_numeric_chat_id(chat_identifier: str) -> Optional[int]:
    """
    Отримує numeric Telegram chat_id з registry файлу.
    
    Args:
        chat_identifier: String identifier (filename without .txt)
    
    Returns:
        Numeric chat_id or None if not found
    """
    registry_file = os.path.join(_BASE_DIR, "logs", "chat_registry.json")
    if not os.path.exists(registry_file):
        return None
    
    try:
        with open(registry_file, encoding="utf-8") as f:
            registry = json.load(f)
        return registry.get(chat_identifier)
    except Exception as e:
        print(f"[Jasmine] Error reading registry: {e}")
        return None


def get_chat_kind(msg: Dict) -> str:
    """Return Telegram chat kind: private/group/supergroup/channel/unknown."""
    chat_type = (msg.get("chat_type") or "").lower()
    if chat_type:
        return chat_type

    numeric_chat_id = get_numeric_chat_id(msg.get("chat_id", ""))
    if numeric_chat_id is None:
        return "unknown"
    # Telegram private chats are positive ids; groups/supergroups are usually negative.
    return "private" if int(numeric_chat_id) > 0 else "group"


def get_last_messages(n: int) -> List[Dict]:
    """
    Читає останні N повідомлень з логів.
    
    Returns:
        List of dicts with keys: timestamp, msg_type, sender, text, 
        chat_id, date_str, file_path, line_idx
    """
    messages = []
    
    if not os.path.exists(_LOGS_DIR):
        return messages
    
    for year in sorted(os.listdir(_LOGS_DIR)):
        year_path = os.path.join(_LOGS_DIR, year)
        if not os.path.isdir(year_path) or not year.isdigit():
            continue
        for month in sorted(os.listdir(year_path)):
            month_path = os.path.join(year_path, month)
            if not os.path.isdir(month_path):
                continue
            for day in sorted(os.listdir(month_path)):
                day_path = os.path.join(month_path, day)
                if not os.path.isdir(day_path):
                    continue
                date_str = f"{year}-{month}-{day}"
                for log_file in sorted(os.listdir(day_path)):
                    if not log_file.endswith(".txt"):
                        continue
                    chat_identifier = log_file[:-4]
                    file_path = os.path.join(day_path, log_file)
                    try:
                        with open(file_path, encoding="utf-8") as f:
                            for i, line in enumerate(f):
                                m = _LINE_RE.match(line.strip())
                                if not m:
                                    continue
                                ts, msg_type, third, fourth, text = m.groups()
                                if third in {"private", "group", "supergroup", "channel"}:
                                    chat_type = third
                                    sender = fourth or chat_identifier
                                else:
                                    chat_type = ""
                                    sender = third or chat_identifier
                                sender = sender or chat_identifier
                                messages.append({
                                    "timestamp": ts,
                                    "msg_type": msg_type,
                                    "chat_type": chat_type,
                                    "sender": sender,
                                    "text": text,
                                    "chat_id": chat_identifier,
                                    "date_str": date_str,
                                    "dt": f"{date_str} {ts}",
                                    "file_path": file_path,
                                    "line_idx": i
                                })
                    except Exception as e:
                        print(f"[Jasmine] Cannot read {file_path}: {e}")
    
    # Сортуємо за датою та часом (припускаємо, що файли вже відсортовані)
    # Беремо останні N повідомлень
    return messages[-n:] if len(messages) > n else messages


def classify_message(text: str, config: dict, chat_id: str = "unknown") -> Tuple[bool, bool, str]:
    """
    Класифікує повідомлення через LM Studio (з fallback на Ollama) з RAG контекстом з БЗ.

    Returns:
        (is_jasmine_address, is_question, explanation)
    """
    bot_name = config["jasmine_filter"]["bot_name"]
    variations = config["jasmine_filter"]["bot_name_variations"]

    # Отримуємо RAG контекст з БЗ
    rag_context = get_rag_context(text, chat_id, config, max_results=3)

    system_prompt = f"""Ти — класифікатор повідомлень для сімейного чат-бота на ім'я "{bot_name}".
Твоя задача - точно визначати коли боту слід відповідати, а коли ні.

Правила для is_jasmine_address:
- True тільки якщо є пряме звернення до бота за іменем: {', '.join(variations)}
- False для будь-яких інших повідомлень

Правила для is_question:
- True тільки якщо це пряме прохання про допомогу/пораду/інформацію
- False для:
  * Простих повідомлень без питання
  * Привітань/побажань
  * Сарказму/жартів без прохання про допомогу
  * Загальних фраз на кшталт "як справи", "що нового"
  * Повідомлень які не вимагають інтелектуальної відповіді

Поверни ТІЛЬКИ JSON з двома булевими полями:
- "is_jasmine_address": true/false
- "is_question": true/false

Без жодного пояснення, тільки JSON."""

    base_user_prompt = f"Повідомлення: {text}"
    
    # Додаємо RAG контекст якщо є
    if rag_context:
        user_prompt = f"""{base_user_prompt}

{rag_context}

Врахуй контекст з бази знань при класифікації."""
    else:
        user_prompt = base_user_prompt

    # Викликаємо LLM з повним fallback ланцюжком
    content = _call_llm_with_fallback(
        config,
        system_prompt,
        user_prompt,
        temperature=0.1,
        task_name="classification",
        use_low_temp=True
    )
    
    if content is None:
        # Fallback до простого аналізу
        return simple_classify(text, bot_name, variations)
    
    # Парсимо JSON з відповіді
    try:
        classification = json.loads(content)
        is_jasmine = classification.get("is_jasmine_address", False)
        is_question = classification.get("is_question", False)
        rag_info = " + RAG" if rag_context else ""
        explanation = f"classified{rag_info}: jasmine={is_jasmine}, question={is_question}"
        return is_jasmine, is_question, explanation
    except json.JSONDecodeError:
        # Якщо не коректний JSON, пробуємо простий аналіз
        return simple_classify(text, bot_name, variations)


def simple_classify(text: str, bot_name: str, variations: List[str]) -> Tuple[bool, bool, str]:
    """
    Простий аналіз тексту без Ollama (fallback).
    Консервативний підхід - за замовчуванням не відповідаємо.
    """
    text_lower = text.lower()

    # Перевіряємо на звернення до бота
    is_jasmine = any(var in text_lower for var in variations)

    # За замовчуванням не вважаємо питанням
    is_question = False

    # Тільки пряме звернення за допомогою з "мені" вважається питанням
    direct_question_indicators = [
        'допоможи мені', 'підкажи мені', 'розкажи мені', 'поясни мені'
    ]

    if any(indicator in text_lower for indicator in direct_question_indicators):
        is_question = True

    # Якщо є "?" але без звернення "мені" або імені бота - не вважаємо питанням
    if not is_question and '?' in text_lower:
        if not is_jasmine and 'мені' not in text_lower:
            is_question = False

    explanation = f"Simple: jasmine={is_jasmine}, question={is_question}"
    return is_jasmine, is_question, explanation


def calculate_message_relevance(text: str, config: dict) -> Tuple[float, Optional[str]]:
    """
    Розраховує метрику релевантності повідомлення для галузей.
    
    Returns:
        (relevance_score, matched_industry_name)
        relevance_score: float between 0.0 and 1.0
        matched_industry_name: name of the matched industry or None
    """
    response_coeffs = config.get("jasmine_filter", {}).get("response_coefficients", {})
    industries = response_coeffs.get("industries", [])
    default_coefficient = response_coeffs.get("default_coefficient", 0.4)
    
    if not industries:
        return default_coefficient, None
    
    text_lower = text.lower()
    
    # Знаходимо галузь з найвищим релевантним скором
    best_score = 0.0
    best_industry = None
    
    for industry in industries:
        keywords = industry.get("keywords", [])
        if not keywords:
            continue
        
        # Рахуємо скільки ключових слів є в тексті
        matched_keywords = sum(1 for kw in keywords if kw.lower() in text_lower)
        
        if matched_keywords == 0:
            continue
        
        # Релевантність = кількість співпадінь / загальна кількість ключових слів
        relevance = matched_keywords / len(keywords)
        
        # Застосовуємо коефіцієнт галузі
        weighted_score = relevance * industry.get("coefficient", 0.5)
        
        if weighted_score > best_score:
            best_score = weighted_score
            best_industry = industry.get("name")
    
    if best_score > 0:
        return min(best_score, 1.0), best_industry
    
    return default_coefficient, None


def _lm_studio_root_url(chat_completions_url: str) -> str:
    for suffix in ("/v1/chat/completions", "/chat/completions"):
        if chat_completions_url.endswith(suffix):
            return chat_completions_url[: -len(suffix)]
    return chat_completions_url.rstrip("/")


def _lm_studio_loaded_models(lm_config: dict) -> List[str]:
    """Return currently loaded LM Studio chat-capable model ids."""
    root_url = _lm_studio_root_url(lm_config["url"])
    try:
        response = requests.get(f"{root_url}/api/v0/models", timeout=5)
        response.raise_for_status()
        data = response.json().get("data", [])
    except Exception as exc:
        print(f"[Jasmine] LM Studio loaded-model check failed: {exc}")
        return []

    loaded = []
    for item in data:
        model_id = item.get("id")
        model_type = item.get("type")
        state = item.get("state")
        if not model_id or state != "loaded" or model_type == "embeddings":
            continue
        loaded.append(model_id)
    return loaded


def _lm_studio_chat(
    lm_config: dict,
    model: str,
    system_prompt: str,
    user_prompt: str,
    timeout: int = 450,
) -> str:
    # Stop sequences щоб модель не продовжувала фейковий діалог
    stop_sequences = [
        "\n[20",       # початок штампу часу [2026-...
        "\n[BandiuB",
        "\n[ЮРІЙ",
        "\n[Band",
        "\n[Жасмін]:",
        "\n[Jasmine]:",
    ]
    response = requests.post(
        lm_config["url"],
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.8,
            "max_tokens": 20000,
            "top_p": 0.9,
            "stream": False,
            "stop": stop_sequences,
        },
        timeout=timeout
    )
    response.raise_for_status()
    result = response.json()
    return result.get("choices", [{}])[0].get("message", {}).get("content", "")


def _call_llm_with_fallback(
    config: dict,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.8,
    task_name: str = "LLM task",
    use_low_temp: bool = False
) -> Optional[str]:
    """
    Universal LLM call with full fallback chain:
    LM Studio (primary) → LM Studio loaded models → Ollama
    
    Args:
        use_low_temp: If True, use temperature 0.1 (for classification/decision tasks)
    
    Returns:
        Response content or None if all failed
    """
    lm_config = config["jasmine_filter"]["lm_studio"]
    temp = 0.1 if use_low_temp else temperature
    
    # 1. Try primary LM Studio model
    try:
        content = _lm_studio_chat(
            lm_config,
            lm_config["model"],
            system_prompt,
            user_prompt,
            timeout=450,
        )
        if content:
            print(f"[Jasmine] {task_name}: LM Studio primary")
            return content
    except Exception as e:
        print(f"[Jasmine] LM Studio primary error for {task_name}: {e}")
    
    # 2. Try loaded LM Studio models
    if lm_config.get("use_loaded_model_fallback", True):
        loaded_models = _lm_studio_loaded_models(lm_config)
        for loaded_model in loaded_models:
            if loaded_model == lm_config.get("model"):
                continue
            try:
                content = _lm_studio_chat(
                    lm_config,
                    loaded_model,
                    system_prompt,
                    user_prompt,
                    timeout=450,
                )
                if content:
                    print(f"[Jasmine] {task_name}: LM Studio fallback ({loaded_model})")
                    return content
            except Exception as e:
                print(f"[Jasmine] LM Studio fallback error ({loaded_model}): {e}")
    
    # 3. Final fallback to Ollama
    print(f"[Jasmine] {task_name}: Fallback to Ollama...")
    try:
        ollama_config = config["jasmine_filter"]["ollama"]
        fallback_model = ollama_config.get("fallback_model", ollama_config["model"])
        
        response = requests.post(
            ollama_config["url"],
            json={
                "model": fallback_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "stream": False,
                "temperature": temp
            },
            timeout=450
        )
        response.raise_for_status()
        result = response.json()
        content = result.get("message", {}).get("content", "")
        
        if content:
            print(f"[Jasmine] {task_name}: Ollama fallback")
            return content
    except Exception as e:
        print(f"[Jasmine] Ollama fallback error for {task_name}: {e}")
    
    return None


def send_to_lm_studio(messages: List[Dict], config: dict, chat_id: str = "unknown", processed_ids: Optional[set] = None) -> Optional[str]:
    """
    Відправляє відфільтровані повідомлення до "мізків Жасмін" (LM Studio) з RAG контекстом.
    Повідомлення з processed_ids маркуються як [ОБРОБЛЕНО].

    Returns:
        Response text or None if failed
    """
    processed_ids = processed_ids or set()
    lm_config = config["jasmine_filter"]["lm_studio"]

    # Формуємо контекст з повідомлень
    roles = infer_chat_roles(messages, config)
    role_lines = []
    for sender, meta in sorted(roles.items(), key=lambda x: -x[1].get("messages", 0)):
        role_lines.append(f"- {sender}: роль={meta['role']}, повідомлень={meta['messages']}")

    def _format_msg(msg: Dict) -> str:
        msg_id = get_message_id(msg)
        marker = " [ОБРОБЛЕНО]" if msg_id in processed_ids else ""
        return f"[{msg['date_str']} {msg['timestamp']}] [{msg['sender']}]:{marker} {msg['text']}"
    
    context = "\n".join([_format_msg(msg) for msg in messages])

    # Отримуємо RAG контекст з БЗ для останнього повідомлення
    last_message = messages[-1] if messages else None
    rag_context = ""
    web_context = ""
    if last_message:
        rag_context = get_rag_context(last_message["text"], chat_id, config, max_results=5)
        web_context = get_web_search_context(last_message["text"], config, max_results=5)

    web_search_enabled = bool(
        config.get("jasmine_filter", {}).get("web_search", {}).get("enabled", False)
    )
    web_search_note = (
        "\n\nДоступні інструменти:\n"
        "- 🌐 Пошук в інтернеті (DuckDuckGo + Wikipedia) активується АВТОМАТИЧНО, "
        "коли користувач використовує тригерні слова: 'пошукай', 'знайди', 'загугли', "
        "'хто такий', 'що таке', 'новини', 'актуальн', 'сьогодні'. "
        "Якщо результати пошуку додано в контекст — використай їх та обов'язково додай URL-джерело. "
        "Якщо користувач хоче інформацію з інтернету, але не використав тригерні слова — "
        "запропонуй: \"Хочеш я пошукаю в інтернеті? Скажи 'пошукай ...'\""
        if web_search_enabled else ""
    )

    system_prompt = f"""Ти — Жасмін, інтелектуальна сімейна чат-бот помічниця. Ти — дівчина з почуттям гумору, яка знає що всім подобається, але не пихата.

Твій стиль:
- Будь жартівливою, грайливою, трохи кокетливою, але завжди ввічливою
- Давай корисні, продумані відповіді — аналізуй контекст глибоко
- Якщо не знаєш відповіді — чесно скажи, не вигадуй
- Використовуй емоції та емпатію в відповідях
- Будь лаконічною, але інформативною
- Адаптуй відповідь під контекст розмови
- Використовуй знання з бази знань (якщо є) для кращих відповідей

Відповідай українською мовою.{web_search_note}

⚠️ КРИТИЧНІ ПРАВИЛА ФОРМАТУ ВІДПОВІДІ:
1. Видавай ТІЛЬКИ ОДНЕ повідомлення від свого імені (Жасмін).
2. НЕ імітуй і НЕ пиши повідомлення від імені інших учасників чату (BandiuB, ЮРІЙ, alex_konsta тощо).
3. НЕ додавай маркери часу типу [2026-05-10 13:31:55] чи [Жасмін]: — їх додасть система.
4. НЕ продовжуй діалог за інших — зупинись після своєї єдиної відповіді.
5. Не вигадуй вигаданих діалогів.

Ти можеш відправляти повідомлення в інші чати. Доступні чати: сімейний (family).
Якщо користувач просить "напиши в сімейний чат" або подібне — почни відповідь з тегу [SEND_TO:ім'я_чату] на окремому рядку, потім текст повідомлення.
Приклад:
[SEND_TO:сімейний]
Привіт усім, я тут з приватного чату!"""

    base_user_prompt = f"""Останні повідомлення в чаті:

Учасники та їх імовірні ролі:
{chr(10).join(role_lines) if role_lines else "- невідомо"}

{context}

Дай розумну, корисну відповідь з урахуванням контексту.
Якщо в контексті не видно прямого звернення до Жасмін або запиту на допомогу — відповідай дуже коротко і нейтрально."""

    # Додаємо RAG та веб-контекст якщо є
    extra_blocks = []
    if rag_context:
        extra_blocks.append(rag_context + "\n\nВрахуй цей контекст з бази знань при формуванні відповіді.")
    if web_context:
        extra_blocks.append(web_context + "\n\nВикористай ці актуальні дані з інтернету у відповіді. Обов'язково додай джерело (URL) якщо посилаєшся на конкретний факт.")

    if extra_blocks:
        user_prompt = base_user_prompt + "\n\n" + "\n\n".join(extra_blocks)
    else:
        user_prompt = base_user_prompt

    try:
        content = _lm_studio_chat(
            lm_config,
            lm_config["model"],
            system_prompt,
            user_prompt,
        )
        
        if rag_context:
            print(f"[Jasmine] Відповідь згенерована з RAG контекстом (LM Studio)")
        
        return content

    except Exception as e:
        print(f"[Jasmine] LM Studio error: {e}")
        if lm_config.get("use_loaded_model_fallback", True):
            loaded_models = _lm_studio_loaded_models(lm_config)
            for loaded_model in loaded_models:
                if loaded_model == lm_config.get("model"):
                    continue
                print(f"[Jasmine] Trying currently loaded LM Studio model: {loaded_model}")
                try:
                    content = _lm_studio_chat(
                        lm_config,
                        loaded_model,
                        system_prompt,
                        user_prompt,
                    )
                    if content:
                        print(f"[Jasmine] LM Studio fallback model used: {loaded_model}")
                        return content
                except Exception as loaded_error:
                    print(f"[Jasmine] Loaded LM Studio model failed ({loaded_model}): {loaded_error}")

        print(f"[Jasmine] Fallback to Ollama...")
        
        # Fallback на Ollama якщо LM Studio недоступний
        try:
            ollama_config = config["jasmine_filter"]["ollama"]
            fallback_model = ollama_config.get("fallback_model", ollama_config["model"])
            
            response = requests.post(
                ollama_config["url"],
                json={
                    "model": fallback_model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "stream": False
                },
                timeout=450
            )
            response.raise_for_status()
            result = response.json()
            
            content = result.get("message", {}).get("content", "")
            
            if rag_context:
                print(f"[Jasmine] Відповідь згенерована з RAG контекстом (Ollama fallback)")
            else:
                print(f"[Jasmine] Відповідь згенерована через Ollama fallback")
            
            return content
        except Exception as ollama_error:
            print(f"[Jasmine] Ollama fallback error: {ollama_error}")
            return None


def text_to_speech(text: str, config: dict, voice: str = "Dmytro") -> Optional[bytes]:
    """
    Озвучує текст через TTS сервер.

    Returns:
        Audio bytes or None if failed
    """
    tts_url = config.get("jasmine_filter", {}).get("tts_url", "http://127.0.0.1:8002/tts")

    try:
        response = requests.post(
            tts_url,
            json={"text": text, "voice": voice, "stress": "Dictionary"},
            timeout=60
        )
        response.raise_for_status()
        return response.content
    except Exception as e:
        print(f"[Jasmine] TTS error: {e}")
        return None


def detect_tts_request_llm(text: str, config: dict) -> Tuple[bool, Optional[str]]:
    """
    Розпізнає запити на озвучку тексту через малу ЛЛМ (Ollama).

    Returns:
        (is_tts_request, text_to_speech)
    """
    ollama_config = config["jasmine_filter"]["ollama"]

    prompt = f"""Проаналізуй повідомлення і визначи чи це прохання озвучити текст.

Повідомлення: "{text}"

Поверни JSON з двома полями:
- "is_tts": true якщо це прохання озвучити текст, false інакше
- "text_to_speak": текст який треба озвучити, або "PREVIOUS_MESSAGE" якщо треба озвучити попереднє повідомлення, або null якщо немає тексту

Якщо це не прохання озвучки - поверни {{"is_tts": false, "text_to_speak": null}}
Поверни ТІЛЬКИ JSON, без пояснень."""

    try:
        response = requests.post(
            ollama_config["url"],
            json={
                "model": ollama_config["model"],
                "messages": [{"role": "user", "content": prompt}],
                "stream": False
            },
            timeout=450
        )
        response.raise_for_status()
        result = response.json()

        content = result.get("message", {}).get("content", "{}")

        # Парсимо JSON з відповіді
        import json
        import re
        match = re.search(r'\{[^{}]*\}', content)
        if match:
            json_str = match.group(0)
            parsed = json.loads(json_str)
            is_tts = parsed.get("is_tts", False)
            text_to_speak = parsed.get("text_to_speak")

            if is_tts:
                return True, text_to_speak

        return False, None

    except Exception as e:
        print(f"[Jasmine] LLM TTS detection error: {e}")
        return False, None


def detect_tts_request(text: str, config: dict, use_llm: bool = False) -> Tuple[bool, Optional[str]]:
    """
    Розпізнає запити на озвучку тексту.

    Returns:
        (is_tts_request, text_to_speech)
    """
    # Спочатку пробуємо просте розпізнавання
    text_lower = text.lower()

    # Ключові слова для запиту озвучки (цілі слова)
    tts_keywords = [
        r"\bозвуч\b", r"\bозвучь\b", r"\bскажи\s+голосом\b",
        r"\bпрочитай\s+вголос\b", r"\bпрочитай\b", r"\bозвуч\s+це\b",
        r"\bпроговори\b", r"\bпроизнеси\b", r"\bзапиши\s+голосом\b",
        r"\bзапиши\s+аудіо\b", r"\bзроби\s+аудіо\b"
    ]

    import re

    # Перевіряємо чи є запит на озвучку (цілі слова)
    is_request = any(re.search(keyword, text_lower) for keyword in tts_keywords)

    if not is_request:
        # Якщо просте розпізнавання не спрацювало і увімкнено ЛЛМ - пробуємо ЛЛМ
        if use_llm:
            return detect_tts_request_llm(text, config)
        return False, None

    # Якщо є цитата в лапках або дужках - озвучуємо її
    quote_pattern = r'["«](.+?)["»»]'
    quotes = re.findall(quote_pattern, text)
    if quotes:
        return True, quotes[0]

    # Якщо є запит на озвучку попереднього повідомлення
    prev_keywords = [r"\bпопереднє\b", r"\bостаннє\b", r"\bте\s+що\s+вище\b", r"\bвище\s+написане\b"]
    if any(re.search(keyword, text_lower) for keyword in prev_keywords):
        return True, "PREVIOUS_MESSAGE"

    # Якщо немає конкретного тексту - озвучуємо все повідомлення без команди
    # Видаляємо ключові слова озвучки
    cleaned_text = text_lower
    for keyword in tts_keywords:
        cleaned_text = re.sub(keyword, "", cleaned_text).strip()

    if cleaned_text:
        return True, cleaned_text

    # Якщо просте розпізнавання не дало результату і увімкнено ЛЛМ - пробуємо ЛЛМ
    if use_llm:
        return detect_tts_request_llm(text, config)

    return True, None


def get_previous_message(messages: List[Dict], current_index: int) -> Optional[str]:
    """
    Отримує текст попереднього повідомлення.

    Returns:
        Text of previous message or None
    """
    if current_index > 0 and current_index < len(messages):
        return messages[current_index - 1]["text"]
    return None


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def _extract_keywords(text: str, max_keywords: int = 6) -> List[str]:
    tokens = re.findall(r"[a-zа-яіїєґ0-9_'-]{3,}", _normalize_text(text))
    keywords = [t for t in tokens if t not in _STOPWORDS]
    seen = set()
    result = []
    for kw in keywords:
        if kw in seen:
            continue
        seen.add(kw)
        result.append(kw)
        if len(result) >= max_keywords:
            break
    return result


def infer_chat_roles(messages: List[Dict], config: dict) -> Dict[str, Dict]:
    """Грубо визначає ролі учасників у чаті для кращого розуміння 'хто є хто'."""
    bot_name = _normalize_text(config["jasmine_filter"].get("bot_name", "Жасмін"))
    bot_vars = [_normalize_text(v) for v in config["jasmine_filter"].get("bot_name_variations", [])]
    bot_aliases = {bot_name, *bot_vars, "bot", "assistant", "жасмін"}

    counts: Dict[str, int] = {}
    for msg in messages:
        sender = msg.get("sender", "").strip()
        if not sender:
            continue
        counts[sender] = counts.get(sender, 0) + 1

    roles = {}
    for sender, count in counts.items():
        sender_norm = _normalize_text(sender)
        role = "assistant" if any(alias in sender_norm for alias in bot_aliases) else "human"
        roles[sender] = {"role": role, "messages": count}
    return roles


def evaluate_response_usefulness(
    msg: Dict,
    config: dict,
    recent_chat_messages: List[Dict],
    is_jasmine: bool,
    is_question: bool,
) -> Tuple[Optional[bool], float, str]:
    """
    Ask the service LLM whether Jasmine should answer in a group chat.
    Uses unified LLM call with LM Studio primary + fallback chain.
    """
    bot_name = config["jasmine_filter"].get("bot_name", "Жасмін")
    bot_aliases = ", ".join(config["jasmine_filter"].get("bot_name_variations", []))
    chat_id = msg.get("chat_id", "unknown")
    rag_context = get_rag_context(msg.get("text", ""), chat_id, config, max_results=5)

    recent_context = "\n".join(
        f"[{m.get('timestamp', '')}] [{m.get('sender', '')}]: {m.get('text', '')}"
        for m in recent_chat_messages[-8:]
    )

    system_prompt = f"""Ти — диспетчер сімейного чат-бота {bot_name}.
Треба вирішити, чи варто боту відповісти в груповому чаті.

Важливо:
- Не вимагай явного звернення "{bot_name}" або aliases: {bot_aliases}.
- Відповідай true, якщо бот може дати корисну, доречну, контекстну відповідь.
- Відповідай true, якщо є питання, прохання, плутанина, корисна порада, нагадування, факт із пам'яті або контексту.
- Відповідай false, якщо це приватна розмова між людьми, жарт без потреби, коротка реакція, або втручання буде зайвим.
- Якщо не впевнений, краще false.

Поверни ТІЛЬКИ JSON з полями:
- "should_respond": true/false
- "confidence": 0.0-1.0
- "reason": "коротко українською" 
"""

    user_prompt = f"""Поточне повідомлення:
[{msg.get('sender', '')}] {msg.get('text', '')}

Ознаки:
- explicit_bot_address: {is_jasmine}
- question_like: {is_question}

Останній контекст чату:
{recent_context or "- немає"}

{rag_context or "Контекст з пам'яті: немає"}"""

    # Викликаємо unified LLM з повним fallback
    content = _call_llm_with_fallback(
        config,
        system_prompt,
        user_prompt,
        temperature=0.0,
        task_name="response_decision",
        use_low_temp=True
    )
    
    if content is None:
        return None, 0.0, "LLM decision unavailable: all LLM backends failed"
    
    try:
        match = re.search(r"\{[\s\S]*\}", content)
        parsed = json.loads(match.group(0) if match else content)
        should = bool(parsed.get("should_respond", False))
        confidence = float(parsed.get("confidence", 0.0))
        reason = str(parsed.get("reason", "LLM decision"))
        return should, max(0.0, min(confidence, 1.0)), reason
    except Exception as exc:
        print(f"[Jasmine] LLM response-decision parse error: {exc}")
        return None, 0.0, f"LLM decision unavailable: {exc}"


def _parse_dt(msg: Dict) -> Optional[datetime]:
    try:
        return datetime.strptime(f"{msg['date_str']} {msg['timestamp']}", "%Y-%m-%d %H:%M:%S")
    except Exception:
        return None


def _topic_overlap(a: List[str], b: List[str]) -> float:
    if not a or not b:
        return 0.0
    sa, sb = set(a), set(b)
    return len(sa & sb) / max(len(sa | sb), 1)


def decide_response(msg: Dict, config: dict, context_state: Dict, recent_chat_messages: List[Dict],
                    is_jasmine: bool, is_question: bool) -> Tuple[bool, float, List[str]]:
    """
    Приймає рішення чи варто відповідати.
    Повертає: (should_respond, score, reasons)
    """
    score = 0.0
    reasons: List[str] = []
    text = msg.get("text", "")
    text_norm = _normalize_text(text)
    chat_id = msg.get("chat_id", "unknown")
    chat_kind = get_chat_kind(msg)
    topic_keywords = _extract_keywords(text)
    relevance, industry = calculate_message_relevance(text, config)

    if chat_kind == "private":
        return True, 1.0, ["приватний чат: відповідаємо без явного виклику"]

    if is_jasmine:
        score += 0.8
        reasons.append("пряме звернення до Жасмін")
    if is_question:
        score += 0.45
        reasons.append("є запит/питання")
    if "?" in text and len(text) > 8:
        score += 0.15
        reasons.append("питальна форма")
    if _GREETING_RE.search(text_norm) and len(text_norm) < 22:
        score -= 0.25
        reasons.append("коротке вітання без задачі")

    score += min(relevance, 1.0) * 0.25
    if industry:
        reasons.append(f"релевантна галузь: {industry}")

    # Контекст попередніх взаємодій у чаті
    chat_state = context_state.get("chats", {}).get(chat_id, {})
    active = chat_state.get("active_topic", {})
    active_keywords = active.get("keywords", [])
    overlap = _topic_overlap(topic_keywords, active_keywords)
    if overlap >= 0.25:
        score += 0.2
        reasons.append(f"продовження активної теми ({overlap:.2f})")

    active_until = chat_state.get("active_until")
    now_dt = _parse_dt(msg) or datetime.now()
    if active_until:
        try:
            until_dt = datetime.fromisoformat(active_until)
            if now_dt <= until_dt:
                score += 0.1
                reasons.append("в межах активного контекстного вікна")
        except Exception:
            pass

    # Якщо є ознаки діалогу "людина -> питання -> уточнення"
    if len(recent_chat_messages) >= 2:
        prev = recent_chat_messages[-2]
        prev_keywords = _extract_keywords(prev.get("text", ""))
        if _topic_overlap(topic_keywords, prev_keywords) >= 0.25:
            score += 0.1
            reasons.append("локальна зв'язність з попереднім повідомленням")

    if is_jasmine:
        should_respond = True
    else:
        llm_decision, llm_confidence, llm_reason = evaluate_response_usefulness(
            msg,
            config,
            recent_chat_messages,
            is_jasmine,
            is_question,
        )
        if llm_decision is not None:
            reasons.append(f"LLM-рішення: {llm_reason}")
            score = max(score, llm_confidence)
            should_respond = llm_decision and llm_confidence >= 0.55
        else:
            reasons.append(llm_reason)
            if is_question and score >= 0.55:
                should_respond = True
                reasons.append("fallback: питання з достатнім контекстним скором")
            else:
                should_respond = score >= 0.65
    return should_respond, round(score, 3), reasons


def build_context_window(messages: List[Dict], target_idx: int, max_messages: int = 12) -> List[Dict]:
    """Будує контекстне вікно в межах однієї теми та одного чату."""
    if target_idx < 0 or target_idx >= len(messages):
        return []
    target = messages[target_idx]
    chat_id = target.get("chat_id")
    target_keys = _extract_keywords(target.get("text", ""))

    window = [target]
    i = target_idx - 1
    while i >= 0 and len(window) < max_messages:
        msg = messages[i]
        if msg.get("chat_id") != chat_id:
            i -= 1
            continue
        keys = _extract_keywords(msg.get("text", ""))
        overlap = _topic_overlap(target_keys, keys)
        if overlap >= 0.2 or i >= target_idx - 3:
            window.append(msg)
        else:
            break
        i -= 1

    return list(reversed(window))


def send_audio_to_chat(chat_id: str, audio: bytes, config: dict) -> bool:
    """
    Відправляє аудіо в чат через бота.

    Args:
        chat_id: Chat identifier (string from filename)
        audio: Audio bytes
        config: Configuration dict

    Returns:
        True if successful, False otherwise
    """
    import sys
    import subprocess

    try:
        # Отримуємо numeric Telegram chat_id з registry
        numeric_chat_id = get_numeric_chat_id(chat_id)
        if not numeric_chat_id:
            print(f"[Jasmine] Не знайдено numeric chat_id для {chat_id}")
            return False

        # Використовуємо bot.py для відправки аудіо
        bot_path = os.path.join(_BASE_DIR, "bot.py")

        # Зберігаємо аудіо тимчасово
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(audio)
            tmp_path = tmp.name

        try:
            # Відправляємо аудіо через бота
            result = subprocess.run(
                [sys.executable, bot_path, "--send-voice", str(numeric_chat_id), tmp_path],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=_BASE_DIR  # Ensure correct working directory
            )

            if result.returncode == 0:
                print(f"[Jasmine] Аудіо відправлено в чат {chat_id} (id: {numeric_chat_id})")
                return True
            else:
                print(f"[Jasmine] Помилка відправки аудіо (code {result.returncode})")
                if result.stdout:
                    print(f"[Jasmine] stdout: {result.stdout}")
                if result.stderr:
                    print(f"[Jasmine] stderr: {result.stderr}")
                return False

        finally:
            # Видаляємо тимчасовий файл
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    except Exception as e:
        print(f"[Jasmine] Помилка відправки аудіо: {e}")
        return False


def _parse_send_to_target(response: str, config: dict) -> tuple[str, int | None]:
    """
    Parse [SEND_TO:target] tag from response and resolve to numeric chat ID.
    
    Returns:
        (cleaned_response, target_numeric_chat_id or None)
    """
    import re
    
    allowed_chats = config.get("jasmine_filter", {}).get("allowed_target_chats", {})
    if not allowed_chats:
        return response, None
    
    # Look for [SEND_TO:chat_name] pattern
    pattern = r'^\[SEND_TO:([^\]]+)\]\s*\n?'
    match = re.match(pattern, response.strip())
    
    if not match:
        return response, None
    
    target_name = match.group(1).strip().lower()
    target_chat_id = None
    
    # Try to match by name
    for name, chat_id in allowed_chats.items():
        if name.lower() == target_name:
            target_chat_id = chat_id
            break
    
    if not target_chat_id:
        print(f"[Jasmine] SEND_TO target '{target_name}' not in allowed_target_chats")
        return response, None
    
    # Clean the response by removing the tag
    cleaned = re.sub(pattern, '', response.strip(), count=1)
    print(f"[Jasmine] Cross-chat send to '{target_name}' ({target_chat_id})")
    return cleaned, target_chat_id


def process_messages(config: dict, verbose: bool = True) -> Dict:
    """
    Обробляє повідомлення: фільтрує та відправляє до LM Studio.
    
    Returns:
        Stats dict with keys: total, filtered, sent_to_lm
    """
    n_messages = config["jasmine_filter"]["last_n_messages"]
    messages = get_last_messages(n_messages)
    
    # Завантажуємо список оброблених повідомлень
    processed_ids = load_processed_messages()
    context_state = load_context_state()
    
    stats = {
        "total": len(messages),
        "filtered": 0,
        "sent_to_lm": 0,
        "tts_generated": 0,
        "skipped": 0,
        "graphiti_ingested": 0,
    }

    if not messages:
        if verbose:
            print("[Jasmine] Немає повідомлень для обробки")
        return stats

    if verbose:
        print(f"[Jasmine] Перевіряю {len(messages)} останніх повідомлень...")

    filtered_by_chat: Dict[str, Dict] = {}
    tts_requests = []  # Зберігаємо запити на озвучку

    # Отримуємо налаштування ЛЛМ для TTS
    use_llm_tts = config.get("jasmine_filter", {}).get("use_llm_tts", False)

    for idx, msg in enumerate(messages):
        msg_id = get_message_id(msg)
        
        # Пропускаємо вже оброблені повідомлення
        if msg_id in processed_ids:
            stats["skipped"] += 1
            if verbose and stats["skipped"] <= 3:  # Show first 3 skips for debugging
                print(f"[Jasmine] ⊘ [{msg['sender']}] {msg['text'][:30]}... (вже оброблено)")
            continue
        
        # Додаємо повідомлення в список оброблених (незалежно від результату класифікації)
        processed_ids.add(msg_id)

        if add_message_to_graphiti(msg, config, msg_id):
            stats["graphiti_ingested"] += 1
            if verbose:
                print(f"[Jasmine] 🧠 Graphiti episode: [{msg['sender']}] {msg['text'][:50]}...")
        
        is_jasmine, is_question, explanation = classify_message(msg["text"], config, msg["chat_id"])

        # Перевіряємо чи це запит на озвучку
        is_tts, text_to_speak = detect_tts_request(msg["text"], config, use_llm=use_llm_tts)
        if is_tts:
            tts_requests.append({
                "msg": msg,
                "text": text_to_speak,
                "index": idx,
                "msg_id": msg_id
            })
            if verbose:
                print(f"[Jasmine] 🔊 TTS запит: [{msg['sender']}] {msg['text'][:50]}...")
            continue  # Не відправляємо в LM Studio якщо це TTS запит

        # Нова логіка рішення чи відповідати
        recent_in_chat = [m for m in messages[max(0, idx - 8): idx + 1] if m["chat_id"] == msg["chat_id"]]
        should_respond, score, reasons = decide_response(
            msg, config, context_state, recent_in_chat, is_jasmine, is_question
        )

        if should_respond:
            stats["filtered"] += 1
            context_window = build_context_window(messages, idx)
            filtered_by_chat[msg["chat_id"]] = {
                "msg": msg,
                "msg_id": msg_id,
                "context": context_window
            }

            if verbose:
                print(
                    f"[Jasmine] ✓ [{msg['sender']}] {msg['text'][:50]}... "
                    f"(score={score}, {explanation}; {'; '.join(reasons[:3])})"
                )
        else:
            if verbose:
                print(f"[Jasmine] ✗ [{msg['sender']}] {msg['text'][:50]}... (score={score})")
    
    # Відправляємо відфільтровані повідомлення до LM Studio
    filtered_messages = list(filtered_by_chat.values())
    if filtered_messages:
        if verbose:
            print(f"[Jasmine] Відправляю {len(filtered_messages)} контекстних запитів до Жасмін (LM Studio)...")

        for item in filtered_messages:
            chat_id = item["msg"]["chat_id"]
            context_messages = item.get("context") or [item["msg"]]
            response = send_to_lm_studio(context_messages, config, chat_id, processed_ids)

            if not response:
                if verbose:
                    print(f"[Jasmine] Не вдалося отримати відповідь для чату {chat_id}")
                continue

            stats["sent_to_lm"] += 1
            processed_ids.add(item["msg_id"])
            if verbose:
                print(f"[Jasmine] Жасмін відповіла ({chat_id}): {response[:100]}...")

            # Оновлюємо контекстний стан чату
            chat_state = context_state.setdefault("chats", {}).setdefault(chat_id, {})
            keywords = _extract_keywords(item["msg"]["text"])
            now_dt = _parse_dt(item["msg"]) or datetime.now()
            chat_state["active_topic"] = {
                "keywords": keywords,
                "updated_at": now_dt.isoformat(timespec="seconds"),
                "last_sender": item["msg"]["sender"]
            }
            chat_state["active_until"] = (now_dt + timedelta(minutes=15)).isoformat(timespec="seconds")

            # Озвучуємо відповідь якщо TTS увімкнено, інакше відправляємо текст
            tts_enabled = config.get("jasmine_filter", {}).get("tts_enabled", False)
            if tts_enabled:
                voice = config.get("jasmine_filter", {}).get("tts_voice", "Tetiana")
                audio = text_to_speech(response, config, voice)
                if audio and verbose:
                    print(f"[Jasmine] Аудіо згенеровано ({len(audio)} байт)")
                    send_audio_to_chat(chat_id, audio, config)
                elif verbose:
                    print(f"[Jasmine] Не вдалося згенерувати аудіо")
            else:
                if verbose:
                    print(f"[Jasmine] Відправляю текстову відповідь...")
                
                # Parse SEND_TO tag for cross-chat messaging
                response_cleaned, target_chat_id = _parse_send_to_target(response, config)
                
                # Use target chat if specified and allowed, otherwise use original
                numeric_chat_id = target_chat_id if target_chat_id else get_numeric_chat_id(chat_id)
                
                if numeric_chat_id:
                    import subprocess
                    import sys
                    bot_path = os.path.join(_BASE_DIR, "bot.py")

                    # Telegram має ліміт 4096 символів на повідомлення
                    TELEGRAM_MAX = 4000  # запас 96 символів
                    chunks = []
                    text_to_send = response_cleaned
                    while len(text_to_send) > TELEGRAM_MAX:
                        # шукаємо найближчий перенос рядка для розриву
                        cut = text_to_send.rfind("\n", 0, TELEGRAM_MAX)
                        if cut < TELEGRAM_MAX // 2:
                            cut = TELEGRAM_MAX
                        chunks.append(text_to_send[:cut])
                        text_to_send = text_to_send[cut:].lstrip()
                    if text_to_send:
                        chunks.append(text_to_send)

                    all_ok = True
                    last_err = ""
                    for idx, chunk in enumerate(chunks, 1):
                        result = subprocess.run(
                            [sys.executable, bot_path, "--send", str(numeric_chat_id), chunk],
                            capture_output=True,
                            text=True,
                            timeout=90,
                            cwd=_BASE_DIR
                        )
                        if result.returncode != 0:
                            all_ok = False
                            last_err = (
                                f"rc={result.returncode}, "
                                f"stderr={result.stderr.strip()!r}, "
                                f"stdout={result.stdout.strip()[:300]!r}"
                            )
                            break
                    if all_ok and verbose:
                        target_desc = target_chat_id if target_chat_id else chat_id
                        chunk_info = f" ({len(chunks)} частин)" if len(chunks) > 1 else ""
                        print(f"[Jasmine] Текст відправлено в чат {target_desc}{chunk_info}")
                    elif verbose:
                        print(
                            f"[Jasmine] Помилка відправки тексту: {last_err} "
                            f"| len(response)={len(response_cleaned)}"
                        )
    elif verbose:
        print(f"[Jasmine] Немає повідомлень, які потребують відповіді")

    # Обробляємо TTS запити
    if tts_requests:
        voice = config.get("jasmine_filter", {}).get("tts_voice", "Tetiana")
        if verbose:
            print(f"[Jasmine] Обробляю {len(tts_requests)} TTS запитів...")

        for tts_req in tts_requests:
            msg = tts_req["msg"]
            text_to_speak = tts_req["text"]
            idx = tts_req["index"]
            msg_id = tts_req["msg_id"]

            # Якщо запит на попереднє повідомлення
            if text_to_speak == "PREVIOUS_MESSAGE":
                text_to_speak = get_previous_message(messages, idx)
                if not text_to_speak:
                    if verbose:
                        print(f"[Jasmine] Немає попереднього повідомлення")
                    continue

            if not text_to_speak:
                if verbose:
                    print(f"[Jasmine] Немає тексту для озвучки")
                continue

            # Генеруємо аудіо
            audio = text_to_speech(text_to_speak, config, voice)
            if audio:
                stats["tts_generated"] += 1
                if verbose:
                    print(f"[Jasmine] 🔊 Озвучено: {text_to_speak[:50]}... ({len(audio)} байт)")

                # Позначаємо TTS запит як оброблений
                processed_ids.add(msg_id)

                # Відправляємо аудіо в чат
                send_audio_to_chat(msg["chat_id"], audio, config)
            elif verbose:
                print(f"[Jasmine] Не вдалося згенерувати аудіо для: {text_to_speak[:50]}...")

    # Зберігаємо список оброблених повідомлень (навіть якщо нічого не відправлено)
    save_processed_messages(processed_ids)
    save_context_state(context_state)

    return stats


def run_watch(config: dict):
    """Запускає watch-режим для постійної перевірки нових повідомлень"""
    interval = config["jasmine_filter"]["check_interval_seconds"]
    print(f"[Jasmine] Watch-режим: перевірка кожні {interval} с. Ctrl+C для зупинки.\n")
    
    try:
        while True:
            stats = process_messages(config, verbose=True)
            
            if stats["filtered"] > 0 or stats["tts_generated"] > 0 or stats["skipped"] > 0:
                ts = datetime.now().strftime("%H:%M:%S")
                print(f"[Jasmine] {ts} — перевірено {stats['total']}, "
                      f"нових: {stats['filtered'] + stats['tts_generated']}, "
                      f"пропущено: {stats['skipped']}, "
                      f"відправлено до Жасмін: {stats['sent_to_lm']}")
            
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n[Jasmine] Watch зупинено.")


def main():
    parser = argparse.ArgumentParser(
        description="Jasmine Filter — фільтрує повідомлення для сімейного чат-бота",
        add_help=True,
    )
    parser.add_argument("--process", action="store_true", help="Обробити повідомлення один раз")
    parser.add_argument("--watch", action="store_true", help="Watch-режим (постійна перевірка)")
    args = parser.parse_args()
    
    config = load_config()
    
    if not config["jasmine_filter"]["enabled"]:
        print("[Jasmine] Фільтр відключений в config.json")
        return
    
    if args.process:
        stats = process_messages(config, verbose=True)
        print(f"\n[Jasmine] Готово: перевірено {stats['total']} повідомлень, "
              f"відфільтровано {stats['filtered']}, відправлено {stats['sent_to_lm']} до Жасмін")
    elif args.watch:
        run_watch(config)
    else:
        # За замовчуванням — один раз
        stats = process_messages(config, verbose=True)
        print(f"\n[Jasmine] Готово: перевірено {stats['total']} повідомлень, "
              f"відфільтровано {stats['filtered']}, відправлено {stats['sent_to_lm']} до Жасмін")


if __name__ == "__main__":
    main()
