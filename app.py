import os
import threading
from functools import wraps
from datetime import datetime, timedelta

import psycopg2
from psycopg2 import Error
import telebot
from telebot import types
from flask import Flask


# ------------------------------------------------------------
# 1. FLASK HEALTH CHECK (To prevent shutdown)
# ------------------------------------------------------------
server = Flask(__name__)

@server.route('/')
def health_check():
    return "Bot is active", 200

def run_flask():
    # Uses port 8080 as requested
    port = int(os.environ.get("PORT", 8080))
    server.run(host="0.0.0.0", port=port)

# ------------------------------------------------------------
# 2. Configuration & Initialization
# ------------------------------------------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
DB_URI = os.environ.get("DB_URI")
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")

if not BOT_TOKEN or not DB_URI:
    raise RuntimeError("BOT_TOKEN or DB_URI not set in environment variables.")

bot = telebot.TeleBot(BOT_TOKEN)
user_sessions = {}  # chat_id -> {"logged_in": True, "username": str}

# ------------------------------------------------------------
# 3. Helpers & Auth
# ------------------------------------------------------------
def get_db_connection():
    try:
        return psycopg2.connect(DB_URI)
    except Error as e:
        print(f"Database connection error: {e}")
        return None

def is_logged_in(chat_id: int) -> bool:
    return user_sessions.get(chat_id, {}).get("logged_in", False)

def login_required(func):
    @wraps(func)
    def wrapper(message, *args, **kwargs):
        chat_id = message.chat.id
        if not is_logged_in(chat_id):
            bot.send_message(chat_id, "❗ ابتدا باید وارد سیستم شوید.\nدستور /start را بزنید.")
            return
        return func(message, *args, **kwargs)
    return wrapper

# ------------------------------------------------------------
# 4. Keyboards
# ------------------------------------------------------------
def main_menu_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add("📋 منوی غذاها", "👥 مشتریان", "🚴‍♂️ پیک‌ها", "🧾 سفارش‌ها", "⭐ امتیاز و نظرات", "🚪 خروج از حساب")
    return kb

def menu_submenu_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add("➕ افزودن غذای جدید", "📄 لیست غذاها", "✏️ ویرایش غذا", "🗑 حذف غذا", "⬅️ بازگشت به منوی اصلی")
    return kb

def customer_submenu_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add("➕ افزودن مشتری", "📄 لیست مشتریان", "✏️ ویرایش مشتری", "🗑 حذف مشتری", "⬅️ بازگشت به منوی اصلی")
    return kb

def courier_submenu_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add("➕ افزودن پیک", "📄 لیست پیک‌ها", "✏️ ویرایش پیک", "🗑 حذف پیک", "⬅️ بازگشت به منوی اصلی")
    return kb

def order_submenu_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add("➕ ثبت سفارش جدید", "📄 لیست سفارش‌ها", "✏️ تغییر وضعیت سفارش", "🗑 حذف سفارش", "⬅️ بازگشت به منوی اصلی")
    return kb

def rating_submenu_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add("➕ ثبت نظر/امتیاز برای غذا", "📄 نمایش نظرات یک غذا", "⬅️ بازگشت به منوی اصلی")
    return kb

# ------------------------------------------------------------
# 5. Start & Login Flow
# ------------------------------------------------------------
@bot.message_handler(commands=["start", "login"])
def start_command(message):
    chat_id = message.chat.id
    if is_logged_in(chat_id):
        bot.send_message(chat_id, "منوی اصلی مدیریت رستوران 🍽", reply_markup=main_menu_keyboard())
        return
    bot.send_message(chat_id, "به ربات مدیریت رستوران خوش آمدید 🍽\n\nبرای شروع، نام کاربری را وارد کنید:", reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(message, process_login_username)

def process_login_username(message):
    username = (message.text or "").strip()
    user_sessions[message.chat.id] = {"username": username}
    bot.send_message(message.chat.id, "لطفاً شماره تلفن خود را وارد کنید:")
    bot.register_next_step_handler(message, process_login_password, username)

def process_login_password(message, username):
    password = (message.text or "").strip()
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        user_sessions[message.chat.id] = {"logged_in": True, "username": username}
        bot.send_message(message.chat.id, "✅ ورود موفقیت‌آمیز بود.", reply_markup=main_menu_keyboard())
    else:
        bot.send_message(message.chat.id, "❌ نام کاربری یا تلفن اشتباه است.")

# ------------------------------------------------------------
# 6. Navigation
# ------------------------------------------------------------
@bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "📋 منوی غذاها")
def menu_section(message):
    bot.send_message(message.chat.id, "مدیریت منوی غذاها:", reply_markup=menu_submenu_keyboard())

@bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "👥 مشتریان")
def customers_section(message):
    bot.send_message(message.chat.id, "مدیریت مشتریان:", reply_markup=customer_submenu_keyboard())

@bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "🚴‍♂️ پیک‌ها")
def couriers_section(message):
    bot.send_message(message.chat.id, "مدیریت پیک‌ها:", reply_markup=courier_submenu_keyboard())

@bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "🧾 سفارش‌ها")
def orders_section(message):
    bot.send_message(message.chat.id, "مدیریت سفارش‌ها:", reply_markup=order_submenu_keyboard())

@bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "⭐ امتیاز و نظرات")
def ratings_section(message):
    bot.send_message(message.chat.id, "امتیاز و نظرات غذاها:", reply_markup=rating_submenu_keyboard())

@bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "⬅️ بازگشت به منوی اصلی")
def back_to_main(message):
    bot.send_message(message.chat.id, "منوی اصلی:", reply_markup=main_menu_keyboard())

# ------------------------------------------------------------
# 7. Menu Items CRUD
# ------------------------------------------------------------
@bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "📄 لیست غذاها")
def list_menu_items(message):
    conn = get_db_connection()
    if not conn: return
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, name, price, category, is_available FROM menu_items ORDER BY id LIMIT 50")
        rows = cur.fetchall()
        if not rows:
            bot.send_message(message.chat.id, "غذایی ثبت نشده است.")
            return
        txt = "📋 لیست غذاها:\n\n"
        for r in rows:
            status = "✅ موجود" if r[4] else "⛔ ناموجود"
            txt += f"#{r[0]} - {r[1]}\nقیمت: {r[2]} | {status}\n------------------------\n"
        bot.send_message(message.chat.id, txt)
    finally: conn.close()

@bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "➕ افزودن غذای جدید")
def add_menu_item_start(message):
    msg = bot.send_message(message.chat.id, "نام غذا را وارد کنید:")
    bot.register_next_step_handler(msg, add_menu_item_name)

def add_menu_item_name(message):
    name = (message.text or "").strip()
    msg = bot.send_message(message.chat.id, "قیمت را وارد کنید:")
    bot.register_next_step_handler(msg, add_menu_item_price, name)

def add_menu_item_price(message, name):
    try:
        price = float(message.text)
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO menu_items (name, price, is_available) VALUES (%s, %s, TRUE) RETURNING id", (name, price))
        new_id = cur.fetchone()[0]
        conn.commit()
        bot.send_message(message.chat.id, f"غذا با موفقیت ثبت شد. کد: {new_id}")
    except: bot.send_message(message.chat.id, "خطا در قیمت.")
    finally: conn.close()

@bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "🗑 حذف غذا")
def delete_menu_item_start(message):
    msg = bot.send_message(message.chat.id, "کد غذا را برای حذف وارد کنید:")
    bot.register_next_step_handler(msg, delete_menu_item)

def delete_menu_item(message):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM menu_items WHERE id = %s", (message.text,))
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, "حذف انجام شد.")

# ------------------------------------------------------------
# 8. Customer Management
# ------------------------------------------------------------
@bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "📄 لیست مشتریان")
def list_customers_handler(message):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT c.id, c.first_name, cp.phone FROM customers c LEFT JOIN customer_phones cp ON c.id = cp.customer_id")
    rows = cur.fetchall()
    conn.close()
    txt = "👥 لیست مشتریان:\n\n"
    for r in rows: txt += f"#{r[0]} - {r[1]} | تلفن: {r[2]}\n"
    bot.send_message(message.chat.id, txt)

# ------------------------------------------------------------
# 9. Order Management
# ------------------------------------------------------------
@bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "➕ ثبت سفارش جدید")
def add_order_start(message):
    msg = bot.send_message(message.chat.id, "کد مشتری را وارد کنید:")
    bot.register_next_step_handler(msg, add_order_customer_step)

def add_order_customer_step(message):
    cid = message.text.strip()
    msg = bot.send_message(message.chat.id, "اقلام (کدغذا:تعداد):")
    bot.register_next_step_handler(msg, add_order_finish, cid)

def add_order_finish(message, cid):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO orders (customer_id, status, total_price) VALUES (%s, 'pending', 0) RETURNING id", (cid,))
        order_id = cur.fetchone()[0]
        bot.send_message(message.chat.id, f"سفارش #{order_id} ثبت شد.")
        conn.commit()
    except Exception as e: bot.send_message(message.chat.id, f"خطا: {e}")
    finally: conn.close()

# ------------------------------------------------------------
# 10. Execution
# ------------------------------------------------------------
@bot.message_handler(func=lambda m: m.text == "🚪 خروج از حساب")
@login_required
def logout_handler(message):
    user_sessions.pop(message.chat.id, None)
    bot.send_message(message.chat.id, "خارج شدید.", reply_markup=types.ReplyKeyboardRemove())

if __name__ == "__main__":
    # Start Flask Health Check in background
    threading.Thread(target=run_flask, daemon=True).start()
    print("Health check running on port 8080...")
    
    # Start Bot Polling
    bot.remove_webhook()
    bot.polling(none_stop=True)
