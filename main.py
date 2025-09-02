import os
import logging
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv

load_dotenv()
from queue_manager import task_queue, active_tasks
from worker import worker

# Загружаем переменные окружения

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация Telegram-бота
bot = Bot(token=os.getenv("TELEGRAM_BOT_TOKEN"))
dp = Dispatcher()

# Читаем список каналов из .env
REQUIRED_CHANNELS = os.getenv("TG_CHANNELS", "").split(",")


async def check_subscription(user_id: int) -> bool:
    """Проверяем подписку пользователя на все каналы"""
    for channel in REQUIRED_CHANNELS:
        ch = channel.strip()
        if not ch:
            continue
        try:
            member = await bot.get_chat_member(ch, user_id)
            if member.status not in ("creator", "administrator", "member"):
                return False
        except Exception as e:
            logger.warning(f"Не удалось проверить подписку {user_id} на {ch}: {e}")
            return False
    return True


@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    text = "👋 Привет!\n\n"
    text += "Отправь мне ссылку на Instagram пост или Reels, и я пришлю тебе видео.\n\n"

    if any(REQUIRED_CHANNELS):
        text += "⚠️ Для использования бота нужно быть подписанным на все каналы:\n\n"
        for ch in REQUIRED_CHANNELS:
            if ch.strip():
                text += f"👉 {ch}\n"

        # Кнопка "Я подписался"
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="✅ Я подписался", callback_data="check_subs")]
            ]
        )
        await message.reply(text, reply_markup=keyboard)
    else:
        await message.reply(text)


@dp.callback_query(F.data == "check_subs")
async def process_check_subs(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    is_subscribed = await check_subscription(user_id)

    if is_subscribed:
        await callback.message.answer("✅ Отлично! Теперь можете отправлять ссылку на Instagram.")
    else:
        await callback.message.answer("⚠️ Вы ещё не подписаны на все каналы. Подпишитесь и попробуйте снова.")

    await callback.answer()  # убираем "часики" на кнопке


@dp.message()
async def handle_message(message: types.Message):
    url = message.text.strip()

    if not any(domain in url for domain in ["instagram.com", "instagr.am"]):
        await message.reply("⚠️ Пожалуйста, отправьте ссылку на Instagram.")
        return

    user_id = message.from_user.id

    # проверка подписки
    is_subscribed = await check_subscription(user_id)
    if not is_subscribed:
        # ... (твой код с клавиатурой)
        return

    # проверка на активную задачу
    if active_tasks.get(user_id):
        await message.reply("⏳ Подождите, пока я обработаю ваше предыдущее видео.")
        return

    # ставим в очередь
    active_tasks[user_id] = True
    await message.reply("⏳ Видео поставлено в очередь…")
    await task_queue.put((message, url))

async def main():
    # Запускаем несколько воркеров
    workers = [asyncio.create_task(worker(bot, i)) for i in range(5)]

    await dp.start_polling(bot)

    # Останавливаем воркеров при завершении
    for w in workers:
        w.cancel()


if __name__ == "__main__":
    asyncio.run(main())
