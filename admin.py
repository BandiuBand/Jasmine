import os
import sys
import json
from datetime import datetime
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn
import asyncio
from telegram import Bot

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kg.store import KnowledgeGraph

# Імпорт функції відправки повідомлень з bot.py
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BOT_TOKEN = os.getenv("BOT_TOKEN")
_token_file = os.path.join(_BASE_DIR, "tockenBot.txt")
if not BOT_TOKEN and os.path.exists(_token_file):
    with open(_token_file, "r", encoding="utf-8") as f:
        BOT_TOKEN = f.read().strip()

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set and tockenBot.txt was not found or empty")

# Knowledge Graph configuration
GRAPH_PATH = os.path.join(_BASE_DIR, "kg", "graph.json")
EMBED_URL = os.getenv("EMBED_URL", "http://127.0.0.1:1234/v1/embeddings")
EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-nomic-embed-text-v1.5")

app = FastAPI(title="Bot Admin Interface")

class SendMessageRequest(BaseModel):
    chat_id: str
    message: str

def _load_registry() -> dict:
    """Завантажує chat_registry.json: {identifier: chat_id}"""
    registry_file = os.path.join(_BASE_DIR, "logs", "chat_registry.json")
    if os.path.exists(registry_file):
        try:
            with open(registry_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def get_chats_from_logs():
    """Сканує папку logs і повертає список чатів з якими була взаємодія"""
    chats = {}
    logs_dir = os.path.join(_BASE_DIR, "logs")
    registry = _load_registry()

    if not os.path.exists(logs_dir):
        return []

    for year in os.listdir(logs_dir):
        year_path = os.path.join(logs_dir, year)
        if not os.path.isdir(year_path):
            continue

        for month in os.listdir(year_path):
            month_path = os.path.join(year_path, month)
            if not os.path.isdir(month_path):
                continue

            for day in os.listdir(month_path):
                day_path = os.path.join(month_path, day)
                if not os.path.isdir(day_path):
                    continue

                for chat_file in os.listdir(day_path):
                    if chat_file.endswith(".txt"):
                        identifier = chat_file[:-4]
                        file_path = os.path.join(day_path, chat_file)

                        mtime = os.path.getmtime(file_path)
                        last_activity = datetime.fromtimestamp(mtime)

                        # Реальний chat_id з реєстру або сам identifier
                        real_chat_id = registry.get(identifier, identifier)

                        if identifier not in chats or chats[identifier]["last_activity"] < last_activity:
                            chats[identifier] = {
                                "identifier": identifier,
                                "chat_id": str(real_chat_id),
                                "last_activity": last_activity,
                            }

    sorted_chats = sorted(chats.values(), key=lambda x: x["last_activity"], reverse=True)
    return sorted_chats

def get_chat_messages(chat_identifier: str, limit: int = 50):
    """Отримує повідомлення з логів для конкретного чату"""
    logs_dir = "logs"
    messages = []
    
    logs_dir = os.path.join(_BASE_DIR, logs_dir)
    if not os.path.exists(logs_dir):
        return messages
    
    for year in os.listdir(logs_dir):
        year_path = os.path.join(logs_dir, year)
        if not os.path.isdir(year_path):
            continue
            
        for month in os.listdir(year_path):
            month_path = os.path.join(year_path, month)
            if not os.path.isdir(month_path):
                continue
                
            for day in os.listdir(month_path):
                day_path = os.path.join(month_path, day)
                if not os.path.isdir(day_path):
                    continue
                    
                file_path = os.path.join(day_path, f"{chat_identifier}.txt")
                if os.path.exists(file_path):
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            for line in f:
                                line = line.strip()
                                if line:
                                    messages.append(line)
                    except Exception as e:
                        print(f"Error reading {file_path}: {e}")
    
    # Обмежуємо кількість повідомлень і сортуємо в зворотному порядку
    messages = messages[-limit:]
    return messages

async def send_message_to_chat(chat_id: str, message: str):
    """Відправляє повідомлення в чат через Telegram API"""
    bot = Bot(token=BOT_TOKEN)
    try:
        await bot.send_message(chat_id=int(chat_id), text=message)
        return True
    except Exception as e:
        print(f"Error sending message: {e}")
        return False
    finally:
        await bot.close()

@app.get("/", response_class=HTMLResponse)
async def admin_interface():
    """Повертає HTML інтерфейс адмінки для чатів"""
    html_content = """
    <!DOCTYPE html>
    <html lang="uk">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Bot Admin Interface</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                padding: 20px;
            }
            
            .container {
                max-width: 1200px;
                margin: 0 auto;
                background: white;
                border-radius: 20px;
                box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
                overflow: hidden;
            }
            
            .header {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 30px;
                text-align: center;
            }
            
            .header h1 {
                font-size: 2.5em;
                margin-bottom: 10px;
            }
            
            .header p {
                opacity: 0.9;
                font-size: 1.1em;
            }
            
            .content {
                padding: 30px;
            }
            
            .chats-section {
                margin-bottom: 30px;
            }
            
            .section-title {
                font-size: 1.8em;
                color: #333;
                margin-bottom: 20px;
                padding-bottom: 10px;
                border-bottom: 3px solid #667eea;
            }
            
            .chats-grid {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
                gap: 20px;
            }
            
            .chat-card {
                background: #f8f9fa;
                border-radius: 15px;
                padding: 20px;
                cursor: pointer;
                transition: all 0.3s ease;
                border: 2px solid transparent;
            }
            
            .chat-card:hover {
                transform: translateY(-5px);
                box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1);
                border-color: #667eea;
            }
            
            .chat-card.selected {
                border-color: #667eea;
                background: #e8eaf6;
            }
            
            .chat-name {
                font-size: 1.3em;
                font-weight: bold;
                color: #333;
                margin-bottom: 10px;
            }
            
            .chat-info {
                color: #666;
                font-size: 0.9em;
            }
            
            .send-section {
                background: #f8f9fa;
                border-radius: 15px;
                padding: 25px;
            }
            
            .form-group {
                margin-bottom: 20px;
            }
            
            .form-group label {
                display: block;
                margin-bottom: 8px;
                font-weight: bold;
                color: #333;
            }
            
            .form-group input, 
            .form-group textarea {
                width: 100%;
                padding: 12px;
                border: 2px solid #ddd;
                border-radius: 8px;
                font-size: 1em;
                transition: border-color 0.3s ease;
            }
            
            .form-group input:focus,
            .form-group textarea:focus {
                outline: none;
                border-color: #667eea;
            }
            
            .form-group textarea {
                min-height: 120px;
                resize: vertical;
            }
            
            .send-button {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border: none;
                padding: 15px 40px;
            font-size: 1.1em;
                border-radius: 8px;
                cursor: pointer;
                transition: all 0.3s ease;
                font-weight: bold;
            }
            
            .send-button:hover {
                transform: translateY(-2px);
                box-shadow: 0 5px 20px rgba(102, 126, 234, 0.4);
            }
            
            .send-button:disabled {
                opacity: 0.6;
                cursor: not-allowed;
                transform: none;
            }
            
            .messages-section {
                margin-top: 30px;
                display: none;
            }
            
            .messages-section.active {
                display: block;
            }
            
            .messages-list {
                background: #f8f9fa;
                border-radius: 15px;
                padding: 20px;
                max-height: 400px;
                overflow-y: auto;
            }
            
            .message-item {
                padding: 10px;
                border-bottom: 1px solid #ddd;
                font-size: 0.9em;
            }
            
            .message-item:last-child {
                border-bottom: none;
            }
            
            .message-time {
                color: #667eea;
                font-weight: bold;
                margin-right: 10px;
            }
            
            .message-type {
                display: inline-block;
                padding: 2px 8px;
                border-radius: 4px;
                font-size: 0.8em;
                margin-right: 10px;
            }
            
            .message-type.voice {
                background: #e8f5e9;
                color: #2e7d32;
            }
            
            .message-type.text {
                background: #e3f2fd;
                color: #1565c0;
            }
            
            .alert {
                padding: 15px;
                border-radius: 8px;
                margin-bottom: 20px;
                display: none;
            }
            
            .alert.success {
                background: #d4edda;
                color: #155724;
                border: 1px solid #c3e6cb;
            }
            
            .alert.error {
                background: #f8d7da;
                color: #721c24;
                border: 1px solid #f5c6cb;
            }
            
            .alert.active {
                display: block;
            }
            
            .loading {
                text-align: center;
                padding: 40px;
                color: #666;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🤖 Bot Admin Interface</h1>
                <p>Керуйте ботом через веб-інтерфейс</p>
                <div style="margin-top: 15px;">
                    <a href="/response-coefficients" style="color: white; text-decoration: none; background: rgba(255,255,255,0.2); padding: 8px 16px; border-radius: 8px; margin: 0 5px;">🎯 Коефіцієнти відповіді</a>
                    <a href="/kg" style="color: white; text-decoration: none; background: rgba(255,255,255,0.2); padding: 8px 16px; border-radius: 8px; margin: 0 5px;">🧠 Граф знань</a>
                </div>
            </div>
            
            <div class="content">
                <div class="alert success" id="successAlert">
                    Повідомлення успішно відправлено!
                </div>
                
                <div class="alert error" id="errorAlert">
                    Помилка при відправці повідомлення.
                </div>
                
                <div class="chats-section">
                    <h2 class="section-title">💬 Чати з взаємодією</h2>
                    <div class="chats-grid" id="chatsGrid">
                        <div class="loading">Завантаження чатів...</div>
                    </div>
                </div>
                
                <div class="send-section">
                    <h2 class="section-title">📤 Відправити повідомлення</h2>
                    <div class="form-group">
                        <label for="chatId">Chat ID:</label>
                        <input type="text" id="chatId" placeholder="Виберіть чат або введіть chat_id вручну">
                    </div>
                    <div class="form-group">
                        <label for="message">Повідомлення:</label>
                        <textarea id="message" placeholder="Введіть текст повідомлення..."></textarea>
                    </div>
                    <button class="send-button" id="sendButton" onclick="sendMessage()">Відправити повідомлення</button>
                </div>
                
                <div class="messages-section" id="messagesSection">
                    <h2 class="section-title">📜 Останні повідомлення</h2>
                    <div class="messages-list" id="messagesList"></div>
                </div>
            </div>
        </div>

        <script>
            let selectedChat = null;
            
            async function loadChats() {
                try {
                    console.log('Loading chats...');
                    const response = await fetch('/api/chats');
                    console.log('Response status:', response.status);

                    if (!response.ok) {
                        throw new Error(`HTTP error! status: ${response.status}`);
                    }

                    const chats = await response.json();
                    console.log('Chats loaded:', chats);

                    const grid = document.getElementById('chatsGrid');

                    if (chats.length === 0) {
                        grid.innerHTML = '<div class="loading">Чатів не знайдено. Запустіть бота і взаємодійте з ним.</div>';
                        return;
                    }

                    grid.innerHTML = chats.map(chat => `
                        <div class="chat-card" onclick="selectChat('${chat.chat_id}', '${chat.identifier}', event)">
                            <div class="chat-name">${chat.identifier}</div>
                            <div class="chat-info">Chat ID: ${chat.chat_id}</div>
                            <div class="chat-info">Остання активність: ${new Date(chat.last_activity).toLocaleString('uk-UA')}</div>
                        </div>
                    `).join('');
                } catch (error) {
                    console.error('Error loading chats:', error);
                    document.getElementById('chatsGrid').innerHTML = '<div class="loading">Помилка завантаження чатів: ' + error.message + '</div>';
                }
            }
            
            function selectChat(chatId, identifier, evt) {
                selectedChat = chatId;
                document.getElementById('chatId').value = chatId;

                document.querySelectorAll('.chat-card').forEach(card => {
                    card.classList.remove('selected');
                });
                evt.currentTarget.classList.add('selected');

                loadMessages(identifier);
            }
            
            async function loadMessages(chatIdentifier) {
                try {
                    const response = await fetch(`/api/chats/${chatIdentifier}/messages`);
                    const messages = await response.json();
                    
                    const messagesSection = document.getElementById('messagesSection');
                    const messagesList = document.getElementById('messagesList');
                    
                    if (messages.length === 0) {
                        messagesSection.classList.add('active');
                        messagesList.innerHTML = '<div class="loading">Повідомлень не знайдено.</div>';
                        return;
                    }
                    
                    messagesSection.classList.add('active');
                    messagesList.innerHTML = messages.map(msg => {
                        const typeMatch = msg.match(/\\[([0-9]{2}:[0-9]{2}:[0-9]{2})\\] \\[(\\w+)\\] (.+)/);
                        if (typeMatch) {
                            const time = typeMatch[1];
                            const type = typeMatch[2];
                            const text = typeMatch[3];
                            return `
                                <div class="message-item">
                                    <span class="message-time">${time}</span>
                                    <span class="message-type ${type}">${type}</span>
                                    <span class="message-text">${text}</span>
                                </div>
                            `;
                        }
                        return `<div class="message-item">${msg}</div>`;
                    }).join('');
                } catch (error) {
                    console.error('Error loading messages:', error);
                }
            }
            
            async function sendMessage() {
                const chatId = document.getElementById('chatId').value;
                const message = document.getElementById('message').value;
                
                if (!chatId || !message) {
                    alert('Будь ласка, заповніть всі поля.');
                    return;
                }
                
                const sendButton = document.getElementById('sendButton');
                sendButton.disabled = true;
                sendButton.textContent = 'Відправка...';
                
                try {
                    const response = await fetch('/api/send', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            chat_id: chatId,
                            message: message
                        })
                    });
                    
                    const result = await response.json();
                    
                    if (result.success) {
                        document.getElementById('successAlert').classList.add('active');
                        document.getElementById('message').value = '';
                        
                        setTimeout(() => {
                            document.getElementById('successAlert').classList.remove('active');
                        }, 3000);
                    } else {
                        document.getElementById('errorAlert').classList.add('active');
                        
                        setTimeout(() => {
                            document.getElementById('errorAlert').classList.remove('active');
                        }, 3000);
                    }
                } catch (error) {
                    console.error('Error sending message:', error);
                    document.getElementById('errorAlert').classList.add('active');
                    
                    setTimeout(() => {
                        document.getElementById('errorAlert').classList.remove('active');
                    }, 3000);
                }
                
                sendButton.disabled = false;
                sendButton.textContent = 'Відправити повідомлення';
            }
            
            // Завантажуємо чати при старті
            loadChats();
        </script>
    </body>
    </html>
    """
    return html_content

@app.get("/response-coefficients", response_class=HTMLResponse)
async def response_coefficients_interface():
    """Повертає HTML інтерфейс для керування коефіцієнтами відповіді"""
    html_content = """
    <!DOCTYPE html>
    <html lang="uk">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Коефіцієнти відповіді Жасмін</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }

            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                padding: 20px;
            }

            .container {
                max-width: 1200px;
                margin: 0 auto;
                background: white;
                border-radius: 20px;
                box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
                overflow: hidden;
            }

            .header {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 30px;
                text-align: center;
            }

            .header h1 {
                font-size: 2.5em;
                margin-bottom: 10px;
            }

            .header p {
                opacity: 0.9;
                font-size: 1.1em;
            }

            .content {
                padding: 30px;
            }

            .section-title {
                font-size: 1.8em;
                color: #333;
                margin-bottom: 20px;
                padding-bottom: 10px;
                border-bottom: 3px solid #667eea;
            }

            .default-coefficient-section {
                background: #f8f9fa;
                border-radius: 15px;
                padding: 25px;
                margin-bottom: 30px;
            }

            .form-group {
                margin-bottom: 20px;
            }

            .form-group label {
                display: block;
                margin-bottom: 8px;
                font-weight: bold;
                color: #333;
            }

            .form-group input,
            .form-group textarea {
                width: 100%;
                padding: 12px;
                border: 2px solid #ddd;
                border-radius: 8px;
                font-size: 1em;
                transition: border-color 0.3s ease;
            }

            .form-group input:focus,
            .form-group textarea:focus {
                outline: none;
                border-color: #667eea;
            }

            .form-group textarea {
                min-height: 80px;
                resize: vertical;
            }

            .form-row {
                display: grid;
                grid-template-columns: 2fr 1fr;
                gap: 15px;
            }

            .button {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border: none;
                padding: 12px 25px;
                font-size: 1em;
                border-radius: 8px;
                cursor: pointer;
                transition: all 0.3s ease;
                font-weight: bold;
            }

            .button:hover {
                transform: translateY(-2px);
                box-shadow: 0 5px 20px rgba(102, 126, 234, 0.4);
            }

            .button.danger {
                background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%);
            }

            .button.danger:hover {
                box-shadow: 0 5px 20px rgba(231, 76, 60, 0.4);
            }

            .button.secondary {
                background: #6c757d;
            }

            .button.secondary:hover {
                box-shadow: 0 5px 20px rgba(108, 117, 125, 0.4);
            }

            .industries-grid {
                display: grid;
                gap: 20px;
                margin-top: 20px;
            }

            .industry-card {
                background: #f8f9fa;
                border-radius: 15px;
                padding: 20px;
                border: 2px solid #e9ecef;
                transition: all 0.3s ease;
            }

            .industry-card:hover {
                border-color: #667eea;
                box-shadow: 0 5px 15px rgba(102, 126, 234, 0.1);
            }

            .industry-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 15px;
            }

            .industry-name {
                font-size: 1.4em;
                font-weight: bold;
                color: #333;
            }

            .coefficient-value {
                font-size: 1.2em;
                font-weight: bold;
                color: #667eea;
                background: white;
                padding: 8px 15px;
                border-radius: 8px;
            }

            .keywords-list {
                margin-bottom: 15px;
            }

            .keyword-tag {
                display: inline-block;
                background: #e3f2fd;
                color: #1565c0;
                padding: 5px 12px;
                border-radius: 15px;
                margin: 3px;
                font-size: 0.9em;
            }

            .industry-actions {
                display: flex;
                gap: 10px;
            }

            .add-industry-section {
                background: #e8eaf6;
                border-radius: 15px;
                padding: 25px;
                margin-top: 30px;
            }

            .alert {
                padding: 15px;
                border-radius: 8px;
                margin-bottom: 20px;
                display: none;
            }

            .alert.success {
                background: #d4edda;
                color: #155724;
                border: 1px solid #c3e6cb;
            }

            .alert.error {
                background: #f8d7da;
                color: #721c24;
                border: 1px solid #f5c6cb;
            }

            .alert.active {
                display: block;
            }

            .loading {
                text-align: center;
                padding: 40px;
                color: #666;
            }

            .back-link {
                display: inline-block;
                margin-bottom: 20px;
                color: white;
                text-decoration: none;
                font-weight: bold;
            }

            .back-link:hover {
                text-decoration: underline;
            }

            .help-text {
                color: #666;
                font-size: 0.9em;
                margin-top: 5px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <a href="/" class="back-link">← Назад до головної</a>
                <h1>🎯 Коефіцієнти відповіді Жасмін</h1>
                <p>Налаштуйте коефіцієнти для автоматичних відповідей Жасмін</p>
            </div>

            <div class="content">
                <div class="alert success" id="successAlert"></div>
                <div class="alert error" id="errorAlert"></div>

                <div class="default-coefficient-section">
                    <h2 class="section-title">📊 Коефіцієнт за замовчуванням</h2>
                    <div class="form-group">
                        <label for="defaultCoefficient">Коефіцієнт за замовчуванням (0.0 - 1.0):</label>
                        <input type="number" id="defaultCoefficient" step="0.1" min="0" max="1" value="0.4">
                        <p class="help-text">Цей коефіцієнт використовується, якщо повідомлення не відноситься до жодної галузі</p>
                    </div>
                    <button class="button" onclick="updateDefaultCoefficient()">Оновити коефіцієнт за замовчуванням</button>
                </div>

                <h2 class="section-title">🏭 Галузі</h2>
                <div id="industriesGrid" class="industries-grid">
                    <div class="loading">Завантаження галузей...</div>
                </div>

                <div class="add-industry-section">
                    <h3 class="section-title">➕ Додати нову галузь</h3>
                    <div class="form-group">
                        <label for="newIndustryName">Назва галузі:</label>
                        <input type="text" id="newIndustryName" placeholder="Наприклад: Фінанси">
                    </div>
                    <div class="form-group">
                        <label for="newIndustryCoefficient">Коефіцієнт (0.0 - 1.0):</label>
                        <input type="number" id="newIndustryCoefficient" step="0.1" min="0" max="1" value="0.5">
                    </div>
                    <div class="form-group">
                        <label for="newIndustryKeywords">Ключові слова (через кому):</label>
                        <textarea id="newIndustryKeywords" placeholder="Наприклад: гроші, інвестиції, банк, кредит"></textarea>
                        <p class="help-text">Ключові слова використовуються для визначення галузі повідомлення</p>
                    </div>
                    <button class="button" onclick="addIndustry()">Додати галузь</button>
                </div>
            </div>
        </div>

        <script>
            let industries = [];

            async function loadIndustries() {
                try {
                    const response = await fetch('/api/response-coefficients');
                    const data = await response.json();
                    
                    industries = data.industries || [];
                    document.getElementById('defaultCoefficient').value = data.default_coefficient || 0.4;
                    
                    renderIndustries();
                } catch (error) {
                    console.error('Error loading industries:', error);
                    showError('Помилка завантаження галузей: ' + error.message);
                }
            }

            function renderIndustries() {
                const grid = document.getElementById('industriesGrid');
                
                if (industries.length === 0) {
                    grid.innerHTML = '<div class="loading">Галузей не знайдено. Додайте першу галузь нижче.</div>';
                    return;
                }

                grid.innerHTML = industries.map(ind => `
                    <div class="industry-card" id="industry-${ind.name.replace(/\s+/g, '-')}">
                        <div class="industry-header">
                            <div class="industry-name">${ind.name}</div>
                            <div class="coefficient-value">${ind.coefficient}</div>
                        </div>
                        <div class="keywords-list">
                            ${(ind.keywords || []).map(kw => `<span class="keyword-tag">${kw}</span>`).join('')}
                        </div>
                        <div class="industry-actions">
                            <button class="button secondary" onclick="editIndustry('${ind.name}')">Редагувати</button>
                            <button class="button danger" onclick="deleteIndustry('${ind.name}')">Видалити</button>
                        </div>
                    </div>
                `).join('');
            }

            async function updateDefaultCoefficient() {
                const coefficient = parseFloat(document.getElementById('defaultCoefficient').value);
                
                if (isNaN(coefficient) || coefficient < 0 || coefficient > 1) {
                    showError('Коефіцієнт має бути числом від 0.0 до 1.0');
                    return;
                }

                try {
                    const response = await fetch('/api/response-coefficients', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            industries: industries,
                            default_coefficient: coefficient
                        })
                    });

                    const result = await response.json();
                    
                    if (result.success) {
                        showSuccess('Коефіцієнт за замовчуванням успішно оновлено');
                    } else {
                        showError('Помилка оновлення коефіцієнта');
                    }
                } catch (error) {
                    console.error('Error updating default coefficient:', error);
                    showError('Помилка оновлення: ' + error.message);
                }
            }

            async function addIndustry() {
                const name = document.getElementById('newIndustryName').value.trim();
                const coefficient = parseFloat(document.getElementById('newIndustryCoefficient').value);
                const keywordsText = document.getElementById('newIndustryKeywords').value.trim();
                
                if (!name) {
                    showError('Введіть назву галузі');
                    return;
                }

                if (isNaN(coefficient) || coefficient < 0 || coefficient > 1) {
                    showError('Коефіцієнт має бути числом від 0.0 до 1.0');
                    return;
                }

                const keywords = keywordsText.split(',').map(k => k.trim()).filter(k => k);
                
                if (keywords.length === 0) {
                    showError('Введіть хоча б одне ключове слово');
                    return;
                }

                try {
                    const response = await fetch('/api/response-coefficients/industry', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            name: name,
                            coefficient: coefficient,
                            keywords: keywords
                        })
                    });

                    const result = await response.json();
                    
                    if (result.success) {
                        showSuccess('Галузь успішно додано');
                        document.getElementById('newIndustryName').value = '';
                        document.getElementById('newIndustryCoefficient').value = '0.5';
                        document.getElementById('newIndustryKeywords').value = '';
                        loadIndustries();
                    } else {
                        showError('Помилка додавання галузі');
                    }
                } catch (error) {
                    console.error('Error adding industry:', error);
                    showError('Помилка додавання: ' + error.message);
                }
            }

            async function deleteIndustry(name) {
                if (!confirm(`Ви впевнені, що хочете видалити галузь "${name}"?`)) {
                    return;
                }

                try {
                    const response = await fetch(`/api/response-coefficients/industry/${encodeURIComponent(name)}`, {
                        method: 'DELETE'
                    });

                    const result = await response.json();
                    
                    if (result.success) {
                        showSuccess('Галузь успішно видалено');
                        loadIndustries();
                    } else {
                        showError('Помилка видалення галузі');
                    }
                } catch (error) {
                    console.error('Error deleting industry:', error);
                    showError('Помилка видалення: ' + error.message);
                }
            }

            function editIndustry(name) {
                const industry = industries.find(ind => ind.name === name);
                if (!industry) return;

                document.getElementById('newIndustryName').value = industry.name;
                document.getElementById('newIndustryCoefficient').value = industry.coefficient;
                document.getElementById('newIndustryKeywords').value = (industry.keywords || []).join(', ');
                
                // Delete the old one first (will be re-added)
                deleteIndustry(name);
            }

            function showSuccess(message) {
                const alert = document.getElementById('successAlert');
                alert.textContent = message;
                alert.classList.add('active');
                setTimeout(() => {
                    alert.classList.remove('active');
                }, 3000);
            }

            function showError(message) {
                const alert = document.getElementById('errorAlert');
                alert.textContent = message;
                alert.classList.add('active');
                setTimeout(() => {
                    alert.classList.remove('active');
                }, 5000);
            }

            // Завантажуємо галузі при старті
            loadIndustries();
        </script>
    </body>
    </html>
    """
    return html_content

@app.get("/kg", response_class=HTMLResponse)
async def kg_interface():
    """Повертає HTML інтерфейс для відображення графа знань"""
    html_content = r"""
    <!DOCTYPE html>
    <html lang="uk">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Knowledge Graph Viewer</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }

            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                padding: 20px;
            }

            .container {
                max-width: 1200px;
                margin: 0 auto;
                background: white;
                border-radius: 20px;
                box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
                overflow: hidden;
            }

            .header {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 30px;
                text-align: center;
            }

            .header h1 {
                font-size: 2.5em;
                margin-bottom: 10px;
            }

            .header p {
                opacity: 0.9;
                font-size: 1.1em;
            }

            .content {
                padding: 30px;
            }

            .kg-stats {
                background: #f8f9fa;
                border-radius: 15px;
                padding: 20px;
                margin-bottom: 20px;
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 15px;
            }

            .kg-stat-item {
                background: white;
                padding: 15px;
                border-radius: 10px;
                text-align: center;
                border: 2px solid #e9ecef;
            }

            .kg-stat-value {
                font-size: 2em;
                font-weight: bold;
                color: #667eea;
            }

            .kg-stat-label {
                color: #666;
                font-size: 0.9em;
                margin-top: 5px;
            }

            .kg-controls {
                display: flex;
                gap: 15px;
                margin-bottom: 20px;
                flex-wrap: wrap;
            }

            .kg-button {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border: none;
                padding: 12px 25px;
                font-size: 1em;
                border-radius: 8px;
                cursor: pointer;
                transition: all 0.3s ease;
                font-weight: bold;
            }

            .kg-button:hover {
                transform: translateY(-2px);
                box-shadow: 0 5px 20px rgba(102, 126, 234, 0.4);
            }

            .kg-button.secondary {
                background: #6c757d;
            }

            .kg-button.secondary:hover {
                box-shadow: 0 5px 20px rgba(108, 117, 125, 0.4);
            }

            .kg-person-select {
                padding: 12px;
                border: 2px solid #ddd;
                border-radius: 8px;
                font-size: 1em;
                min-width: 200px;
                flex-grow: 1;
            }

            .kg-person-select:focus {
                outline: none;
                border-color: #667eea;
            }

            #cy {
                width: 100%;
                height: 600px;
                background: #f8f9fa;
                border-radius: 15px;
                border: 2px solid #ddd;
                display: none;
            }

            #cy.active {
                display: block;
            }

            .alert {
                padding: 15px;
                border-radius: 8px;
                margin-bottom: 20px;
                display: none;
            }

            .alert.error {
                background: #f8d7da;
                color: #721c24;
                border: 1px solid #f5c6cb;
            }

            .alert.success {
                background: #d4edda;
                color: #155724;
                border: 1px solid #c3e6cb;
            }

            .alert.active {
                display: block;
            }

            .cleanup-section {
                background: #f8f9fa;
                border-radius: 15px;
                padding: 25px;
                margin-bottom: 20px;
                border: 2px solid #e9ecef;
            }

            .cleanup-section h3 {
                font-size: 1.4em;
                color: #333;
                margin-bottom: 15px;
                padding-bottom: 10px;
                border-bottom: 2px solid #667eea;
            }

            .cleanup-controls {
                display: flex;
                gap: 15px;
                flex-wrap: wrap;
                margin-top: 15px;
            }

            .cleanup-button {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border: none;
                padding: 12px 25px;
                font-size: 1em;
                border-radius: 8px;
                cursor: pointer;
                transition: all 0.3s ease;
                font-weight: bold;
            }

            .cleanup-button:hover {
                transform: translateY(-2px);
                box-shadow: 0 5px 20px rgba(102, 126, 234, 0.4);
            }

            .cleanup-button.danger {
                background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%);
            }

            .cleanup-button.danger:hover {
                box-shadow: 0 5px 20px rgba(231, 76, 60, 0.4);
            }

            .cleanup-button.warning {
                background: linear-gradient(135deg, #f39c12 0%, #e67e22 100%);
            }

            .cleanup-button.warning:hover {
                box-shadow: 0 5px 20px rgba(243, 156, 18, 0.4);
            }

            .cleanup-button:disabled {
                opacity: 0.6;
                cursor: not-allowed;
                transform: none;
            }

            .cleanup-results {
                margin-top: 20px;
                padding: 15px;
                background: white;
                border-radius: 10px;
                border: 1px solid #ddd;
                display: none;
            }

            .cleanup-results.active {
                display: block;
            }

            .cleanup-results h4 {
                font-size: 1.2em;
                color: #333;
                margin-bottom: 10px;
            }

            .cleanup-results pre {
                background: #f8f9fa;
                padding: 10px;
                border-radius: 5px;
                overflow-x: auto;
                font-size: 0.9em;
            }

            .form-row {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 15px;
                margin-bottom: 15px;
            }

            .form-group {
                margin-bottom: 15px;
            }

            .form-group label {
                display: block;
                margin-bottom: 8px;
                font-weight: bold;
                color: #333;
            }

            .form-group input {
                width: 100%;
                padding: 10px;
                border: 2px solid #ddd;
                border-radius: 8px;
                font-size: 1em;
            }

            .form-group input:focus {
                outline: none;
                border-color: #667eea;
            }

            .checkbox-group {
                display: flex;
                align-items: center;
                gap: 10px;
            }

            .checkbox-group input[type="checkbox"] {
                width: auto;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🧠 Knowledge Graph Viewer</h1>
                <p>Інтерактивна візуалізація графа знань</p>
            </div>

            <div class="content">
                <div class="alert error" id="errorAlert"></div>
                <div class="alert success" id="successAlert"></div>

                <div class="kg-stats" id="kgStats">
                    <div class="kg-stat-item">
                        <div class="kg-stat-value" id="totalNodes">-</div>
                        <div class="kg-stat-label">Всього вузлів</div>
                    </div>
                    <div class="kg-stat-item">
                        <div class="kg-stat-value" id="totalEdges">-</div>
                        <div class="kg-stat-label">Всього зв'язків</div>
                    </div>
                    <div class="kg-stat-item">
                        <div class="kg-stat-value" id="totalPersons">-</div>
                        <div class="kg-stat-label">Осіб</div>
                    </div>
                    <div class="kg-stat-item">
                        <div class="kg-stat-value" id="totalProcessed">-</div>
                        <div class="kg-stat-label">Оброблено повідомлень</div>
                    </div>
                </div>

                <div class="cleanup-section">
                    <h3>🧹 Очищення графу знань</h3>
                    <div class="form-row">
                        <div class="form-group">
                            <label for="minMentions">Мін. згадок для видалення:</label>
                            <input type="number" id="minMentions" value="2" min="1" max="10">
                        </div>
                        <div class="form-group">
                            <label for="consolidateThreshold">Поріг консолідації:</label>
                            <input type="number" id="consolidateThreshold" value="0.85" min="0.5" max="1.0" step="0.05">
                        </div>
                    </div>
                    <div class="form-group">
                        <label for="connectionsThreshold">Поріг зв'язків:</label>
                        <input type="number" id="connectionsThreshold" value="0.75" min="0.5" max="1.0" step="0.05">
                    </div>
                    <div class="form-group checkbox-group">
                        <input type="checkbox" id="dryRun" checked>
                        <label for="dryRun">Тільки перегляд (dry-run)</label>
                    </div>
                    <div class="cleanup-controls">
                        <button class="cleanup-button warning" onclick="runCleanup(true)">🔍 Перегнути результати</button>
                        <button class="cleanup-button danger" onclick="runCleanup(false)">⚡ Виконати очищення</button>
                        <button class="cleanup-button" onclick="analyzeFrequency()">📊 Аналіз частоти</button>
                    </div>
                    <div class="cleanup-results" id="cleanupResults"></div>
                </div>

                <div class="kg-controls">
                    <select class="kg-person-select" id="personSelect">
                        <option value="">-- Оберіть особу --</option>
                    </select>
                    <button class="kg-button" onclick="loadFullGraph()">Показати весь граф</button>
                    <button class="kg-button" onclick="loadPersonGraph()">Показати граф особи</button>
                    <button class="kg-button secondary" onclick="hideGraph()">Приховати граф</button>
                </div>

                <div id="cy"></div>
            </div>
        </div>

        <script src="https://cdn.jsdelivr.net/npm/cytoscape@3.26.0/dist/cytoscape.min.js"></script>

        <script>
            let cy = null;

            async function loadKGStats() {
                try {
                    const response = await fetch('/api/kg/stats');
                    const data = await response.json();

                    document.getElementById('totalNodes').textContent = data.total_nodes;
                    document.getElementById('totalEdges').textContent = data.total_edges;
                    document.getElementById('totalPersons').textContent = data.persons.length;

                    // Extract processed messages count from stats string
                    const statsLines = data.stats.split('\\n');
                    for (const line of statsLines) {
                        if (line.includes('Processed messages')) {
                            const match = line.match(/Processed messages: (\d+)/);
                            if (match) {
                                document.getElementById('totalProcessed').textContent = match[1];
                            }
                        }
                    }
                } catch (error) {
                    console.error('Error loading KG stats:', error);
                }
            }

            async function analyzeFrequency() {
                try {
                    const response = await fetch('/api/kg/frequency');
                    const data = await response.json();
                    
                    const resultsDiv = document.getElementById('cleanupResults');
                    resultsDiv.classList.add('active');
                    
                    let html = '<h4>📊 Частота появи сутностей</h4>';
                    
                    for (const [type, items] of Object.entries(data.data)) {
                        if (items.length === 0) continue;
                        html += `<h5>${type.toUpperCase()} (${items.length})</h5>`;
                        html += '<pre>';
                        items.slice(0, 20).forEach(item => {
                            const dots = '●'.repeat(Math.min(item.mentions, 5));
                            html += `${dots} ${item.value} (згадок: ${item.mentions})\\n`;
                        });
                        if (items.length > 20) {
                            html += `... та ще ${items.length - 20}\\n`;
                        }
                        html += '</pre>';
                    }
                    
                    resultsDiv.innerHTML = html;
                } catch (error) {
                    console.error('Error analyzing frequency:', error);
                    showError('Помилка аналізу частоти: ' + error.message);
                }
            }

            async function runCleanup(dryRunOverride = null) {
                const minMentions = parseInt(document.getElementById('minMentions').value);
                const consolidateThreshold = parseFloat(document.getElementById('consolidateThreshold').value);
                const connectionsThreshold = parseFloat(document.getElementById('connectionsThreshold').value);
                const dryRun = dryRunOverride !== null ? dryRunOverride : document.getElementById('dryRun').checked;
                
                const resultsDiv = document.getElementById('cleanupResults');
                resultsDiv.classList.add('active');
                resultsDiv.innerHTML = '<p>Обробка...</p>';
                
                try {
                    const response = await fetch('/api/kg/cleanup', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            min_mentions: minMentions,
                            consolidate_threshold: consolidateThreshold,
                            connections_threshold: connectionsThreshold,
                            dry_run: dryRun
                        })
                    });
                    
                    const result = await response.json();
                    
                    if (!result.success) {
                        showError('Помилка очищення');
                        return;
                    }
                    
                    let html = '<h4>' + (dryRun ? '🔍 Результати перегляду (dry-run)' : '⚡ Результати очищення') + '</h4>';
                    
                    // Шум
                    const noise = result.results.noise;
                    const noiseKey = dryRun ? 'would_remove' : 'removed';
                    html += `<h5>Видалення шуму: ${noise[noiseKey]} сутностей</h5>`;
                    if (noise[noiseKey] > 0) {
                        html += '<pre>';
                        noise.items.slice(0, 10).forEach(item => {
                            html += `- [${item.type}] ${item.value} (згадок: ${item.mentions})\\n`;
                        });
                        if (noise.items.length > 10) {
                            html += `... та ще ${noise.items.length - 10}\\n`;
                        }
                        html += '</pre>';
                    }
                    
                    // Консолідація
                    const cons = result.results.consolidate;
                    const consKey = dryRun ? 'would_consolidate' : 'consolidated';
                    html += `<h5>Консолідація: ${cons[consKey]} пар</h5>`;
                    if (cons[consKey] > 0) {
                        html += '<pre>';
                        cons.items.slice(0, 10).forEach(item => {
                            html += `- [${item.type}] '${item.remove_value}' -> '${item.keep_value}' (схожість: ${item.similarity.toFixed(2)})\\n`;
                        });
                        if (cons.items.length > 10) {
                            html += `... та ще ${cons.items.length - 10}\\n`;
                        }
                        html += '</pre>';
                    }
                    
                    // Зв'язки
                    const conn = result.results.connections;
                    const connKey = dryRun ? 'would_connect' : 'connected';
                    html += `<h5>Нові зв'язки: ${conn[connKey]}</h5>`;
                    if (conn[connKey] > 0) {
                        html += '<pre>';
                        conn.items.slice(0, 10).forEach(item => {
                            html += `- [${item.from_type}] '${item.from_value}' <-> [${item.to_type}] '${item.to_value}' (схожість: ${item.similarity.toFixed(2)})\\n`;
                        });
                        if (conn.items.length > 10) {
                            html += `... та ще ${conn.items.length - 10}\\n`;
                        }
                        html += '</pre>';
                    }
                    
                    if (!dryRun) {
                        html += '<p style="color: green; font-weight: bold; margin-top: 10px;">✅ Очищення завершено! Граф збережено.</p>';
                        // Перезавантажуємо статистику
                        loadKGStats();
                    } else {
                        html += '<p style="color: orange; font-weight: bold; margin-top: 10px;">⚠️ Це dry-run режим. Нічого не було видалено. Зніміть галочку "Тільки перегляд" для виконання.</p>';
                    }
                    
                    resultsDiv.innerHTML = html;
                    
                    if (!dryRun) {
                        showSuccess('Очищення завершено успішно');
                    }
                } catch (error) {
                    console.error('Error running cleanup:', error);
                    showError('Помилка очищення: ' + error.message);
                }
            }

            function showError(message) {
                const alert = document.getElementById('errorAlert');
                alert.textContent = message;
                alert.classList.add('active');
                setTimeout(() => alert.classList.remove('active'), 5000);
            }

            function showSuccess(message) {
                const alert = document.getElementById('successAlert');
                alert.textContent = message;
                alert.classList.add('active');
                setTimeout(() => alert.classList.remove('active'), 5000);
            }

            async function loadPersonList() {
                try {
                    const response = await fetch('/api/kg/stats');
                    const data = await response.json();
                    const select = document.getElementById('personSelect');

                    data.persons.forEach(person => {
                        const option = document.createElement('option');
                        option.value = person.value;
                        option.textContent = `${person.value} (${person.mentions || 0} згадок)`;
                        select.appendChild(option);
                    });
                } catch (error) {
                    console.error('Error loading person list:', error);
                }
            }

            async function loadFullGraph() {
                try {
                    console.log('Loading full graph...');
                    const response = await fetch('/api/kg/graph');
                    console.log('Response status:', response.status);

                    if (!response.ok) {
                        throw new Error(`HTTP error! status: ${response.status}`);
                    }

                    const data = await response.json();
                    console.log('Graph data loaded:', data);

                    const elements = convertToCytoscape(data.nodes, data.edges);
                    console.log('Converted elements:', elements);

                    renderGraph(elements);
                } catch (error) {
                    console.error('Error loading full graph:', error);
                    showError('Помилка при завантаженні графа: ' + error.message);
                }
            }

            async function loadPersonGraph() {
                const identifier = document.getElementById('personSelect').value;
                if (!identifier) {
                    showError('Будь ласка, оберіть особу');
                    return;
                }

                try {
                    const response = await fetch(`/api/kg/person/${identifier}`);
                    const data = await response.json();

                    if (!data.graph) {
                        showError('Граф не знайдено для цієї особи');
                        return;
                    }

                    const elements = convertPersonGraphToCytoscape(data);
                    renderGraph(elements);
                } catch (error) {
                    console.error('Error loading person graph:', error);
                    showError('Помилка при завантаженні графа особи');
                }
            }

            function convertToCytoscape(nodes, edges) {
                const elements = [];

                // Convert nodes
                for (const [id, node] of Object.entries(nodes)) {
                    const colors = {
                        person: '#667eea',
                        fact: '#28a745',
                        intent: '#fd7e14',
                        emotion: '#dc3545',
                        behavior: '#6c757d'
                    };

                    elements.push({
                        data: {
                            id: id,
                            label: node.value,
                            type: node.type,
                            mentions: node.mentions || 0,
                            color: colors[node.type] || '#999'
                        }
                    });
                }

                // Convert edges
                edges.forEach(edge => {
                    elements.push({
                        data: {
                            source: edge.from,
                            target: edge.to,
                            relation: edge.relation
                        }
                    });
                });

                return elements;
            }

            function convertPersonGraphToCytoscape(data) {
                const elements = [];

                // Add person node
                elements.push({
                    data: {
                        id: 'person',
                        label: data.person,
                        type: 'person',
                        color: '#667eea'
                    }
                });

                // Add connected nodes
                const graph = data.graph;
                const typeColors = {
                    fact: '#28a745',
                    intent: '#fd7e14',
                    emotion: '#dc3545',
                    behavior: '#6c757d'
                };

                for (const [type, items] of Object.entries(graph)) {
                    items.forEach((item, index) => {
                        const nodeId = `${type}_${index}`;
                        elements.push({
                            data: {
                                id: nodeId,
                                label: item.value,
                                type: type,
                                mentions: item.mentions || 0,
                                color: typeColors[type] || '#999'
                            }
                        });

                        elements.push({
                            data: {
                                source: 'person',
                                target: nodeId,
                                relation: `has_${type}`
                            }
                        });
                    });
                }

                return elements;
            }

            function renderGraph(elements) {
                const container = document.getElementById('cy');
                container.classList.add('active');

                if (cy) {
                    cy.destroy();
                }

                cy = cytoscape({
                    container: container,
                    elements: elements,
                    style: [
                        {
                            selector: 'node',
                            style: {
                                'background-color': 'data(color)',
                                'label': 'data(label)',
                                'font-size': '14px',
                                'font-weight': 'bold',
                                'text-valign': 'bottom',
                                'text-halign': 'center',
                                'text-margin-y': '-5px',
                                'text-outline-color': '#fff',
                                'text-outline-width': '3px',
                                'text-background-color': '#fff',
                                'text-background-opacity': '0.8',
                                'text-background-padding': '3px',
                                'width': '60px',
                                'height': '60px',
                                'border-width': 3,
                                'border-color': '#fff',
                                'text-wrap': 'wrap',
                                'text-max-width': '80px'
                            }
                        },
                        {
                            selector: 'node[type="person"]',
                            style: {
                                'width': '80px',
                                'height': '80px',
                                'font-size': '16px',
                                'text-max-width': '100px'
                            }
                        },
                        {
                            selector: 'edge',
                            style: {
                                'width': 3,
                                'line-color': '#bdc3c7',
                                'target-arrow-color': '#bdc3c7',
                                'target-arrow-shape': 'triangle',
                                'curve-style': 'bezier',
                                'label': 'data(relation)',
                                'font-size': '11px',
                                'text-rotation': 'autorotate',
                                'text-margin-y': '-5px',
                                'text-background-color': '#fff',
                                'text-background-opacity': '0.9',
                                'text-background-padding': '2px',
                                'text-outline-color': '#fff',
                                'text-outline-width': '2px',
                                'arrow-scale': 1.2
                            }
                        },
                        {
                            selector: ':selected',
                            style: {
                                'border-width': 5,
                                'border-color': '#ff6b6b',
                                'background-color': '#ff6b6b'
                            }
                        },
                        {
                            selector: '.faded',
                            style: {
                                'opacity': 0.3
                            }
                        }
                    ],
                    layout: {
                        name: 'cose',
                        animate: true,
                        animationDuration: 1500,
                        nodeRepulsion: 1000000,
                        nodeOverlap: 30,
                        idealEdgeLength: 120,
                        edgeElasticity: 100,
                        nestingFactor: 5,
                        gravity: 80,
                        numIter: 1000,
                        initialTemp: 200,
                        coolingFactor: 0.95,
                        minTemp: 1.0
                    },
                    zoomingEnabled: true,
                    panningEnabled: true,
                    userZoomingEnabled: true,
                    userPanningEnabled: true,
                    wheelSensitivity: 0.3
                });
            }

            function hideGraph() {
                const container = document.getElementById('cy');
                container.classList.remove('active');
                if (cy) {
                    cy.destroy();
                    cy = null;
                }
            }

            function showError(message) {
                const alert = document.getElementById('errorAlert');
                alert.textContent = message;
                alert.classList.add('active');
                setTimeout(() => {
                    alert.classList.remove('active');
                }, 5000);
            }

            // Завантажуємо статистику та список осіб при старті
            loadKGStats();
            loadPersonList();
        </script>
    </body>
    </html>
    """
    return html_content

@app.get("/api/chats")
async def get_chats():
    """API endpoint для отримання списку чатів"""
    try:
        chats = get_chats_from_logs()
        return chats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/chats/{chat_identifier}/messages")
async def get_chat_messages_api(chat_identifier: str, limit: int = 50):
    """API endpoint для отримання повідомлень конкретного чату"""
    try:
        messages = get_chat_messages(chat_identifier, limit)
        return messages
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/send")
async def send_message_api(request: SendMessageRequest):
    """API endpoint для відправки повідомлень"""
    try:
        success = await send_message_to_chat(request.chat_id, request.message)
        return {"success": success}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/kg/stats")
async def get_kg_stats():
    """API endpoint для отримання статистики графа знань"""
    try:
        kg = KnowledgeGraph(GRAPH_PATH, EMBED_URL, EMBED_MODEL)
        stats = kg.summary()
        persons = kg.list_persons()
        return {
            "stats": stats,
            "persons": persons,
            "total_nodes": len(kg.nodes),
            "total_edges": len(kg.edges)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/kg/graph")
async def get_kg_graph():
    """API endpoint для отримання повних даних графа знань"""
    try:
        kg = KnowledgeGraph(GRAPH_PATH, EMBED_URL, EMBED_MODEL)

        # Remove embeddings to reduce payload size
        nodes_without_embeddings = {}
        for node_id, node_data in kg.nodes.items():
            node_copy = dict(node_data)
            node_copy.pop("embedding", None)
            nodes_without_embeddings[node_id] = node_copy

        return {
            "nodes": nodes_without_embeddings,
            "edges": kg.edges
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/kg/person/{identifier}")
async def get_person_graph(identifier: str):
    """API endpoint для отримання графа конкретної особи"""
    try:
        kg = KnowledgeGraph(GRAPH_PATH, EMBED_URL, EMBED_MODEL)
        graph = kg.get_person_graph(identifier)
        return graph
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class IndustryCoefficient(BaseModel):
    name: str
    coefficient: float
    keywords: list[str]

class ResponseCoefficients(BaseModel):
    industries: list[IndustryCoefficient]
    default_coefficient: float

def load_config() -> dict:
    """Завантажує конфігурацію з config.json"""
    config_file = os.path.join(_BASE_DIR, "config.json")
    if os.path.exists(config_file):
        with open(config_file, encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_config(config: dict):
    """Зберігає конфігурацію в config.json"""
    config_file = os.path.join(_BASE_DIR, "config.json")
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

@app.get("/api/response-coefficients")
async def get_response_coefficients():
    """API endpoint для отримання коефіцієнтів відповіді"""
    try:
        config = load_config()
        response_coeffs = config.get("jasmine_filter", {}).get("response_coefficients", {
            "industries": [],
            "default_coefficient": 0.4
        })
        return response_coeffs
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/response-coefficients")
async def update_response_coefficients(coeffs: ResponseCoefficients):
    """API endpoint для оновлення коефіцієнтів відповіді"""
    try:
        config = load_config()
        
        # Переконуємося, що jasmine_filter існує
        if "jasmine_filter" not in config:
            config["jasmine_filter"] = {}
        
        # Оновлюємо коефіцієнти
        config["jasmine_filter"]["response_coefficients"] = {
            "industries": [
                {
                    "name": ind.name,
                    "coefficient": ind.coefficient,
                    "keywords": ind.keywords
                }
                for ind in coeffs.industries
            ],
            "default_coefficient": coeffs.default_coefficient
        }
        
        save_config(config)
        return {"success": True, "message": "Коефіцієнти успішно оновлено"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/response-coefficients/industry")
async def add_industry(industry: IndustryCoefficient):
    """API endpoint для додавання нової галузі"""
    try:
        config = load_config()
        
        if "jasmine_filter" not in config:
            config["jasmine_filter"] = {}
        if "response_coefficients" not in config["jasmine_filter"]:
            config["jasmine_filter"]["response_coefficients"] = {
                "industries": [],
                "default_coefficient": 0.4
            }
        
        coeffs = config["jasmine_filter"]["response_coefficients"]
        coeffs["industries"].append({
            "name": industry.name,
            "coefficient": industry.coefficient,
            "keywords": industry.keywords
        })
        
        save_config(config)
        return {"success": True, "message": "Галузь успішно додано"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class CleanupRequest(BaseModel):
    min_mentions: int = 2
    consolidate_threshold: float = 0.85
    connections_threshold: float = 0.75
    dry_run: bool = False


@app.get("/api/kg/frequency")
async def get_kg_frequency():
    """API endpoint для аналізу частоти появи сутностей"""
    try:
        kg = KnowledgeGraph(GRAPH_PATH, EMBED_URL, EMBED_MODEL)
        freq = kg.analyze_frequency()
        return {"success": True, "data": freq}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/kg/cleanup")
async def cleanup_kg(request: CleanupRequest):
    """API endpoint для повного очищення графу (шум + консолідація + зв'язки)"""
    try:
        kg = KnowledgeGraph(GRAPH_PATH, EMBED_URL, EMBED_MODEL)
        
        # Крок 1: Видалення шуму
        noise_result = kg.remove_noise(
            min_mentions=request.min_mentions,
            dry_run=request.dry_run
        )
        
        # Крок 2: Консолідація
        cons_result = kg.consolidate_similar(
            similarity_threshold=request.consolidate_threshold,
            dry_run=request.dry_run
        )
        
        # Крок 3: Пошук нових зв'язків
        conn_result = kg.find_connections(
            min_similarity=request.connections_threshold,
            dry_run=request.dry_run
        )
        
        if not request.dry_run:
            kg.save()
        
        return {
            "success": True,
            "dry_run": request.dry_run,
            "results": {
                "noise": noise_result,
                "consolidate": cons_result,
                "connections": conn_result
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/kg/remove-noise")
async def remove_noise_kg(min_mentions: int = 2, dry_run: bool = False):
    """API endpoint для видалення шуму з графу"""
    try:
        kg = KnowledgeGraph(GRAPH_PATH, EMBED_URL, EMBED_MODEL)
        result = kg.remove_noise(min_mentions=min_mentions, dry_run=dry_run)
        
        if not dry_run:
            kg.save()
        
        return {"success": True, "dry_run": dry_run, "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/kg/consolidate")
async def consolidate_kg(threshold: float = 0.85, dry_run: bool = False):
    """API endpoint для консолідації схожих сутностей"""
    try:
        kg = KnowledgeGraph(GRAPH_PATH, EMBED_URL, EMBED_MODEL)
        result = kg.consolidate_similar(similarity_threshold=threshold, dry_run=dry_run)
        
        if not dry_run:
            kg.save()
        
        return {"success": True, "dry_run": dry_run, "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/kg/find-connections")
async def find_connections_kg(threshold: float = 0.75, dry_run: bool = False):
    """API endpoint для пошуку нових зв'язків між сутностями"""
    try:
        kg = KnowledgeGraph(GRAPH_PATH, EMBED_URL, EMBED_MODEL)
        result = kg.find_connections(min_similarity=threshold, dry_run=dry_run)
        
        if not dry_run:
            kg.save()
        
        return {"success": True, "dry_run": dry_run, "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/response-coefficients/industry/{industry_name}")
async def delete_industry(industry_name: str):
    """API endpoint для видалення галузі"""
    try:
        config = load_config()
        
        if "jasmine_filter" not in config or "response_coefficients" not in config["jasmine_filter"]:
            raise HTTPException(status_code=404, detail="Коефіцієнти не знайдено")
        
        coeffs = config["jasmine_filter"]["response_coefficients"]
        coeffs["industries"] = [ind for ind in coeffs["industries"] if ind["name"] != industry_name]
        
        save_config(config)
        return {"success": True, "message": "Галузь успішно видалено"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/response-coefficients/industry/{industry_name}")
async def update_industry(industry_name: str, industry: IndustryCoefficient):
    """API endpoint для оновлення галузі"""
    try:
        config = load_config()
        
        if "jasmine_filter" not in config or "response_coefficients" not in config["jasmine_filter"]:
            raise HTTPException(status_code=404, detail="Коефіцієнти не знайдено")
        
        coeffs = config["jasmine_filter"]["response_coefficients"]
        
        # Знаходимо і оновлюємо галузь
        for ind in coeffs["industries"]:
            if ind["name"] == industry_name:
                ind["name"] = industry.name
                ind["coefficient"] = industry.coefficient
                ind["keywords"] = industry.keywords
                break
        else:
            raise HTTPException(status_code=404, detail="Галузь не знайдено")
        
        save_config(config)
        return {"success": True, "message": "Галузь успішно оновлено"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("admin:app", host="0.0.0.0", port=8005, log_level="info")
