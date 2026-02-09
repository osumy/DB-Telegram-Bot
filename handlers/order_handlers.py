from helpers import get_db_connection, is_logged_in
from keyboards import *

def register_order_handlers(bot, user_sessions):
    @bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "🧾 سفارش‌ها")
    def order_handler(message):
        bot.send_message(message.chat.id, "مدیریت سفارش‌ها:", reply_markup=submenu_keyboard("سفارش"))

    @bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "📄 لیست سفارش‌ها")
    def list_orders(message):
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, customer_id, total_price, status, created_at FROM orders ORDER BY id DESC LIMIT 10")
        rows = cur.fetchall()
        conn.close()

        txt = "🧾 آخرین سفارش‌ها:\n\n"
        if not rows: txt = "خالی."
        for r in rows:
            txt += f"🆔 {r[0]} | مشتری: {r[1]} | مبلغ: {r[2]}\nوضعیت: {r[3]} | زمان: {r[4].strftime('%Y-%m-%d %H:%M')}\n-----------------\n"
        bot.send_message(message.chat.id, txt)

    @bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "➕ افزودن سفارش")
    def add_order_s1(message):
        bot.send_message(message.chat.id, "کد مشتری:")
        bot.register_next_step_handler(message, add_order_s2)

    def add_order_s2(message):
        user_sessions[message.chat.id]["new_order"] = {"cid": message.text.strip()}
        bot.send_message(message.chat.id, "آیتم‌ها (کدغذا:تعداد , ...)\nمثال: 1:2, 5:1")
        bot.register_next_step_handler(message, add_order_s3)

    def add_order_s3(message):
        cid = user_sessions[message.chat.id]["new_order"]["cid"]
        raw = message.text.strip()

        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO orders (customer_id, status, order_type, total_price) VALUES (%s, 'pending', 'delivery', 0) RETURNING id",
                (cid,))
            oid = cur.fetchone()[0]

            total = 0
            for item in raw.split(","):
                if ":" not in item: continue
                fid, qty = item.split(":")
                fid, qty = int(fid), int(qty)

                cur.execute("SELECT price FROM menu_items WHERE id=%s", (fid,))
                res = cur.fetchone()
                if not res: continue
                price = float(res[0])
                item_total = price * qty
                total += item_total

                cur.execute(
                    "INSERT INTO order_items (order_id, menu_item_id, quantity, unit_price, total_price) VALUES (%s,%s,%s,%s,%s)",
                    (oid, fid, qty, price, item_total))

            cur.execute("UPDATE orders SET total_price=%s WHERE id=%s", (total, oid))
            conn.commit()
            bot.send_message(message.chat.id, f"✅ سفارش #{oid} ثبت شد. مبلغ: {total}")
        except Exception as e:
            bot.send_message(message.chat.id, f"خطا: {e}")
        finally:
            conn.close()

    @bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "✏️ ویرایش سفارش")
    def edit_order_s1(message):
        bot.send_message(message.chat.id, "کد سفارش:")
        bot.register_next_step_handler(message, edit_order_final)

    def edit_order_final(message):
        # Simplified edit: just toggle status for now or change status text
        oid = message.text.strip()
        user_sessions[message.chat.id]["edit_order"] = {"id": oid}
        bot.send_message(message.chat.id, "وضعیت جدید (pending, delivered, cancelled):")
        bot.register_next_step_handler(message, edit_order_save)

    def edit_order_save(message):
        status = message.text.strip()
        oid = user_sessions[message.chat.id]["edit_order"]["id"]
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE orders SET status=%s WHERE id=%s", (status, oid))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, "✅ وضعیت سفارش تغییر کرد.")

    @bot.message_handler(func=lambda m: is_logged_in(m.chat.id) and m.text == "🗑 حذف سفارش")
    def del_order_s1(message):
        bot.send_message(message.chat.id, "کد سفارش:")
        bot.register_next_step_handler(message, del_order_final)

    def del_order_final(message):
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM orders WHERE id=%s", (message.text.strip(),))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, "🗑 سفارش حذف شد.")