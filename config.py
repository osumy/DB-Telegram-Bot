import  os

BOT_TOKEN = os.environ.get("BOT_TOKEN")
DB_URI = os.environ.get("DB_URI")

if not BOT_TOKEN or not DB_URI:
    raise RuntimeError("Error: BOT_TOKEN or DB_URI is missing.")

# Global session storage
user_sessions = {}



