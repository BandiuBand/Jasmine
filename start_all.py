#!/usr/bin/env python3
import subprocess
import sys
import os
import signal
import json
import time
import requests

# Відключаємо завантаження Stanza ПЕРЕД будь-якими імпортами
os.environ["STANZA_RESOURCES_DIR"] = "/home/bandiu/.cache/stanza"
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["UKRAINIAN_TTS_CACHE_DIR"] = os.path.dirname(os.path.abspath(__file__))

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
_CONFIG_FILE = os.path.join(PROJECT_DIR, "config.json")
DEFAULT_GRAPHITI_SERVICE_DIR = os.path.expanduser("~/PycharmProjects/graphiti-local-memory")


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


def is_server_ready(url: str, timeout: int = 2) -> bool:
    try:
        response = requests.get(url, timeout=timeout)
        return response.status_code == 200
    except requests.RequestException:
        return False


def ensure_graphiti_service(graphiti_config: dict, env: dict) -> subprocess.Popen | None:
    if not graphiti_config.get("enabled", False):
        return None
    if not graphiti_config.get("auto_start_service", True):
        return None

    base_url = str(graphiti_config.get("url", "http://127.0.0.1:8088")).rstrip("/")
    health_url = f"{base_url}/health"
    if is_server_ready(health_url):
        print("[Graphiti Service] ✅ Вже запущений")
        return None

    service_dir = os.path.expanduser(
        str(graphiti_config.get("service_dir", DEFAULT_GRAPHITI_SERVICE_DIR))
    )
    run_script = os.path.join(service_dir, "scripts", "run_api.sh")
    if not os.path.exists(run_script):
        raise FileNotFoundError(f"Не знайдено Graphiti run script: {run_script}")

    print("[Graphiti Service] Не відповідає, запускаю...")
    process = subprocess.Popen(["bash", run_script], cwd=service_dir, env=env)
    timeout = int(graphiti_config.get("startup_timeout_seconds", 90))
    if not wait_for_server(health_url, timeout=timeout, service_name="Graphiti Service"):
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
        raise RuntimeError("Graphiti Service не стартував")
    return process


def main():
    config = load_config()

    # Читаємо налаштування з config.json
    kg_watch_enabled = config.get("kg_watch", {}).get("enabled", False)
    jasmine_filter_enabled = config.get("jasmine_filter", {}).get("enabled", False)
    graphiti_config = config.get("jasmine_filter", {}).get("graphiti_memory", {})
    graphiti_worker_enabled = bool(
        graphiti_config.get("enabled", False)
        and graphiti_config.get("ingest_episodes", True)
        and graphiti_config.get("ingest_mode", "queue") == "queue"
    )
    kg_cleanup_enabled = config.get("kg_cleanup", {}).get("enabled", False)

    graphiti_service_autostart = bool(
        graphiti_config.get("enabled", False)
        and graphiti_config.get("auto_start_service", True)
    )

    # Рахуємо загальну кількість сервісів
    total_services = 3  # bot, server, admin
    if graphiti_service_autostart:
        total_services += 1
    if kg_watch_enabled:
        total_services += 1
    if jasmine_filter_enabled:
        total_services += 1
    if graphiti_worker_enabled:
        total_services += 1
    if kg_cleanup_enabled:
        total_services += 1

    print("🚀 Запуск всіх сервісів...")
    print("📝 Bot (bot.py)")
    print("🎤 Whisper Server (server.py)")
    print("🌐 Admin Interface (admin.py)")
    if graphiti_service_autostart:
        print("🧠 Graphiti Service (graphiti-local-memory)")
    if kg_watch_enabled:
        print("🧠 Knowledge Graph (kg_tool.py --watch)")
    if jasmine_filter_enabled:
        print("🌸 Jasmine Filter (jasmine_filter.py --watch)")
    if graphiti_worker_enabled:
        print("🧠 Graphiti Worker (graphiti_ingest_worker.py --watch)")
    if kg_cleanup_enabled:
        print("🧹 KG Cleanup (kg_cleanup.py)")
    print("=" * 50)
    
    processes = []
    
    try:
        # Підготовка оточення для дочірніх процесів (вимикаємо stanza завантаження)
        env = os.environ.copy()
        env["STANZA_RESOURCES_DIR"] = "/home/bandiu/.cache/stanza"
        env["HF_HUB_OFFLINE"] = "1"
        env["TRANSFORMERS_OFFLINE"] = "1"
        env["UKRAINIAN_TTS_CACHE_DIR"] = PROJECT_DIR

        step_num = 1
        if graphiti_service_autostart:
            print("\n[{}/{}] Перевірка Graphiti Service...".format(step_num, total_services))
            graphiti_service_process = ensure_graphiti_service(graphiti_config, env)
            if graphiti_service_process is not None:
                processes.append(("Graphiti Service", graphiti_service_process))
                print("✅ Graphiti Service запущено")
            step_num += 1
        
        # Запуск бота
        print("\n[{}/{}] Запуск бота...".format(step_num, total_services))
        bot_process = subprocess.Popen([sys.executable, "bot.py"], cwd=PROJECT_DIR, env=env)
        processes.append(("Bot", bot_process))
        print("✅ Bot запущено")
        step_num += 1

        # Запуск Whisper сервера
        print("\n[{}/{}] Запуск Whisper сервера...".format(step_num, total_services))
        server_process = subprocess.Popen([sys.executable, "server.py"], cwd=PROJECT_DIR, env=env)
        processes.append(("Whisper Server", server_process))
        print("✅ Whisper Server запущено")
        step_num += 1
        
        # Чекаємо поки Whisper Server стане готовим
        wait_for_server("http://127.0.0.1:8002", timeout=60, service_name="Whisper Server")

        # Запуск адмін інтерфейсу
        print("\n[{}/{}] Запуск адмін інтерфейсу...".format(step_num, total_services))
        admin_process = subprocess.Popen([sys.executable, "admin.py"], cwd=PROJECT_DIR, env=env)
        processes.append(("Admin Interface", admin_process))
        print("✅ Admin Interface запущено")
        step_num += 1
        if kg_watch_enabled:
            print("\n[{}/{}] Запуск Knowledge Graph watch...".format(step_num, total_services))
            kg_process = subprocess.Popen(
                [sys.executable, "kg_tool.py", "--watch"], cwd=PROJECT_DIR, env=env
            )
            processes.append(("Knowledge Graph", kg_process))
            print("✅ Knowledge Graph watch запущено")
            step_num += 1

        if jasmine_filter_enabled:
            print("\n[{}/{}] Запуск Jasmine Filter...".format(step_num, total_services))
            jasmine_process = subprocess.Popen(
                [sys.executable, "jasmine_filter.py", "--watch"], cwd=PROJECT_DIR, env=env
            )
            processes.append(("Jasmine Filter", jasmine_process))
            print("✅ Jasmine Filter запущено")
            step_num += 1

        if graphiti_worker_enabled:
            print("\n[{}/{}] Запуск Graphiti ingest worker...".format(step_num, total_services))
            graphiti_process = subprocess.Popen(
                [sys.executable, "graphiti_ingest_worker.py", "--watch"], cwd=PROJECT_DIR, env=env
            )
            processes.append(("Graphiti Worker", graphiti_process))
            print("✅ Graphiti ingest worker запущено")
            step_num += 1

        if kg_cleanup_enabled:
            print("\n[{}/{}] Запуск KG Cleanup...".format(step_num, total_services))
            kg_cleanup_process = subprocess.Popen(
                [sys.executable, "kg_cleanup.py"], cwd=PROJECT_DIR, env=env
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
