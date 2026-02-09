import os
from functools import wraps
from datetime import datetime, timedelta

import psycopg2
from psycopg2 import Error
import telebot
from telebot import types


# ------------------------------------------------------------
# تنظیم متغیرهای محیطی
# ------------------------------------------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
DB_URI = os.environ.get("DB_URI")
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN در متغیرهای محیطی تنظیم نشده است.")
if not DB_URI:
    raise RuntimeError("DB_URI در متغیرهای محیطی تنظیم نشده است.")


bot = telebot.TeleBot(BOT_TOKEN)


# ------------------------------------------------------------
# مدیریت سشن کاربران (لاگین)
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
# اتصال به دیتابیس
# ------------------------------------------------------------
def get_db_connection():
    try:
        conn = psycopg2.connect(DB_URI)
        return conn
    except Error as e:
        print(f"Database connection error: {e}")
        return None


# ------------------------------------------------------------
# کیبوردها
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
# شروع و لاگین
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
        "برای شروع، لطفاً نام کاربری (مثلاً AmirAli) را وارد کنید:",
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
    msg = bot.send_message(
        chat_id,
        "لطفاً تلفن یا رمز عبور خود را وارد کنید:",
    )
    bot.register_next_step_handler(msg, process_login_password, username)


def process_login_password(message, username):
    chat_id = message.chat.id
    password = (message.text or "").strip()

    # در این پروژه برای سادگی فقط یک کاربر ادمین داریم
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        user_sessions[chat_id] = {
            "logged_in": True,
            "username": username,
        }
        bot.send_message(chat_id, "✅ ورود موفقیت‌آمیز بود.", reply_markup=main_menu_keyboard())
    else:
        bot.send_message(
            chat_id,
            "❌ نام کاربری یا تلفن/رمز اشتباه است.\n"
            "اگر مقدار متغیرهای محیطی ADMIN_USERNAME و ADMIN_PASSWORD را عوض کرده‌اید، "
            "با آن‌ها دوباره تلاش کنید.",
        )


@bot.message_handler(func=lambda m: m.text == "🚪 خروج از حساب")
@login_required
def logout_handler(message):
    chat_id = message.chat.id
    user_sessions.pop(chat_id, None)
    bot.send_message(chat_id, "از سیستم خارج شدید. برای ورود دوباره /start را بزنید.",
                     reply_markup=types.ReplyKeyboardRemove())


def send_main_menu(message):
    text = (
        "منوی اصلی مدیریت رستوران 🍽\n"
        "یکی از گزینه‌ها را انتخاب کنید:"
    )
    bot.send_message(message.chat.id, text, reply_markup=main_menu_keyboard())


@bot.message_handler(commands=["menu", "help"])
@login_required
def help_command(message):
    send_main_menu(message)


# ------------------------------------------------------------
# مسیریابی منوی اصلی
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
# CRUD منوی غذاها (menu_items)
# ------------------------------------------------------------
@bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "📄 لیست غذاها")
def list_menu_items(message):
    conn = get_db_connection()
    if not conn:
        bot.send_message(message.chat.id, "خطا در اتصال به پایگاه داده.")
        return
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, name, price, category, is_available
            FROM menu_items
            ORDER BY id
            LIMIT 50
            """
        )
        rows = cur.fetchall()
        if not rows:
            bot.send_message(message.chat.id, "هنوز هیچ غذایی ثبت نشده است.")
            return
        txt = "📋 لیست غذاها:\n\n"
        for r in rows:
            status = "✅ موجود" if r[4] else "⛔ ناموجود"
            txt += f"#{r[0]} - {r[1]}\n"
            txt += f"قیمت: {r[2]} | دسته: {r[3] or '-'} | {status}\n"
            txt += "------------------------\n"
        bot.send_message(message.chat.id, txt)
    except Error as e:
        bot.send_message(message.chat.id, f"خطا در دریافت اطلاعات غذاها: {e}")
    finally:
        conn.close()


@bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "➕ افزودن غذای جدید")
def add_menu_item_start(message):
    msg = bot.send_message(message.chat.id, "نام غذا را وارد کنید:")
    bot.register_next_step_handler(msg, add_menu_item_name)


def add_menu_item_name(message):
    name = (message.text or "").strip()
    if not name:
        bot.send_message(message.chat.id, "نام غذا معتبر نیست.")
        return
    msg = bot.send_message(message.chat.id, "قیمت غذا را به عدد وارد کنید (مثلاً 120000):")
    bot.register_next_step_handler(msg, add_menu_item_price, name)


def add_menu_item_price(message, name):
    price_text = (message.text or "").strip()
    try:
        price = float(price_text)
    except ValueError:
        bot.send_message(message.chat.id, "قیمت نامعتبر است.")
        return
    msg = bot.send_message(message.chat.id, "دسته/گروه غذا (مثلاً پیتزا، نوشیدنی):")
    bot.register_next_step_handler(msg, add_menu_item_category, name, price)


def add_menu_item_category(message, name, price):
    category = (message.text or "").strip() or None
    msg = bot.send_message(
        message.chat.id,
        "آیا غذا موجود است؟ (بله/خیر)",
    )
    bot.register_next_step_handler(msg, add_menu_item_available, name, price, category)


def add_menu_item_available(message, name, price, category):
    ans = (message.text or "").strip()
    is_available = ans in ["بله", "بله ", "yes", "Yes", "y", "Y"]

    conn = get_db_connection()
    if not conn:
        bot.send_message(message.chat.id, "خطا در اتصال به پایگاه داده.")
        return
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO menu_items (name, price, category, is_available)
            VALUES (%s, %s, %s, %s)
            RETURNING id
            """,
            (name, price, category, is_available),
        )
        new_id = cur.fetchone()[0]
        conn.commit()
        bot.send_message(message.chat.id, f"غذا با موفقیت ثبت شد. کد غذا: {new_id}")
    except Error as e:
        bot.send_message(message.chat.id, f"خطا در ثبت غذا: {e}")
    finally:
        conn.close()


@bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "✏️ ویرایش غذا")
def edit_menu_item_start(message):
    msg = bot.send_message(message.chat.id, "کد غذا (id) را برای ویرایش وارد کنید:")
    bot.register_next_step_handler(msg, edit_menu_item_load)


def edit_menu_item_load(message):
    chat_id = message.chat.id
    item_id_text = (message.text or "").strip()
    if not item_id_text.isdigit():
        bot.send_message(chat_id, "کد غذا باید عدد باشد.")
        return
    item_id = int(item_id_text)

    conn = get_db_connection()
    if not conn:
        bot.send_message(chat_id, "خطا در اتصال به پایگاه داده.")
        return
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT name, price, category, is_available FROM menu_items WHERE id = %s",
            (item_id,),
        )
        row = cur.fetchone()
        if not row:
            bot.send_message(chat_id, "غذا با این کد یافت نشد.")
            return

        name, price, category, is_available = row
        txt = (
            f"ویرایش غذا #{item_id}\n"
            f"نام فعلی: {name}\n"
            f"قیمت فعلی: {price}\n"
            f"دسته فعلی: {category or '-'}\n"
            f"وضعیت فعلی: {'موجود' if is_available else 'ناموجود'}\n\n"
            "نام جدید را وارد کنید (یا - برای بدون تغییر):"
        )
        bot.send_message(chat_id, txt)
        # ذخیره موقت در حافظه
        user_sessions.setdefault("edit_menu", {})[chat_id] = {
            "id": item_id,
            "name": name,
            "price": float(price),
            "category": category,
            "is_available": is_available,
        }
        bot.register_next_step_handler(message, edit_menu_item_new_name)
    except Error as e:
        bot.send_message(chat_id, f"خطا در خواندن اطلاعات غذا: {e}")
    finally:
        conn.close()


def edit_menu_item_new_name(message):
    chat_id = message.chat.id
    st = user_sessions.get("edit_menu", {}).get(chat_id)
    if not st:
        bot.send_message(chat_id, "اطلاعات ویرایش یافت نشد. دوباره تلاش کنید.")
        return
    txt = (message.text or "").strip()
    if txt != "-":
        st["name"] = txt

    msg = bot.send_message(chat_id, "قیمت جدید را وارد کنید (یا - برای بدون تغییر):")
    bot.register_next_step_handler(msg, edit_menu_item_new_price)


def edit_menu_item_new_price(message):
    chat_id = message.chat.id
    st = user_sessions.get("edit_menu", {}).get(chat_id)
    if not st:
        bot.send_message(chat_id, "اطلاعات ویرایش یافت نشد.")
        return
    txt = (message.text or "").strip()
    if txt != "-":
        try:
            st["price"] = float(txt)
        except ValueError:
            bot.send_message(chat_id, "قیمت نامعتبر، مقدار قبلی حفظ می‌شود.")

    msg = bot.send_message(chat_id, "دسته جدید را وارد کنید (یا - برای بدون تغییر):")
    bot.register_next_step_handler(msg, edit_menu_item_new_category)


def edit_menu_item_new_category(message):
    chat_id = message.chat.id
    st = user_sessions.get("edit_menu", {}).get(chat_id)
    if not st:
        bot.send_message(chat_id, "اطلاعات ویرایش یافت نشد.")
        return
    txt = (message.text or "").strip()
    if txt != "-":
        st["category"] = txt or None

    msg = bot.send_message(
        chat_id,
        "وضعیت موجود بودن را مشخص کنید (بله/خیر یا - برای بدون تغییر):",
    )
    bot.register_next_step_handler(msg, edit_menu_item_new_available)


def edit_menu_item_new_available(message):
    chat_id = message.chat.id
    st = user_sessions.get("edit_menu", {}).get(chat_id)
    if not st:
        bot.send_message(chat_id, "اطلاعات ویرایش یافت نشد.")
        return
    txt = (message.text or "").strip()
    if txt not in ["-", ""]:
        st["is_available"] = txt in ["بله", "yes", "Yes", "y", "Y"]

    conn = get_db_connection()
    if not conn:
        bot.send_message(chat_id, "خطا در اتصال به پایگاه داده.")
        return
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE menu_items
            SET name = %s,
                price = %s,
                category = %s,
                is_available = %s
            WHERE id = %s
            """,
            (st["name"], st["price"], st["category"], st["is_available"], st["id"]),
        )
        conn.commit()
        bot.send_message(chat_id, "غذا با موفقیت ویرایش شد.")
    except Error as e:
        bot.send_message(chat_id, f"خطا در ویرایش غذا: {e}")
    finally:
        conn.close()
        user_sessions.get("edit_menu", {}).pop(chat_id, None)


@bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "🗑 حذف غذا")
def delete_menu_item_start(message):
    msg = bot.send_message(message.chat.id, "کد غذای مورد نظر برای حذف را وارد کنید:")
    bot.register_next_step_handler(msg, delete_menu_item)


def delete_menu_item(message):
    chat_id = message.chat.id
    item_id_text = (message.text or "").strip()
    if not item_id_text.isdigit():
        bot.send_message(chat_id, "کد غذا باید عدد باشد.")
        return
    item_id = int(item_id_text)

    conn = get_db_connection()
    if not conn:
        bot.send_message(chat_id, "خطا در اتصال به پایگاه داده.")
        return
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM menu_items WHERE id = %s", (item_id,))
        if cur.rowcount == 0:
            bot.send_message(chat_id, "غذا با این کد یافت نشد.")
        else:
            conn.commit()
            bot.send_message(chat_id, "غذا با موفقیت حذف شد.")
    except Error as e:
        bot.send_message(chat_id, f"خطا در حذف غذا: {e}")
    finally:
        conn.close()


# ------------------------------------------------------------
# CRUD مشتریان (customers)
# ------------------------------------------------------------
@bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "📄 لیست مشتریان")
def list_customers(message):
    conn = get_db_connection()
    if not conn:
        bot.send_message(message.chat.id, "خطا در اتصال به پایگاه داده.")
        return
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT c.id, c.first_name, c.last_name, c.score,
                   cp.phone, ca.address
            FROM customers c
            LEFT JOIN customer_phones cp ON c.id = cp.customer_id
            LEFT JOIN customer_address ca ON c.id = ca.customer_id
            ORDER BY c.id
            LIMIT 50
            """
        )
        rows = cur.fetchall()
        if not rows:
            bot.send_message(message.chat.id, "هیچ مشتری ثبت نشده است.")
            return
        txt = "👥 لیست مشتریان:\n\n"
        for r in rows:
            txt += f"#{r[0]} - {r[1] or ''} {r[2] or ''}\n"
            txt += f"امتیاز: {r[3] or 0}\n"
            txt += f"تلفن: {r[4] or '-'}\n"
            txt += f"آدرس: {r[5] or '-'}\n"
            txt += "------------------------\n"
        bot.send_message(message.chat.id, txt)
    except Error as e:
        bot.send_message(message.chat.id, f"خطا در دریافت لیست مشتریان: {e}")
    finally:
        conn.close()


@bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "➕ افزودن مشتری")
def add_customer_start(message):
    msg = bot.send_message(message.chat.id, "نام کوچک مشتری را وارد کنید:")
    bot.register_next_step_handler(msg, add_customer_first_name)


def add_customer_first_name(message):
    first_name = (message.text or "").strip()
    if not first_name:
        bot.send_message(message.chat.id, "نام کوچک معتبر نیست.")
        return
    msg = bot.send_message(message.chat.id, "نام خانوادگی مشتری را وارد کنید:")
    bot.register_next_step_handler(msg, add_customer_last_name, first_name)


def add_customer_last_name(message, first_name):
    last_name = (message.text or "").strip()
    msg = bot.send_message(message.chat.id, "شماره تلفن مشتری را وارد کنید (اجباری):")
    bot.register_next_step_handler(msg, add_customer_phone, first_name, last_name)


def add_customer_phone(message, first_name, last_name):
    phone = (message.text or "").strip()
    if not phone:
        bot.send_message(message.chat.id, "شماره تلفن نمی‌تواند خالی باشد.")
        return
    msg = bot.send_message(message.chat.id, "آدرس مشتری را وارد کنید (اختیاری):")
    bot.register_next_step_handler(msg, add_customer_address, first_name, last_name, phone)


def add_customer_address(message, first_name, last_name, phone):
    chat_id = message.chat.id
    address = (message.text or "").strip() or None

    conn = get_db_connection()
    if not conn:
        bot.send_message(chat_id, "خطا در اتصال به پایگاه داده.")
        return
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO customers (first_name, last_name) VALUES (%s, %s) RETURNING id",
            (first_name, last_name),
        )
        customer_id = cur.fetchone()[0]

        cur.execute(
            "INSERT INTO customer_phones (phone, customer_id) VALUES (%s, %s)",
            (phone, customer_id),
        )
        if address:
            cur.execute(
                "INSERT INTO customer_address (customer_id, address) VALUES (%s, %s)",
                (customer_id, address),
            )
        conn.commit()
        bot.send_message(chat_id, f"مشتری جدید ثبت شد. کد مشتری: {customer_id}")
    except Error as e:
        bot.send_message(chat_id, f"خطا در ثبت مشتری: {e}")
    finally:
        conn.close()


@bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "✏️ ویرایش مشتری")
def edit_customer_start(message):
    msg = bot.send_message(message.chat.id, "کد مشتری برای ویرایش را وارد کنید:")
    bot.register_next_step_handler(msg, edit_customer_load)


def edit_customer_load(message):
    chat_id = message.chat.id
    cid_text = (message.text or "").strip()
    if not cid_text.isdigit():
        bot.send_message(chat_id, "کد مشتری باید عدد باشد.")
        return
    cid = int(cid_text)
    conn = get_db_connection()
    if not conn:
        bot.send_message(chat_id, "خطا در اتصال به پایگاه داده.")
        return
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT c.first_name, c.last_name, c.score,
                   cp.phone, ca.address
            FROM customers c
            LEFT JOIN customer_phones cp ON c.id = cp.customer_id
            LEFT JOIN customer_address ca ON c.id = ca.customer_id
            WHERE c.id = %s
            """,
            (cid,),
        )
        row = cur.fetchone()
        if not row:
            bot.send_message(chat_id, "مشتری با این کد یافت نشد.")
            return
        first_name, last_name, score, phone, address = row
        user_sessions.setdefault("edit_customer", {})[chat_id] = {
            "id": cid,
            "first_name": first_name,
            "last_name": last_name,
            "score": float(score or 0),
            "phone": phone,
            "address": address,
        }
        txt = (
            f"ویرایش مشتری #{cid}\n"
            f"نام فعلی: {first_name or ''}\n"
            f"نام خانوادگی فعلی: {last_name or ''}\n"
            f"امتیاز فعلی: {score or 0}\n"
            f"تلفن فعلی: {phone or '-'}\n"
            f"آدرس فعلی: {address or '-'}\n\n"
            "نام جدید را وارد کنید (یا - برای بدون تغییر):"
        )
        bot.send_message(chat_id, txt)
        bot.register_next_step_handler(message, edit_customer_first_name_new)
    except Error as e:
        bot.send_message(chat_id, f"خطا در خواندن اطلاعات مشتری: {e}")
    finally:
        conn.close()


def edit_customer_first_name_new(message):
    chat_id = message.chat.id
    st = user_sessions.get("edit_customer", {}).get(chat_id)
    if not st:
        bot.send_message(chat_id, "اطلاعات ویرایش یافت نشد.")
        return
    txt = (message.text or "").strip()
    if txt != "-":
        st["first_name"] = txt
    msg = bot.send_message(chat_id, "نام خانوادگی جدید را وارد کنید (یا - برای بدون تغییر):")
    bot.register_next_step_handler(msg, edit_customer_last_name_new)


def edit_customer_last_name_new(message):
    chat_id = message.chat.id
    st = user_sessions.get("edit_customer", {}).get(chat_id)
    if not st:
        bot.send_message(chat_id, "اطلاعات ویرایش یافت نشد.")
        return
    txt = (message.text or "").strip()
    if txt != "-":
        st["last_name"] = txt
    msg = bot.send_message(chat_id, "امتیاز جدید مشتری را وارد کنید (یا - برای بدون تغییر):")
    bot.register_next_step_handler(msg, edit_customer_score_new)


def edit_customer_score_new(message):
    chat_id = message.chat.id
    st = user_sessions.get("edit_customer", {}).get(chat_id)
    if not st:
        bot.send_message(chat_id, "اطلاعات ویرایش یافت نشد.")
        return
    txt = (message.text or "").strip()
    if txt != "-":
        try:
            st["score"] = float(txt)
        except ValueError:
            bot.send_message(chat_id, "امتیاز نامعتبر، مقدار قبلی حفظ می‌شود.")
    msg = bot.send_message(chat_id, "تلفن جدید را وارد کنید (یا - برای بدون تغییر):")
    bot.register_next_step_handler(msg, edit_customer_phone_new)


def edit_customer_phone_new(message):
    chat_id = message.chat.id
    st = user_sessions.get("edit_customer", {}).get(chat_id)
    if not st:
        bot.send_message(chat_id, "اطلاعات ویرایش یافت نشد.")
        return
    txt = (message.text or "").strip()
    if txt != "-":
        st["phone"] = txt or None
    msg = bot.send_message(chat_id, "آدرس جدید را وارد کنید (یا - برای بدون تغییر):")
    bot.register_next_step_handler(msg, edit_customer_address_new)


def edit_customer_address_new(message):
    chat_id = message.chat.id
    st = user_sessions.get("edit_customer", {}).get(chat_id)
    if not st:
        bot.send_message(chat_id, "اطلاعات ویرایش یافت نشد.")
        return
    txt = (message.text or "").strip()
    if txt != "-":
        st["address"] = txt or None

    conn = get_db_connection()
    if not conn:
        bot.send_message(chat_id, "خطا در اتصال به پایگاه داده.")
        return
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE customers SET first_name = %s, last_name = %s, score = %s WHERE id = %s",
            (st["first_name"], st["last_name"], st["score"], st["id"]),
        )
        # تلفن
        cur.execute(
            "SELECT id FROM customer_phones WHERE customer_id = %s",
            (st["id"],),
        )
        row = cur.fetchone()
        if st["phone"]:
            if row:
                cur.execute(
                    "UPDATE customer_phones SET phone = %s WHERE customer_id = %s",
                    (st["phone"], st["id"]),
                )
            else:
                cur.execute(
                    "INSERT INTO customer_phones (phone, customer_id) VALUES (%s, %s)",
                    (st["phone"], st["id"]),
                )
        # آدرس
        cur.execute(
            "SELECT id FROM customer_address WHERE customer_id = %s",
            (st["id"],),
        )
        row = cur.fetchone()
        if st["address"]:
            if row:
                cur.execute(
                    "UPDATE customer_address SET address = %s WHERE customer_id = %s",
                    (st["address"], st["id"]),
                )
            else:
                cur.execute(
                    "INSERT INTO customer_address (customer_id, address) VALUES (%s, %s)",
                    (st["id"], st["address"]),
                )
        conn.commit()
        bot.send_message(chat_id, "مشخصات مشتری با موفقیت ویرایش شد.")
    except Error as e:
        bot.send_message(chat_id, f"خطا در ویرایش مشتری: {e}")
    finally:
        conn.close()
        user_sessions.get("edit_customer", {}).pop(chat_id, None)


@bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "🗑 حذف مشتری")
def delete_customer_start(message):
    msg = bot.send_message(message.chat.id, "کد مشتری مورد نظر برای حذف را وارد کنید:")
    bot.register_next_step_handler(msg, delete_customer)


def delete_customer(message):
    chat_id = message.chat.id
    cid_text = (message.text or "").strip()
    if not cid_text.isdigit():
        bot.send_message(chat_id, "کد مشتری باید عدد باشد.")
        return
    cid = int(cid_text)
    conn = get_db_connection()
    if not conn:
        bot.send_message(chat_id, "خطا در اتصال به پایگاه داده.")
        return
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM customers WHERE id = %s", (cid,))
        if cur.rowcount == 0:
            bot.send_message(chat_id, "مشتری با این کد یافت نشد.")
        else:
            conn.commit()
            bot.send_message(chat_id, "مشتری با موفقیت حذف شد.")
    except Error as e:
        bot.send_message(chat_id, f"خطا در حذف مشتری: {e}")
    finally:
        conn.close()


# ------------------------------------------------------------
# CRUD پیک‌ها (couriers)
# ------------------------------------------------------------
@bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "📄 لیست پیک‌ها")
def list_couriers(message):
    conn = get_db_connection()
    if not conn:
        bot.send_message(message.chat.id, "خطا در اتصال به پایگاه داده.")
        return
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, first_name, last_name, phone, status, average_score
            FROM couriers
            ORDER BY id
            LIMIT 50
            """
        )
        rows = cur.fetchall()
        if not rows:
            bot.send_message(message.chat.id, "هیچ پیکی ثبت نشده است.")
            return
        txt = "🚴‍♂️ لیست پیک‌ها:\n\n"
        for r in rows:
            txt += f"#{r[0]} - {r[1] or ''} {r[2] or ''}\n"
            txt += f"تلفن: {r[3] or '-'} | وضعیت: {r[4] or '-'} | امتیاز: {r[5] or 0}\n"
            txt += "------------------------\n"
        bot.send_message(message.chat.id, txt)
    except Error as e:
        bot.send_message(message.chat.id, f"خطا در دریافت لیست پیک‌ها: {e}")
    finally:
        conn.close()


@bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "➕ افزودن پیک")
def add_courier_start(message):
    msg = bot.send_message(message.chat.id, "نام کوچک پیک را وارد کنید:")
    bot.register_next_step_handler(msg, add_courier_first_name)


def add_courier_first_name(message):
    first_name = (message.text or "").strip()
    if not first_name:
        bot.send_message(message.chat.id, "نام کوچک معتبر نیست.")
        return
    msg = bot.send_message(message.chat.id, "نام خانوادگی پیک را وارد کنید:")
    bot.register_next_step_handler(msg, add_courier_last_name, first_name)


def add_courier_last_name(message, first_name):
    last_name = (message.text or "").strip()
    msg = bot.send_message(message.chat.id, "شماره تلفن پیک را وارد کنید:")
    bot.register_next_step_handler(msg, add_courier_phone, first_name, last_name)


def add_courier_phone(message, first_name, last_name):
    phone = (message.text or "").strip()
    msg = bot.send_message(message.chat.id, "آدرس یا توضیحات پیک را وارد کنید (اختیاری):")
    bot.register_next_step_handler(msg, add_courier_address, first_name, last_name, phone)


def add_courier_address(message, first_name, last_name, phone):
    chat_id = message.chat.id
    address = (message.text or "").strip() or None

    conn = get_db_connection()
    if not conn:
        bot.send_message(chat_id, "خطا در اتصال به پایگاه داده.")
        return
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO couriers (first_name, last_name, phone, address, status, average_score)
            VALUES (%s, %s, %s, %s, %s, 0)
            RETURNING id
            """,
            (first_name, last_name, phone, address, "available"),
        )
        courier_id = cur.fetchone()[0]
        conn.commit()
        bot.send_message(chat_id, f"پیک جدید ثبت شد. کد پیک: {courier_id}")
    except Error as e:
        bot.send_message(chat_id, f"خطا در ثبت پیک: {e}")
    finally:
        conn.close()


@bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "✏️ ویرایش پیک")
def edit_courier_start(message):
    msg = bot.send_message(message.chat.id, "کد پیک برای ویرایش را وارد کنید:")
    bot.register_next_step_handler(msg, edit_courier_load)


def edit_courier_load(message):
    chat_id = message.chat.id
    cid_text = (message.text or "").strip()
    if not cid_text.isdigit():
        bot.send_message(chat_id, "کد پیک باید عدد باشد.")
        return
    cid = int(cid_text)

    conn = get_db_connection()
    if not conn:
        bot.send_message(chat_id, "خطا در اتصال به پایگاه داده.")
        return
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT first_name, last_name, phone, address, status
            FROM couriers
            WHERE id = %s
            """,
            (cid,),
        )
        row = cur.fetchone()
        if not row:
            bot.send_message(chat_id, "پیک با این کد یافت نشد.")
            return
        first_name, last_name, phone, address, status = row
        user_sessions.setdefault("edit_courier", {})[chat_id] = {
            "id": cid,
            "first_name": first_name,
            "last_name": last_name,
            "phone": phone,
            "address": address,
            "status": status,
        }
        txt = (
            f"ویرایش پیک #{cid}\n"
            f"نام فعلی: {first_name or ''}\n"
            f"نام خانوادگی فعلی: {last_name or ''}\n"
            f"تلفن فعلی: {phone or '-'}\n"
            f"آدرس فعلی: {address or '-'}\n"
            f"وضعیت فعلی: {status or '-'}\n\n"
            "نام جدید را وارد کنید (یا - برای بدون تغییر):"
        )
        bot.send_message(chat_id, txt)
        bot.register_next_step_handler(message, edit_courier_first_name_new)
    except Error as e:
        bot.send_message(chat_id, f"خطا در خواندن اطلاعات پیک: {e}")
    finally:
        conn.close()


def edit_courier_first_name_new(message):
    chat_id = message.chat.id
    st = user_sessions.get("edit_courier", {}).get(chat_id)
    if not st:
        bot.send_message(chat_id, "اطلاعات ویرایش یافت نشد.")
        return
    txt = (message.text or "").strip()
    if txt != "-":
        st["first_name"] = txt
    msg = bot.send_message(chat_id, "نام خانوادگی جدید را وارد کنید (یا - برای بدون تغییر):")
    bot.register_next_step_handler(msg, edit_courier_last_name_new)


def edit_courier_last_name_new(message):
    chat_id = message.chat.id
    st = user_sessions.get("edit_courier", {}).get(chat_id)
    if not st:
        bot.send_message(chat_id, "اطلاعات ویرایش یافت نشد.")
        return
    txt = (message.text or "").strip()
    if txt != "-":
        st["last_name"] = txt
    msg = bot.send_message(chat_id, "تلفن جدید را وارد کنید (یا - برای بدون تغییر):")
    bot.register_next_step_handler(msg, edit_courier_phone_new)


def edit_courier_phone_new(message):
    chat_id = message.chat.id
    st = user_sessions.get("edit_courier", {}).get(chat_id)
    if not st:
        bot.send_message(chat_id, "اطلاعات ویرایش یافت نشد.")
        return
    txt = (message.text or "").strip()
    if txt != "-":
        st["phone"] = txt or None
    msg = bot.send_message(chat_id, "آدرس جدید را وارد کنید (یا - برای بدون تغییر):")
    bot.register_next_step_handler(msg, edit_courier_address_new)


def edit_courier_address_new(message):
    chat_id = message.chat.id
    st = user_sessions.get("edit_courier", {}).get(chat_id)
    if not st:
        bot.send_message(chat_id, "اطلاعات ویرایش یافت نشد.")
        return
    txt = (message.text or "").strip()
    if txt != "-":
        st["address"] = txt or None
    msg = bot.send_message(chat_id, "وضعیت جدید پیک (مثلاً available, busy, offline یا - برای بدون تغییر):")
    bot.register_next_step_handler(msg, edit_courier_status_new)


def edit_courier_status_new(message):
    chat_id = message.chat.id
    st = user_sessions.get("edit_courier", {}).get(chat_id)
    if not st:
        bot.send_message(chat_id, "اطلاعات ویرایش یافت نشد.")
        return
    txt = (message.text or "").strip()
    if txt != "-":
        st["status"] = txt or None

    conn = get_db_connection()
    if not conn:
        bot.send_message(chat_id, "خطا در اتصال به پایگاه داده.")
        return
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE couriers
            SET first_name = %s,
                last_name = %s,
                phone = %s,
                address = %s,
                status = %s
            WHERE id = %s
            """,
            (
                st["first_name"],
                st["last_name"],
                st["phone"],
                st["address"],
                st["status"],
                st["id"],
            ),
        )
        conn.commit()
        bot.send_message(chat_id, "پیک با موفقیت ویرایش شد.")
    except Error as e:
        bot.send_message(chat_id, f"خطا در ویرایش پیک: {e}")
    finally:
        conn.close()
        user_sessions.get("edit_courier", {}).pop(chat_id, None)


@bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "🗑 حذف پیک")
def delete_courier_start(message):
    msg = bot.send_message(message.chat.id, "کد پیک مورد نظر برای حذف را وارد کنید:")
    bot.register_next_step_handler(msg, delete_courier)


def delete_courier(message):
    chat_id = message.chat.id
    cid_text = (message.text or "").strip()
    if not cid_text.isdigit():
        bot.send_message(chat_id, "کد پیک باید عدد باشد.")
        return
    cid = int(cid_text)
    conn = get_db_connection()
    if not conn:
        bot.send_message(chat_id, "خطا در اتصال به پایگاه داده.")
        return
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM couriers WHERE id = %s", (cid,))
        if cur.rowcount == 0:
            bot.send_message(chat_id, "پیک با این کد یافت نشد.")
        else:
            conn.commit()
            bot.send_message(chat_id, "پیک با موفقیت حذف شد.")
    except Error as e:
        bot.send_message(chat_id, f"خطا در حذف پیک: {e}")
    finally:
        conn.close()


# ------------------------------------------------------------
# CRUD سفارش‌ها (orders + order_items)
# ------------------------------------------------------------
@bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "📄 لیست سفارش‌ها")
def list_orders(message):
    conn = get_db_connection()
    if not conn:
        bot.send_message(message.chat.id, "خطا در اتصال به پایگاه داده.")
        return
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, customer_id, courier_id, status, total_price, created_at
            FROM orders
            ORDER BY id DESC
            LIMIT 50
            """
        )
        rows = cur.fetchall()
        if not rows:
            bot.send_message(message.chat.id, "هیچ سفارشی ثبت نشده است.")
            return
        txt = "🧾 لیست سفارش‌ها:\n\n"
        for r in rows:
            created = r[5].strftime("%Y-%m-%d %H:%M") if r[5] else "-"
            txt += f"#{r[0]} | مشتری: {r[1]} | پیک: {r[2] or '-'}\n"
            txt += f"وضعیت: {r[3] or '-'} | مبلغ کل: {r[4] or 0}\n"
            txt += f"تاریخ ثبت: {created}\n"
            txt += "------------------------\n"
        bot.send_message(message.chat.id, txt)
    except Error as e:
        bot.send_message(message.chat.id, f"خطا در دریافت سفارش‌ها: {e}")
    finally:
        conn.close()


@bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "➕ ثبت سفارش جدید")
def add_order_start(message):
    msg = bot.send_message(message.chat.id, "کد مشتری سفارش را وارد کنید:")
    bot.register_next_step_handler(msg, add_order_customer)


def add_order_customer(message):
    chat_id = message.chat.id
    cid_text = (message.text or "").strip()
    if not cid_text.isdigit():
        bot.send_message(chat_id, "کد مشتری باید عدد باشد.")
        return
    cid = int(cid_text)
    msg = bot.send_message(chat_id, "آدرس تحویل را وارد کنید (یا - برای سفارش حضوری):")
    bot.register_next_step_handler(msg, add_order_address, cid)


def add_order_address(message, customer_id):
    chat_id = message.chat.id
    addr = (message.text or "").strip()
    if addr == "-":
        addr = "pickup at restaurant"
    msg = bot.send_message(
        chat_id,
        "روش پرداخت را وارد کنید (مثلاً cash یا card):",
    )
    bot.register_next_step_handler(msg, add_order_payment, customer_id, addr)


def add_order_payment(message, customer_id, delivery_address):
    chat_id = message.chat.id
    payment = (message.text or "").strip() or "cash"
    txt = (
        "لیست آیتم‌های سفارش را وارد کنید به صورت:\n"
        "<کد غذا>:<تعداد>,<کد غذا>:<تعداد>\n"
        "مثال: 1:2,3:1  یعنی 2 عدد از غذا 1 و 1 عدد از غذا 3"
    )
    msg = bot.send_message(chat_id, txt)
    bot.register_next_step_handler(
        msg,
        add_order_items,
        customer_id,
        delivery_address,
        payment,
    )


def add_order_items(message, customer_id, delivery_address, payment_method):
    chat_id = message.chat.id
    raw = (message.text or "").strip()
    if not raw:
        bot.send_message(chat_id, "ورودی خالی است.")
        return
    items = []
    try:
        parts = [p.strip() for p in raw.split(",") if p.strip()]
        for part in parts:
            mid, qty = part.split(":")
            mid = int(mid.strip())
            qty = int(qty.strip())
            if qty <= 0:
                continue
            items.append((mid, qty))
    except Exception:
        bot.send_message(chat_id, "فرمت ورودی نامعتبر است.")
        return

    if not items:
        bot.send_message(chat_id, "هیچ آیتم معتبری ثبت نشد.")
        return

    conn = get_db_connection()
    if not conn:
        bot.send_message(chat_id, "خطا در اتصال به پایگاه داده.")
        return
    try:
        cur = conn.cursor()
        order_type = "delivery" if delivery_address != "pickup at restaurant" else "pickup"
        cur.execute(
            """
            INSERT INTO orders (customer_id, delivery_address, order_type, status, payment_method, total_price)
            VALUES (%s, %s, %s, %s, %s, 0)
            RETURNING id
            """,
            (customer_id, delivery_address, order_type, "pending", payment_method),
        )
        order_id = cur.fetchone()[0]

        total_price = 0
        for mid, qty in items:
            cur.execute(
                "SELECT price, name FROM menu_items WHERE id = %s AND is_available = TRUE",
                (mid,),
            )
            row = cur.fetchone()
            if not row:
                continue
            price, name = row
            price = float(price)
            item_total = price * qty
            total_price += item_total
            cur.execute(
                """
                INSERT INTO order_items (order_id, menu_item_id, quantity, unit_price, total_price)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (order_id, mid, qty, price, item_total),
            )

        cur.execute(
            "UPDATE orders SET total_price = %s WHERE id = %s",
            (total_price, order_id),
        )
        conn.commit()
        bot.send_message(chat_id, f"سفارش جدید ثبت شد. کد سفارش: {order_id} | مبلغ کل: {total_price}")
    except Error as e:
        bot.send_message(chat_id, f"خطا در ثبت سفارش: {e}")
    finally:
        conn.close()


@bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "✏️ تغییر وضعیت سفارش")
def update_order_status_start(message):
    msg = bot.send_message(message.chat.id, "کد سفارش را وارد کنید:")
    bot.register_next_step_handler(msg, update_order_status_order)


def update_order_status_order(message):
    chat_id = message.chat.id
    oid_text = (message.text or "").strip()
    if not oid_text.isdigit():
        bot.send_message(chat_id, "کد سفارش باید عدد باشد.")
        return
    oid = int(oid_text)
    msg = bot.send_message(
        chat_id,
        "وضعیت جدید سفارش را وارد کنید (مثلاً pending, confirmed, delivered, cancelled):",
    )
    bot.register_next_step_handler(msg, update_order_status_set, oid)


def update_order_status_set(message, order_id):
    chat_id = message.chat.id
    status = (message.text or "").strip()
    if not status:
        bot.send_message(chat_id, "وضعیت خالی است.")
        return
    conn = get_db_connection()
    if not conn:
        bot.send_message(chat_id, "خطا در اتصال به پایگاه داده.")
        return
    try:
        cur = conn.cursor()
        delivered_at = None
        if status.lower() == "delivered":
            delivered_at = datetime.utcnow()
        cur.execute(
            """
            UPDATE orders
            SET status = %s,
                delivered_at = %s
            WHERE id = %s
            """,
            (status, delivered_at, order_id),
        )
        if cur.rowcount == 0:
            bot.send_message(chat_id, "سفارشی با این کد یافت نشد.")
        else:
            conn.commit()
            bot.send_message(chat_id, "وضعیت سفارش به‌روزرسانی شد.")
    except Error as e:
        bot.send_message(chat_id, f"خطا در تغییر وضعیت سفارش: {e}")
    finally:
        conn.close()


@bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "🗑 حذف سفارش")
def delete_order_start(message):
    msg = bot.send_message(message.chat.id, "کد سفارش مورد نظر برای حذف را وارد کنید:")
    bot.register_next_step_handler(msg, delete_order)


def delete_order(message):
    chat_id = message.chat.id
    oid_text = (message.text or "").strip()
    if not oid_text.isdigit():
        bot.send_message(chat_id, "کد سفارش باید عدد باشد.")
        return
    oid = int(oid_text)
    conn = get_db_connection()
    if not conn:
        bot.send_message(chat_id, "خطا در اتصال به پایگاه داده.")
        return
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM orders WHERE id = %s", (oid,))
        if cur.rowcount == 0:
            bot.send_message(chat_id, "سفارشی با این کد یافت نشد.")
        else:
            conn.commit()
            bot.send_message(chat_id, "سفارش با موفقیت حذف شد.")
    except Error as e:
        bot.send_message(chat_id, f"خطا در حذف سفارش: {e}")
    finally:
        conn.close()


# ------------------------------------------------------------
# نظرات و امتیاز غذاها (comments + item_score)
# ------------------------------------------------------------
@bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "➕ ثبت نظر/امتیاز برای غذا")
def add_comment_start(message):
    txt = (
        "برای ثبت نظر/امتیاز لطفاً اطلاعات را به صورت زیر وارد کنید:\n"
        "customer_id,order_id,menu_item_id,score(1-5),متن نظر\n"
        "مثال:\n"
        "1,10,3,5,غذای خیلی خوشمزه و داغ بود"
    )
    msg = bot.send_message(message.chat.id, txt)
    bot.register_next_step_handler(msg, add_comment_process)


def add_comment_process(message):
    chat_id = message.chat.id
    raw = (message.text or "").strip()
    try:
        parts = raw.split(",", 4)
        customer_id = int(parts[0].strip())
        order_id = int(parts[1].strip())
        menu_item_id = int(parts[2].strip())
        score = int(parts[3].strip())
        text = parts[4].strip() if len(parts) > 4 else ""
    except Exception:
        bot.send_message(chat_id, "فرمت ورودی نامعتبر است.")
        return

    if score < 1 or score > 5:
        bot.send_message(chat_id, "امتیاز باید بین 1 تا 5 باشد.")
        return

    conn = get_db_connection()
    if not conn:
        bot.send_message(chat_id, "خطا در اتصال به پایگاه داده.")
        return
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO comments (order_id, menu_item_id, customer_id, score, text)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (order_id, menu_item_id, customer_id, score, text),
        )

        # امتیاز item_score: یک رکورد در هر مشتری
        cur.execute(
            "SELECT id, score FROM item_score WHERE item_id = %s AND customer_id = %s",
            (menu_item_id, customer_id),
        )
        row = cur.fetchone()
        if row:
            cur.execute(
                "UPDATE item_score SET score = %s WHERE id = %s",
                (score, row[0]),
            )
        else:
            cur.execute(
                "INSERT INTO item_score (item_id, score, customer_id) VALUES (%s, %s, %s)",
                (menu_item_id, score, customer_id),
            )

        # به‌روزرسانی average_score در menu_items
        cur.execute(
            "SELECT AVG(score) FROM item_score WHERE item_id = %s",
            (menu_item_id,),
        )
        avg = cur.fetchone()[0] or 0
        cur.execute(
            "UPDATE menu_items SET average_score = %s WHERE id = %s",
            (avg, menu_item_id),
        )

        conn.commit()
        bot.send_message(chat_id, "نظر و امتیاز با موفقیت ثبت شد.")
    except Error as e:
        bot.send_message(chat_id, f"خطا در ثبت نظر: {e}")
    finally:
        conn.close()


@bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "📄 نمایش نظرات یک غذا")
def list_comments_start(message):
    msg = bot.send_message(message.chat.id, "کد غذا (menu_item_id) را وارد کنید:")
    bot.register_next_step_handler(msg, list_comments_for_item)


def list_comments_for_item(message):
    chat_id = message.chat.id
    mid_text = (message.text or "").strip()
    if not mid_text.isdigit():
        bot.send_message(chat_id, "کد غذا باید عدد باشد.")
        return
    mid = int(mid_text)
    conn = get_db_connection()
    if not conn:
        bot.send_message(chat_id, "خطا در اتصال به پایگاه داده.")
        return
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT c.id, c.score, c.text, c.created_at, cu.first_name, cu.last_name
            FROM comments c
            LEFT JOIN customers cu ON c.customer_id = cu.id
            WHERE c.menu_item_id = %s
            ORDER BY c.created_at DESC
            LIMIT 30
            """,
            (mid,),
        )
        rows = cur.fetchall()
        if not rows:
            bot.send_message(chat_id, "هنوز نظری برای این غذا ثبت نشده است.")
            return
        txt = f"⭐ نظرات غذا #{mid}:\n\n"
        for r in rows:
            created = r[3].strftime("%Y-%m-%d %H:%M") if r[3] else "-"
            name = (r[4] or "") + " " + (r[5] or "")
            txt += f"#{r[0]} | امتیاز: {r[1]} | مشتری: {name.strip() or '-'}\n"
            txt += f"{r[2] or ''}\n"
            txt += f"تاریخ: {created}\n"
            txt += "------------------------\n"
        bot.send_message(chat_id, txt)
    except Error as e:
        bot.send_message(chat_id, f"خطا در دریافت نظرات: {e}")
    finally:
        conn.close()


# ------------------------------------------------------------
# راه‌اندازی ربات
# ------------------------------------------------------------
if __name__ == "__main__":
    print("Restaurant bot is running ...")
    bot.polling(none_stop=True)

