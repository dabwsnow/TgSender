import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', 0))
API_ID = int(os.getenv('API_ID', 0))
API_HASH = os.getenv('API_HASH')

SESSION_NAME = 'user_session'
DB_NAME = 'sender_bot.db'

INTERVALS = {
    'hour': 3600,
    'day': 86400
}
