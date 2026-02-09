import os
from functools import wraps
from datetime import datetime

import psycopg2
from psycopg2 import Error
import telebot
from telebot import types
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

# ------------------------------------------------------------
# Environment Variables Configuration
# ------------------------------------------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
DB_URI = os.environ.get("DB_URI")
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set in environment variables.")
if not DB_URI:
    raise RuntimeError("DB_URI is not set in environment variables.")

bot = telebot.TeleBot(BOT_TOKEN)

# ------------------------------------------------------------
# User Session Management (Login)
# ------------------------------------------------------------
user_sessions = {}  # chat_id -> {"logged_in": True, "username": str}

def is_logged_in(chat_id: int) -> bool:
    return user_sessions.get(chat_id, {}).get("logged_in", False)

def login_required(func):
    @wraps(func)
    def wrapper(message, *args, **kwargs):
        chat_id = message.chat.id
        if not is_logged_in(chat_id):
            bot.send_message(
                chat_id,
                "❗ ابتدا باید وارد سیستم شوید.\n"
                "دستور /start را بزنید و نام کاربری و تلفن/رمز را وارد کنید."
            )
            return
        return func(message, *args, **kwargs)
    return wrapper

# ------------------------------------------------------------
# Database Connection
# ------------------------------------------------------------
def get_db_connection():
    try:
        conn = psycopg2.connect(DB_URI)
        return conn
    except Error as e:
        print(f"Database connection error: {e}")
        return None

# ------------------------------------------------------------
# Keyboards (Persian Interface)
# ------------------------------------------------------------
def main_menu_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(
        types.KeyboardButton("📋 منوی غذاها"),
        types.KeyboardButton("👥 مشتریان"),
        types.KeyboardButton("🚴‍♂️ پیک‌ها"),
        types.KeyboardButton("🧾 سفارش‌ها"),
        types.KeyboardButton("⭐ امتیاز و نظرات"),
        types.KeyboardButton("🚪 خروج از حساب"),
    )
    return kb

def menu_submenu_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(
        types.KeyboardButton("➕ افزودن غذای جدید"),
        types.KeyboardButton("📄 لیست غذاها"),
        types.KeyboardButton("✏️ ویرایش غذا"),
        types.KeyboardButton("🗑 حذف غذا"),
        types.KeyboardButton("⬅️ بازگشت به منوی اصلی"),
    )
    return kb

def customer_submenu_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(
        types.KeyboardButton("➕ افزودن مشتری"),
        types.KeyboardButton("📄 لیست مشتریان"),
        types.KeyboardButton("✏️ ویرایش مشتری"),
        types.KeyboardButton("🗑 حذف مشتری"),
        types.KeyboardButton("⬅️ بازگشت به منوی اصلی"),
    )
    return kb

def courier_submenu_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(
        types.KeyboardButton("➕ افزودن پیک"),
        types.KeyboardButton("📄 لیست پیک‌ها"),
        types.KeyboardButton("✏️ ویرایش پیک"),
        types.KeyboardButton("🗑 حذف پیک"),
        types.KeyboardButton("⬅️ بازگشت به منوی اصلی"),
    )
    return kb

def order_submenu_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(
        types.KeyboardButton("➕ ثبت سفارش جدید"),
        types.KeyboardButton("📄 لیست سفارش‌ها"),
        types.KeyboardButton("✏️ تغییر وضعیت سفارش"),
        types.KeyboardButton("🗑 حذف سفارش"),
        types.KeyboardButton("⬅️ بازگشت به منوی اصلی"),
    )
    return kb

def rating_submenu_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(
        types.KeyboardButton("➕ ثبت نظر/امتیاز برای غذا"),
        types.KeyboardButton("📄 نمایش نظرات یک غذا"),
        types.KeyboardButton("⬅️ بازگشت به منوی اصلی"),
    )
    return kb

# ------------------------------------------------------------
# Authentication Flow
# ------------------------------------------------------------
@bot.message_handler(commands=["start", "login"])
def start_command(message):
    chat_id = message.chat.id
    if is_logged_in(chat_id):
        send_main_menu(message)
        return
    bot.send_message(
        chat_id,
        "به ربات مدیریت رستوران خوش آمدید 🍽\n\n"
        "برای شروع، لطفاً نام کاربری خود را وارد کنید:",
        reply_markup=types.ReplyKeyboardRemove(),
    )
    bot.register_next_step_handler(message, process_login_username)

def process_login_username(message):
    chat_id = message.chat.id
    username = (message.text or "").strip()
    if not username:
        bot.send_message(chat_id, "نام کاربری خالی است، دوباره تلاش کنید و /start را بزنید.")
        return
    user_sessions[chat_id] = {"username": username}
    msg = bot.send_message(chat_id, "لطفاً رمز عبور (شماره تلفن مدیریت) را وارد کنید:")
    bot.register_next_step_handler(msg, process_login_password, username)

def process_login_password(message, username):
    chat_id = message.chat.id
    password = (message.text or "").strip()
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        user_sessions[chat_id] = {"logged_in": True, "username": username}
        bot.send_message(chat_id, "✅ ورود موفقیت‌آمیز بود.", reply_markup=main_menu_keyboard())
    else:
        bot.send_message(chat_id, "❌ نام کاربری یا رمز اشتباه است. دوباره تلاش کنید /start")

@bot.message_handler(func=lambda m: m.text == "🚪 خروج از حساب")
@login_required
def logout_handler(message):
    chat_id = message.chat.id
    user_sessions.pop(chat_id, None)
    bot.send_message(chat_id, "از سیستم خارج شدید. برای ورود دوباره /start را بزنید.",
                     reply_markup=types.ReplyKeyboardRemove())

def send_main_menu(message):
    bot.send_message(message.chat.id, "منوی اصلی مدیریت رستوران 🍽", reply_markup=main_menu_keyboard())

# ------------------------------------------------------------
# Main Navigation
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
    send_main_menu(message)

# ------------------------------------------------------------
# CRUD: Menu Items
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
            bot.send_message(message.chat.id, "هنوز هیچ غذایی ثبت نشده است.")
            return
        txt = "📋 لیست غذاها:\n\n"
        for r in rows:
            status = "✅ موجود" if r[4] else "⛔ ناموجود"
            txt += f"#{r[0]} - {r[1]}\nقیمت: {r[2]} | {status}\n------------------------\n"
        bot.send_message(message.chat.id, txt)
    finally:
        conn.close()

@bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "➕ افزودن غذای جدید")
def add_menu_item_start(message):
    msg = bot.send_message(message.chat.id, "نام غذا را وارد کنید:")
    bot.register_next_step_handler(msg, add_menu_item_name)

def add_menu_item_name(message):
    name = (message.text or "").strip()
    msg = bot.send_message(message.chat.id, "قیمت غذا را وارد کنید:")
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
    except:
        bot.send_message(message.chat.id, "خطا در ثبت اطلاعات.")
    finally:
        if 'conn' in locals(): conn.close()

@bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "🗑 حذف غذا")
def delete_menu_item_start(message):
    msg = bot.send_message(message.chat.id, "کد غذای مورد نظر برای حذف را وارد کنید:")
    bot.register_next_step_handler(msg, delete_menu_item)

def delete_menu_item(message):
    item_id = message.text.strip()
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM menu_items WHERE id = %s", (item_id,))
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, "عملیات حذف انجام شد.")

# ------------------------------------------------------------
# CRUD: Customers
# ------------------------------------------------------------
@bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "📄 لیست مشتریان")
def list_customers_handler(message):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT c.id, c.first_name, c.last_name, cp.phone 
        FROM customers c 
        LEFT JOIN customer_phones cp ON c.id = cp.customer_id
    """)
    rows = cur.fetchall()
    conn.close()
    txt = "👥 لیست مشتریان:\n\n"
    for r in rows:
        txt += f"#{r[0]} - {r[1]} {r[2]} | تلفن: {r[3]}\n"
    bot.send_message(message.chat.id, txt)

@bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "➕ افزودن مشتری")
def add_customer_start(message):
    msg = bot.send_message(message.chat.id, "نام مشتری را وارد کنید:")
    bot.register_next_step_handler(msg, add_customer_name)

def add_customer_name(message):
    name = message.text.strip()
    msg = bot.send_message(message.chat.id, "شماره تلفن مشتری:")
    bot.register_next_step_handler(msg, add_customer_finish, name)

def add_customer_finish(message, name):
    phone = message.text.strip()
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO customers (first_name) VALUES (%s) RETURNING id", (name,))
    cid = cur.fetchone()[0]
    cur.execute("INSERT INTO customer_phones (customer_id, phone) VALUES (%s, %s)", (cid, phone))
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, "مشتری ثبت شد.")

# ------------------------------------------------------------
# CRUD: Orders
# ------------------------------------------------------------
@bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "📄 لیست سفارش‌ها")
def list_orders(message):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, customer_id, status, total_price FROM orders ORDER BY id DESC LIMIT 20")
    rows = cur.fetchall()
    conn.close()
    txt = "🧾 آخرین سفارش‌ها:\n\n"
    for r in rows:
        txt += f"#{r[0]} | مشتری: {r[1]} | وضعیت: {r[2]} | مبلغ: {r[3]}\n"
    bot.send_message(message.chat.id, txt)

@bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "➕ ثبت سفارش جدید")
def add_order_start(message):
    msg = bot.send_message(message.chat.id, "کد مشتری را وارد کنید:")
    bot.register_next_step_handler(msg, add_order_items_step)

def add_order_items_step(message):
    cid = message.text.strip()
    msg = bot.send_message(message.chat.id, "آیتم‌ها را وارد کنید (کدغذا:تعداد):\nمثال: 1:2,3:1")
    bot.register_next_step_handler(msg, add_order_finish, cid)

def add_order_finish(message, cid):
    raw_items = message.text.strip()
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO orders (customer_id, status, total_price) VALUES (%s, 'pending', 0) RETURNING id", (cid,))
        order_id = cur.fetchone()[0]
        total = 0
        for item in raw_items.split(','):
            mid, qty = item.split(':')
            cur.execute("SELECT price FROM menu_items WHERE id = %s", (mid,))
            price = cur.fetchone()[0]
            item_total = float(price) * int(qty)
            total += item_total
            cur.execute("INSERT INTO order_items (order_id, menu_item_id, quantity, unit_price, total_price) VALUES (%s,%s,%s,%s,%s)",
                        (order_id, mid, qty, price, item_total))
        cur.execute("UPDATE orders SET total_price = %s WHERE id = %s", (total, order_id))
        conn.commit()
        bot.send_message(message.chat.id, f"سفارش #{order_id} ثبت شد. مبلغ: {total}")
    except Exception as e:
        bot.send_message(message.chat.id, f"خطا: {e}")
    finally:
        conn.close()

# ------------------------------------------------------------
# Ratings & Comments
# ------------------------------------------------------------
@bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "📄 نمایش نظرات یک غذا")
def list_comments(message):
    msg = bot.send_message(message.chat.id, "کد غذا را وارد کنید:")
    bot.register_next_step_handler(msg, list_comments_finish)

def list_comments_finish(message):
    mid = message.text.strip()
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT score, text FROM comments WHERE menu_item_id = %s", (mid,))
    rows = cur.fetchall()
    conn.close()
    txt = f"⭐ نظرات غذای #{mid}:\n\n"
    for r in rows:
        txt += f"امتیاز: {r[0]} | نظر: {r[1]}\n"
    bot.send_message(message.chat.id, txt if rows else "نظری یافت نشد.")

# ------------------------------------------------------------
# Execution
# ------------------------------------------------------------
if __name__ == "__main__":
    print("Restaurant bot is running (Standard Mode) ...")
    # This keeps the bot running and listening for messages
    bot.remove_webhook()
    bot.polling(none_stop=True)
