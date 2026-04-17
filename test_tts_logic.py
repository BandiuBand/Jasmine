#!/usr/bin/env python3
"""
Тестовий скрипт для логіки розпізнавання TTS запитів з ЛЛМ
"""

import sys
import os

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _BASE_DIR)

from jasmine_filter import detect_tts_request, load_config

config = load_config()

# Тестові повідомлення
test_messages = [
    "озвуч це привіт світ",
    "Жасмін, скажи голосом: сьогодні чудовий день",
    "прочитай вголос «цитата в лапках»",
    "озвуч попереднє повідомлення",
    "запиши голосом те що вище",
    "просто повідомлення без озвучки",
    "озвуч «тестова цитата» будь ласка",
    "произнеси останнє повідомлення",
    # Складніші приклади для ЛЛМ
    "можеш ти це прочитати вголос?",
    "хотілось би почути це голосом",
    "зроби так щоб це звучало",
    "це треба озвучити",
]

print("Тестування логіки розпізнавання TTS запитів (без ЛЛМ):\n")

for msg in test_messages:
    is_tts, text_to_speak = detect_tts_request(msg, config, use_llm=False)
    print(f"Повідомлення: {msg}")
    print(f"  TTS запит: {is_tts}")
    print(f"  Текст для озвучки: {text_to_speak}")
    print()

print("\n" + "="*50 + "\n")
print("Тестування логіки розпізнавання TTS запитів (з ЛЛМ):\n")

for msg in test_messages:
    is_tts, text_to_speak = detect_tts_request(msg, config, use_llm=True)
    print(f"Повідомлення: {msg}")
    print(f"  TTS запит: {is_tts}")
    print(f"  Текст для озвучки: {text_to_speak}")
    print()
