import os
import telebot
from flask import Flask, request
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from yt_dlp import YoutubeDL

# Твої налаштування
BOT_TOKEN = '8550616930:AAHnyVIZV3m2lI90ATxZWYCQmjL3IZRLTdU'
RENDER_URL = 'https://my-tg-bot-s.onrender.com'
ADMIN_ID = 1694972951

bot = telebot.TeleBot(BOT_TOKEN, threaded=False)
app = Flask(__name__)

# Словник для контролю спаму посиланнями
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

# 1. КОЛИ КОРИСТУВАЧ НАДСИЛАЄ ПОСИЛАННЯ
@bot.message_handler(func=lambda message: message.text.startswith(('http://', 'https://')))
def ask_main_format(message):
    user_id = message.from_user.id
    url = message.text
    
    current_count = user_spam_counter.get(user_id, 0)
    if current_count >= 3:
        bot.reply_to(message, "❌ Ой, забагато посилань одночасно! Дочекайтеся завантаження попередніх, більше 3 штук підряд не можна.")
        return
        
    user_spam_counter[user_id] = current_count + 1
    
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("🎬 Відео", callback_data=f"choose_qual|{url}"),
        InlineKeyboardButton("🎵 Звук (MP3)", callback_data=f"audio|best|{url}")
    )
    bot.reply_to(message, "Що саме ви хочете завантажити?", reply_markup=markup)

# 2. ОБРОБКА НА КНОПКИ
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    data_parts = call.data.split('|', 2)
    action_type = data_parts[0]
    
    chat_id = call.message.chat.id
    user_id = call.from_user.id

    if action_type == "choose_qual":
        url = data_parts[1]
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("📉 Низька (360p)", callback_data=f"video|360|{url}"),
            InlineKeyboardButton("🎬 Середня (720p)", callback_data=f"video|720|{url}"),
            InlineKeyboardButton("🔥 Найкраща", callback_data=f"video|best|{url}")
        )
        bot.edit_message_text("Виберіть бажану якість відео:", chat_id, call.message.message_id, reply_markup=markup)
        return

    quality = data_parts[1]
    url = data_parts[2]
    
    status_msg = bot.edit_message_text("⏳ Починаю завантаження, зачекайте...", chat_id, call.message.message_id)
    filename_template = f"file_{chat_id}_{call.message.message_id}.%(ext)s"
    
    ydl_opts = {
        'outtmpl': filename_template,
        'max_filesize': 50 * 1024 * 1024,
        'quiet': True,
        'no_warnings': True,
    }
    
    # 🔥 ПРАВИЛЬНЕ ПІДКЛЮЧЕННЯ КУКІВ ЧЕРЕЗ АБСОЛЮТНИЙ ШЛЯХ
    if "youtube.com" in url or "youtu.be" in url:
        # Отримуємо точний шлях до папки, де лежить bot.py
        base_dir = os.path.dirname(os.path.abspath(__file__))
        cookies_path = os.path.join(base_dir, 'youtube_cookies.txt')
        
        if os.path.exists(cookies_path):
            ydl_opts['cookiefile'] = cookies_path
        else:
            # Якщо файлу немає, бот одразу попередить про це в консолі Render
            print(f"УВАГА: Файл куків не знайдено за шляхом: {cookies_path}")

    if action_type == "video":
        if quality == "360":
            ydl_opts['format'] = 'bestvideo[height<=360]+bestaudio/best[height<=360]'
        elif quality == "720":
            ydl_opts['format'] = 'bestvideo[height<=720]+bestaudio/best[height<=720]'
        else:
            ydl_opts['format'] = 'best'
            
    elif action_type == "audio":
        ydl_opts['format'] = 'bestaudio/best'
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]

    filename = None
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            
            if action_type == "audio" and not os.path.exists(filename):
                base, _ = os.path.splitext(filename)
                if os.path.exists(base + '.mp3'):
                    filename = base + '.mp3'
                elif os.path.exists(base + '.m4a'):
                    filename = base + '.m4a'

        with open(filename, 'rb') as f:
            if action_type == "video":
                bot.send_video(chat_id, f, reply_to_message_id=call.message.reply_to_message.message_id)
            else:
                bot.send_audio(chat_id, f, reply_to_message_id=call.message.reply_to_message.message_id)
        
        bot.delete_message(chat_id, status_msg.message_id)

    except Exception as e:
        error_message = str(e)
        if "setdefault" in error_message:
            error_message = "Помилка форматів YouTube. Оберіть іншу якість або інше відео."
        elif "Sign in to confirm" in error_message:
            error_message = "YouTube заблокував запит. Сервер Render не зміг прочитати або підставити куки youtube_cookies.txt."
            
        bot.edit_message_text(f"❌ Помилка завантаження: {error_message}", chat_id, status_msg.message_id)

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
