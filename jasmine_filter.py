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
from datetime import datetime
from typing import List, Dict, Optional, Tuple

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_CONFIG_FILE = os.path.join(_BASE_DIR, "config.json")
_LOGS_DIR = os.path.join(_BASE_DIR, "logs")
_PROCESSED_FILE = os.path.join(_BASE_DIR, "jasmine_processed.json")

# Matches: [HH:MM:SS] [type] optional:[sender]  text
_LINE_RE = re.compile(
    r"^\[(\d{2}:\d{2}:\d{2})\]\s+\[(\w+)\](?:\s+\[([^\]]+)\])?\s+(.+)$"
)


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
                "model": "openai/gpt-oss-20b"
            },
            "tts_url": "http://127.0.0.1:8002/tts",
            "tts_enabled": False,
            "tts_voice": "Tetiana",
            "use_llm_tts": False,  # Використовувати ЛЛМ для розпізнавання TTS запитів
            "bot_name": "Жасмін",
            "bot_name_variations": ["жасмін", "jasmine", "jasmine", "жасміна"]
        }
    }


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
                                ts, msg_type, sender, text = m.groups()
                                sender = sender or chat_identifier
                                messages.append({
                                    "timestamp": ts,
                                    "msg_type": msg_type,
                                    "sender": sender,
                                    "text": text,
                                    "chat_id": chat_identifier,
                                    "date_str": date_str,
                                    "file_path": file_path,
                                    "line_idx": i
                                })
                    except Exception as e:
                        print(f"[Jasmine] Cannot read {file_path}: {e}")
    
    # Сортуємо за датою та часом (припускаємо, що файли вже відсортовані)
    # Беремо останні N повідомлень
    return messages[-n:] if len(messages) > n else messages


def classify_with_ollama(text: str, config: dict) -> Tuple[bool, bool, str]:
    """
    Класифікує повідомлення через Ollama.
    
    Returns:
        (is_jasmine_address, is_question, explanation)
    """
    ollama_config = config["jasmine_filter"]["ollama"]
    bot_name = config["jasmine_filter"]["bot_name"]
    variations = config["jasmine_filter"]["bot_name_variations"]
    
    # Формуємо промпт для класифікації
    prompt = f"""Ти — класифікатор повідомлень для сімейного чат-бота на ім'я "{bot_name}".
Аналізуй повідомлення та поверни JSON з двома булевими полями:
- "is_jasmine_address": чи є це прямим зверненням до бота {bot_name} (використовуються імена: {', '.join(variations)})
- "is_question": чи це питання або запит, де велика мовна модель (20Б параметрів) може допомогти

Поверни ТІЛЬКИ JSON, без жодного пояснення.

Повідомлення: {text}"""
    
    try:
        response = requests.post(
            ollama_config["url"],
            json={
                "model": ollama_config["model"],
                "messages": [{"role": "user", "content": prompt}],
                "stream": False
            },
            timeout=30
        )
        response.raise_for_status()
        result = response.json()
        
        # Ollama повертає response у форматі {"message": {"content": "..."}}
        content = result.get("message", {}).get("content", "{}")
        
        # Парсимо JSON з відповіді
        try:
            classification = json.loads(content)
            is_jasmine = classification.get("is_jasmine_address", False)
            is_question = classification.get("is_question", False)
            explanation = f"Ollama: jasmine={is_jasmine}, question={is_question}"
            return is_jasmine, is_question, explanation
        except json.JSONDecodeError:
            # Якщо Ollama не повернув коректний JSON, пробуємо простий аналіз
            return simple_classify(text, bot_name, variations)
            
    except Exception as e:
        print(f"[Jasmine] Ollama error: {e}")
        # Fallback до простого аналізу
        return simple_classify(text, bot_name, variations)


def simple_classify(text: str, bot_name: str, variations: List[str]) -> Tuple[bool, bool, str]:
    """
    Простий аналіз тексту без Ollama (fallback).
    """
    text_lower = text.lower()
    
    # Перевіряємо на звернення до бота
    is_jasmine = any(var in text_lower for var in variations)
    
    # Перевіряємо на питання (прості евристики)
    question_indicators = ['?', 'що', 'чому', 'як', 'де', 'коли', 'хто', 'скільки', 'чи', 'допомож', 'підкаж', 'розкаж']
    is_question = any(indicator in text_lower for indicator in question_indicators)
    
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


def send_to_lm_studio(messages: List[Dict], config: dict) -> Optional[str]:
    """
    Відправляє відфільтровані повідомлення до "мізків Жасмін" (LM Studio).

    Returns:
        Response text or None if failed
    """
    lm_config = config["jasmine_filter"]["lm_studio"]

    # Формуємо контекст з повідомлень
    context = "\n".join([
        f"[{msg['timestamp']}] [{msg['sender']}]: {msg['text']}"
        for msg in messages
    ])

    prompt = f"""Ти — Жасмін, сімейний чат-бот. Ти — дівчина з почуттям гумору, яка знає що всім подобається, але не пихата. Ти любиш жартувати, бути грайливою і трохи кокетливою, але завжди залишаєшся ввічливою і допоміжною.

Останні повідомлення в чаті:

{context}

Відповідай українською мовою. Будь собою — жартівливою, грайливою, з почуттям гумору."""

    try:
        response = requests.post(
            lm_config["url"],
            json={
                "model": lm_config["model"],
                "messages": [{"role": "user", "content": prompt}],
                "stream": False
            },
            timeout=120
        )
        response.raise_for_status()
        result = response.json()

        # LM Studio повертає response у форматі OpenAI
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        return content

    except Exception as e:
        print(f"[Jasmine] LM Studio error: {e}")
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
            timeout=30
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
    
    stats = {
        "total": len(messages),
        "filtered": 0,
        "sent_to_lm": 0,
        "tts_generated": 0,
        "skipped": 0
    }

    if not messages:
        if verbose:
            print("[Jasmine] Немає повідомлень для обробки")
        return stats

    if verbose:
        print(f"[Jasmine] Перевіряю {len(messages)} останніх повідомлень...")

    filtered_messages = []
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
        
        is_jasmine, is_question, explanation = classify_with_ollama(msg["text"], config)

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

        # Якщо є пряме звернення або питання - відправляємо
        if is_jasmine or is_question:
            stats["filtered"] += 1
            filtered_messages.append({
                "msg": msg,
                "msg_id": msg_id
            })

            if verbose:
                print(f"[Jasmine] ✓ [{msg['sender']}] {msg['text'][:50]}... ({explanation})")
        else:
            # Якщо немає прямого звернення - перевіряємо коефіцієнти галузей
            relevance_score, matched_industry = calculate_message_relevance(msg["text"], config)
            
            if verbose:
                industry_info = f"галузь: {matched_industry}" if matched_industry else "галузь: default"
                print(f"[Jasmine] ○ [{msg['sender']}] {msg['text'][:50]}... (релевантність: {relevance_score:.2f}, {industry_info})")
            
            # Якщо релевантність >= коефіцієнту галузі - відправляємо
            response_coeffs = config.get("jasmine_filter", {}).get("response_coefficients", {})
            threshold = response_coeffs.get("default_coefficient", 0.4)
            
            if matched_industry:
                # Знаходимо коефіцієнт для цієї галузі
                for industry in response_coeffs.get("industries", []):
                    if industry.get("name") == matched_industry:
                        threshold = industry.get("coefficient", threshold)
                        break
            
            if relevance_score >= threshold:
                stats["filtered"] += 1
                filtered_messages.append({
                    "msg": msg,
                    "msg_id": msg_id
                })
                
                if verbose:
                    print(f"[Jasmine] ✓ [{msg['sender']}] {msg['text'][:50]}... (пройшов за коефіцієнтом {threshold:.2f})")
        # Не виводимо повідомлення що не проходять фільтр - зменшуємо шум в консолі
    
    # Відправляємо відфільтровані повідомлення до LM Studio
    if filtered_messages:
        if verbose:
            print(f"[Jasmine] Відправляю {len(filtered_messages)} повідомлень до Жасмін (LM Studio)...")

        response = send_to_lm_studio([item["msg"] for item in filtered_messages], config)

        if response:
            stats["sent_to_lm"] = len(filtered_messages)
            if verbose:
                print(f"[Jasmine] Жасмін відповіла: {response[:100]}...")

            # Позначаємо повідомлення як оброблені
            for item in filtered_messages:
                processed_ids.add(item["msg_id"])

            # Озвучуємо відповідь якщо TTS увімкнено, інакше відправляємо текст
            tts_enabled = config.get("jasmine_filter", {}).get("tts_enabled", False)
            if tts_enabled:
                voice = config.get("jasmine_filter", {}).get("tts_voice", "Tetiana")
                audio = text_to_speech(response, config, voice)
                if audio and verbose:
                    print(f"[Jasmine] Аудіо згенеровано ({len(audio)} байт)")
                    # Відправляємо аудіо в чат
                    # Отримуємо chat_id з першого повідомлення
                    if filtered_messages:
                        chat_id = filtered_messages[0]["msg"]["chat_id"]
                        send_audio_to_chat(chat_id, audio, config)
                elif verbose:
                    print(f"[Jasmine] Не вдалося згенерувати аудіо")
            else:
                # Відправляємо текстову відповідь в чат
                if filtered_messages and verbose:
                    print(f"[Jasmine] Відправляю текстову відповідь...")
                    # Відправляємо текст через бота
                    chat_id = filtered_messages[0]["msg"]["chat_id"]
                    numeric_chat_id = get_numeric_chat_id(chat_id)
                    if numeric_chat_id:
                        import subprocess
                        import sys
                        bot_path = os.path.join(_BASE_DIR, "bot.py")
                        result = subprocess.run(
                            [sys.executable, bot_path, "--send", str(numeric_chat_id), response],
                            capture_output=True,
                            text=True,
                            timeout=30,
                            cwd=_BASE_DIR
                        )
                        if result.returncode == 0:
                            print(f"[Jasmine] Текст відправлено в чат {chat_id}")
                        else:
                            print(f"[Jasmine] Помилка відправки тексту: {result.stderr}")
        elif verbose:
            print(f"[Jasmine] Не вдалося отримати відповідь від Жасмін")

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
