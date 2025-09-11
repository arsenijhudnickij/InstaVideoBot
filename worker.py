import logging
import time
from aiogram.types import URLInputFile
from instagram_api import get_instagram_video
from queue_manager import task_queue, active_tasks
from utils import check_subscription
from database import get_language

logger = logging.getLogger(__name__)


async def worker(bot, worker_id: int, required_channels: list[str]):
    """
    Асинхронный воркер, который обрабатывает очередь видео.
    Принимает (message, url).
    В finally удаляет queued-сообщение (если оно было) из active_tasks.
    """
    while True:
        message, url = await task_queue.get()
        start_time = time.perf_counter()
        user_id = message.from_user.id

        try:
            lang = await get_language(user_id)

            # Проверка подписки
            is_subscribed = await check_subscription(bot, user_id, required_channels)
            if not is_subscribed:
                from main import show_subscription_requirements
                await show_subscription_requirements(message)
                continue

            # Получаем mp4 URL через RapidAPI
            video_url = await get_instagram_video(url)
            if not video_url:
                msg = (
                    "❌ Не удалось получить видео. Попробуйте другую ссылку."
                    if lang == "ru"
                    else "❌ Could not retrieve the video. Try another link."
                )
                await message.reply(msg)
                continue

            caption = "Вот ваше видео 🎬" if lang == "ru" else "Here is your video 🎬"
            await message.reply_video(URLInputFile(video_url), caption=caption)
            logger.info(f"[Worker {worker_id}] ✅ Видео отправлено по URL: {url}")

        except Exception as e:
            logger.error(f"[Worker {worker_id}] ❌ Ошибка обработки {url}: {e}")
            msg = (
                "❌ Ошибка при загрузке видео." if lang == "ru" else "❌ Error while downloading video."
            )
            try:
                await message.reply(msg)
            except Exception:
                logger.exception("Не удалось отправить сообщение об ошибке пользователю.")

        finally:
            elapsed = time.perf_counter() - start_time
            logger.info(f"[Worker {worker_id}] ⏱ {url} обработано за {elapsed:.2f} сек")
            task_queue.task_done()

            queued_msg = active_tasks.pop(user_id, None)
            if queued_msg:
                try:
                    await bot.delete_message(queued_msg.chat.id, queued_msg.message_id)
                except Exception as e:
                    logger.debug(f"[Worker {worker_id}] Не удалось удалить queued_msg: {e}")
