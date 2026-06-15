import os
import telebot
from flask import Flask, request
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# Твої налаштування
BOT_TOKEN = '8550616930:AAHnyVIZV3m2lI90ATxZWYCQmjL3IZRLTdU'
RENDER_URL = 'https://my-tg-bot-s.onrender.com'
ADMIN_ID = 1694972951

bot = telebot.TeleBot(BOT_TOKEN, threaded=False)
app = Flask(__name__)

@app.route('/', methods=['GET'])
def index():
    return "Бот працює у надлегкому та стабільному режимі 24/7!", 200

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
    bot.reply_to(message, "Привіт! Надішли мені посилання на будь-яке відео (YouTube, TikTok, Instagram), і я підготую швидкі кнопки для скачування без блокувань! 🚀")

# ОБРОБКА ПОСИЛАНЬ
@bot.message_handler(func=lambda message: message.text.startswith(('http://', 'https://')))
def handle_link(message):
    url = message.text
    markup = InlineKeyboardMarkup()
    
    if "youtube.com" in url or "youtu.be" in url:
        # Генеруємо прямі лінки через надійні веб-інструменти, які YouTube не може забанити на Render
        ss_url = url.replace("youtube.com/", "ssyoutube.com/").replace("youtu.be/", "ssyoutube.com/watch?v=")
        deturl = f"https://deturl.com/{url}"
        
        markup.add(
            InlineKeyboardButton("🚀 Швидке скачати (через SaveFrom)", url=ss_url)
        )
        markup.add(
            InlineKeyboardButton("🎵 Конвертувати в MP3 / Інші формати", url=deturl)
        )
        bot.reply_to(message, "YouTube блокує пряме завантаження через сервери, але ви можете миттєво завантажити відео через ці перевірені шлюзи:", reply_markup=markup)
        
    else:
        # Для TikTok / Instagram / Інших платформ (універсальний швидкий шлюз)
        snap_url = f"https://snapinst.app/?url={url}" # приклад для інсти, або універсальний:
        universal_url = f"https://en.savefrom.net/#url={url}"
        
        markup.add(
            InlineKeyboardButton("🎬 Відкрити сторінку завантаження", url=universal_url)
        )
        bot.reply_to(message, "Ваше посилання готове! Натисніть кнопку нижче, щоб завантажити медіафайл:", reply_markup=markup)

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
    print(f"Бот переведений на безвідмовну архітектуру!")
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
