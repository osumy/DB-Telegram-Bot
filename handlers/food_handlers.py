from helpers import get_db_connection, is_logged_in
from keyboards import *

def register_food_handlers(bot, user_sessions):
    @bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "📋 منوی غذاها")
    def menu_handler(message):
        bot.send_message(message.chat.id, "مدیریت غذاها:", reply_markup=submenu_keyboard("غذا"))

    @bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "📄 لیست غذا‌ها")
    def list_foods(message):
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, name, price, category, is_available FROM menu_items ORDER BY id")
        rows = cur.fetchall()
        conn.close()

        if not rows:
            bot.send_message(message.chat.id, "لیست خالی است.")
            return

        txt = "🍔 لیست غذاها:\n\n"
        for r in rows:
            status = "✅" if r[4] else "❌"
            txt += f"🆔 {r[0]} | {r[1]} | {r[2]} تومان | {r[3] or '-'} | {status}\n"
        bot.send_message(message.chat.id, txt)

    @bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "➕ افزودن غذا")
    def add_food_s1(message):
        bot.send_message(message.chat.id, "نام غذا:")
        bot.register_next_step_handler(message, add_food_s2)

    def add_food_s2(message):
        user_sessions[message.chat.id]["new_food"] = {"name": message.text.strip()}
        bot.send_message(message.chat.id, "قیمت (تومان):")
        bot.register_next_step_handler(message, add_food_s3)

    def add_food_s3(message):
        try:
            user_sessions[message.chat.id]["new_food"]["price"] = float(message.text.strip())
            bot.send_message(message.chat.id, "دسته بندی (مثلا پیتزا):")
            bot.register_next_step_handler(message, add_food_s4)
        except:
            bot.send_message(message.chat.id, "قیمت باید عدد باشد. مجدد:")
            bot.register_next_step_handler(message, add_food_s3)

    def add_food_s4(message):
        data = user_sessions[message.chat.id]["new_food"]
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO menu_items (name, price, category, is_available) VALUES (%s, %s, %s, TRUE) RETURNING id",
                (data["name"], data["price"], message.text.strip()))
            nid = cur.fetchone()[0]
            conn.commit()
            bot.send_message(message.chat.id, f"✅ غذا با کد {nid} ثبت شد.")
        finally:
            conn.close()

    @bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "✏️ ویرایش غذا")
    def edit_food_s1(message):
        bot.send_message(message.chat.id, "کد غذا برای ویرایش:")
        bot.register_next_step_handler(message, edit_food_s2)

    def edit_food_s2(message):
        fid = message.text.strip()
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, name, price, category, is_available FROM menu_items WHERE id=%s", (fid,))
        row = cur.fetchone()
        conn.close()

        if not row:
            bot.send_message(message.chat.id, "غذا یافت نشد.")
            return

        user_sessions[message.chat.id]["edit_food"] = {"id": row[0], "name": row[1], "price": row[2], "cat": row[3],
                                                       "avail": row[4]}
        txt = f"نام فعلی: {row[1]}\nقیمت: {row[2]}\nوضعیت: {row[4]}\n\nنام جدید (یا -):"
        bot.send_message(message.chat.id, txt)
        bot.register_next_step_handler(message, edit_food_s3)

    def edit_food_s3(message):
        if message.text.strip() != "-": user_sessions[message.chat.id]["edit_food"]["name"] = message.text.strip()
        bot.send_message(message.chat.id, "قیمت جدید (یا -):")
        bot.register_next_step_handler(message, edit_food_s4)

    def edit_food_s4(message):
        if message.text.strip() != "-":
            try:
                user_sessions[message.chat.id]["edit_food"]["price"] = float(message.text.strip())
            except:
                pass
        bot.send_message(message.chat.id, "دسته جدید (یا -):")
        bot.register_next_step_handler(message, edit_food_s5)

    def edit_food_s5(message):
        if message.text.strip() != "-": user_sessions[message.chat.id]["edit_food"]["cat"] = message.text.strip()
        bot.send_message(message.chat.id, "موجودی (1=بله 0=خیر -:بدون تغییر):")
        bot.register_next_step_handler(message, edit_food_final)

    def edit_food_final(message):
        txt = message.text.strip()
        data = user_sessions[message.chat.id]["edit_food"]
        if txt == "1":
            data["avail"] = True
        elif txt == "0":
            data["avail"] = False

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE menu_items SET name=%s, price=%s, category=%s, is_available=%s WHERE id=%s",
                    (data["name"], data["price"], data["cat"], data["avail"], data["id"]))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, "✅ ویرایش غذا انجام شد.")

    @bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "🗑 حذف غذا")
    def del_food_s1(message):
        bot.send_message(message.chat.id, "کد غذا برای حذف:")
        bot.register_next_step_handler(message, del_food_final)

    def del_food_final(message):
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("DELETE FROM menu_items WHERE id=%s", (message.text.strip(),))
            conn.commit()
            bot.send_message(message.chat.id, "🗑 غذا حذف شد.")
            conn.close()
        except:
            bot.send_message(message.chat.id, "❌ خطا در حذف (احتمالاً در سفارش استفاده شده).")
