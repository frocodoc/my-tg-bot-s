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

# 🌟 НАЛАШТУВАННЯ ПРОКСІ ДЛЯ YOUTUBE
# Зареєструйся на будь-якому безкоштовному проксі-сервісі (наприклад, webshare.io або іншому) 
# і встав сюди свої дані. Формат: http://username:password@ip:port
# Якщо використовуєш безкоштовні публічні проксі без пароля, формат: http://ip:port
YOUTUBE_PROXY = "http://p.webshare.io:80"  # Заміни на своє робоче проксі

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
    if "youtube.com" in url or "youtu.be" in url:
        markup.add(
            InlineKeyboardButton("🎬 Відео (360p)", callback_data=f"yt|360|{url}"),
            InlineKeyboardButton("🎬 Відео (720p)", callback_data=f"yt|720|{url}"),
            InlineKeyboardButton("🎵 Звук (MP3)", callback_data=f"yt|audio|{url}")
        )
    else:
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
    filename_template = f"media_{chat_id}_{call.message.message_id}.%(ext)s"
    
    ydl_opts = {
        'outtmpl': filename_template,
        'max_filesize': 60 * 1024 * 1024,
        'quiet': True,
        'no_warnings': True,
    }

    # --- СХЕМА ДЛЯ YOUTUBE (ЗВИЧАЙНИЙ YT-DLP + СТАБІЛЬНЕ ПРОКСІ) ---
    if action_type == "yt":
        # Пускаємо трафік через резидентське або приватне проксі, щоб приховати Render
        if YOUTUBE_PROXY and YOUTUBE_PROXY != "http://p.webshare.io:80":
            ydl_opts['proxy'] = YOUTUBE_PROXY
            
        ydl_opts['extractor_args'] = {
            'youtube': {
                'player_client': ['android', 'ios'],
                'skip': ['dash', 'hls']
            }
        }
        
        if mode == "360":
            ydl_opts['format'] = 'best[{ext=mp4}][height<=360]/best[height<=360]'
        elif mode == "720":
            ydl_opts['format'] = 'best[{ext=mp4}][height<=720]/best[height<=720]'
        elif mode == "audio":
            ydl_opts['format'] = 'bestaudio/best'
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]

    # --- СХЕМА ДЛЯ ТТ / ІНСТИ / ПІНТЕРЕСТУ (НАПРЯМУ) ---
    elif action_type == "direct":
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

        bot.edit_message_text("📥 Надсилаю файл у Телеграм...", chat_id, status_msg.message_id)
        
        with open(filename, 'rb') as f:
            if mode == "audio":
                bot.send_audio(chat_id, f, reply_to_message_id=call.message.reply_to_message.message_id)
            else:
                bot.send_video(chat_id, f, reply_to_message_id=call.message.reply_to_message.message_id)
                
        bot.delete_message(chat_id, status_msg.message_id)
            
    except Exception as e:
        err_text = str(e)
        # Захист від зациклення ідентичних повідомлень у Телеграмі
        friendly_msg = f"❌ Не вдалося обробити: {err_text[:80]}"
        if "Sign in to confirm" in err_text:
            friendly_msg = "❌ YouTube заблокував цей проксі-вузол. Спробуйте змінити адресу проксі в коді."
        
        try:
            bot.edit_message_text(friendly_msg, chat_id, status_msg.message_id)
        except Exception:
            bot.send_message(chat_id, friendly_msg)
            
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
