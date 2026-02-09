import os
from functools import wraps
import psycopg2
from psycopg2 import Error
import telebot
from telebot import types


# ------------------------------------------------------------
# Configurations
# ------------------------------------------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
DB_URI = os.environ.get("DB_URI")

if not BOT_TOKEN or not DB_URI:
    raise RuntimeError("Missing BOT_TOKEN or DB_URI in .env file")

bot = telebot.TeleBot(BOT_TOKEN)

# Session storage: chat_id -> {"logged_in": bool, "user_id": int, "role": str, "customer_id": int}
user_sessions = {}


# ------------------------------------------------------------
# Database Helpers
# ------------------------------------------------------------
def get_db_connection():
    try:
        return psycopg2.connect(DB_URI)
    except Error as e:
        print(f"Database Error: {e}")
        return None


def get_user_by_phone(phone):
    conn = get_db_connection()
    if not conn: return None
    try:
        cur = conn.cursor()
        query = """
            SELECT u.id, u.role, u.customer_id, c.first_name 
            FROM users u
            JOIN customers c ON u.customer_id = c.id
            JOIN customer_phones cp ON c.id = cp.customer_id
            WHERE cp.phone = %s
        """
        cur.execute(query, (phone,))
        return cur.fetchone()
    finally:
        conn.close()


# ------------------------------------------------------------
# Keyboards (Persian)
# ------------------------------------------------------------
def get_main_keyboard(role):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(types.KeyboardButton("🛒 ثبت سفارش جدید"))

    if role == 'admin':
        kb.add(
            types.KeyboardButton("📊 مدیریت غذاها"),
            types.KeyboardButton("👥 لیست مشتریان"),
            types.KeyboardButton("🚴 مدیریت پیک‌ها"),
            types.KeyboardButton("🧾 مشاهده همه سفارش‌ها")
        )

    kb.add(types.KeyboardButton("🚪 خروج"))
    return kb


# ------------------------------------------------------------
# Auth Flow
# ------------------------------------------------------------
@bot.message_handler(commands=["start"])
def start(message):
    chat_id = message.chat.id
    bot.send_message(
        chat_id,
        "سلام! به سیستم رستوران خوش آمدید. 👋\nلطفاً شماره تلفن خود را وارد کنید (مثال: 09919529364):",
        reply_markup=types.ReplyKeyboardRemove()
    )
    bot.register_next_step_handler(message, process_login)


def process_login(message):
    chat_id = message.chat.id
    phone = message.text.strip()

    user_data = get_user_by_phone(phone)

    if user_data:
        user_id, role, customer_id, name = user_data
        user_sessions[chat_id] = {
            "logged_in": True,
            "user_id": user_id,
            "role": role,
            "customer_id": customer_id
        }
        bot.send_message(
            chat_id,
            f"خوش آمدید {name} عزیز! ❤️\nنقش شما: {role}",
            reply_markup=get_main_keyboard(role)
        )
    else:
        bot.send_message(chat_id, "❌ کاربری با این شماره یافت نشد. لطفا دوباره /start را بزنید.")


# ------------------------------------------------------------
# Ordering Feature (For Admin & Customer)
# ------------------------------------------------------------
@bot.message_handler(func=lambda m: m.text == "🛒 ثبت سفارش جدید")
def order_start(message):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name, price FROM menu_items WHERE is_available = TRUE")
    items = cur.fetchall()
    conn.close()

    if not items:
        bot.send_message(message.chat.id, "در حال حاضر منوی غذا خالی است.")
        return

    response = "🍴 منوی غذاها:\n\n"
    for item in items:
        response += f"کد: {item[0]} | {item[1]} | قیمت: {item[2]} تومان\n"

    response += "\nلطفاً سفارش خود را به این صورت ارسال کنید:\nکدغذا:تعداد\nمثال: 1:2"
    bot.send_message(message.chat.id, response)
    bot.register_next_step_handler(message, process_order_placement)


def process_order_placement(message):
    chat_id = message.chat.id
    session = user_sessions.get(chat_id)

    try:
        item_id, qty = map(int, message.text.split(':'))
        conn = get_db_connection()
        cur = conn.cursor()

        # Get Price
        cur.execute("SELECT price FROM menu_items WHERE id = %s", (item_id,))
        price = cur.fetchone()[0]
        total = price * qty

        # Insert Order
        cur.execute(
            "INSERT INTO orders (customer_id, status, total_price, order_type) VALUES (%s, 'pending', %s, 'delivery') RETURNING id",
            (session['customer_id'], total)
        )
        order_id = cur.fetchone()[0]

        # Insert Order Item
        cur.execute(
            "INSERT INTO order_items (order_id, menu_item_id, quantity, unit_price, total_price) VALUES (%s, %s, %s, %s, %s)",
            (order_id, item_id, qty, price, total)
        )

        conn.commit()
        bot.send_message(chat_id, f"✅ سفارش شماره {order_id} با موفقیت ثبت شد.\nمبلغ کل: {total} تومان")
    except Exception as e:
        bot.send_message(chat_id, "❌ خطا در ثبت سفارش. فرمت صحیح (کد:تعداد) را رعایت کنید.")
    finally:
        conn.close()


# ------------------------------------------------------------
# Admin Management
# ------------------------------------------------------------
@bot.message_handler(func=lambda m: m.text == "👥 لیست مشتریان")
def list_customers(message):
    session = user_sessions.get(message.chat.id)
    if not session or session['role'] != 'admin':
        bot.send_message(message.chat.id, "🚫 شما دسترسی به این بخش را ندارید.")
        return

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT c.id, c.first_name, cp.phone FROM customers c JOIN customer_phones cp ON c.id = cp.customer_id")
    rows = cur.fetchall()
    conn.close()

    res = "👥 لیست مشتریان:\n"
    for r in rows:
        res += f"ID: {r[0]} | نام: {r[1]} | تلفن: {r[2]}\n"
    bot.send_message(message.chat.id, res)


@bot.message_handler(func=lambda m: m.text == "🚪 خروج")
def logout(message):
    user_sessions.pop(message.chat.id, None)
    bot.send_message(message.chat.id, "شما از حساب خارج شدید. برای ورود مجدد /start را بزنید.",
                     reply_markup=types.ReplyKeyboardRemove())


if __name__ == "__main__":
    print("Bot is running...")
    bot.polling(none_stop=True)