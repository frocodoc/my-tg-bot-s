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

user_spam_counter = {}

@app.route('/', methods=['GET'])
def index():
    return "Гібридний бот-скачувач активний та працює 24/7!", 200

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
    bot.reply_to(message, "Привіт! Надішли мені посилання на відео з TikTok, YouTube, Instagram або Pinterest, і я завантажу його. 🚀")

# 1. ОБРОБКА ПОСИЛАННЯ ВІД КОРИСТУВАЧА
@bot.message_handler(func=lambda message: message.text.startswith(('http://', 'https://')))
def handle_incoming_link(message):
    user_id = message.from_user.id
    url = message.text
    
    # Перевірка на спам
    current_count = user_spam_counter.get(user_id, 0)
    if current_count >= 3:
        bot.reply_to(message, "❌ Ой, забагато посилань одночасно! Дочекайтеся завантаження попередніх.")
        return
        
    # --- СЦЕНАРІЙ 1: ЯКЩО ЦЕ ЮТУБ (Одразу відправляємо на веб-шлюзи) ---
    if "youtube.com" in url or "youtu.be" in url:
        ss_url = url.replace("youtube.com/", "ssyoutube.com/").replace("youtu.be/", "ssyoutube.com/watch?v=")
        deturl = f"https://deturl.com/{url}"
        
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🚀 Скачати Відео (через SaveFrom)", url=ss_url))
        markup.add(InlineKeyboardButton("🎵 Скачати Аудіо / MP3 (через DetURL)", url=deturl))
        
        bot.reply_to(message, "⚠️ YouTube повністю заблокував скачування через сервери хостингів. Але ви можете миттєво завантажити файл через ці безпечні шлюзи:", reply_markup=markup)
        return

    # --- СЦЕНАРІЙ 2: ІНШІ СОЦМЕРЕЖІ (Пропонуємо скачати прямо в Телеграм) ---
    user_spam_counter[user_id] = current_count + 1
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("🎬 Скачати Відео", callback_data=f"direct|video|{url}"),
        InlineKeyboardButton("🎵 Скачати Аудіо", callback_data=f"direct|audio|{url}")
    )
    bot.reply_to(message, "Що саме ви хочете завантажити з цієї соцмережі?", reply_markup=markup)

# 2. ОБРОБКА КНОПОК ДЛЯ ТТ / ІНСТИ / ПІНТЕРЕСТУ
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    data_parts = call.data.split('|', 2)
    action_type = data_parts[0]
    mode = data_parts[1]
    url = data_parts[2]
    
    chat_id = call.message.chat.id
    user_id = call.from_user.id
    
    status_msg = bot.edit_message_text("⏳ Намагаюся завантажити медіафайл, зачекайте...", chat_id, call.message.message_id)
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
        # Спроба прямого завантаження
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
        # 🔥 ПІДСТРАХОВКА: Якщо ТТ або Інста вибили помилку, даємо веб-шлюз, як для Ютуба!
        universal_url = f"https://en.savefrom.net/#url={url}"
        
        fail_markup = InlineKeyboardMarkup()
        fail_markup.add(InlineKeyboardButton("🔗 Перейти до скачування в браузері", url=universal_url))
        
        bot.edit_message_text(
            "⚠️ Ця соцмережа зараз теж балується або заблокувала прямий запит сервера.\n"
            "Не хвилюйтеся, ви можете завантажити файл через зовнішній шлюз:", 
            chat_id, status_msg.message_id, reply_markup=fail_markup
        )
        
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
    print(f"Гібридний режим запущено!")
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
