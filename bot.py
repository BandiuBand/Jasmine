import os
import sys
import json
import time
from datetime import datetime
import requests
from telegram import Update, Chat
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes, CommandHandler
from telegram.request import HTTPXRequest

from jasmine_v2.transport.telegram_shadow import run_telegram_shadow_event

# 1) Налаштування
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN and os.path.exists("tockenBot.txt"):
    with open("tockenBot.txt", "r", encoding="utf-8") as f:
        BOT_TOKEN = f.read().strip()

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set and tockenBot.txt was not found or empty")

# URL вашого Whisper-сервера (FastAPI) для транскрипції
WHISPER_TRANSCRIBE_URL = os.getenv("WHISPER_TRANSCRIBE_URL", "http://localhost:8002/transcribe")

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_REGISTRY_FILE = os.path.join(_BASE_DIR, "logs", "chat_registry.json")
_CONFIG_FILE = os.path.join(_BASE_DIR, "config.json")


def _load_config() -> dict:
    """Завантажує config.json, повертає порожній dict при помилці."""
    try:
        with open(_CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _update_registry(identifier: str, chat_id: int):
    """Зберігає маппінг identifier → chat_id для відправки повідомлень"""
    os.makedirs(os.path.dirname(_REGISTRY_FILE), exist_ok=True)
    registry = {}
    if os.path.exists(_REGISTRY_FILE):
        try:
            with open(_REGISTRY_FILE, "r", encoding="utf-8") as f:
                registry = json.load(f)
        except Exception:
            pass
    registry[identifier] = chat_id
    with open(_REGISTRY_FILE, "w", encoding="utf-8") as f:
        json.dump(registry, f, ensure_ascii=False, indent=2)

def save_message(chat_id: int, chat_title: str, text: str,
                 message_type: str = "text", sender: str = "", chat_type: str = "unknown"):
    """Зберігає повідомлення в структуру logs/рік/місяць/день/чат.txt"""
    now = datetime.now()
    log_dir = os.path.join(_BASE_DIR, "logs", str(now.year), f"{now.month:02d}", f"{now.day:02d}")
    os.makedirs(log_dir, exist_ok=True)

    # Ім'я файлу: назва чату або chat_id (для груп)
    safe_title = "".join(c if c.isalnum() or c in "_- " else "_" for c in chat_title)
    identifier = safe_title.strip() or str(chat_id)
    log_file = os.path.join(log_dir, f"{identifier}.txt")

    # Зберігаємо маппінг identifier → числовий chat_id
    _update_registry(identifier, chat_id)

    timestamp = now.strftime("%H:%M:%S")
    chat_type_part = f" [{chat_type}]" if chat_type else ""
    sender_part = f" [{sender}]" if sender else ""
    log_entry = f"[{timestamp}] [{message_type}]{chat_type_part}{sender_part} {text}\n"

    with open(log_file, "a", encoding="utf-8") as f:
        f.write(log_entry)

async def transcribe_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.voice:
        return

    user = update.effective_user
    chat = update.effective_chat
    tg_file = await context.bot.get_file(update.message.voice.file_id)
    bio = await tg_file.download_as_bytearray()

    try:
        resp = requests.post(
            WHISPER_TRANSCRIBE_URL,
            files={"file": ("voice.ogg", bio, "audio/ogg")},
            timeout=300,
        )
        resp.raise_for_status()
        result = resp.json()
        text = result.get("text", "Не вдалося розпізнати текст.")
    except Exception:
        text = "Помилка при обробці аудіо."

    # Зберігаємо транскрипцію в логи
    if text and text != "null":
        chat_title = chat.title or chat.username or str(chat.id)
        sender = user.username or user.first_name or str(user.id)
        save_message(chat.id, chat_title, text, "voice", sender, chat.type)
        await update.message.reply_text(text)

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробляє текстові повідомлення і зберігає їх в логи"""
    if not update.message or not update.message.text:
        return

    user = update.effective_user
    chat = update.effective_chat
    text = update.message.text

    chat_title = chat.title or chat.username or str(chat.id)
    sender = user.username or user.first_name or str(user.id) if user else ""
    save_message(chat.id, chat_title, text, "text", sender, chat.type)

    # Jasmine v2 shadow mode - не впливає на стару логіку
    config = _load_config()
    v2_cfg = config.get("jasmine_v2", {})
    if v2_cfg.get("enabled", False):
        try:
            message = update.effective_message
            if message and message.text:
                run_telegram_shadow_event(
                    chat_id=chat.id if chat else "unknown",
                    user_id=user.id if user else "unknown",
                    user_name=user.full_name if user else None,
                    text=message.text,
                    raw={
                        "message_id": message.message_id,
                        "chat_type": chat.type if chat else None,
                        "username": user.username if user else None,
                    },
                )
        except Exception as exc:
            print(f"[Jasmine v2 shadow] error: {exc}")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показує chat_id при команді /start"""
    chat = update.effective_chat
    user = update.effective_user
    info = f"Chat ID: {chat.id}\n"
    if chat.title:
        info += f"Назва: {chat.title}\n"
    if user:
        info += f"Ім'я: {user.first_name}\n"
        if user.username:
            info += f"Username: @{user.username}\n"
    await context.bot.send_message(chat_id=chat.id, text=info)


async def voice_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Озвучує текст через TTS - використання: /voice текст"""
    if not update.message or not context.args:
        await update.message.reply_text("Використання: /voice <текст для озвучки>")
        return

    text = " ".join(context.args)

    try:
        resp = requests.post(
            WHISPER_TRANSCRIBE_URL.replace("/transcribe", "/tts"),
            json={"text": text, "voice": "Tetiana", "stress": "Dictionary"},
            timeout=60,
        )
        resp.raise_for_status()

        # Отримуємо аудіо байти
        audio_bytes = resp.content

        # Відправляємо аудіо в чат
        from io import BytesIO
        audio_file = BytesIO(audio_bytes)
        audio_file.name = "voice.wav"

        await update.message.reply_voice(audio_file)
    except Exception as e:
        await update.message.reply_text(f"Помилка при озвучці: {e}")

def _build_app_with_timeouts(read: float = 30.0, write: float = 30.0, connect: float = 15.0, pool: float = 5.0):
    """ApplicationBuilder з кастомними HTTPXRequest таймаутами для CLI режимів."""
    request = HTTPXRequest(
        connection_pool_size=8,
        read_timeout=read,
        write_timeout=write,
        connect_timeout=connect,
        pool_timeout=pool,
    )
    return (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .request(request)
        .get_updates_request(request)
        .build()
    )


async def _send_with_retry(coro_factory, attempts: int = 3, base_delay: float = 2.0):
    """Викликає coro_factory() з ретраями при помилках мережі."""
    import asyncio
    last_exc = None
    for i in range(attempts):
        try:
            return await coro_factory()
        except Exception as exc:
            last_exc = exc
            if i < attempts - 1:
                delay = base_delay * (2 ** i)
                print(f"Спроба {i+1}/{attempts} провалилась ({type(exc).__name__}: {exc}). Повтор через {delay}с...")
                await asyncio.sleep(delay)
    raise last_exc


async def send_message(chat_id: int, text: str):
    """Відправляє повідомлення від бота в зазначений чат"""
    app = _build_app_with_timeouts()
    async with app:
        await _send_with_retry(
            lambda: app.bot.send_message(chat_id=chat_id, text=text)
        )
        print(f"Повідомлення відправлено в чат {chat_id}")


async def send_voice_message(chat_id: int, audio_path: str):
    """Відправляє голосове повідомлення від бота в зазначений чат"""
    app = _build_app_with_timeouts(read=60.0, write=60.0)
    async with app:
        async def _send():
            with open(audio_path, "rb") as audio_file:
                return await app.bot.send_voice(chat_id=chat_id, voice=audio_file)
        await _send_with_retry(_send)
        print(f"Голосове повідомлення відправлено в чат {chat_id}")

def main():
    # Перевіряємо CLI аргументи
    if len(sys.argv) >= 4 and sys.argv[1] == "--send":
        # python bot.py --send <chat_id> <message>
        try:
            chat_id = int(sys.argv[2])
            message = " ".join(sys.argv[3:])
            import asyncio
            asyncio.run(send_message(chat_id, message))
        except ValueError:
            print("Помилка: chat_id має бути числом")
            sys.exit(1)
        except Exception as e:
            print(f"Помилка при відправці: {e}")
            sys.exit(1)
        return

    if len(sys.argv) >= 4 and sys.argv[1] == "--send-voice":
        # python bot.py --send-voice <chat_id> <audio_file>
        try:
            chat_id = int(sys.argv[2])
            audio_file = sys.argv[3]
            import asyncio
            asyncio.run(send_voice_message(chat_id, audio_file))
        except ValueError:
            print("Помилка: chat_id має бути числом")
            sys.exit(1)
        except Exception as e:
            print(f"Помилка при відправці голосового повідомлення: {e}")
            sys.exit(1)
        return

    # Звичайний запуск бота
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Обробник команди /start
    app.add_handler(CommandHandler("start", start_command))

    # Обробник команди /voice для озвучки тексту
    app.add_handler(CommandHandler("voice", voice_command))

    # Обробник для голосових повідомлень
    app.add_handler(MessageHandler(filters.VOICE, transcribe_voice))

    # Обробник для текстових повідомлень (приватні чати і групи)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

    # Ініціалізація з повторними спробами при мережевих помилках
    max_retries = 5
    retry_delay = 5  # seconds
    
    for attempt in range(max_retries):
        try:
            print("Bot is polling…")
            app.run_polling(allowed_updates=["message", "edited_message", "channel_post"])
            break  # If successful, exit the retry loop
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"[Bot] Помилка з'єднання: {e}")
                print(f"[Bot] Повторна спроба через {retry_delay} сек... (спроба {attempt + 1}/{max_retries})")
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                print(f"[Bot] Не вдалося підключитися після {max_retries} спроб")
                raise

if __name__ == "__main__":
    main()
