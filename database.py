import aiosqlite
from typing import Tuple

DB_PATH = None  # устанавливается в main при старте


async def init_db(path: str):
    global DB_PATH
    DB_PATH = path
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            language TEXT DEFAULT 'ru',
            last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        await db.commit()


# ---- users ----
async def set_language(user_id: int, lang: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        INSERT INTO users (user_id, language, last_active)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(user_id) DO UPDATE SET language=excluded.language, last_active=CURRENT_TIMESTAMP
        """, (user_id, lang))
        await db.commit()


async def get_language(user_id: int) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT language FROM users WHERE user_id=?", (user_id,)) as cur:
            row = await cur.fetchone()
            return row[0] if row else "ru"


async def mark_active(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        INSERT INTO users (user_id, last_active)
        VALUES (?, CURRENT_TIMESTAMP)
        ON CONFLICT(user_id) DO UPDATE SET last_active=CURRENT_TIMESTAMP
        """, (user_id,))
        await db.commit()


# ---- videos ----
async def add_video(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO videos (user_id) VALUES (?)", (user_id,))
        await db.commit()


# ---- stats ----
async def get_daily_stats(date_str: str = None) -> Tuple[int, int]:
    """
    Возвращает (unique_users, videos_count) за дату.
    date_str — 'YYYY-MM-DD'. Если None — берём today localtime.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        if date_str:
            users_q = "SELECT COUNT(DISTINCT user_id) FROM users WHERE date(last_active) = ?"
            videos_q = "SELECT COUNT(*) FROM videos WHERE date(created_at) = ?"
            async with db.execute(users_q, (date_str,)) as cur:
                users_today = (await cur.fetchone())[0]
            async with db.execute(videos_q, (date_str,)) as cur:
                videos_today = (await cur.fetchone())[0]
        else:
            users_q = "SELECT COUNT(DISTINCT user_id) FROM users WHERE date(last_active) = date('now','localtime')"
            videos_q = "SELECT COUNT(*) FROM videos WHERE date(created_at) = date('now','localtime')"
            async with db.execute(users_q) as cur:
                users_today = (await cur.fetchone())[0]
            async with db.execute(videos_q) as cur:
                videos_today = (await cur.fetchone())[0]

        return users_today, videos_today
