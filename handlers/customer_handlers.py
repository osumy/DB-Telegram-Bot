from helpers import get_db_connection, is_logged_in
from keyboards import *

def register_customer_handlers(bot, user_sessions):
    @bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "👥 مشتریان")
    def customer_handler(message):
        bot.send_message(message.chat.id, "مدیریت مشتریان:", reply_markup=submenu_keyboard("مشتری"))

    @bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "📄 لیست مشتری‌ها")
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
    def add_cust_s1(message):
        bot.send_message(message.chat.id, "نام مشتری:")
        bot.register_next_step_handler(message, add_cust_s2)

    def add_cust_s2(message):
        user_sessions[message.chat.id]["new_cust"] = {"fname": message.text.strip()}
        bot.send_message(message.chat.id, "نام خانوادگی:")
        bot.register_next_step_handler(message, add_cust_s3)

    def add_cust_s3(message):
        user_sessions[message.chat.id]["new_cust"]["lname"] = message.text.strip()
        bot.send_message(message.chat.id, "شماره تلفن:")
        bot.register_next_step_handler(message, add_cust_s4)

    def add_cust_s4(message):
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
            cid = cur.fetchone()[0]
            cur.execute("INSERT INTO customer_phones (phone, customer_id) VALUES (%s, %s)", (data["phone"], cid))
            if address != "-":
                cur.execute("INSERT INTO customer_address (address, customer_id) VALUES (%s, %s)", (address, cid))
            conn.commit()
            bot.send_message(message.chat.id, f"✅ مشتری {cid} ثبت شد.")
        finally:
            conn.close()

    @bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "✏️ ویرایش مشتری")
    def edit_cust_s1(message):
        bot.send_message(message.chat.id, "کد مشتری:")
        bot.register_next_step_handler(message, edit_cust_s2)

    def edit_cust_s2(message):
        cid = message.text.strip()
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT c.id, c.first_name, c.last_name, cp.phone, ca.address
            FROM customers c
            LEFT JOIN customer_phones cp ON c.id = cp.customer_id
            LEFT JOIN customer_address ca ON c.id = ca.customer_id
            WHERE c.id=%s
        """, (cid,))
        row = cur.fetchone()
        conn.close()

        if not row:
            bot.send_message(message.chat.id, "مشتری یافت نشد.")
            return

        user_sessions[message.chat.id]["edit_cust"] = {"id": row[0], "fname": row[1], "lname": row[2], "phone": row[3],
                                                       "addr": row[4]}
        txt = f"نام فعلی: {row[1]} {row[2]}\nتلفن: {row[3]}\nآدرس: {row[4]}\n\nنام جدید (یا -):"
        bot.send_message(message.chat.id, txt)
        bot.register_next_step_handler(message, edit_cust_s3)

    def edit_cust_s3(message):
        if message.text.strip() != "-": user_sessions[message.chat.id]["edit_cust"]["fname"] = message.text.strip()
        bot.send_message(message.chat.id, "نام خانوادگی جدید (یا -):")
        bot.register_next_step_handler(message, edit_cust_s4)

    def edit_cust_s4(message):
        if message.text.strip() != "-": user_sessions[message.chat.id]["edit_cust"]["lname"] = message.text.strip()
        bot.send_message(message.chat.id, "تلفن جدید (یا -):")
        bot.register_next_step_handler(message, edit_cust_s5)

    def edit_cust_s5(message):
        if message.text.strip() != "-": user_sessions[message.chat.id]["edit_cust"]["phone"] = message.text.strip()
        bot.send_message(message.chat.id, "آدرس جدید (یا -):")
        bot.register_next_step_handler(message, edit_cust_final)

    def edit_cust_final(message):
        if message.text.strip() != "-": user_sessions[message.chat.id]["edit_cust"]["addr"] = message.text.strip()
        data = user_sessions[message.chat.id]["edit_cust"]

        conn = get_db_connection()
        cur = conn.cursor()
        # Update Name
        cur.execute("UPDATE customers SET first_name=%s, last_name=%s WHERE id=%s",
                    (data["fname"], data["lname"], data["id"]))
        # Update Phone (Delete old, insert new)
        cur.execute("DELETE FROM customer_phones WHERE customer_id=%s", (data["id"],))
        if data["phone"]: cur.execute("INSERT INTO customer_phones (customer_id, phone) VALUES (%s, %s)",
                                      (data["id"], data["phone"]))
        # Update Address
        cur.execute("DELETE FROM customer_address WHERE customer_id=%s", (data["id"],))
        if data["addr"]: cur.execute("INSERT INTO customer_address (customer_id, address) VALUES (%s, %s)",
                                     (data["id"], data["addr"]))

        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, "✅ مشتری ویرایش شد.")

    @bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "🗑 حذف مشتری")
    def del_cust_s1(message):
        bot.send_message(message.chat.id, "کد مشتری:")
        bot.register_next_step_handler(message, del_cust_final)

    def del_cust_final(message):
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM customers WHERE id=%s", (message.text.strip(),))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, "🗑 مشتری حذف شد.")
