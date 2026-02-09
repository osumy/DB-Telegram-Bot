from telebot import types

def main_menu_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add("📋 منوی غذاها", "👥 مشتریان", "🚴‍♂️ پیک‌ها", "🧾 سفارش‌ها", "⭐ نظرات", "🚪 خروج")
    return kb

def submenu_keyboard(item_type):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    # دقیقا همین متن‌ها باید در هندلرها چک شوند
    kb.add(f"➕ افزودن {item_type}", f"📄 لیست {item_type}‌ها", f"✏️ ویرایش {item_type}", f"🗑 حذف {item_type}", "⬅️ بازگشت")
    return kb
