import json
import requests
import time
import os
import shutil
import argparse

# Настройки (через переменные окружения для GitHub Actions или значения по умолчанию)
BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '8488878358:AAGSqOTwvQ_FbW92gsgghq6FkThwzQVPK4w')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '-1002337210896')
REPO_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
QUEUE_FILE = os.environ.get('QUEUE_FILE', os.path.join(REPO_DIR, 'automation', 'scheduled_posts.json'))
INTERVAL = 3600  # 1 час

def send_telegram_photo(text, image_path):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    payload = {'chat_id': CHAT_ID, 'caption': text, 'parse_mode': 'Markdown'}
    
    if not os.path.exists(image_path):
        return {"ok": False, "error": f"Файл изображения не найден: {image_path}"}
        
    try:
        with open(image_path, 'rb') as f:
            files = {'photo': f}
            response = requests.post(url, data=payload, files=files)
            return response.json()
    except Exception as e:
        return {"ok": False, "error": str(e)}

def check_for_new_news():
    print("Проверка новых новостей в репозитории...")
    queue = []
    if os.path.exists(QUEUE_FILE):
        try:
            with open(QUEUE_FILE, 'r', encoding='utf-8') as f:
                queue = json.load(f)
        except:
            queue = []
            
    existing_texts = [post['text'] for post in queue]
    newly_added = 0
    
    for folder in os.listdir(REPO_DIR):
        folder_path = os.path.join(REPO_DIR, folder)
        news_data_path = os.path.join(folder_path, 'news_data.json')
        
        if os.path.isdir(folder_path) and os.path.exists(news_data_path) and folder != 'automation':
            try:
                with open(news_data_path, 'r', encoding='utf-8') as f:
                    news_list = json.load(f)
                    
                for news in news_list:
                    if news['text'] not in existing_texts:
                        img_name = news['image']
                        # Резолвим путь относительно корня репозитория
                        full_img_path = os.path.abspath(os.path.join(REPO_DIR, img_name))
                        
                        queue.append({
                            "text": news['text'],
                            "image": full_img_path
                        })
                        existing_texts.append(news['text'])
                        newly_added += 1
            except Exception as e:
                print(f"Ошибка при чтении {news_data_path}: {e}")
                    
    if newly_added > 0:
        os.makedirs(os.path.dirname(QUEUE_FILE), exist_ok=True)
        with open(QUEUE_FILE, 'w', encoding='utf-8') as f:
            json.dump(queue, f, ensure_ascii=False, indent=2)
        print(f"Добавлено {newly_added} новых новостей.")
    else:
        print("Новых новостей не обнаружено.")
    return newly_added

def run_once():
    if not os.path.exists(QUEUE_FILE):
        return False
        
    with open(QUEUE_FILE, 'r', encoding='utf-8') as f:
        queue = json.load(f)
        
    if not queue:
        return False
        
    post = queue[0]
    print(f"Публикация: {post['text'][:50]}...")
    
    result = send_telegram_photo(post['text'], post['image'])
    
    if result.get('ok'):
        print(f"УСПЕХ: message_id {result['result']['message_id']}")
        remaining_queue = queue[1:]
        with open(QUEUE_FILE, 'w', encoding='utf-8') as f:
            json.dump(remaining_queue, f, ensure_ascii=False, indent=2)
            
        # Удаляем изображение
        try:
            if os.path.exists(post['image']):
                os.remove(post['image'])
                print(f"Файл удален: {post['image']}")
        except:
            pass
        return True
    else:
        print(f"ОШИБКА: {result}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--once', action='store_true', help='Запустить один раз и выйти')
    args = parser.parse_args()

    check_for_new_news()
    
    if args.once:
        run_once()
    else:
        print("=== Авто-публикатор запущен (цикл) ===")
        while True:
            if run_once():
                time.sleep(INTERVAL)
            else:
                time.sleep(300)
                check_for_new_news()
