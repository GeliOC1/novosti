import requests
import time
import os
import sys
from dotenv import load_dotenv

# Загрузка переменных из .env (предполагаем, что .env в корне d:/progekt1)
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

# Настройки через переменные окружения
BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Импорт локального генератора
sys.path.append(os.path.dirname(__file__))
import news_generator

def send_message(chat_id, text):
    requests.post(f"{API_URL}/sendMessage", data={'chat_id': chat_id, 'text': text})

def main():
    print("=== Бот управления запущен ===")
    last_update_id = 0
    while True:
        try:
            res = requests.get(f"{API_URL}/getUpdates", params={'offset': last_update_id+1, 'timeout': 30}).json()
            for up in res.get('result', []):
                last_update_id = up['update_id']
                if 'message' in up:
                    cid = up['message']['chat']['id']
                    txt = up['message'].get('text', '')
                    if txt.startswith('/research'):
                        topic = txt.replace('/research', '').strip() or "новости ИИ"
                        send_message(cid, f"🔍 Исследую: {topic}")
                        items = news_generator.fetch_and_format_news(topic)
                        if items:
                            news_generator.add_to_queue(items)
                            send_message(cid, f"✅ Добавлено {len(items)} в очередь.")
                        else:
                            send_message(cid, "❌ Ошибка поиска.")
                    elif txt == '/status':
                        if os.path.exists(news_generator.QUEUE_FILE):
                            with open(news_generator.QUEUE_FILE, 'r', encoding='utf-8') as f:
                                count = len(json.load(f))
                        else: count = 0
                        send_message(cid, f"📊 В очереди: {count}")
        except:
            time.sleep(5)

if __name__ == "__main__":
    import json
    main()
