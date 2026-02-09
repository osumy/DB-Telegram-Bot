import os
import threading
from functools import wraps
from datetime import datetime

import psycopg2
from psycopg2 import Error
import telebot
from telebot import types
from flask import Flask
from dotenv import load_dotenv

load_dotenv()

# ------------------------------------------------------------
# 1. FLASK HEALTH CHECK SERVER (Port 8080)
# ------------------------------------------------------------
# This prevents the platform from shutting down the bot.
server = Flask(__name__)

@server.route('/')
def health_check():
    return "Bot is running!", 200

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    server.run(host="0.0.0.0", port=port)

# ------------------------------------------------------------
# 2. BOT CONFIGURATION
# ------------------------------------------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
DB_URI = os.environ.get("DB_URI")
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")

if not BOT_TOKEN or not DB_URI:
    raise RuntimeError("BOT_TOKEN or DB_URI not found in environment variables.")

bot = telebot.TeleBot(BOT_TOKEN)
user_sessions = {} # chat_id -> {"logged_in": True, "username": str}

# ------------------------------------------------------------
# 3. DATABASE & AUTH HELPERS
# ------------------------------------------------------------
def get_db_connection():
    try:
        return psycopg2.connect(DB_URI)
    except Error as e:
        print(f"Database Error: {e}")
        return None

def is_logged_in(chat_id: int) -> bool:
    return user_sessions.get(chat_id, {}).get("logged_in", False)

def login_required(func):
    @wraps(func)
    def wrapper(message, *args, **kwargs):
        if not is_logged_in(message.chat.id):
            bot.send_message(message.chat.id, "❗ ابتدا وارد شوید. دستور /start را بزنید.")
            return
        return func(message, *args, **kwargs)
    return wrapper

# ------------------------------------------------------------
# 4. KEYBOARDS
# ------------------------------------------------------------
def main_menu_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add("📋 منوی غذاها", "👥 مشتریان", "🚴‍♂️ پیک‌ها", "🧾 سفارش‌ها", "⭐ امتیاز و نظرات", "🚪 خروج از حساب")
    return kb

def menu_submenu_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add("➕ افزودن غذای جدید", "📄 لیست غذاها", "✏️ ویرایش غذا", "🗑 حذف غذا", "⬅️ بازگشت به منوی اصلی")
    return kb

# ------------------------------------------------------------
# 5. AUTH HANDLERS
# ------------------------------------------------------------
@bot.message_handler(commands=["start", "login"])
def start_command(message):
    if is_logged_in(message.chat.id):
        bot.send_message(message.chat.id, "خوش آمدید!", reply_markup=main_menu_keyboard())
        return
    bot.send_message(message.chat.id, "لطفاً نام کاربری خود را وارد کنید:", reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(message, process_login_username)

def process_login_username(message):
    username = (message.text or "").strip()
    user_sessions[message.chat.id] = {"username": username}
    bot.send_message(message.chat.id, "لطفاً شماره تلفن (رمز) را وارد کنید:")
    bot.register_next_step_handler(message, process_login_password, username)

def process_login_password(message, username):
    password = (message.text or "").strip()
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        user_sessions[message.chat.id] = {"logged_in": True, "username": username}
        bot.send_message(message.chat.id, "✅ ورود موفقیت‌آمیز بود.", reply_markup=main_menu_keyboard())
    else:
        bot.send_message(message.chat.id, "❌ خطا در ورود. دوباره /start بزنید.")

# ------------------------------------------------------------
# 6. RESTAURANT LOGIC (Menu, Customers, Orders)
# ------------------------------------------------------------
@bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "📋 منوی غذاها")
def menu_section(message):
    bot.send_message(message.chat.id, "مدیریت غذاها:", reply_markup=menu_submenu_keyboard())

@bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "📄 لیست غذاها")
def list_menu_items(message):
    conn = get_db_connection()
    if not conn: return
    cur = conn.cursor()
    cur.execute("SELECT id, name, price, is_available FROM menu_items LIMIT 50")
    rows = cur.fetchall()
    conn.close()
    
    if not rows:
        bot.send_message(message.chat.id, "غذایی یافت نشد.")
        return
    
    txt = "📋 لیست غذاها:\n\n"
    for r in rows:
        status = "✅" if r[3] else "⛔"
        txt += f"#{r[0]} {r[1]} - {r[2]} تومان {status}\n"
    bot.send_message(message.chat.id, txt)

@bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "⬅️ بازگشت به منوی اصلی")
def back_to_main(message):
    bot.send_message(message.chat.id, "منوی اصلی:", reply_markup=main_menu_keyboard())

@bot.message_handler(func=lambda m: m.text == "🚪 خروج از حساب")
@login_required
def logout_handler(message):
    user_sessions.pop(message.chat.id, None)
    bot.send_message(message.chat.id, "خارج شدید.", reply_markup=types.ReplyKeyboardRemove())

# ... (You can keep your other Add/Edit/Delete handlers here) ...

# ------------------------------------------------------------
# 7. MAIN EXECUTION
# ------------------------------------------------------------
if __name__ == "__main__":
    # Start Flask in a background thread
    print("Starting Flask health check on port 8080...")
    threading.Thread(target=run_flask, daemon=True).start()
    
    # Start Bot Polling in the main thread
    print("Restaurant bot is starting...")
    bot.remove_webhook()
    bot.polling(none_stop=True)
