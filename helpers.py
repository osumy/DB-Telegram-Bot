import psycopg2
from psycopg2 import Error
from functools import wraps
from config import DB_URI, user_sessions

def get_db_connection():
    try:
        return psycopg2.connect(DB_URI)
    except Error as e:
        print(f"DB Error: {e}")
        return None

def is_logged_in(chat_id):
    return user_sessions.get(chat_id, {}).get("logged_in", False)

def login_required(bot):
    def decorator(func):
        @wraps(func)
        def wrapper(message, *args, **kwargs):
            if not is_logged_in(message.chat.id):
                bot.send_message(message.chat.id, "⛔ دسترسی غیرمجاز. لطفاً ابتدا وارد شوید: /start")
                return
            return func(message, *args, **kwargs)
        return wrapper
    return decorator