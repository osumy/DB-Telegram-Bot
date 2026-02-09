import os
import threading
from flask import Flask
import telebot
import psycopg2
from telebot import types

# --- LEAPCELL FIX: Respond 200 to everything ---
server = Flask(__name__)


@server.errorhandler(404)
@server.route("/", defaults={'path': ''})
@server.route("/<path:path>")
def catch_all(path):
    # This ensures /kaithhealthcheck returns 200 instead of 404
    return "OK", 200


def run_flask():
    port = int(os.environ.get("PORT", 8080))
    server.run(host="0.0.0.0", port=port)


# --- BOT CONFIG ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
DB_URI = os.environ.get("DB_URI")
bot = telebot.TeleBot(BOT_TOKEN)

# Session storage
user_sessions = {}


def get_db_connection():
    return psycopg2.connect(DB_URI)


# --- BOT HANDLERS ---
@bot.message_handler(commands=["start"])
def start(message):
    bot.send_message(message.chat.id, "سلام! خوش آمدید. شماره تلفن خود را وارد کنید:")


# ... (Paste your other handlers like process_login and order_start here) ...

# --- STARTUP ---
if __name__ == "__main__":
    # 1. Start Flask in background to satisfy Leapcell's health check
    threading.Thread(target=run_flask, daemon=True).start()

    print("Bot is starting...")

    # 2. CRITICAL: Clear any existing sessions/webhooks to fix 409 Conflict
    bot.remove_webhook()

    # 3. Start Polling
    bot.polling(none_stop=True, interval=0, timeout=20)