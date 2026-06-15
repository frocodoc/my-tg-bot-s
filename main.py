import os
import telebot
from flask import Flask, request
from yt_dlp import YoutubeDL

# Токен і ваш ID
BOT_TOKEN = '8550616930:AAExxZcEU6YPKQ6rFINf6DAeTir1XPe_UZk'
ADMIN_ID = 1694972951

bot = telebot.TeleBot(BOT_TOKEN, threaded=False)
app = Flask(__name__)

# Веб-сторінка для перевірки працездатності хостингом
@app.route('/', methods=['GET'])
def index():
    return "Бот активний та працює!", 200

# Обробка запитів від Telegram (Webhooks)
@app.route('/' + BOT_TOKEN, methods=['POST'])
def get_message():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "OK", 200

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Привіт! Надішли мені посилання на відео з TikTok, YouTube або Pinterest, і я його завантажу.")

@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    url = message.text

    if url.startswith(('http://', 'https://')):
        status_msg = bot.reply_to(message, "⏳ Завантажую відео, зачекайте...")
        ydl_opts = {
            'format': 'best',
            'outtmpl': f'video_{message.chat.id}.%(ext)s',
            'max_filesize': 50 * 1024 * 1024,
            'quiet': True
        }
        try:
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)

            with open(filename, 'rb') as video:
                bot.send_video(message.chat.id, video)
            
            if os.path.exists(filename):
                os.remove(filename)
            bot.delete_message(message.chat.id, status_msg.message_id)
        except Exception as e:
            bot.edit_message_text(f"❌ Помилка завантаження: {str(e)}", message.chat.id, status_msg.message_id)
            if 'filename' in locals() and os.path.exists(filename):
                os.remove(filename)
    
    elif message.from_user.id != ADMIN_ID:
        user_info = f"📩 Нове повідомлення від @{message.from_user.username or 'без_юзернейма'} (ID: {message.from_user.id}):\n\n"
        bot.send_message(ADMIN_ID, user_info + message.text)
        bot.reply_to(message, "Дякую! Твоє повідомлення надіслано власнику бота.")

@bot.message_handler(func=lambda message: message.reply_to_message is not None and message.from_user.id == ADMIN_ID)
def reply_to_user(message):
    try:
        reply_text = message.reply_to_message.text
        if "ID: " in reply_text:
            target_user_id = int(reply_text.split("ID: ").split(")"))
            bot.send_message(target_user_id, f"💬 Відповідь від розробника:\n\n{message.text}")
            bot.reply_to(message, "✅ Відповідь успішно доставлена користувачу!")
    except Exception as e:
        bot.reply_to(message, f"❌ Не вдалося відправити відповідь: {str(e)}")

# Функція налаштування зв'язку з Telegram при запуску сервера
def set_webhook(url):
    bot.remove_webhook()
    bot.set_webhook(url=url + BOT_TOKEN)

if __name__ == '__main__':
    # Локальний запуск для тесту
    app.run(host='0.0.0.0', port=5000)
