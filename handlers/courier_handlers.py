from helpers import get_db_connection, is_logged_in
from keyboards import *

def register_courier_handlers(bot, user_sessions):
    @bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "🚴‍♂️ پیک‌ها")
    def courier_handler(message):
        bot.send_message(message.chat.id, "مدیریت پیک‌ها:", reply_markup=submenu_keyboard("پیک"))

    @bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "📄 لیست پیک‌ها")
    def list_couriers(message):
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, first_name, last_name, phone, status FROM couriers ORDER BY id")
        rows = cur.fetchall()
        conn.close()

        txt = "🚴‍♂️ پیک‌ها:\n\n"
        if not rows: txt = "لیست خالی است."
        for r in rows:
            txt += f"🆔 {r[0]} | {r[1]} {r[2]}\n📞 {r[3]} | وضعیت: {r[4]}\n-----------------\n"
        bot.send_message(message.chat.id, txt)

    @bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "➕ افزودن پیک")
    def add_cour_s1(message):
        bot.send_message(message.chat.id, "نام پیک:")
        bot.register_next_step_handler(message, add_cour_s2)

    def add_cour_s2(message):
        user_sessions[message.chat.id]["new_cour"] = {"fname": message.text.strip()}
        bot.send_message(message.chat.id, "نام خانوادگی:")
        bot.register_next_step_handler(message, add_cour_s3)

    def add_cour_s3(message):
        user_sessions[message.chat.id]["new_cour"]["lname"] = message.text.strip()
        bot.send_message(message.chat.id, "تلفن:")
        bot.register_next_step_handler(message, add_cour_s4)

    def add_cour_s4(message):
        user_sessions[message.chat.id]["new_cour"]["phone"] = message.text.strip()
        data = user_sessions[message.chat.id]["new_cour"]

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO couriers (first_name, last_name, phone, status) VALUES (%s, %s, %s, 'available') RETURNING id",
            (data["fname"], data["lname"], data["phone"]))
        cid = cur.fetchone()[0]
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, f"✅ پیک {cid} ثبت شد.")

    @bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "✏️ ویرایش پیک")
    def edit_cour_s1(message):
        bot.send_message(message.chat.id, "کد پیک:")
        bot.register_next_step_handler(message, edit_cour_s2)

    def edit_cour_s2(message):
        cid = message.text.strip()
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, first_name, last_name, phone, address, status FROM couriers WHERE id=%s", (cid,))
        row = cur.fetchone()
        conn.close()

        if not row:
            bot.send_message(message.chat.id, "پیک یافت نشد.")
            return

        user_sessions[message.chat.id]["edit_cour"] = {"id": row[0], "fname": row[1], "lname": row[2], "phone": row[3],
                                                       "addr": row[4], "status": row[5]}
        txt = f"ویرایش #{row[0]}\nنام: {row[1]} {row[2]}\nتلفن: {row[3]}\nآدرس: {row[4]}\nوضعیت: {row[5]}\n\nنام جدید (یا -):"
        bot.send_message(message.chat.id, txt)
        bot.register_next_step_handler(message, edit_cour_s3)

    def edit_cour_s3(message):
        if message.text.strip() != "-": user_sessions[message.chat.id]["edit_cour"]["fname"] = message.text.strip()
        bot.send_message(message.chat.id, "نام خانوادگی جدید (یا -):")
        bot.register_next_step_handler(message, edit_cour_s4)

    def edit_cour_s4(message):
        if message.text.strip() != "-": user_sessions[message.chat.id]["edit_cour"]["lname"] = message.text.strip()
        bot.send_message(message.chat.id, "تلفن جدید (یا -):")
        bot.register_next_step_handler(message, edit_cour_s5)

    def edit_cour_s5(message):
        if message.text.strip() != "-": user_sessions[message.chat.id]["edit_cour"]["phone"] = message.text.strip()
        bot.send_message(message.chat.id, "آدرس جدید (یا -):")
        bot.register_next_step_handler(message, edit_cour_s6)

    def edit_cour_s6(message):
        if message.text.strip() != "-": user_sessions[message.chat.id]["edit_cour"]["addr"] = message.text.strip()
        bot.send_message(message.chat.id, "وضعیت جدید (یا -):")
        bot.register_next_step_handler(message, edit_cour_final)

    def edit_cour_final(message):
        if message.text.strip() != "-": user_sessions[message.chat.id]["edit_cour"]["status"] = message.text.strip()
        data = user_sessions[message.chat.id]["edit_cour"]

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE couriers SET first_name=%s, last_name=%s, phone=%s, address=%s, status=%s WHERE id=%s",
                    (data["fname"], data["lname"], data["phone"], data["addr"], data["status"], data["id"]))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, "✅ ویرایش پیک انجام شد.")

    @bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "🗑 حذف پیک")
    def del_cour_s1(message):
        bot.send_message(message.chat.id, "کد پیک برای حذف:")
        bot.register_next_step_handler(message, del_cour_final)

    def del_cour_final(message):
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM couriers WHERE id=%s", (message.text.strip(),))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, "🗑 پیک حذف شد.")