import os
import threading
from flask import Flask
import telebot
import psycopg2
from telebot import types

# --- LEAPCELL HEALTH CHECK ---
# Leapcell needs the app to listen on a port or it will kill the process
server = Flask(__name__)


@server.route("/")
def health_check():
    return "Bot is running", 200


def run_flask():
    # Leapcell provides the PORT environment variable
    port = int(os.environ.get("PORT", 8080))
    server.run(host="0.0.0.0", port=port)


# --- TELEGRAM BOT LOGIC ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
DB_URI = os.environ.get("DB_URI")

bot = telebot.TeleBot(BOT_TOKEN)


# ... (Include all your bot handlers here from the previous message) ...

@bot.message_handler(commands=['start'])
def welcome(message):
    bot.reply_to(message, "خوش آمدید! شماره خود را وارد کنید:")


# --- MAIN EXECUTION ---
if __name__ == "__main__":
    # 1. Start Flask in background
    threading.Thread(target=run_flask, daemon=True).start()

    # 2. Start Bot Polling in foreground
    print("Bot is starting...")
    # remove_webhook clears any old connections to prevent Conflict 409
    bot.remove_webhook()
    bot.polling(none_stop=True)