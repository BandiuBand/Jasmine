import os
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

# 1) Налаштування
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN and os.path.exists("tockenBot.txt"):
    with open("tockenBot.txt", "r", encoding="utf-8") as f:
        BOT_TOKEN = f.read().strip()

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set and tockenBot.txt was not found or empty")

# URL вашого Whisper-сервера (FastAPI) для транскрипції
WHISPER_TRANSCRIBE_URL = os.getenv("WHISPER_TRANSCRIBE_URL", "http://localhost:8002/transcribe")

async def transcribe_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.voice:
        return

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

    if text != "null":
        await update.message.reply_text(text)

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Обробник для будь-яких повідомлень
    app.add_handler(MessageHandler(filters.ALL, transcribe_voice))

    print("Bot is polling…")
    app.run_polling()

if __name__ == "__main__":
    main()