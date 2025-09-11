import aiohttp
import logging
import os

logger = logging.getLogger("instagram_api")

RAPIDAPI_HOST = "instagram-reels-downloader-api.p.rapidapi.com"
API_KEY = os.getenv("RAPIDAPI_KEY", "5ea171444emsha62f97c0301c0d3p103820jsn8bdc7499963b")
PROXY_URL = "http://abc8176630_ofn0:05636634@108.165.157.48:6050"  # ⚡️ пример: http://user:pass@ip:port


async def get_instagram_video(url: str) -> str | None:
    """
    Получает прямой mp4 URL через RapidAPI Instagram Reels Downloader.
    Работает через прокси, если задан PROXY_URL.
    Возвращает None, если не удалось.
    """
    api_url = "https://instagram-reels-downloader-api.p.rapidapi.com/download"
    params = {"url": url}
    headers = {
        "x-rapidapi-host": RAPIDAPI_HOST,
        "x-rapidapi-key": API_KEY,
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                api_url, headers=headers, params=params, proxy=PROXY_URL
            ) as resp:
                if resp.status != 200:
                    logger.warning(f"Instagram API вернул статус {resp.status} для {url}")
                    return None

                try:
                    data = await resp.json(content_type=None)
                except Exception:
                    text = await resp.text()
                    logger.error(f"Не удалось распарсить JSON. Ответ: {text[:200]}")
                    return None

                # ✅ Парсим medias
                video_url = None
                medias = data.get("data", {}).get("medias", [])
                for media in medias:
                    if media.get("type") == "video":
                        video_url = media.get("url")
                        break

                if not video_url:
                    logger.warning(f"API не вернул video_url для {url} → {data}")
                return video_url
    except Exception as e:
        logger.error(f"Ошибка при запросе к Instagram API: {e}")
        return None
