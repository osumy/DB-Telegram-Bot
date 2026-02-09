from helpers import get_db_connection, is_logged_in
from keyboards import *


def register_comment_handlers(bot, user_sessions):
    @bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "⭐ نظرات")
    def comments_handler(message):
        bot.send_message(message.chat.id, "مدیریت نظرات:", reply_markup=submenu_keyboard('کامنت'))

    @bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "📄 لیست کامنت‌ها")
    def list_comments(message):
        conn = get_db_connection()
        cur = conn.cursor()
        query = """
            SELECT c.id, c.score, c.text, m.name, cust.first_name 
            FROM comments c
            LEFT JOIN menu_items m ON c.menu_item_id = m.id
            LEFT JOIN customers cust ON c.customer_id = cust.id
            ORDER BY c.id DESC LIMIT 10
        """
        cur.execute(query)
        rows = cur.fetchall()
        conn.close()

        if not rows:
            bot.send_message(message.chat.id, "هنوز هیچ نظری ثبت نشده است.")
            return

        txt = "⭐ آخرین نظرات ثبت شده:\n\n"
        for r in rows:
            txt += f"🆔 کد نظر: {r[0]}\n👤 مشتری: {r[4] or 'ناشناس'}\n🍔 غذا: {r[3] or 'نامشخص'}\nامتیاز: {r[1]} | متن: {r[2][:30]}...\n"
            txt += "------------------------\n"
        bot.send_message(message.chat.id, txt)

    @bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "➕ افزودن کامنت")
    def add_comment_s1(message):
        bot.send_message(message.chat.id, "کد سفارش (Order ID):")
        bot.register_next_step_handler(message, add_comment_s2)

    def add_comment_s2(message):
        user_sessions[message.chat.id]["new_comment"] = {"oid": message.text.strip()}
        bot.send_message(message.chat.id, "کد غذا (Menu Item ID):")
        bot.register_next_step_handler(message, add_comment_s3)

    def add_comment_s3(message):
        user_sessions[message.chat.id]["new_comment"]["fid"] = message.text.strip()
        bot.send_message(message.chat.id, "کد مشتری (Customer ID):")
        bot.register_next_step_handler(message, add_comment_s4)

    def add_comment_s4(message):
        user_sessions[message.chat.id]["new_comment"]["cid"] = message.text.strip()
        bot.send_message(message.chat.id, "امتیاز از 1 تا 5:")
        bot.register_next_step_handler(message, add_comment_s5)

    def add_comment_s5(message):
        val = message.text.strip()
        if not val.isdigit() or not (1 <= int(val) <= 5):
            bot.send_message(message.chat.id, "لطفاً فقط عدد بین 1 تا 5 بفرستید:")
            bot.register_next_step_handler(message, add_comment_s5)
            return
        user_sessions[message.chat.id]["new_comment"]["score"] = int(val)
        bot.send_message(message.chat.id, "متن نظر شما:")
        bot.register_next_step_handler(message, add_comment_final)

    def add_comment_final(message):
        data = user_sessions[message.chat.id]["new_comment"]
        text = message.text.strip()
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO comments (order_id, menu_item_id, customer_id, score, text)
                VALUES (%s, %s, %s, %s, %s)
            """, (data["oid"], data["fid"], data["cid"], data["score"], text))
            conn.commit()
            bot.send_message(message.chat.id, "✅ نظر با موفقیت ثبت شد.")
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ خطا در ثبت: {e}")
        finally:
            conn.close()

    @bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "✏️ ویرایش کامنت")
    def edit_comment_s1(message):
        bot.send_message(message.chat.id, "کد (ID) نظری که قصد ویرایش آن را دارید:")
        bot.register_next_step_handler(message, edit_comment_s2)

    def edit_comment_s2(message):
        cid = message.text.strip()
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, score, text FROM comments WHERE id=%s", (cid,))
        row = cur.fetchone()
        conn.close()

        if not row:
            bot.send_message(message.chat.id, "⚠️ نظری با این کد یافت نشد.")
            return

        user_sessions[message.chat.id]["edit_comment"] = {"id": row[0], "score": row[1], "text": row[2]}
        bot.send_message(message.chat.id, f"امتیاز فعلی: {row[1]}\nامتیاز جدید (یا -):")
        bot.register_next_step_handler(message, edit_comment_s3)

    def edit_comment_s3(message):
        if message.text.strip() != "-":
            user_sessions[message.chat.id]["edit_comment"]["score"] = message.text.strip()
        bot.send_message(message.chat.id,
                         f"متن فعلی: {user_sessions[message.chat.id]['edit_comment']['text']}\nمتن جدید (یا -):")
        bot.register_next_step_handler(message, edit_comment_final)

    def edit_comment_final(message):
        if message.text.strip() != "-":
            user_sessions[message.chat.id]["edit_comment"]["text"] = message.text.strip()

        data = user_sessions[message.chat.id]["edit_comment"]
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute("UPDATE comments SET score=%s, text=%s WHERE id=%s",
                        (data["score"], data["text"], data["id"]))
            conn.commit()
            bot.send_message(message.chat.id, "✅ نظر با موفقیت ویرایش شد.")
        finally:
            conn.close()

    @bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "🗑 حذف کامنت")
    def del_comment_s1(message):
        bot.send_message(message.chat.id, "کد (ID) نظر برای حذف:")
        bot.register_next_step_handler(message, del_comment_final)

    def del_comment_final(message):
        cid = message.text.strip()
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM comments WHERE id=%s", (cid,))
            conn.commit()
            bot.send_message(message.chat.id, f"🗑 نظر کد {cid} حذف شد.")
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ خطا در حذف: {e}")
        finally:
            conn.close()