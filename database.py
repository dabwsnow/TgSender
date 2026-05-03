import aiosqlite
from config import DB_NAME

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS scheduled_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_text TEXT,
                media_path TEXT,
                media_type TEXT,
                chat_ids TEXT,
                interval_seconds INTEGER,
                next_send_time INTEGER,
                is_active INTEGER DEFAULT 1
            )
        ''')

        await db.execute('''
            CREATE TABLE IF NOT EXISTS user_session (
                id INTEGER PRIMARY KEY,
                phone TEXT,
                is_authorized INTEGER DEFAULT 0
            )
        ''')

        await db.commit()

async def save_scheduled_message(message_text, media_path, media_type, chat_ids, interval_seconds, next_send_time):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''
            INSERT INTO scheduled_messages
            (message_text, media_path, media_type, chat_ids, interval_seconds, next_send_time)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (message_text, media_path, media_type, chat_ids, interval_seconds, next_send_time))
        await db.commit()

async def get_active_scheduled_messages():
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('''
            SELECT id, message_text, media_path, media_type, chat_ids, interval_seconds, next_send_time
            FROM scheduled_messages WHERE is_active = 1
        ''') as cursor:
            return await cursor.fetchall()

async def update_next_send_time(message_id, next_send_time):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''
            UPDATE scheduled_messages SET next_send_time = ? WHERE id = ?
        ''', (next_send_time, message_id))
        await db.commit()

async def delete_scheduled_message(message_id):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('DELETE FROM scheduled_messages WHERE id = ?', (message_id,))
        await db.commit()

async def save_user_session(phone):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''
            INSERT OR REPLACE INTO user_session (id, phone, is_authorized)
            VALUES (1, ?, 1)
        ''', (phone,))
        await db.commit()

async def get_user_session():
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('SELECT phone, is_authorized FROM user_session WHERE id = 1') as cursor:
            return await cursor.fetchone()

async def update_broadcast_message(message_id, message_text, media_path, media_type):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''
            UPDATE scheduled_messages
            SET message_text = ?, media_path = ?, media_type = ?
            WHERE id = ?
        ''', (message_text, media_path, media_type, message_id))
        await db.commit()

async def update_broadcast_chats(message_id, chat_ids):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''
            UPDATE scheduled_messages SET chat_ids = ? WHERE id = ?
        ''', (chat_ids, message_id))
        await db.commit()

async def update_broadcast_interval(message_id, interval_seconds):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''
            UPDATE scheduled_messages SET interval_seconds = ? WHERE id = ?
        ''', (interval_seconds, message_id))
        await db.commit()
