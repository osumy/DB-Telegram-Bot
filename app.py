import os
from functools import wraps
from datetime import datetime

import psycopg2
from psycopg2 import Error
import telebot
from telebot import types


# ------------------------------------------------------------
# تنظیمات و متغیرهای محیطی
# ------------------------------------------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
DB_URI = os.environ.get("DB_URI")
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")

if not BOT_TOKEN or not DB_URI:
    raise RuntimeError("لطفاً BOT_TOKEN و DB_URI را در فایل .env تنظیم کنید.")

bot = telebot.TeleBot(BOT_TOKEN)

# حافظه موقت برای مدیریت وضعیت کاربران
# ساختار: chat_id -> { "logged_in": bool, "step_data": {} }
user_sessions = {}

# ------------------------------------------------------------
# توابع کمکی دیتابیس و احراز هویت
# ------------------------------------------------------------
def get_db_connection():
    try:
        conn = psycopg2.connect(DB_URI)
        return conn
    except Error as e:
        print(f"خطای اتصال به دیتابیس: {e}")
        return None

def is_logged_in(chat_id):
    return user_sessions.get(chat_id, {}).get("logged_in", False)

def login_required(func):
    @wraps(func)
    def wrapper(message, *args, **kwargs):
        if not is_logged_in(message.chat.id):
            bot.send_message(message.chat.id, "⛔ دسترسی غیرمجاز. ابتدا با /start وارد شوید.")
            return
        return func(message, *args, **kwargs)
    return wrapper

# ------------------------------------------------------------
# کیبوردها (منوها)
# ------------------------------------------------------------
def main_menu_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add("📋 منوی غذاها", "👥 مشتریان", "🚴‍♂️ پیک‌ها", "🧾 سفارش‌ها", "⭐ نظرات", "🚪 خروج")
    return kb

def submenu_keyboard(item_type):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    # item_type can be: غذا, مشتری, پیک, سفارش
    kb.add(f"➕ افزودن {item_type}", f"📄 لیست {item_type}‌ها", f"✏️ ویرایش {item_type}", f"🗑 حذف {item_type}", "⬅️ بازگشت")
    return kb

# ------------------------------------------------------------
# بخش 1: شروع و ورود (Login)
# ------------------------------------------------------------
@bot.message_handler(commands=["start"])
def start_command(message):
    chat_id = message.chat.id
    if is_logged_in(chat_id):
        bot.send_message(chat_id, "خوش آمدید! یکی از گزینه‌ها را انتخاب کنید:", reply_markup=main_menu_keyboard())
    else:
        bot.send_message(chat_id, "🔐 سیستم مدیریت رستوران\nلطفاً نام کاربری ادمین را وارد کنید:", reply_markup=types.ReplyKeyboardRemove())
        bot.register_next_step_handler(message, process_username)

def process_username(message):
    user_sessions[message.chat.id] = {"temp_user": message.text.strip()}
    bot.send_message(message.chat.id, "🔑 رمز عبور را وارد کنید:")
    bot.register_next_step_handler(message, process_password)

def process_password(message):
    chat_id = message.chat.id
    username = user_sessions.get(chat_id, {}).get("temp_user")
    password = message.text.strip()
    
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        user_sessions[chat_id] = {"logged_in": True}
        bot.send_message(chat_id, "✅ ورود موفقیت‌آمیز بود.", reply_markup=main_menu_keyboard())
    else:
        bot.send_message(chat_id, "❌ اطلاعات ورود اشتباه است. مجدداً تلاش کنید: /start")

@bot.message_handler(func=lambda m: m.text == "🚪 خروج")
def logout(message):
    user_sessions.pop(message.chat.id, None)
    bot.send_message(message.chat.id, "شما از سیستم خارج شدید.", reply_markup=types.ReplyKeyboardRemove())

@bot.message_handler(func=lambda m: m.text == "⬅️ بازگشت")
def back_to_main(message):
    bot.send_message(message.chat.id, "منوی اصلی:", reply_markup=main_menu_keyboard())

# ------------------------------------------------------------
# بخش 2: مدیریت غذاها (Menu Items)
# ------------------------------------------------------------
@bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "📋 منوی غذاها")
def menu_handler(message):
    bot.send_message(message.chat.id, "مدیریت منو:", reply_markup=submenu_keyboard("غذا"))

# --- لیست غذاها ---
@bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "📄 لیست غذا‌ها")
def list_foods(message):
    conn = get_db_connection()
    if not conn: return
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, name, price, category, is_available FROM menu_items ORDER BY id")
        rows = cur.fetchall()
        if not rows:
            bot.send_message(message.chat.id, "هیچ غذایی یافت نشد.")
            return
        
        txt = "🍔 لیست غذاها:\n\n"
        for r in rows:
            status = "✅" if r[4] else "❌"
            txt += f"🆔 {r[0]} | {r[1]} | {r[2]} تومان | {r[3] or '-'} | {status}\n"
        bot.send_message(message.chat.id, txt)
    finally:
        conn.close()

# --- افزودن غذا ---
@bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "➕ افزودن غذا")
def add_food_step1(message):
    bot.send_message(message.chat.id, "نام غذا را وارد کنید:")
    bot.register_next_step_handler(message, add_food_step2)

def add_food_step2(message):
    user_sessions[message.chat.id]["new_food"] = {"name": message.text.strip()}
    bot.send_message(message.chat.id, "قیمت غذا (تومان) را وارد کنید:")
    bot.register_next_step_handler(message, add_food_step3)

def add_food_step3(message):
    try:
        price = float(message.text.strip())
        user_sessions[message.chat.id]["new_food"]["price"] = price
        bot.send_message(message.chat.id, "دسته بندی غذا (مثلاً پیتزا، نوشیدنی):")
        bot.register_next_step_handler(message, add_food_step4)
    except ValueError:
        bot.send_message(message.chat.id, "❌ قیمت باید عدد باشد. لطفاً دوباره قیمت را وارد کنید:")
        bot.register_next_step_handler(message, add_food_step3)

def add_food_step4(message):
    data = user_sessions[message.chat.id]["new_food"]
    category = message.text.strip()
    
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("INSERT INTO menu_items (name, price, category, is_available) VALUES (%s, %s, %s, TRUE) RETURNING id",
                    (data["name"], data["price"], category))
        new_id = cur.fetchone()[0]
        conn.commit()
        bot.send_message(message.chat.id, f"✅ غذا با کد {new_id} ثبت شد.")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ خطا: {e}")
    finally:
        conn.close()

# --- ویرایش غذا ---
@bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "✏️ ویرایش غذا")
def edit_food_step1(message):
    bot.send_message(message.chat.id, "کد (ID) غذا را وارد کنید:")
    bot.register_next_step_handler(message, edit_food_step2)

def edit_food_step2(message):
    fid = message.text.strip()
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name, price, category, is_available FROM menu_items WHERE id = %s", (fid,))
    row = cur.fetchone()
    conn.close()
    
    if not row:
        bot.send_message(message.chat.id, "❌ غذا یافت نشد.")
        return

    user_sessions[message.chat.id]["edit_food"] = {
        "id": row[0], "name": row[1], "price": row[2], "cat": row[3], "avail": row[4]
    }
    
    txt = (f"ویرایش غذا #{row[0]}\n"
           f"نام فعلی: {row[1]}\n"
           f"قیمت فعلی: {row[2]}\n"
           f"دسته فعلی: {row[3]}\n"
           f"موجودی: {'بله' if row[4] else 'خیر'}\n\n"
           "نام جدید را وارد کنید (یا - برای بدون تغییر):")
    bot.send_message(message.chat.id, txt)
    bot.register_next_step_handler(message, edit_food_step3)

def edit_food_step3(message):
    if message.text.strip() != "-":
        user_sessions[message.chat.id]["edit_food"]["name"] = message.text.strip()
    bot.send_message(message.chat.id, "قیمت جدید (یا -):")
    bot.register_next_step_handler(message, edit_food_step4)

def edit_food_step4(message):
    txt = message.text.strip()
    if txt != "-":
        try:
            user_sessions[message.chat.id]["edit_food"]["price"] = float(txt)
        except: pass 
    bot.send_message(message.chat.id, "دسته بندی جدید (یا -):")
    bot.register_next_step_handler(message, edit_food_step5)

def edit_food_step5(message):
    if message.text.strip() != "-":
        user_sessions[message.chat.id]["edit_food"]["cat"] = message.text.strip()
    bot.send_message(message.chat.id, "موجودی (1=بله، 0=خیر، -=بدون تغییر):")
    bot.register_next_step_handler(message, edit_food_final)

def edit_food_final(message):
    txt = message.text.strip()
    data = user_sessions[message.chat.id]["edit_food"]
    
    if txt == "1": data["avail"] = True
    elif txt == "0": data["avail"] = False

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE menu_items SET name=%s, price=%s, category=%s, is_available=%s WHERE id=%s",
                    (data["name"], data["price"], data["cat"], data["avail"], data["id"]))
        conn.commit()
        bot.send_message(message.chat.id, "✅ ویرایش انجام شد.")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ خطا: {e}")
    finally:
        conn.close()

# --- حذف غذا ---
@bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "🗑 حذف غذا")
def delete_food_step1(message):
    bot.send_message(message.chat.id, "کد غذا برای حذف:")
    bot.register_next_step_handler(message, delete_food_final)

def delete_food_final(message):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM menu_items WHERE id = %s", (message.text.strip(),))
        conn.commit()
        bot.send_message(message.chat.id, "🗑 غذا حذف شد.")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ خطا (شاید در سفارش استفاده شده باشد): {e}")
    finally:
        conn.close()

# ------------------------------------------------------------
# بخش 3: مدیریت مشتریان (Customers)
# ------------------------------------------------------------
@bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "👥 مشتریان")
def customer_handler(message):
    bot.send_message(message.chat.id, "مدیریت مشتریان:", reply_markup=submenu_keyboard("مشتری"))

# --- لیست مشتریان ---
@bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "📄 لیست مشتریان‌ها")
def list_customers(message):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT c.id, c.first_name, c.last_name, cp.phone, ca.address 
        FROM customers c
        LEFT JOIN customer_phones cp ON c.id = cp.customer_id
        LEFT JOIN customer_address ca ON c.id = ca.customer_id
        ORDER BY c.id DESC LIMIT 20
    """)
    rows = cur.fetchall()
    conn.close()
    
    txt = "👥 آخرین مشتریان:\n\n"
    if not rows: txt = "مشتری یافت نشد."
    for r in rows:
        txt += f"🆔 {r[0]} | {r[1]} {r[2]}\n📞 {r[3] or '-'}\n📍 {r[4] or '-'}\n-----------------\n"
    bot.send_message(message.chat.id, txt)

# --- افزودن مشتری ---
@bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "➕ افزودن مشتری")
def add_cust_step1(message):
    bot.send_message(message.chat.id, "نام کوچک مشتری:")
    bot.register_next_step_handler(message, add_cust_step2)

def add_cust_step2(message):
    user_sessions[message.chat.id]["new_cust"] = {"fname": message.text.strip()}
    bot.send_message(message.chat.id, "نام خانوادگی مشتری:")
    bot.register_next_step_handler(message, add_cust_step3)

def add_cust_step3(message):
    user_sessions[message.chat.id]["new_cust"]["lname"] = message.text.strip()
    bot.send_message(message.chat.id, "شماره تلفن:")
    bot.register_next_step_handler(message, add_cust_step4)

def add_cust_step4(message):
    user_sessions[message.chat.id]["new_cust"]["phone"] = message.text.strip()
    bot.send_message(message.chat.id, "آدرس (اختیاری):")
    bot.register_next_step_handler(message, add_cust_final)

def add_cust_final(message):
    data = user_sessions[message.chat.id]["new_cust"]
    address = message.text.strip()
    
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        # 1. Insert Customer
        cur.execute("INSERT INTO customers (first_name, last_name) VALUES (%s, %s) RETURNING id", 
                    (data["fname"], data["lname"]))
        cust_id = cur.fetchone()[0]
        
        # 2. Insert Phone
        cur.execute("INSERT INTO customer_phones (phone, customer_id) VALUES (%s, %s)", 
                    (data["phone"], cust_id))
        
        # 3. Insert Address (if provided)
        if address and address != "-":
            cur.execute("INSERT INTO customer_address (address, customer_id) VALUES (%s, %s)",
                        (address, cust_id))
            
        conn.commit()
        bot.send_message(message.chat.id, f"✅ مشتری با کد {cust_id} ثبت شد.")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ خطا: {e}")
    finally:
        conn.close()

# --- ویرایش مشتری ---
@bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "✏️ ویرایش مشتری")
def edit_cust_step1(message):
    bot.send_message(message.chat.id, "کد مشتری را وارد کنید:")
    bot.register_next_step_handler(message, edit_cust_step2)

def edit_cust_step2(message):
    cid = message.text.strip()
    conn = get_db_connection()
    cur = conn.cursor()
    # Join tables to get current data
    cur.execute("""
        SELECT c.id, c.first_name, c.last_name, cp.phone, ca.address
        FROM customers c
        LEFT JOIN customer_phones cp ON c.id = cp.customer_id
        LEFT JOIN customer_address ca ON c.id = ca.customer_id
        WHERE c.id = %s
    """, (cid,))
    row = cur.fetchone()
    conn.close()
    
    if not row:
        bot.send_message(message.chat.id, "❌ مشتری یافت نشد.")
        return

    user_sessions[message.chat.id]["edit_cust"] = {
        "id": row[0], "fname": row[1], "lname": row[2], "phone": row[3], "addr": row[4]
    }
    
    txt = (f"ویرایش مشتری #{row[0]}\n"
           f"نام: {row[1]} {row[2]}\n"
           f"تلفن: {row[3]}\n"
           f"آدرس: {row[4]}\n\n"
           "نام کوچک جدید (یا -):")
    bot.send_message(message.chat.id, txt)
    bot.register_next_step_handler(message, edit_cust_step3)

def edit_cust_step3(message):
    if message.text.strip() != "-": user_sessions[message.chat.id]["edit_cust"]["fname"] = message.text.strip()
    bot.send_message(message.chat.id, "نام خانوادگی جدید (یا -):")
    bot.register_next_step_handler(message, edit_cust_step4)

def edit_cust_step4(message):
    if message.text.strip() != "-": user_sessions[message.chat.id]["edit_cust"]["lname"] = message.text.strip()
    bot.send_message(message.chat.id, "تلفن جدید (یا -):")
    bot.register_next_step_handler(message, edit_cust_step5)

def edit_cust_step5(message):
    if message.text.strip() != "-": user_sessions[message.chat.id]["edit_cust"]["phone"] = message.text.strip()
    bot.send_message(message.chat.id, "آدرس جدید (یا -):")
    bot.register_next_step_handler(message, edit_cust_final)

def edit_cust_final(message):
    if message.text.strip() != "-": user_sessions[message.chat.id]["edit_cust"]["addr"] = message.text.strip()
    data = user_sessions[message.chat.id]["edit_cust"]
    
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        # Update Main info
        cur.execute("UPDATE customers SET first_name=%s, last_name=%s WHERE id=%s", 
                    (data["fname"], data["lname"], data["id"]))
        
        # Update/Insert Phone
        cur.execute("DELETE FROM customer_phones WHERE customer_id=%s", (data["id"],))
        if data["phone"]:
            cur.execute("INSERT INTO customer_phones (customer_id, phone) VALUES (%s, %s)", (data["id"], data["phone"]))
            
        # Update/Insert Address
        cur.execute("DELETE FROM customer_address WHERE customer_id=%s", (data["id"],))
        if data["addr"]:
            cur.execute("INSERT INTO customer_address (customer_id, address) VALUES (%s, %s)", (data["id"], data["addr"]))

        conn.commit()
        bot.send_message(message.chat.id, "✅ اطلاعات مشتری بروزرسانی شد.")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ خطا: {e}")
    finally:
        conn.close()

# --- حذف مشتری ---
@bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "🗑 حذف مشتری")
def del_cust_step1(message):
    bot.send_message(message.chat.id, "کد مشتری برای حذف:")
    bot.register_next_step_handler(message, del_cust_final)

def del_cust_final(message):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM customers WHERE id = %s", (message.text.strip(),))
        if cur.rowcount == 0:
            bot.send_message(message.chat.id, "مشتری یافت نشد.")
        else:
            conn.commit()
            bot.send_message(message.chat.id, "🗑 مشتری حذف شد.")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ خطا: {e}")
    finally:
        conn.close()

# ------------------------------------------------------------
# بخش 4: مدیریت پیک‌ها (Couriers)
# ------------------------------------------------------------
@bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "🚴‍♂️ پیک‌ها")
def courier_handler(message):
    bot.send_message(message.chat.id, "مدیریت پیک‌ها:", reply_markup=submenu_keyboard("پیک"))

# --- لیست پیک‌ها ---
@bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "📄 لیست پیک‌ها‌ها")
def list_couriers(message):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, first_name, last_name, phone, status FROM couriers ORDER BY id")
    rows = cur.fetchall()
    conn.close()
    
    txt = "🚴‍♂️ لیست پیک‌ها:\n\n"
    if not rows: txt = "پیکی یافت نشد."
    for r in rows:
        txt += f"🆔 {r[0]} | {r[1]} {r[2]}\n📞 {r[3]} | وضعیت: {r[4]}\n-----------------\n"
    bot.send_message(message.chat.id, txt)

# --- افزودن پیک ---
@bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "➕ افزودن پیک")
def add_cour_step1(message):
    bot.send_message(message.chat.id, "نام پیک:")
    bot.register_next_step_handler(message, add_cour_step2)

def add_cour_step2(message):
    user_sessions[message.chat.id]["new_cour"] = {"fname": message.text.strip()}
    bot.send_message(message.chat.id, "نام خانوادگی پیک:")
    bot.register_next_step_handler(message, add_cour_step3)

def add_cour_step3(message):
    user_sessions[message.chat.id]["new_cour"]["lname"] = message.text.strip()
    bot.send_message(message.chat.id, "شماره تلفن:")
    bot.register_next_step_handler(message, add_cour_step4)

def add_cour_step4(message):
    user_sessions[message.chat.id]["new_cour"]["phone"] = message.text.strip()
    conn = get_db_connection()
    try:
        data = user_sessions[message.chat.id]["new_cour"]
        cur = conn.cursor()
        cur.execute("INSERT INTO couriers (first_name, last_name, phone, status) VALUES (%s, %s, %s, 'available') RETURNING id",
                    (data["fname"], data["lname"], data["phone"]))
        cid = cur.fetchone()[0]
        conn.commit()
        bot.send_message(message.chat.id, f"✅ پیک با کد {cid} ثبت شد.")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ خطا: {e}")
    finally:
        conn.close()

# --- حذف پیک ---
@bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "🗑 حذف پیک")
def del_cour_step1(message):
    bot.send_message(message.chat.id, "کد پیک برای حذف:")
    bot.register_next_step_handler(message, del_cour_final)

def del_cour_final(message):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM couriers WHERE id = %s", (message.text.strip(),))
        conn.commit()
        bot.send_message(message.chat.id, "🗑 پیک حذف شد.")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ خطا: {e}")
    finally:
        conn.close()

# --- ویرایش پیک (ساده شده) ---
@bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "✏️ ویرایش پیک")
def edit_cour_step1(message):
    bot.send_message(message.chat.id, "کد پیک را وارد کنید:")
    bot.register_next_step_handler(message, edit_cour_step2)

def edit_cour_step2(message):
    cid = message.text.strip()
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, first_name, last_name, phone, status FROM couriers WHERE id=%s", (cid,))
    row = cur.fetchone()
    conn.close()
    
    if not row:
        bot.send_message(message.chat.id, "پیک یافت نشد.")
        return

    user_sessions[message.chat.id]["edit_cour"] = {"id": row[0], "fname": row[1], "lname": row[2], "phone": row[3], "status": row[4]}
    
    txt = (f"ویرایش پیک #{row[0]}\nنام: {row[1]} {row[2]}\nتلفن: {row[3]}\nوضعیت: {row[4]}\n\n"
           "نام جدید (یا -):")
    bot.send_message(message.chat.id, txt)
    bot.register_next_step_handler(message, edit_cour_final_step)

def edit_cour_final_step(message):
    # برای خلاصه کردن، فقط نام و وضعیت را اینجا آپدیت می‌کنیم (بقیه مشابه مشتری است)
    if message.text.strip() != "-": user_sessions[message.chat.id]["edit_cour"]["fname"] = message.text.strip()
    
    # آپدیت مستقیم
    data = user_sessions[message.chat.id]["edit_cour"]
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE couriers SET first_name=%s WHERE id=%s", (data["fname"], data["id"]))
        conn.commit()
        bot.send_message(message.chat.id, "✅ نام پیک بروزرسانی شد (برای سایر فیلدها کد را گسترش دهید).")
    finally:
        conn.close()

# ------------------------------------------------------------
# بخش 5: مدیریت سفارش‌ها (Orders)
# ------------------------------------------------------------
@bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "🧾 سفارش‌ها")
def order_handler(message):
    bot.send_message(message.chat.id, "مدیریت سفارش‌ها:", reply_markup=submenu_keyboard("سفارش"))

@bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "📄 لیست سفارش‌ها‌ها")
def list_orders(message):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, customer_id, total_price, status, created_at FROM orders ORDER BY id DESC LIMIT 10")
    rows = cur.fetchall()
    conn.close()
    
    txt = "🧾 آخرین سفارش‌ها:\n\n"
    for r in rows:
        txt += f"🆔 {r[0]} | مشتری: {r[1]} | مبلغ: {r[2]}\nوضعیت: {r[3]} | زمان: {r[4].strftime('%Y-%m-%d %H:%M')}\n-----------------\n"
    bot.send_message(message.chat.id, txt)

# --- ثبت سفارش جدید ---
@bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "➕ افزودن سفارش")
def add_order_step1(message):
    bot.send_message(message.chat.id, "کد مشتری را وارد کنید:")
    bot.register_next_step_handler(message, add_order_step2)

def add_order_step2(message):
    cid = message.text.strip()
    user_sessions[message.chat.id]["new_order"] = {"cid": cid}
    bot.send_message(message.chat.id, "آیتم‌ها را وارد کنید (فرمت: کدغذا:تعداد, کدغذا:تعداد)\nمثال: 1:2, 5:1")
    bot.register_next_step_handler(message, add_order_step3)

def add_order_step3(message):
    raw_items = message.text.strip()
    cid = user_sessions[message.chat.id]["new_order"]["cid"]
    
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        # 1. ایجاد سفارش اولیه
        cur.execute("INSERT INTO orders (customer_id, status, order_type, total_price) VALUES (%s, 'pending', 'delivery', 0) RETURNING id", (cid,))
        order_id = cur.fetchone()[0]
        
        total_price = 0
        
        # 2. پردازش آیتم‌ها
        items = raw_items.split(",")
        for item in items:
            if ":" not in item: continue
            fid, qty = item.split(":")
            fid, qty = int(fid), int(qty)
            
            # دریافت قیمت غذا
            cur.execute("SELECT price FROM menu_items WHERE id=%s", (fid,))
            price = cur.fetchone()[0]
            item_total = float(price) * qty
            total_price += item_total
            
            # افزودن به order_items
            cur.execute("INSERT INTO order_items (order_id, menu_item_id, quantity, unit_price, total_price) VALUES (%s, %s, %s, %s, %s)",
                        (order_id, fid, qty, price, item_total))
            
        # 3. آپدیت قیمت نهایی
        cur.execute("UPDATE orders SET total_price=%s WHERE id=%s", (total_price, order_id))
        conn.commit()
        bot.send_message(message.chat.id, f"✅ سفارش #{order_id} با مبلغ {total_price} ثبت شد.")
        
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ خطا در ثبت سفارش (فرمت را چک کنید): {e}")
    finally:
        conn.close()

# --- حذف سفارش ---
@bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "🗑 حذف سفارش")
def del_order_step1(message):
    bot.send_message(message.chat.id, "کد سفارش برای حذف:")
    bot.register_next_step_handler(message, del_order_final)

def del_order_final(message):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM orders WHERE id=%s", (message.text.strip(),))
        conn.commit()
        bot.send_message(message.chat.id, "🗑 سفارش حذف شد.")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ خطا: {e}")
    finally:
        conn.close()

# ------------------------------------------------------------
# اجرای برنامه
# ------------------------------------------------------------
if __name__ == "__main__":
    print("🤖 ربات رستوران در حال اجراست...")
    bot.infinity_polling()
