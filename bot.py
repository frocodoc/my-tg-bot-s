import os
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

# Сервери обходу для YouTube
INVIDIOUS_INSTANCES = [
    "https://invidious.io.lol",
    "https://yewtu.be",
    "https://vid.puffyan.us",
    "https://invidious.nerdvpn.de",
    "https://inv.tux.digital"
]

def get_youtube_id(url):
    """Витягує ID відео з посилання YouTube"""
    if "youtu.be" in url:
        return url.split("/")[-1].split("?")[0]
    elif "v=" in url:
        return url.split("v=")[1].split("&")[0]
    return None

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
    bot.reply_to(message, "Привіт! Надішли мені посилання на відео з TikTok, YouTube, Instagram або Pinterest, і вибери формат завантаження. 🚀")

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
    # Для YouTube залишаємо вибір якості або звуку
    if "youtube.com" in url or "youtu.be" in url:
        markup.add(
            InlineKeyboardButton("🎬 Відео", callback_data=f"video|best|{url}"),
            InlineKeyboardButton("🎵 Звук (MP3)", callback_data=f"audio|best|{url}")
        )
    else:
        # Для ТТ, Інсти та Пінтересту робимо прості кнопки прямого завантаження
        markup.add(
            InlineKeyboardButton("🎬 Скачати Відео", callback_data=f"direct_dl|video|{url}"),
            InlineKeyboardButton("🎵 Скачати Аудіо", callback_data=f"direct_dl|audio|{url}")
        )
    bot.reply_to(message, "Що саме ви хочете завантажити?", reply_markup=markup)

# 2. ОБРОБКА НА КНОПКИ
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    data_parts = call.data.split('|', 2)
    action_type = data_parts[0]
    
    chat_id = call.message.chat.id
    user_id = call.from_user.id
    
    # --- СХЕМА 1: ЗАВАНТАЖЕННЯ З YOUTUBE ЧЕРЕЗ API-ОБХІД ---
    if action_type in ["video", "audio"]:
        quality = data_parts[1]
        url = data_parts[2]
        
        status_msg = bot.edit_message_text("⏳ З'єднуюсь із сервером обходу YouTube...", chat_id, call.message.message_id)
        video_id = get_youtube_id(url)
        
        if not video_id:
            bot.edit_message_text("❌ Не вдалося розпізнати посилання на YouTube.", chat_id, status_msg.message_id)
            return

        direct_url = None
        for instance in INVIDIOUS_INSTANCES:
            try:
                res = requests.get(f"{instance}/api/v1/videos/{video_id}", timeout=3)
                if res.status_code == 200:
                    data = res.json()
                    if action_type == "video":
                        video_formats = [f for f in data.get('formatStreams', []) if f.get('container') == 'mp4']
                        if video_formats:
                            direct_url = video_formats[-1]['url']
                            break
                    else:
                        audio_formats = [f for f in data.get('adaptiveFormats', []) if "audio/" in f.get('type', '')]
                        if audio_formats:
                            direct_url = audio_formats[0]['url']
                            break
            except Exception:
                continue

        if not direct_url:
            bot.edit_message_text("❌ Сервери обходу YouTube зараз перевантажені. Спробуйте ще раз.", chat_id, status_msg.message_id)
            if user_id in user_spam_counter and user_spam_counter[user_id] > 0: user_spam_counter[user_id] -= 1
            return

        ext = "mp4" if action_type == "video" else "mp3"
        filename = f"yt_{chat_id}_{call.message.message_id}.{ext}"
        
        try:
            bot.edit_message_text("📥 Обхід спрацював! Передаю файл у Телеграм...", chat_id, status_msg.message_id)
            res_file = requests.get(direct_url, stream=True, timeout=30)
            with open(filename, 'wb') as f:
                for chunk in res_file.iter_content(chunk_size=1024*1024):
                    if chunk: f.write(chunk)
            
            with open(filename, 'rb') as f:
                if action_type == "video":
                    bot.send_video(chat_id, f, reply_to_message_id=call.message.reply_to_message.message_id)
                else:
                    bot.send_audio(chat_id, f, reply_to_message_id=call.message.reply_to_message.message_id)
            bot.delete_message(chat_id, status_msg.message_id)
        except Exception as e:
            bot.edit_message_text(f"❌ Помилка: {str(e)}", chat_id, status_msg.message_id)
        finally:
            if os.path.exists(filename): os.remove(filename)
            if user_id in user_spam_counter and user_spam_counter[user_id] > 0: user_spam_counter[user_id] -= 1

    # --- СХЕМА 2: ЗАВАНТАЖЕННЯ З TIKTOK / INSTAGRAM / PINTEREST ЧЕРЕЗ YT-DLP ---
    elif action_type == "direct_dl":
        sub_type = data_parts[1]
        url = data_parts[2]
        
        status_msg = bot.edit_message_text("⏳ Завантажую медіафайл, зачекайте...", chat_id, call.message.message_id)
        filename_template = f"direct_{chat_id}_{call.message.message_id}.%(ext)s"
        
        ydl_opts = {
            'outtmpl': filename_template,
            'max_filesize': 50 * 1024 * 1024,
            'quiet': True,
            'no_warnings': True,
        }
        
        if sub_type == "audio":
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
                
                if sub_type == "audio" and not os.path.exists(filename):
                    base, _ = os.path.splitext(filename)
                    if os.path.exists(base + '.mp3'): filename = base + '.mp3'
                    elif os.path.exists(base + '.m4a'): filename = base + '.m4a'

            with open(filename, 'rb') as f:
                if sub_type == "video":
                    bot.send_video(chat_id, f, reply_to_message_id=call.message.reply_to_message.message_id)
                else:
                    bot.send_audio(chat_id, f, reply_to_message_id=call.message.reply_to_message.message_id)
            bot.delete_message(chat_id, status_msg.message_id)
            
        except Exception as e:
            bot.edit_message_text(f"❌ Помилка завантаження: {str(e)}", chat_id, status_msg.message_id)
        finally:
            if filename and os.path.exists(filename): os.remove(filename)
            if user_id in user_spam_counter and user_spam_counter[user_id] > 0: user_spam_counter[user_id] -= 1

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
