#!/usr/bin/env python3
"""
Тестовий скрипт для української TTS
"""
# Патчимо stanza ПЕРЕД будь-якими імпортами
import stanza_patch  # noqa: F401

from ukrainian_tts.tts import TTS, Voices, Stress
import torch

print("Завантаження TTS моделі...")
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Використовую пристрій: {device}")

tts = TTS(device=device)
print("Модель завантажено!")

# Тестовий текст
test_text = "Привіт! Я Жасмін, ваш сімейний помічник. Сьогодні чудовий день для нових відкриттів!"
print(f"\nТекст для озвучки: {test_text}")

# Генерація аудіо
output_file = "test_output.wav"
voice = Voices.Tetiana  # Жіночий голос
stress = Stress.Dictionary

print(f"\nГенерація аудіо (голос: {voice.name}, наголоси: {stress.name})...")

with open(output_file, "wb") as f:
    _, accented_text = tts.tts(test_text, voice.value, stress.value, f)
    print(f"Текст з наголосами: {accented_text}")

print(f"\n✅ Аудіо збережено у файл: {output_file}")
print(f"Розмір файлу: {len(open(output_file, 'rb').read())} байт")
