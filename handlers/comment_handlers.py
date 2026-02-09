from helpers import get_db_connection, is_logged_in
from keyboards import *

def register_comment_handlers(bot, user_sessions):
    @bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "⭐ نظرات")
    def comments_handler(message):
        bot.send_message(message.chat.id, "مدیریت نظرات:", reply_markup=submenu_keyboard('کامنت'))

    @bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "➕ ثبت نظر جدید")
    def add_comment_s1(message):
        bot.send_message(message.chat.id, "کد سفارش:")
        bot.register_next_step_handler(message, add_comment_s2)

    def add_comment_s2(message):
        user_sessions[message.chat.id]["new_comment"] = {"oid": message.text.strip()}
        bot.send_message(message.chat.id, "کد غذا:")
        bot.register_next_step_handler(message, add_comment_s3)

    def add_comment_s3(message):
        user_sessions[message.chat.id]["new_comment"]["fid"] = message.text.strip()
        bot.send_message(message.chat.id, "کد مشتری:")
        bot.register_next_step_handler(message, add_comment_s4)

    def add_comment_s4(message):
        user_sessions[message.chat.id]["new_comment"]["cid"] = message.text.strip()
        bot.send_message(message.chat.id, "امتیاز (1-5):")
        bot.register_next_step_handler(message, add_comment_s5)

    def add_comment_s5(message):
        user_sessions[message.chat.id]["new_comment"]["score"] = message.text.strip()
        bot.send_message(message.chat.id, "متن نظر:")
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
            bot.send_message(message.chat.id, "✅ نظر ثبت شد.")
        except Exception as e:
            bot.send_message(message.chat.id, f"Error: {e}")
        finally:
            conn.close()

    @bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "📄 مشاهده نظرات غذا")
    def list_comments_s1(message):
        bot.send_message(message.chat.id, "کد غذا:")
        bot.register_next_step_handler(message, list_comments_final)

    def list_comments_final(message):
        fid = message.text.strip()
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT score, text FROM comments WHERE menu_item_id=%s ORDER BY id DESC LIMIT 5", (fid,))
        rows = cur.fetchall()
        conn.close()

        txt = f"نظرات غذای #{fid}:\n"
        if not rows: txt = "نظری نیست."
        for r in rows:
            txt += f"⭐ {r[0]} | {r[1]}\n"
        bot.send_message(message.chat.id, txt)
