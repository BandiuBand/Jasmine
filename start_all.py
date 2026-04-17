#!/usr/bin/env python3
import subprocess
import sys
import os
import signal
import json
import time
import requests

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
_CONFIG_FILE = os.path.join(PROJECT_DIR, "config.json")


def load_config() -> dict:
    """Завантажує конфігурацію з config.json"""
    if os.path.exists(_CONFIG_FILE):
        with open(_CONFIG_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def wait_for_server(url: str, timeout: int = 60, service_name: str = "server") -> bool:
    """
    Чекає поки сервер стане доступним.
    
    Args:
        url: URL для перевірки (наприклад, http://127.0.0.1:8002)
        timeout: Максимальний час очікування в секундах
        service_name: Назва сервісу для логування
    
    Returns:
        True якщо сервер доступний, False якщо тайм-аут
    """
    print(f"[{service_name}] Очікування готовності...")
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        try:
            response = requests.get(url, timeout=2)
            if response.status_code == 200:
                print(f"[{service_name}] ✅ Готовий")
                return True
        except:
            pass
        time.sleep(1)
    
    print(f"[{service_name}] ⚠️  Не вдалося дочекатися готовності за {timeout} сек")
    return False


def main():
    config = load_config()

    # Читаємо налаштування з config.json
    kg_watch_enabled = config.get("kg_watch", {}).get("enabled", False)
    jasmine_filter_enabled = config.get("jasmine_filter", {}).get("enabled", False)
    kg_cleanup_enabled = config.get("kg_cleanup", {}).get("enabled", False)

    # Рахуємо загальну кількість сервісів
    total_services = 3  # bot, server, admin
    if kg_watch_enabled:
        total_services += 1
    if jasmine_filter_enabled:
        total_services += 1
    if kg_cleanup_enabled:
        total_services += 1

    print("🚀 Запуск всіх сервісів...")
    print("📝 Bot (bot.py)")
    print("🎤 Whisper Server (server.py)")
    print("🌐 Admin Interface (admin.py)")
    if kg_watch_enabled:
        print("🧠 Knowledge Graph (kg_tool.py --watch)")
    if jasmine_filter_enabled:
        print("🌸 Jasmine Filter (jasmine_filter.py --watch)")
    if kg_cleanup_enabled:
        print("🧹 KG Cleanup (kg_cleanup.py)")
    print("=" * 50)
    
    processes = []
    
    try:
        # Запуск бота
        print("\n[1/{}] Запуск бота...".format(total_services))
        bot_process = subprocess.Popen([sys.executable, "bot.py"], cwd=PROJECT_DIR)
        processes.append(("Bot", bot_process))
        print("✅ Bot запущено")

        # Запуск Whisper сервера
        print("\n[2/{}] Запуск Whisper сервера...".format(total_services))
        server_process = subprocess.Popen([sys.executable, "server.py"], cwd=PROJECT_DIR)
        processes.append(("Whisper Server", server_process))
        print("✅ Whisper Server запущено")
        
        # Чекаємо поки Whisper Server стане готовим
        wait_for_server("http://127.0.0.1:8002", timeout=60, service_name="Whisper Server")

        # Запуск адмін інтерфейсу
        print("\n[3/{}] Запуск адмін інтерфейсу...".format(total_services))
        admin_process = subprocess.Popen([sys.executable, "admin.py"], cwd=PROJECT_DIR)
        processes.append(("Admin Interface", admin_process))
        print("✅ Admin Interface запущено")

        step_num = 4
        if kg_watch_enabled:
            print("\n[{}/{}] Запуск Knowledge Graph watch...".format(step_num, total_services))
            kg_process = subprocess.Popen(
                [sys.executable, "kg_tool.py", "--watch"], cwd=PROJECT_DIR
            )
            processes.append(("Knowledge Graph", kg_process))
            print("✅ Knowledge Graph watch запущено")
            step_num += 1

        if jasmine_filter_enabled:
            print("\n[{}/{}] Запуск Jasmine Filter...".format(step_num, total_services))
            jasmine_process = subprocess.Popen(
                [sys.executable, "jasmine_filter.py", "--watch"], cwd=PROJECT_DIR
            )
            processes.append(("Jasmine Filter", jasmine_process))
            print("✅ Jasmine Filter запущено")
            step_num += 1

        if kg_cleanup_enabled:
            print("\n[{}/{}] Запуск KG Cleanup...".format(step_num, total_services))
            kg_cleanup_process = subprocess.Popen(
                [sys.executable, "kg_cleanup.py"], cwd=PROJECT_DIR
            )
            processes.append(("KG Cleanup", kg_cleanup_process))
            print("✅ KG Cleanup запущено")

        print("\n" + "=" * 50)
        print("🎉 Всі сервіси запущено успішно!")
        print("\n📍 Доступні адреси:")
        print("   - Bot: працює в Telegram")
        print("   - Whisper Server: http://localhost:8002")
        print("   - Admin Interface: http://localhost:8005")
        print("\n⚠️  Натисни Ctrl+C для зупинки всіх сервісів")
        print("=" * 50 + "\n")
        
        # Чекаємо завершення процесів
        for name, process in processes:
            process.wait()
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Отримано сигнал зупинки...")
        print("🛑 Зупинка всіх сервісів...")
        
        for name, process in processes:
            print(f"Зупинка {name}...", end=" ")
            try:
                process.terminate()
                process.wait(timeout=5)
                print("✅")
            except subprocess.TimeoutExpired:
                print("⚠️  примусово...")
                process.kill()
                print("✅")
        
        print("\n👋 Всі сервіси зупинено.")
        
    except Exception as e:
        print(f"\n❌ Помилка: {e}")
        print("🛑 Зупинка всіх сервісів...")
        
        for name, process in processes:
            try:
                process.terminate()
                process.wait(timeout=5)
            except:
                process.kill()

if __name__ == "__main__":
    main()
