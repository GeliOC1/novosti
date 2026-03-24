import os
import json
import time
from google import genai
from google.genai import types

# Конфигурация через переменные окружения
API_KEY = os.environ.get('GEMINI_API_KEY', 'AIzaSyAbnZHaQsrMUcA5lF4Ezm7zRtCwxldZqoA')
REPO_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
QUEUE_FILE = os.path.join(REPO_DIR, 'automation', 'scheduled_posts.json')

client = genai.Client(api_key=API_KEY)

def fetch_and_format_news(topic="Последние важные новости ИИ", count=3):
    print(f"Поиск новостей: {topic}...")
    prompt = f"""
    Найди {count} самых свежих и важных новостей на тему: {topic}.
    Напиши пост для Telegram на русском языке с эмодзи, разбором и обязательной кликабельной ссылкой: 
    🔗 Источник: [Название](URL)
    
    Верни строго JSON:
    [
      {{
        "text": "текст поста",
        "image_prompt": "prompt for image in English"
      }}
    ]
    """
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                response_mime_type="application/json"
            )
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"Ошибка генерации: {e}")
        return []

def generate_placeholder_image(index):
    import requests
    img_path = os.path.join(REPO_DIR, 'automation', f"img_{int(time.time())}_{index}.jpg")
    try:
        res = requests.get(f"https://picsum.photos/1024/1024?random={time.time()}_{index}")
        with open(img_path, "wb") as f:
            f.write(res.content)
        return img_path
    except:
        return None

def add_to_queue(news_items):
    queue = []
    if os.path.exists(QUEUE_FILE):
        with open(QUEUE_FILE, "r", encoding="utf-8") as f:
            queue = json.load(f)
            
    for i, item in enumerate(news_items):
        img = generate_placeholder_image(i)
        queue.append({"text": item['text'], "image": img})
        
    with open(QUEUE_FILE, "w", encoding="utf-8") as f:
        json.dump(queue, f, ensure_ascii=False, indent=2)
    print(f"Очередь обновлена.")

if __name__ == "__main__":
    items = fetch_and_format_news()
    if items:
        add_to_queue(items)
