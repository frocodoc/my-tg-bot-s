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

# Коли користувач надсилає посилання — показуємо кнопки
@bot.message_handler(func=lambda message: message.text.startswith(('http://', 'https://')))
def ask_format(message):
    url = message.text
    
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("🎬 Відео", callback_data=f"video|{url}"),
        InlineKeyboardButton("🎵 Звук (MP3/M4A)", callback_data=f"audio|{url}")
    )
    
    bot.reply_to(message, "Як завантажити це посилання?", reply_markup=markup)

# Обробка натискання на кнопки Відео / Звук
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    action_type, url = call.data.split('|', 1)
    chat_id = call.message.chat.id
    
    status_msg = bot.edit_message_text("⏳ Починаю завантаження, зачекайте...", chat_id, call.message.message_id)
    filename_template = f"file_{chat_id}_{call.message.message_id}.%(ext)s"
    
    # Конфігурація завантажувача
    ydl_opts = {
        'outtmpl': filename_template,
        'max_filesize': 50 * 1024 * 1024, # Ліміт Telegram 50 МБ
        'quiet': True,
        'no_warnings': True,
        'ignoreerrors': True,
    }
    
    # Автоматично підключаємо куки, якщо посилання з Ютубу і файл є на сервері
    if "youtube.com" in url or "youtu.be" in url:
        if os.path.exists('youtube_cookies.txt'):
            ydl_opts['cookiefile'] = 'youtube_cookies.txt'

    # Налаштування формату під вибір користувача
    if action_type == "video":
        ydl_opts['format'] = 'bestvideo+bestaudio/best/best*'
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
            
            # Перевірка розширень для аудіо (про всяк випадок)
            if action_type == "audio" and not os.path.exists(filename):
                base, _ = os.path.splitext(filename)
                if os.path.exists(base + '.mp3'):
                    filename = base + '.mp3'
                elif os.path.exists(base + '.m4a'):
                    filename = base + '.m4a'

        # Відправка готового файлу
        with open(filename, 'rb') as f:
            if action_type == "video":
                bot.send_video(chat_id, f, reply_to_message_id=call.message.reply_to_message.message_id)
            else:
                bot.send_audio(chat_id, f, reply_to_message_id=call.message.reply_to_message.message_id)
        
        bot.delete_message(chat_id, status_msg.message_id)
        if filename and os.path.exists(filename):
            os.remove(filename)

    except Exception as e:
        bot.edit_message_text(f"❌ Помилка завантаження: {str(e)}", chat_id, status_msg.message_id)
        if filename and os.path.exists(filename):
            os.remove(filename)

# Зворотний зв'язок з адміном
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
    # Оновлюємо вебхук при кожному запуску
    bot.remove_webhook()
    bot.set_webhook(url=f"{RENDER_URL}/{BOT_TOKEN}")
    print(f"Webhook встановлено на: {RENDER_URL}/{BOT_TOKEN}")
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
