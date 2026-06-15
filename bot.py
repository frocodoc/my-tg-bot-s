import os
import re
import time
import telebot
import requests
from flask import Flask, request
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from yt_dlp import YoutubeDL

# Твої налаштування
BOT_TOKEN = '8550616930:AAHnyVIZV3m2lI90ATxZWYCQmjL3IZRLTdU'
RENDER_URL = 'https://my-tg-bot-s.onrender.com'
ADMIN_ID = 1694972951

bot = telebot.TeleBot(BOT_TOKEN, threaded=False)
app = Flask(__name__)

user_spam_counter = {}

@app.route('/', methods=['GET'])
def index():
    return "Бот успішно запущений, активний та працює 24/7!", 200

@app.route('/' + BOT_TOKEN, methods=['POST'])
def get_message():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return "OK", 200
    else:
        return "Forbidden", 403

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Привіт! Надішли мені посилання на відео з TikTok, YouTube, Instagram або Pinterest, і я його завантажу. 🚀")

# 1. ОБРОБКА ПОСИЛАННЯ ВІД КОРИСТУВАЧА
@bot.message_handler(func=lambda message: message.text.startswith(('http://', 'https://')))
def ask_main_format(message):
    user_id = message.from_user.id
    url = message.text
    
    current_count = user_spam_counter.get(user_id, 0)
    if current_count >= 3:
        bot.reply_to(message, "❌ Ой, забагато посилань одночасно! Дочекайтеся завантаження попередніх.")
        return
        
    user_spam_counter[user_id] = current_count + 1
    
    markup = InlineKeyboardMarkup()
    if "youtube.com" in url or "youtu.be" in url:
        # Для YouTube викликаємо прямий шлюз без вибору, щоб одразу віддати найкращий готовий mp4/mp3
        markup.add(
            InlineKeyboardButton("🎬 Скачати Відео (YouTube)", callback_data=f"sf|video|{url}"),
            InlineKeyboardButton("🎵 Скачати Аудіо (MP3)", callback_data=f"sf|audio|{url}")
        )
    else:
        # TikTok, Instagram, Pinterest — через стандартний локальний yt-dlp
        markup.add(
            InlineKeyboardButton("🎬 Скачати Відео", callback_data=f"direct|video|{url}"),
            InlineKeyboardButton("🎵 Скачати Аудіо", callback_data=f"direct|audio|{url}")
        )
    bot.reply_to(message, "Що саме ви хочете завантажити?", reply_markup=markup)

# 2. ОБРОБКА КНОПОК
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    data_parts = call.data.split('|', 2)
    action_type = data_parts[0]
    mode = data_parts[1]
    url = data_parts[2]
    
    chat_id = call.message.chat.id
    user_id = call.from_user.id
    
    status_msg = bot.edit_message_text("⏳ Завантажую медіафайл, зачекайте...", chat_id, call.message.message_id)
    
    # --- СХЕМА 1: АВТОРСЬКИЙ ШЛЮЗ ОБХОДУ YOUTUBE ЧЕРЕЗ SAVEFROM ---
    if action_type == "sf":
        ext = "mp4" if mode == "video" else "mp3"
        local_filename = f"sf_{chat_id}_{call.message.message_id}.{ext}"
        
        try:
            bot.edit_message_text("📡 Підключаюся до магістрального шлюзу SaveFrom...", chat_id, status_msg.message_id)
            
            # Надсилаємо офіційний запит на парсинг до бекенду SaveFrom
            sf_api_url = "https://worker.sf-api.com/savefrom.php"
            payload = {
                "url": url,
                "lang": "en",
                "app": "com.savefrom.net",
                "v": "242"
            }
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Origin": "https://en.savefrom.net",
                "Referer": "https://en.savefrom.net/"
            }
            
            res = requests.post(sf_api_url, data=payload, headers=headers, timeout=15)
            # Прибираємо зайві JS-обгортки, якщо сервіс їх повертає
            text_data = res.text
            if "savefrom.set" in text_data:
                text_data = text_data.split("savefrom.set(")[1].rstrip(");")
                
            import json
            data = json.loads(text_data)
            
            # Шукаємо посилання у відповіді
            links = data.get("url", [])
            if not links:
                raise Exception("Відео не знайдено або воно приватне.")
                
            direct_url = None
            
            if mode == "video":
                # Шукаємо найкращу якість з готовим звуком (зазвичай це 720p або 360p mp4)
                for link in links:
                    if link.get("ext") == "mp4" and link.get("audio") is not False:
                        direct_url = link["url"]
                        break
            else:
                # Шукаємо аудіопотік
                for link in links:
                    if link.get("type") == "audio" or link.get("ext") == "mp3":
                        direct_url = link["url"]
                        break
                if not direct_url:  # Якщо чистого mp3 немає, беремо будь-яке відео для подальшого надсилання
                    direct_url = links[0]["url"]

            if not direct_url:
                direct_url = links[0]["url"]

            bot.edit_message_text("📥 Шлюз пробито! Стягую медіапотік...", chat_id, status_msg.message_id)
            
            # Качаємо отриманий прямий потік шматками на диск Render
            file_res = requests.get(direct_url, stream=True, headers={"User-Agent": headers["User-Agent"]}, timeout=60)
            with open(local_filename, 'wb') as f:
                for chunk in file_res.iter_content(chunk_size=1024*1024):
                    if chunk:
                        f.write(chunk)
            
            # Надсилаємо готовий файл у чат
            with open(local_filename, 'rb') as f:
                if mode == "video":
                    bot.send_video(chat_id, f, reply_to_message_id=call.message.reply_to_message.message_id)
                else:
                    bot.send_audio(chat_id, f, reply_to_message_id=call.message.reply_to_message.message_id)
                    
            bot.delete_message(chat_id, status_msg.message_id)
            
        except Exception as e:
            bot.edit_message_text(f"❌ Помилка шлюзу SaveFrom: {str(e)[:100]}", chat_id, status_msg.message_id)
        finally:
            if os.path.exists(local_filename):
                os.remove(local_filename)
            if user_id in user_spam_counter and user_spam_counter[user_id] > 0:
                user_spam_counter[user_id] -= 1

    # --- СХЕМА 2: СТАНДАРТНИЙ YT-DLP ДЛЯ ТТ / ІНСТИ / ПІНТЕРЕСТУ ---
    elif action_type == "direct":
        filename_template = f"direct_{chat_id}_{call.message.message_id}.%(ext)s"
        ydl_opts = {
            'outtmpl': filename_template,
            'max_filesize': 50 * 1024 * 1024,
            'quiet': True,
            'no_warnings': True,
        }
        
        if mode == "audio":
            ydl_opts['format'] = 'bestaudio/best'
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]
        else:
            ydl_opts['format'] = 'best'

        filename = None
        try:
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                
                if mode == "audio" and not os.path.exists(filename):
                    base, _ = os.path.splitext(filename)
                    if os.path.exists(base + '.mp3'): filename = base + '.mp3'
                    elif os.path.exists(base + '.m4a'): filename = base + '.m4a'

            with open(filename, 'rb') as f:
                if mode == "video":
                    bot.send_video(chat_id, f, reply_to_message_id=call.message.reply_to_message.message_id)
                else:
                    bot.send_audio(chat_id, f, reply_to_message_id=call.message.reply_to_message.message_id)
            bot.delete_message(chat_id, status_msg.message_id)
            
        except Exception as e:
            bot.edit_message_text(f"❌ Помилка соцмережі: {str(e)[:100]}", chat_id, status_msg.message_id)
        finally:
            if filename and os.path.exists(filename):
                os.remove(filename)
            if user_id in user_spam_counter and user_spam_counter[user_id] > 0:
                user_spam_counter[user_id] -= 1

# ЗВОРOTНИЙ ЗВ'ЯЗОК З АДМІНОМ
@bot.message_handler(func=lambda message: message.text and not message.text.startswith(('http://', 'https://')) and message.from_user.id != ADMIN_ID)
def forward_to_admin(message):
    user_info = f"📩 Нове повідомлення від @{message.from_user.username or 'без_юзернейма'} (ID: {message.from_user.id}):\n\n"
    bot.send_message(ADMIN_ID, user_info + message.text)
    bot.reply_to(message, "Дякую! Твоє повідомлення надіслано власнику бота.")

@bot.message_handler(func=lambda message: message.reply_to_message is not None and message.from_user.id == ADMIN_ID)
def reply_to_user(message):
    try:
        reply_text = message.reply_to_message.text
        if "ID: " in reply_text:
            target_user_id = int(reply_text.split("ID: ")[1].split("\n")[0].strip())
            bot.send_message(target_user_id, f"💬 Відповідь від розробника:\n\n{message.text}")
            bot.reply_to(message, "✅ Відповідь успішно доставлена користувачу!")
    except Exception as e:
        bot.reply_to(message, f"❌ Не вдалося відправити відповідь: {str(e)}")

if __name__ == '__main__':
    bot.remove_webhook()
    bot.set_webhook(url=f"{RENDER_URL}/{BOT_TOKEN}")
    print(f"Webhook активовано: {RENDER_URL}/{BOT_TOKEN}")
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
