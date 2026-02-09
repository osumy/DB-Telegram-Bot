import telebot
from config import *
from handlers.auth import register_auth_handlers
from handlers.food_handlers import register_food_handlers
from handlers.customer_handlers import register_customer_handlers
from handlers.courier_handlers import register_courier_handlers
from handlers.order_handlers import register_order_handlers
from handlers.comment_handlers import register_comment_handlers

# Initialize Bot
bot = telebot.TeleBot(BOT_TOKEN)

register_auth_handlers(bot, user_sessions)
register_food_handlers(bot, user_sessions)
register_customer_handlers(bot, user_sessions)
register_courier_handlers(bot, user_sessions)
register_order_handlers(bot, user_sessions)
register_comment_handlers(bot, user_sessions)


if __name__ == "__main__":
    print("Bot is running...")
    bot.infinity_polling(timeout=10, long_polling_timeout=5)
