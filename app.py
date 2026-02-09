import os
from functools import wraps
import psycopg2
from psycopg2 import Error
import telebot
from telebot import types


# ------------------------------------------------------------
# Configuration
# ------------------------------------------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
DB_URI = os.environ.get("DB_URI")

if not BOT_TOKEN or not DB_URI:
    raise RuntimeError("BOT_TOKEN or DB_URI is missing in .env file.")

bot = telebot.TeleBot(BOT_TOKEN)

# Session storage: chat_id -> { "logged_in": bool, "step_data": {} }
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

def is_logged_in(chat_id):
    return user_sessions.get(chat_id, {}).get("logged_in", False)

def login_required(func):
    @wraps(func)
    def wrapper(message, *args, **kwargs):
        if not is_logged_in(message.chat.id):
            bot.send_message(message.chat.id, "⛔ Unauthorized. Please login via /start")
            return
        return func(message, *args, **kwargs)
    return wrapper

# ------------------------------------------------------------
# Keyboards
# ------------------------------------------------------------
def main_menu_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add("📋 منوی غذاها", "👥 مشتریان", "🚴‍♂️ پیک‌ها", "🧾 سفارش‌ها", "⭐ نظرات", "🚪 خروج")
    return kb

def submenu_keyboard(item_type):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    # Buttons: Add, List, Edit, Delete, Back
    kb.add(f"➕ افزودن {item_type}", f"📄 لیست {item_type}‌ها", f"✏️ ویرایش {item_type}", f"🗑 حذف {item_type}", "⬅️ بازگشت")
    return kb

# ------------------------------------------------------------
# Auth Flow (Name + Phone)
# ------------------------------------------------------------
@bot.message_handler(commands=["start"])
def start_command(message):
    chat_id = message.chat.id
    if is_logged_in(chat_id):
        bot.send_message(chat_id, "🍽️ به سیستم مدیریت رستوران خوش آمدید!", reply_markup=main_menu_keyboard())
    else:
        bot.send_message(chat_id, "🍽️ سیستم مدیریت رستوران\nلطفاً نام خود را وارد کنید:", reply_markup=types.ReplyKeyboardRemove())
        bot.register_next_step_handler(message, process_login_name)

def process_login_name(message):
    name = message.text.strip()
    user_sessions[message.chat.id] = {"temp_name": name}
    bot.send_message(message.chat.id, "📱 لطفاً شماره تلفن خود را وارد کنید:")
    bot.register_next_step_handler(message, process_login_phone)

def process_login_phone(message):
    chat_id = message.chat.id
    phone = message.text.strip()
    name = user_sessions.get(chat_id, {}).get("temp_name")
    
    conn = get_db_connection()
    if not conn:
        bot.send_message(chat_id, "❌ Database connection failed.")
        return

    try:
        cur = conn.cursor()
        # Check if user exists, has phone, and is admin
        query = """
            SELECT u.role 
            FROM users u
            JOIN customers c ON u.customer_id = c.id
            JOIN customer_phones cp ON c.id = cp.customer_id
            WHERE c.first_name = %s AND cp.phone = %s
        """
        cur.execute(query, (name, phone))
        row = cur.fetchone()
        
        if row and row[0] == 'admin':
            user_sessions[chat_id] = {"logged_in": True}
            bot.send_message(chat_id, "✅ ورود موفقیت‌آمیز بود.", reply_markup=main_menu_keyboard())
        else:
            bot.send_message(chat_id, "❌ اطلاعات نامعتبر است یا دسترسی ادمین ندارید. /start")
    except Exception as e:
        bot.send_message(chat_id, f"Error: {e}")
    finally:
        conn.close()

@bot.message_handler(func=lambda m: m.text == "🚪 خروج")
def logout(message):
    user_sessions.pop(message.chat.id, None)
    bot.send_message(message.chat.id, "شما خارج شدید.", reply_markup=types.ReplyKeyboardRemove())

@bot.message_handler(func=lambda m: m.text == "⬅️ بازگشت")
def back_to_main(message):
    bot.send_message(message.chat.id, "منوی اصلی:", reply_markup=main_menu_keyboard())

# ------------------------------------------------------------
# 1. Food Management
# ------------------------------------------------------------
@bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "📋 منوی غذاها")
def menu_handler(message):
    bot.send_message(message.chat.id, "مدیریت منو:", reply_markup=submenu_keyboard("غذا"))

@bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "📄 لیست غذا‌ها")
def list_foods(message):
    conn = get_db_connection()
    if not conn: return
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, name, price, category, is_available FROM menu_items ORDER BY id")
        rows = cur.fetchall()
        if not rows:
            bot.send_message(message.chat.id, "لیست خالی است.")
            return
        
        txt = "🍔 لیست غذاها:\n\n"
        for r in rows:
            status = "✅" if r[4] else "❌"
            txt += f"🆔 {r[0]} | {r[1]} | {r[2]} تومان | {r[3] or '-'} | {status}\n"
        bot.send_message(message.chat.id, txt)
    finally:
        conn.close()

@bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "➕ افزودن غذا")
def add_food_step1(message):
    bot.send_message(message.chat.id, "نام غذا:")
    bot.register_next_step_handler(message, add_food_step2)

def add_food_step2(message):
    user_sessions[message.chat.id]["new_food"] = {"name": message.text.strip()}
    bot.send_message(message.chat.id, "قیمت (تومان):")
    bot.register_next_step_handler(message, add_food_step3)

def add_food_step3(message):
    try:
        price = float(message.text.strip())
        user_sessions[message.chat.id]["new_food"]["price"] = price
        bot.send_message(message.chat.id, "دسته بندی (یا -):")
        bot.register_next_step_handler(message, add_food_step4)
    except:
        bot.send_message(message.chat.id, "قیمت باید عدد باشد. مجدد وارد کنید:")
        bot.register_next_step_handler(message, add_food_step3)

def add_food_step4(message):
    data = user_sessions[message.chat.id]["new_food"]
    category = message.text.strip()
    
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("INSERT INTO menu_items (name, price, category, is_available) VALUES (%s, %s, %s, TRUE) RETURNING id",
                    (data["name"], data["price"], category))
        nid = cur.fetchone()[0]
        conn.commit()
        bot.send_message(message.chat.id, f"✅ غذا ثبت شد. کد: {nid}")
    finally:
        conn.close()

@bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "✏️ ویرایش غذا")
def edit_food_step1(message):
    bot.send_message(message.chat.id, "کد غذا برای ویرایش:")
    bot.register_next_step_handler(message, edit_food_step2)

def edit_food_step2(message):
    fid = message.text.strip()
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name, price, category, is_available FROM menu_items WHERE id = %s", (fid,))
    row = cur.fetchone()
    conn.close()
    
    if not row:
        bot.send_message(message.chat.id, "غذا یافت نشد.")
        return

    user_sessions[message.chat.id]["edit_food"] = {
        "id": row[0], "name": row[1], "price": row[2], "cat": row[3], "avail": row[4]
    }
    
    txt = (f"ویرایش #{row[0]}\nنام: {row[1]}\nقیمت: {row[2]}\nوضعیت: {row[4]}\n\nنام جدید (یا -):")
    bot.send_message(message.chat.id, txt)
    bot.register_next_step_handler(message, edit_food_step3)

def edit_food_step3(message):
    if message.text.strip() != "-": user_sessions[message.chat.id]["edit_food"]["name"] = message.text.strip()
    bot.send_message(message.chat.id, "قیمت جدید (یا -):")
    bot.register_next_step_handler(message, edit_food_step4)

def edit_food_step4(message):
    txt = message.text.strip()
    if txt != "-":
        try: user_sessions[message.chat.id]["edit_food"]["price"] = float(txt)
        except: pass 
    bot.send_message(message.chat.id, "دسته جدید (یا -):")
    bot.register_next_step_handler(message, edit_food_step5)

def edit_food_step5(message):
    if message.text.strip() != "-": user_sessions[message.chat.id]["edit_food"]["cat"] = message.text.strip()
    bot.send_message(message.chat.id, "موجودی (1=بله 0=خیر -:بدون تغییر):")
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
        bot.send_message(message.chat.id, "✅ ویرایش شد.")
    finally:
        conn.close()

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
        bot.send_message(message.chat.id, "🗑 حذف شد.")
    except Exception as e:
        bot.send_message(message.chat.id, f"Error: {e}")
    finally:
        conn.close()

# ------------------------------------------------------------
# 2. Customer Management
# ------------------------------------------------------------
@bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "👥 مشتریان")
def customer_handler(message):
    bot.send_message(message.chat.id, "مدیریت مشتریان:", reply_markup=submenu_keyboard("مشتری"))

@bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "📄 لیست مشتریان‌ها")
def list_customers(message):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT c.id, c.first_name, c.last_name, cp.phone 
        FROM customers c
        LEFT JOIN customer_phones cp ON c.id = cp.customer_id
        ORDER BY c.id DESC LIMIT 20
    """)
    rows = cur.fetchall()
    conn.close()
    
    txt = "👥 مشتریان:\n\n"
    if not rows: txt = "یافت نشد."
    for r in rows:
        txt += f"🆔 {r[0]} | {r[1]} {r[2]} | 📞 {r[3] or '-'}\n"
    bot.send_message(message.chat.id, txt)

@bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "➕ افزودن مشتری")
def add_cust_step1(message):
    bot.send_message(message.chat.id, "نام مشتری:")
    bot.register_next_step_handler(message, add_cust_step2)

def add_cust_step2(message):
    user_sessions[message.chat.id]["new_cust"] = {"fname": message.text.strip()}
    bot.send_message(message.chat.id, "نام خانوادگی:")
    bot.register_next_step_handler(message, add_cust_step3)

def add_cust_step3(message):
    user_sessions[message.chat.id]["new_cust"]["lname"] = message.text.strip()
    bot.send_message(message.chat.id, "شماره تلفن:")
    bot.register_next_step_handler(message, add_cust_step4)

def add_cust_step4(message):
    user_sessions[message.chat.id]["new_cust"]["phone"] = message.text.strip()
    bot.send_message(message.chat.id, "آدرس:")
    bot.register_next_step_handler(message, add_cust_final)

def add_cust_final(message):
    data = user_sessions[message.chat.id]["new_cust"]
    address = message.text.strip()
    
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("INSERT INTO customers (first_name, last_name) VALUES (%s, %s) RETURNING id", 
                    (data["fname"], data["lname"]))
        cust_id = cur.fetchone()[0]
        cur.execute("INSERT INTO customer_phones (phone, customer_id) VALUES (%s, %s)", 
                    (data["phone"], cust_id))
        if address and address != "-":
            cur.execute("INSERT INTO customer_address (address, customer_id) VALUES (%s, %s)",
                        (address, cust_id))
        conn.commit()
        bot.send_message(message.chat.id, f"✅ مشتری {cust_id} ثبت شد.")
    finally:
        conn.close()

@bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "✏️ ویرایش مشتری")
def edit_cust_step1(message):
    bot.send_message(message.chat.id, "کد مشتری:")
    bot.register_next_step_handler(message, edit_cust_step2)

def edit_cust_step2(message):
    cid = message.text.strip()
    conn = get_db_connection()
    cur = conn.cursor()
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
        bot.send_message(message.chat.id, "یافت نشد.")
        return

    user_sessions[message.chat.id]["edit_cust"] = {
        "id": row[0], "fname": row[1], "lname": row[2], "phone": row[3], "addr": row[4]
    }
    
    txt = (f"ویرایش #{row[0]}\nنام: {row[1]} {row[2]}\nتلفن: {row[3]}\nآدرس: {row[4]}\n\nنام جدید (یا -):")
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
        cur.execute("UPDATE customers SET first_name=%s, last_name=%s WHERE id=%s", 
                    (data["fname"], data["lname"], data["id"]))
        
        # Phone logic: delete old, insert new (simplest way to handle update if ID unknown)
        cur.execute("DELETE FROM customer_phones WHERE customer_id=%s", (data["id"],))
        if data["phone"]:
            cur.execute("INSERT INTO customer_phones (customer_id, phone) VALUES (%s, %s)", (data["id"], data["phone"]))
            
        # Address logic
        cur.execute("DELETE FROM customer_address WHERE customer_id=%s", (data["id"],))
        if data["addr"]:
            cur.execute("INSERT INTO customer_address (customer_id, address) VALUES (%s, %s)", (data["id"], data["addr"]))

        conn.commit()
        bot.send_message(message.chat.id, "✅ ویرایش مشتری انجام شد.")
    finally:
        conn.close()

@bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "🗑 حذف مشتری")
def del_cust_step1(message):
    bot.send_message(message.chat.id, "کد مشتری:")
    bot.register_next_step_handler(message, del_cust_final)

def del_cust_final(message):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM customers WHERE id = %s", (message.text.strip(),))
        conn.commit()
        bot.send_message(message.chat.id, "🗑 حذف شد.")
    except Exception as e:
        bot.send_message(message.chat.id, f"Error: {e}")
    finally:
        conn.close()

# ------------------------------------------------------------
# 3. Courier Management
# ------------------------------------------------------------
@bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "🚴‍♂️ پیک‌ها")
def courier_handler(message):
    bot.send_message(message.chat.id, "مدیریت پیک‌ها:", reply_markup=submenu_keyboard("پیک"))

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
    bot.send_message(message.chat.id, "تلفن:")
    bot.register_next_step_handler(message, add_cour_step4)

def add_cour_step4(message):
    user_sessions[message.chat.id]["new_cour"]["phone"] = message.text.strip()
    data = user_sessions[message.chat.id]["new_cour"]
    
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("INSERT INTO couriers (first_name, last_name, phone, status) VALUES (%s, %s, %s, 'available') RETURNING id",
                    (data["fname"], data["lname"], data["phone"]))
        cid = cur.fetchone()[0]
        conn.commit()
        bot.send_message(message.chat.id, f"✅ پیک ثبت شد. کد: {cid}")
    finally:
        conn.close()

# Full Edit Courier Flow
@bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "✏️ ویرایش پیک")
def edit_cour_step1(message):
    bot.send_message(message.chat.id, "کد پیک:")
    bot.register_next_step_handler(message, edit_cour_step2)

def edit_cour_step2(message):
    cid = message.text.strip()
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, first_name, last_name, phone, address, status FROM couriers WHERE id=%s", (cid,))
    row = cur.fetchone()
    conn.close()
    
    if not row:
        bot.send_message(message.chat.id, "پیک یافت نشد.")
        return

    user_sessions[message.chat.id]["edit_cour"] = {
        "id": row[0], "fname": row[1], "lname": row[2], "phone": row[3], "addr": row[4], "status": row[5]
    }
    
    txt = (f"ویرایش پیک #{row[0]}\nنام: {row[1]} {row[2]}\nتلفن: {row[3]}\nآدرس: {row[4]}\nوضعیت: {row[5]}\n\n"
           "نام جدید (یا -):")
    bot.send_message(message.chat.id, txt)
    bot.register_next_step_handler(message, edit_cour_step3)

def edit_cour_step3(message):
    if message.text.strip() != "-": user_sessions[message.chat.id]["edit_cour"]["fname"] = message.text.strip()
    bot.send_message(message.chat.id, "نام خانوادگی جدید (یا -):")
    bot.register_next_step_handler(message, edit_cour_step4)

def edit_cour_step4(message):
    if message.text.strip() != "-": user_sessions[message.chat.id]["edit_cour"]["lname"] = message.text.strip()
    bot.send_message(message.chat.id, "تلفن جدید (یا -):")
    bot.register_next_step_handler(message, edit_cour_step5)

def edit_cour_step5(message):
    if message.text.strip() != "-": user_sessions[message.chat.id]["edit_cour"]["phone"] = message.text.strip()
    bot.send_message(message.chat.id, "آدرس جدید (یا -):")
    bot.register_next_step_handler(message, edit_cour_step6)

def edit_cour_step6(message):
    if message.text.strip() != "-": user_sessions[message.chat.id]["edit_cour"]["addr"] = message.text.strip()
    bot.send_message(message.chat.id, "وضعیت جدید (مثل available, busy) (یا -):")
    bot.register_next_step_handler(message, edit_cour_final)

def edit_cour_final(message):
    if message.text.strip() != "-": user_sessions[message.chat.id]["edit_cour"]["status"] = message.text.strip()
    data = user_sessions[message.chat.id]["edit_cour"]
    
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            UPDATE couriers SET first_name=%s, last_name=%s, phone=%s, address=%s, status=%s 
            WHERE id=%s
        """, (data["fname"], data["lname"], data["phone"], data["addr"], data["status"], data["id"]))
        conn.commit()
        bot.send_message(message.chat.id, "✅ ویرایش پیک کامل شد.")
    finally:
        conn.close()

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
        bot.send_message(message.chat.id, f"Error: {e}")
    finally:
        conn.close()

# ------------------------------------------------------------
# 4. Orders
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

@bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "➕ افزودن سفارش")
def add_order_step1(message):
    bot.send_message(message.chat.id, "کد مشتری:")
    bot.register_next_step_handler(message, add_order_step2)

def add_order_step2(message):
    cid = message.text.strip()
    user_sessions[message.chat.id]["new_order"] = {"cid": cid}
    bot.send_message(message.chat.id, "آیتم‌ها (کدغذا:تعداد, کدغذا:تعداد)\nمثال: 1:2, 5:1")
    bot.register_next_step_handler(message, add_order_step3)

def add_order_step3(message):
    raw_items = message.text.strip()
    cid = user_sessions[message.chat.id]["new_order"]["cid"]
    
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("INSERT INTO orders (customer_id, status, order_type, total_price) VALUES (%s, 'pending', 'delivery', 0) RETURNING id", (cid,))
        order_id = cur.fetchone()[0]
        
        total_price = 0
        items = raw_items.split(",")
        for item in items:
            if ":" not in item: continue
            fid, qty = item.split(":")
            fid, qty = int(fid), int(qty)
            
            cur.execute("SELECT price FROM menu_items WHERE id=%s", (fid,))
            res = cur.fetchone()
            if not res: continue
            price = res[0]
            
            item_total = float(price) * qty
            total_price += item_total
            
            cur.execute("INSERT INTO order_items (order_id, menu_item_id, quantity, unit_price, total_price) VALUES (%s, %s, %s, %s, %s)",
                        (order_id, fid, qty, price, item_total))
            
        cur.execute("UPDATE orders SET total_price=%s WHERE id=%s", (total_price, order_id))
        conn.commit()
        bot.send_message(message.chat.id, f"✅ سفارش #{order_id} با مبلغ {total_price} ثبت شد.")
        
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ خطا در ثبت: {e}")
    finally:
        conn.close()

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
        bot.send_message(message.chat.id, f"Error: {e}")
    finally:
        conn.close()

# ------------------------------------------------------------
# Execution
# ------------------------------------------------------------
if __name__ == "__main__":
    print("Bot is running...")
    bot.infinity_polling()
