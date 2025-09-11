import os
import logging
import aiosqlite
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, BotCommand
from dotenv import load_dotenv
from datetime import datetime, timedelta

from queue_manager import task_queue, active_tasks, pending_requests
from worker import worker
from utils import check_subscription
from database import init_db, set_language, get_language, mark_active, get_daily_stats

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=os.getenv("TELEGRAM_BOT_TOKEN"))
dp = Dispatcher()

REQUIRED_CHANNELS = os.getenv("TG_CHANNELS", "").split(",")
DB_PATH = os.getenv("DB_PATH", "bot.db")
ADMINS = [int(x) for x in os.getenv("ADMINS", "").split(",") if x.strip()]

# -------- Сообщения -------- #
MESSAGES = {
    "ru": {
        "welcome_first": (
            "👋 Добро пожаловать!\n\n"
            "Этот бот поможет вам скачивать видео с Instagram 📲\n"
            "Всё очень просто: отправьте ссылку на пост, и я подготовлю для вас видео 🎬\n\n"
            "Ожидаю твоих ссылок 👇"
        ),
        "lang_changed": "✅ Язык изменён. Теперь можете продолжать работу!",
        "need_subs": "⚠️ Чтобы продолжить работу, подпишитесь на все партнерские каналы:\n\n",
        "btn_subscribed": "✅ Я подписался",
        "send_url": "⚠️ Пожалуйста, отправьте ссылку на Instagram.",
        "wait_prev": "⏳ Подождите, пока я обработаю ваше предыдущее видео.",
        "queued": "⏳ Видео поставлено в очередь…",
        "ready": "✅ Отлично! Теперь можете отправлять ссылку на Instagram.",
    },
    "en": {
        "welcome_first": (
            "👋 Welcome!\n\n"
            "This bot helps you download videos from Instagram 📲\n"
            "It’s simple: just send me a link to a post, and I’ll fetch the video 🎬\n\n"
            "I'm waiting for your links 👇"
        ),
        "lang_changed": "✅ Language changed. You can continue using the bot!",
        "need_subs": "⚠️ To continue, you must be subscribed to all partner channels:\n\n",
        "btn_subscribed": "✅ I subscribed",
        "send_url": "⚠️ Please send a valid Instagram link.",
        "wait_prev": "⏳ Please wait until your previous video is processed.",
        "queued": "⏳ Your video has been added to the queue…",
        "ready": "✅ Great! Now you can send an Instagram link.",
    }
}


async def get_lang(user_id: int) -> str:
    return await get_language(user_id)


# -------- Меню команд -------- #
async def set_bot_commands(bot: Bot):
    commands = [
        BotCommand(command="/lang", description="Сменить язык / Change language"),
    ]
    await bot.set_my_commands(commands)


# ----------- Требование подписки ----------- #
async def show_subscription_requirements(message: types.Message):
    user_id = message.from_user.id
    lang = await get_lang(user_id)

    text = MESSAGES[lang]["need_subs"]
    for ch in REQUIRED_CHANNELS:
        if ch.strip():
            text += f"👉 {ch}\n"

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=MESSAGES[lang]["btn_subscribed"], callback_data="check_subs")]]
    )
    await message.reply(text, reply_markup=keyboard)


# --------- /start --------- #
@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    user_id = message.from_user.id

    # Проверяем, есть ли пользователь в базе
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT 1 FROM users WHERE user_id=?", (user_id,)) as cur:
            exists = await cur.fetchone()

    if not exists:
        # Новый пользователь — сразу предложим выбрать язык
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(text="🇷🇺 Русский", callback_data="set_lang_ru"),
                InlineKeyboardButton(text="🇬🇧 English", callback_data="set_lang_en")
            ]]
        )
        await message.reply("🌎 Выберите язык / Choose your language:", reply_markup=keyboard)
        # Добавляем пользователя в БД с временной меткой
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
            await db.commit()
    else:
        # Существующий пользователь — берём язык из базы
        lang = await get_language(user_id)
        await mark_active(user_id)
        await message.reply(MESSAGES[lang]["welcome_first"])

# --------- /lang --------- #
@dp.message(Command("lang"))
async def change_language(message: types.Message):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="set_lang_ru"),
             InlineKeyboardButton(text="🇬🇧 English", callback_data="set_lang_en")]
        ]
    )
    await message.answer("🌎 Выберите язык / Choose your language:", reply_markup=keyboard)


# --------- Callback: выбор языка --------- #
@dp.callback_query(F.data.startswith("set_lang_"))
async def set_language_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    choice = callback.data.split("_")[-1]

    if choice not in ("ru", "en"):
        await callback.answer()
        return

    await set_language(user_id, choice)

    try:
        await callback.message.delete()
    except:
        pass

    await callback.message.answer(MESSAGES[choice]["lang_changed"])
    await callback.answer()


# --------- Callback: проверка подписки --------- #
@dp.callback_query(F.data == "check_subs")
async def process_check_subs(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    lang = await get_lang(user_id)

    is_subscribed = await check_subscription(bot, user_id, REQUIRED_CHANNELS)
    if is_subscribed:
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except:
            pass

        pending = pending_requests.pop(user_id, None)
        if pending:
            orig_message, url = pending
            if user_id in active_tasks:
                await callback.message.answer(MESSAGES[lang]["wait_prev"])
            else:
                queued_msg = await orig_message.reply(MESSAGES[lang]["queued"])
                active_tasks[user_id] = queued_msg
                await task_queue.put((orig_message, url))
        else:
            await callback.message.answer(MESSAGES[lang]["ready"])
    else:
        pending = pending_requests.get(user_id)
        if pending:
            orig_message, _ = pending
            await show_subscription_requirements(orig_message)
        else:
            await show_subscription_requirements(callback.message)

    await callback.answer()


# --------- Обработка ссылок --------- #
@dp.message()
async def handle_message(message: types.Message):
    user_id = message.from_user.id
    lang = await get_lang(user_id)
    await mark_active(user_id)
    url = message.text.strip()

    if not any(domain in url for domain in ["instagram.com", "instagr.am"]):
        await message.reply(MESSAGES[lang]["send_url"])
        return

    if user_id in active_tasks:
        await message.reply(MESSAGES[lang]["wait_prev"])
        return

    is_subscribed = await check_subscription(bot, user_id, REQUIRED_CHANNELS)
    if is_subscribed:
        queued_msg = await message.reply(MESSAGES[lang]["queued"])
        active_tasks[user_id] = queued_msg
        await task_queue.put((message, url))
    else:
        pending_requests[user_id] = (message, url)
        await show_subscription_requirements(message)


# --------- Планировщик статистики --------- #
async def daily_stats_task():
    while True:
        now = datetime.now()
        tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        wait_seconds = (tomorrow - now).total_seconds()
        await asyncio.sleep(wait_seconds)

        users_today, videos_today = await get_daily_stats()
        text = f"📊 Daily stats:\n👥 Users: {users_today}\n🎬 Videos: {videos_today}"

        for admin_id in ADMINS:
            try:
                await bot.send_message(admin_id, text)
            except Exception as e:
                logger.warning(f"Не удалось отправить статистику админу {admin_id}: {e}")


# --------- Запуск --------- #
async def main():
    await init_db(DB_PATH)
    await set_bot_commands(bot)

    workers = [asyncio.create_task(worker(bot, i, REQUIRED_CHANNELS)) for i in range(5)]
    asyncio.create_task(daily_stats_task())

    await dp.start_polling(bot)

    for w in workers:
        w.cancel()


if __name__ == "__main__":
    asyncio.run(main())
