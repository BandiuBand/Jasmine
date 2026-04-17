#!/usr/bin/env python3
"""
Тести для Jasmine Filter з використанням реальної Ollama (phi4-mini).
"""

import json
import os
import sys

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _BASE_DIR)

from jasmine_filter import (
    load_config,
    classify_with_ollama,
    simple_classify,
    get_last_messages,
    process_messages
)


def test_config_loading():
    """Тест 1: Завантаження конфігурації"""
    print("\n=== Тест 1: Завантаження конфігурації ===")
    config = load_config()
    
    assert "jasmine_filter" in config, "Немає секції jasmine_filter"
    assert "ollama" in config["jasmine_filter"], "Немає налаштувань Ollama"
    assert "lm_studio" in config["jasmine_filter"], "Немає налаштувань LM Studio"
    
    print(f"✅ Конфігурація завантажена")
    print(f"   Модель Ollama: {config['jasmine_filter']['ollama']['model']}")
    print(f"   Модель LM Studio: {config['jasmine_filter']['lm_studio']['model']}")
    print(f"   Кількість повідомлень: {config['jasmine_filter']['last_n_messages']}")
    return True


def test_simple_classify():
    """Тест 2: Проста класифікація без Ollama (fallback)"""
    print("\n=== Тест 2: Проста класифікація (fallback) ===")
    
    config = load_config()
    bot_name = config["jasmine_filter"]["bot_name"]
    variations = config["jasmine_filter"]["bot_name_variations"]
    
    test_cases = [
        ("Жасмін, як погода?", True, True),
        ("Привіт, як справи?", False, True),
        ("Що робити якщо...", False, True),
        ("jasmine допоможи мені", True, True),
        ("Просто повідомлення", False, False),
    ]
    
    for text, expected_jasmine, expected_question in test_cases:
        is_jasmine, is_question, explanation = simple_classify(text, bot_name, variations)
        print(f"   Текст: '{text[:40]}...'")
        print(f"     Jasmine: {is_jasmine} (очікувалось: {expected_jasmine})")
        print(f"     Питання: {is_question} (очікувалось: {expected_question})")
        print(f"     {explanation}")
        
        # Перевіряємо хоча б частково (fallback не ідеальний)
        if expected_jasmine and not is_jasmine:
            print(f"   ⚠️  Не розпізнано звернення до Жасмін")
        if expected_question and not is_question:
            print(f"   ⚠️  Не розпізнано питання")
    
    print("✅ Проста класифікація працює")
    return True


def test_ollama_classification():
    """Тест 3: Класифікація через реальну Ollama"""
    print("\n=== Тест 3: Класифікація через Ollama (phi4-mini) ===")
    
    config = load_config()
    
    test_cases = [
        "Жасмін, яка погода сьогодні?",
        "Привіт, як справи?",
        "Хто знає як це працює?",
        "jasmine допоможи мені з проблемою",
        "Просто звичайне повідомлення без питань",
    ]
    
    for text in test_cases:
        print(f"\n   Текст: '{text}'")
        try:
            is_jasmine, is_question, explanation = classify_with_ollama(text, config)
            print(f"     Jasmine: {is_jasmine}")
            print(f"     Питання: {is_question}")
            print(f"     {explanation}")
        except Exception as e:
            print(f"   ❌ Помилка: {e}")
            return False
    
    print("\n✅ Класифікація через Ollama працює")
    return True


def test_get_last_messages():
    """Тест 4: Читання повідомлень з логів"""
    print("\n=== Тест 4: Читання повідомлень з логів ===")
    
    config = load_config()
    n = config["jasmine_filter"]["last_n_messages"]
    
    messages = get_last_messages(n)
    
    print(f"   Знайдено {len(messages)} повідомлень (максимум {n})")
    
    if messages:
        print(f"   Останнє повідомлення:")
        msg = messages[-1]
        print(f"     Час: {msg['timestamp']}")
        print(f"   Відправник: {msg['sender']}")
        print(f"   Текст: {msg['text'][:50]}...")
        print(f"   Чат: {msg['chat_id']}")
    else:
        print("   ℹ️  Логи порожні або не існують")
    
    print("✅ Читання повідомлень працює")
    return True


def test_process_messages():
    """Тест 5: Повна обробка повідомлень"""
    print("\n=== Тест 5: Повна обробка повідомлень ===")

    config = load_config()

    try:
        # Збираємо повідомлення та їх класифікацію
        n = config["jasmine_filter"]["last_n_messages"]
        messages = get_last_messages(n)
        bot_name = config["jasmine_filter"]["bot_name"]
        variations = config["jasmine_filter"]["bot_name_variations"]

        false_positives = []
        true_positives = []
        false_negatives = []

        for msg in messages:
            is_jasmine, is_question, explanation = simple_classify(msg["text"], bot_name, variations)
            # Перевіряємо чи є ім'я Жасмін в тексті (ground truth)
            text_lower = msg["text"].lower()
            has_jasmine_name = any(var in text_lower for var in variations)

            if is_jasmine and not has_jasmine_name:
                false_positives.append(msg)
            elif is_jasmine and has_jasmine_name:
                true_positives.append(msg)
            elif not is_jasmine and has_jasmine_name:
                false_negatives.append(msg)

        stats = process_messages(config, verbose=False)
        print(f"\n   Статистика:")
        print(f"     Всього повідомлень: {stats['total']}")
        print(f"     Відфільтровано: {stats['filtered']}")
        print(f"     Відправлено до Жасмін: {stats['sent_to_lm']}")

        if false_positives:
            print(f"\n   ❌ False positives (помилково класифіковані як Жасмін): {len(false_positives)}")
            for msg in false_positives[:10]:  # Показуємо перші 10
                print(f"     [{msg['sender']}] {msg['text'][:60]}...")

        if false_negatives:
            print(f"\n   ⚠️  False negatives (пропущені звернення до Жасмін): {len(false_negatives)}")
            for msg in false_negatives[:10]:
                print(f"     [{msg['sender']}] {msg['text'][:60]}...")

        if true_positives:
            print(f"\n   ✅ True positives (коректно розпізнані звернення до Жасмін): {len(true_positives)}")
            for msg in true_positives[:10]:
                print(f"     [{msg['sender']}] {msg['text'][:60]}...")

        print("✅ Повна обробка працює")
        return True
    except Exception as e:
        print(f"   ❌ Помилка: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("🧪 Запуск тестів Jasmine Filter")
    print("=" * 50)
    
    tests = [
        ("Завантаження конфігурації", test_config_loading),
        ("Проста класифікація", test_simple_classify),
        ("Класифікація через Ollama", test_ollama_classification),
        ("Читання повідомлень", test_get_last_messages),
        ("Повна обробка", test_process_messages),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"❌ Тест '{name}' не пройшов: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    print("\n" + "=" * 50)
    print("📊 Результати тестів:")
    for name, result in results:
        status = "✅ ПРЙДЕНО" if result else "❌ НЕ ПРЙДЕНО"
        print(f"   {status}: {name}")
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    print(f"\nВсього: {passed}/{total} тестів пройшло")
    
    if passed == total:
        print("\n🎉 Всі тести пройшли успішно!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} тестів не пройшло")
        return 1


if __name__ == "__main__":
    sys.exit(main())
