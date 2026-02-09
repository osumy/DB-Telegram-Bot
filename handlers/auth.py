from telebot import types
import keyboards as kb
from helpers import get_db_connection

def register_auth_handlers(bot, user_sessions):
    @bot.message_handler(commands=["start"])
    def start_command(message):
        chat_id = message.chat.id
        # Check if session exists and user is logged in
        if user_sessions.get(chat_id, {}).get("logged_in"):
            bot.send_message(chat_id, "🍽️ خوش آمدید! منوی اصلی:", reply_markup=kb.main_menu_keyboard())
        else:
            bot.send_message(chat_id, "🍽️ سیستم مدیریت رستوران\nلطفاً نام خود را وارد کنید:",
                             reply_markup=types.ReplyKeyboardRemove())
            bot.register_next_step_handler(message, lambda m: process_login_name(m, bot, user_sessions))

    def process_login_name(message, bot, user_sessions):
        name = message.text.strip()
        user_sessions[message.chat.id] = {"temp_name": name}
        bot.send_message(message.chat.id, "📱 شماره تلفن خود را وارد کنید:")
        bot.register_next_step_handler(message, lambda m: process_login_phone(m, bot, user_sessions))

    def process_login_phone(message, bot, user_sessions):
        chat_id = message.chat.id
        phone = message.text.strip()
        name = user_sessions.get(chat_id, {}).get("temp_name", "")

        conn = get_db_connection()
        if not conn:
            bot.send_message(chat_id, "❌ Database connection error.")
            return

        try:
            cur = conn.cursor()
            # Authentication based on first_name, phone and admin role
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
                bot.send_message(chat_id, "✅ ورود موفقیت‌آمیز.", reply_markup=kb.main_menu_keyboard())
            else:
                bot.send_message(chat_id, "❌ اطلاعات صحیح نیست یا دسترسی ادمین ندارید. /start")
        except Exception as e:
            bot.send_message(chat_id, f"Error: {e}")
        finally:
            conn.close()

    @bot.message_handler(func=lambda m: m.text == "🚪 خروج")
    def logout(message):
        user_sessions.pop(message.chat.id, None)
        bot.send_message(message.chat.id, "خارج شدید.", reply_markup=types.ReplyKeyboardRemove())

    @bot.message_handler(func=lambda m: m.text == "⬅️ بازگشت")
    def back_to_main(message):
        bot.send_message(message.chat.id, "منوی اصلی:", reply_markup=kb.main_menu_keyboard())