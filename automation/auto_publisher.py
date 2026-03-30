import json
import requests
import time
import os
import shutil
import argparse
from dotenv import load_dotenv

# Загрузка переменных из .env
# Сначала ищем в текущей папке, потом на уровень выше, потом на два уровня выше
env_path = os.path.join(os.path.dirname(__file__), '.env')
if not os.path.exists(env_path):
    env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
if not os.path.exists(env_path):
    env_path = os.path.join(os.path.dirname(__file__), '..', '..', '.env')
load_dotenv(env_path)

# Настройки
BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
REPO_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
QUEUE_FILE = os.environ.get('QUEUE_FILE', os.path.join(REPO_DIR, 'automation', 'scheduled_posts.json'))
INTERVAL = 3600  # 1 час

def send_telegram_photo(text, image_path):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    payload = {'chat_id': CHAT_ID, 'caption': text, 'parse_mode': 'Markdown'}
    
    # Резолвим путь относительно REPO_DIR если он относительный
    if not os.path.isabs(image_path):
        image_path = os.path.join(REPO_DIR, image_path)
    
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
                        img_path = news['image']
                        
                        # Сохраняем путь как относительный для переносимости
                        # Если в news_data.json уже относительный путь, оставляем как есть
                        # Если абсолютный, пробуем сделать относительным к REPO_DIR
                        if os.path.isabs(img_path):
                            try:
                                img_path = os.path.relpath(img_path, REPO_DIR)
                            except ValueError:
                                pass # Оставляем абсолютным если на другом диске
                        
                        # Путь к файлу источника сохраняем как относительный
                        rel_source_path = os.path.relpath(news_data_path, REPO_DIR)
                        
                        queue.append({
                            "text": news['text'],
                            "image": img_path,
                            "source_file": rel_source_path,
                            "original_news_link": news.get('source', '')
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

def cleanup_orphaned_folders():
    """Удаляет папки дат, в которых больше нет новостей и которых нет в очереди."""
    print("Запуск очистки осиротевших папок...")
    import re
    date_pattern = re.compile(r'^\d{4}-\d{2}-\d{2}$')
    
    # Читаем очередь, чтобы знать, какие файлы еще нужны
    in_queue_files = set()
    if os.path.exists(QUEUE_FILE):
        try:
            with open(QUEUE_FILE, 'r', encoding='utf-8') as f:
                queue = json.load(f)
                for post in queue:
                    sf = post.get('source_file')
                    if sf:
                        if os.path.isabs(sf):
                            in_queue_files.add(os.path.dirname(sf))
                        else:
                            in_queue_files.add(os.path.dirname(os.path.join(REPO_DIR, sf)))
        except:
            pass

    for folder in os.listdir(REPO_DIR):
        folder_path = os.path.join(REPO_DIR, folder)
        if os.path.isdir(folder_path) and date_pattern.match(folder):
            news_data_path = os.path.join(folder_path, 'news_data.json')
            
            # Если папки нет в очереди И в ней нет news_data.json (или он пустой), удаляем
            should_delete = False
            if folder_path not in in_queue_files:
                if not os.path.exists(news_data_path):
                    should_delete = True
                else:
                    try:
                        with open(news_data_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            if not data:
                                should_delete = True
                    except:
                        should_delete = True
            
            if should_delete:
                try:
                    shutil.rmtree(folder_path)
                    print(f"Удалена пустая или неиспользуемая папка: {folder}")
                except Exception as e:
                    print(f"Не удалось удалить {folder}: {e}")

def run_once():
    if not os.path.exists(QUEUE_FILE):
        print("Очередь не найдена.")
        return False
        
    try:
        with open(QUEUE_FILE, 'r', encoding='utf-8') as f:
            queue = json.load(f)
    except Exception as e:
        print(f"Ошибка чтения очереди: {e}")
        return False
        
    if not queue:
        print("Очередь пуста.")
        return False
        
    post = queue[0]
    print(f"Попытка публикации: {post['text'][:50]}...")
    
    result = send_telegram_photo(post['text'], post['image'])
    
    if result.get('ok'):
        print(f"УСПЕХ: message_id {result['result']['message_id']}")
        
        # Удаление статьи из исходного файла news_data.json
        source_rel_path = post.get('source_file')
        if source_rel_path:
            source_file = os.path.join(REPO_DIR, source_rel_path) if not os.path.isabs(source_rel_path) else source_rel_path
            
            if os.path.exists(source_file):
                try:
                    with open(source_file, 'r', encoding='utf-8') as f:
                        source_data = json.load(f)
                    
                    # Фильтруем данные, удаляя уже опубликованную новость
                    updated_source_data = [item for item in source_data if item['text'] != post['text']]
                    
                    if updated_source_data:
                        with open(source_file, 'w', encoding='utf-8') as f:
                            json.dump(updated_source_data, f, ensure_ascii=False, indent=2)
                    else:
                        # Если файл пуст, удаляем его
                        os.remove(source_file)
                        print(f"Файл {source_file} удален, так как все новости опубликованы.")
                except Exception as e:
                    print(f"Ошибка при обновлении источника: {e}")

        # Удаляем из очереди и сохраняем
        remaining_queue = queue[1:]
        with open(QUEUE_FILE, 'w', encoding='utf-8') as f:
            json.dump(remaining_queue, f, ensure_ascii=False, indent=2)
            
        return True
    else:
        error_msg = result.get('error', result.get('description', 'Неизвестная ошибка'))
        print(f"ОШИБКА: {error_msg}")
        
        # Если ошибка в том, что файл не найден, возможно стоит пропустить этот пост?
        if "не найден" in error_msg.lower() or "not found" in error_msg.lower():
            print("Пропуск битого поста и переход к следующему...")
            remaining_queue = queue[1:]
            with open(QUEUE_FILE, 'w', encoding='utf-8') as f:
                json.dump(remaining_queue, f, ensure_ascii=False, indent=2)
                
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--once', action='store_true', help='Запустить один раз и выйти')
    args = parser.parse_args()

    # Сначала проверяем новое
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
                # Периодическая очистка
                cleanup_orphaned_folders()

