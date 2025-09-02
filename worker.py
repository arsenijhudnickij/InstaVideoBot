import asyncio
import logging
import time
import os
import tempfile
from aiogram.types import FSInputFile, URLInputFile
from downloader import get_video_url
from queue_manager import task_queue, active_tasks
import yt_dlp

logger = logging.getLogger(__name__)

async def worker(bot, worker_id: int):
    while True:
        message, url = await task_queue.get()
        start_time = time.perf_counter()

        try:
            video_url, ext = get_video_url(url)
            if not video_url:
                await message.reply("❌ Не удалось получить видео. Возможно ссылка неверна.")
                continue

            caption = "Вот ваше видео 🎬"

            # Сначала пробуем отдать по URL (быстро, без скачивания)
            try:
                await message.reply_video(URLInputFile(video_url), caption=caption)
                logger.info(f"[Worker {worker_id}] ✅ Видео отправлено по URL: {url}")
            except Exception as e:
                logger.warning(f"[Worker {worker_id}] ⚠️ Ошибка URL {e}, качаем файл")

                with tempfile.TemporaryDirectory(prefix="igdl_") as tmpdir:
                    ydl_opts = {
                        "outtmpl": os.path.join(tmpdir, "%(id)s.%(ext)s"),
                        "format": "best[ext=mp4]/bestvideo[ext=mp4]+bestaudio/best",
                        "noplaylist": True,
                        "quiet": True,
                        "no_warnings": True,
                    }
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(url, download=True)
                        filepath = ydl.prepare_filename(info)

                    await message.reply_video(FSInputFile(filepath), caption=caption)
                    logger.info(f"[Worker {worker_id}] ✅ Видео скачано и отправлено: {url}")

        except Exception as e:
            logger.error(f"[Worker {worker_id}] ❌ Ошибка обработки {url}: {e}")
            await message.reply("❌ Ошибка при загрузке видео.")
        finally:
            elapsed = time.perf_counter() - start_time
            logger.info(f"[Worker {worker_id}] ⏱ {url} за {elapsed:.2f} сек")
            task_queue.task_done()
            active_tasks.pop(message.from_user.id, None)
